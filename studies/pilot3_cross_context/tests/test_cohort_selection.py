import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from cohort_selection import account_rank, candidate_prefix, hash_quota_allocation


def records(words=250, count=16):
    return [{'account_key': 'fixture', 'community': 'X', 'record_id': str(i),
             'created_utc': f'2016-01-{i + 1:02d}T00:00:00Z',
             'retained_words': words, 'reason': None} for i in range(count)]


def test_whole_midpoint_buffer_then_chronology_no_mutation():
    rows = records()
    old = copy.deepcopy(rows)
    result = candidate_prefix(rows, ['2016-01-01', '2016-02-01'])
    assert [r['record_id'] for r in result] == [str(i) for i in range(4, 16)]
    assert sum(r['retained_words'] for r in result) == 3000
    assert rows == old


def test_scarce_buffer_is_all_originals_not_failed_full_cell():
    rows = records(count=8)
    assert candidate_prefix(rows, ['2016-01-01', '2016-02-01']) == rows


@pytest.mark.parametrize('rows', [records(words=200, count=8), records(words=900, count=7)])
def test_both_full_prerequisites_are_required(rows):
    with pytest.raises(ValueError, match='prerequisite'):
        candidate_prefix(rows, ['2016-01-01', '2016-02-01'])


def test_overshoot_and_record_guard_cannot_split_long_comments():
    rows = records(words=1000, count=10)
    result = candidate_prefix(rows, ['2016-01-01', '2016-02-01'])
    assert len(result) == 8
    assert sum(r['retained_words'] for r in result) == 8000


@pytest.mark.parametrize('defect', ['duplicate', 'outside', 'community', 'ineligible'])
def test_bad_candidate_metadata_fails(defect):
    rows = records()
    if defect == 'duplicate': rows[-1]['record_id'] = rows[0]['record_id']
    if defect == 'outside': rows[-1]['created_utc'] = '2016-02-01T00:00:00Z'
    if defect == 'community': rows[-1]['community'] = 'Y'
    if defect == 'ineligible': rows[-1]['reason'] = 'below_guard'
    with pytest.raises(ValueError): candidate_prefix(rows, ['2016-01-01', '2016-02-01'])


def test_hash_flow_retains_global_quota_feasibility_and_determinism():
    eligible = {'first': {'a', 'b', 'c', 'd'}, 'second': {'a', 'b'}}
    result = hash_quota_allocation(eligible, 2)
    assert result['quota_counts'] == {'first': 2, 'second': 2}
    assert set(result['assigned']['first']) == {'c', 'd'}
    assert set(result['assigned']['second']) == {'a', 'b'}
    assert hash_quota_allocation(dict(reversed(list(eligible.items()))), 2) == result


def test_noncanonical_account_is_not_silently_conflated():
    with pytest.raises(ValueError): account_rank('UPPER')


def test_insufficient_stratum_stays_insufficient():
    result = hash_quota_allocation({'a': {f'a{i}' for i in range(20)},
                                    'b': {f'b{i}' for i in range(19)},
                                    'c': {f'c{i}' for i in range(20)}})
    assert result['total_accounts'] == 58
    assert result['quota_counts']['b'] == 18
