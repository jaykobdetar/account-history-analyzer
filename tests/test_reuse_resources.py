"""AUD-003 exact matching, deterministic resource accounting and abstention."""
from __future__ import annotations

from itertools import product
from random import Random

import pytest

from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import canonical_bytes
from account_history_analyzer.reuse import analyze_reuse, _candidates, _matching_passages
from account_history_analyzer.reuse_matching import ReuseLimit, TokenMatch, TokenMatcher, WorkMeter
from test_reuse import run_texts, WORDS


def brute_match(left, right, minimum):
    """Enumerate every legal start pair; no suffix/index/DP shared with production."""
    best = None
    for li, a in enumerate(left):
        for ri, b in enumerate(right):
            for start_a in range(len(a)):
                for start_b in range(len(b)):
                    size = 0
                    while start_a+size<len(a) and start_b+size<len(b) and a[start_a+size]==b[start_b+size]:
                        size += 1
                    key = (-size,li,ri,start_a,start_b)
                    if size>=minimum and (best is None or key<best):
                        best = key
    return None if best is None else TokenMatch(-best[0],*best[1:])


def test_exhaustive_binary_short_sequences_and_all_ties():
    sequences = [list(p) for n in range(5) for p in product(('a','b'),repeat=n)]
    # Every binary segment through length four, including empty and equal cases.
    for left,right in product(sequences,repeat=2):
        for minimum in (1,2,3,5):
            assert TokenMatcher([left],minimum).find([right]) == brute_match([left],[right],minimum)


def test_exhaustive_binary_multiple_segment_boundaries():
    segments = [[],['a'],['b'],['a','a'],['a','b'],['b','a'],['b','b']]
    records = [list(p) for p in product(segments,repeat=2)]
    for left,right in product(records,repeat=2):
        for minimum in (1,2,3):
            assert TokenMatcher(left,minimum).find(right) == brute_match(left,right,minimum)


def test_random_longer_multisegment_against_independent_oracle_and_reused_index():
    rng = Random(1941)
    for _ in range(1000):
        left = [[rng.choice('abcde') for _ in range(rng.randrange(16))] for _ in range(rng.randrange(1,5))]
        matcher = TokenMatcher(left,rng.randrange(1,6))
        for _ in range(3):
            right = [[rng.choice('abcde') for _ in range(rng.randrange(16))] for _ in range(rng.randrange(1,5))]
            assert matcher.find(right) == brute_match(left,right,matcher.minimum)


def test_multisegment_source_offsets_and_tie_order(tmp_path):
    left = 'prefix omega alpha, beta gamma delta epsilon end\n\nalpha beta gamma delta epsilon'
    right = 'alpha BETA; gamma delta epsilon different\n\nalpha beta gamma delta epsilon'
    result,_,features,_ = run_texts(tmp_path,[left,right],overrides={'reuse':{'minimum_near_duplicate_words':1,'near_threshold_numerator':0}})
    passage = result['pairs'][0]['matching_passages'][0]
    assert passage['token_count']==5
    assert passage['left']['segment_index']==passage['right']['segment_index']==0
    assert passage['left']['text']=='alpha, beta gamma delta epsilon'
    assert passage['right']['text']=='alpha BETA; gamma delta epsilon'
    assert _matching_passages(features[0],features[1],5)==[passage]


@pytest.mark.parametrize('name',['max_index_postings','max_work_units','max_evidence_tokens','max_evidence_codepoints'])
def test_each_zero_budget_abstains_without_partial_near_or_lost_exact(tmp_path,name):
    text=' '.join(WORDS[:30])
    result,*_=run_texts(tmp_path,[text]*3,overrides={'reuse':{name:0,'repeat_reduced_near_sensitivity':True}})
    assert result['resource_limit_reason']==name
    assert result['near_status']=='resource_limit' and not result['budget_complete']
    assert result['pairs']==result['connected_groups']==result['near_reductions']==[]
    assert len(result['exact_groups'])==3 and len(result['exact_reductions'])==2
    assert result['repeat_reduced_retained_ids']==['r000']
    assert result['near_reduction_status']=='not_run_resource_limit'
    assert result['candidate_count_is_lower_bound']==(name in {'max_index_postings','max_work_units'})
    for key,value in result['resource_limits'].items():
        assert result['resource_usage'][key.removeprefix('max_')]<=value


def test_evidence_counts_are_reserved_source_and_token_codepoints(tmp_path):
    result,snapshot,features,config=run_texts(tmp_path,[' '.join(WORDS[:30])]*3)
    usage=result['resource_usage']
    assert usage['evidence_tokens']==90
    assert usage['evidence_codepoints']==sum(len(side['text']) for pair in result['pairs'] for passage in pair['matching_passages'] for side in (passage['left'],passage['right']))+sum(len(token) for pair in result['pairs'] for passage in pair['matching_passages'] for token in passage['tokens'])
    for field in ('max_work_units','max_index_postings','max_evidence_tokens','max_evidence_codepoints'):
        needed=usage[field.removeprefix('max_')]
        exact=AnalysisConfig.from_mapping({'reuse':{field:needed}})
        enough=analyze_reuse(snapshot,features,exact)
        assert enough['budget_complete']
        short=AnalysisConfig.from_mapping({'reuse':{field:needed-1}})
        limited=analyze_reuse(snapshot,features,short)
        assert not limited['budget_complete'] and limited['resource_limit_reason']==field
        assert limited['pairs']==limited['connected_groups']==[]
        assert limited['exact_groups']==result['exact_groups']
        assert limited['exact_reductions']==result['exact_reductions']
        if field!='max_index_postings':
            assert not limited['candidate_count_is_lower_bound']


def test_posting_encounters_charge_repeated_candidate_pairs():
    # Only one distinct pair, encountered once for every shared shingle. The old
    # distinct-pair guard cannot bound this phase; reserve every encounter.
    cfg=AnalysisConfig.from_mapping()['reuse']
    shingles=frozenset((str(i),) for i in range(200))
    meter=WorkMeter({**cfg,'max_work_units':10**8})
    pairs=set()
    _candidates([{},{}],[shingles,shingles],{**cfg,'shingle_tokens':1},meter,pairs)
    assert pairs=={(0,1)}
    needed=meter.usage['work_units']
    bounded=WorkMeter({**cfg,'max_work_units':needed-1})
    partial=set()
    with pytest.raises(ReuseLimit,match='max_work_units'):
        _candidates([{},{}],[shingles,shingles],{**cfg,'shingle_tokens':1},bounded,partial)
    assert partial==pairs
    assert bounded.usage['work_units']==needed-1


@pytest.mark.parametrize('pattern',['identical','edited','periodic_edited','shifted','high_entropy'])
def test_general_matcher_has_linear_work_reservations(pattern):
    amounts=[]
    for size in (500,1000,2000,4000):
        left=['a']*size if pattern in {'identical','edited'} else ['a','b','c','d']*(size//4)
        if pattern=='high_entropy':
            left=[str(i) for i in range(size)]
        right=list(left)
        if pattern in {'edited','periodic_edited','high_entropy'}:
            right[size//2]='other'
        if pattern=='shifted':
            right=['other']+right[:-1]
        meter=WorkMeter(AnalysisConfig.from_mapping()['reuse'])
        match=TokenMatcher([left],5,meter).find([right])
        assert match is not None
        expected=size if pattern=='identical' else size//2 if pattern in {'edited','periodic_edited','high_entropy'} else size-1
        assert match.size==expected
        amounts.append(meter.usage['work_units'])
    assert all(larger<=2*smaller+100 for smaller,larger in zip(amounts,amounts[1:]))


def test_long_nonidentical_repeated_pair_remains_exact_and_input_immutable(tmp_path):
    left=['alpha']*8000
    right=left.copy();right[4000]='different'
    result,snapshot,features,config=run_texts(tmp_path,[' '.join(left),' '.join(right)])
    before=canonical_bytes(features)
    assert result['budget_complete'] and result['candidate_pair_count']==1
    assert result['pairs'][0]['matching_passages'][0]['token_count']==4000
    assert result['resource_usage']['work_units']<300000
    assert canonical_bytes(analyze_reuse(snapshot,features,config))==canonical_bytes(result)
    assert canonical_bytes(features)==before


def test_size_guards_do_not_change_observed_nonempty_shingle_counts(tmp_path):
    result,*_=run_texts(tmp_path,['alpha beta gamma delta epsilon']*2)
    assert result['nonempty_shingle_records']==2
    assert result['resource_usage']['index_postings']==0
    assert result['candidate_pair_count']==0 and result['budget_complete']


def test_resource_counters_ignore_identifiers_and_process_hash_seed(tmp_path):
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys
    script = """
import json
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.features import extract_records
from account_history_analyzer.io import canonical_bytes,load_snapshot
from account_history_analyzer.reuse import analyze_reuse
import sys
config=AnalysisConfig.from_mapping({'reuse':{'max_evidence_tokens':35}})
snapshot=load_snapshot(sys.argv[1],sys.argv[2],config)
result=analyze_reuse(snapshot,extract_records(snapshot,config),config)
print(canonical_bytes({k:result[k] for k in ('resource_usage','resource_limits','resource_limit_reason','candidate_pair_count','candidate_count_is_lower_bound','budget_complete')}).decode(),end='')
"""
    text=' '.join(WORDS[:30])
    run_texts(tmp_path,[text,text.upper(),text+' later'])
    records=tmp_path/'records.jsonl';manifest=tmp_path/'snapshot.json'
    first=subprocess.run([sys.executable,'-c',script,str(records),str(manifest)],check=True,capture_output=True,env=dict(os.environ,PYTHONHASHSEED='1'))
    # Rename IDs consistently and reverse records, retaining their timestamp order.
    rows=[json.loads(line) for line in records.read_text().splitlines()]
    for index,row in enumerate(rows):
        row['id']='ordinary-'+str(90-index)
    records.write_bytes(b''.join(canonical_bytes(row) for row in reversed(rows)))
    second=subprocess.run([sys.executable,'-c',script,str(records),str(manifest)],check=True,capture_output=True,env=dict(os.environ,PYTHONHASHSEED='3456',TZ='Asia/Tokyo'),cwd=tmp_path)
    assert first.stdout==second.stdout
    assert json.loads(first.stdout)['resource_limit_reason']=='max_evidence_tokens'


@pytest.mark.parametrize('field',['max_index_postings','max_work_units','max_evidence_tokens','max_evidence_codepoints'])
def test_resource_abstention_pipeline_exit4_and_schema(tmp_path,field):
    from account_history_analyzer.pipeline import analyze
    from account_history_analyzer.io import thaw
    from account_history_analyzer.schemas import validate
    _,snapshot,_,_=run_texts(tmp_path,[' '.join(WORDS[:30])]*2)
    config=AnalysisConfig.from_mapping({'reuse':{field:0}})
    analysis=analyze(snapshot,config)
    results=thaw(analysis.results)
    validate(results,'results')
    assert analysis.exit_code==4
    module=results['modules']['reuse']
    assert field in module['reason_codes']
    assert module['payload']['pairs']==[]


def test_edited_low_entropy_near_duplicate_keeps_exact_threshold_and_passage(tmp_path):
    vocabulary=WORDS[:31]
    left=[vocabulary[i%31] for i in range(4000)]
    right=left.copy();right[2000]='different'
    result,_,_,_=run_texts(tmp_path,[' '.join(left),' '.join(right)])
    pair=result['pairs'][0]
    assert result['budget_complete'] and pair['near_duplicate']
    assert pair['intersection']==31 and pair['union']==36
    assert pair['jaccard']==31/36
    passage=pair['matching_passages'][0]
    assert passage['token_count']==2000
    assert passage['left']['normalized_start']==passage['right']['normalized_start']==0
    assert passage['tokens']==left[:2000]


def test_work_exhaustion_inside_general_passage_match_discards_near(tmp_path):
    left=['alpha']*2000
    right=left.copy();right[1000]='different'
    result,_,_,_=run_texts(tmp_path,[' '.join(left),' '.join(right)],overrides={'reuse':{'max_work_units':30000}})
    assert result['candidate_pair_count']==1 and not result['candidate_count_is_lower_bound']
    assert result['resource_limit_reason']=='max_work_units'
    assert result['resource_usage']['evidence_tokens']==0
    assert result['pairs']==result['connected_groups']==[]
