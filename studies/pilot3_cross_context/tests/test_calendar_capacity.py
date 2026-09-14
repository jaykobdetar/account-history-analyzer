"""Independent full-timestamp, every-cut enumeration versus interval sweep."""
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path
import random
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import calendar_capacity as calendar


def records(account, community, timestamp, count=8, words=250):
    return [{'account_key': account, 'community': community, 'created_utc': timestamp,
             'retained_words': words} for _ in range(count)]


def interval_rows(account, first_cut, last_cut, communities=('X', 'Y')):
    first = datetime.fromisoformat(first_cut) - timedelta(days=1)
    return [row for community in communities
            for row in (records(account, community, first.isoformat() + 'Z') +
                        records(account, community, last_cut + 'T00:00:00Z'))]


def brute_force(rows, communities, start, end):
    """No prefix sums or interval logic: evaluate every original row at every cut."""
    initial = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    final = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
    accounts = sorted({row['account_key'] for row in rows})
    timestamped = [(datetime.fromisoformat(row['created_utc'].replace('Z', '+00:00')), row) for row in rows]
    answer = {}
    for x, y in combinations(sorted(communities), 2):
        cut = initial + timedelta(days=1)
        candidates = []
        available_by_account = {account: [] for account in accounts}
        while cut < final:
            valid = []
            for account in accounts:
                qualified = True
                for community in (x, y):
                    for low, high in ((initial, cut), (cut, final)):
                        observed = [row for instant, row in timestamped
                                    if row['account_key'] == account and row['community'] == community and low <= instant < high]
                        qualified &= len(observed) >= 8 and sum(row['retained_words'] for row in observed) >= 2000
                if qualified:
                    valid.append(account)
                    available_by_account[account].append(cut.date().isoformat())
            candidates.append(((-len(valid), abs((cut - initial) - (final - cut)), cut), valid))
            cut += timedelta(days=1)
        chosen = min(candidates) if candidates else None
        answer[x + ' / ' + y] = {
            'cut': chosen[0][2].date().isoformat() if chosen else None,
            'accounts': chosen[1] if chosen else [],
            'intervals': [{'account_key': account, 'first_cut': cuts[0], 'last_cut': cuts[-1]}
                          for account, cuts in available_by_account.items() if cuts],
            'counts': [len(valid) for _, valid in candidates],
        }
    return answer


def assert_matches_brute(rows, communities, start, end):
    actual = calendar.best_calendar_pairs(iter(rows), communities, start, end)
    expected = brute_force(rows, communities, start, end)
    for name, comparison in expected.items():
        pair = actual['pairs'][name]
        assert pair['accounts'] == comparison['accounts']
        assert pair['maximum_accounts'] == len(comparison['accounts'])
        assert (pair['scheme']['early'][1] if pair['scheme'] else None) == comparison['cut']
        assert pair['account_cut_intervals_private'] == comparison['intervals']
        assert pair['all_internal_day_cuts_considered'] == len(comparison['counts'])
        assert pair['day_cuts_with_any_accounts'] == sum(count > 0 for count in comparison['counts'])
        maximum = max(comparison['counts'], default=None)
        assert pair['day_cuts_at_maximum'] == sum(count == maximum for count in comparison['counts'])
    return actual


def test_midnight_ties_go_wholly_to_late_and_reverse_threshold_is_inclusive():
    rows = interval_rows('account', '2017-01-02', '2017-01-02')
    result = assert_matches_brute(rows, ['X', 'Y'], '2017-01-01', '2017-01-04')
    pair = result['pairs']['X / Y']
    assert pair['scheme']['early'] == ['2017-01-01', '2017-01-02']
    assert pair['scheme']['late'] == ['2017-01-02', '2017-01-04']
    assert pair['day_cuts_with_any_accounts'] == 1
    assert pair['maximum_accounts'] == 1


def test_all_records_at_same_instant_cannot_supply_both_periods():
    rows = records('tied', 'X', '2017-01-02T00:00:00Z', count=16)
    rows += records('tied', 'Y', '2017-01-02T00:00:00Z', count=16)
    pair = assert_matches_brute(rows, ['X', 'Y'], '2017-01-01', '2017-01-05')['pairs']['X / Y']
    assert pair['maximum_accounts'] == 0
    assert pair['account_cut_intervals_private'] == []


def test_subsecond_before_midnight_and_exact_midnight_are_not_rounded_together():
    rows = [row for community in ['X', 'Y'] for row in
            records('account', community, '2017-01-01T23:59:59.999999Z') +
            records('account', community, '2017-01-02T00:00:00Z')]
    pair = assert_matches_brute(rows, ['X', 'Y'], '2017-01-01', '2017-01-04')['pairs']['X / Y']
    assert pair['maximum_accounts'] == 1
    assert pair['available_cut_bounds'] == {'earliest': '2017-01-02', 'latest': '2017-01-02'}


def test_intersect_both_community_intervals_and_balance_earlier_tie():
    rows = interval_rows('account', '2017-01-02', '2017-01-08', ['X'])
    rows += interval_rows('account', '2017-01-04', '2017-01-06', ['Y'])
    pair = assert_matches_brute(rows, ['X', 'Y'], '2017-01-01', '2017-01-10')['pairs']['X / Y']
    assert pair['available_cut_bounds'] == {'earliest': '2017-01-04', 'latest': '2017-01-06'}
    assert pair['scheme']['early'][1] == '2017-01-05'
    assert pair['selected_calendar_imbalance_days'] == 1


def test_both_word_and_record_guards_apply_and_no_individual_record_is_cut():
    rows = []
    for community in ['X', 'Y']:
        for account, count, words in [('shortwords', 8, 249), ('shortrecords', 7, 400), ('longrecord', 1, 5000)]:
            rows += records(account, community, '2017-01-01T12:00:00Z', count, words)
            rows += records(account, community, '2017-01-09T12:00:00Z')
    pair = assert_matches_brute(rows, ['X', 'Y'], '2017-01-01', '2017-01-11')['pairs']['X / Y']
    assert pair['maximum_accounts'] == 0


def test_maximum_shared_account_capacity_precedes_balanced_calendar_cut():
    rows = interval_rows('a', '2017-01-02', '2017-01-04')
    rows += interval_rows('b', '2017-01-03', '2017-01-04')
    rows += interval_rows('c', '2017-01-08', '2017-01-09')
    pair = assert_matches_brute(rows, ['X', 'Y'], '2017-01-01', '2017-01-11')['pairs']['X / Y']
    assert pair['accounts'] == ['a', 'b']
    assert pair['accounts_with_any_feasible_cut'] == 3
    assert pair['scheme']['early'][1] == '2017-01-04'
    assert pair['day_cuts_at_maximum'] == 2


def test_disconnected_maxima_use_earlier_cut_when_calendar_imbalance_ties():
    rows = interval_rows('a', '2017-01-04', '2017-01-04')
    rows += interval_rows('b', '2017-01-08', '2017-01-08')
    pair = assert_matches_brute(rows, ['X', 'Y'], '2017-01-01', '2017-01-11')['pairs']['X / Y']
    assert pair['scheme']['early'][1] == '2017-01-04'
    assert pair['maximizing_cut_ranges'] == [{'first': '2017-01-04', 'last': '2017-01-04'},
                                             {'first': '2017-01-08', 'last': '2017-01-08'}]
    assert pair['day_cuts_with_any_accounts'] == 2


def test_net_zero_event_preserves_correct_membership_and_merges_adjacent_maximum_range():
    rows = interval_rows('a', '2017-01-02', '2017-01-04')
    rows += interval_rows('b', '2017-01-05', '2017-01-07')
    pair = assert_matches_brute(rows, ['X', 'Y'], '2017-01-01', '2017-01-09')['pairs']['X / Y']
    assert pair['accounts'] == ['b']
    assert pair['scheme']['early'][1] == '2017-01-05'
    assert pair['maximizing_cut_ranges'] == [{'first': '2017-01-02', 'last': '2017-01-07'}]
    assert pair['day_cuts_at_maximum'] == 6


def test_no_interiors_empty_inputs_leap_day_and_outside_overall_bounds():
    single = calendar.best_calendar_pairs([], ['X', 'Y'], '2017-01-01', '2017-01-02')['pairs']['X / Y']
    assert single['scheme'] is None and single['maximum_accounts'] == 0
    assert single['all_internal_day_cuts_considered'] == 0
    leap = assert_matches_brute([], ['X', 'Y'], '2008-02-28', '2008-03-02')['pairs']['X / Y']
    assert leap['scheme']['early'][1] == '2008-02-29'
    assert leap['all_internal_day_cuts_considered'] == 2
    rows = records('outside', 'X', '2007-12-31T23:59:59Z') + records('outside', 'Y', '2018-11-01T00:00:00Z')
    result = calendar.best_calendar_pairs(rows, ['X', 'Y'], '2008-01-01', '2018-11-01')
    assert result['rows_inside_calendar_bounds'] == 0
    assert result['rows_outside_calendar_bounds'] == result['input_eligible_metadata_rows'] == 16


def test_random_unsorted_full_timestamp_records_against_every_cut_oracle():
    rng = random.Random(991831)
    for _ in range(12):
        rows = []
        for account in ['a', 'b', 'c']:
            for community in ['X', 'Y', 'Z']:
                for _ in range(rng.randrange(14, 32)):
                    day = rng.randrange(1, 16)
                    time = rng.choice(['00:00:00', '00:00:00.000001', '12:00:00', '23:59:59.999999'])
                    rows += records(account, community, f'2017-01-{day:02}T{time}Z', 1, rng.randrange(20, 601))
        rng.shuffle(rows)
        actual = assert_matches_brute(rows, ['X', 'Y', 'Z'], '2017-01-01', '2017-01-16')
        assert calendar.best_calendar_pairs(reversed(rows), ['Z', 'X', 'Y'], '2017-01-01', '2017-01-16') == actual


def test_twenty_eight_pairs_and_one_pass_metadata_iterable():
    communities = [f'community{i}' for i in range(8)]
    rows = interval_rows('account', '2017-01-04', '2017-01-08', communities)
    class Once:
        def __init__(self):
            self.called = False
        def __iter__(self):
            assert not self.called
            self.called = True
            return iter(rows)
    result = calendar.best_calendar_pairs(Once(), communities, '2017-01-01', '2017-01-11')
    assert len(result['pairs']) == 28
    assert all(p['accounts'] == ['account'] for p in result['pairs'].values())
    assert all(p['scheme']['early'][1] == '2017-01-06' for p in result['pairs'].values())


@pytest.mark.parametrize('override', [
    {'created_utc': None}, {'created_utc': '2017-01-01T00:00:00'},
    {'created_utc': '2017-01-01T00:00:00-05:00'}, {'retained_words': 19},
    {'retained_words': 250.0}, {'retained_words': True}, {'reason': 'rejected'},
    {'community': 'unlisted'}, {'account_key': 'MixedCase'},
])
def test_invalid_or_ineligible_metadata_is_not_silently_reinterpreted(override):
    row = records('account', 'X', '2017-01-01T00:00:00Z', 1)[0]
    row.update(override)
    with pytest.raises(ValueError):
        calendar.best_calendar_pairs([row], ['X', 'Y'], '2017-01-01', '2017-01-11')


def test_explicit_metadata_calendar_and_community_resource_bounds(monkeypatch):
    monkeypatch.setattr(calendar, 'MAX_RECORD_ROWS', 1)
    with pytest.raises(ValueError, match='one million'):
        calendar.best_calendar_pairs(records('a', 'X', '2017-01-01T00:00:00Z', 2), ['X', 'Y'], '2017-01-01', '2017-01-11')
    with pytest.raises(ValueError):
        calendar.best_calendar_pairs([], ['X', 'Y'], '2018-01-01', '2017-01-01')
    with pytest.raises(ValueError):
        calendar.best_calendar_pairs([], ['X', 'Y'], '1900-01-01', '2017-01-01')
    with pytest.raises(ValueError):
        calendar.best_calendar_pairs([], ['X', 'X'], '2017-01-01', '2017-01-11')
    with pytest.raises(ValueError):
        calendar.best_calendar_pairs([], [str(i) for i in range(9)], '2017-01-01', '2017-01-11')
