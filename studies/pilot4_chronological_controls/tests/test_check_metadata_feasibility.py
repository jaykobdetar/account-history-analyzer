"""Synthetic checks of the independent all-calendar metadata verifier."""
import importlib.util
import json
from pathlib import Path
from fractions import Fraction
import pytest

HERE=Path(__file__).resolve().parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

check=load('metadata_checker',HERE.parent/'scripts/check_metadata_feasibility.py')
fixtures=load('metadata_checker_fixtures',HERE/'test_metadata_feasibility_independent.py')

@pytest.fixture
def complete(tmp_path):
    plan,flags,registration=fixtures.synthetic_registration(tmp_path)
    p=check.read(plan)
    p['cuts']=[f'{1965+i//12:04d}-{1+i%12:02d}-01T00:00:00Z' for i in range(101)]
    plan.write_text(json.dumps(p))
    r=check.read(registration);r.update(plan_sha256=check.sha(plan),registered_utc='2000-01-01T00:00:00+00:00')
    registration.write_text(json.dumps(r))
    public,private=tmp_path/'public',tmp_path/'private'
    assert fixtures.feasibility.run(plan,flags,registration,public,private)==0
    receipt=tmp_path/'receipt.json';receipt.write_text(json.dumps({'exit_code':0,'started_utc':'2001-01-01T00:00:00+00:00'}))
    return (plan,flags,registration,public,private/'candidates-and-witness.json',receipt)


def test_full303_recomputation_with_disjoint_two_block_witness(complete):
    result=check.verify(*complete)
    assert result['status']=='passed' and result['calendar_rows_independently_recomputed']==303
    assert result['maximum_blocks_by_stratum']==dict.fromkeys(('stratum-01','stratum-02','stratum-03'),2)
    assert result['chosen_candidate_cells_verified']==48
    assert result['chosen_candidate_records_verified']==1920
    assert result['preprocessor_calls']==result['source_archive_reads']==0


@pytest.mark.parametrize('target,mutate,error',[
    ('all-calendar-cuts.json',lambda r:r[0].update(maximum_disjoint_blocks=3),'calendar_capacity'),
    ('feasibility-summary.json',lambda r:r['selected_calendar_witnesses'][0].update(cut='1970-02-01T00:00:00Z'),'public_chosen'),
])
def test_false_public_capacity_or_calendar_rejected(complete,target,mutate,error):
    p=complete[3]/target;r=check.read(p);mutate(r);p.write_text(json.dumps(r))
    with pytest.raises(ValueError,match=error):check.verify(*complete)


def test_original_metadata_change_rejected(complete):
    p=complete[4];r=check.read(p)
    a=next(iter(r['strata']['stratum-01']['candidate_cells'].values()))
    a['X/early']['rows'][0]['retained_words']+=1;p.write_text(json.dumps(r))
    with pytest.raises(ValueError,match='witness_original_metadata_changed'):check.verify(*complete)


def test_csv_rational_cost_change_rejected(complete):
    p=complete[3]/'all-calendar-cuts.csv'
    import csv
    with p.open(newline='') as f: rows=list(csv.DictReader(f))
    rows[0]['cost_denominator']='2'
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    with pytest.raises(ValueError,match='csv_exact_cost'):check.verify(*complete)


def test_matching_independent_unmatched_and_fractional_tie():
    assert check.matching('abcd',{('a','b'):0,('a','c'):2,('b','d'):2})==(2,Fraction(4),[('a','c'),('b','d')])
    edges={('a','b'):Fraction(1)+Fraction(1,10**40),('c','d'):1,('a','c'):1,('b','d'):1}
    assert check.matching('abcd',edges)==(2,Fraction(2),[('a','c'),('b','d')])


def test_prefix_outer_endpoints_and_conjunctive_ceiling():
    day=check.DAY
    records=[(-180*day,f'r{i:03}',125) for i in range(40)]
    assert check.cell(records,0,'early')['records']==40
    assert check.cell([(t-1,i,w) for t,i,w in records],0,'early') is None
    assert check.cell([(180*day,i,w) for t,i,w in records],0,'late') is None
    assert check.cell([(0,i,w) for t,i,w in records],0,'late')['words']==5000
    assert check.cell([(i,str(i),20) for i in range(200)]+[(201,'large',500)],0,'late') is None
