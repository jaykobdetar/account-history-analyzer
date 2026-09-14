#!/usr/bin/env python3
"""Read recorded costs after both batches finish; never run an AHAS analysis.

This review script deliberately reads no evaluation scores or source text values.
Input JSONL files are only counted, and original-study bytes are only hashed.
All paths and record identifiers from source histories remain out of the report.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import statistics


JSON_LIMIT = 1024 * 1024


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path):
    if path.stat().st_size > JSON_LIMIT:
        raise ValueError('Review metadata exceeds the fixed 1 MiB read limit')
    return json.loads(path.read_text(encoding='utf-8'))


def resolve_under(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('Path escapes its declared root')
    return path


def stats(values):
    values = list(values)
    if not values:
        return {'count': 0, 'minimum': None, 'median': None, 'maximum': None, 'sum': None}
    return {'count': len(values), 'minimum': min(values),
            'median': statistics.median(values), 'maximum': max(values), 'sum': sum(values)}


def configuration_identity():
    from account_history_analyzer.config import AnalysisConfig
    from account_history_analyzer.io import canonical_digest
    # Match the public analytical identity: resource IDs/content hashes replace
    # local paths, and an absent Delta reference is explicit null.
    return canonical_digest(AnalysisConfig.from_toml().analytical())


def regular_files(root: Path):
    if not root.is_dir():
        raise ValueError('Expected output directory is absent')
    result = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlinks are not accepted in reviewed artifacts')
        if path.is_file():
            result.append(path)
    return result


def size_files(paths):
    files = [p.stat() for p in paths]
    return {'file_count': len(files), 'logical_bytes': sum(p.st_size for p in files),
            'allocated_bytes': sum(p.st_blocks * 512 for p in files),
            'largest_file_bytes': max((p.st_size for p in files), default=0)}


def bundle_stats(path: Path, limits: dict):
    files = regular_files(path)
    names = {str(p.relative_to(path)): p for p in files}
    checksums = read_json(path / 'checksums.json')
    canonical = {'checksums.json'} | set(checksums)
    if not canonical.issubset(names):
        raise ValueError('Published checksum manifest names an absent artifact')
    for name in canonical:
        resolve_under(path, name)
    for metadata in ('checksums.json', 'resolved_config.json'):
        if metadata in names and names[metadata].stat().st_size > JSON_LIMIT:
            raise ValueError('Published metadata exceeds the fixed metadata cap')
    out = size_files(files)
    out.update(canonical_file_count=len(canonical),
               canonical_bytes=sum(names[n].stat().st_size for n in canonical),
               operational_receipt_bytes=sum(p.stat().st_size for n, p in names.items() if n not in canonical),
               checksum_manifest_sha256=sha_file(path / 'checksums.json'))
    out['within_artifact_limits'] = (out['file_count'] <= limits['max_files']
                                    and out['logical_bytes'] <= limits['max_total_bytes']
                                    and out['largest_file_bytes'] <= limits['max_file_bytes'])
    return out


def recorded_cost(root: Path, path: Path):
    receipt = read_json(path)
    prefix = str(path)[:-len('.receipt.json')]
    for key, suffix in (('stdout_sha256', '.stdout.log'), ('stderr_sha256', '.stderr.log')):
        if sha_file(Path(prefix + suffix)) != receipt[key]:
            raise ValueError('A recorded command log no longer matches its receipt')
    return {'receipt': str(path.relative_to(root)), 'receipt_sha256': sha_file(path),
            'exit_code': receipt['exit_code'], 'wall_seconds': receipt['wall_seconds'],
            'peak_rss_kib': receipt['peak_rss_kib'],
            'receipt_bytes': path.stat().st_size,
            'captured_log_bytes': sum(Path(prefix + s).stat().st_size for s in ('.stdout.log', '.stderr.log'))}


def input_workload(root: Path, dataset: Path | None, input_path: Path | None = None,
                   manifest_path: Path | None = None):
    """Return file/row counts, without reading any authored JSON string values."""
    data_files, all_files = set(), set()
    if dataset is not None:
        doc = read_json(dataset)
        all_files.add(dataset.resolve())
        entries = doc.get('texts', doc.get('streams', []))
        if not entries:
            raise ValueError('A registered dataset has no source entries')
        for entry in entries:
            source = resolve_under(root, str((dataset.parent / entry['input']).relative_to(root)))
            manifest = resolve_under(root, str((dataset.parent / entry['manifest']).relative_to(root)))
            data_files.add(source)
            all_files.update((source, manifest))
    else:
        if input_path is None or manifest_path is None:
            raise ValueError('Analysis case needs its input and manifest')
        data_files.add(input_path)
        all_files.update((input_path, manifest_path))
    rows = 0
    for path in data_files:
        with path.open('rb') as f:
            rows += sum(bool(line.strip()) for line in f)
    return {'distinct_input_files': len(data_files),
            'record_rows_in_distinct_input_files': rows,
            'dataset_input_and_manifest_bytes': sum(p.stat().st_size for p in all_files)}


def summarize_cases(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row['execution_class']].append(row)
    result = {}
    for name, values in sorted(groups.items()):
        bundles = [r['bundle'] for r in values if r['bundle'] is not None]
        measured = [r for r in values if r['inner_run_receipt'] is not None]
        result[name] = {
            'scheduled_slots': len(values),
            'analyzer_invocations': sum(r['analyzer_invoked'] for r in values),
            'status_counts': dict(sorted(Counter(r['status'] for r in values).items())),
            'outer_wall_seconds': stats(r['outer_receipt']['wall_seconds'] for r in values),
            'outer_peak_rss_kib': stats(r['outer_receipt']['peak_rss_kib'] for r in values),
            'inner_runtime_seconds': stats(r['inner_run_receipt']['runtime_seconds'] for r in measured),
            'inner_peak_process_rss_kib': stats(r['inner_run_receipt']['peak_process_rss_kib'] for r in measured),
            'input_record_rows': stats(r['input_workload']['record_rows_in_distinct_input_files']
                                      for r in values if r['input_workload'] is not None),
            'input_bytes': stats(r['input_workload']['dataset_input_and_manifest_bytes']
                                for r in values if r['input_workload'] is not None),
            'output_logical_bytes': stats(b['logical_bytes'] for b in bundles),
            'output_allocated_bytes': stats(b['allocated_bytes'] for b in bundles),
            'largest_output_file_bytes': stats(b['largest_file_bytes'] for b in bundles),
            'output_file_count': stats(b['file_count'] for b in bundles),
            'canonical_output_bytes': stats(b['canonical_bytes'] for b in bundles),
            'operational_receipt_bytes': stats(b['operational_receipt_bytes'] for b in bundles),
        }
    return result


def resource_rows(root: Path, freeze: dict, config: dict):
    paired_index = read_json(root / 'outputs/paired/execution-index.json')
    stream_index = read_json(root / 'outputs/streams/execution-index.json')
    freeze_sha = sha_file(root / 'protocol/scoring-freeze.json')
    if any(index['freeze_sha256'] != freeze_sha for index in (paired_index, stream_index)):
        raise ValueError('An execution index belongs to another scoring freeze')
    paired_root = resolve_under(root, freeze['paired_prepared_directory'])
    plan = read_json(root / 'prepared/streams/stream-plan.json')
    expected = {c['case_id']: c for c in plan['cases'] + plan['operational_availability_views']}
    actual = [r['case_id'] for r in stream_index['runs']]
    if len(actual) != len(set(actual)) or set(actual) != set(expected):
        raise ValueError('Stream index is incomplete or contains duplicate/unregistered cases')
    paired_expected = read_json(paired_root / 'preparation-summary.json')['datasets']
    if {d['path']: d['sha256'] for d in paired_expected} != {d['path']: d['sha256'] for d in paired_index['runs']}:
        raise ValueError('Paired execution index differs from its registered dataset inventory')
    if len(paired_expected) != len(paired_index['runs']):
        raise ValueError('Paired index has repeated rows')
    rows = []
    for family, index in (('paired', paired_index), ('streams', stream_index)):
        for execution in index['runs']:
            name = Path(execution['path']).stem if family == 'paired' else execution['case_id']
            directory = resolve_under(root, execution['output'])
            outer = recorded_cost(root, root / 'outputs' / family / 'logs' / (name + '.receipt.json'))
            if outer['exit_code'] != execution['driver_exit_code']:
                raise ValueError('Execution index and command receipt disagree')
            if family == 'paired':
                invoked, status, category = True, ('executed' if outer['exit_code'] == 0 else 'failed'), 'paired_comparison_evaluation'
                dataset = resolve_under(paired_root, execution['path'])
                if sha_file(dataset) != execution['sha256']:
                    raise ValueError('Executed paired dataset bytes changed')
                workload = input_workload(root, dataset)
            else:
                case = expected[name]
                operation = read_json(Path(str(directory) + '.operation') / 'run.json')
                if operation['freeze_sha256'] != freeze_sha:
                    raise ValueError('Stream operation belongs to another freeze')
                invoked, status = operation['command'] is not None, operation['status']
                category = {'splice': 'constructed_splice_evaluation',
                            'continuity_proxy': 'account_id_continuity_proxy_evaluation',
                            'unknown_truth_natural': 'unknown_truth_full_natural_analysis',
                            'operational_module_availability_only': 'operational_omission_availability_analysis'}[case['case_type']]
                if case['execution_mode'] is None:
                    if invoked or directory.exists():
                        raise ValueError('An unfilled slot unexpectedly invoked or published analysis')
                    category, workload = 'unfilled_slot_no_analyzer_invocation', None
                else:
                    prepared = root / 'prepared/streams'
                    dataset = resolve_under(prepared, case['dataset']) if case['dataset'] else None
                    workload = input_workload(root, dataset, resolve_under(prepared, case['input']),
                                              resolve_under(prepared, case['manifest']))
                    if workload['record_rows_in_distinct_input_files'] != case['record_count']:
                        raise ValueError('Prepared and executed record counts disagree')
            inner_path = directory / 'run_receipt.json'
            inner = read_json(inner_path) if inner_path.exists() else None
            if inner is not None:
                if inner['network_isolation'] != 'linux_seccomp_socket_denial':
                    raise ValueError('An actual analyzer receipt lacks kernel network denial')
                inner = {k: inner[k] for k in ('runtime_seconds', 'peak_process_rss_kib', 'network_isolation')}
                inner.update(sha256=sha_file(inner_path), receipt_bytes=inner_path.stat().st_size)
            bundle = bundle_stats(directory, config['artifacts']) if directory.exists() else None
            rows.append({'case': name, 'execution_class': category, 'analyzer_invoked': invoked,
                         'status': status, 'outer_receipt': outer, 'inner_run_receipt': inner,
                         'input_workload': workload, 'bundle': bundle})
    return rows, paired_index, stream_index


def integrity(root: Path, old_study: Path, repo: Path, freeze: dict, baseline: dict):
    from account_history_analyzer import __version__
    from account_history_analyzer.io import canonical_digest
    from account_history_analyzer.pipeline import implementation_identity
    failed = 0
    for relative, expected in freeze['files'].items():
        if sha_file(resolve_under(root, relative)) != expected:
            failed += 1
    fingerprint, environment, resources = implementation_identity()
    lock_matches = {name: sha_file(resolve_under(repo, name)) == expected
                    for name, expected in baseline['lockfiles'].items()}
    source_rows = []
    plan = read_json(root / 'protocol/plan.json')
    for community, source in sorted(plan['source_archives'].items()):
        path = (root / source['path']).resolve()
        observed = sha_file(path)
        source_rows.append({'community': community, 'bytes': path.stat().st_size,
                            'expected_sha256': source['sha256'], 'observed_sha256': observed,
                            'unchanged': observed == source['sha256']})
    historical = read_json(root / 'diagnostics/grid-diagnostics.json')['historical_preservation']
    mapping = {str(p.relative_to(old_study)): sha_file(p) for p in regular_files(old_study)}
    historical_digest = canonical_digest(mapping)
    current_config = configuration_identity()
    report = {
        'suite_version': __version__, 'scoring_freeze_sha256': sha_file(root / 'protocol/scoring-freeze.json'),
        'frozen_file_count': len(freeze['files']), 'changed_frozen_file_count': failed,
        'implementation_fingerprint': fingerprint,
        'implementation_matches_frozen_baseline': fingerprint == baseline['implementation_fingerprint'] == freeze['implementation_fingerprint'],
        'configuration_sha256': current_config,
        'configuration_matches_frozen_baseline': current_config == baseline['configuration_sha256'] == freeze['analysis_config_sha256'],
        'reference_environment': environment, 'reference_environment_matches_baseline': environment == baseline['reference_environment'],
        'resource_hashes_match_baseline': resources == baseline['resources'], 'lockfile_hash_matches': lock_matches,
        'source_archives': source_rows,
        'historical_study': {'expected_file_count': historical['file_count'], 'observed_file_count': len(mapping),
                             'expected_inventory_sha256': historical['inventory_sha256_after'],
                             'observed_inventory_sha256': historical_digest,
                             'all_file_bytes_unchanged': len(mapping) == historical['file_count'] and historical_digest == historical['inventory_sha256_after']},
        'source_maps_and_private_prose_exported': False,
        'review_script_sha256': sha_file(Path(__file__)),
    }
    report['all_binding_checks_passed'] = (failed == 0 and all((report['implementation_matches_frozen_baseline'],
        report['configuration_matches_frozen_baseline'], report['reference_environment_matches_baseline'],
        report['resource_hashes_match_baseline'], all(lock_matches.values()), all(s['unchanged'] for s in source_rows),
        report['historical_study']['all_file_bytes_unchanged'])))
    return report


def preparation_ledger(root: Path):
    sources = {
        'acquisition_separate_from_analysis': ['logs/approved-acquisition.receipt.json', 'logs/approved-acquisition-network.receipt.json'],
        'corpus_inventory_and_preparation': ['inventory/cornell-inventory.receipt.json', 'inventory/source-frame-run.receipt.json',
            'inventory/paired-candidates.receipt.json', 'inventory/paired-registered-candidates-run.receipt.json',
            'inventory/paired-finalize-run.receipt.json', 'inventory/paired-registered-finalize-run.receipt.json',
            'logs/paired-leakage-audit.receipt.json', 'logs/chronological-preparation.receipt.json',
            'logs/chronological-preparation-retry.receipt.json'],
        'independent_preparation_verification': ['inventory/paired-preflight-run.receipt.json',
            'inventory/paired-registered-replay-check-run.receipt.json', 'inventory/paired-prepared-check-run.receipt.json',
            'logs/paired-leakage-independent-check.receipt.json', 'logs/audit-cap-and-joint-bridges.receipt.json',
            'logs/chronological-prepared-artifact-tests.receipt.json'],
        'exposed_development_instrumented_profile': ['logs/exposed-development-profile.receipt.json'],
        'exposed_development_unprofiled_recompute': ['logs/exposed-development-recompute.receipt.json'],
        'registered_measurement_reproduction': ['review/paired-replay-run.receipt.json',
            'logs/natural-canonical-recompute.receipt.json', 'logs/splice-canonical-replay.receipt.json'],
        'post_score_preprocessor_only_characterization': ['review/largest-cost-word-characterization.receipt.json'],
        'preserved_failed_resource_review': ['review/resource-cost-build.receipt.json'],
    }
    return {category: [recorded_cost(root, root / name) for name in names] for category, names in sources.items()}


def render(report):
    def span(s, factor=1, decimals=3):
        if s['count'] == 0:
            return 'not measured'
        return f"{s['minimum']/factor:.{decimals}f}–{s['maximum']/factor:.{decimals}f}"
    lines = ['# Recorded resource and storage costs', '',
        'Both registered batches finished before this review. This report reads receipts, file sizes, and hashes; it runs no new analyses and makes no scientific accuracy claim.', '',
        '| Execution class | Slots / analyzer invocations | Outer elapsed seconds, min–max | Outer process RSS MiB, min–max | Supplied record rows, min–max | Output MiB, min–max |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for category, row in report['by_execution_class'].items():
        lines.append(f"| {category.replace('_', ' ')} | {row['scheduled_slots']} / {row['analyzer_invocations']} | {span(row['outer_wall_seconds'])} | {span(row['outer_peak_rss_kib'],1024)} | {span(row['input_record_rows'],decimals=0)} | {span(row['output_logical_bytes'],1024**2)} |")
    lines += ['', '| Completed batch | Jobs | Wall seconds | Sum of case elapsed seconds | Receipt peak RSS MiB |', '| --- | ---: | ---: | ---: | ---: |']
    for name, batch in report['batches'].items():
        lines.append(f"| {name} | {batch['jobs']} | {batch['receipt']['wall_seconds']:.3f} | {batch['sum_case_elapsed_seconds']:.3f} | {batch['receipt']['peak_rss_kib']/1024:.3f} |")
    lines += ['', 'Outer case elapsed includes startup and orchestration; stream cases also verify the frozen inventory and reconstruct the legal grid after execution. Inner run receipts are reported separately in JSON: their timer and RSS are captured before final report/artifact publication. Concurrent job elapsed times overlap and are not CPU time. RSS is a process high-water mark reported by the command/descendant receipt, not the sum of simultaneous process memory; system-wide peak RAM was not measured.', '',
        'Unfilled preparation slots are counted as no analyzer invocation. Their short wrapper costs are real; absent scientific results are not zero measurements.', '']
    largest = report['largest_cost_splice_word_characterization']
    case = next(row for row in report['cases'] if row['case'] == largest['case_id'])
    lines += [f"The highest-RSS splice, `{largest['case_id']}`, used {case['outer_receipt']['peak_rss_kib']/1024:.3f} MiB by the outer receipt and took {case['outer_receipt']['wall_seconds']:.3f} seconds. Its {largest['record_count']} records contain {largest['retained_body_words']:,} retained body words, including {largest['eligible_style_words']:,} eligible style words in {largest['eligible_style_records']} records. Its published evaluator bundle is {case['bundle']['logical_bytes']/1024**2:.3f} MiB; compact evaluator output does not imply a small intermediate analysis. Word counts were obtained afterward by the unchanged preprocessor only, with a separate receipt and no style/optimizer invocation.", '',
        f"The largest supplied constructed/omission case has {report['extrema']['largest_record_workload']['record_rows']} records. The 200–400-comment selection bounds apply to complete available source-account histories; combining one account's earlier portion and another account's later portion can exceed 400. Word volume, windows, comparisons, and intermediate serialization also affect cost. The earlier 400-comment development profile is not an upper bound for later histories or splices.", '',
        '| Recorded preparation or prior development check | Exit status | Elapsed seconds | Peak RSS MiB |',
        '| --- | ---: | ---: | ---: |']
    for category, values in report['preparation_and_profile_receipts'].items():
        for row in values:
            lines.append(f"| {row['receipt']} | {row['exit_code']} | {row['wall_seconds']:.3f} | {row['peak_rss_kib']/1024:.3f} |")
    lines += ['', 'Failed preparation/acquisition attempts are preserved and remain failures. The first resource-review build also failed because the review helper initially compared an unexpanded configuration mapping with the analytical resource-bound identity; its exact failed source/receipt are preserved, and a regression checks the corrected identity. No frozen configuration had changed. The registered paired replay reproduced the earlier cohort and candidate bytes after registration; it is additional preparation cost. The joint chronological audit is included in the successful chronological preparation receipt, with no separately recorded stage time. These selected receipts are not an accounting of all engineering work or test runs.', '',
        'The development resource probe is an already exposed 400-comment history. cProfile adds instrumentation overhead. Its canonical serialization and schema-validation cumulative times overlap and must not be added as independent phases; the separate unprofiled recomputation includes artifact verification, full analysis, and publication replay. No optimization or limit change was made.', '',
        '| Storage scope | Files | Logical MiB | Allocated MiB |', '| --- | ---: | ---: | ---: |']
    for name, row in report['storage'].items():
        lines.append(f"| {name.replace('_',' ')} | {row['file_count']} | {row['logical_bytes']/1024**2:.3f} | {row['allocated_bytes']/1024**2:.3f} |")
    lines += ['', 'Storage is the sum of final regular-file sizes; allocated bytes use Linux st_blocks × 512. Transient staging space and peak disk usage were not measured. Primary output directories include operational logs and receipts; per-case bundle sizes and canonical bytes are separated in JSON. Storage scopes may overlap (for example the profiled bundle is within resources), so these rows must not be blindly summed.', '',
        'The unchanged frozen limits are 50 MiB cumulative input, 10,000 unique records, and 200,000 codepoints per text; each published bundle allows at most 256 MiB per file, 512 MiB total, and 32 files including receipts/checksums. Metadata JSON has a fixed 1 MiB cap. The evaluator enforces cumulative distinct snapshot/input budgets across the dataset. The table counts rows across distinct supplied input files, a conservative upper bound if multiple files encode the same canonical snapshot. One registered case per invocation keeps these limits local and explicit.', '',
        'Near reuse remains capped at 2,000,000 candidate pairs, 2,000,000 record/shingle postings, 250,000,000 work units, 2,000,000 evidence tokens, and 8,000,000 evidence codepoints. Artifact size limits are not a universal RAM bound. The preparation graph audits used a 3 GiB address-space ceiling; ordinary measurement batches used at most two workers and have no claimed system-wide RAM cap. The full resolved limits and observed headroom are in JSON.', '',
        f"Binding checks passed: {report['integrity']['all_binding_checks_passed']}. All {report['integrity']['frozen_file_count']} frozen study files, three source archives, implementation/resources/lockfiles, and {report['integrity']['historical_study']['observed_file_count']} original-study files were checked without exporting private text or source maps. Implementation: `{report['integrity']['implementation_fingerprint']}`. Scoring freeze: `{report['integrity']['scoring_freeze_sha256']}`.", '',
        'No monetary cost is inferred: local elapsed time and memory/storage observations are available, while electricity, hardware depreciation, cloud billing, and human effort were not measured. No cross-platform byte identity or general performance guarantee is claimed.', '']
    return '\n'.join(lines)


def build(root: Path, old_study: Path, repo: Path):
    if os.environ.get('AHAS_NETWORK_ISOLATION') != 'linux_seccomp_socket_denial':
        raise ValueError('Use the offline runner for this read-only review')
    for name in ('logs/paired-batch.receipt.json', 'logs/stream-batch.receipt.json',
                 'outputs/paired/execution-index.json', 'outputs/streams/execution-index.json'):
        if not (root / name).is_file():
            raise ValueError('Both primary batches must finish before aggregation')
    freeze, baseline = read_json(root / 'protocol/scoring-freeze.json'), read_json(root / 'protocol/measurement-baseline.json')
    config = read_json(root / 'protocol/resolved_config.json')
    rows, paired, streams = resource_rows(root, freeze, config)
    binding = integrity(root, old_study, repo, freeze, baseline)
    if not binding['all_binding_checks_passed']:
        raise ValueError('An immutable source/baseline/historical binding changed')
    batches = {}
    for name, index in (('paired', paired), ('streams', streams)):
        values = [r for r in rows if ('paired' in r['execution_class']) == (name == 'paired')]
        batches[name] = {'jobs': index['jobs'], 'network_isolation': index['network_isolation'],
                         'receipt': recorded_cost(root, root / 'logs' / (('paired' if name == 'paired' else 'stream') + '-batch.receipt.json')),
                         'sum_case_elapsed_seconds': sum(r['outer_receipt']['wall_seconds'] for r in values),
                         'scheduled_slots': len(values), 'analyzer_invocations': sum(r['analyzer_invoked'] for r in values)}
    profile = read_json(root / 'resources/profile-summary.json')
    profile_functions = [{k: v for k, v in row.items() if k != 'path'} | {'source': row['path']}
                         for row in profile['top_cumulative_functions']
                         if row['path'] in {'io.py', 'schemas.py', 'artifacts.py', 'pipeline.py'}]
    storage = {name: size_files(regular_files(root / path)) for name, path in {
        'prepared_datasets_and_sidecars': 'prepared', 'primary_paired_outputs_with_logs': 'outputs/paired',
        'primary_stream_outputs_with_logs': 'outputs/streams', 'profiled_development_bundle': 'resources/exposed-development-report',
        'development_profile_and_resources': 'resources'}.items()}
    storage['three_source_archives'] = size_files([(root / source['path']).resolve()
        for source in read_json(root / 'protocol/plan.json')['source_archives'].values()])
    report = {
        'report_kind': 'recorded_resource_and_storage_review', 'network_isolation': os.environ['AHAS_NETWORK_ISOLATION'],
        'new_analyses_launched': 0, 'integrity': binding, 'limits': {k: config[k] for k in ('input', 'artifacts', 'reuse', 'activity')},
        'fixed_metadata_json_limit_bytes': JSON_LIMIT,
        'scope_notes': ['Outer elapsed includes orchestration; stream wrapper includes inventory verification and legal-grid reconstruction.',
                        'Inner runtime and RSS precede final publication; they are not full CLI cost.',
                        'Sum of elapsed job times is not CPU time and overlaps across two concurrent workers.',
                        'RSS is not a sum across simultaneous processes; system-wide peak memory was not measured.',
                        'Final file bytes are observed; transient/peak disk usage was not measured.',
                        'No source text values or scientific score fields are read by this review.',
                        'No billing, electricity, hardware depreciation, or human-effort measurements are available.'],
        'batches': batches, 'by_execution_class': summarize_cases(rows), 'cases': rows,
        'preparation_and_profile_receipts': preparation_ledger(root),
        'instrumented_profile': {'scope': 'previously_exposed_400_comment_development_history',
            'instrumentation_overhead_included': True, 'cumulative_times_overlap': True,
            'selected_package_cumulative_functions': profile_functions,
            'optimization_performed': False, 'profile_summary_sha256': sha_file(root / 'resources/profile-summary.json')},
        'storage': storage,
    }
    largest_words = read_json(root / 'review/largest-cost-word-volume.json')
    if largest_words['implementation_fingerprint'] != binding['implementation_fingerprint'] or not largest_words['source_and_existing_result_bytes_unchanged']:
        raise ValueError('Word-volume characterization does not match the unchanged baseline')
    report['largest_cost_splice_word_characterization'] = largest_words
    report['reproduction'] = read_json(root / 'review/stream-reproduction.json')
    actual = [r for r in rows if r['analyzer_invoked']]
    largest_rss = max(actual, key=lambda r: r['outer_receipt']['peak_rss_kib'])
    largest_time = max(actual, key=lambda r: r['outer_receipt']['wall_seconds'])
    largest_output = max(actual, key=lambda r: r['bundle']['logical_bytes'] if r['bundle'] else -1)
    largest_records = max((r for r in actual if r['execution_class'] != 'paired_comparison_evaluation'),
                          key=lambda r: r['input_workload']['record_rows_in_distinct_input_files'])
    report['extrema'] = {
        'largest_outer_peak_rss': {'case': largest_rss['case'], 'peak_rss_kib': largest_rss['outer_receipt']['peak_rss_kib']},
        'longest_outer_elapsed': {'case': largest_time['case'], 'wall_seconds': largest_time['outer_receipt']['wall_seconds']},
        'largest_published_bundle': {'case': largest_output['case'], 'logical_bytes': largest_output['bundle']['logical_bytes']},
        'largest_record_workload': {'case': largest_records['case'], 'record_rows': largest_records['input_workload']['record_rows_in_distinct_input_files']},
    }
    report['all_published_bundles_within_limits'] = all(r['bundle']['within_artifact_limits'] for r in rows if r['bundle'])
    report['all_supplied_workload_upper_bounds_within_limits'] = all(
        r['input_workload']['record_rows_in_distinct_input_files'] <= config['input']['max_unique_records']
        and r['input_workload']['dataset_input_and_manifest_bytes'] <= config['input']['max_input_bytes']
        for r in rows if r['input_workload'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--old-study', required=True, type=Path)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--out-json', required=True, type=Path)
    parser.add_argument('--out-markdown', required=True, type=Path)
    args = parser.parse_args()
    frozen = read_json(args.root / 'protocol/scoring-freeze.json')['files']
    for path in (Path(__file__), args.out_json, args.out_markdown):
        relative = str(path.resolve().relative_to(args.root.resolve()))
        if relative in frozen:
            raise ValueError('Review cannot modify a frozen path')
    if args.out_json.exists() or args.out_markdown.exists():
        raise ValueError('Use new report destinations; existing receipts are preserved')
    report = build(args.root.resolve(), args.old_study.resolve(), args.repo.resolve())
    args.out_json.write_text(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2, allow_nan=False) + '\n')
    args.out_markdown.write_text(render(report), encoding='utf-8')
    print(json.dumps({'report_status': 'complete', 'scheduled_slots': len(report['cases']),
                      'analyzer_invocations': sum(r['analyzer_invoked'] for r in report['cases']),
                      'all_binding_checks_passed': report['integrity']['all_binding_checks_passed'],
                      'json_sha256': sha_file(args.out_json), 'markdown_sha256': sha_file(args.out_markdown)}, sort_keys=True))


if __name__ == '__main__':
    main()
