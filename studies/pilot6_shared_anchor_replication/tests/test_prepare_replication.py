"""Independent synthetic source-membership/finalization checks."""
import importlib.util
import json
from pathlib import Path
from datetime import datetime,timezone
import pytest

path=Path(__file__).resolve().parents[1]/'scripts/prepare_replication.py'
spec=importlib.util.spec_from_file_location('prepare_replication_test',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_fixed_five_source_cells():
    p={'account_a':'a','account_b':'b','community_x':'X','community_y':'Y'}
    assert list(m.cell_specs(p).values())==[('a','X','early'),('a','X','late'),('b','X','late'),('a','Y','late'),('b','Y','late')]


def test_buffer_original_id_date_word_prefix():
    rows=[{'record_id':str(i),'created_utc':datetime.fromtimestamp(10000000+i,timezone.utc).isoformat(),'retained_words':125} for i in range(90)]
    result=m.buffer_prefix(rows,10000000,'late')
    assert result==rows[:64] and sum(r['retained_words'] for r in result)==8000


def test_buffer_never_skips_oversize_endpoint_to_refill():
    rows=[{'record_id':str(i),'created_utc':datetime.fromtimestamp(10000000+i,timezone.utc).isoformat(),'retained_words':500} for i in range(70)]
    result=m.buffer_prefix(rows,10000000,'late')
    assert result==rows[:17] and len(result)<64


def synthetic_inputs(tmp_path,missing=False):
    cut=1500000000
    pair={'pair_id':'pilot6-pair-01','account_a':'a','account_b':'b','community_x':'X','community_y':'Y','stratum_id':'stratum-01',
          'cut':datetime.fromtimestamp(cut,timezone.utc).isoformat(),'cost':{'numerator':0,'denominator':1},'valid':True}
    entries=[]
    for j,(key,(a,c,period)) in enumerate(m.cell_specs(pair).items()):
        for i in range(64):
            timestamp=cut-10000+i if period=='early' else cut+1000+i+j
            record={'schema_version':'1.0.0','id':f'{key}-{i:03}','account_id':a,'kind':'comment','text':('word '*80).rstrip(),'status':'present',
                    'created_utc':datetime.fromtimestamp(timestamp,timezone.utc).isoformat(),'subreddit':c,'language':None,'edit_state':'unknown','thread_id':f't-{key}-{i}'}
            entries.append({'account_key':a,'community':c,'period':period,'stratum_id':'stratum-01','retained_words':80,'record':record})
    paths={n:tmp_path/(n+'.json') for n in ('buffer_selection','audit','exposure_flags','pilot5_selection')};paths['pool']=tmp_path/'pool.jsonl'
    paths['buffer_selection'].write_text(json.dumps({'pairs':[pair]}))
    ids=[e['record']['id'] for e in entries if not missing or e['record']['id'].startswith('anchor')]
    paths['audit'].write_text(json.dumps({'actionable':True,'summary':{'gate_b_ready':True,'available_content_and_grouping_audit_complete':True},'surviving_candidate_ids':ids,'purge_record_ids':[e['record']['id'] for e in entries if e['record']['id'] not in ids]}))
    paths['pool'].write_text(''.join(json.dumps(e)+'\n' for e in entries))
    paths['exposure_flags'].write_text('{}');paths['pilot5_selection'].write_text('{}')
    return {k:str(p) for k,p in paths.items()},entries


def test_final_history_source_fidelity_and_independent_p5_input_checker(tmp_path,monkeypatch):
    plan,entries=synthetic_inputs(tmp_path)
    monkeypatch.setattr(m,'checked_plan',lambda *_:plan);monkeypatch.setattr(m,'flags_excluded',lambda *_:(set(),set()))
    plan_file=tmp_path/'plan.json';plan_file.write_text('{}')
    m.finalize(plan_file,tmp_path/'out',tmp_path/'public')
    cohort=json.loads((tmp_path/'out/cohort-prepared.json').read_text());assert len(cohort['pairs'])==1
    from run_diagnostic import checked_index
    index=checked_index(cohort['pairs'][0]['index']);originals={e['record']['id']:e['record'] for e in entries}
    anchors=[]
    for c in index['cases']:
        records=list(map(json.loads,Path(c['input']).read_text().splitlines()));k=c['truth_k'] or c['control_junction_k'];anchors.append([r['id'] for r in records[:k]])
        assert k==63 # nearest-cut prefix reaches5040words in63 whole80-word comments
        for r in records:assert r==dict(originals[r['id']],account_id=c['case_id'])
    assert all(a==anchors[0] for a in anchors)
    assert [c['truth_k'] for c in index['cases']]==[None,63,None,63]


def test_failed_audited_samples_remain_visible_as_unavailable(tmp_path,monkeypatch):
    plan,_=synthetic_inputs(tmp_path,missing=True)
    monkeypatch.setattr(m,'checked_plan',lambda *_:plan);monkeypatch.setattr(m,'flags_excluded',lambda *_:(set(),set()))
    plan_file=tmp_path/'plan.json';plan_file.write_text('{}')
    m.finalize(plan_file,tmp_path/'out',tmp_path/'public')
    summary=json.loads((tmp_path/'public/selection-summary.json').read_text());assert summary['selected_new_pairs']==0 and summary['pair_shortfall']==10
    rows=json.loads((tmp_path/'public/pair-availability.json').read_text());assert rows[0]['selection_status']=='unavailable_after_audit'
    assert all(rows[0][k] is None for k in ('five_sample_word_ratio','five_sample_record_ratio','late_median_span_days'))
