import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_replay import compare_replay


@pytest.fixture
def outputs(tmp_path):
    roots = [tmp_path / 'first', tmp_path / 'relocated']
    for number, root in enumerate(roots):
        batch = root / 'batch-one'
        batch.mkdir(parents=True)
        files = {'evaluation.json': '{}\n', 'report.md': 'Same canonical report\n',
                 'checksums.json': '{}\n', 'run_receipt.json': str(number)}
        for name, value in files.items():
            (batch / name).write_text(value)
        row = {'batch_id': 'batch-one', 'exit_code': 0,
               'output_files': {name: {'sha256': hashlib.sha256((batch / name).read_bytes()).hexdigest()}
                                for name in files}}
        (root / 'execution-index.json').write_text(json.dumps({'status': 'completed', 'replay': bool(number),
                                                             'freeze_sha256': 'a' * 64, 'runs': [row]}))
    return roots


def test_only_runtime_receipts_may_differ(outputs):
    result = compare_replay(*outputs, ['batch-one'])
    assert result['status'] == 'passed'
    assert result['canonical_artifact_comparisons'] == 3


def test_changed_report_is_detected_even_if_recorded_hash_is_updated(outputs):
    first, second = outputs
    path = second / 'batch-one/report.md'
    path.write_text('Changed canonical report')
    index_path = second / 'execution-index.json'
    index = json.loads(index_path.read_text())
    index['runs'][0]['output_files']['report.md']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    index_path.write_text(json.dumps(index))
    assert compare_replay(first, second, ['batch-one'])['status'] == 'failed'


def test_missing_batch_cannot_be_dropped(outputs):
    with pytest.raises(ValueError):
        compare_replay(*outputs, ['batch-one', 'missing-batch'])


def test_primary_receipt_is_not_a_fresh_replay(outputs):
    with pytest.raises(ValueError):
        compare_replay(outputs[0], outputs[0], ['batch-one'])


def test_changed_output_without_receipt_update_is_detected(outputs):
    (outputs[1] / 'batch-one/evaluation.json').write_text('{"changed":true}')
    result = compare_replay(*outputs, ['batch-one'])
    assert result['status'] == 'failed'
    assert result['mismatches'][0]['recorded_output_binding_matches'] is False


def test_repeated_expected_batch_does_not_inflate_replay_count(outputs):
    with pytest.raises(ValueError):
        compare_replay(*outputs, ['batch-one', 'batch-one'])


def test_repeated_primary_receipt_is_not_collapsed(outputs):
    path = outputs[0] / 'execution-index.json'
    index = json.loads(path.read_text())
    index['runs'].append(dict(index['runs'][0]))
    path.write_text(json.dumps(index))
    with pytest.raises(ValueError):
        compare_replay(*outputs, ['batch-one'])
