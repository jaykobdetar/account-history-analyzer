"""WIN guards, whole-record allocation, canonical position and selector tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.errors import InputError
from account_history_analyzer.features import measure
from account_history_analyzer.io import canonical_bytes
from account_history_analyzer.text import preprocess
from account_history_analyzer.windows import build_streams, select_comparison, select_records

CONFIG = AnalysisConfig.from_toml()
BASE = datetime(2025, 1, 1, tzinfo=timezone.utc)
MANIFEST = {"text_format": "plain", "default_language": "en"}


def feature(index, words=125, *, text=None, config=CONFIG, **changes):
    record = {"id": f"r{index:04}", "account_id": "account", "kind": "comment", "status": "present",
              "text": text if text is not None else " ".join(["word"] * words),
              "created_utc": (BASE + timedelta(seconds=index)).isoformat().replace("+00:00", "Z"),
              "subreddit": "community", "language": "en", "edit_state": "unknown", "title": None, **changes}
    return measure(preprocess(record, MANIFEST, config), config)


def pooled_comment(result):
    return next(stream for stream in result["streams"] if stream["scope_type"] == "pooled" and stream["kind"] == "comment")


def test_WIN_01_both_word_and_record_guards_required():
    records = [feature(0, 1500)] + [feature(i, 20) for i in range(1, 8)]
    stream = pooled_comment(build_streams(records, CONFIG))
    assert stream["qualified_window_count"] == 1
    window = stream["windows"][0]
    assert window["record_count"] == 8
    assert window["word_count"] == 1640
    assert window["record_ids"] == [record["id"] for record in records]


def test_WIN_02_final_remainder_visible_no_padded_or_reused_records():
    records = [feature(i) for i in range(9)]
    stream = pooled_comment(build_streams(records, CONFIG))
    assert len(stream["windows"]) == 2
    assert stream["qualified_window_count"] == 1
    assert stream["eligible_words"] == 1125
    assert stream["remainder_word_count"] == 125
    first, remainder = stream["windows"]
    assert first["word_count"] == 1000 and first["qualified"]
    assert remainder["word_count"] == 125 and not remainder["qualified"]
    assert remainder["remainder"] is True
    assert "insufficient_target_words" in remainder["reason_codes"]
    assert "insufficient_record_count" in remainder["reason_codes"]
    assert [identifier for window in stream["windows"] for identifier in window["record_ids"]] == [record["id"] for record in records]


def test_WIN_03_whole_dominant_record_and_exact_half_threshold():
    first = [feature(0, 1500)] + [feature(i, 20) for i in range(1, 8)]
    window = pooled_comment(build_streams(first, CONFIG))["windows"][0]
    assert window["largest_record_share"] == 1500 / 1640
    assert "single_record_dominance" in window["reason_codes"]
    exact_half = [feature(0, 1000)] + [feature(i, 150) for i in range(1, 7)] + [feature(7, 100)]
    window = pooled_comment(build_streams(exact_half, CONFIG))["windows"][0]
    assert window["largest_record_share"] == .5
    assert "single_record_dominance" not in window["reason_codes"]


def test_WIN_04_kinds_titles_languages_and_missing_times_separate():
    comments = [feature(i) for i in range(8)]
    submissions = [feature(i, kind="submission", title=" ".join(["title"] * 5000)) for i in range(8, 16)]
    ineligible = [feature(16, language="und"), feature(17, language="es"), feature(18, created_utc=None), feature(19, words=19), feature(20, status="removed", text=None)]
    result = build_streams(comments + submissions + ineligible, CONFIG)
    pooled_streams = [stream for stream in result["streams"] if stream["scope_type"] == "pooled"]
    assert len(pooled_streams) == 2
    assert [stream["eligible_words"] for stream in pooled_streams] == [1000, 1000]
    assert [stream["windows"][0]["record_count"] for stream in pooled_streams] == [8, 8]
    assert set(pooled_streams[0]["eligible_record_ids"]).isdisjoint(pooled_streams[1]["eligible_record_ids"])


def test_WIN_10_edited_observed_and_exclusion_positions_remain_original():
    records = [feature(i, edit_state="edited" if i == 3 else "unknown") for i in range(17)]
    original = build_streams(records, CONFIG)
    assert "known_edited_observed_text" in pooled_comment(original)["windows"][0]["reason_codes"]
    reduced = pooled_comment(build_streams(records, CONFIG, excluded_ids=["r0003"]))
    assert reduced["windows"][0]["last_record_id"] == "r0008"
    assert reduced["windows"][0]["last_record_position"] == 8
    assert reduced["windows"][1]["first_record_position"] == 9
    assert all("r0003" not in window["record_ids"] for window in reduced["windows"])
    assert pooled_comment(original)["record_count"] == 17


def test_WIN_11_empty_and_underpowered_scopes_are_explicit():
    empty = build_streams([], CONFIG)
    assert len(empty["streams"]) == 2
    assert all(stream["windows"] == [] and stream["record_count"] == 0 for stream in empty["streams"])
    short = build_streams([feature(0, 20)], CONFIG)
    community = [stream for stream in short["streams"] if stream["scope_type"] == "community" and stream["kind"] == "comment"][0]
    assert community["qualified_window_count"] == 0
    assert community["remainder_word_count"] == 20
    assert community["windows"][0]["remainder"]


def test_WIN_12_targets_never_relabel_indices_as_same_boundaries():
    records = [feature(i) for i in range(32)]
    primary = pooled_comment(build_streams(records, CONFIG))
    large = pooled_comment(build_streams(records, CONFIG, target_words=2000))
    assert len(primary["windows"]) == 4
    assert len(large["windows"]) == 2
    assert primary["windows"][0]["last_record_position"] == 7
    assert large["windows"][0]["last_record_position"] == 15
    assert primary["windows"][0]["window_id"] != large["windows"][0]["window_id"]


def test_WIN_14_manual_selector_intersection_time_and_overlap():
    records = [feature(0), feature(1, kind="submission"), feature(2, subreddit="other"), feature(3, created_utc=None)]
    selected = select_records(records, {"start_utc": "2025-01-01T00:00:00Z", "end_utc": "2025-01-01T00:00:02Z"})
    assert [record["id"] for record in selected] == ["r0000", "r0001"]
    assert [record["id"] for record in select_records(records, {"ids": ["r0000", "r0001"], "kind": "submission"})] == ["r0001"]
    assert [record["id"] for record in select_records(records, {"ids": ["r0003"]})] == ["r0003"]
    assert select_records(records, {"ids": ["r0003"], "start_utc": "2025-01-01T00:00:00Z"}) == []
    assert [record["id"] for record in select_records(records, {"subreddit": "other"})] == ["r0002"]
    assert select_records(records, {"ids": []}) == []
    selection = {"schema_version": "1.0.0", "left": {"ids": ["r0000", "r0001"]}, "right": {"ids": ["r0001"]}}
    with pytest.raises(InputError, match="overlapping_comparison"):
        select_comparison(records, selection)
    left, right, dependent = select_comparison(records, {**selection, "allow_overlap": True})
    assert len(left) == 2 and len(right) == 1 and dependent is True
    _, _, dependent = select_comparison(records, {"schema_version": "1.0.0", "left": {"ids": ["r0000"]}, "right": {"ids": ["r0001"]}, "allow_overlap": True})
    assert dependent is False


def test_manual_selectors_reject_unknown_ids_fields_and_bad_intervals():
    records = [feature(0)]
    with pytest.raises(InputError, match="unknown_record_id"):
        select_records(records, {"ids": ["absent"]})
    with pytest.raises(InputError, match="schema_validation"):
        select_records(records, {"language": "en"})
    with pytest.raises(InputError, match="inverted_selection_interval"):
        select_records(records, {"start_utc": "2025-01-02T00:00:00Z", "end_utc": "2025-01-01T00:00:00Z"})
    assert select_records(records, {"start_utc": "2025-01-01T00:00:00Z", "end_utc": "2025-01-01T00:00:00Z"}) == []
    with pytest.raises(InputError, match="invalid_window_target"):
        build_streams(records, CONFIG, target_words=0)
    with pytest.raises(InputError, match="unknown_record_id"):
        build_streams(records, CONFIG, excluded_ids=["absent"])


def test_community_selection_volume_ties_and_unknown_scope():
    config = AnalysisConfig.from_mapping({"windows": {"max_community_streams": 2}})
    records = [feature(0, 50, subreddit="z"), feature(1, 50, subreddit="a"), feature(2, 50, subreddit=None), feature(3, 20, subreddit="b")]
    result = build_streams(records, config)
    selected = [stream for stream in result["streams"] if stream["scope_type"] == "community" and stream["kind"] == "comment"]
    assert [stream["subreddit"] for stream in selected] == [None, "a"]
    assert selected[0]["eligible_record_ids"] == ["r0002"]
    assert selected[1]["eligible_record_ids"] == ["r0001"]
    assert result["omitted_communities"] == [{"subreddit": "z", "eligible_words": 50}, {"subreddit": "b", "eligible_words": 20}]


def test_window_features_are_pooled_rates_and_input_not_mutated():
    config = AnalysisConfig.from_mapping({"style": {"minimum_record_words": 1}, "windows": {"target_words": 4, "minimum_records": 2}})
    records = [feature(0, text="word,", config=config), feature(1, text="word word word", config=config)]
    before = canonical_bytes(records)
    window = pooled_comment(build_streams(records, config))["windows"][0]
    assert window["features"]["rates"]["punctuation_per_1000_words"]["comma"] == 250
    assert canonical_bytes(records) == before
    assert canonical_bytes(build_streams(records, config)) == canonical_bytes(build_streams(list(reversed(records)), config))


@given(st.lists(st.integers(min_value=20, max_value=500), min_size=0, max_size=30))
@settings(max_examples=20, deadline=None)
def test_property_all_eligible_records_partition_once_and_guards(lengths):
    records = [feature(index, word_count) for index, word_count in enumerate(lengths)]
    stream = pooled_comment(build_streams(records, CONFIG))
    assert [identifier for window in stream["windows"] for identifier in window["record_ids"]] == [record["id"] for record in records]
    assert sum(window["word_count"] for window in stream["windows"]) == sum(lengths)
    for index, window in enumerate(stream["windows"]):
        assert window["qualified"] == (window["word_count"] >= 1000 and window["record_count"] >= 8)
        if not window["qualified"]:
            assert index == len(stream["windows"]) - 1
        if window["qualified"] and window["record_count"] > 8:
            last_index = int(window["record_ids"][-1][1:])
            assert window["word_count"] - lengths[last_index] < 1000
