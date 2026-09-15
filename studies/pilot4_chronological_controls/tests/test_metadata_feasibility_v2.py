"""Synthetic-only extended feasibility, binding and joint-witness checks."""
from datetime import datetime, timezone
from fractions import Fraction
import importlib.util
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
m=module('pilot4_v2_test',ROOT/'scripts/metadata_feasibility_v2.py')
old=module('pilot4_v1_test',ROOT/'scripts/metadata_feasibility.py')
PLAN={'half_band_days':180,'record_word_min':20,'record_word_max':500,
      'half_target_words':5000,'half_min_records':40,'half_max_words':5500,'half_max_records':200,
      'all_eight_cell_word_ratio_max':'11/10','all_eight_cell_record_ratio_max':'5/4',
      'within_period_four_cell_median_span_days_max':30}

def put(path,value):
    path.write_text(json.dumps(value));return {'path':str(path),'sha256':m.sha(path)}

@pytest.mark.parametrize('name',['select_prefix','compatible','edge_cost','identity_order','seconds'])
def test_unchanged_arithmetic_and_selection_source(name):
    assert inspect.getsource(getattr(m,name))==inspect.getsource(getattr(old,name))

def actual_config():
    return {k:{'path':str(ROOT/v),'sha256':m.sha(ROOT/v)} for k,v in {
        'backend_registration':'protocol/EXACT_MATCHING_BACKEND_REGISTRATION.json',
        'helper':'scripts/exact_blossom.py',
        'dependency_manifest':'environment/isolated-matching-dependency.json'}.items()}

def test_actual_registered_library_guard_then_synthetic_matching():
    match=m.verify_matching_backend(actual_config())
    result=match(['a','b','c','d'],{('a','b'):Fraction(1,2**4096),('c','d'):0,('a','c'):0,('b','d'):0})
    assert result['cardinality']==2 and result['cost']==0 and result['pairs']==[('a','c'),('b','d')]

def fake_backend(tmp_path,monkeypatch):
    install=tmp_path/'library';(install/'networkx').mkdir(parents=True)
    files=[]
    for i in range(595):
        path=install/('networkx/__init__.py' if i==0 else f'file-{i:03d}.txt')
        path.write_text('# Synthetic library marker\n')
        files.append({'path':str(path.relative_to(install)),'sha256':m.sha(path)})
    wheel=tmp_path/'synthetic.whl';wheel.write_bytes(b'Synthetic wheel marker')
    dep={'package':'networkx','version':'3.5','production_environment_modified':False,
         'wheel_path':str(wheel),'wheel_bytes':wheel.stat().st_size,'wheel_sha256':m.sha(wheel),
         'isolated_installation':str(install),'installed_files':files}
    depref=put(tmp_path/'dependency.json',dep)
    helper=tmp_path/'helper.py';helper.write_text('import networkx as nx\ndef exact_matching(*args): return None\n')
    href={'path':str(helper),'sha256':m.sha(helper)}
    regref=put(tmp_path/'backend.json',{'bindings':[depref,href]})
    monkeypatch.setitem(sys.modules,'networkx',SimpleNamespace(__version__='3.5',__file__=str(install/'networkx/__init__.py')))
    return {'backend_registration':regref,'helper':href,'dependency_manifest':depref},dep

@pytest.mark.parametrize('change',['extra_file','missing_file','changed_file','wrong_version','wrong_import_path','wheel_changed','binding_changed'])
def test_guard_rejects_changed_dependency_before_matching(tmp_path,monkeypatch,change):
    cfg,dep=fake_backend(tmp_path,monkeypatch)
    root=Path(dep['isolated_installation'])
    if change=='extra_file':(root/'extra.txt').write_text('changed')
    elif change=='missing_file':(root/'file-001.txt').unlink()
    elif change=='changed_file':(root/'file-001.txt').write_text('changed')
    elif change=='wrong_version':sys.modules['networkx'].__version__='3.6'
    elif change=='wrong_import_path':sys.modules['networkx'].__file__=str(root/'elsewhere.py')
    elif change=='wheel_changed':Path(dep['wheel_path']).write_bytes(b'changed')
    elif change=='binding_changed':Path(cfg['helper']['path']).write_text('# Changed\n')
    with pytest.raises(ValueError):m.verify_matching_backend(cfg)

def synthetic_run_files(tmp_path,*,new_count=5,shared_external=True):
    (tmp_path/'protocol').mkdir();(tmp_path/'tests').mkdir()
    marker=tmp_path/'tests/marker.py';marker.write_text('# synthetic binding\n')
    flags=[{'account_key':f'protected-{i:03d}','pilot1_or_pilot2_or_private_mandatory_exclusion':i<57,
            'pilot3_selected_scored_exposure':i>=57,'prior_capacity_only_exposure':False} for i in range(117)]
    flags.append({'account_key':'new-0-0','pilot1_or_pilot2_or_private_mandatory_exclusion':False,
                  'pilot3_selected_scored_exposure':False,'prior_capacity_only_exposure':True})
    flagpath=tmp_path/'flags.json';put(flagpath,{'accounts':flags})
    pairs=[['linux','linuxquestions'],['programming','learnprogramming']]
    rows=[]
    for s,pair in enumerate(pairs):
        for a in range(new_count):
            for community in pair:
                for base in [-864000,864000]:
                    for i in range(40):
                        rows.append({'record_id':f'new-{s}-{a}-{community}-{base}-{i}',
                          'account_key':f'new-{s}-{a}','community':community,'retained_words':125,'reason':None,
                          'created_utc':datetime.fromtimestamp(base+i,tz=timezone.utc).isoformat()})
    rows.append({'record_id':'excluded','account_key':'PROTECTED-000','reason':None})
    meta=tmp_path/'metadata.jsonl';meta.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    baseplan={**PLAN,'cuts':['1970-01-02T00:00:00Z','1970-01-01T00:00:00Z'],
       'exposure_flags_sha256':m.sha(flagpath),'address_space_bytes':4*1024**3,'census_wall_seconds':600,
       'intended_maximum_blocks_per_stratum':2}
    originalref=put(tmp_path/'original-plan.json',baseplan)
    external_account='new-0-0' if shared_external else 'old-0'
    oldentry={'public':{'stratum_id':'stratum-02','cut':'1970-01-01T00:00:00Z'},
              'maximum_matching':{'pairs':[[external_account,'old-1']],'cardinality':1},
              'candidate_cells':{external_account:{},'old-1':{}}}
    externalref=put(tmp_path/'old-witness.json',{'strata':{'stratum-02':oldentry}})
    externalref.update({'stratum_id':'stratum-02','source_stratum_id':'stratum-02'})
    plan={**baseplan,'community_pairs':pairs,'stratum_ids':['stratum-04','stratum-05'],
          'original_feasibility_plan':originalref,'matching_backend':actual_config(),
          'global_witness_quotas':{'stratum-02':1,'stratum-04':2,'stratum-05':2},
          'external_fixed_witnesses':[externalref],
          'metadata_record_cap':3000000,'metadata_bytes_cap':1024**3,
          'source_metadata':[{'path':str(meta),'bytes':meta.stat().st_size,'sha256':m.sha(meta)}]}
    planpath=tmp_path/'protocol/plan.json';put(planpath,plan)
    reg={'plan_sha256':m.sha(planpath),'implementation_sha256':m.sha(ROOT/'scripts/metadata_feasibility_v2.py'),
         'exposure_flags_sha256':m.sha(flagpath),'cost_rule':m.COST_RULE,'band_rule':m.BAND_RULE,'tie_rule':m.TIE_RULE,
         'test_files':[{'path':'tests/marker.py','sha256':m.sha(marker)}],
         **{k:plan[k] for k in ('matching_backend','external_fixed_witnesses','global_witness_quotas')}}
    regpath=tmp_path/'protocol/registration.json';put(regpath,reg)
    return planpath,flagpath,regpath

@pytest.mark.parametrize('count,feasible',[(5,True),(4,False)])
def test_synthetic_full_run_external_reservation_does_not_reduce_pair_capacity(tmp_path,monkeypatch,count,feasible):
    monkeypatch.setattr(m.resource,'setrlimit',lambda *a:None)
    paths=synthetic_run_files(tmp_path,new_count=count)
    out=tmp_path/'public';private=tmp_path/'private'
    assert m.run(*paths,out,private)==0
    result=json.loads((out/'feasibility-summary.json').read_text())
    assert result['globally_disjoint_intended_blocks_exist'] is feasible
    assert result['global_witness_joint_deficit'] is not feasible
    assert [r['stratum_id'] for r in result['selected_calendar_witnesses']]==['stratum-04','stratum-05']
    assert all(r['maximum_disjoint_blocks']==2 and r['cut']=='1970-01-01T00:00:00Z' for r in result['selected_calendar_witnesses'])
    assert result['counts']['excluded_rows']==1 and result['evaluated_pair_cuts']==4
    private_result=json.loads((private/'candidates-and-witness.json').read_text())
    assert 'new-0-0' in private_result['strata']['stratum-04']['candidate_cells']
    witness=private_result['globally_disjoint_intended_block_witness']
    if feasible:
        assert {s:len(e) for s,e in witness.items()}=={'stratum-02':1,'stratum-04':2,'stratum-05':2}
        assert len({a for edges in witness.values() for pair in edges for a in pair})==10
    else:assert witness is None

@pytest.mark.parametrize('field,value',[('half_band_days',181),('half_min_records',39),('cuts',[]),('metadata_record_cap',3000001),('metadata_bytes_cap',1024**3+1)])
def test_changed_design_or_excess_operational_cap_rejected(tmp_path,field,value):
    paths=synthetic_run_files(tmp_path)
    plan=json.loads(paths[0].read_bytes());plan[field]=value
    with pytest.raises(ValueError):m.validate_extension_plan(plan)

def test_external_fixed_witness_hash_and_protected_identity_checks(tmp_path):
    paths=synthetic_run_files(tmp_path)
    plan=json.loads(paths[0].read_bytes())
    with pytest.raises(ValueError,match='Invalid external'):m.load_external_witnesses(plan,{'new-0-0'})
    Path(plan['external_fixed_witnesses'][0]['path']).write_text('{}')
    with pytest.raises(ValueError,match='dependency changed'):m.load_external_witnesses(plan,set())

def test_variable_quota_global_backtracking():
    edges={'stratum-02':[('old-a','old-b')],
           'stratum-04':[('a','b'),('c','d'),('e','f')],
           'stratum-05':[('a','g'),('h','i')]}
    quotas={'stratum-02':1,'stratum-04':2,'stratum-05':2}
    answer=m.disjoint_strata_witness(edges,quotas)
    assert answer['stratum-04']==[('c','d'),('e','f')]
    assert m.disjoint_strata_witness({'stratum-02':[('a','b')],'stratum-04':[('a','c')]},{'stratum-02':1,'stratum-04':1}) is None
