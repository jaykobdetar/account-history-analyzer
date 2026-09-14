"""IN acceptance gates, independent calendar/hash properties, and regressions."""
from __future__ import annotations

import itertools
import json
import random
import socket
from pathlib import Path

import pytest

from account_history_analyzer.errors import InputError, IntegrityError, LimitError
from account_history_analyzer.io import canonical_bytes, digest, epoch_us, load_json, load_snapshot, parse_json, thaw
from account_history_analyzer.schemas import load_schema, validate

ROOT = Path(__file__).resolve().parents[1]


def record(identifier: str = "r1", **changes):
    return {"schema_version": "1.0.0", "id": identifier, "account_id": "a",
            "kind": "comment", "status": "present", "text": "source text", **changes}


def manifest(**changes):
    return {"schema_version": "1.0.0", "snapshot_id": "s", "account_id": "a",
            "source_category": "user_supplied", "text_format": "plain", "default_language": "und",
            "coverage": {"status": "unknown"}, **changes}


def write_snapshot(tmp_path, rows, supplied_manifest=None, config=None):
    input_path = tmp_path / "records.jsonl"
    manifest_path = tmp_path / "snapshot.json"
    input_path.write_bytes(b"".join(canonical_bytes(row) for row in rows))
    manifest_path.write_bytes(canonical_bytes(supplied_manifest or manifest()))
    return load_snapshot(input_path, manifest_path, config)


def test_IN_01_IN_03_arithmetic_deduplicates_after_expansion():
    snapshot = load_snapshot(ROOT / "fixtures/arithmetic.jsonl", ROOT / "fixtures/arithmetic.snapshot.json")
    assert snapshot.receipt["parsed_rows"] == 7
    assert snapshot.receipt["duplicate_rows"] == 1
    assert len(snapshot.records) == 6
    assert [epoch_us(r["created_utc"]) - epoch_us(snapshot.records[0]["created_utc"]) for r in snapshot.records] == [0, 10000000, 20000000, 60000000, 120000000, 180000000]


@pytest.mark.parametrize("bad", ['{', '{"a":1,"a":2}', '{"a":{"x":1,"x":2}}', 'NaN', 'Infinity', '-Infinity', '1e999', '\ufeff{}', b'"\xff"', '"\\ud800"'])
def test_IN_02_strict_json_rejects_invalid_and_nonfinite(bad):
    with pytest.raises(InputError):
        parse_json(bad)


def test_IN_03_default_expansion_precedes_duplicate_equality(tmp_path):
    first = record()
    expanded = {**first, "created_utc": None, "subreddit": None, "language": None, "edit_state": "unknown", "edited_utc": None, "title": None, "parent_id": None, "thread_id": None, "parent_created_utc": None, "permalink": None}
    snapshot = write_snapshot(tmp_path, [first, expanded])
    assert len(snapshot.records) == 1
    assert snapshot.receipt["duplicate_rows"] == 1
    assert dict(snapshot.records[0]) == expanded
    assert snapshot.manifest["coverage"]["known_gaps"] == ()
    assert snapshot.manifest["capture_utc"] is None


@pytest.mark.parametrize("difference", [{"text": "different"}, {"created_utc": "2025-01-01T00:00:00Z"}])
def test_IN_04_conflicting_record_is_error(tmp_path, difference):
    with pytest.raises(InputError, match="conflicting_record"):
        write_snapshot(tmp_path, [record(), record(**difference)])


def test_IN_05_distinct_ids_same_prose_are_two_events(tmp_path):
    assert len(write_snapshot(tmp_path, [record("r1"), record("r2")]).records) == 2


def test_IN_06_mixed_accounts_rejected(tmp_path):
    with pytest.raises(InputError, match="mixed_accounts"):
        write_snapshot(tmp_path, [record(), record("r2", account_id="other")])


def test_IN_07_unknown_record_and_manifest_keys_rejected(tmp_path):
    with pytest.raises(InputError, match="unexpected.*was unexpected|Additional properties"):
        write_snapshot(tmp_path, [record(unexpected="not a feature")])
    with pytest.raises(InputError, match="Additional properties"):
        write_snapshot(tmp_path, [], manifest(unexpected="no"))


@pytest.mark.parametrize("timestamp", ["2025-02-29T00:00:00Z", "2024-04-31T00:00:00Z", "2025-01-01T24:00:00Z", "2025-01-01T00:00:60Z", "2025-01-01T00:00:00", "2025-01-01T00:00:00+00:00", "2025-01-01T00:00:00.1234567Z", "２０２５-01-01T00:00:00Z"])
def test_IN_08_calendar_UTC_precision_validation(tmp_path, timestamp):
    with pytest.raises(InputError):
        write_snapshot(tmp_path, [record(created_utc=timestamp)])
    with pytest.raises(InputError):
        epoch_us(timestamp)


def test_IN_08_integer_epoch_handles_subseconds_leap_year_pre_epoch():
    assert epoch_us("1970-01-01T00:00:00Z") == 0
    assert epoch_us("1969-12-31T23:59:59.999999Z") == -1
    assert epoch_us("1970-01-01T00:00:00.000001Z") == 1
    assert epoch_us("2024-03-01T00:00:00Z") - epoch_us("2024-02-28T00:00:00Z") == 2 * 86400 * 1000000
    assert epoch_us("9999-12-31T23:59:59.999999Z") - epoch_us("9999-12-31T23:59:59.999998Z") == 1


def test_IN_09_missing_times_sort_last_keep_prose(tmp_path):
    snapshot = write_snapshot(tmp_path, [record("z"), record("b", created_utc="2025-01-01T00:00:00Z"), record("a"), record("c", created_utc="2025-01-01T00:00:00Z")])
    assert [r["id"] for r in snapshot.records] == ["b", "c", "a", "z"]
    assert all(r["text"] == "source text" for r in snapshot.records)


def test_IN_10_known_edit_order_and_unknown_timestamp(tmp_path):
    with pytest.raises(InputError, match="edit_before_creation"):
        write_snapshot(tmp_path, [record(created_utc="2025-01-02T00:00:00Z", edit_state="edited", edited_utc="2025-01-01T00:00:00Z")])
    snapshot = write_snapshot(tmp_path, [record(edit_state="edited")])
    assert snapshot.records[0]["edited_utc"] is None
    assert snapshot.warnings[0]["code"] == "known_edited_observed_text"
    with pytest.raises(InputError):
        write_snapshot(tmp_path, [record(edited_utc="2025-01-01T00:00:00Z")])


def test_IN_11_status_text_contradiction_and_preserved_sentinel(tmp_path):
    with pytest.raises(InputError):
        write_snapshot(tmp_path, [record(status="deleted")])
    with pytest.raises(InputError):
        write_snapshot(tmp_path, [record(text=None)])
    snapshot = write_snapshot(tmp_path, [record(text="  [deleted]  ")])
    assert snapshot.records[0]["text"] == "  [deleted]  "
    assert snapshot.warnings[0]["code"] == "removed_content_sentinel"
    assert len(write_snapshot(tmp_path, [record(status="removed", text=None)]).records) == 1


def test_IN_12_limits_return_code_four_without_truncation(tmp_path):
    with pytest.raises(LimitError, match="record_count_limit"):
        write_snapshot(tmp_path, [record("r1"), record("r2")], config={"input": {"max_unique_records": 1}})
    assert len(write_snapshot(tmp_path, [record(), record()], config={"input": {"max_unique_records": 1}}).records) == 1
    with pytest.raises(LimitError, match="text_size_limit"):
        write_snapshot(tmp_path, [record(text="ééé")], config={"input": {"max_text_codepoints": 2}})
    with pytest.raises(LimitError, match="input_byte_limit"):
        write_snapshot(tmp_path, [], config={"input": {"max_input_bytes": 1}})
    with pytest.raises(LimitError, match="text_size_limit"):
        write_snapshot(tmp_path, [record(text="a" * 200001)])
    assert LimitError.exit_code == 4
    assert InputError.exit_code == 2
    assert IntegrityError.exit_code == 5


def test_IN_13_empty_is_valid_snapshot(tmp_path):
    snapshot = write_snapshot(tmp_path, [])
    assert snapshot.records == ()
    assert snapshot.receipt["physical_lines"] == 0
    assert snapshot.receipt["parsed_rows"] == 0
    assert snapshot.warnings == ()


def test_IN_14_row_key_and_whitespace_permutations(tmp_path):
    rows = [record("missing"), record("a", created_utc="2025-01-01T00:00:00Z"), record("b", created_utc="2025-01-01T00:00:00Z")]
    expected = write_snapshot(tmp_path, rows).canonical_sha256
    raw_hashes = set()
    for permutation in itertools.permutations(rows):
        snapshot = write_snapshot(tmp_path, permutation)
        assert snapshot.canonical_sha256 == expected
        raw_hashes.add(snapshot.receipt["raw_input_sha256"])
    assert len(raw_hashes) == 6
    path = tmp_path / "records.jsonl"
    path.write_text("\n" + "\n".join(json.dumps(dict(reversed(list(r.items()))), separators=(", ", " : ")) for r in rows) + "\n\n", encoding="utf-8")
    assert load_snapshot(path, tmp_path / "snapshot.json").canonical_sha256 == expected


def test_IN_15_text_coverage_provenance_changes_identity(tmp_path):
    base = write_snapshot(tmp_path, [record()]).canonical_sha256
    assert write_snapshot(tmp_path, [record(text="different")]).canonical_sha256 != base
    assert write_snapshot(tmp_path, [record()], manifest(coverage={"status": "sampled"})).canonical_sha256 != base
    assert write_snapshot(tmp_path, [record()], manifest(source_notes="supplier statement")).canonical_sha256 != base


def test_schema_format_checker_and_strict_envelopes():
    validate(record(), "record")
    validate(manifest(), "snapshot")
    with pytest.raises(InputError):
        validate(record(created_utc="2025-02-31T00:00:00Z"), "record")
    with pytest.raises(InputError):
        load_schema("../record")


def test_canonical_json_definition_and_immutable_snapshot(tmp_path):
    assert canonical_bytes({"z": -0.0, "a": "é", "i": 1}) == '{"a":"é","i":1,"z":0.0}\n'.encode()
    with pytest.raises(ValueError):
        canonical_bytes({"a": float("nan")})
    snapshot = write_snapshot(tmp_path, [record()])
    with pytest.raises(TypeError):
        snapshot.records[0]["text"] = "changed"
    with pytest.raises(TypeError):
        snapshot.manifest["coverage"]["status"] = "sampled"
    copied = thaw(snapshot.manifest)
    copied["coverage"]["status"] = "sampled"
    assert snapshot.manifest["coverage"]["status"] == "unknown"


def test_known_coverage_intervals_and_gap_order(tmp_path):
    with pytest.raises(InputError, match="inverted_interval"):
        write_snapshot(tmp_path, [], manifest(coverage={"status": "unknown", "start_utc": "2025-01-02T00:00:00Z", "end_utc": "2025-01-01T00:00:00Z"}))
    with pytest.raises(InputError, match="inverted_interval"):
        write_snapshot(tmp_path, [], manifest(coverage={"status": "unknown", "known_gaps": [{"start_utc": "2025-01-02T00:00:00Z", "end_utc": "2025-01-01T00:00:00Z"}]}))


def test_parent_metadata_internal_contradictions_and_external_warning(tmp_path):
    parent = record("parent", created_utc="2025-01-01T00:00:10Z")
    child = record("child", created_utc="2025-01-01T00:00:00Z", parent_id="parent")
    with pytest.raises(InputError, match="internal_parent_after_child"):
        write_snapshot(tmp_path, [parent, child])
    with pytest.raises(InputError, match="internal_parent_timestamp_conflict"):
        write_snapshot(tmp_path, [parent, {**child, "parent_created_utc": "2025-01-01T00:00:11Z"}])
    snapshot = write_snapshot(tmp_path, [{**child, "parent_id": "absent", "parent_created_utc": "2025-01-01T00:00:10Z"}])
    assert snapshot.warnings[0]["code"] == "unverified_external_parent_after_child"


def test_parent_cycle_walk_is_iterative_and_deterministic(tmp_path):
    rows = [record("a", parent_id="b"), record("b", parent_id="c"), record("c", parent_id="a"), record("z", parent_id="z")]
    snapshot = write_snapshot(tmp_path, rows)
    assert [dict(w) for w in snapshot.warnings] == [{"code": "parent_reference_cycle", "source_record_ids": ("a", "b", "c")}, {"code": "parent_reference_cycle", "source_record_ids": ("z",)}]
    assert write_snapshot(tmp_path, reversed(rows)).warnings == snapshot.warnings
    chain = [record(str(i), parent_id=str(i + 1)) for i in range(2000)]
    assert write_snapshot(tmp_path, chain).warnings == ()


def test_future_checks_only_use_supplied_capture(tmp_path):
    future = record(created_utc="9999-01-01T00:00:00Z")
    assert write_snapshot(tmp_path, [future]).warnings == ()
    warnings = write_snapshot(tmp_path, [future], manifest(capture_utc="2025-01-01T00:00:00Z")).warnings
    assert warnings[0]["code"] == "created_after_supplied_capture"


def test_no_network_during_ingestion(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("network forbidden")
    monkeypatch.setattr(socket, "socket", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    assert len(write_snapshot(tmp_path, [record()]).records) == 1


def test_regression_literal_unicode_line_separator_is_source_text(tmp_path):
    # str.splitlines() would wrongly split valid JSON strings at U+2028/U+0085.
    text = "alpha\u2028beta\u0085gamma"
    snapshot = write_snapshot(tmp_path, [record(text=text)])
    assert snapshot.records[0]["text"] == text
    assert snapshot.receipt["physical_lines"] == 1


def test_property_canonical_key_order_preserves_unicode_and_integers():
    rng = random.Random(1842)
    items = [(f"key{i}", {"text": "é🐚–", "integer": rng.randrange(-10**30, 10**30)}) for i in range(30)]
    expected = digest(dict(items))
    for _ in range(100):
        rng.shuffle(items)
        assert digest(dict(items)) == expected
        assert parse_json(canonical_bytes(dict(items))) == dict(items)


def test_load_json_is_strict_and_filesystem_only(tmp_path):
    path = tmp_path / "malformed.json"
    path.write_text('{"duplicate": 1, "duplicate": 2}')
    with pytest.raises(InputError, match="duplicate_json_key"):
        load_json(path)
    with pytest.raises(InputError, match="input_file_error"):
        load_json("https://example.test/must-not-fetch")
