from pathlib import Path
from account_history_analyzer.io import load_snapshot, load_json, canonical_bytes
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.pipeline import analyze
from account_history_analyzer.artifacts import write_artifacts


def test_M1_arithmetic_end_to_end(tmp_path):
    result = analyze(load_snapshot('fixtures/arithmetic.jsonl','fixtures/arithmetic.snapshot.json'))
    write_artifacts(result, tmp_path/'report')
    output = load_json(tmp_path/'report'/'results.json')
    assert output['modules']['coverage']['payload']['unique_records'] == 6
    records = [__import__('json').loads(line) for line in result.files['records_features.jsonl'].splitlines()]
    assert [r['counts']['retained_words'] for r in records] == [8,8,9,4,4,3]
    assert output['modules']['text']['payload']['body']['counts']['retained_words'] == 36
    assert output['modules']['activity']['payload']['event_count'] == 6
    assert output['modules']['ai_text_detection']['reason_codes'] == ['not_implemented_in_v1']
    assert 'not_established' in (tmp_path/'report'/'report.md').read_text()
    assert result.ingest_receipt['duplicate_rows'] == 1


def test_M1_empty_and_short(tmp_path):
    result = analyze(load_snapshot('fixtures/empty.jsonl','fixtures/empty.snapshot.json'))
    write_artifacts(result, tmp_path/'empty')
    assert result.results['modules']['activity']['status'] == 'insufficient_data'
    assert result.results['modules']['text']['status'] == 'insufficient_data'
    assert result.results['modules']['style']['status'] in ('not_run','insufficient_data')
    assert b'NaN' not in canonical_bytes(result.results)
