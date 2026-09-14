"""Descriptive UTC activity of distinct supplied events, including absent prose."""
from __future__ import annotations

import math
from collections import Counter
from datetime import date, datetime, timezone
from typing import Any

import numpy as np

from .io import Snapshot, epoch_us, thaw
from .errors import LimitError

_DAY_US = 86_400_000_000
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _calendar_date(timestamp: str) -> date:
    return datetime.fromisoformat(timestamp[:-1] + "+00:00").date()


def _interval_summary(gaps_us: list[int]) -> dict[str, Any]:
    values = [gap / 1_000_000 for gap in gaps_us]
    count = len(values)
    mean = math.fsum(values) / count if count else None
    variance = math.fsum((value - mean) ** 2 for value in values) / count if count else None
    stddev = math.sqrt(variance) if variance is not None else None
    reason = "fewer_than_two_intervals" if count < 2 else "zero_mean_interval" if mean == 0 else None
    quantiles = np.quantile(values, [0.25, 0.5, 0.75], method="linear").tolist() if count else [None, None, None]
    return {
        "count": count, "unit": "seconds", "mean": mean,
        "population_variance_seconds_squared": variance, "population_standard_deviation": stddev,
        "minimum": min(values) if values else None, "q25": quantiles[0],
        "median": quantiles[1], "q75": quantiles[2], "maximum": max(values) if values else None,
        "quantile_method": "numpy_linear_n_minus_1",
        "coefficient_of_variation": stddev / mean if reason is None else None,
        "coefficient_of_variation_reason": reason,
        "summary_reason": "no_intervals" if not count else None,
    }


def analyze_activity(snapshot: Snapshot, config: Any) -> dict[str, Any]:
    """Return activity payload from all unique timestamped supplied events.

    Deleted/removed records and text-ineligible records still count. Inclusive
    sliding windows tie-break at the earliest event in canonical record order.
    Missing interval summaries are null with reasons. The caller supplies the
    module envelope (`ok` when events exist, `insufficient_data` otherwise).
    """
    events = [record for record in snapshot.records if record["created_utc"] is not None]
    times = [epoch_us(record["created_utc"]) for record in events]
    dates = [_calendar_date(record["created_utc"]) for record in events]
    event_count = len(events)
    date_counts = Counter(dates)
    hourly = [0] * 24
    weekday_events = [0] * 7
    for record, event_date in zip(events, dates, strict=True):
        hour = int(record["created_utc"][11:13])
        hourly[hour] += 1
        weekday_events[event_date.weekday()] += 1
    known_gaps = thaw(snapshot.manifest["coverage"]["known_gaps"])
    gap_intervals = [(epoch_us(gap["start_utc"]), epoch_us(gap["end_utc"])) for gap in known_gaps]
    daily = []
    weekday_days = [0] * 7
    if events:
        first_ordinal, last_ordinal = dates[0].toordinal(), dates[-1].toordinal()
        calendar_days = last_ordinal - first_ordinal + 1
        if calendar_days > config["activity"]["max_calendar_days"]:
            raise LimitError(
                f"Observed UTC range requires {calendar_days} daily bins; configured limit is {config['activity']['max_calendar_days']}",
                code="activity_calendar_day_limit",
            )
        for ordinal in range(first_ordinal, last_ordinal + 1):
            day = date.fromordinal(ordinal)
            start_us = (ordinal - date(1970, 1, 1).toordinal()) * _DAY_US
            weekday_days[day.weekday()] += 1
            daily.append({
                "date": day.isoformat(), "event_count": date_counts[day],
                "edge_day": ordinal in (first_ordinal, last_ordinal),
                "known_gap": any(start < start_us + _DAY_US and end >= start_us for start, end in gap_intervals),
            })
    weekdays = [{"weekday": name, "days_in_supplied_range": weekday_days[index], "supplied_events": weekday_events[index]} for index, name in enumerate(_WEEKDAYS)]
    gaps_us = [right - left for left, right in zip(times, times[1:])]
    gaps = [{"left_record_id": events[index]["id"], "right_record_id": events[index + 1]["id"], "microseconds": gap, "seconds": gap / 1_000_000} for index, gap in enumerate(gaps_us)]
    simultaneous = []
    position = 0
    while position < event_count:
        end = position + 1
        while end < event_count and times[end] == times[position]:
            end += 1
        if end - position > 1:
            simultaneous.append({"created_utc": events[position]["created_utc"], "record_ids": [record["id"] for record in events[position:end]]})
        position = end
    sliding = []
    for duration in sorted(config["activity"]["sliding_window_seconds"]):
        duration_us = duration * 1_000_000
        end = best_start = best_end = 0
        for start in range(event_count):
            while end < event_count and times[end] - times[start] <= duration_us:
                end += 1
            if end - start > best_end - best_start:
                best_start, best_end = start, end
        selected = events[best_start:best_end]
        sliding.append({
            "duration_seconds": duration, "inclusive_endpoints": True,
            "maximum_events": len(selected), "record_ids": [record["id"] for record in selected],
            "first_utc": selected[0]["created_utc"] if selected else None,
            "last_utc": selected[-1]["created_utc"] if selected else None,
        })
    burst_duration = config["activity"]["burst_duration_seconds"]
    burst_minimum = config["activity"]["burst_minimum_events"]
    bursts = []
    start = 0
    end = 0
    while start < event_count:
        end = max(end, start)
        while end < event_count and times[end] - times[start] <= burst_duration * 1_000_000:
            end += 1
        if end - start >= burst_minimum:
            bursts.append({
                "record_ids": [record["id"] for record in events[start:end]],
                "first_utc": events[start]["created_utc"], "last_utc": events[end - 1]["created_utc"],
                "observed_duration_seconds": (times[end - 1] - times[start]) / 1_000_000,
            })
            start = end
        else:
            start += 1
    return {
        "timezone": "UTC", "scope": "distinct_supplied_events_with_creation_timestamps",
        "event_count": event_count, "missing_timestamp_records": len(snapshot.records) - event_count,
        "earliest_utc": events[0]["created_utc"] if events else None,
        "latest_utc": events[-1]["created_utc"] if events else None,
        "observed_span_seconds": (times[-1] - times[0]) / 1_000_000 if events else None,
        "events_per_day": daily, "hour_histogram": hourly, "weekdays": weekdays,
        "day_count": len(daily), "event_bearing_days": len(date_counts),
        "zero_event_days": len(daily) - len(date_counts), "known_coverage_gaps": known_gaps,
        "gaps": gaps, "gap_summary": _interval_summary(gaps_us),
        "simultaneous_timestamp_groups": simultaneous, "maximum_sliding_windows": sliding,
        "burst_method": "greedy_nonoverlapping_fixed_window_bursts",
        "burst_duration_seconds": burst_duration, "burst_minimum_events": burst_minimum,
        "greedy_bursts": bursts,
        "limitations": ["supplied_events_only", "gaps_do_not_establish_inactivity_or_sleep", "UTC_hours_aggregate_over_dates", "coverage_is_supplier_declared"],
    }
