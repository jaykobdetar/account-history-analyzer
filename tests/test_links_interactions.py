"""LINK/INT observation scopes, hostname denominators and resource safeguards."""
from __future__ import annotations

from pathlib import Path

import pytest

from account_history_analyzer.activity import analyze_activity
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.errors import InputError, LimitError
from account_history_analyzer.features import extract_records
from account_history_analyzer.interactions import analyze_interactions
from account_history_analyzer.io import canonical_bytes, load_snapshot
from account_history_analyzer.links import analyze_links

ROOT = Path(__file__).resolve().parents[1]
CONFIG = AnalysisConfig.from_toml()


def supplied(tmp_path, changes, *, config=CONFIG):
    records = [{"schema_version": "1.0.0", "id": f"r{index}", "account_id": "a", "kind": "comment", "status": "present", "text": "source words", "created_utc": f"2025-01-01T00:00:{index:02}Z", "subreddit": "a", **change} for index, change in enumerate(changes)]
    manifest = {"schema_version": "1.0.0", "snapshot_id": "s", "account_id": "a", "source_category": "synthetic", "text_format": "markdown", "default_language": "en", "coverage": {"status": "unknown"}}
    records_path, manifest_path = tmp_path / "records.jsonl", tmp_path / "snapshot.json"
    records_path.write_bytes(b"".join(canonical_bytes(record) for record in records))
    manifest_path.write_bytes(canonical_bytes(manifest))
    snapshot = load_snapshot(records_path, manifest_path, config)
    return snapshot, extract_records(snapshot, config)


def test_LINK_01_INT_01_arithmetic_oracles():
    snapshot = load_snapshot(ROOT / "fixtures/arithmetic.jsonl", ROOT / "fixtures/arithmetic.snapshot.json")
    features = extract_records(snapshot, CONFIG)
    links = analyze_links(snapshot, features, [], CONFIG)
    summary = links["summary"]
    assert summary["record_count"] == 6
    assert summary["total_link_occurrences"] == summary["valid_http_occurrences"] == 2
    assert summary["distinct_hosts"] == 1
    host = summary["hosts"][0]
    assert host["hostname"] == "example.test"
    assert host["occurrences"] == 2 and host["record_count"] == 1
    assert host["share_of_records"] == 1 / 6 and host["share_of_valid_http_links"] == 1
    assert host["source_record_ids"] == ["arithmetic_005"]
    interactions = analyze_interactions(snapshot, CONFIG)
    difference = interactions["parent_differences"][0]
    assert difference["record_id"] == "arithmetic_004"
    assert difference["creation_to_parent_creation_seconds"] == 60
    assert difference["parent_time_source"] == "internal_record"
    assert "creation_to_parent_creation_is_not_typing_or_read_to_reply_time" in interactions["limitations"]


def test_LINK_02_repeated_occurrences_normalization_IDNA_and_www_distinct(tmp_path):
    snapshot, features = supplied(tmp_path, [
        {"text": "https://EXAMPLE.test./first https://example.test/second https://example.test/third"},
        {"text": "[notes](https://www.example.test/path) https://bücher.example/"},
        {"status": "removed", "text": None},
    ])
    result = analyze_links(snapshot, features, [], CONFIG)
    assert result["summary"]["total_link_occurrences"] == 5
    hosts = {host["hostname"]: host for host in result["summary"]["hosts"]}
    assert set(hosts) == {"example.test", "www.example.test", "xn--bcher-kva.example"}
    assert hosts["example.test"]["occurrences"] == 3
    assert hosts["example.test"]["record_count"] == 1
    assert hosts["example.test"]["share_of_records"] == 1 / 3
    assert hosts["example.test"]["share_of_valid_http_links"] == 3 / 5


def test_LINK_03_title_body_community_and_window_scopes(tmp_path):
    snapshot, features = supplied(tmp_path, [
        {"kind": "submission", "title": "[title source](https://title.test)", "text": "https://body.test https://body.test", "subreddit": None},
        {"text": "https://body.test", "subreddit": "other"},
    ])
    windows = [{"window_id": "one", "record_ids": ["r0"]}, {"window_id": "two", "record_ids": ["r1"]}]
    result = analyze_links(snapshot, features, windows, CONFIG)
    assert result["summary"]["total_link_occurrences"] == 4
    fields = {item["source_field"]: item["summary"] for item in result["by_field"]}
    assert fields["text"]["record_count"] == 2 and fields["text"]["total_link_occurrences"] == 3
    assert fields["title"]["record_count"] == 1 and fields["title"]["total_link_occurrences"] == 1
    assert result["by_community"][0]["subreddit"] is None
    assert result["by_community"][0]["summary"]["total_link_occurrences"] == 3
    assert result["by_window"][0]["summary"]["record_count"] == 1
    assert result["by_window"][0]["summary"]["total_link_occurrences"] == 3
    assert any(item["source_field"] == "title" and item["record_id"] == "r0" for item in result["occurrences"])


def test_LINK_04_malformed_unsafe_links_and_userinfo_safe_display(tmp_path):
    snapshot, features = supplied(tmp_path, [{"text": "https://user:secret@example.test/safe https://example.test:invalid/path [email](mailto:name@example.test)"}])
    result = analyze_links(snapshot, features, [], CONFIG)
    summary = result["summary"]
    assert summary["total_link_occurrences"] == 3
    assert summary["valid_http_occurrences"] == summary["malformed_occurrences"] == summary["unsafe_scheme_occurrences"] == 1
    assert all("secret" not in item["url"] and "user" not in item["url"] for item in result["occurrences"] if item["url"] is not None)
    assert all(item["url"] is None for item in result["occurrences"] if item["status"] != "ok")
    assert summary["hosts"][0]["share_of_valid_http_links"] == 1


def test_LINK_05_excluded_quote_and_code_links_are_observable_source_metadata(tmp_path):
    snapshot, features = supplied(tmp_path, [{"text": "> [quote](https://quote.test)\n\n```\nhttps://code.test\n```\n\nRetained prose."}])
    assert features[0]["counts"]["retained_words"] == 2
    result = analyze_links(snapshot, features, [], CONFIG)
    assert result["summary"]["total_link_occurrences"] == 2
    assert {host["hostname"] for host in result["summary"]["hosts"]} == {"quote.test", "code.test"}


def test_INT_02_thread_counts_parent_sources_missingness_and_label_transitions(tmp_path):
    snapshot, _ = supplied(tmp_path, [
        {"kind": "submission", "thread_id": "t", "created_utc": "2025-01-01T00:00:00Z"},
        {"parent_id": "r0", "thread_id": "t", "created_utc": "2025-01-01T00:00:10Z"},
        {"status": "removed", "text": None, "parent_id": "external", "parent_created_utc": "2025-01-01T00:00:30Z", "thread_id": "t", "created_utc": "2025-01-01T00:00:20Z", "subreddit": None},
        {"parent_id": "missing", "created_utc": None, "subreddit": "not_in_time_sequence"},
        {"parent_created_utc": "2025-01-01T00:00:00Z", "created_utc": "2025-01-01T00:00:40Z", "thread_id": "u", "subreddit": "b"},
    ])
    result = analyze_interactions(snapshot, CONFIG)
    assert result["supplied_reply_records"] == 3
    assert result["internal_parent_links"] == 1 and result["unresolved_parent_links"] == 2
    assert result["records_without_parent_id"] == 2 and result["records_without_thread_id"] == 1
    assert result["repeat_participation_thread_count"] == 1
    thread = result["threads"][0]
    assert thread["thread_id"] == "t" and thread["record_count"] == 3 and thread["reply_count"] == 2
    differences = {item["record_id"]: item for item in result["parent_differences"]}
    assert differences["r1"]["creation_to_parent_creation_seconds"] == 10
    assert differences["r2"]["creation_to_parent_creation_seconds"] == -10
    assert differences["r2"]["status"] == "negative_unverified_metadata"
    assert differences["r3"]["creation_to_parent_creation_seconds"] is None
    assert differences["r3"]["status"] == "missing_timestamps"
    assert differences["r4"]["parent_time_source"] == "supplied_parent_metadata"
    assert result["parent_difference_available_count"] == 3
    assert result["negative_unverified_difference_count"] == 1
    sequence = result["community_sequence"]
    assert sequence["timestamped_record_count"] == 4 and sequence["adjacent_pairs"] == 3
    assert sequence["changed_label_count"] == 2
    assert all("r3" not in (item["left_record_id"], item["right_record_id"]) for item in sequence["transitions"])


def test_INT_03_cycles_are_counted_without_recursive_inference(tmp_path):
    snapshot, _ = supplied(tmp_path, [{"parent_id": "r1", "created_utc": None}, {"parent_id": "r0", "created_utc": None}])
    result = analyze_interactions(snapshot, CONFIG)
    assert result["parent_cycles"] == [{"source_record_ids": ["r0", "r1"]}]
    assert result["internal_parent_links"] == 2
    assert result["parent_difference_available_count"] == 0
    assert result["community_sequence"]["adjacent_pairs"] == 0


def test_INT_04_verified_internal_parent_contradiction_still_rejected(tmp_path):
    with pytest.raises(InputError, match="internal_parent_after_child"):
        supplied(tmp_path, [{"created_utc": "2025-01-01T00:00:10Z"}, {"parent_id": "r0", "created_utc": "2025-01-01T00:00:00Z"}])


def test_LINK_INT_empty_scope_preserves_missing_denominators(tmp_path):
    snapshot, features = supplied(tmp_path, [])
    links = analyze_links(snapshot, features, [], CONFIG)
    assert links["summary"]["share_records_with_valid_links"] is None
    assert links["summary"]["hosts"] == []
    assert all(item["summary"]["share_records_with_valid_links"] is None for item in links["by_field"])
    interactions = analyze_interactions(snapshot, CONFIG)
    assert interactions["record_count"] == 0
    assert interactions["parent_differences"] == interactions["threads"] == []


def test_ACT_11_calendar_guard_rejects_huge_legal_range_before_allocation(tmp_path):
    snapshot, _ = supplied(tmp_path, [{"created_utc": "0001-01-01T00:00:00Z"}, {"created_utc": "9999-12-31T23:59:59Z"}])
    with pytest.raises(LimitError, match="activity_calendar_day_limit") as error:
        analyze_activity(snapshot, CONFIG)
    assert error.value.exit_code == 4
    config = AnalysisConfig.from_mapping({"activity": {"max_calendar_days": 3}})
    snapshot, _ = supplied(tmp_path, [{"created_utc": "2025-01-01T00:00:00Z"}, {"created_utc": "2025-01-03T00:00:00Z"}], config=config)
    assert analyze_activity(snapshot, config)["day_count"] == 3
    snapshot, _ = supplied(tmp_path, [{"created_utc": "2025-01-01T00:00:00Z"}, {"created_utc": "2025-01-04T00:00:00Z"}], config=config)
    with pytest.raises(LimitError, match="activity_calendar_day_limit"):
        analyze_activity(snapshot, config)
