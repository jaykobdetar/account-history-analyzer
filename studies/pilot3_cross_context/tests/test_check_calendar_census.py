"""Independent calendar checker arithmetic on synthetic metadata only."""
from datetime import datetime, timedelta, timezone
from itertools import combinations, product
from pathlib import Path
import random
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_calendar_census as checker


def records(account, community, timestamp, count=8, words=250):
    return [{'account_key': account, 'community': community,
             'record_id': f'{account}-{community}-{timestamp}-{index}',
             'created_utc': timestamp, 'retained_words': words, 'reason': None}
            for index in range(count)]


def test_midnight_ties_put_every_whole_record_on_one_side_only():
    rows = []
    for community in ('X', 'Y'):
        rows += records('a', community, '2017-01-02T23:59:59Z')
        rows += records('a', community, '2017-01-03T00:00:00Z')
    result = checker.direct_calendar_counts(rows, ['X', 'Y'], '2017-01-01', '2017-01-06')['pairs']['X / Y']
    assert result['maximum_accounts'] == 1 and result['accounts'] == {'a'}
    assert result['scheme']['early'] == ['2017-01-01', '2017-01-03']
    assert result['day_cuts_with_any_accounts'] == 1
    assert result['account_cut_intervals_private'] == [{'account_key': 'a', 'first_cut': '2017-01-03', 'last_cut': '2017-01-03'}]


def test_records_on_same_calendar_day_cannot_be_split_by_shared_midnight():
    rows = []
    for community in ('X', 'Y'):
        rows += records('a', community, '2017-01-02T00:00:00Z')
        rows += records('a', community, '2017-01-02T23:59:59Z')
    result = checker.direct_calendar_counts(rows, ['X', 'Y'], '2017-01-01', '2017-01-06')['pairs']['X / Y']
    assert result['maximum_accounts'] == 0 and result['accounts'] == set()
    assert result['scheme']['early'][-1] == '2017-01-03'  # Earliest equal-imbalance midpoint.
    assert result['day_cuts_at_maximum'] == 4


@pytest.mark.parametrize('count,words', [(7, 400), (8, 249)])
def test_all_four_cells_need_both_2000_words_and_eight_records(count, words):
    rows = []
    for community in ('X', 'Y'):
        rows += records('a', community, '2017-01-01T00:00:00Z')
        rows += records('a', community, '2017-01-05T00:00:00Z', count=count if community == 'Y' else 8, words=words if community == 'Y' else 250)
    result = checker.direct_calendar_counts(rows, ['X', 'Y'], '2017-01-01', '2017-01-06')['pairs']['X / Y']
    assert result['maximum_accounts'] == 0


def brute_calendar(rows, start, end):
    begin = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    finish = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
    candidates = []
    for day in range(1, (finish - begin).days):
        cut = begin + timedelta(days=day)
        members = set()
        for account in {row['account_key'] for row in rows}:
            qualifies = True
            for community in ('X', 'Y'):
                for left, right in ((begin, cut), (cut, finish)):
                    cell = [row for row in rows if row['account_key'] == account and row['community'] == community and left <= datetime.fromisoformat(row['created_utc'].replace('Z', '+00:00')) < right]
                    qualifies &= len(cell) >= 8 and sum(row['retained_words'] for row in cell) >= 2000
            if qualifies:
                members.add(account)
        candidates.append(((-len(members), abs((cut - begin).days - (finish - cut).days), cut), members))
    return min(candidates, key=lambda item: item[0])


@pytest.mark.parametrize('seed', range(5))
def test_binary_prefix_checker_matches_literal_four_cell_enumeration(seed):
    randomizer = random.Random(seed)
    rows = []
    for account in ('a', 'b', 'c'):
        for community in ('X', 'Y'):
            for index in range(24):
                day = randomizer.randint(1, 7)
                rows.append({'account_key': account, 'community': community,
                             'record_id': f'{account}-{community}-{index}',
                             'created_utc': f'2017-01-{day:02d}T00:00:00Z',
                             'retained_words': randomizer.choice((20, 249, 250, 500)), 'reason': None})
    actual = checker.direct_calendar_counts(rows, ['X', 'Y'], '2017-01-01', '2017-01-08')['pairs']['X / Y']
    expected, members = brute_calendar(rows, '2017-01-01', '2017-01-08')
    assert actual['maximum_accounts'] == -expected[0]
    assert actual['scheme']['early'][-1] == expected[2].date().isoformat()
    assert actual['accounts'] == members


def brute_strata(sets):
    best = None
    full = 0
    for names in combinations(sorted(sets), 3):
        members = sorted(set.union(*(sets[name] for name in names)))
        attainable = set()
        for assignments in product(range(-1, 3), repeat=len(members)):
            if all(destination == -1 or member in sets[names[destination]] for member, destination in zip(members, assignments)):
                quotas = tuple(assignments.count(i) for i in range(3))
                if all(q % 2 == 0 and q <= 20 for q in quotas):
                    attainable.add(quotas)
        quotas = max(attainable, key=lambda q: (sum(q), sorted(q), q))
        full += quotas == (20, 20, 20)
        raw = [len(sets[name]) for name in names]
        key = (-sum(quotas), tuple(-q for q in sorted(quotas)), -min(raw), -sum(raw), names)
        if best is None or key < best[0]:
            best = key, names, quotas
    return list(best[1]), dict(zip(best[1], best[2])), full


@pytest.mark.parametrize('seed', range(3))
def test_hall_enumeration_matches_literal_account_assignments(seed):
    randomizer = random.Random(seed)
    sets = {name: {str(i) for i in range(5) if randomizer.randrange(2)} for name in ('P', 'Q', 'R', 'S')}
    expected_names, expected_quotas, full = brute_strata(sets)
    actual = checker.exhaustive_three_strata(sets)
    assert actual['selected_pairs'] == expected_names
    assert actual['quota_counts'] == expected_quotas
    assert actual['full_target_feasible_triple_count'] == full
    assert actual['candidate_triples_checked'] == 4


def test_disjoint_capacity_is_not_sum_of_overlapping_pair_capacities():
    shared = {str(i) for i in range(20)}
    result = checker.exhaustive_three_strata({'A': shared, 'B': shared, 'C': shared})
    assert result['total_accounts'] == 20 and result['total_blocks'] == 10
    assert sorted(result['quota_counts'].values()) == [6, 6, 8]
    assert result['full_target_feasible_triple_count'] == 0


def test_synthetic_52_account_bound_and_saved_assignment_target():
    sets = {'A': {f'a-{i}' for i in range(12)}, 'B': {f'b-{i}' for i in range(39)}, 'C': {f'c-{i}' for i in range(36)}, 'D': {'a-0'}}
    result = checker.exhaustive_three_strata(sets)
    assert result['selected_pairs'] == ['A', 'B', 'C']
    assert result['quota_counts'] == {'A': 12, 'B': 20, 'C': 20}
    assert result['total_accounts'] == 52 and result['total_blocks'] == 26


def test_protected_or_duplicate_metadata_fails_before_calendar_counts():
    rows = records('protected', 'X', '2017-01-02T00:00:00Z')
    with pytest.raises(ValueError, match='Protected'):
        checker.direct_calendar_counts(rows, ['X', 'Y'], '2017-01-01', '2017-01-06', {'protected'})
    rows = records('a', 'X', '2017-01-02T00:00:00Z')
    with pytest.raises(ValueError, match='Repeated original'):
        checker.direct_calendar_counts(rows + rows[:1], ['X', 'Y'], '2017-01-01', '2017-01-06')
