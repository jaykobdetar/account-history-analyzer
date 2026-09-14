#!/usr/bin/env python3
"""Extract complete sanitized cases from frozen evaluator outputs, never score.

No source account/record identifiers, original prose, paths or grouping hashes
are emitted. Private evaluator outputs and provenance remain separately retained.
"""
import argparse
import hashlib
import json
from pathlib import Path

from analyze_cases import CASE_FIELDS, UNIT_FIELDS, validate_inputs
from study_math import comparison_design


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def extract_batch(item, evaluation, stratum_id):
    design = {r['pair_id']: r for r in comparison_design(item['block_id'])}
    method = {k: item[k] for k in ('method_id', 'view', 'n')}
    expected_id = item['block_id'] + '/' + item['arm'] + '/' + item['view']
    if (evaluation['distance'] != method or evaluation['exit_code'] != 0
            or evaluation['dataset_id'] != expected_id):
        raise ValueError('Evaluator method changed or batch did not complete')
    if evaluation['partitions']['development']['rows']:
        raise ValueError('No development or reserve cases belong to this study')
    rows = evaluation['partitions']['evaluation']['rows']
    if len(rows) != 16 or len({r['pair_id'] for r in rows}) != 16 or {r['pair_id'] for r in rows} != set(design):
        raise ValueError('Every batch must retain all sixteen distinct planned pairs')
    result = []
    for row in rows:
        expected = design[row['pair_id']]
        if (row['label'] != expected['label'] or row['left_text_id'] != expected['left_cell_id']
                or row['right_text_id'] != expected['right_cell_id'] or row['split'] != 'evaluation'):
            raise ValueError('A measured pair differs from its frozen source-account contrast')
        result.append({**method, 'arm': item['arm'], 'stratum_id': stratum_id,
                       'block_id': item['block_id'], 'anchor_id': expected['anchor_id'],
                       'category': expected['category'], 'score': row['score'],
                       'raw_distance': row['raw_distance'], 'status': row['status'],
                       'reason_codes': list(row['reason_codes'])})
    if any(set(row) != CASE_FIELDS for row in result):
        raise AssertionError('Public case schema changed')
    return result


def sample_totals(evaluation):
    """Count each of eight supplied units once, despite repeated anchor use."""
    fields = ('record_count', 'word_count', 'eligible_record_count', 'eligible_word_count', 'usable_record_count')
    units = {}
    for row in evaluation['partitions']['evaluation']['rows']:
        for side in ('left', 'right'):
            key = row[side + '_text_id']
            observed = {field: row['samples'][side][field] for field in fields}
            if key in units and units[key] != observed:
                raise ValueError('Repeated unit has inconsistent evaluator sample counts')
            units[key] = observed
    if len(units) != 8:
        raise ValueError('Exactly eight explicit units must enter each evaluator invocation')
    return {'supplied_units': 8, **{field: sum(u[field] for u in units.values()) for field in fields}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--executions', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    freeze = json.loads(args.freeze.read_text())
    if freeze['status'] != 'frozen_before_first_style_score' or sha(__file__) != freeze['normalizer_sha256']:
        raise ValueError('Sanitized extraction code must be bound before scoring')
    for artifact in freeze['bound_artifacts']:
        if sha(artifact['path']) != artifact['sha256']:
            raise ValueError('A registered preparation or analysis input changed after scoring')
    index_path = args.prepared / 'batch-index.json'
    if sha(index_path) != freeze['batch_index_sha256']:
        raise ValueError('The complete frozen batch list changed')
    index = json.loads(index_path.read_text())
    execution_path = args.executions / 'execution-index.json'
    execution = json.loads(execution_path.read_text())
    if (execution['status'] != 'completed' or execution['replay'] is not False
            or execution['executed_batches'] != 360 or len(execution['runs']) != 360
            or execution['freeze_sha256'] != sha(args.freeze)):
        raise ValueError('Complete original study execution required; no substituted replay or partial cases')
    runs = {r['batch_id']: r for r in execution['runs']}
    if len(runs) != 360 or set(runs) != {b['batch_id'] for b in index}:
        raise ValueError('Every frozen batch must have one retained execution receipt')
    stratum_map = freeze['public_stratum_map']
    cases, resources = [], []
    for item in index:
        row = runs[item['batch_id']]
        path = args.executions / item['batch_id'] / 'evaluation.json'
        if row['exit_code'] != 0 or sha(path) != row['output_files']['evaluation.json']['sha256']:
            raise ValueError('Missing, failed or changed evaluator output')
        evaluation = json.loads(path.read_text())
        dataset_path = args.prepared / item['dataset']
        if sha(dataset_path) != item['dataset_sha256']:
            raise ValueError('Frozen source dataset changed before result extraction')
        dataset = json.loads(dataset_path.read_text())
        if (evaluation['dataset_id'] != dataset['dataset_id']
                or evaluation['protocol'] != dataset['protocol']
                or evaluation['dataset_provenance'] != dataset['provenance']
                or evaluation['label_definition'] != dataset['label_definition']):
            raise ValueError('A result belongs to another arm, protocol or supplied dataset')
        if (evaluation['implementation_fingerprint'] != freeze['implementation_fingerprint']
                or evaluation['analysis_config_sha256'] != freeze['analysis_config_sha256']):
            raise ValueError('A result does not use the registered numerical baseline')
        cases.extend(extract_batch(item, evaluation, stratum_map[item['stratum_id']]))
        resources.append({**{k: item[k] for k in ('batch_id', 'block_id', 'method_id', 'view', 'n', 'arm')},
                          'stratum_id': stratum_map[item['stratum_id']],
                          **{k: row[k] for k in ('exit_code', 'wall_seconds', 'peak_rss_mib', 'input_bytes')},
                          **sample_totals(evaluation),
                          'output_bytes': sum(r['bytes'] for r in row['output_files'].values())})
    units = []
    for row in json.loads((args.prepared / 'unit-metadata.json').read_text()):
        clean = {k: row[k] for k in UNIT_FIELDS}
        clean['stratum_id'] = stratum_map[row['stratum_id']]
        units.append(clean)
    dependencies = json.loads((args.prepared / 'dependency-units.json').read_text())
    validate_inputs(cases, units, dependencies, sorted(stratum_map.values()))
    args.out.mkdir(exist_ok=False, parents=True)
    files = {'cases.json': cases, 'units.json': units, 'dependencies.json': dependencies,
             'batch-resources.json': resources}
    for name, value in files.items():
        with (args.out / name).open('x') as f:
            json.dump(value, f, sort_keys=True, indent=2)
            f.write('\n')
    with (args.out / 'normalization-receipt.json').open('x') as f:
        json.dump({'status': 'complete_sanitized_extraction', 'case_rows': len(cases), 'unit_rows': len(units),
                   'scoring_freeze_sha256': sha(args.freeze), 'source_execution_index_sha256': sha(execution_path),
                   'script_sha256': sha(__file__), 'files': {name: sha(args.out / name) for name in files},
                   'style_scores_recomputed': 0}, f, indent=2)
        f.write('\n')


if __name__ == '__main__':
    main()
