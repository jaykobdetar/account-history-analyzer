"""Independent synthetic extension checks; no real census input is read."""
from copy import deepcopy
import importlib.util
import inspect
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

v2=load('v2_independent_target',ROOT/'scripts/metadata_feasibility_v2.py')
old=load('v1_independent_target',ROOT/'scripts/metadata_feasibility.py')
fixtures=load('v1_independent_fixtures',ROOT/'tests/test_metadata_feasibility_independent.py')


def ref(path):return {'path':str(path),'sha256':v2.sha(path)}


def backend():
    return {'backend_registration':ref(ROOT/'protocol/EXACT_MATCHING_BACKEND_REGISTRATION.json'),
            'helper':ref(ROOT/'scripts/exact_blossom.py'),
            'dependency_manifest':ref(ROOT/'environment/isolated-matching-dependency.json')}


def make_plan(tmp_path,overlap=False):
    original,flags,registration=fixtures.synthetic_registration(tmp_path)
    p=json.loads(original.read_bytes())
    fixed_a='allowed-0-0' if overlap else 'fixed-a'
    witness=tmp_path/'old-private-synthetic.json'
    witness.write_text(json.dumps({'strata':{'stratum-02':{'public':{'stratum_id':'stratum-02'},
        'maximum_matching':{'cardinality':1,'pairs':[[fixed_a,'fixed-b']]},
        'candidate_cells':{fixed_a:{},'fixed-b':{}}}}}))
    p.update(original_feasibility_plan=ref(original),stratum_ids=['stratum-04','stratum-05'],
             community_pairs=p['community_pairs'][:2],matching_backend=backend(),
             external_fixed_witnesses=[{**ref(witness),'stratum_id':'stratum-02','source_stratum_id':'stratum-02'}],
             global_witness_quotas={'stratum-02':1,'stratum-04':2,'stratum-05':2})
    plan=tmp_path/'protocol/extension.json';plan.write_text(json.dumps(p))
    r=json.loads(registration.read_bytes());r.update(plan_sha256=v2.sha(plan),implementation_sha256=v2.sha(v2.__file__),
        matching_backend=p['matching_backend'],external_fixed_witnesses=p['external_fixed_witnesses'],global_witness_quotas=p['global_witness_quotas'])
    registration.write_text(json.dumps(r))
    return plan,flags,registration


def test_prefix_gates_and_cost_functions_are_byte_identical_to_frozen_v1():
    for name in ('select_prefix','compatible','edge_cost','identity_order'):
        assert inspect.getsource(getattr(v2,name))==inspect.getsource(getattr(old,name))


def test_registered_actual_isolated_matching_backend_on_synthetic_graph():
    match=v2.verify_matching_backend(backend())
    result=match('abcd',{('a','b'):0,('a','c'):5,('b','d'):5})
    assert result['cardinality']==2 and result['cost']==10 and result['pairs']==[('a','c'),('b','d')]


def test_unequal_global_quotas_backtrack_without_reusing_fixed_external_accounts():
    edges={'old':[('a','b')],'new-one':[('a','c'),('d','e'),('f','g')],
           'new-two':[('h','i'),('j','k')]}
    witness=v2.disjoint_strata_witness(edges,{'old':1,'new-one':2,'new-two':2})
    assert witness['old']==[('a','b')] and witness['new-one']==[('d','e'),('f','g')]
    assert len({a for pairs in witness.values() for pair in pairs for a in pair})==10


@pytest.mark.parametrize('overlap,expected_status',[(False,'feasible_before_contamination_audit'),(True,'fixed_design_capacity_deficit')])
def test_full_synthetic_new_pairs_stay_independent_of_fixed_prior_identity(tmp_path,overlap,expected_status):
    plan,flags,registration=make_plan(tmp_path,overlap)
    out,private=tmp_path/'out',tmp_path/'private'
    assert v2.run(plan,flags,registration,out,private)==0
    summary=json.loads((out/'feasibility-summary.json').read_bytes())
    assert summary['status']==expected_status and summary['evaluated_pair_cuts']==4
    assert [r['maximum_disjoint_blocks'] for r in summary['selected_calendar_witnesses']]==[2,2]
    assert [r['cut'] for r in summary['selected_calendar_witnesses']]==['1970-01-01T00:00:00Z']*2
    assert summary['global_witness_target_blocks']==5 and summary['global_witness_joint_deficit']==overlap
    witness=json.loads((private/'candidates-and-witness.json').read_bytes())
    assert set(witness['strata'])=={'stratum-04','stratum-05'}
    assert witness['globally_disjoint_intended_block_witness'] is None if overlap else len(witness['globally_disjoint_intended_block_witness'])==3
    assert summary['new_preprocessing_calls']==summary['new_style_distance_calls']==0


@pytest.mark.parametrize('field,value',[
    ('half_target_words',4999),('half_min_records',39),('half_max_words',5501),('half_band_days',181),
    ('within_period_four_cell_median_span_days_max',31),('all_eight_cell_word_ratio_max','12/10'),
    ('cuts',['1970-01-03T00:00:00Z']),('metadata_record_cap',3000001),('metadata_bytes_cap',1024**3+1),
])
def test_extension_rejects_changed_design_or_expanded_operational_cap(tmp_path,field,value):
    plan,*_=make_plan(tmp_path);p=json.loads(plan.read_bytes());p[field]=value
    with pytest.raises(ValueError):v2.validate_extension_plan(p)


def test_external_pair_exclusion_and_exact_quota_enforced(tmp_path):
    path,*_=make_plan(tmp_path);plan=json.loads(path.read_bytes())
    with pytest.raises(ValueError,match='identities'):v2.load_external_witnesses(plan,{'fixed-a'})
    plan['global_witness_quotas']['stratum-02']=2
    with pytest.raises(ValueError,match='exactly satisfy'):v2.load_external_witnesses(plan,set())


def test_backend_config_must_match_registered_helper_hash():
    config=backend();config['helper']['sha256']='wrong'
    with pytest.raises(ValueError,match='preregistered'):v2.verify_matching_backend(config)


def test_global_quota_missing_stratum_or_noninteger_rejected():
    for quotas in ({'a':1},{'a':1,'b':True},{'a':1,'b':-1}):
        with pytest.raises(ValueError):v2.disjoint_strata_witness({'a':[('x','y')],'b':[('z','w')]},quotas)
