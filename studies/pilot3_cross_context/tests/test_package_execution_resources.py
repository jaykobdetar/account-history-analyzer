"""Post-registration reporting tests using constructed receipts, never scores."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import package_execution_resources as reporting

CELLS = [f'{a}/{c}/{t}' for a in ('A', 'B') for c in ('X', 'Y') for t in ('early', 'late')]


def sample_result(item):
    rows = []
    for anchor in [key for key in CELLS if key.endswith('/early')]:
        for target in [key for key in CELLS if key.endswith('/late')]:
            rows.append({'left_text_id': anchor, 'right_text_id': target,
                         'score': 'NOT A NUMERICAL SCORE; MUST NEVER BE READ',
                         'samples': {side: {'record_count': 8, 'word_count': 2000,
                            'eligible_record_count': 8, 'eligible_word_count': 2000,
                            'usable_record_count': 8, 'private_extra': 'secret-person prose'} for side in ('left', 'right')}})
    return {'exit_code': 0, 'dataset_id': item['block_id'] + '/' + item['arm'] + '/' + item['view'],
            'private_source_map': {'secret-person': 'private writing'},
            'partitions': {'evaluation': {'rows': rows}, 'development': {'rows': []}}}


def item(block='stratum-01-block-01', arm='full', method=('cosine_distance_v1', 'retained_prose', 4)):
    identifier = block + '-' + arm + '-' + method[1]
    return {'batch_id': identifier, 'block_id': block, 'stratum_id': block[:10], 'arm': arm,
            **dict(zip(('method_id', 'view', 'n'), method)), 'dataset': identifier + '/dataset.json'}


def write_batch(root, prepared, row):
    folder = root/row['batch_id']; folder.mkdir(parents=True)
    logs = root/'logs'; logs.mkdir(exist_ok=True)
    evaluation = folder/'evaluation.json'; evaluation.write_bytes(reporting.canonical(sample_result(row)))
    argv = ['/usr/bin/timeout', '--kill-after=5', '300.000000', '/home/secret-person/runtime/python',
            '-B', '-m', 'account_history_analyzer', 'evaluate', '--suite', 'paired_text',
            '--dataset', str(prepared/row['dataset']), '--out', str(folder)]
    outputs = {}
    for suffix in ('stdout.log', 'stderr.log'):
        path = logs/(row['batch_id'] + '.' + suffix)
        path.write_text('private stdout content' if suffix == 'stdout.log' else '')
        outputs[suffix] = {'bytes': path.stat().st_size, 'sha256': reporting.sha(path)}
    receipt = {'argv': argv, 'cwd': '/home/secret-person/private-project',
               'started_utc': '2026-01-01T00:00:00+00:00', 'finished_utc': '2026-01-01T00:00:01+00:00',
               'exit_code': 0, 'wall_seconds': 1.0, 'child_peak_rss_mib': 32.0, 'outputs': outputs}
    (logs/(row['batch_id'] + '.receipt.json')).write_bytes(reporting.canonical(receipt))
    return {**{k: row[k] for k in ('batch_id', 'block_id', 'stratum_id', 'method_id', 'view', 'n', 'arm')},
            'exit_code': 0, 'wall_seconds': 1.0, 'peak_rss_mib': 32.0, 'input_bytes': 12345,
            'driver_stdout': 'secret-person: DO NOT EXPORT THIS',
            'output_files': {'evaluation.json': {'bytes': evaluation.stat().st_size, 'sha256': reporting.sha(evaluation)}}}


def test_sample_resources_count_eight_units_once_and_never_read_score_values():
    result = sample_result(item())
    assert reporting.sample_counts(result) == {'supplied_units': 8, 'record_count': 64, 'word_count': 16000,
        'eligible_record_count': 64, 'eligible_word_count': 16000, 'usable_record_count': 64}
    result['partitions']['evaluation']['rows'][0]['samples']['left']['word_count'] = 2001
    with pytest.raises(reporting.ReportingFailure, match='repeated_unit'):
        reporting.sample_counts(result)


def test_one_batch_preserves_command_hash_and_resources_but_not_private_values(tmp_path):
    row = item(); root, prepared = tmp_path/'main', tmp_path/'prepared'
    run = write_batch(root, prepared, row)
    lookup = {(row['block_id'], row['arm'], cell): {'records': 8, 'retained_words': 2000} for cell in CELLS}
    result = reporting.one_batch('main', root, prepared, row, run, lookup, 'stratum-01')
    serialized = json.dumps(result)
    assert all(secret not in serialized for secret in ('secret-person', 'private writing', 'private stdout content', str(tmp_path)))
    assert result['command']['redacted_argument_indices'] == [3, 11, 13]
    receipt = json.loads((root/'logs'/(row['batch_id'] + '.receipt.json')).read_bytes())
    assert result['command']['exact_original_argv_sha256'] == hashlib.sha256(reporting.canonical(receipt['argv'])).hexdigest()
    assert result['command']['argv'][11].startswith('<PRIMARY_PREPARED>/')
    assert result['observed_sample_counts']['record_count'] == 64
    assert result['output_bytes'] == (root/row['batch_id']/'evaluation.json').stat().st_size


def test_nonstarted_failure_preserves_missing_command_and_observed_counts(tmp_path):
    row = item(); root, prepared = tmp_path/'main', tmp_path/'prepared'
    run = {**row, 'exit_code': 124, 'status': 'not_started_run_wall_budget_exhausted',
           'wall_seconds': 0, 'peak_rss_mib': None, 'output_files': {}}
    lookup = {(row['block_id'], row['arm'], cell): {'records': 8, 'retained_words': 2000} for cell in CELLS}
    result = reporting.one_batch('main', root, prepared, row, run, lookup, 'stratum-01')
    assert result['status'] == 'not_started_run_wall_budget_exhausted'
    assert result['command'] is None and result['observed_sample_counts'] is None
    assert result['input_bytes'] is None


def test_unknown_command_or_modified_output_is_rejected_without_disclosure(tmp_path):
    row = item(); root, prepared = tmp_path/'main', tmp_path/'prepared'
    run = write_batch(root, prepared, row)
    lookup = {(row['block_id'], row['arm'], cell): {'records': 8, 'retained_words': 2000} for cell in CELLS}
    receipt_path = root/'logs'/(row['batch_id'] + '.receipt.json')
    receipt = json.loads(receipt_path.read_bytes()); receipt['argv'][6] = 'secret-unregistered-command'
    receipt_path.write_bytes(reporting.canonical(receipt))
    with pytest.raises(reporting.ReportingFailure, match='unrecognized_actual_command_literals'):
        reporting.one_batch('main', root, prepared, row, run, lookup, 'stratum-01')
    receipt['argv'][6] = 'account_history_analyzer'; receipt_path.write_bytes(reporting.canonical(receipt))
    (root/row['batch_id']/'evaluation.json').write_text('changed private data')
    with pytest.raises(reporting.ReportingFailure, match='recorded_output_artifact_changed'):
        reporting.one_batch('main', root, prepared, row, run, lookup, 'stratum-01')


def test_full_480_receipt_cli_is_sanitized_post_registration_reporting_only(tmp_path):
    prepared, relocated = tmp_path/'prepared', tmp_path/'relocated'
    prepared.mkdir(); relocated.mkdir()
    index, units = [], []
    for s in range(1, 4):
        for b in range(1, 11):
            block = f'stratum-{s:02d}-block-{b:02d}'
            for arm in sorted(reporting.ARMS):
                for method in sorted(reporting.METHODS): index.append(item(block, arm, method))
                units.extend({'block_id': block, 'stratum_id': f'stratum-{s:02d}', 'arm': arm, 'cell_id': cell,
                              'records': 8, 'retained_words': 2000} for cell in CELLS)
    (prepared/'batch-index.json').write_bytes(reporting.canonical(index))
    (prepared/'unit-metadata.json').write_bytes(reporting.canonical(units))
    freeze = {'status': 'frozen_before_first_style_score', 'batch_index_sha256': reporting.sha(prepared/'batch-index.json'),
              'replay_stratum_id': 'stratum-01', 'public_stratum_map': {f'stratum-{i:02d}': f'stratum-{i:02d}' for i in range(1, 4)},
              'bound_artifacts': [{'path': str(prepared/'unit-metadata.json'), 'sha256': reporting.sha(prepared/'unit-metadata.json')}]}
    freeze_path = tmp_path/'freeze.json'; freeze_path.write_bytes(reporting.canonical(freeze))
    roots = [tmp_path/'main', tmp_path/'replay']
    for mode, root, inputs in zip(('main', 'replay'), roots, (prepared, relocated)):
        selected = index if mode == 'main' else [r for r in index if r['stratum_id'] == 'stratum-01']
        runs = [write_batch(root, inputs, row) for row in selected]
        (root/'execution-index.json').write_bytes(reporting.canonical({'status': 'completed',
            'freeze_sha256': reporting.sha(freeze_path), 'replay': mode == 'replay', 'wall_seconds': 100.0, 'runs': runs}))
    output = tmp_path/'public-resources'
    command = [sys.executable, reporting.__file__, '--main-executions', str(roots[0]), '--replay-executions', str(roots[1]),
               '--prepared', str(prepared), '--freeze', str(freeze_path), '--out', str(output)]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stderr == ''
    public = (output/'batch-resources.json').read_text() + (output/'resource-summary.json').read_text()
    assert all(secret not in public for secret in ('secret-person', 'private writing', 'private stdout content', str(tmp_path)))
    summary = json.loads((output/'resource-summary.json').read_bytes())
    assert summary['per_batch_rows'] == 480 and summary['style_scores_recomputed'] == 0
    assert 'after scoring registration' in summary['registration_relationship']
    assert summary['resource_totals']['main']['observed_samples_summed_across_invocations']['record_count'] == 360 * 64
    assert summary['resource_totals']['replay']['observed_samples_summed_across_invocations']['eligible_word_count'] == 120 * 16000
    assert summary['resource_totals']['main']['maximum_reported_child_peak_rss_mib'] == 32.0
    rerun = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert rerun.returncode == 4 and 'report_output_already_exists' in rerun.stdout
