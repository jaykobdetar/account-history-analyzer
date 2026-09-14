import pytest
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import load_snapshot
from account_history_analyzer.features import extract_records
from account_history_analyzer.findings import evidence_object, context_evidence, validate_references, finding


def test_TXT_18_evidence_actual_slice():
    s=load_snapshot('fixtures/arithmetic.jsonl','fixtures/arithmetic.snapshot.json')
    records=extract_records(s,AnalysisConfig.from_toml())
    e=context_evidence(records[0])
    f=finding('context',method='feature_evidence_v1',scope={},values={},records=[records[0]['id']],evidence=[e['evidence_id']])
    validate_references([f],[e],records,[],s)
    e['text']='fabricated'
    with pytest.raises(ValueError,match='actual source slice'):
        validate_references([f],[e],records,[],s)


def test_OUT_01_unknown_ids():
    s=load_snapshot('fixtures/arithmetic.jsonl','fixtures/arithmetic.snapshot.json')
    records=extract_records(s,AnalysisConfig.from_toml())
    e=evidence_object('not_supplied','text')
    with pytest.raises(ValueError,match='absent source'):
        validate_references([], [e], records, [], s)


def test_feature_context_uses_matching_segment(tmp_path):
    from account_history_analyzer.text import preprocess
    from account_history_analyzer.features import measure
    from account_history_analyzer.io import canonical_bytes,load_json
    record=dict(load_json('fixtures/arithmetic.snapshot.json'))
    r={'id':'example','kind':'comment','subreddit':None,'created_utc':None,'edit_state':'unknown',
       'language':'en','text':'ordinary first paragraph\n\nThe marker is here; it is real.', 'status':'present','title':None}
    c=AnalysisConfig.from_toml()
    f=measure(preprocess(r,record,c),c)
    e=context_evidence(f,feature_id='punctuation.semicolon.per_1000_word_tokens')
    assert e['segment_index']==1
    assert ';' in e['text']
    assert f['segments'][1]['text'][e['start']:e['end']]==e['text']
