"""Synthetic202-cut independent reconstruction and fixed-witness checks."""
import importlib.util
import json
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

check=load('independent_v2_checker',ROOT/'scripts/check_metadata_feasibility_v2.py')
fixtures=load('independent_v2_generator',ROOT/'tests/test_metadata_feasibility_v2_independent.py')


def generated(tmp_path,overlap=False):
    plan,flags,registration=fixtures.make_plan(tmp_path,overlap)
    p=check.read(plan);old_path=Path(p['original_feasibility_plan']['path']);old=check.read(old_path)
    cuts=[f'{1965+i//12:04d}-{1+i%12:02d}-01T00:00:00Z' for i in range(101)]
    old['cuts']=cuts;old_path.write_text(json.dumps(old));p['original_feasibility_plan']['sha256']=check.sha(old_path)
    p['cuts']=cuts;plan.write_text(json.dumps(p))
    r=check.read(registration);r.update(plan_sha256=check.sha(plan),registered_utc='2000-01-01T00:00:00+00:00');registration.write_text(json.dumps(r))
    out,private=tmp_path/'census',tmp_path/'private'
    assert fixtures.v2.run(plan,flags,registration,out,private)==0
    receipt=tmp_path/'receipt.json';receipt.write_text(json.dumps({'exit_code':0,'started_utc':'2001-01-01T00:00:00+00:00'}))
    prior=tmp_path/'old-independent.json';prior.write_text(json.dumps({'status':'passed','maximum_blocks_by_stratum':{'stratum-02':1},
        'input_hashes':{'private':p['external_fixed_witnesses'][0]['sha256']}}))
    return plan,flags,registration,out,private/'candidates-and-witness.json',receipt,prior


@pytest.mark.parametrize('overlap',[False,True])
def test_all202_rows_and_global_overlap_deficit_independently_verified(tmp_path,overlap):
    paths=generated(tmp_path,overlap);result=check.verify(*paths)
    assert result['status']=='passed' and result['calendar_rows_independently_recomputed']==202
    assert result['maximum_blocks_by_stratum']=={'stratum-02':1,'stratum-04':2,'stratum-05':2}
    assert result['global_registered_1_2_2_target_feasible'] is not overlap
    assert result['source_archive_reads']==result['preprocessor_calls']==result['style_scores_computed']==0


def test_changed_original_prior_witness_binding_rejected(tmp_path):
    paths=generated(tmp_path);r=check.read(paths[-1]);r['input_hashes']['private']='wrong';paths[-1].write_text(json.dumps(r))
    with pytest.raises(ValueError,match='prior_independent_witness'):check.verify(*paths)


def test_wrong_global_witness_or_csv_cost_rejected(tmp_path):
    paths=generated(tmp_path);r=check.read(paths[4]);r['globally_disjoint_intended_block_witness']=None;paths[4].write_text(json.dumps(r))
    with pytest.raises(ValueError,match='global_witness'):check.verify(*paths)
