"""M4 matching oracle, interval semantics, guards and immutable sensitivity runs."""
from datetime import datetime, timedelta, timezone
from itertools import product

import pytest
from hypothesis import given, settings, strategies as st

from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.errors import InputError
from account_history_analyzer.features import measure
from account_history_analyzer.io import canonical_bytes, thaw
from account_history_analyzer.sensitivity import (analyze_temporal, compare_boundary_intervals,
                                                 maximum_boundary_matching, _same_window_stability)
from account_history_analyzer.text import preprocess
from account_history_analyzer.windows import build_streams


def brute_matching(left,right,tolerance):
    """Enumerate unrestricted bipartite matchings, including crossing edges."""
    outcomes=[]
    def walk(position,used,pairs):
        if position==len(left):
            ordered=tuple(sorted(pairs))
            outcomes.append((-len(ordered),sum(abs(a-b) for a,b in ordered),ordered))
            return
        walk(position+1,used,pairs)
        for target in right:
            if target not in used and abs(left[position]-target)<=tolerance:
                walk(position+1,used|{target},pairs+[(left[position],target)])
    walk(0,set(),[])
    return [list(pair) for pair in min(outcomes)[2]]


@given(st.lists(st.integers(0,12),max_size=4,unique=True),
       st.lists(st.integers(0,12),max_size=4,unique=True),st.integers(0,5))
@settings(max_examples=120)
def test_WIN_13_matching_against_independent_unrestricted_oracle(left,right,tolerance):
    assert maximum_boundary_matching(left,right,tolerance)==brute_matching(left,right,tolerance)


def test_matching_cardinality_cost_then_lexicographic():
    assert maximum_boundary_matching([1,3],[2,4],1)==[[1,2],[3,4]]
    assert maximum_boundary_matching([1,2],[2],1)==[[2,2]]
    assert maximum_boundary_matching([1,3],[2],1)==[[1,2]]
    # Both perfect assignments have the same L1 cost; the noncrossing one is lex first.
    assert maximum_boundary_matching([0,1],[3,4],4)==[[0,3],[1,4]]
    assert maximum_boundary_matching([],[],1)==[]
    assert maximum_boundary_matching([1],[3],1)==[]


@pytest.mark.parametrize('left,right,tolerance',[([1,1],[2],1),([-1],[1],1),([True],[1],1),([1],[1],-1)])
def test_invalid_matching_inputs_fail(left,right,tolerance):
    with pytest.raises(InputError):
        maximum_boundary_matching(left,right,tolerance)


def change(boundaries,status='ok'):
    return {'stream_id':'stream','status':status,'reason_codes':[],'internal_boundaries':[x[2] for x in boundaries],
            'boundaries':[{'boundary_id':identifier,'record_interval':interval,'window_index':index}
                          for identifier,interval,index in boundaries]}


def test_WIN_12_different_windows_use_record_intervals_not_indices():
    primary=change([('p',[7,8],4)])
    alternate=change([('a',[6,9],2),('b',[20,21],4)])
    comparison=compare_boundary_intervals(primary,alternate)
    row=comparison['comparisons'][0]
    assert row['overlapping_boundary_ids']==['a']
    assert row['nearest_boundary_id']=='a'
    assert row['relation']=='overlap'
    assert comparison['setting_boundaries_without_overlap']==['b']
    separated=compare_boundary_intervals(primary,change([('b',[20,21],4)]))['comparisons'][0]
    assert separated['relation']=='separated' and separated['record_position_gap']==12
    assert separated['nearest_boundary_id']=='b'


def test_interval_endpoint_touch_and_absence_are_explicit():
    primary=change([('p',[7,8],4)])
    touch=compare_boundary_intervals(primary,change([('a',[8,9],4)]))['comparisons'][0]
    assert touch['relation']=='touching' and touch['overlapping_boundary_ids']==[]
    assert touch['touching_boundary_ids']==['a']
    empty=compare_boundary_intervals(primary,change([]))['comparisons'][0]
    assert empty['relation']=='no_setting_boundaries' and empty['record_position_gap'] is None
    assert compare_boundary_intervals(primary,change([],status='insufficient_data'))['status']=='not_comparable'


def test_WIN_13_executed_denominator_skips_insufficient_but_counts_constant():
    primary=change([('p',[7,8],4)])
    settings=[{'setting_id':name,'penalty_lambda':value,'results':[result]}
              for name,value,result in [('primary',1,primary),('near',0.5,change([('a',[8,9],5)])),
                                        ('constant',2,change([],status='no_measurable_variation')),
                                        ('skipped',4,change([],status='insufficient_data'))]]
    result=_same_window_stability([primary],settings,1)[0]
    assert result['executed_setting_count']==3 and result['skipped_setting_count']==1
    assert result['boundaries']==[{'primary_window_index':4,'matched_in_k_of_m_executed_settings':2,
                                   'executed_setting_count':3,'matched_setting_ids':['primary','near']}]


def make_history(count=64,edited=(),constant=False):
    config=AnalysisConfig.from_mapping()
    result=[]
    for index in range(count):
        marker='word'+chr(97+index//26)+chr(97+index%26)
        words=['the','word']*63+['the',marker]
        source=' '.join(words)+','
        if not constant and index>=count//2:
            source=source.upper().replace(',',';')
        record={'id':f'r{index:03d}','kind':'comment','subreddit':'supplied','language':'en',
                'created_utc':(datetime(2025,1,1,tzinfo=timezone.utc)+timedelta(seconds=index)).isoformat().replace('+00:00','Z'),
                'edit_state':'edited' if index in edited else 'unknown','text':source,'status':'present','title':None}
        result.append(measure(preprocess(record,{'text_format':'plain','default_language':'en'},config),config))
    return result


def setup_streams(features,config):
    built=build_streams(features,config)
    windows=[window for stream in built['streams'] for window in stream['windows']]
    streams=[{**{key:value for key,value in stream.items() if key!='windows'},
              'window_ids':[window['window_id'] for window in stream['windows']]} for stream in built['streams']]
    return {'streams':streams},windows


def empty_reuse():
    return {'exact_reductions':[],'near_reductions':[],'near_reduction_status':'not_run_disabled'}


def test_M4_predefined_settings_full_membership_and_primary_immutable():
    config=AnalysisConfig.from_mapping()
    features=make_history()
    primary,windows=setup_streams(features,config)
    original=canonical_bytes({'features':features,'style':primary,'windows':windows,'config':config.analytical()})
    result=analyze_temporal(features,primary,windows,empty_reuse(),config)
    assert canonical_bytes({'features':features,'style':primary,'windows':windows,'config':config.analytical()})==original
    sensitivity=result['sensitivity']
    assert [setting['penalty_lambda'] for setting in sensitivity['penalty_settings']]==[1,0.5,2,4]
    comment_id=next(stream['stream_id'] for stream in primary['streams'] if stream['scope_type']=='pooled' and stream['kind']=='comment')
    candidate=next(change for change in result['changes'] if change['stream_id']==comment_id)
    assert candidate['internal_boundaries']==[4]
    stability=next(item for item in sensitivity['same_window_stability'] if item['stream_id']==comment_id)
    assert stability['executed_setting_count']==4
    assert stability['boundaries'][0]['matched_in_k_of_m_executed_settings']==3
    settings=sensitivity['construction_settings']
    targets=[setting for setting in settings if setting['setting_type']=='window_target']
    assert [setting['target_words'] for setting in targets]==[500,2000]
    assert targets[1]['status']=='insufficient_data'
    assert all(stream['scope_type']=='pooled' for setting in settings for stream in setting['streams'])
    assert sensitivity['within_community']['status']=='executed'
    all_windows={window['window_id'] for window in windows+result['extra_windows']}
    assert all(identifier in all_windows for setting in settings for stream in setting['streams'] for identifier in stream['window_ids'])
    assert len({window['window_id'] for window in result['extra_windows']})==len(result['extra_windows'])
    assert sensitivity['interpretation']=='parameter_stability_not_confidence'


def test_WIN_10_known_edits_removed_unknown_edits_retained():
    config=AnalysisConfig.from_mapping()
    features=make_history(80,edited=(0,))
    primary,windows=setup_streams(features,config)
    result=analyze_temporal(features,primary,windows,empty_reuse(),config)
    edited=next(setting for setting in result['sensitivity']['construction_settings'] if setting['setting_type']=='exclude_known_edited')
    assert edited['excluded_record_ids']==['r000']
    eligible=next(stream['eligible_record_ids'] for stream in edited['streams'] if stream['kind']=='comment')
    assert 'r000' not in eligible and 'r001' in eligible
    assert 'r000' in next(stream['eligible_record_ids'] for stream in primary['streams'] if stream['scope_type']=='pooled' and stream['kind']=='comment')


def test_repeat_deweighting_relationships_and_resource_limit():
    config=AnalysisConfig.from_mapping({'reuse':{'repeat_reduced_near_sensitivity':True}})
    features=make_history()
    primary,windows=setup_streams(features,config)
    reuse={'exact_reductions':[{'excluded_record_id':'r001','representative_record_id':'r000',
                                'reason':'normalized_prose_identical','match_group_id':'supplied_group'}],
           'near_reductions':[],'near_reduction_status':'not_run_resource_limit'}
    result=analyze_temporal(features,primary,windows,reuse,config)
    exact=next(setting for setting in result['sensitivity']['construction_settings'] if setting['setting_type']=='repeat_reduced_exact')
    near=next(setting for setting in result['sensitivity']['construction_settings'] if setting['setting_type']=='repeat_reduced_near')
    assert exact['excluded_record_ids']==['r001']
    assert exact['exclusion_relationships'][0]['representative_record_id']=='r000'
    assert near['status']=='resource_limit' and near['results']==[]
    assert near['reason_codes']==['near_reduction_unavailable_resource_limit']


def test_constant_measurement_settings_execute_without_confidence_claim():
    config=AnalysisConfig.from_mapping()
    features=make_history(constant=True)
    primary,windows=setup_streams(features,config)
    result=analyze_temporal(features,primary,windows,empty_reuse(),config)
    pooled=next(item for item in result['changes'] if item['stream_id']==primary['streams'][0]['stream_id'])
    assert pooled['status']=='no_measurable_variation'
    stability=result['sensitivity']['same_window_stability'][0]
    assert stability['executed_setting_count']==4
    assert stability['boundaries']==[]


def test_disabled_and_short_settings_are_visible():
    config=AnalysisConfig.from_mapping({'sensitivity':{'exclude_known_edited':False,'within_community':False},
                                        'reuse':{'repeat_reduced_exact_sensitivity':False}})
    features=make_history(4)
    primary,windows=setup_streams(features,config)
    result=analyze_temporal(features,primary,windows,empty_reuse(),config)
    assert all(item['executed_setting_count']==0 for item in result['sensitivity']['same_window_stability'])
    assert all(item['skipped_setting_count']==4 for item in result['sensitivity']['same_window_stability'])
    assert result['sensitivity']['within_community']['status']=='not_run'
    for setting in result['sensitivity']['construction_settings']:
        if setting['setting_type']!='window_target':
            assert setting['status']=='not_run' and setting['reason_codes']==['disabled_by_configuration']
