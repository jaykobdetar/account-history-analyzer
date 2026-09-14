#!/usr/bin/env python3
"""Compare every canonical artifact for the fixed complete stratum replay."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def compare_replay(primary, replay, expected_ids):
    """Only operational runtime receipts may differ; absent outputs are failures."""
    first = json.loads((primary / 'execution-index.json').read_text())
    second = json.loads((replay / 'execution-index.json').read_text())
    if (first['status'] != 'completed' or second['status'] != 'completed'
            or first['replay'] is not False or second['replay'] is not True
            or first['freeze_sha256'] != second['freeze_sha256']):
        raise ValueError('Two completed main/replay executions of the same freeze are required')
    original = {r['batch_id']: r for r in first['runs']}
    repeated = {r['batch_id']: r for r in second['runs']}
    if (len(original) != len(first['runs']) or len(repeated) != len(second['runs'])
            or len(expected_ids) != len(set(expected_ids))
            or set(repeated) != set(expected_ids) or not set(expected_ids) <= set(original)):
        raise ValueError('The entire fixed replay stratum must be present exactly once')
    comparisons, mismatches = [], []
    for identifier in sorted(expected_ids):
        if original[identifier]['exit_code'] or repeated[identifier]['exit_code']:
            raise ValueError('A failed invocation is not a valid completed replay')
        left, right = primary / identifier, replay / identifier
        a, b = set(original[identifier]['output_files']), set(repeated[identifier]['output_files'])
        if a != b or a != {p.name for p in left.iterdir()} or b != {p.name for p in right.iterdir()}:
            raise ValueError('Replay artifact inventories differ from actual recorded output')
        if not {'evaluation.json', 'report.md', 'checksums.json', 'run_receipt.json'} <= a:
            raise ValueError('Expected canonical evaluator artifacts are missing')
        for filename in sorted(a - {'run_receipt.json'}):
            lh, rh = sha(left / filename), sha(right / filename)
            bound = (lh == original[identifier]['output_files'][filename]['sha256']
                     and rh == repeated[identifier]['output_files'][filename]['sha256'])
            row = {'batch_id': identifier, 'artifact': filename,
                   'primary_sha256': lh, 'replay_sha256': rh,
                   'recorded_output_binding_matches': bound, 'byte_identical': lh == rh}
            comparisons.append(row)
            if not bound or lh != rh:
                mismatches.append(row)
    return {'status': 'passed' if not mismatches else 'failed', 'replayed_batches': len(expected_ids),
            'canonical_artifact_comparisons': len(comparisons), 'mismatches': mismatches,
            'excluded_operational_artifacts': ['run_receipt.json'], 'comparisons': comparisons,
            'style_scores_recomputed_by_checker': 0}


def main():
    parser = argparse.ArgumentParser()
    for name in ('freeze', 'primary', 'replay', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    freeze = json.loads(args.freeze.read_text())
    if sha(__file__) != freeze['replay_checker_sha256']:
        raise ValueError('Replay checker changed after registration')
    index_path = Path(freeze['primary_prepared_directory']) / 'batch-index.json'
    if sha(index_path) != freeze['batch_index_sha256']:
        raise ValueError('The registered prepared batch index changed')
    index = json.loads(index_path.read_text())
    for root, count in ((args.primary, 360), (args.replay, 120)):
        execution = json.loads((root / 'execution-index.json').read_text())
        if (execution['freeze_sha256'] != sha(args.freeze) or len(execution['runs']) != count
                or len({r['batch_id'] for r in execution['runs']}) != count
                or execution['executed_batches'] != count):
            raise ValueError('Complete executions must belong to this exact supplied scoring freeze')
    expected = [r['batch_id'] for r in index if r['stratum_id'] == freeze['replay_stratum_id']]
    if len(index) != 360 or len(expected) != 120:
        raise ValueError('Complete registered360-batch study and120-batch stratum replay required')
    result = compare_replay(args.primary, args.replay, expected)
    result.update(freeze_sha256=sha(args.freeze), checker_sha256=sha(__file__),
                  primary_execution_index_sha256=sha(args.primary / 'execution-index.json'),
                  replay_execution_index_sha256=sha(args.replay / 'execution-index.json'))
    with args.out.open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps({k: result[k] for k in ('status', 'replayed_batches', 'canonical_artifact_comparisons')}))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
