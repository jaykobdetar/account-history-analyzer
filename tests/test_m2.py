from pathlib import Path
import json
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import load_snapshot, canonical_bytes, load_json
from account_history_analyzer.pipeline import analyze
from account_history_analyzer.artifacts import write_artifacts
from account_history_analyzer.reuse import shingle_set, shingle_metrics


def test_M2_shipped_shingle_oracle():
    o=json.loads(Path('fixtures/numerical_oracles.json').read_text())['shingles']
    r=shingle_metrics(shingle_set([o['tokens_a']],o['n']),shingle_set([o['tokens_b']],o['n']))
    assert r['left_shingles']==r['right_shingles']==3
    assert (r['intersection'],r['union'],r['jaccard'])==(2,4,0.5)
    assert r['left_in_right']==r['right_in_left']==2/3


def test_RE_01_short_arithmetic_distinctions():
    r=analyze(load_snapshot('fixtures/arithmetic.jsonl','fixtures/arithmetic.snapshot.json'))
    groups=r.results['modules']['reuse']['payload']['exact_groups']
    g=next(g for g in groups if g['match_type']=='normalized_prose_identical')
    assert list(g['record_ids'])==['arithmetic_001','arithmetic_002']
    assert g['substantial'] is False
    assert all(g['match_type']!='raw_text_identical' for g in groups)


def make_snapshot(tmp_path):
    manifest=load_json('fixtures/arithmetic.snapshot.json')
    records=[]
    for i in range(3):
        records.append({'schema_version':'1.0.0','id':str(i),'account_id':'arithmetic',
                        'kind':'comment','status':'present','text':' '.join(['alpha beta gamma delta epsilon']*12),
                        'created_utc':f'2025-01-01T00:00:0{i}Z'})
    (tmp_path/'m.json').write_bytes(canonical_bytes(manifest))
    (tmp_path/'r.jsonl').write_bytes(b''.join(canonical_bytes(r) for r in records))
    return load_snapshot(tmp_path/'r.jsonl',tmp_path/'m.json')


def test_M2_evidence_and_resource_limit(tmp_path):
    s=make_snapshot(tmp_path)
    result=analyze(s)
    assert len(result.results['modules']['reuse']['payload']['pairs'])==3
    assert result.results['findings']
    assert result.files['evidence.jsonl']
    write_artifacts(result,tmp_path/'complete')
    limited=analyze(s,AnalysisConfig.from_mapping({'reuse':{'max_candidate_pairs':0}}))
    assert limited.exit_code==4
    reuse=limited.results['modules']['reuse']
    assert reuse['status']=='resource_limit'
    assert reuse['payload']['pairs']==()
    assert reuse['payload']['exact_groups']
    assert reuse['payload']['budget_complete'] is False
    write_artifacts(limited,tmp_path/'limited')
