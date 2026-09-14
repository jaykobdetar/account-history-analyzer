"""Synthetic arithmetic/selection fixtures only; never read real style results."""
from collections import Counter
from copy import deepcopy
import math
from pathlib import Path
import random
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import check_raw_distances as check
from account_history_analyzer.config import AnalysisConfig, resource_bytes
from account_history_analyzer.features import measure
from account_history_analyzer.style import compare_features, cosine_distance, jensen_shannon
from account_history_analyzer.text import preprocess


def records(text, n=8, *, language=None, kind='comment'):
    return [{'id':f'synthetic-{i}','kind':kind,'status':'present','text':text,
             'language':language,'subreddit':'synthetic-community',
             'created_utc':'2017-01-01T00:00:00Z','edit_state':'unknown'} for i in range(n)]


MANIFEST={'text_format':'markdown','default_language':'en'}
CONFIG=AnalysisConfig.from_toml()
VOCAB=resource_bytes('function_words_en_v1.txt').decode().splitlines()


def production_results(left,right,method):
    def measured(rows):
        result=[]
        for r in rows:
            derived=preprocess(r,MANIFEST,CONFIG)
            result.append({**derived,**measure(derived,CONFIG)})
        return result
    result=compare_features(measured(left),measured(right),CONFIG)
    distance=next(r for r in result['distances'] if tuple(r[k] for k in ('method_id','view','n'))==method)
    reasons=set(result['reason_codes'])
    if distance['reason']:
        reasons.add(distance['reason'])
    ok=result['status']=='ok' and distance['status']=='ok'
    return {'raw_distance':distance['value'],'score':distance['value'] if ok else None,
            'status':'ok' if ok else 'abstained','reason_codes':sorted(reasons),'distance_status':distance['status']}


def test_character_counts_respect_case_codepoints_and_segment_boundaries():
    assert check.character_counts(['abcd','efgh'])==Counter({'abcd':1,'efgh':1})
    assert check.character_counts(['AbCdabcd'])['AbCd']==1
    assert check.character_counts(['éééé','😀😀😀😀'])==Counter({'éééé':1,'😀😀😀😀':1})
    assert not check.character_counts(['abc'])


def test_cosine_known_cases_empty_and_proportional():
    assert check.cosine(Counter(),Counter(a=1)) is None
    assert check.cosine(Counter(a=1),Counter(b=1))==1
    assert check.cosine(Counter(a=2,b=4),Counter(a=1,b=2))==pytest.approx(0,abs=1e-12)
    assert check.cosine(Counter(a=1,b=1),Counter(a=1))==pytest.approx(1-1/math.sqrt(2))


def test_js_known_cases_other_category_and_no_pseudocount():
    assert check.js_distance(Counter(),Counter(the=1),['the']) is None
    assert check.js_distance(Counter(the=10),Counter(apple=10),['the'])==1
    assert check.js_distance(Counter(apple=10),Counter(orange=10),['the'])==0
    assert check.js_distance(Counter(the=2,apple=4),Counter(the=1,apple=2),['the'])==pytest.approx(0)


def test_independent_count_arithmetic_matches_frozen_scalars_random_synthetic_vectors():
    rng=random.Random(8148)
    for _ in range(100):
        x=[rng.randrange(10000) for _ in range(8)]; y=[rng.randrange(10000) for _ in range(8)]
        a,b=Counter(dict(enumerate(x))),Counter(dict(enumerate(y)))
        assert check.cosine(a,b)==pytest.approx(cosine_distance(x,y),abs=1e-12,rel=1e-12)
        assert check.js_distance(a,b,list(range(8)))==pytest.approx(jensen_shannon(x,y),abs=1e-12,rel=1e-12)


@pytest.mark.parametrize('method',check.METHODS)
@pytest.mark.parametrize('scenario',['full','below_records','below_words','empty','language','kind','markdown'])
def test_preprocessor_counting_raw_values_and_null_qualification_match_synthetic_contract(method,scenario):
    left=records('the and if we can write these words carefully. '*20)
    right=records('an or but they would read those examples slowly. '*20)
    if scenario=='below_records':
        right=right[:4]
    elif scenario=='below_words':
        left=records('the and if we can write these words carefully. '*3)
    elif scenario=='empty':
        right=[]
    elif scenario=='language':
        right=records('la le du et ce que nous pouvons lire ici. '*20,language='fr')
    elif scenario=='kind':
        right=records('the and if we can write these words carefully. '*20,kind='submission')
    elif scenario=='markdown':
        left=records('> quoted words are excluded\n\n'+('We **can** write `code excluded` and [visible text](https://example.com). '*20))
    a=check.representations(left,MANIFEST,CONFIG); b=check.representations(right,MANIFEST,CONFIG)
    expected=check.independent_result(a,b,method,VOCAB)
    actual=production_results(left,right,method)
    assert check.compare_result(expected,actual)<=1e-12
    if scenario in ('below_records','below_words'):
        assert expected['raw_distance'] is not None and expected['score'] is None


def synthetic_design():
    index,datasets=[],{}
    for sid in range(3):
        for block in range(10):
            bid=f'stratum-{sid}-block-{block:02d}'
            for method in check.METHODS:
                for arm in check.ARMS:
                    batch_id=f'{bid}-{arm}-{method[1]}'
                    item={'stratum_id':f'stratum-{sid}','block_id':bid,'batch_id':batch_id,'arm':arm,
                          **dict(zip(('method_id','view','n'),method))}
                    index.append(item)
                    datasets[batch_id]={'protocol':{'distance':dict(zip(('method_id','view','n'),method))},
                                       'pairs':[{'pair_id':f'{bid}/synthetic-pair-{p:02d}','split':'evaluation',
                                                 'left_text_id':'A/X/early','right_text_id':'B/Y/late'} for p in range(16)]}
    return index,datasets


def test_fixed_sample_72_ignores_input_order_and_qualification_without_quiet_drops():
    index,datasets=synthetic_design()
    selected=check.select_cases(index,datasets)
    assert len(selected)==72
    expected={(s,m,a):[] for s in range(3) for m in check.METHODS for a in check.ARMS}
    for row in selected:
        key=int(row['batch']['stratum_id'].split('-')[-1]),tuple(row['batch'][k] for k in ('method_id','view','n')),row['batch']['arm']
        expected[key].append(row['pair']['pair_id'])
    assert all(len(rows)==2 for rows in expected.values())
    for sid in range(3):
        assert len({tuple(v) for k,v in expected.items() if k[0]==sid})==1
    changed=deepcopy(datasets)
    for dataset in changed.values():
        dataset['pairs'].reverse()
        for pair in dataset['pairs']:
            pair.update(status='abstained',score=None,raw_distance=0.999)
    actual=check.select_cases(list(reversed(index)),changed)
    assert [r['pair']['pair_id'] for r in actual]==[r['pair']['pair_id'] for r in selected]
    with pytest.raises(check.CheckFailure,match='complete_fixed_batch_index_required'):
        check.select_cases(index[:-1],datasets)


def test_numeric_check_rejects_promoting_unqualified_raw_distance_to_score():
    expected={'raw_distance':0.25,'score':None,'status':'abstained',
              'distance_status':'ok','reason_codes':['insufficient_comparable_text']}
    actual={**expected,'score':0.25}
    with pytest.raises(check.CheckFailure,match='unavailable_distance_or_score_changed'):
        check.compare_result(expected,actual)
    actual={**expected,'raw_distance':0.26}
    with pytest.raises(check.CheckFailure,match='raw_arithmetic_mismatch'):
        check.compare_result(expected,actual)


def test_arithmetic_checker_imports_no_scoring_or_preparation_aggregation():
    source=Path(check.__file__).read_text()
    for forbidden in ('from account_history_analyzer.style','from account_history_analyzer.features',
                      'import prepare_units','import study_math','from account_history_analyzer.evaluation'):
        assert forbidden not in source
