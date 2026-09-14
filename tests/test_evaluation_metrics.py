"""Evaluator-only arithmetic: tied rankings, abstentions, exact interval matching."""
from itertools import permutations
import math

import pytest
from hypothesis import given, strategies as st
from scipy.stats import rankdata

from account_history_analyzer.errors import InputError
from account_history_analyzer.evaluation_metrics import aggregate_stream_metrics, boundary_metrics, paired_metrics


def test_hand_checked_rankings_and_frozen_confusion():
    labels = ['different_author','same_author','different_author','same_author']
    result = paired_metrics(labels, [.9,.8,.8,.1], threshold=.8)
    # Positive .9 wins twice; positive .8 wins once and ties once: 3.5/4.
    assert result['ranking']['roc_auc']['value'] == .875
    # Whole .8 tie group enters at once: .5*1 + .5*(2/3).
    assert result['ranking']['average_precision']['value'] == pytest.approx(5/6)
    assert result['decisions']['confusion'] == {
        'true_positive':2, 'false_positive':1, 'true_negative':1, 'false_negative':0,
    }
    assert result['decisions']['false_positive_rate']['denominator'] == 2
    assert result['decisions']['false_positive_rate']['value'] == .5
    assert result['decisions']['precision']['value'] == 2/3
    assert result['decisions']['recall']['value'] == 1


def test_equal_scores_enter_as_one_threshold_group_regardless_input_order():
    rows = [('different_author',1), ('same_author',1), ('same_author',1)]
    for ordered in permutations(rows):
        result = paired_metrics([row[0] for row in ordered], [row[1] for row in ordered])
        assert result['ranking']['roc_auc']['value'] == .5
        assert result['ranking']['average_precision']['value'] == 1/3
        assert result['decisions']['status'] == 'not_run_missing_threshold'
        assert result['decisions']['confusion'] is None


def test_ranking_does_not_narrow_finite_integer_scores_to_float():
    result = paired_metrics(['same_author','different_author'],[10**499,10**500],threshold=10**500)
    assert result['ranking']['roc_auc']['value'] == 1
    assert result['decisions']['confusion']['true_positive'] == 1


def test_abstentions_and_undefined_denominators_do_not_become_zero_scores():
    result = paired_metrics(['same_author','different_author'], [None,None], threshold=.4)
    assert result['total_pair_count'] == 2 and result['scored_pair_count'] == 0
    assert result['sample_coverage']['value'] == 0
    assert result['abstention_rate']['value'] == 1
    assert result['ranking']['roc_auc']['value'] is None
    assert result['ranking']['average_precision']['value'] is None
    for name in ('false_positive_rate','precision','recall'):
        assert result['decisions'][name]['value'] is None
        assert result['decisions'][name]['denominator'] == 0
        assert result['decisions'][name]['reason_codes']
    empty = paired_metrics([], [])
    assert empty['sample_coverage']['value'] is None
    assert empty['abstention_rate']['value'] is None
    one_class = paired_metrics(['different_author'], [.3], threshold=.5)
    assert one_class['ranking']['roc_auc']['value'] is None
    assert one_class['ranking']['average_precision']['value'] == 1
    assert one_class['decisions']['recall']['value'] == 0
    assert one_class['decisions']['precision']['value'] is None


@given(st.lists(st.tuples(st.booleans(), st.integers(-8,8)), min_size=1, max_size=50))
def test_roc_auc_agrees_with_independent_scipy_mann_whitney_ranks(rows):
    labels = ['different_author' if positive else 'same_author' for positive,_ in rows]
    scores = [score for _,score in rows]
    positives = sum(positive for positive,_ in rows)
    negatives = len(rows)-positives
    result = paired_metrics(labels,scores)['ranking']['roc_auc']
    if not positives or not negatives:
        assert result['value'] is None
    else:
        ranks = rankdata(scores,method='average')
        rank_sum = math.fsum(float(rank) for rank,(positive,_) in zip(ranks,rows,strict=True) if positive)
        expected = (rank_sum-positives*(positives+1)/2)/(positives*negatives)
        assert result['value'] == expected


@pytest.mark.parametrize('labels,scores,threshold', [
    (['invented'],[.5],None), (['same_author'],[],None),
    (['same_author'],[float('nan')],None), (['same_author'],[float('inf')],None),
    (['same_author'],[True],None), (['same_author'],[.5],float('nan')),
    (['same_author'],[.5],False),
])
def test_invalid_evaluation_pairs_rejected(labels,scores,threshold):
    with pytest.raises(InputError):
        paired_metrics(labels,scores,threshold=threshold)


def test_boundary_intervals_use_original_split_positions_and_inclusive_tolerance():
    result = boundary_metrics([[8,10],[20,20],[31,32]], [9,22], tolerance=2)
    assert [(row['candidate_interval'],row['truth_position'],row['location_error_records']) for row in result['matches']] == [
        ([8,10],9,0),([20,20],22,2),
    ]
    assert result['precision']['value'] == 2/3
    assert result['recall']['value'] == 1
    assert result['mean_location_error_records']['value'] == 1
    assert result['unmatched_candidate_indices'] == [2]
    assert result['maximum_location_error_records'] == 2


def _brute_interval_matching(candidates, truth, tolerance):
    """Unrestricted tiny bipartite enumeration, independent of production DP."""
    outputs = []
    def visit(index, used, pairs, cost):
        if index == len(candidates):
            outputs.append((len(pairs),cost,sorted(pairs)))
            return
        visit(index+1,used,pairs,cost)
        interval = candidates[index]
        for j, point in enumerate(truth):
            error = max(interval[0]-point,point-interval[1],0)
            if j not in used and error<=tolerance:
                visit(index+1,used|{j},pairs+[(tuple(interval),point)],cost+error)
    visit(0,set(),[],0)
    return min(outputs,key=lambda item:(-item[0],item[1],item[2]))


@given(st.lists(st.integers(1,8),unique=True,max_size=4),
       st.lists(st.integers(1,28),unique=True,max_size=4),st.integers(0,6))
def test_boundary_matching_matches_unrestricted_exhaustive_oracle(starts,truth,tolerance):
    candidates = [[3*start,3*start+1] for start in starts]
    expected = _brute_interval_matching(candidates,truth,tolerance)
    actual = boundary_metrics(candidates,truth,tolerance=tolerance)
    pairs = [(tuple(row['candidate_interval']),row['truth_position']) for row in actual['matches']]
    errors = sum(row['location_error_records'] for row in actual['matches'])
    assert (actual['matched_count'],errors,pairs) == expected
    for row in actual['matches']:
        assert candidates[row['candidate_index']] == row['candidate_interval']
        assert truth[row['truth_index']] == row['truth_position']


def test_boundary_denominators_and_unchanged_stream_aggregation():
    unchanged = boundary_metrics([[4,4],[9,9]],[],tolerance=0)
    quiet = boundary_metrics([],[],tolerance=0)
    changed = boundary_metrics([[4,5]],[5,10],tolerance=0)
    assert unchanged['precision']['value'] == 0
    assert unchanged['recall']['value'] is None
    assert quiet['precision']['value'] is None
    assert quiet['mean_location_error_records']['value'] is None
    result = aggregate_stream_metrics([unchanged,quiet,changed],abstained_stream_count=1)
    assert result['total_stream_count'] == 4 and result['sample_coverage']['value'] == .75
    assert result['executed_unchanged_stream_count'] == 2
    assert result['false_candidates_per_unchanged_stream']['value'] == 1
    assert result['false_candidates_per_unchanged_stream']['numerator'] == 2
    assert result['precision']['value'] == 1/3
    assert result['recall']['value'] == .5
    assert aggregate_stream_metrics([])['false_candidates_per_unchanged_stream']['value'] is None
    assert aggregate_stream_metrics([])['sample_coverage']['value'] is None


@pytest.mark.parametrize('candidates,truth,tolerance', [
    ([[0,1]],[1],1), ([[2,1]],[1],1), ([[1,3],[3,5]],[2],1),
    ([[True,2]],[1],1), ([[1,1]],[0],1), ([[1,1]],[2,2],1),
    ([[1,1]],[2],-1), ([[1,1]],[2],True),
])
def test_invalid_boundary_coordinates_rejected(candidates,truth,tolerance):
    with pytest.raises(InputError):
        boundary_metrics(candidates,truth,tolerance=tolerance)
