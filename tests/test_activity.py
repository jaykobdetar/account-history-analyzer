"""ACT acceptance arithmetic and independent small-history properties."""
from __future__ import annotations

import math
import random
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from account_history_analyzer.activity import analyze_activity
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import canonical_bytes, load_snapshot

ROOT = Path(__file__).resolve().parents[1]
BASE = datetime(2025, 1, 1, tzinfo=timezone.utc)


def timestamp(offset):
    return (BASE + timedelta(seconds=offset)).isoformat().replace("+00:00", "Z")


def activity(tmp_path, offsets, *, extra_records=(), coverage=None, overrides=None):
    rows = [{"schema_version": "1.0.0", "id": f"r{index:04d}", "account_id": "a", "kind": "comment", "status": "present", "text": "x", "created_utc": timestamp(offset)} for index, offset in enumerate(offsets)]
    rows.extend(extra_records)
    manifest = {"schema_version": "1.0.0", "snapshot_id": "s", "account_id": "a", "source_category": "synthetic", "text_format": "plain", "default_language": "und", "coverage": coverage or {"status": "unknown"}}
    records_path = tmp_path / "records.jsonl"
    manifest_path = tmp_path / "snapshot.json"
    records_path.write_bytes(b"".join(canonical_bytes(row) for row in rows))
    manifest_path.write_bytes(canonical_bytes(manifest))
    return analyze_activity(load_snapshot(records_path, manifest_path), AnalysisConfig.from_mapping(overrides))


def test_ACT_01_arithmetic_full_oracle():
    snapshot = load_snapshot(ROOT / "fixtures/arithmetic.jsonl", ROOT / "fixtures/arithmetic.snapshot.json")
    result = analyze_activity(snapshot, AnalysisConfig.from_toml())
    assert result["event_count"] == 6
    assert result["observed_span_seconds"] == 180
    assert [gap["seconds"] for gap in result["gaps"]] == [10, 10, 40, 60, 60]
    summary = result["gap_summary"]
    assert summary["count"] == 5
    assert summary["mean"] == 36
    assert summary["population_variance_seconds_squared"] == 504
    assert summary["median"] == 40
    assert summary["q25"] == 10
    assert summary["q75"] == 60
    assert summary["coefficient_of_variation"] == pytest.approx(math.sqrt(504) / 36)
    assert [row["maximum_events"] for row in result["maximum_sliding_windows"]] == [3, 5, 6]
    assert result["greedy_bursts"][0]["record_ids"] == ["arithmetic_001", "arithmetic_002", "arithmetic_003"]
    assert len(result["greedy_bursts"]) == 1
    assert result["hour_histogram"] == [6] + [0] * 23
    assert result["events_per_day"] == [{"date": "2025-01-01", "event_count": 6, "edge_day": True, "known_gap": False}]


def test_ACT_02_empty_history_and_single_event_missingness(tmp_path):
    result = activity(tmp_path, [])
    assert result["event_count"] == result["day_count"] == result["zero_event_days"] == 0
    assert result["earliest_utc"] is result["latest_utc"] is result["observed_span_seconds"] is None
    assert result["gap_summary"]["mean"] is None
    assert result["gap_summary"]["summary_reason"] == "no_intervals"
    assert all(row["maximum_events"] == 0 and row["record_ids"] == [] for row in result["maximum_sliding_windows"])
    assert result["greedy_bursts"] == []
    single = activity(tmp_path, [0])
    assert single["event_count"] == 1 and single["observed_span_seconds"] == 0
    assert single["gap_summary"]["coefficient_of_variation"] is None
    assert single["gap_summary"]["coefficient_of_variation_reason"] == "fewer_than_two_intervals"


def test_ACT_03_simultaneous_timestamps_and_zero_gap_mean(tmp_path):
    result = activity(tmp_path, [0, 0, 0, 0])
    assert result["gap_summary"]["mean"] == 0
    assert result["gap_summary"]["population_variance_seconds_squared"] == 0
    assert result["gap_summary"]["coefficient_of_variation"] is None
    assert result["gap_summary"]["coefficient_of_variation_reason"] == "zero_mean_interval"
    assert result["simultaneous_timestamp_groups"][0]["record_ids"] == ["r0000", "r0001", "r0002", "r0003"]
    assert all(row["maximum_events"] == 4 for row in result["maximum_sliding_windows"])
    assert result["greedy_bursts"][0]["observed_duration_seconds"] == 0


def test_ACT_04_inclusive_endpoint_and_microsecond_precision(tmp_path):
    result = activity(tmp_path, [0, 10, 30, 30.000001])
    assert result["maximum_sliding_windows"][0]["maximum_events"] == 3
    assert result["maximum_sliding_windows"][0]["record_ids"] == ["r0000", "r0001", "r0002"]
    assert result["gaps"][-1]["microseconds"] == 1
    assert result["greedy_bursts"][0]["record_ids"] == ["r0000", "r0001", "r0002"]


def test_ACT_05_greedy_nonoverlapping_is_not_gap_connected(tmp_path):
    result = activity(tmp_path, [0, 20, 30, 40, 50, 60])
    assert [burst["record_ids"] for burst in result["greedy_bursts"]] == [["r0000", "r0001", "r0002"], ["r0003", "r0004", "r0005"]]
    assert len({record_id for burst in result["greedy_bursts"] for record_id in burst["record_ids"]}) == 6
    result = activity(tmp_path, [0, 200, 205, 210])
    assert result["greedy_bursts"][0]["record_ids"] == ["r0001", "r0002", "r0003"]


def test_ACT_06_absent_prose_and_missing_times(tmp_path):
    extra = [
        {"schema_version": "1.0.0", "id": "removed", "account_id": "a", "kind": "comment", "status": "removed", "text": None, "created_utc": timestamp(10)},
        {"schema_version": "1.0.0", "id": "missing", "account_id": "a", "kind": "comment", "status": "present", "text": "Still available for text analysis"},
    ]
    result = activity(tmp_path, [0], extra_records=extra)
    assert result["event_count"] == 2
    assert result["missing_timestamp_records"] == 1
    assert result["gaps"][0]["right_record_id"] == "removed"
    assert result["gap_summary"]["count"] == 1
    assert result["gap_summary"]["coefficient_of_variation"] is None


def test_ACT_07_calendar_exposure_cross_midnight_year_and_gaps(tmp_path):
    result = activity(tmp_path, [-1, 2 * 86400], coverage={
        "status": "sampled", "start_utc": "2024-12-01T00:00:00Z", "end_utc": "2025-02-01T00:00:00Z",
        "known_gaps": [{"start_utc": "2025-01-01T01:00:00Z", "end_utc": "2025-01-01T02:00:00Z"}],
    })
    assert [row["date"] for row in result["events_per_day"]] == ["2024-12-31", "2025-01-01", "2025-01-02", "2025-01-03"]
    assert [row["event_count"] for row in result["events_per_day"]] == [1, 0, 0, 1]
    assert [row["edge_day"] for row in result["events_per_day"]] == [True, False, False, True]
    assert [row["known_gap"] for row in result["events_per_day"]] == [False, True, False, False]
    assert result["zero_event_days"] == 2
    assert result["event_bearing_days"] == 2
    assert sum(row["days_in_supplied_range"] for row in result["weekdays"]) == 4
    assert sum(row["supplied_events"] for row in result["weekdays"]) == 2
    assert result["hour_histogram"][0] == result["hour_histogram"][23] == 1


def test_ACT_08_quantiles_and_population_statistics_independent(tmp_path):
    result = activity(tmp_path, [0, 1, 5, 14, 30, 55])
    gaps = [1, 4, 9, 16, 25]
    summary = result["gap_summary"]
    assert summary["mean"] == statistics.mean(gaps)
    assert summary["population_variance_seconds_squared"] == pytest.approx(statistics.pvariance(gaps))
    assert summary["median"] == statistics.median(gaps)
    assert [summary["q25"], summary["median"], summary["q75"]] == np.quantile(gaps, [.25, .5, .75], method="linear").tolist()
    even = activity(tmp_path, [0, 1, 4, 9, 16])["gap_summary"]
    assert even["q25"] == 2.5 and even["median"] == 4 and even["q75"] == 5.5


def test_ACT_09_random_sliding_windows_against_brute_force(tmp_path):
    rng = random.Random(7489)
    for _ in range(30):
        offsets = sorted(rng.choices(range(500), k=rng.randrange(1, 45)))
        result = activity(tmp_path, offsets)
        for window in result["maximum_sliding_windows"]:
            duration = window["duration_seconds"]
            expected = max(sum(start <= value <= start + duration for value in offsets) for start in offsets)
            assert window["maximum_events"] == expected
        assert sum(row["event_count"] for row in result["events_per_day"]) == len(offsets)
        assert sum(result["hour_histogram"]) == len(offsets)
        assert len(result["gaps"]) == len(offsets) - 1


def test_ACT_10_input_order_does_not_affect_temporal_measurements(tmp_path):
    # IDs move with the records in actual ingestion tests; here unique times make
    # the numeric summaries independent even when construction IDs differ.
    first = activity(tmp_path, [10, 0, 30, 50])
    second = activity(tmp_path, [50, 10, 30, 0])
    assert first["gap_summary"] == second["gap_summary"]
    assert first["events_per_day"] == second["events_per_day"]
    assert [w["maximum_events"] for w in first["maximum_sliding_windows"]] == [w["maximum_events"] for w in second["maximum_sliding_windows"]]
