"""Execution-index checks only; these fixtures are never fed to the evaluator."""
import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from run_scoring import ARMS, METHODS, child_wall_budget, failure_row, safe_child, validate_batches


@pytest.fixture
def prepared(tmp_path):
    base_hashes = {}
    for i in range(8):
        for suffix in ['jsonl', 'snapshot.json']:
            path = tmp_path / f'unit-{i}.{suffix}'
            path.write_bytes(b'{}\n')
            base_hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    rows = []
    for s in range(3):
        for b in range(10):
            for arm in sorted(ARMS):
                for method, view, n in sorted(METHODS):
                    doc = {'format': 'paired_text',
                           'dataset_id': f's{s}-b{b}/{arm}/{view}',
                           'texts': [{'input': f'unit-{i}.jsonl', 'manifest': f'unit-{i}.snapshot.json'} for i in range(8)],
                           'pairs': [{'split': 'evaluation'} for _ in range(16)],
                           'protocol': {'frozen_threshold': None, 'registered_before_evaluation': True,
                                        'distance': {'method_id': method, 'view': view, 'n': n}}}
                    name = f's{s}-b{b}-{arm}-{view}.json'
                    (tmp_path / name).write_text(json.dumps(doc))
                    checksum = hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()
                    rows.append({'stratum_id': f's{s}', 'block_id': f's{s}-b{b}', 'batch_id': name[:-5],
                                 'method_id': method, 'view': view, 'n': n, 'arm': arm,
                                 'dataset': name, 'dataset_sha256': checksum,
                                 'input_hashes': {**base_hashes, name: checksum}})
    return tmp_path, rows


def test_complete_index_and_all_hashes(prepared):
    root, rows = prepared
    assert validate_batches(root, rows) == ['s0', 's1', 's2']


def test_no_silent_smaller_denominator(prepared):
    root, rows = prepared
    with pytest.raises(ValueError, match='360'):
        validate_batches(root, rows[:-1])


def test_repeated_method_cannot_replace_missing_method(prepared):
    root, rows = prepared
    rows[1] = copy.deepcopy(rows[0])
    rows[1]['batch_id'] = 'different-output-id'
    with pytest.raises(ValueError, match='Repeated'):
        validate_batches(root, rows)


def test_unfrozen_manifest_change(prepared):
    root, rows = prepared
    (root / 'unit-1.snapshot.json').write_text('{"unexpected":true}')
    with pytest.raises(ValueError, match='changed'):
        validate_batches(root, rows)


def test_missing_source_hash(prepared):
    root, rows = prepared
    del rows[0]['input_hashes']['unit-1.jsonl']
    with pytest.raises(ValueError, match='hash-bound'):
        validate_batches(root, rows)


def test_prepared_dataset_cannot_request_confirmation(prepared):
    root, rows = prepared
    first = rows[0]
    path = root / first['dataset']
    doc = json.loads(path.read_text())
    doc['pairs'][0]['split'] = 'confirmation'
    path.write_text(json.dumps(doc))
    first['dataset_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    first['input_hashes'][path.name] = first['dataset_sha256']
    with pytest.raises(ValueError, match='evaluation-only'):
        validate_batches(root, rows)


@pytest.mark.parametrize('path', ['/tmp/unregistered.json', '../unregistered.json'])
def test_paths_cannot_escape(tmp_path, path):
    with pytest.raises(ValueError):
        safe_child(tmp_path, path)


def test_symlink_escape(tmp_path):
    (tmp_path / 'escape').symlink_to(tmp_path.parent, target_is_directory=True)
    with pytest.raises(ValueError):
        safe_child(tmp_path, 'escape/source.json')


@pytest.mark.parametrize('defect', ['duplicate', 'missing', 'unsafe'])
def test_all_output_ids_are_validated_before_any_launch(prepared, defect):
    root, rows = prepared
    if defect == 'duplicate': rows[-1]['batch_id'] = rows[0]['batch_id']
    if defect == 'missing': del rows[-1]['batch_id']
    if defect == 'unsafe': rows[-1]['batch_id'] = '../outside'
    with pytest.raises(ValueError, match='batch ID'):
        validate_batches(root, rows)


def test_child_cannot_receive_a_fresh_full_budget_at_run_deadline():
    assert child_wall_budget(0) == 300
    assert child_wall_budget(7100) == 95
    assert child_wall_budget(7195) == 0
    assert child_wall_budget(7201) == 0


def test_driver_failure_keeps_registered_identity(prepared):
    _, rows = prepared
    result = failure_row(rows[0], 'FileNotFoundError')
    assert result['batch_id'] == rows[0]['batch_id']
    assert result['status'] == 'execution_driver_failed'
    assert result['exit_code'] == 1
