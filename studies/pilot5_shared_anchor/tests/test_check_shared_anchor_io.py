"""Synthetic saved-file integration and mutation checks; no real source access."""
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import signal

import pytest

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
checker=module('shared_anchor_independent_io',ROOT/'scripts/check_shared_anchor.py')
producer=module('shared_anchor_synthetic_producer',ROOT/'scripts/prepare_shared_anchor.py')

def put(path,value):
    path.write_text(json.dumps(value));return path

def fixture(tmp_path,monkeypatch):
    monkeypatch.setenv('AHAS_NETWORK_ISOLATION','linux_seccomp_socket_denial')
    strata=[];metadata={};pool=[];extra_ids=[]
    for sid,n in [('stratum-02',2),('stratum-04',3),('stratum-05',2)]:
        accounts=[sid+'-synthetic-'+str(i) for i in range(n)];communities=[sid+'-x',sid+'-y']
        strata.append({'stratum_id':sid,'accounts':accounts,'communities':communities,'cut':'1970-01-01T00:00:00Z'})
        for a in accounts:
            for c in communities:
                for period in ('early','late'):
                    for i in range(88 if len(metadata)<11*88 else 87):
                        # The first11 cells have88 records, the remaining17 have87:
                        #28*87+11=2447. Farther records cannot alter the nearest40.
                        near=i<40;base=(-1 if period=='early' else 1)*(86400 if near else 90*86400)
                        rid=f'{sid}-{a}-{c}-{period}-{i}'
                        date=datetime.fromtimestamp(base+i,tz=timezone.utc).isoformat()
                        row={'record_id':rid,'account_key':a,'community':c,'period':period,'stratum_id':sid,
                             'created_utc':date,'retained_words':125 if near else 20,'reason':None}
                        metadata[rid]=row
                        pool.append({'account_key':a,'community':c,'period':period,'stratum_id':sid,'retained_words':row['retained_words'],
                          'record':{'id':rid,'account_id':a,'created_utc':date,'kind':'comment','text':'Synthetic fixture writing only.',
                                    'subreddit':c,'status':'present','thread_id':'synthetic-'+rid}})
                        if not near:extra_ids.append(rid)
    assert len(metadata)==2447
    old=put(tmp_path/'old-plan.json',{'strata':strata})
    selection=put(tmp_path/'old-selection.json',{'selected_metadata':metadata})
    pool_path=tmp_path/'pool.jsonl';pool_path.write_text(''.join(json.dumps(r)+'\n' for r in pool))
    prep=put(tmp_path/'old-preparation.json',{'selection_sha256':checker.sha(selection),'candidate_pool_sha256':checker.sha(pool_path),'plan_sha256':checker.sha(old)})
    purged=extra_ids[:195]
    audit=put(tmp_path/'audit.json',{'summary':{'gate_b_ready':True,'available_content_and_grouping_audit_complete':True},
      'engine_audit':{'status':'audited'},'purge_record_ids':purged,'surviving_candidate_ids':[rid for rid in metadata if rid not in set(purged)]})
    rules=put(tmp_path/'rules.json',{'half_band_days':180,'record_word_min':20,'record_word_max':500,
      'half_target_words':5000,'half_min_records':40,'half_max_words':5500,'half_max_records':200})
    plan={'phase':'frozen_before_five_sample_enumeration','script_sha256':checker.sha(ROOT/'scripts/prepare_shared_anchor.py'),
      'pool':str(pool_path),'audit':str(audit),'preparation_plan':str(old),'original_prefix_rules':str(rules),
      'source_selection_metadata':str(selection),'source_preparation_receipt':str(prep),
      'bindings':[{'path':str(p),'sha256':checker.sha(p)} for p in (pool_path,audit,old,rules,selection,prep)]}
    plan_path=put(tmp_path/'plan.json',plan)
    prepared=tmp_path/'prepared';public=tmp_path/'public'
    producer.prepare(plan_path,prepared,public);signal.alarm(0)
    return plan_path,prepared,public

def test_all_twenty_trials_winner_samples_and_saved_metadata_synthetic(tmp_path,monkeypatch):
    args=fixture(tmp_path,monkeypatch)
    result=checker.verify(*args)
    assert result['status']=='passed' and result['candidate_directions_verified']==20
    assert result['valid_directions']==20 and result['prepared_histories']==4
    assert result['unique_selected_records']==200 and result['shared_anchor_records']==40
    assert result['qualified_windows_per_history']==[10]*4

@pytest.mark.parametrize('mutation',['candidate_cost','selected_winner','sample_membership','window_counts','public_candidate_cost'])
def test_saved_result_mutations_are_rejected(tmp_path,monkeypatch,mutation):
    plan,prepared,public=fixture(tmp_path,monkeypatch)
    path=prepared/'selection.json';r=json.loads(path.read_bytes())
    if mutation=='candidate_cost':r['candidates'][0]['cost']['numerator']+=1
    elif mutation=='selected_winner':r['selected']=r['candidates'][1]
    elif mutation=='sample_membership':r['source_samples']['anchor'][0]=r['source_samples']['late_AX'][0]
    elif mutation=='window_counts':r['candidates'][0]['qualified_window_counts'][0]=7
    else:
        path=public/'candidate-enumeration.json';r=json.loads(path.read_bytes());r['candidates'][0]['cost']['numerator']+=1
    put(path,r)
    with pytest.raises(ValueError):checker.verify(plan,prepared,public)
