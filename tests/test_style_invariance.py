"""Independent M3 invariance and real CLI selection contracts; no truth sidecars."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.features import extract_records
from account_history_analyzer.io import canonical_bytes, load_snapshot, thaw
from account_history_analyzer.style import chargrams, compare_features, feature_values

ROOT = Path(__file__).resolve().parents[1]
CONFIG = AnalysisConfig.from_toml()


def test_WIN_16_shipped_topic_substitution_preserves_designed_profiles():
    snapshot = load_snapshot(ROOT / "fixtures/constructed_topic_shift.jsonl", ROOT / "fixtures/constructed_topic_shift.snapshot.json")
    features = extract_records(snapshot, CONFIG)
    # Check the invariant across every supplied record, without reading a label,
    # boundary annotation, or truth sidecar and without changing configuration.
    assert len({tuple(record["masked_segments"]) for record in features}) == 1
    assert len({tuple(feature_values(record).items()) for record in features}) == 1
    assert all(record["function_counts"] == features[0]["function_counts"] for record in features)
    assert all(record["counts"] == features[0]["counts"] for record in features)
    left, right = features[0], features[-1]
    assert chargrams([segment["text"] for segment in left["segments"]], 4) != chargrams([segment["text"] for segment in right["segments"]], 4)
    comparison = compare_features([left], [right], CONFIG)
    assert comparison["status"] == "insufficient_data"
    assert all(distance["value"] == 0 for distance in comparison["distances"] if distance["view"] == "function_mask_v1")
    assert all(distance["value"] > 0 for distance in comparison["distances"] if distance["view"] == "retained_prose")
    assert next(distance for distance in comparison["distances"] if distance["method_id"] == "function_word_js_v1")["value"] == 0


def test_TXT_14_renamed_identifiers_accounts_and_paths_cannot_change_features(tmp_path):
    original = load_snapshot(ROOT / "fixtures/arithmetic.jsonl", ROOT / "fixtures/arithmetic.snapshot.json")
    rows = thaw(original.records)
    names = {row["id"]: f"arbitrary_identifier_{index}" for index, row in enumerate(rows)}
    for row in rows:
        row["id"] = names[row["id"]]
        row["account_id"] = "unrelated_account_label"
        if row["parent_id"] in names:
            row["parent_id"] = names[row["parent_id"]]
    manifest = thaw(original.manifest)
    manifest.update(account_id="unrelated_account_label", snapshot_id="unrelated_snapshot_label")
    records_path, manifest_path = tmp_path / "renamed_source.jsonl", tmp_path / "renamed_manifest.json"
    records_path.write_bytes(b"".join(canonical_bytes(row) for row in rows))
    manifest_path.write_bytes(canonical_bytes(manifest))
    renamed = load_snapshot(records_path, manifest_path)
    assert renamed.canonical_sha256 != original.canonical_sha256
    left, right = extract_records(original, CONFIG), extract_records(renamed, CONFIG)
    for before, after in zip(left, right, strict=True):
        for key in ("counts", "rates", "function_counts", "function_rates", "contractions", "tokens", "word_tokens", "masked_segments", "token_offsets"):
            assert before[key] == after[key]
        assert [segment["text"] for segment in before["segments"]] == [segment["text"] for segment in after["segments"]]
    assert canonical_bytes(compare_features(left[:3], left[3:], CONFIG)) == canonical_bytes(compare_features(right[:3], right[3:], CONFIG))


def test_OUT_11_comparison_numerics_are_invariant_to_record_permutation():
    snapshot = load_snapshot(ROOT / "fixtures/arithmetic.jsonl", ROOT / "fixtures/arithmetic.snapshot.json")
    features = extract_records(snapshot, CONFIG)
    result = compare_features(features[:3], features[3:], CONFIG)
    permuted = compare_features(list(reversed(features[:3])), list(reversed(features[3:])), CONFIG)
    assert canonical_bytes(result) == canonical_bytes(permuted)


def _compare_cli(tmp_path, selection, name, *, records_path=None, manifest_path=None):
    selection_path = tmp_path / (name + ".selection.json")
    selection_path.write_bytes(canonical_bytes({"schema_version": "1.0.0", **selection}))
    output = tmp_path / (name + "_output")
    command = [sys.executable, "-m", "account_history_analyzer", "compare",
               "--input", str(records_path or ROOT / "fixtures/arithmetic.jsonl"),
               "--manifest", str(manifest_path or ROOT / "fixtures/arithmetic.snapshot.json"),
               "--selection", str(selection_path), "--out", str(output)]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
    return completed, output


def test_WIN_14_CLI_refuses_overlap_unknown_ID_and_inverted_interval(tmp_path):
    cases = [
        ({"left": {"ids": ["arithmetic_001"]}, "right": {"ids": ["arithmetic_001"]}}, "overlapping_comparison"),
        ({"left": {"ids": ["absent"]}, "right": {"ids": ["arithmetic_001"]}}, "unknown_record_id"),
        ({"left": {"start_utc": "2025-01-02T00:00:00Z", "end_utc": "2025-01-01T00:00:00Z"}, "right": {"ids": []}}, "inverted_selection_interval"),
    ]
    for index, (selection, reason) in enumerate(cases):
        completed, output = _compare_cli(tmp_path, selection, f"invalid_{index}")
        assert completed.returncode == 2, completed.stderr
        assert reason in completed.stderr
        assert completed.stdout == ""
        assert not output.exists()


def test_WIN_14_CLI_time_end_exclusive_missing_time_and_explicit_overlap(tmp_path):
    original = load_snapshot(ROOT / "fixtures/arithmetic.jsonl", ROOT / "fixtures/arithmetic.snapshot.json")
    rows = thaw(original.records)
    rows.append({**rows[0], "id": "missing_time", "created_utc": None})
    records_path, manifest_path = tmp_path / "supplied.jsonl", tmp_path / "supplied.snapshot.json"
    records_path.write_bytes(b"".join(canonical_bytes(row) for row in rows))
    manifest_path.write_bytes(canonical_bytes(original.manifest))
    completed, output = _compare_cli(tmp_path, {
        "left": {"ids": ["arithmetic_001", "arithmetic_002", "missing_time"], "start_utc": "2025-01-01T00:00:00Z", "end_utc": "2025-01-01T00:00:10Z"},
        "right": {"ids": ["missing_time"]},
    }, "time_filter", records_path=records_path, manifest_path=manifest_path)
    assert completed.returncode == 0, completed.stderr
    result = json.loads((output / "results.json").read_text())
    comparison = result["modules"]["style"]["payload"]["comparisons"][-1]
    assert comparison["samples"]["left"]["record_count"] == 1
    assert comparison["samples"]["left"]["missing_timestamps"] == 0
    assert comparison["samples"]["right"]["record_count"] == 1
    assert comparison["samples"]["right"]["missing_timestamps"] == 1
    assert comparison["status"] == "insufficient_data"
    completed, output = _compare_cli(tmp_path, {"left": {"ids": ["arithmetic_001"]}, "right": {"ids": ["arithmetic_001"]}, "allow_overlap": True}, "diagnostic")
    assert completed.returncode == 0, completed.stderr
    result = json.loads((output / "results.json").read_text())
    comparison = result["modules"]["style"]["payload"]["comparisons"][-1]
    assert "overlapping_selection_dependent" in comparison["limitations"]
