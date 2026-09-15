"""Independent synthetic oracles; no real records or scores are read."""
from copy import deepcopy
from fractions import Fraction
import hashlib
import importlib.util
from pathlib import Path

import pytest

spec=importlib.util.spec_from_file_location('independent_shared_anchor',Path(__file__).resolve().parents[1]/'scripts/check_shared_anchor.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
D=86400

def records(words,base=0,prefix='r'):
    return [{'timestamp':base+i,'record_id':f'{prefix}-{i:03d}','retained_words':w} for i,w in enumerate(words)]

def sample(words=None,base=0,prefix='r'):
    rows=records(words or [125]*40,base,prefix)
    return {'rows':rows,'records':len(rows),'retained_words':sum(r['retained_words'] for r in rows),
            'median_timestamp':Fraction(rows[(len(rows)-1)//2]['timestamp']+rows[len(rows)//2]['timestamp'],2)}

def samples(anchor_words=None):
    return {k:sample(anchor_words if k=='anchor' else None,-D if k=='anchor' else D,k) for k in m.SAMPLES}

@pytest.mark.parametrize('period,offset,accepted',[
 ('early',-180*D-1,False),('early',-180*D,True),('early',-1,True),('early',0,False),
 ('late',-1,False),('late',0,True),('late',180*D-1,True),('late',180*D,False)])
def test_inclusive_outer_and_exclusive_cut_band_endpoints(period,offset,accepted):
    rows=records([125]*40)
    for r in rows:r['timestamp']=offset
    assert (m.select_prefix(rows,0,period) is not None)==accepted

def test_prefix_targets_word_filter_and_no_skipping_after_overshoot():
    selected=m.select_prefix(records([19,501]+[124]*40+[40,500]),0,'late')
    assert selected['records']==41 and selected['retained_words']==5000
    assert m.select_prefix(records([150]*40),0,'late') is None
    assert m.select_prefix(records([25]*200),0,'late')['records']==200
    assert m.select_prefix(records([20]*201+[500]*20),0,'late') is None

def test_prefix_nearest_order_keeps_whole_original_id_and_exact_median():
    value=m.select_prefix(list(reversed(records([125]*45,base=-45))),0,'early')
    assert value['rows'][0]['record_id']=='r-005' and value['rows'][-1]['record_id']=='r-044'
    assert value['median_timestamp']==Fraction(-41,2)

def test_exact_cost_six_late_date_pairs_and_ten_five_sample_volume_pairs():
    values=samples()
    for i,key in enumerate(m.LATE):values[key]['median_timestamp']=Fraction(i*D)
    for i,key in enumerate(m.SAMPLES):values[key]['retained_words']=5000+i*100;values[key]['records']=40+i
    result=m.evaluate_samples(values)
    # Distances for four evenly spaced late medians sum to10 days; five
    # evenly spaced words/counts yield sum of index distances20, not10.
    expected=Fraction(10,180)+Fraction(2000,5000)+Fraction(20,40)
    assert result['exact_cost']==expected
    values['anchor']['median_timestamp']-=170*D
    assert m.evaluate_samples(values)['exact_cost']==expected
    assert m.evaluate_samples(values)['valid']

def test_five_sample_ratio_and_late_span_equality():
    values=samples();values['anchor']['records']=50;values['anchor']['retained_words']=5500
    values['late_BY']['median_timestamp']+=30*D
    assert m.evaluate_samples(values)['valid']
    values['late_BY']['median_timestamp']+=Fraction(1,2)
    assert m.evaluate_samples(values)['failed_gates']==['four_late_median_span_above_30_days']
    values['anchor']['records']=51
    assert 'five_sample_record_ratio_above_5_over_4' in m.evaluate_samples(values)['failed_gates']

def test_independent_whole_record_window_guard_can_fail_despite_all_volume_gates():
    pattern=([20]*10+[500]*2)*3+[350]*4
    assert len(pattern)==40 and sum(pattern)==5000
    values=samples(pattern);values['late_AX']=sample(pattern,D,'late_AX')
    result=m.evaluate_samples(values)
    assert result['word_ratio']==1 and result['record_ratio']==1
    assert result['histories']['late_AX']['qualified_windows']==7
    assert result['histories']['late_AX']['remainder_records']==4
    assert all(result['histories'][k]['qualified_windows']==8 for k in m.LATE if k!='late_AX')
    assert result['failed_gates']==['one_or_more_histories_below_eight_primary_windows']

def test_grid_attainability_is_not_a_selection_input():
    text=Path(m.__file__).read_text()
    assert 'legal_grid' not in text and 'candidate_intervals' not in text and 'attainable' not in text
    assert m.evaluate_samples(samples())['valid']

def synthetic_universe():
    strata=[];data={}
    for sid,n in [('stratum-02',2),('stratum-04',3),('stratum-05',2)]:
        names=[sid+'-account-'+str(i) for i in range(n)];comms=[sid+'-x',sid+'-y']
        strata.append({'stratum_id':sid,'accounts':names,'communities':comms,'cut':'1970-01-01T00:00:00Z'})
        for name in names:
            for comm in comms:
                for period,base in [('early',-D),('late',D)]:
                    data[sid,name,comm,period]=records([125]*40,base,f'{name}-{comm}-{period}')
    return strata,data

def test_twenty_directional_trials_and_exact_registered_tie():
    strata,data=synthetic_universe();trials,winner=m.enumerate_trials(strata,data)
    assert len(trials)==20 and all(t['evaluation']['valid'] for t in trials)
    assert winner['stratum_id']=='stratum-02'
    ordered=sorted(strata[0]['accounts'],key=lambda a:hashlib.sha256(b'pilot5-anchor-order-v1\0'+a.encode()).hexdigest())
    assert [winner['A'],winner['B']]==ordered
    assert [winner['X'],winner['Y']]==sorted(strata[0]['communities'])

def test_unused_reciprocal_early_cells_cannot_invalidate_shared_anchor_trial():
    strata,data=synthetic_universe();spec=strata[0];a,b=spec['accounts'];x,y=spec['communities']
    data[spec['stratum_id'],b,x,'early']=[]
    data[spec['stratum_id'],b,y,'early']=[]
    data[spec['stratum_id'],a,y,'early']=[]
    trials,_=m.enumerate_trials(strata,data)
    chosen=next(t for t in trials if (t['stratum_id'],t['A'],t['B'],t['X'])==(spec['stratum_id'],a,b,x))
    assert chosen['evaluation']['valid']
    assert len([t for t in trials if t['stratum_id']==spec['stratum_id'] and t['evaluation']['valid']])==1

def test_no_valid_quintet_yields_no_selection():
    strata,data=synthetic_universe()
    trials,winner=m.enumerate_trials(strata,{})
    assert len(trials)==20 and winner is None and all(not t['evaluation']['valid'] for t in trials)

def test_float_precision_cannot_reverse_cost_rank_and_account_keys_are_canonical():
    values=samples();t={'evaluation':m.evaluate_samples(values),'stratum_id':'s','A':'a','B':'b','X':'x','Y':'y'}
    larger=deepcopy(t);larger['evaluation']['exact_cost']+=Fraction(1,2**4096)
    assert m.trial_key(t)<m.trial_key(larger)
    with pytest.raises(ValueError):m.account_hash('Noncanonical')
