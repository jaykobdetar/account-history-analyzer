"""M3 numerical oracles, independent SciPy checks and representation contracts."""
from collections import Counter
import json
import math
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, strategies as st
from scipy.spatial.distance import cosine as scipy_cosine, jensenshannon

from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.errors import InputError
from account_history_analyzer.features import measure
from account_history_analyzer.registry import feature_registry
from account_history_analyzer.style import (chargrams, classic_delta, compare_features, cosine_distance,
                                           feature_units, feature_values, jensen_shannon, js_contributions)
from account_history_analyzer.text import preprocess

ROOT=Path(__file__).resolve().parents[1]
CONFIG=AnalysisConfig.from_mapping()
ORACLES=json.loads((ROOT/'fixtures/numerical_oracles.json').read_text())
TOY=json.loads((ROOT/'design_examples/delta_reference_toy.json').read_text())


def feature(source, *, language='en', kind='comment', record_id='record', timestamp='2025-01-01T00:00:00Z', community=None):
    record={'id':record_id,'kind':kind,'subreddit':community,'language':language,'created_utc':timestamp,
            'edit_state':'unknown','text':source,'status':'present' if source is not None else 'unavailable','title':None}
    return measure(preprocess(record,{'text_format':'markdown','default_language':'und'},CONFIG),CONFIG)


def find_distance(result, method, *, view=None, n=None):
    return next(item for item in result['distances'] if item['method_id']==method
                and (view is None or item['view']==view) and (n is None or item['n']==n))


def test_NUM_cosine_hand_oracles_and_zero_abstention():
    for case in ORACLES['cosine']:
        assert cosine_distance(case['x'],case['y']) == pytest.approx(case['expected_distance'],abs=1e-15)
    assert cosine_distance([0,0],[1,0]) is None
    assert cosine_distance([],[]) is None
    assert cosine_distance([1e308,1e308],[1e308,0]) == pytest.approx(1-1/math.sqrt(2),abs=1e-15)


def test_NUM_cosine_independent_scipy():
    random=np.random.default_rng(271828)
    for length in (1,2,3,16,129):
        for _ in range(12):
            left=random.uniform(0,10,length)
            right=random.uniform(0,10,length)
            assert cosine_distance(left,right) == pytest.approx(scipy_cosine(left,right),abs=2e-15)
            assert cosine_distance(left,right) == cosine_distance(right,left)


def test_NUM_js_hand_oracles_distance_not_divergence():
    for case in ORACLES['jensen_shannon_base_2_distance']:
        assert jensen_shannon(case['p'],case['q']) == pytest.approx(case['expected_distance'],abs=1e-15)
    contributions=js_contributions([1,0],[0.5,0.5])
    distance=jensen_shannon([1,0],[0.5,0.5])
    assert distance == pytest.approx(math.sqrt(sum(contributions)),abs=1e-15)
    assert distance != pytest.approx(sum(contributions))
    assert all(value>=0 for value in contributions)
    assert jensen_shannon([0,0],[1,0]) is None
    assert js_contributions([],[]) is None


def test_NUM_js_independent_scipy_and_probability_rescaling():
    random=np.random.default_rng(314159)
    for length in (1,2,3,16,129):
        for _ in range(12):
            left=random.uniform(0,10,length)
            right=random.uniform(0,10,length)
            assert jensen_shannon(left,right) == pytest.approx(jensenshannon(left,right,base=2),abs=1e-12)
            assert jensen_shannon(left,right) == jensen_shannon(right,left)
    assert jensen_shannon([1e308,1e308],[1e308,0]) == pytest.approx(jensenshannon([0.5,0.5],[1,0],base=2),abs=1e-15)


@pytest.mark.parametrize('function',[cosine_distance,jensen_shannon])
@pytest.mark.parametrize('left,right',[([1],[1,2]),([math.nan],[1]),([math.inf],[1]),([-1],[1])])
def test_NUM_invalid_vectors_fail_explicitly(function,left,right):
    with pytest.raises(InputError):
        function(left,right)


def test_NUM_delta_hand_arithmetic_zero_sd_units_lengths_and_toy_guard():
    values=ORACLES['delta']
    with pytest.raises(InputError,match='toy_reference_forbidden'):
        classic_delta(values['frequency_a'],values['frequency_b'],TOY)
    result=classic_delta(values['frequency_a'],values['frequency_b'],TOY,allow_toy_reference=True)
    assert result['value']==2
    assert result['reference_kind']=='toy'
    assert [item['contribution'] for item in result['contributions']]==[2,2]
    assert classic_delta([1],[2],None)['reason']=='not_run_missing_reference'
    zero={**TOY,'standard_deviations':[0,20]}
    result=classic_delta([40,140],[60,100],zero,allow_toy_reference=True)
    assert result['value']==2 and result['excluded_coordinates']==['the']
    empty={**TOY,'standard_deviations':[0,1e-12]}
    result=classic_delta([40,140],[60,100],empty,allow_toy_reference=True)
    assert result['value'] is None and result['reason']=='no_valid_reference_coordinates'
    with pytest.raises(InputError,match='incompatible_frequency_unit'):
        classic_delta([40,140],[60,100],TOY,frequency_unit='per_word',allow_toy_reference=True)
    with pytest.raises(InputError):
        classic_delta([40],[60],TOY,allow_toy_reference=True)


def test_NUM_delta_independent_coordinate_calculation():
    reference={**TOY,'reference_kind':'research','vocabulary':['a','the','and'],
               'means':[8,12,20],'standard_deviations':[2,4,5]}
    result=classic_delta([4,4,5],[12,16,30],reference)
    # zA=(-2,-2,-3), zB=(2,1,2), absolute differences=(4,3,5)
    assert result['value']==4
    assert [(x['feature_id'],x['contribution']) for x in result['contributions']]==[
        ('reference_word.and',5),('reference_word.a',4),('reference_word.the',3)]


def test_CHAR_segments_records_code_and_case_boundaries():
    assert chargrams(['abc','def'],3)==Counter({'abc':1,'def':1})
    assert chargrams(['abcd'],3)==Counter({'abc':1,'bcd':1})
    assert chargrams(['aaa','aaa'],3)==Counter({'aaa':2})
    assert chargrams(['a','bc'],3)==Counter()
    record=feature('alpha `excluded` beta\n\ngamma')
    groups=[segment['text'] for segment in record['segments']]
    assert 'abe' not in chargrams(groups,3)
    assert 'tag' not in chargrams(groups,3)
    assert chargrams(['ABC'],3)!=chargrams(['abc'],3)


def test_STYLE_function_other_category_and_contribution_units():
    result=compare_features([feature('the alpha')],[feature('the the')],CONFIG)
    js=find_distance(result,'function_word_js_v1')
    categories={item['feature_id']:item for item in js['contributions']}
    assert categories['function_word.OTHER_WORD']['left_count']==1
    assert categories['function_word.OTHER_WORD']['right_count']==0
    assert categories['function_word.the']['left_rate']==500
    assert categories['function_word.the']['right_rate']==1000
    assert sum(item['left_count'] for item in js['contributions'])==2
    assert js['value']==pytest.approx(jensenshannon([0.5,0.5],[1,0],base=2))
    assert js['value']**2==pytest.approx(math.fsum(item['contribution'] for item in js['contributions']))
    assert result['status']=='insufficient_data'
    assert find_distance(result,'classic_delta_v1')['reason']=='not_run_missing_reference'


def test_STYLE_empty_vectors_never_perfect_similarity():
    result=compare_features([feature('`only code`')],[feature('> only quote')],CONFIG)
    assert all(item['value'] is None for item in result['distances'])
    assert result['status']=='insufficient_data'
    assert all(item['absolute_change'] is None for item in result['surface_changes'])


def test_STYLE_nonenglish_generic_raw_comparison_only():
    result=compare_features([feature('las palabras aquí',language='es')],[feature('las palabras aquí',language='es')],CONFIG)
    assert find_distance(result,'cosine_distance_v1',view='retained_prose',n=3)['value']==0
    assert find_distance(result,'cosine_distance_v1',view='function_mask_v1',n=3)['status']=='not_run'
    assert find_distance(result,'function_word_js_v1')['status']=='not_run'
    assert result['status']=='insufficient_data'


def test_STYLE_qualification_scope_and_context():
    left=[feature('the word, '*64,record_id=f'l{i}',timestamp=None,community='left') for i in range(8)]
    right=[feature('the word; '*64,record_id=f'r{i}',community='right') for i in range(8)]
    result=compare_features(left,right,CONFIG)
    assert result['status']=='ok'
    assert result['samples']['left']['eligible_word_count']==1024
    assert result['samples']['left']['missing_timestamps']==8
    assert result['samples']['left']['community_distribution']==[{'subreddit':'left','record_count':8,'word_count':1024}]
    assert result['samples']['left']['largest_record_share']==0.125
    assert 'unknown_edit_history' in result['limitations']
    short=compare_features(left[:7],right,CONFIG)
    assert short['status']=='insufficient_data'
    mixed=[feature('the word, '*64,kind='submission',record_id=f'm{i}') for i in range(8)]
    assert 'incompatible_kind_scope' in compare_features(left,mixed,CONFIG)['reason_codes']


def test_STYLE_vocabulary_only_matched_length_distortion_invariance():
    left=[feature('The amber lamp and round stone. '*5)]
    right=[feature('The green desk and sweet cloud. '*5)]
    result=compare_features(left,right,CONFIG)
    raw=find_distance(result,'cosine_distance_v1',view='retained_prose',n=4)
    masked=find_distance(result,'cosine_distance_v1',view='function_mask_v1',n=4)
    assert raw['value']>0
    assert masked['value']==0
    assert find_distance(result,'function_word_js_v1')['value']==0
    assert all(item['absolute_change']==0 for item in result['surface_changes'] if item['absolute_change'] is not None)


def test_STYLE_feature_rates_registered_and_pooled():
    record=feature('I, I... words')
    values=feature_values(record)
    registered={entry['feature_id'] for entry in feature_registry()}
    assert set(values)<=registered
    assert set(values)==set(feature_units())
    assert values['punctuation.comma.per_1000_word_tokens']==1000/3
    assert values['punctuation.ascii_period_runs.per_1000_word_tokens']==1000/3


def test_STYLE_toy_reference_explicit_output(tmp_path):
    target=tmp_path/'ref.json'
    target.write_text(json.dumps(TOY))
    config=AnalysisConfig.from_mapping({'delta':{'reference_path':str(target)}},allow_toy_reference=True)
    result=compare_features([feature('the and words')],[feature('the the and')],config)
    delta=find_distance(result,'classic_delta_v1')
    assert delta['status']=='ok'
    assert delta['reference_kind']=='toy'
    assert 'toy_reference' in result['limitations']


@given(st.lists(st.text(alphabet='ab C.!',max_size=12),max_size=6),st.sampled_from([3,4,5]))
def test_property_character_count_mass_and_boundaries(segments,n):
    counts=chargrams(segments,n)
    assert sum(counts.values())==sum(max(len(segment)-n+1,0) for segment in segments)
    assert all(len(key)==n for key in counts)


def test_regression_js_one_sided_subnormal_does_not_divide_by_zero():
    result=jensen_shannon([1,5e-324],[1,0])
    assert math.isfinite(result)
    assert result>=0
    assert js_contributions([1,5e-324],[1,0]) is not None


def test_regression_delta_invariant_to_large_reference_mean():
    reference={**TOY,'reference_kind':'research','vocabulary':['the'],
               'means':[1e20],'standard_deviations':[1]}
    assert classic_delta([1],[2],reference)['value']==1
    reference['means']=[0]
    assert classic_delta([1],[2],reference)['value']==1


def test_regression_mixed_language_comparison_does_not_compare_english_subset_silently():
    left=[feature('the word'),feature('el texto',language='es')]
    right=[feature('the the'),feature('el texto',language='es')]
    result=compare_features(left,right,CONFIG)
    assert find_distance(result,'function_word_js_v1')['status']=='not_run'
    assert all(item['left_value'] is None and item['right_value'] is None
               for item in result['surface_changes'] if item['feature_id'].startswith('function_word.'))


@pytest.mark.parametrize('word',['The','two words','123','don’t'])
def test_regression_public_delta_rejects_noncanonical_reference_vocabulary(word):
    reference={**TOY,'reference_kind':'research','vocabulary':[word],
               'means':[1],'standard_deviations':[1]}
    with pytest.raises(InputError,match='invalid_reference_vocabulary'):
        classic_delta([1],[2],reference)
