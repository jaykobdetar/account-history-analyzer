"""Synthetic endpoint checks for the reporting-only metadata diagnosis."""
from fractions import Fraction
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('edge_diagnosis',Path(__file__).resolve().parents[1]/'scripts/diagnose_pre_post_audit_edges.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def rows(n,words=125):return [{'record_id':f'synthetic-{i:03d}','timestamp':i,'retained_words':words} for i in range(n)]
def account(records=40,words=5000):
    return {c+'/'+p:{'available':True,'records':records,'words':words,'median_timestamp':Fraction(0)} for c in 'XY' for p in ('early','late')}

def test_nearest_whole_prefix_and_exact_targets():
    assert m.prefix(rows(40),0,'late')['available']
    assert not m.prefix(rows(39),0,'late')['available']
    assert m.prefix(rows(41,124),0,'late')['records']==41

def test_word_ceiling_can_fail_while_count_is_insufficient():
    value=m.prefix(rows(39,150),0,'late')
    assert value['reason']=='whole_prefix_exceeds_5500_words_before_both_targets'
    assert value['stopped_prefix_records']==37

def test_ratio_and_span_equality_then_violation():
    a,b=account(),account(50,5500)
    for c in b.values():c['median_timestamp']=Fraction(30*86400)
    assert m.gates([a,b])['compatible']
    b['X/early']['median_timestamp']+=Fraction(1,2)
    assert m.gates([a,b])['failed_gates']==['early_median_span_above_30_days']
    b['X/early']['records']=51
    assert 'record_ratio_above_5_over_4' in m.gates([a,b])['failed_gates']

def test_unavailable_prefix_separately_blocks_account_and_edge():
    a,b=account(),account();a['X/early']['available']=False
    assert m.gates([a])['failed_gates']==['cell_prefix_unavailable']
    assert m.gates([a,b])['unavailable_cell_count']==1

def test_complete_matching_beats_first_edge_greedy():
    edges={frozenset(e) for e in [('a','b'),('a','c'),('b','d')]}
    assert m.maximum_matching(list('abcd'),edges)==2
