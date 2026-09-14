"""SCH: external contracts reject malformed module payloads recursively."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from account_history_analyzer.payload_schemas import change_schema, evidence_schema, module_payloads, records_features_schema, style_stream_schema, tighten_config, tighten_results, windows_schema
from account_history_analyzer.errors import InputError
from account_history_analyzer.schemas import load_schema, validate

ROOT = Path(__file__).resolve().parents[1]


def test_sch01_installed_and_source_contracts_agree():
    for source in sorted((ROOT / "schemas").glob("*.schema.json")):
        assert load_schema(source.name) == json.loads(source.read_text(encoding="utf-8"))


def test_sch02_module_contracts_are_generated_and_valid():
    source = load_schema("results")
    assert tighten_results(source, load_schema("snapshot")) == source
    Draft202012Validator.check_schema(source)
    assert records_features_schema() == load_schema("records_features")
    assert evidence_schema() == load_schema("evidence")
    assert tighten_config(load_schema("config")) == load_schema("config")
    assert windows_schema() == load_schema("windows")


def test_sch03_no_generic_module_object_slots():
    def inspect(value):
        if isinstance(value, dict):
            if value.get("type") == "object":
                assert value.get("additionalProperties") is False or isinstance(value.get("additionalProperties"), dict)
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)
    for schema in module_payloads(load_schema("snapshot")).values():
        inspect(schema)


@pytest.mark.parametrize("module", ["coverage", "text", "activity", "reuse", "style", "links", "interactions", "ai_text_detection"])
def test_sch04_arbitrary_module_fields_rejected(module):
    schema = module_payloads(load_schema("snapshot"))[module]
    assert not Draft202012Validator(schema).is_valid({"unknown_untyped_result": 0})


def coverage_payload():
    return {
        "unique_records": 0,
        "status_counts": {"present": 0, "deleted": 0, "removed": 0, "unavailable": 0},
        "missing_timestamps": 0, "usable_body_records": 0, "eligible_style_records": 0,
        "declared_coverage": {"status": "unknown", "start_utc": None, "end_utc": None, "known_gaps": [], "notes": ""},
        "warnings": [], "languages": [], "kinds": {"comment": 0, "submission": 0},
    }


def test_sch05_coverage_counts_and_expansion_contract():
    validator = Draft202012Validator(module_payloads(load_schema("snapshot"))["coverage"])
    correct = coverage_payload()
    assert validator.is_valid(correct)
    for replacement in (-1, 0.5, None, "0", True):
        candidate = deepcopy(correct)
        candidate["unique_records"] = replacement
        assert not validator.is_valid(candidate)
    for where, field in (("status_counts", "present"), ("declared_coverage", "known_gaps")):
        candidate = deepcopy(correct)
        del candidate[where][field]
        assert not validator.is_valid(candidate)
    candidate = deepcopy(correct)
    candidate["status_counts"]["unknown"] = 0
    assert not validator.is_valid(candidate)


def test_sch06_supplier_coverage_timestamp_formats_checked():
    candidate = json.loads((ROOT / "fixtures" / "arithmetic.snapshot.json").read_text(encoding="utf-8"))
    candidate["coverage"]["start_utc"] = "2026-02-30T00:00:00Z"
    with pytest.raises(InputError, match="date-time"):
        validate(candidate, "snapshot")


def test_sch07_ai_capability_is_reserved_and_explicit():
    validator = Draft202012Validator(module_payloads(load_schema("snapshot"))["ai_text_detection"])
    assert validator.is_valid({"capability": "not_implemented_in_v1"})
    assert not validator.is_valid({"capability": "low_risk"})
    assert not validator.is_valid({"capability": "not_implemented_in_v1", "probability": 0})


@pytest.mark.parametrize("fixture", ["arithmetic", "empty", "edge_cases"])
def test_sch08_actual_analysis_matches_external_contract(fixture):
    from account_history_analyzer.io import load_snapshot, thaw
    from account_history_analyzer.pipeline import analyze
    snapshot = load_snapshot(ROOT / "fixtures" / f"{fixture}.jsonl", ROOT / "fixtures" / f"{fixture}.snapshot.json")
    result = thaw(analyze(snapshot).results)
    validate(result, "results")
    # Exercise actual nested payloads, not only an invented schema-shaped object.
    for module, path in (
        ("text", ("body", "rates")),
        ("activity", ("gap_summary",)),
        ("coverage", ("status_counts",)),
    ):
        malformed = deepcopy(result)
        target = malformed["modules"][module]["payload"]
        for key in path:
            target = target[key]
        target["invented_probability"] = 0.5
        with pytest.raises(InputError, match="Additional properties"):
            validate(malformed, "results")


@pytest.mark.parametrize("fixture", ["arithmetic", "edge_cases"])
def test_sch09_record_feature_export_contract(fixture):
    from account_history_analyzer.config import AnalysisConfig
    from account_history_analyzer.features import extract_records
    from account_history_analyzer.io import load_snapshot, thaw
    snapshot = load_snapshot(ROOT / "fixtures" / f"{fixture}.jsonl", ROOT / "fixtures" / f"{fixture}.snapshot.json")
    for feature in extract_records(snapshot, AnalysisConfig.from_toml()):
        validate(feature, "records_features")
        candidate = thaw(feature)
        candidate["counts"]["invented_score"] = 0
        with pytest.raises(InputError, match="Additional properties"):
            validate(candidate, "records_features")


def test_sch10_evidence_offsets_have_unambiguous_representation():
    from account_history_analyzer.findings import evidence_object
    normalized = evidence_object("source-id", "alpha beta", segment_index=0, start=6, end=10)
    validate(normalized, "evidence")
    assert normalized["text"] == "beta"
    malformed = dict(normalized, offset_basis="raw_source")
    with pytest.raises(InputError):
        validate(malformed, "evidence")
    raw = evidence_object("source-id", "alpha beta", representation="raw_source", start=0, end=5)
    validate(raw, "evidence")
    with pytest.raises(InputError):
        validate(dict(raw, start=-1), "evidence")


def test_sch11_evidence_and_finding_references_resolve_to_actual_slices():
    from account_history_analyzer.config import AnalysisConfig
    from account_history_analyzer.features import extract_records
    from account_history_analyzer.findings import context_evidence, finding, validate_references
    from account_history_analyzer.io import load_snapshot
    snapshot = load_snapshot(ROOT / "fixtures" / "arithmetic.jsonl", ROOT / "fixtures" / "arithmetic.snapshot.json")
    features = extract_records(snapshot, AnalysisConfig.from_toml())
    evidence = context_evidence(features[0])
    validate(evidence, "evidence")
    observation = finding("text_measurement", method="retained_prose_v1", scope={}, values={},
                          records=[features[0]["id"]], evidence=[evidence["evidence_id"]])
    validate_references([observation], [evidence], features, [], snapshot)
    with pytest.raises(ValueError, match="actual source slice"):
        validate_references([observation], [dict(evidence, text="invented source words")], features, [], snapshot)
    with pytest.raises(ValueError, match="absent source"):
        validate_references([observation], [dict(evidence, source_record_id="missing-source")], features, [], snapshot)
    with pytest.raises(ValueError, match="absent evidence"):
        validate_references([dict(observation, evidence_refs=["missing-evidence"])], [evidence], features, [], snapshot)
    with pytest.raises(ValueError, match="absent source/window"):
        validate_references([dict(observation, window_ids=["missing-window"])], [evidence], features, [], snapshot)


@pytest.mark.parametrize("budget", [0, 100])
def test_sch12_reuse_edges_evidence_and_resource_limit_contracts(budget):
    from account_history_analyzer.config import AnalysisConfig
    from account_history_analyzer.io import load_snapshot, thaw
    from account_history_analyzer.pipeline import analyze
    snapshot = load_snapshot(ROOT / "fixtures" / "arithmetic.jsonl", ROOT / "fixtures" / "arithmetic.snapshot.json")
    config = AnalysisConfig.from_mapping({"reuse": {
        "minimum_near_duplicate_words": 1, "minimum_containment_shorter_words": 1,
        "max_candidate_pairs": budget,
    }})
    analysis = analyze(snapshot, config)
    result = thaw(analysis.results)
    validate(result, "results")
    payload = result["modules"]["reuse"]["payload"]
    assert payload["exact_groups"]
    evidence = [json.loads(line) for line in analysis.files["evidence.jsonl"].splitlines()]
    for item in evidence:
        validate(item, "evidence")
    assert evidence
    if budget:
        assert payload["pairs"]
        assert analysis.exit_code == 0
        payload["pairs"][0]["jaccard"] = 1.1
    else:
        assert analysis.exit_code == 4
        assert payload["pairs"] == []
        assert payload["near_status"] == "resource_limit"
        payload["candidate_count_is_lower_bound"] = False
    with pytest.raises(InputError):
        validate(result, "results")


@pytest.mark.parametrize("overrides", [
    {"ai_text_detection": {"enabled": True}},
    {"input": {"strict": False}},
    {"text": {"normalization": "NFKC"}},
    {"activity": {"timezone": "EST"}},
    {"changes": {"jump": 5}},
    {"style": {"ngram_lengths": [5, 3]}},
    {"style": {"views": ["embedding"]}},
    {"report": {"excerpts": "anonymous"}},
    {"report": {"remote_assets": True}},
    {"report": {"maximum_feature_explanations": 11}},
    {"reuse": {"near_threshold_denominator": 0}},
])
def test_sch13_unsupported_method_overrides_fail_external_contract(overrides):
    with pytest.raises(InputError):
        validate(overrides, "config")


def test_sch14_actual_window_artifacts_and_stream_references():
    from account_history_analyzer.config import AnalysisConfig
    from account_history_analyzer.features import extract_records
    from account_history_analyzer.io import load_snapshot
    from account_history_analyzer.windows import build_streams
    snapshot = load_snapshot(ROOT / "fixtures" / "arithmetic.jsonl", ROOT / "fixtures" / "arithmetic.snapshot.json")
    config = AnalysisConfig.from_mapping({
        "style": {"minimum_record_words": 1},
        "windows": {"target_words": 20, "minimum_records": 2},
    })
    built = build_streams(extract_records(snapshot, config), config)
    validator = Draft202012Validator(style_stream_schema())
    windows = []
    for stream in built["streams"]:
        for window in stream["windows"]:
            validate(window, "windows")
            windows.append(window)
        metadata = {key: value for key, value in stream.items() if key != "windows"}
        metadata["window_ids"] = [window["window_id"] for window in stream["windows"]]
        assert validator.is_valid(metadata)
        assert not validator.is_valid(dict(metadata, future_prediction=0))
    assert windows
    invalid = deepcopy(windows[0])
    invalid["features"]["rates"]["risk"] = 0
    with pytest.raises(InputError):
        validate(invalid, "windows")


@pytest.mark.parametrize("manual", [False, True])
def test_sch15_actual_style_comparisons_and_export_references(manual):
    from account_history_analyzer.config import AnalysisConfig
    from account_history_analyzer.io import load_snapshot, thaw
    from account_history_analyzer.pipeline import analyze
    snapshot = load_snapshot(ROOT / "fixtures" / "arithmetic.jsonl", ROOT / "fixtures" / "arithmetic.snapshot.json")
    ids = [record["id"] for record in snapshot.records]
    selection = {"schema_version": "1.0.0", "left": {"ids": ids[:3]}, "right": {"ids": ids[3:]}} if manual else None
    config = AnalysisConfig.from_mapping({
        "style": {"minimum_record_words": 1, "minimum_comparison_words_per_side": 10, "minimum_comparison_records_per_side": 2},
        "windows": {"target_words": 10, "minimum_records": 2},
    })
    analysis = analyze(snapshot, config, selection=selection)
    result = thaw(analysis.results)
    validate(result, "results")
    payload = result["modules"]["style"]["payload"]
    assert payload["comparisons"]
    assert (payload["manual_selection"] is not None) == manual
    windows = [json.loads(line) for line in analysis.files["windows.jsonl"].splitlines()]
    window_ids = {window["window_id"] for window in windows}
    assert len(window_ids) == len(windows)
    for window in windows:
        validate(window, "windows")
        assert set(window["record_ids"]) <= set(ids)
    for stream in payload["streams"]:
        assert set(stream["window_ids"]) <= window_ids
    for comparison in payload["comparisons"]:
        for side in ("left", "right"):
            assert comparison[side + "_window_id"] is None or comparison[side + "_window_id"] in window_ids
    for line in analysis.files["evidence.jsonl"].splitlines():
        validate(json.loads(line), "evidence")
    fabricated_zero = deepcopy(result)
    missing_distance = next(distance for distance in fabricated_zero["modules"]["style"]["payload"]["comparisons"][0]["distances"] if distance["status"] != "ok")
    missing_distance["value"] = 0
    with pytest.raises(InputError):
        validate(fabricated_zero, "results")
    payload["comparisons"][0]["distances"][0]["hidden_probability"] = 0
    with pytest.raises(InputError):
        validate(result, "results")


@pytest.mark.parametrize("case", ["varying", "constant", "short"])
def test_sch16_change_result_states_and_internal_boundary_objective(tmp_path, case):
    from datetime import datetime, timedelta, timezone
    from account_history_analyzer.changepoints import analyze_changes
    from account_history_analyzer.config import AnalysisConfig
    from account_history_analyzer.features import extract_records
    from account_history_analyzer.io import load_snapshot
    from account_history_analyzer.windows import build_streams
    base = datetime(2025, 1, 1, tzinfo=timezone.utc)
    text = "the trees and the grass are green while the flowers grow near the quiet path and the calm water."
    records = []
    for index in range(56 if case == "short" else 64):
        records.append({
            "schema_version": "1.0.0", "id": str(index), "account_id": "schema-sample", "kind": "comment",
            "status": "present", "text": text.upper() if case == "varying" and index >= 32 else text,
            "created_utc": (base + timedelta(seconds=index)).isoformat().replace("+00:00", "Z"),
        })
    input_path, manifest_path = tmp_path / "records.jsonl", tmp_path / "manifest.json"
    input_path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    manifest_path.write_text(json.dumps({
        "schema_version": "1.0.0", "snapshot_id": "schema-snapshot", "account_id": "schema-sample",
        "source_category": "synthetic", "text_format": "plain", "default_language": "en", "coverage": {"status": "unknown"},
    }), encoding="utf-8")
    snapshot = load_snapshot(input_path, manifest_path)
    config = AnalysisConfig.from_mapping({"windows": {"target_words": 20, "minimum_records": 8}, "style": {"minimum_record_words": 1}})
    built = build_streams(extract_records(snapshot, config), config)
    stream = built["streams"][0]
    result = analyze_changes(stream, stream["windows"], config)
    validator = Draft202012Validator(change_schema())
    assert validator.is_valid(result), list(validator.iter_errors(result))
    if case == "varying":
        assert result["status"] == "ok"
        assert result["internal_boundaries"] == [4]
        assert len(result["window_ids"]) not in result["internal_boundaries"]
        assert result["objective"] == pytest.approx(result["sse"] + result["penalty_beta"] * len(result["internal_boundaries"]))
        assert result["boundaries"][0]["left_record_id"] == stream["windows"][3]["last_record_id"]
        assert result["boundaries"][0]["right_record_id"] == stream["windows"][4]["first_record_id"]
        # Exercise populated sensitivity payloads without an unrelated quadratic
        # reuse table for these deliberately repeated arithmetic source strings.
        from account_history_analyzer.pipeline import analyze
        from account_history_analyzer.io import thaw
        pipeline_config = config.with_overrides({"reuse": {"minimum_near_duplicate_words": 1000, "minimum_containment_shorter_words": 1000}})
        analysis = analyze(snapshot, pipeline_config)
        canonical = thaw(analysis.results)
        validate(canonical, "results")
        sensitivity = canonical["modules"]["style"]["payload"]["sensitivity"]
        assert sensitivity["interpretation"] == "parameter_stability_not_confidence"
        assert len(sensitivity["penalty_settings"]) == 4
        for summary in sensitivity["same_window_stability"]:
            executed = [setting for setting in summary["settings"] if setting["status"] in {"ok", "no_measurable_variation"}]
            assert summary["executed_setting_count"] == len(executed)
            for candidate in summary["boundaries"]:
                assert candidate["matched_in_k_of_m_executed_settings"] == len(candidate["matched_setting_ids"])
                assert candidate["matched_in_k_of_m_executed_settings"] <= candidate["executed_setting_count"]
        all_windows = [json.loads(line) for line in analysis.files["windows.jsonl"].splitlines()]
        window_ids = {window["window_id"] for window in all_windows}
        assert len(window_ids) == len(all_windows)
        for setting in sensitivity["construction_settings"]:
            for alternate_stream in setting["streams"]:
                assert set(alternate_stream["window_ids"]) <= window_ids
    else:
        assert result["status"] == ("no_measurable_variation" if case == "constant" else "insufficient_data")
        assert result["objective"] is None
        assert not validator.is_valid(dict(result, objective=0))


def test_sch17_link_host_and_interaction_references_are_actual_sources():
    from account_history_analyzer.config import AnalysisConfig
    from account_history_analyzer.features import extract_records
    from account_history_analyzer.interactions import analyze_interactions
    from account_history_analyzer.io import load_snapshot
    from account_history_analyzer.links import analyze_links
    from account_history_analyzer.windows import build_streams
    snapshot = load_snapshot(ROOT / "fixtures" / "arithmetic.jsonl", ROOT / "fixtures" / "arithmetic.snapshot.json")
    config = AnalysisConfig.from_mapping({"style": {"minimum_record_words": 1}, "windows": {"target_words": 10, "minimum_records": 2}})
    features = extract_records(snapshot, config)
    windows = [window for stream in build_streams(features, config)["streams"] for window in stream["windows"]]
    links = analyze_links(snapshot, features, windows, config)
    interactions = analyze_interactions(snapshot, config)
    payloads = module_payloads(load_schema("snapshot"))
    assert Draft202012Validator(payloads["links"]).is_valid(links)
    assert Draft202012Validator(payloads["interactions"]).is_valid(interactions)
    record_ids = {record["id"] for record in snapshot.records}
    window_ids = {window["window_id"] for window in windows}
    assert {item["window_id"] for item in links["by_window"]} == window_ids
    for occurrence in links["occurrences"]:
        assert occurrence["record_id"] in record_ids
    for host in links["summary"]["hosts"]:
        assert set(host["source_record_ids"]) <= record_ids
    host = next(item for item in links["summary"]["hosts"] if item["hostname"] == "example.test")
    assert (host["occurrences"], host["record_count"]) == (2, 1)
    for difference in interactions["parent_differences"]:
        assert difference["record_id"] in record_ids
        if difference["parent_time_source"] == "internal_record":
            assert difference["parent_id"] in record_ids
    for transition in interactions["community_sequence"]["transitions"]:
        assert {transition["left_record_id"], transition["right_record_id"]} <= record_ids
    assert interactions["parent_differences"][0]["creation_to_parent_creation_seconds"] == 60
