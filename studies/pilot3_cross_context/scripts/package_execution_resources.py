"""Post-registration reporting only: sanitize existing command/resource receipts.

This helper is not preregistered analysis, never invokes an evaluator, and never
reads source JSONL bodies. It reads already-produced evaluator sample counts and
operational receipts, verifies their recorded hashes, and emits whitelisted fields.
Exact original argv remains private; public argv retains every literal and its
order while replacing operational paths with explicit logical placeholders.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re

VERSION = 'post-registration-execution-resource-report-v1'
COUNT_FIELDS = ('record_count', 'word_count', 'eligible_record_count', 'eligible_word_count', 'usable_record_count')
SAFE = re.compile(r'[A-Za-z0-9_-]{1,128}')
METHODS = {('cosine_distance_v1', 'retained_prose', 4), ('cosine_distance_v1', 'function_mask_v1', 4),
           ('function_word_js_v1', 'lexical_tokens', None)}
ARMS = {'full', 'hash75', 'hash50', 'middle50'}
OUTPUT_ARTIFACTS = {'evaluation.json', 'report.md', 'checksums.json', 'run_receipt.json'}


class ReportingFailure(ValueError):
    """Safe public code only, never raw private input values."""


def require(condition, code):
    if not condition:
        raise ReportingFailure(code)


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(',', ':')) + '\n').encode()


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def child(root, relative):
    rel = Path(relative)
    require(not rel.is_absolute(), 'absolute_artifact_reference')
    path = (root/rel).resolve()
    require(path.is_relative_to(root.resolve()), 'artifact_reference_outside_declared_root')
    return path


def number(value, *, integer=False, nullable=False):
    if value is None and nullable:
        return None
    require(type(value) is int if integer else type(value) in (int, float), 'invalid_resource_number')
    require(math.isfinite(value) and value >= 0, 'invalid_resource_number')
    return value


def utc(value):
    require(isinstance(value, str) and len(value) <= 48, 'invalid_receipt_timestamp')
    moment = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(moment.utcoffset() is not None and moment.utcoffset().total_seconds() == 0,
            'non_utc_receipt_timestamp')
    return value


def sample_counts(evaluation):
    """Eight source units counted once; 16 repeated comparisons do not inflate input."""
    require(evaluation['exit_code'] == 0, 'incomplete_evaluation_sample_counts')
    rows = evaluation['partitions']['evaluation']['rows']
    require(len(rows) == 16 and not evaluation['partitions']['development']['rows'],
            'unexpected_evaluation_partition')
    units = {}
    for row in rows:
        for side in ('left', 'right'):
            key = row[side + '_text_id']
            require(re.fullmatch(r'[AB]/[XY]/(?:early|late)', key) is not None, 'unexpected_sample_identity')
            values = {field: number(row['samples'][side][field], integer=True) for field in COUNT_FIELDS}
            require(key not in units or units[key] == values, 'repeated_unit_resource_counts_disagree')
            units[key] = values
    require(len(units) == 8, 'eight_unit_sample_counts_required')
    return {'supplied_units': 8, **{field: sum(row[field] for row in units.values()) for field in COUNT_FIELDS}}


def command_view(argv, item, mode, execution_root, prepared_root):
    """Known evaluator command grammar prevents arbitrary private argv disclosure."""
    require(isinstance(argv, list) and len(argv) == 14 and all(isinstance(a, str) for a in argv),
            'unrecognized_actual_command_shape')
    require(argv[:2] == ['/usr/bin/timeout', '--kill-after=5'] and
            argv[4:11] == ['-B', '-m', 'account_history_analyzer', 'evaluate', '--suite', 'paired_text', '--dataset'] and
            argv[12] == '--out', 'unrecognized_actual_command_literals')
    require(re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', argv[2]) is not None and 0 < float(argv[2]) <= 300,
            'unrecognized_actual_timeout')
    python, dataset, output = Path(argv[3]), Path(argv[11]), Path(argv[13])
    require(python.is_absolute() and dataset.is_absolute() and output.is_absolute(), 'nonabsolute_operational_path')
    relative = Path(item['dataset'])
    require(not relative.is_absolute() and '..' not in relative.parts and
            tuple(dataset.parts[-len(relative.parts):]) == relative.parts, 'actual_dataset_path_mismatch')
    input_root = dataset.parents[len(relative.parts) - 1]
    require((input_root.resolve() == prepared_root.resolve()) == (mode == 'main'), 'main_replay_input_location_mismatch')
    require(output.resolve() == (execution_root/item['batch_id']).resolve(), 'actual_output_path_mismatch')
    public = list(argv)
    public[3] = '<PYTHON_EXECUTABLE>'
    public[11] = ('<PRIMARY_PREPARED>' if mode == 'main' else '<REPLAY_PREPARED>') + '/' + relative.as_posix()
    public[13] = ('<MAIN_OUTPUT>' if mode == 'main' else '<REPLAY_OUTPUT>') + '/' + item['batch_id']
    return {'argv': public, 'exact_original_argv_sha256': hashlib.sha256(canonical(argv)).hexdigest(),
            'representation': 'Exact argument order and non-path literals; arguments 3,11,13 use explicit path placeholders.',
            'redacted_argument_indices': [3, 11, 13],
            'operational_path_sha256': {str(i): hashlib.sha256(argv[i].encode()).hexdigest() for i in (3, 11, 13)},
            'exact_original_argv_available_in_private_receipt': True}


def one_batch(mode, root, prepared, item, run, unit_lookup, public_stratum):
    fields = ('batch_id', 'block_id', 'method_id', 'view', 'n', 'arm')
    require(all(run[k] == item[k] for k in fields) and run['stratum_id'] == item['stratum_id'],
            'execution_batch_identity_mismatch')
    require(SAFE.fullmatch(item['batch_id']) and SAFE.fullmatch(item['block_id']) and SAFE.fullmatch(public_stratum),
            'nonopaque_public_identity')
    require((item['method_id'], item['view'], item['n']) in METHODS and item['arm'] in ARMS,
            'unexpected_method_or_arm')
    require(type(run['exit_code']) is int, 'invalid_execution_exit_code')
    planned = [unit_lookup[item['block_id'], item['arm'], cell] for cell in
               (f'{a}/{c}/{t}' for a in ('A', 'B') for c in ('X', 'Y') for t in ('early', 'late'))]
    result = {'execution': mode, **{key: item[key] for key in fields}, 'stratum_id': public_stratum,
              'exit_code': run['exit_code'], 'status': 'completed' if run['exit_code'] == 0 else 'failed',
              'planned_input_units': 8, 'planned_input_records': sum(number(u['records'], integer=True) for u in planned),
              'planned_eligible_words': sum(number(u['retained_words'], integer=True) for u in planned),
              'wall_seconds': number(run.get('wall_seconds'), nullable=True),
              'peak_rss_mib': number(run.get('peak_rss_mib'), nullable=True),
              'input_bytes': number(run.get('input_bytes'), integer=True, nullable=True),
              'observed_sample_counts': None, 'command': None, 'receipt': None, 'output_artifacts': {}}
    if run.get('status') == 'not_started_run_wall_budget_exhausted':
        result['status'] = 'not_started_run_wall_budget_exhausted'
    elif run.get('status') == 'execution_driver_failed':
        result['status'] = 'execution_driver_failed'
    receipt_path = root/'logs'/(item['batch_id'] + '.receipt.json')
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_bytes())
        result['command'] = command_view(receipt['argv'], item, mode, root, prepared)
        if result['status'] != 'execution_driver_failed':
            require(receipt['exit_code'] == run['exit_code'] and receipt['wall_seconds'] == run['wall_seconds'] and
                    receipt['child_peak_rss_mib'] == run['peak_rss_mib'], 'operational_receipt_resource_mismatch')
        logs = {}
        require(set(receipt['outputs']) == {'stdout.log', 'stderr.log'}, 'unexpected_operational_log_inventory')
        for name, record in receipt['outputs'].items():
            path = root/'logs'/(item['batch_id'] + '.' + name)
            require(path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], 'operational_log_changed')
            logs[name] = {'bytes': path.stat().st_size, 'sha256': record['sha256']}
        result['receipt'] = {'sha256': sha(receipt_path), 'started_utc': utc(receipt['started_utc']),
                             'finished_utc': utc(receipt['finished_utc']), 'working_directory': '<WORKSPACE>',
                             'logged_command_exit_code': receipt['exit_code'],
                             'logged_command_wall_seconds': number(receipt['wall_seconds']),
                             'logged_command_peak_rss_mib': number(receipt['child_peak_rss_mib']),
                             'exact_working_directory_sha256': hashlib.sha256(receipt['cwd'].encode()).hexdigest(),
                             'logs': logs}
    else:
        require(run['exit_code'] != 0, 'successful_batch_missing_operational_receipt')
    for name, record in run['output_files'].items():
        require(name in OUTPUT_ARTIFACTS, 'unregistered_output_artifact_name')
        path = child(root/item['batch_id'], name)
        require(path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], 'recorded_output_artifact_changed')
        result['output_artifacts'][name] = {'bytes': path.stat().st_size, 'sha256': record['sha256']}
    result['output_bytes'] = sum(v['bytes'] for v in result['output_artifacts'].values())
    if run['exit_code'] == 0:
        require('evaluation.json' in result['output_artifacts'], 'successful_batch_missing_evaluation')
        evaluation = json.loads((root/item['batch_id']/'evaluation.json').read_bytes())
        require(evaluation['dataset_id'] == item['block_id'] + '/' + item['arm'] + '/' + item['view'],
                'reported_evaluation_identity_mismatch')
        counts = sample_counts(evaluation)
        require(counts['record_count'] == result['planned_input_records'] and
                counts['eligible_word_count'] == result['planned_eligible_words'], 'prepared_observed_resource_counts_disagree')
        result['observed_sample_counts'] = counts
    return result


def build_report(main, replay, prepared, freeze_path):
    freeze = json.loads(Path(freeze_path).read_bytes())
    require(freeze['status'] == 'frozen_before_first_style_score', 'registered_study_freeze_required')
    index_path = prepared/'batch-index.json'
    require(sha(index_path) == freeze['batch_index_sha256'], 'prepared_index_changed')
    index = json.loads(index_path.read_bytes())
    by_id = {r['batch_id']: r for r in index}
    require(len(index) == len(by_id) == 360, 'fixed_360_batch_index_required')
    expected_replay = {r['batch_id'] for r in index if r['stratum_id'] == freeze['replay_stratum_id']}
    require(len(expected_replay) == 120, 'fixed_120_batch_replay_required')
    unit_path = prepared/'unit-metadata.json'
    bound_artifacts = {Path(a['path']).resolve(): a['sha256'] for a in freeze['bound_artifacts']}
    require(bound_artifacts.get(unit_path.resolve()) == sha(unit_path), 'prepared_unit_metadata_not_bound_or_changed')
    units = json.loads(unit_path.read_bytes())
    unit_lookup = {(r['block_id'], r['arm'], r['cell_id']): r for r in units}
    require(len(units) == len(unit_lookup) == 960, 'fixed_960_unit_metadata_required')
    public_map = freeze['public_stratum_map']
    rows, executions = [], {}
    for mode, root, expected in [('main', main, set(by_id)), ('replay', replay, expected_replay)]:
        path = root/'execution-index.json'; execution = json.loads(path.read_bytes())
        run_rows = execution['runs']; run_map = {r['batch_id']: r for r in run_rows}
        require(execution['freeze_sha256'] == sha(freeze_path) and execution['replay'] is (mode == 'replay') and
                len(run_rows) == len(run_map) == len(expected) and set(run_map) == expected,
                'execution_does_not_cover_exact_registered_scope')
        require(execution['status'] in ('completed', 'failed_batches_preserved', 'run_wall_budget_exhausted'),
                'unexpected_execution_status')
        executions[mode] = {'status': execution['status'], 'execution_index_sha256': sha(path),
                            'dispatch_wall_seconds': number(execution['wall_seconds']),
                            'registered_batches': 360, 'reported_batches': len(run_rows)}
        for identifier in sorted(expected):
            item = by_id[identifier]
            rows.append(one_batch(mode, root, prepared, item, run_map[identifier], unit_lookup, public_map[item['stratum_id']]))
    summary = {'version': VERSION, 'status': 'existing_execution_resources_packaged',
               'registration_relationship': 'Reporting helper created after scoring registration; not preregistered analysis.',
               'style_scores_recomputed': 0, 'source_jsonl_bodies_read': 0, 'per_batch_rows': len(rows),
               'scoring_freeze_sha256': sha(freeze_path), 'prepared_batch_index_sha256': sha(index_path),
               'prepared_unit_metadata_sha256': sha(unit_path), 'reporting_script_sha256': sha(__file__),
               'executions': executions, 'resource_totals': {}}
    for mode in ('main', 'replay'):
        selected = [r for r in rows if r['execution'] == mode]
        observed = [r['observed_sample_counts'] for r in selected if r['observed_sample_counts'] is not None]
        summary['resource_totals'][mode] = {'status_counts': dict(Counter(r['status'] for r in selected)),
            'exit_code_counts': dict(Counter(str(r['exit_code']) for r in selected)),
            'known_child_wall_seconds_sum': sum(r['wall_seconds'] for r in selected if r['wall_seconds'] is not None),
            'maximum_reported_child_peak_rss_mib': max((r['peak_rss_mib'] for r in selected if r['peak_rss_mib'] is not None), default=None),
            'known_input_bytes_sum': sum(r['input_bytes'] for r in selected if r['input_bytes'] is not None),
            'known_output_bytes_sum': sum(r['output_bytes'] for r in selected),
            'observed_sample_count_batches': len(observed),
            'observed_samples_summed_across_invocations': {field: sum(r[field] for r in observed) for field in COUNT_FIELDS}}
    summary['interpretation'] = ['Per-invocation input counts count each of eight units once, not every repeated pair side.',
        'Totals across invocations intentionally repeat supplied units across methods/arms/replay; they are not unique study words or records.',
        'Sum of child wall times is not elapsed wall time under two-process execution.',
        'Maximum reported child peak RSS is not simultaneous combined process memory.',
        'Public argv has explicitly marked path substitutions; exact original commands and logs remain private and hash-bound.']
    return {'summary': summary, 'batches': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('main-executions', 'replay-executions', 'prepared', 'freeze', 'out'):
        parser.add_argument('--' + key, type=Path, required=True)
    args = parser.parse_args()
    try:
        require(not args.out.exists(), 'report_output_already_exists')
        result = build_report(args.main_executions.resolve(), args.replay_executions.resolve(),
                              args.prepared.resolve(), args.freeze.resolve())
        args.out.mkdir(parents=True, exist_ok=False)
        for name, value in [('batch-resources.json', result['batches']), ('resource-summary.json', result['summary'])]:
            with (args.out/name).open('xb') as handle:
                handle.write(canonical(value))
        print(json.dumps({'status': result['summary']['status'], 'per_batch_rows': len(result['batches']),
                          'style_scores_recomputed': 0, 'reporting_script_sha256': sha(__file__)}, sort_keys=True))
        return 0
    except Exception as error:
        code = str(error) if type(error) is ReportingFailure else 'reporting_failed_' + type(error).__name__
        print(json.dumps({'status': 'resource_packaging_failed', 'reason_codes': [code], 'style_scores_recomputed': 0}), flush=True)
        return 4


if __name__ == '__main__':
    raise SystemExit(main())
