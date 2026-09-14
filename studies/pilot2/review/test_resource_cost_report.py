"""Independent accounting checks; no production measurements are executed."""
import hashlib
import json
from pathlib import Path

import pytest

import build_resource_cost_report as review


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) + '\n')


def test_empty_measurements_remain_unknown():
    assert review.stats([]) == {'count': 0, 'minimum': None, 'median': None, 'maximum': None, 'sum': None}
    assert review.stats([2, 8, 4, 6]) == {'count': 4, 'minimum': 2, 'median': 5, 'maximum': 8, 'sum': 20}


def test_unfilled_slots_are_not_zero_cost_measurements():
    rows = [{'execution_class': 'unfilled', 'analyzer_invoked': False, 'status': 'not_executed',
             'outer_receipt': {'wall_seconds': 2, 'peak_rss_kib': 100},
             'inner_run_receipt': None, 'input_workload': None, 'bundle': None}]
    result = review.summarize_cases(rows)['unfilled']
    assert result['scheduled_slots'] == 1
    assert result['analyzer_invocations'] == 0
    assert result['outer_wall_seconds']['sum'] == 2
    assert result['inner_runtime_seconds']['minimum'] is None
    assert result['output_logical_bytes']['minimum'] is None


def test_bundle_accounting_keeps_canonical_and_receipt_bytes_separate(tmp_path):
    (tmp_path / 'evaluation.json').write_bytes(b'12345')
    (tmp_path / 'run_receipt.json').write_bytes(b'abc')
    save(tmp_path / 'checksums.json', {'evaluation.json': 'unused-for-size-check'})
    expected = sum(p.stat().st_size for p in tmp_path.iterdir())
    result = review.bundle_stats(tmp_path, {'max_file_bytes': 1000, 'max_total_bytes': expected, 'max_files': 3})
    assert result['within_artifact_limits']
    assert result['file_count'] == 3 and result['canonical_file_count'] == 2
    assert result['logical_bytes'] == expected
    assert result['canonical_bytes'] == expected - 3
    assert result['operational_receipt_bytes'] == 3
    assert not review.bundle_stats(tmp_path, {'max_file_bytes': 1000, 'max_total_bytes': expected - 1, 'max_files': 3})['within_artifact_limits']
    assert not review.bundle_stats(tmp_path, {'max_file_bytes': 1000, 'max_total_bytes': expected, 'max_files': 2})['within_artifact_limits']


def test_declared_missing_artifact_rejected(tmp_path):
    save(tmp_path / 'checksums.json', {'absent.json': 'hash'})
    with pytest.raises(ValueError, match='absent artifact'):
        review.bundle_stats(tmp_path, {'max_file_bytes': 1000, 'max_total_bytes': 1000, 'max_files': 32})


def test_metadata_size_and_escaping_paths_rejected_without_parsing(tmp_path, monkeypatch):
    monkeypatch.setattr(review, 'JSON_LIMIT', 5)
    (tmp_path / 'oversize.json').write_text('not json')
    with pytest.raises(ValueError, match='read limit'):
        review.read_json(tmp_path / 'oversize.json')
    with pytest.raises(ValueError, match='escapes'):
        review.resolve_under(tmp_path, '../outside')


def test_record_row_counts_deduplicate_input_paths_not_authored_content(tmp_path):
    # The review treats input lines as opaque bytes; no source JSON text fields are read.
    (tmp_path / 'a.jsonl').write_bytes(b'opaque row 1\nopaque row 2\n\n')
    (tmp_path / 'a.snapshot.json').write_bytes(b'{}\n')
    dataset = tmp_path / 'dataset.json'
    entry = {'input': 'a.jsonl', 'manifest': 'a.snapshot.json'}
    save(dataset, {'texts': [entry, entry]})
    result = review.input_workload(tmp_path, dataset)
    assert result['record_rows_in_distinct_input_files'] == 2
    assert result['distinct_input_files'] == 1
    assert result['dataset_input_and_manifest_bytes'] == sum(p.stat().st_size for p in tmp_path.iterdir())


def test_actual_log_receipts_are_hash_bound(tmp_path):
    stdout, stderr = tmp_path / 'run.stdout.log', tmp_path / 'run.stderr.log'
    stdout.write_bytes(b'aggregate only\n')
    stderr.write_bytes(b'')
    receipt = tmp_path / 'run.receipt.json'
    save(receipt, {'exit_code': 0, 'wall_seconds': 3.5, 'peak_rss_kib': 100,
                   'stdout_sha256': hashlib.sha256(stdout.read_bytes()).hexdigest(),
                   'stderr_sha256': hashlib.sha256(stderr.read_bytes()).hexdigest()})
    assert review.recorded_cost(tmp_path, receipt)['wall_seconds'] == 3.5
    stdout.write_bytes(b'changed\n')
    with pytest.raises(ValueError, match='no longer matches'):
        review.recorded_cost(tmp_path, receipt)


def test_aggregation_requires_both_completed_batches(tmp_path, monkeypatch):
    monkeypatch.setenv('AHAS_NETWORK_ISOLATION', 'linux_seccomp_socket_denial')
    with pytest.raises(ValueError, match='finish before aggregation'):
        review.build(tmp_path, tmp_path, tmp_path)


def test_configuration_binding_matches_registered_analytical_identity():
    baseline = review.read_json(Path(__file__).resolve().parents[1] / 'protocol/measurement-baseline.json')
    assert review.configuration_identity() == baseline['configuration_sha256']
