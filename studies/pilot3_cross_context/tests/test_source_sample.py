"""Synthetic-only raw-byte/token-offset verification tests; never real prose."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_source_sample as checker
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import digest
from account_history_analyzer.pipeline import implementation_identity
from account_history_analyzer.text import preprocess


def raw_record(identifier, *, words=20, account='synthetic-account'):
    return {'id': identifier, 'user': account, 'root': 'synthetic-thread',
            'reply_to': 'synthetic-parent', 'timestamp': 1483228800,
            'text': 'visible ' * words + '`hidden code words` 123', 'meta': {'subreddit': 'Synthetic'}}


def metadata(raw):
    source = json.loads(raw)
    record = {'id': source['id'], 'kind': 'comment', 'text': source['text'], 'status': 'present',
              'created_utc': '2017-01-01T00:00:00Z', 'language': None,
              'subreddit': 'Synthetic', 'edit_state': 'unknown'}
    result = preprocess(record, {'default_language': 'en', 'text_format': 'markdown'}, AnalysisConfig.from_toml())
    words = sum(map(len, result['word_tokens']))
    return {'account_key': source['user'].casefold(), 'community': 'Synthetic', 'record_id': source['id'],
            'created_utc': '2017-01-01T00:00:00Z', 'retained_words': words,
            'reason': None if words >= 20 else 'below_frozen_record_word_guard',
            'source_line_sha256': hashlib.sha256(raw).hexdigest()}


@pytest.fixture
def synthetic_source(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    private = tmp_path / 'private'
    private.mkdir()
    run = private / 'synthetic-run'
    run.mkdir()
    public = tmp_path / 'public'
    public.mkdir()
    raw_lines = [(json.dumps(raw_record(f'synthetic-{index}', words=19 if index % 3 == 0 else 21),
                            ensure_ascii=False, separators=(', ', ': ')) + '\r\n').encode() for index in range(120)]
    raw_lines.append(checker.canonical(raw_record('protected-record', account='protected')))
    archive_path = source / 'synthetic.zip'
    with zipfile.ZipFile(archive_path, 'w') as archive:
        archive.writestr('utterances.jsonl', b''.join(raw_lines))
    excluded = {'complete_for_known_pilot_sources': True, 'accounts': [{'account_key': 'protected'}]}
    exclusions = private / 'exclusions-mandatory.json'
    exclusions.write_bytes(checker.canonical(excluded))
    rows = [metadata(raw) for raw in raw_lines[:-1]]
    row_path = run / 'record-eligibility.jsonl'
    row_path.write_bytes(b''.join(checker.canonical(row) for row in rows))
    config = AnalysisConfig.from_toml()
    fp, _, _ = implementation_identity()
    plan = {'implementation_fingerprint': fp, 'analysis_config_sha256': digest(config.analytical()),
            'sources': [{'community': 'Synthetic', 'archive': str(archive_path),
                         'sha256': checker.file_hash(archive_path), 'bytes': archive_path.stat().st_size}],
            'limits': {'max_source_rows_per_pass': 10000, 'max_source_uncompressed_bytes_per_pass': 10000000,
                       'max_wall_seconds': 300, 'max_address_space_bytes': checker.MAX_ADDRESS_SPACE}}
    plan_path = tmp_path / 'plan.json'
    plan_path.write_bytes(checker.canonical(plan))
    (public / 'start-binding.json').write_bytes(checker.canonical({'plan_sha256': checker.file_hash(plan_path),
                                                               'exclusions_sha256': checker.file_hash(exclusions)}))
    (public / 'private-artifact-hashes.json').write_bytes(checker.canonical({'record-eligibility.jsonl': {'sha256': checker.file_hash(row_path)}}))
    (public / 'source-inventory.json').write_bytes(checker.canonical({'sources': [{
        'community': 'Synthetic', 'counts': {'source_records': len(raw_lines)},
        'utterances_sha256': hashlib.sha256(b''.join(raw_lines)).hexdigest(),
        'utterances_bytes': sum(map(len, raw_lines))}]}))
    return plan_path, source, private, public, rows, raw_lines


def test_sample_is_exact_100_hash_ranks_independent_of_input_order_and_outcome(synthetic_source):
    plan, source, private, public, rows, _ = synthetic_source
    path = private / 'synthetic-run' / 'record-eligibility.jsonl'
    selected, population, count = checker.choose_sample(path, {'protected'})
    oracle = sorted(rows, key=lambda row: (hashlib.sha256(('ahas-pilot3-source-check-v1:' + row['record_id']).encode()).digest(), row['record_id']))[:100]
    assert selected == oracle and population == count == 120
    path.write_bytes(b''.join(checker.canonical(row) for row in reversed(rows)))
    assert checker.choose_sample(path, {'protected'})[0] == selected


def test_rederive_counts_only_word_kind_and_never_reads_word_tokens(monkeypatch):
    raw = (json.dumps(raw_record('sample', words=19)) + '\r\n').encode()
    original = checker.preprocess
    class NoWordTokens(dict):
        def __getitem__(self, key):
            assert key != 'word_tokens', 'Checker must use an independent token-offset tally'
            return super().__getitem__(key)
    monkeypatch.setattr(checker, 'preprocess', lambda *args: NoWordTokens(original(*args)))
    result = checker.rederive(raw, 'Synthetic', set(), AnalysisConfig.from_toml())
    assert result['retained_words'] == 19
    assert result['reason'] == 'below_frozen_record_word_guard'
    assert result['source_line_sha256'] == hashlib.sha256(raw).hexdigest()


def test_protected_source_never_reaches_preprocessor(monkeypatch):
    raw = checker.canonical(raw_record('secret', account='PrOtEcTeD'))
    monkeypatch.setattr(checker, 'preprocess', lambda *args: pytest.fail('Protected writing reached preprocessing'))
    with pytest.raises(checker.SourceSampleError, match='protected_identity_never_preprocessed'):
        checker.rederive(raw, 'Synthetic', {'protected'}, AnalysisConfig.from_toml())


def test_full_streamed_check_preserves_bytes_and_outputs_only_aggregates(synthetic_source):
    plan, source, private, public, _, _ = synthetic_source
    report = checker.check_sample(plan, source, private, 'synthetic-run', census_root=public)
    assert report['status'] == 'pass' and report['mismatch_counts'] == {}
    assert report['sample_size'] == report['preprocessing_calls'] == 100
    assert report['source_passes'] == 1 and report['source_rows'] == 121
    assert set(report['sample_outcomes']) == {'eligible', 'below_frozen_record_word_guard'}
    rendered = json.dumps(report)
    assert 'synthetic-account' not in rendered and 'synthetic-11' not in rendered
    assert 'visible ' not in rendered and 'hidden code words' not in rendered


def test_checker_detects_wrong_retained_counts_even_after_metadata_rehash(synthetic_source):
    plan, source, private, public, rows, _ = synthetic_source
    row_path = private / 'synthetic-run' / 'record-eligibility.jsonl'
    selected, _, _ = checker.choose_sample(row_path, {'protected'})
    chosen_id = selected[0]['record_id']
    for row in rows:
        if row['record_id'] == chosen_id:
            row['retained_words'] += 1
    row_path.write_bytes(b''.join(checker.canonical(row) for row in rows))
    (public / 'private-artifact-hashes.json').write_bytes(checker.canonical({'record-eligibility.jsonl': {'sha256': checker.file_hash(row_path)}}))
    report = checker.check_sample(plan, source, private, 'synthetic-run', census_root=public)
    assert report['status'] == 'fail'
    assert report['mismatch_counts'] == {'retained_words_mismatch': 1}


def test_protected_metadata_exclusion_is_checked_before_sampling(synthetic_source):
    _, _, private, _, rows, _ = synthetic_source
    rows[-1]['account_key'] = 'protected'
    path = private / 'synthetic-run' / 'record-eligibility.jsonl'
    path.write_bytes(b''.join(checker.canonical(row) for row in rows))
    with pytest.raises(checker.SourceSampleError, match='protected_identity_in_preprocessing_metadata'):
        checker.choose_sample(path, {'protected'})


def test_fixed_sample_does_not_silently_shrink(synthetic_source):
    _, _, private, _, rows, _ = synthetic_source
    path = private / 'synthetic-run' / 'record-eligibility.jsonl'
    path.write_bytes(b''.join(checker.canonical(row) for row in rows[:99]))
    with pytest.raises(checker.SourceSampleError, match='fewer_than_100'):
        checker.choose_sample(path, {'protected'})


def test_archive_change_rejected_before_any_preprocessing(synthetic_source, monkeypatch):
    plan, source, private, public, _, _ = synthetic_source
    with (source / 'synthetic.zip').open('ab') as handle:
        handle.write(b'changed archive')
    monkeypatch.setattr(checker, 'preprocess', lambda *args: pytest.fail('Changed archive reached preprocessing'))
    with pytest.raises(checker.SourceSampleError, match='archive_identity_changed'):
        checker.check_sample(plan, source, private, 'synthetic-run', census_root=public)


def test_integer_utc_derivation_rejects_missing_or_imputed_times():
    assert checker._stamp(1483228800) == '2017-01-01T00:00:00Z'
    assert checker._stamp(1483228800.0) is None
    assert checker._stamp(True) is None
    assert checker._stamp('1483228800') is None
