#!/usr/bin/env python3
"""Post-score operational word counts using the frozen preprocessor only.

No comparison, reuse analysis, style distance, windowing or optimizer is called.
The highest-RSS splice is chosen from completed execution receipts, solely for
resource explanation; this selection is not a scientific population change.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path

from build_resource_cost_report import read_json, sha_file, resolve_under


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if os.environ.get('AHAS_NETWORK_ISOLATION') != 'linux_seccomp_socket_denial':
        raise ValueError('Run with kernel network denial')
    root = args.root.resolve()
    if args.out.exists():
        raise ValueError('Use a new output; historical results remain unchanged')
    freeze = read_json(root / 'protocol/scoring-freeze.json')
    if str(args.out.resolve().relative_to(root)) in freeze['files']:
        raise ValueError('Output cannot be a frozen study file')
    from account_history_analyzer.config import AnalysisConfig
    from account_history_analyzer.io import load_snapshot
    from account_history_analyzer.pipeline import implementation_identity
    from account_history_analyzer.text import preprocess
    fingerprint, environment, _ = implementation_identity()
    if fingerprint != freeze['implementation_fingerprint']:
        raise ValueError('Frozen implementation mismatch')
    plan = read_json(root / 'prepared/streams/stream-plan.json')
    candidates = []
    for case in plan['cases']:
        if case['case_type'] == 'splice' and case['execution_mode'] == 'evaluate':
            receipt = read_json(root / 'outputs/streams/logs' / (case['case_id'] + '.receipt.json'))
            candidates.append((receipt['peak_rss_kib'], case['case_id'], case))
    rss, name, case = max(candidates, key=lambda row: (row[0], row[1]))
    prepared = root / 'prepared/streams'
    source, manifest = resolve_under(prepared, case['input']), resolve_under(prepared, case['manifest'])
    paths = [source, manifest] + sorted((root / 'outputs/streams' / name).iterdir())
    before = {path: sha_file(path) for path in paths if path.is_file()}
    config = AnalysisConfig.from_toml()
    snapshot = load_snapshot(source, manifest, config)
    retained_words = eligible_words = eligible_records = usable = largest = 0
    statuses, languages = Counter(), Counter()
    for record in snapshot.records:
        view = preprocess(record, snapshot.manifest, config)
        words = sum(len(segment) for segment in view['word_tokens'])
        statuses[record['status']] += 1
        languages[view['language']] += 1
        retained_words += words
        largest = max(largest, words)
        usable += view['usable']
        if view['usable'] and view['language'] == 'en' and view['created_utc'] is not None and words >= config['style']['minimum_record_words']:
            eligible_records += 1
            eligible_words += words
    unchanged = all(sha_file(path) == digest for path, digest in before.items())
    if not unchanged:
        raise ValueError('Source or existing result bytes changed during read-only characterization')
    report = {'scope': 'post_score_operational_characterization_not_selection_or_scientific_outcome',
              'selection_rule': 'highest_recorded_outer_peak_rss_among_executed_splices_ties_case_id',
              'case_id': name, 'outer_peak_rss_kib': rss,
              'source_input_sha256': sha_file(source), 'manifest_sha256': sha_file(manifest),
              'snapshot_sha256': snapshot.canonical_sha256,
              'record_count': len(snapshot.records), 'usable_body_records': usable,
              'status_counts': dict(sorted(statuses.items())), 'language_counts': dict(sorted(languages.items())),
              'retained_body_words': retained_words, 'eligible_style_records': eligible_records,
              'eligible_style_words': eligible_words, 'largest_single_record_retained_words': largest,
              'preprocessor_calls': len(snapshot.records), 'style_distance_calls': 0,
              'optimizer_calls': 0, 'new_analysis_pipeline_invocations': 0,
              'source_and_existing_result_bytes_unchanged': unchanged,
              'implementation_fingerprint': fingerprint, 'reference_environment': environment,
              'scoring_freeze_sha256': sha_file(root / 'protocol/scoring-freeze.json'),
              'review_script_sha256': sha_file(Path(__file__)),
              'network_isolation': os.environ['AHAS_NETWORK_ISOLATION']}
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({k: report[k] for k in ('case_id', 'record_count', 'retained_body_words',
        'eligible_style_words', 'source_and_existing_result_bytes_unchanged')}, sort_keys=True))


if __name__ == '__main__':
    main()
