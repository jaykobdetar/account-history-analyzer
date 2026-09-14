"""Independent exact-search oracles and graph/threshold properties (RE-05/08)."""
from fractions import Fraction
from itertools import combinations
from pathlib import Path
import tempfile

from hypothesis import given, settings, strategies as st

from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.features import extract_records
from account_history_analyzer.io import canonical_bytes, load_snapshot
from account_history_analyzer.reuse import analyze_reuse, ratio_at_least, shingle_metrics, shingle_set


def run_texts(texts, config=None):
    config = config or AnalysisConfig.from_mapping()
    manifest = {'schema_version':'1.0.0','snapshot_id':'supplied','account_id':'one',
                'source_category':'synthetic','text_format':'plain','default_language':'en',
                'coverage':{'status':'unknown'}}
    with tempfile.TemporaryDirectory() as name:
        path=Path(name)
        (path/'manifest.json').write_bytes(canonical_bytes(manifest))
        records = [{'schema_version':'1.0.0','id':f'r{i:03d}','account_id':'one','kind':'comment',
                    'status':'present','text':text,'created_utc':f'2025-01-01T00:00:{i:02d}Z'}
                   for i,text in enumerate(texts)]
        (path/'records.jsonl').write_bytes(b''.join(canonical_bytes(record) for record in records))
        snapshot=load_snapshot(path/'records.jsonl',path/'manifest.json')
        features=extract_records(snapshot,config)
        return analyze_reuse(snapshot,features,config)


TOKENS = st.sampled_from(['alpha','beta','gamma','delta','epsilon','zeta','eta','theta'])


@given(st.lists(st.lists(TOKENS,min_size=20,max_size=35),min_size=2,max_size=6))
@settings(max_examples=25,deadline=None)
def test_RE_08_index_matches_independent_bruteforce(histories):
    result=run_texts([' '.join(tokens) for tokens in histories])
    # Deliberately simple brute-force oracle: no production shingle constructor
    # or threshold helper is used here. Fraction avoids float decision rounding.
    sets=[{tuple(tokens[i:i+5]) for i in range(len(tokens)-4)} for tokens in histories]
    candidates=0
    expected={}
    for i,j in combinations(range(len(histories)),2):
        intersection=len(sets[i]&sets[j])
        union=len(sets[i]|sets[j])
        candidates += bool(intersection)
        if Fraction(intersection,union) >= Fraction(4,5):
            expected[(f'r{i:03d}',f'r{j:03d}')]=(intersection,union,len(sets[i]),len(sets[j]))
    actual={(pair['left_record_id'],pair['right_record_id']):
            (pair['intersection'],pair['union'],pair['left_shingles'],pair['right_shingles'])
            for pair in result['pairs'] if pair['near_duplicate']}
    assert actual == expected
    assert result['candidate_pair_count'] == candidates
    assert result['budget_complete'] is True


def test_RE_05_connected_similarity_not_pairwise_equivalence():
    original=['word'+chr(97+i//26)+chr(97+i%26) for i in range(50)]
    middle=['replacement'+chr(97+i) for i in range(5)]+original[5:]
    last=middle[:-5]+['trailer'+chr(97+i) for i in range(5)]
    result=run_texts([' '.join(tokens) for tokens in [original,middle,last]])
    edges={(pair['left_record_id'],pair['right_record_id']) for pair in result['pairs'] if pair['near_duplicate']}
    assert edges == {('r000','r001'),('r001','r002')}
    assert len(result['connected_groups']) == 1
    group=result['connected_groups'][0]
    assert set(group['record_ids']) == {'r000','r001','r002'}
    assert group['relationship'] == 'connected_edges_not_pairwise_equivalence'
    assert len(group['pair_ids']) == 2


@given(st.lists(st.lists(TOKENS,max_size=12),max_size=5))
def test_RE_07_shingles_never_cross_segment_boundaries(segments):
    expected=set()
    for segment in segments:
        expected.update(zip(segment,segment[1:],segment[2:],segment[3:],segment[4:]))
    assert shingle_set(segments) == frozenset(expected)


def test_shingles_are_sets_and_empty_sets_abstain():
    sequence=['word']*50
    assert shingle_set([sequence]) == frozenset({('word',)*5})
    result=shingle_metrics(frozenset(),shingle_set([sequence]))
    assert result['status'] == 'not_computable'
    assert result['jaccard'] is None
    assert result['left_in_right'] is None
    assert result['right_in_left'] is None


@given(st.integers(min_value=0,max_value=10**20),st.integers(min_value=1,max_value=10**20),
       st.integers(min_value=0,max_value=100))
def test_RE_threshold_crossproducts_agree_exact_fraction(numerator,denominator,threshold):
    # numerator <= denominator keeps fractions in the valid overlap domain.
    numerator %= denominator+1
    assert ratio_at_least(numerator,denominator,threshold,100) == (Fraction(numerator,denominator) >= Fraction(threshold,100))


def test_threshold_rounding_does_not_cross_decision():
    assert ratio_at_least(4,5,80,100)
    assert not ratio_at_least(799,1000,80,100)
    assert round(799/1000,2) == 0.80
