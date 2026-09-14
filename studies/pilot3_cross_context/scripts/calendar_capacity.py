"""Bounded score-free enumeration of shared UTC-midnight calendar cuts.

Consumes previously verified eligible-record metadata only. It never opens an
archive, computes a writing feature, or changes an eligibility guard. Account
lists and account cut intervals in the result must remain private. Source-ID
uniqueness and mandatory exclusions remain the input census's responsibility.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from itertools import combinations
from typing import Iterable, Mapping, Sequence


VERSION = "pilot3-all-utc-midnight-cuts-v1"
WORDS_PER_CELL = 2000
RECORDS_PER_CELL = 8
MINIMUM_RECORD_WORDS = 20
MAX_COMMUNITIES = 8
MAX_RECORD_ROWS = 1_000_000
MAX_CALENDAR_DAYS = 20_000


def _date(value: str) -> date:
    if not isinstance(value, str):
        raise ValueError("Calendar bounds must be ISO calendar dates")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Calendar bounds must use YYYY-MM-DD")
    return parsed


def _utc_day(value: str) -> int:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("Eligible record timestamps must be explicit UTC with Z")
    instant = datetime.fromisoformat(value[:-1] + "+00:00")
    if instant.tzinfo is None or instant.utcoffset() != timezone.utc.utcoffset(instant):
        raise ValueError("Eligible record timestamps must use UTC")
    return instant.date().toordinal()


def _label(day: int) -> str:
    return date.fromordinal(day).isoformat()


def _cell_cut_interval(day_counts, first_day, end_day):
    """Find every cut satisfying BOTH guards on BOTH sides in one community.

    If the first forward threshold day is E, early records have timestamp <
    midnight(cut), so cut >= E+1, even when E contains midnight records. If the
    reverse threshold day is L, late records have timestamp >= midnight(cut),
    so cut <= L. Day aggregation preserves all timestamp ties, while whole-day
    cuts never split records or include a record on both sides.
    """
    days = sorted(day_counts)
    records = words = 0
    earliest = None
    for day in days:
        count, volume = day_counts[day]
        records += count
        words += volume
        if records >= RECORDS_PER_CELL and words >= WORDS_PER_CELL:
            earliest = day + 1
            break
    records = words = 0
    latest = None
    for day in reversed(days):
        count, volume = day_counts[day]
        records += count
        words += volume
        if records >= RECORDS_PER_CELL and words >= WORDS_PER_CELL:
            latest = day
            break
    if earliest is None or latest is None:
        return None
    earliest, latest = max(earliest, first_day + 1), min(latest, end_day - 1)
    return (earliest, latest) if earliest <= latest else None


def _merge_range(ranges, first, last):
    if ranges and first == ranges[-1][1] + 1:
        ranges[-1] = (ranges[-1][0], last)
    else:
        ranges.append((first, last))


def _pair_sweep(intervals, first_day, end_day):
    first_cut, last_cut = first_day + 1, end_day - 1
    if first_cut > last_cut:
        return {"cut": None, "maximum_accounts": 0, "days_with_any_accounts": 0,
                "days_at_maximum": 0, "maximizing_ranges": [], "available_bounds": None}
    events = defaultdict(int)
    events[first_cut] += 0
    events[last_cut + 1] += 0
    for earliest, latest in intervals.values():
        events[earliest] += 1
        events[latest + 1] -= 1
    points = sorted(events)
    active = 0
    best_key = None
    best_cut = None
    maximum = -1
    positive_days = maximum_days = 0
    ranges = []
    positive_first = positive_last = None
    midpoint_floor = (first_day + end_day) // 2
    for position, following in zip(points, points[1:]):
        active += events[position]
        end = following - 1
        if active:
            positive_days += following - position
            positive_first = position if positive_first is None else positive_first
            positive_last = end
        if active > maximum:
            maximum, maximum_days, ranges = active, following - position, [(position, end)]
        elif active == maximum:
            maximum_days += following - position
            _merge_range(ranges, position, end)
        # Closest integral day in this plateau; floor gives the earliest tie.
        candidate = max(position, min(midpoint_floor, end))
        key = (-active, abs(2 * candidate - first_day - end_day), candidate)
        if best_key is None or key < best_key:
            best_key, best_cut = key, candidate
    return {"cut": best_cut, "maximum_accounts": maximum,
            "days_with_any_accounts": positive_days, "days_at_maximum": maximum_days,
            "maximizing_ranges": ranges,
            "available_bounds": (positive_first, positive_last) if positive_first is not None else None}


def best_calendar_pairs(rows: Iterable[Mapping], communities: Sequence[str],
                        start: str, end: str) -> dict:
    """Maximize four-cell capacity over EVERY shared interior UTC-midnight cut.

    Every pair uses early=[start,cut) and late=[cut,end), with a single cut shared
    by both communities and all accounts in that pair. Full cells require 2000
    eligible words and eight original eligible records. Any tied maximum favors
    smaller abs(2*cut-start-end), then the earlier cut. This is a calendar-capacity
    proposal only; downstream global allocation and contamination gates still
    apply. The iterator is consumed once, and only daily numeric totals retained.
    """
    first_day, end_day = _date(start).toordinal(), _date(end).toordinal()
    if not 0 < end_day - first_day <= MAX_CALENDAR_DAYS:
        raise ValueError("Calendar span must be positive and at most 20000 days")
    if (not communities or len(communities) > MAX_COMMUNITIES
            or len(set(communities)) != len(communities)
            or any(not isinstance(c, str) or not c for c in communities)):
        raise ValueError("Provide one to eight distinct nonempty community names")
    community_names = sorted(communities)
    community_set = set(community_names)
    daily = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    input_rows = inside_rows = outside_rows = 0
    for row in rows:
        input_rows += 1
        if input_rows > MAX_RECORD_ROWS:
            raise ValueError("Predeclared metadata bound of one million rows exceeded")
        account, community = row["account_key"], row["community"]
        words = row["retained_words"]
        if not isinstance(account, str) or not account or account != account.casefold():
            raise ValueError("Account keys must be nonempty globally casefolded source identities")
        if community not in community_set:
            raise ValueError("Record community is outside the declared archive frame")
        if type(words) is not int or words < MINIMUM_RECORD_WORDS:
            raise ValueError("Rows must already satisfy the frozen twenty-word eligibility guard")
        if row.get("reason") is not None:
            raise ValueError("Rejected census rows are not eligible calendar inputs")
        day = _utc_day(row["created_utc"])
        if not first_day <= day < end_day:
            outside_rows += 1
            continue
        inside_rows += 1
        totals = daily[account, community][day]
        totals[0] += 1
        totals[1] += words
    cell_intervals = {}
    for key, day_counts in daily.items():
        interval = _cell_cut_interval(day_counts, first_day, end_day)
        if interval is not None:
            cell_intervals[key] = interval
    accounts = sorted({account for account, _ in daily})
    pairs = {}
    for left, right in combinations(community_names, 2):
        name = left + " / " + right
        intervals = {}
        for account in accounts:
            a, b = cell_intervals.get((account, left)), cell_intervals.get((account, right))
            if a is None or b is None:
                continue
            earliest, latest = max(a[0], b[0]), min(a[1], b[1])
            if earliest <= latest:
                intervals[account] = (earliest, latest)
        sweep = _pair_sweep(intervals, first_day, end_day)
        cut = sweep["cut"]
        chosen = [account for account, (earliest, latest) in sorted(intervals.items())
                  if cut is not None and earliest <= cut <= latest]
        if len(chosen) != sweep["maximum_accounts"]:
            raise AssertionError("Sweep maximum disagrees with actual interval membership")
        bounds = sweep["available_bounds"]
        pairs[name] = {
            "scheme": {"id": "utc_midnight_" + _label(cut), "early": [start, _label(cut)],
                       "late": [_label(cut), end]} if cut is not None else None,
            "accounts": chosen, "maximum_accounts": len(chosen),
            "pairwise_blocks_upper_bound": len(chosen) // 2,
            "accounts_with_any_feasible_cut": len(intervals),
            "all_internal_day_cuts_considered": max(0, end_day - first_day - 1),
            "day_cuts_with_any_accounts": sweep["days_with_any_accounts"],
            "day_cuts_at_maximum": sweep["days_at_maximum"],
            "available_cut_bounds": {"earliest": _label(bounds[0]), "latest": _label(bounds[1])} if bounds else None,
            "maximizing_cut_ranges": [{"first": _label(a), "last": _label(b)} for a, b in sweep["maximizing_ranges"]],
            "selected_calendar_imbalance_days": abs(2 * cut - first_day - end_day) if cut is not None else None,
            "account_cut_intervals_private": [{"account_key": account, "first_cut": _label(a), "last_cut": _label(b)}
                                               for account, (a, b) in sorted(intervals.items())],
        }
    return {"version": VERSION, "start": start, "end": end, "communities": community_names,
            "words_per_cell": WORDS_PER_CELL, "eligible_records_per_cell": RECORDS_PER_CELL,
            "input_eligible_metadata_rows": input_rows, "rows_inside_calendar_bounds": inside_rows,
            "rows_outside_calendar_bounds": outside_rows, "pairs": pairs,
            "selection_rule": "maximum_four_cell_accounts_then_minimum_abs_2cut_minus_start_minus_end_then_earliest_utc_midnight",
            "interval_rule": "early_threshold_day_plus_one_through_late_threshold_day_inclusive_intersected_across_communities",
            "source_prose_read": False, "new_preprocessing_performed": False,
            "style_scores_computed": False, "final_cohort_selected": False,
            "privacy": "Account lists and per-account cut intervals are private source-identity metadata."}
