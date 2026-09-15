"""Metadata selection tests do not invoke the analyzer or read real records."""
import importlib.util
from fractions import Fraction
from pathlib import Path
import sys

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/metadata_replication.py'
spec=importlib.util.spec_from_file_location('replication_meta',SCRIPT)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def row(a='a',b='b',cost=Fraction(1),**updates):
    return {'account_a':a,'account_b':b,'cost':cost,'valid':True,'stratum_id':'stratum-01',
            'cut':'2017-01-01T00:00:00Z','community_x':'X','community_y':'Y',**updates}


def test_direction_cost_precedes_calendar_and_identity():
    expensive=row(cost=Fraction(3,2),cut='2016-01-01T00:00:00Z')
    cheaper=row(a='b',b='a',cost=Fraction(4,3))
    assert list(m.choose_edges([expensive,cheaper]).values())==[cheaper]


def test_invalid_low_cost_never_selected():
    valid=row(cost=Fraction(9))
    assert list(m.choose_edges([row(cost=Fraction(0),valid=False),valid]).values())==[valid]


def test_exact_fraction_cost_no_float_rounding():
    a=row(cost=Fraction(10**30+1,10**30))
    b=row(a='b',b='a',cost=Fraction(1))
    assert list(m.choose_edges([a,b]).values())==[b]


def test_calendar_tie_and_permutation_stability():
    early=row(cut='2011-01-01T00:00:00Z');late=row(cut='2012-01-01T00:00:00Z')
    assert m.choose_edges([early,late])==m.choose_edges([late,early])
    assert list(m.choose_edges([late,early]).values())==[early]


def test_unordered_edges_disjoint_from_direction_order():
    assert m.edge_key(row())==m.edge_key(row(a='b',b='a'))
    assert len(m.choose_edges([row(),row(a='b',b='c')]))==2


def test_raw_40_is_necessary_for_late_only_account_not_80():
    rows=[{'record_id':str(i),'timestamp':1000+i,'retained_words':125} for i in range(40)]
    assert m.select_prefix(rows,1000,'late',m.DESIGN)['records']==40
    assert m.select_prefix(rows,1000,'early',m.DESIGN) is None


def test_whole_comment_ceiling_not_repaired_by_skipping():
    rows=[{'record_id':str(i),'timestamp':i,'retained_words':500} for i in range(40)]
    assert m.select_prefix(rows,0,'late',m.DESIGN) is None


def test_five_sample_no_reciprocal_early_requirement():
    cells={};entries={}
    from datetime import datetime,timezone
    for j,key in enumerate(m.KEYS):
        early=j==0;cut=10000000
        rs=[{'record_id':f'{key}-{i:03}','timestamp':cut+(-10000+i if early else 1000+i+j), 'retained_words':80} for i in range(64)]
        cells[key]=m.select_prefix(rs,cut,'early' if early else 'late',m.DESIGN)
        for r in rs:entries[r['record_id']]={'record':{'created_utc':datetime.fromtimestamp(r['timestamp'],timezone.utc).isoformat()}}
    result=m.evaluate(cells,entries)
    assert result['valid'] and min(result['qualified_window_counts'])>=8
    assert len(cells)==5
