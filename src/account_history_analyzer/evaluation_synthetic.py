"""Evaluator-only construction facts and low-level numerical oracle checks.

The analyzer receives only records, their manifest, and configuration. This
module reads truth sidecars after each analysis and checks already exported
measurements; labels never select analyzer features, windows, or parameters.
Passing these engineering checks does not establish external validity.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .config import AnalysisConfig
from .errors import InputError
from .io import canonical_bytes, digest, load_json, load_snapshot, sha256_bytes, thaw
from .pipeline import analyze, implementation_identity

TOLERANCE = 1e-12
SHIPPED_CASES = {"arithmetic", "constructed_style_shift", "constructed_topic_shift",
                 "stable_constructed_style", "edge_cases", "empty"}


def _equivalent(expected: Any, observed: Any, tolerance: float | None) -> bool:
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return (isinstance(observed, (int, float)) and not isinstance(observed, bool)
                and (math.isclose(expected, observed, rel_tol=0, abs_tol=tolerance)
                     if tolerance is not None else expected == observed))
    if isinstance(expected, dict):
        return isinstance(observed, dict) and expected.keys() == observed.keys() and all(
            _equivalent(expected[key], observed[key], tolerance) for key in expected)
    if isinstance(expected, list):
        return isinstance(observed, list) and len(expected) == len(observed) and all(
            _equivalent(a, b, tolerance) for a, b in zip(expected, observed, strict=True))
    return type(expected) is type(observed) and expected == observed


def _check(check_id: str, expected: Any, observed: Any, *, level: str = "numerical_correctness",
           tolerance: float | None = None, skip: str | None = None) -> dict[str, Any]:
    return {"check_id": check_id,
            "status": "not_evaluated" if skip else "passed" if _equivalent(expected, observed, tolerance) else "failed",
            "evidence_level": level, "expected": expected, "observed": observed,
            "tolerance": tolerance, "reason": skip}


def numerical_checks(oracles: dict[str, Any]) -> list[dict[str, Any]]:
    """Execute supplied hand-checkable oracles below product sample guards.

    The toy Delta reference is constructed from the explicit numerical oracle,
    used only by this evaluator with a test override, and never passed to an
    account analysis. Absolute tolerance is 1e-12 for floating-point values.
    """
    from .changepoints import pelt_l2
    from .reuse import shingle_set, shingle_metrics
    from .style import classic_delta, cosine_distance, jensen_shannon
    checks = []
    try:
        for index, oracle in enumerate(oracles["cosine"]):
            checks.append(_check(f"cosine_{index}", oracle["expected_distance"],
                                 cosine_distance(oracle["x"], oracle["y"]), tolerance=TOLERANCE))
        for index, oracle in enumerate(oracles["jensen_shannon_base_2_distance"]):
            checks.append(_check(f"jensen_shannon_{index}", oracle["expected_distance"],
                                 jensen_shannon(oracle["p"], oracle["q"]), tolerance=TOLERANCE))
        checks.extend([_check("cosine_zero_norm_abstention", None, cosine_distance([0, 0], [1, 0])),
                       _check("jensen_shannon_zero_mass_abstention", None, jensen_shannon([0, 0], [1, 0]))])
        oracle = oracles["shingles"]
        actual = shingle_metrics(shingle_set([oracle["tokens_a"]], oracle["n"]),
                                 shingle_set([oracle["tokens_b"]], oracle["n"]))
        for expected_key, actual_key in (("set_size_a", "left_shingles"), ("set_size_b", "right_shingles"),
                ("intersection", "intersection"), ("union", "union"), ("jaccard", "jaccard"),
                ("containment_a_in_b", "left_in_right"), ("containment_b_in_a", "right_in_left")):
            checks.append(_check("shingles_" + expected_key, oracle[expected_key], actual[actual_key], tolerance=TOLERANCE))
        checks.append(_check("empty_shingles_abstention", None, shingle_metrics(set(), set())["jaccard"]))
        oracle = oracles["delta"]
        reference = {"schema_version": "1.0.0", "reference_id": "evaluator_hand_arithmetic",
                     "reference_kind": "toy", "method_id": "classic_delta_v1",
                     "frequency_unit": "per_1000_word_tokens", "vocabulary": oracle["vocabulary"],
                     "means": oracle["means"], "standard_deviations": oracle["stds"],
                     "fitting_description": "Explicit hand-checkable constants; no reference fitting.",
                     "source_provenance": "Supplied local numerical_oracles.json; evaluator only."}
        actual = classic_delta(oracle["frequency_a"], oracle["frequency_b"], reference, allow_toy_reference=True)
        checks.append(_check("classic_delta_toy_arithmetic", oracle["expected_delta"], actual["value"], tolerance=TOLERANCE))
        oracle = oracles["pelt_unscaled_l2"]
        actual = pelt_l2(oracle["series"], oracle["penalty_per_internal_change"], min_size=oracle["minimum_segment_size"])
        checks.append(_check("pelt_internal_boundaries", oracle["expected_internal_boundaries"], actual["internal_boundaries"]))
        checks.append(_check("pelt_objective", oracle["optimal_objective"], actual["objective"], tolerance=TOLERANCE))
        # A forced single legal segment computes the no-change cost through the
        # same public primitive with independent oracle expectation.
        whole = pelt_l2(oracle["series"], oracle["penalty_per_internal_change"], min_size=len(oracle["series"]))
        checks.append(_check("pelt_no_change_objective", oracle["no_change_objective"], whole["objective"], tolerance=TOLERANCE))
        checks.append(_check("pelt_terminal_endpoint_is_not_change", len(oracle["series"]), actual["endpoints"][-1]))
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        raise InputError("Malformed numerical oracle structure", code="invalid_numerical_oracles") from exc
    return checks


def _inventory(directory: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[str], str]:
    index_path = directory / "fixture_index.json"
    if index_path.is_symlink():
        raise InputError("Fixture index must be an ordinary local file", code="invalid_fixture_index")
    index = load_json(index_path)
    if not isinstance(index, dict) or set(index) != {"fixture_version", "files"} or not isinstance(index["fixture_version"], str) or not isinstance(index["files"], list):
        raise InputError("Expected a fixture version and indexed files", code="invalid_fixture_index")
    inventory = []
    names = set()
    for item in index["files"]:
        if (not isinstance(item, dict) or set(item) != {"file", "bytes", "sha256"}
                or not isinstance(item["file"], str) or not item["file"]
                or Path(item["file"]).name != item["file"] or "\\" in item["file"]
                or item["file"] in {".", ".."} or item["file"] in names
                or type(item["bytes"]) is not int or item["bytes"] < 0
                or not isinstance(item["sha256"], str) or len(item["sha256"]) != 64
                or any(char not in "0123456789abcdef" for char in item["sha256"])):
            raise InputError("Invalid or duplicate fixture file entry", code="invalid_fixture_index")
        path = directory / item["file"]
        if path.is_symlink() or not path.is_file():
            raise InputError("Indexed fixture file is absent or a symlink", code="missing_fixture_file", location=item["file"])
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise InputError("Cannot read indexed fixture file", code="unreadable_fixture_file", location=item["file"]) from exc
        actual_hash = sha256_bytes(data)
        inventory.append({"file": item["file"], "bytes": len(data), "sha256": actual_hash,
                          "index_matches": len(data) == item["bytes"] and actual_hash == item["sha256"]})
        names.add(item["file"])
    cases = sorted(name[:-6] for name in names if name.endswith(".jsonl"))
    if not cases or "numerical_oracles.json" not in names:
        raise InputError("Fixture index needs histories and numerical_oracles.json", code="incomplete_fixture_index")
    for case in cases:
        if not {case + ".snapshot.json", case + ".truth.json"} <= names:
            raise InputError("Each indexed history needs indexed manifest and truth files", code="incomplete_fixture_index", location=case)
    return index, sorted(inventory, key=lambda item: item["file"]), cases, sha256_bytes(index_path.read_bytes())


def _arithmetic(truth: dict, result: dict, features: list[dict], receipt: dict, config: AnalysisConfig) -> list[dict]:
    mods = {key: value["payload"] for key, value in result["modules"].items()}
    activity, body = mods["activity"], mods["text"]["body"]
    checks = []
    for expected, observed in (("raw_input_lines", receipt["parsed_rows"]),
            ("ingestion_duplicate_records", receipt["duplicate_rows"]), ("unique_events", activity["event_count"]),
            ("retained_word_count_total", body["counts"]["retained_words"]),
            ("retained_word_counts_by_unique_record", {r["id"]: r["counts"]["retained_words"] for r in features}),
            ("inter_event_gaps_seconds", [gap["seconds"] for gap in activity["gaps"]]),
            ("gap_mean_seconds", activity["gap_summary"]["mean"]),
            ("gap_population_variance_seconds_squared", activity["gap_summary"]["population_variance_seconds_squared"]),
            ("gap_coefficient_of_variation", activity["gap_summary"]["coefficient_of_variation"]),
            ("gap_quantiles_seconds", {"0.25": activity["gap_summary"]["q25"], "0.5": activity["gap_summary"]["median"], "0.75": activity["gap_summary"]["q75"]})):
        checks.append(_check(expected, truth[expected], observed, tolerance=TOLERANCE))
    sliding = {str(item["duration_seconds"]): item["maximum_events"] for item in activity["maximum_sliding_windows"]}
    for duration, count in sorted(truth["max_events_in_sliding_windows"].items()):
        checks.append(_check("sliding_" + duration + "_seconds", count, sliding.get(duration),
                             skip=None if duration in sliding else "duration_not_in_configuration"))
    checks.append(_check("greedy_burst_membership", truth["greedy_30_second_3_event_bursts"],
                         [item["record_ids"] for item in activity["greedy_bursts"]],
                         skip=None if (activity["burst_duration_seconds"], activity["burst_minimum_events"]) == (30, 3) else "different_burst_configuration"))
    for field, key in (("dont_occurrences", "contracted"), ("do_not_occurrences", "expanded")):
        checks.append(_check(field, truth[field], body["contractions"]["dont_do_not"][key]))
    fraction = truth["literal_dont_preference_raw_fraction"]
    checks.append(_check("raw_contraction_fraction", fraction["numerator"] / fraction["denominator"],
                         body["contractions"]["dont_do_not"]["raw_fraction"], tolerance=TOLERANCE))
    checks.append(_check("contraction_qualification", truth["qualified_contraction_preference_status"],
                         body["contractions"]["dont_do_not"]["status"],
                         skip=None if config["style"]["contraction_minimum_opportunities"] == 10 else "different_contraction_guard"))
    actual_groups = [item["record_ids"] for item in mods["reuse"]["exact_groups"] if item["match_type"] == "normalized_prose_identical"]
    checks.append(_check("normalized_prose_identical_group", True, truth["normalized_prose_identical_group"] in actual_groups))
    hosts = {item["hostname"]: item for item in mods["links"]["summary"]["hosts"]}
    for hostname, expected in sorted(truth["links"].items()):
        actual = hosts.get(hostname)
        checks.append(_check("host_" + hostname, expected, None if actual is None else {
            "occurrences": actual["occurrences"], "records_with_host": actual["record_count"]}))
    checks.append(_check("default_style_eligibility", truth["default_style_eligible_records"], mods["coverage"]["eligible_style_records"],
                         skip=None if config["style"]["minimum_record_words"] == 20 else "different_style_guard"))
    return checks


def boundary_context(position: int | None, style: dict, windows: list[dict]) -> dict | None:
    """Locate a construction operation against exported candidate intervals.

    A neighbor means either construction-adjacent record is inside one of the
    candidate's two immediate windows. It is a geometric description, not a
    detection threshold. Interval gaps use canonical zero-based record positions.
    """
    if position is None:
        return None
    expected = [position - 1, position]
    by_id = {window["window_id"]: window for window in windows}
    streams = []
    for change in style["changes"]:
        candidates = []
        for boundary in change["boundaries"]:
            actual = boundary["record_interval"]
            overlap = min(expected[1], actual[1]) - max(expected[0], actual[0])
            adjacent = [by_id[boundary[side + "_window_id"]] for side in ("left", "right")]
            candidates.append({"boundary_id": boundary["boundary_id"], "record_interval": actual,
                "relation": "overlap" if overlap > 0 else "touching" if overlap == 0 else "separated",
                "record_position_gap": max(0, -overlap),
                "neighboring_window": any(window["first_record_position"] <= point <= window["last_record_position"]
                                          for window in adjacent for point in expected),
                "left_record_id": boundary["left_record_id"], "right_record_id": boundary["right_record_id"]})
        streams.append({"stream_id": change["stream_id"], "status": change["status"], "candidates": candidates})
    return {"position": position, "record_interval": expected,
            "definition": "operation_begins_at_zero_based_record_position",
            "neighbor_definition": "construction_adjacent_record_inside_either_candidate_adjacent_window",
            "streams": streams}


def _fixture_checks(case: str, truth: dict, result: dict, features: list[dict], receipt: dict, config: AnalysisConfig) -> list[dict]:
    mods = result["modules"]
    checks = [_check("complete_analysis", 0, 4 if any(m["status"] == "resource_limit" for m in mods.values()) else 0,
                     level="synthetic_signal")]
    if "record_count" in truth:
        checks.append(_check("constructed_record_count", truth["record_count"], len(features)))
    if case == "arithmetic":
        checks.extend(_arithmetic(truth, result, features, receipt, config))
    elif case == "edge_cases":
        checks.extend([_check("supplied_timestamp_count", truth["valid_timestamp_count"], mods["activity"]["payload"]["event_count"]),
                       _check("removed_records", truth["removed_records"], mods["coverage"]["payload"]["status_counts"]["removed"]),
                       _check("unknown_date_preserved", 1, mods["coverage"]["payload"]["missing_timestamps"])])
    elif case == "empty":
        checks.append(_check("empty_modules_abstain", True, all(m["status"] in {"insufficient_data", "not_run"} for m in mods.values()), level="synthetic_signal"))
        checks.append(_check("empty_uppercase_rate_is_null", None, mods["text"]["payload"]["body"]["rates"]["uppercase_fraction"]))
    elif case in {"stable_constructed_style", "constructed_topic_shift"}:
        from .style import feature_values
        signatures = {canonical_bytes(feature_values(feature)) for feature in features}
        checks.append(_check("registered_rates_constant", 1, len(signatures), level="synthetic_signal"))
        checks.append(_check("constant_registered_features_no_primary_candidates", 0,
                             sum(len(change["boundaries"]) for change in mods["style"]["payload"]["changes"]), level="synthetic_signal"))
    elif case == "constructed_style_shift":
        position = truth["transformation_starts_at_zero_based_record"]
        left, right = features[:position], features[position:]
        for name, expected, actual in (
            ("uppercase_operation_visible", True, bool(left and right) and all(r["rates"]["uppercase_fraction"] == 0 for r in left)
                and all(r["rates"]["uppercase_fraction"] == 1 for r in right)),
            ("comma_replacement_visible", True, bool(left and right) and all(r["counts"]["punctuation"]["comma"] > 0 for r in left)
                and all(r["counts"]["punctuation"]["comma"] == 0 and r["counts"]["punctuation"]["semicolon"] > 0 for r in right)),
            ("literal_contraction_replacement_visible", True, bool(left and right) and all(r["contractions"]["dont_do_not"]["contracted"] > 0 for r in left)
                and all(r["contractions"]["dont_do_not"]["contracted"] == 0 and r["contractions"]["dont_do_not"]["expanded"] > 0 for r in right))):
            checks.append(_check(name, expected, actual, level="synthetic_signal"))
    else:
        checks.append(_check("scenario_specific_checks", None, None, level="synthetic_signal", skip="unrecognized_construction_scenario"))
    return checks


def evaluate_synthetic(fixtures_path: str | Path, config: AnalysisConfig | None = None) -> dict[str, Any]:
    """Analyze every indexed local fixture and return deterministic evaluation.

    Missing/malformed inputs raise InputError. Hash mismatches and incorrect
    measurements are explicit failed checks, never silently repaired. No files
    are downloaded or written; runtime/host receipts belong to the CLI caller.
    An index containing a subset of the six shipped scenarios is supported but
    explicitly marked incomplete. Canonical identity includes actual truth and
    oracle bytes while each analysis identity remains independent of them.
    """
    config = config or AnalysisConfig.from_toml()
    directory = Path(fixtures_path).resolve()
    index, inventory, cases, index_hash = _inventory(directory)
    checks = numerical_checks(load_json(directory / "numerical_oracles.json"))
    checks.append(_check("fixture_index_integrity", True, all(item["index_matches"] for item in inventory), level="fixture_integrity"))
    fixture_results = []
    saved_features = {}
    for case in cases:
        # Deliberate boundary: analyzer completes before truth is parsed. Raw
        # sidecar bytes were hashed for evaluator provenance by _inventory.
        snapshot = load_snapshot(directory / (case + ".jsonl"), directory / (case + ".snapshot.json"), config)
        analysis = analyze(snapshot, config)
        result = thaw(analysis.results)
        features = [json.loads(line) for line in analysis.files["records_features.jsonl"].splitlines()]
        windows = [json.loads(line) for line in analysis.files["windows.jsonl"].splitlines()]
        truth = load_json(directory / (case + ".truth.json"))
        if (not isinstance(truth, dict) or truth.get("label_type") != "construction_operations_only"
                or truth.get("human_bot_or_ai_ground_truth") != "not_applicable" or truth.get("case") != case
                or truth.get("fixture_version") != index["fixture_version"]):
            raise InputError("Truth must identify construction operations only and match its indexed fixture", code="invalid_synthetic_truth", location=case)
        position = truth.get("transformation_starts_at_zero_based_record")
        if case in {"constructed_style_shift", "constructed_topic_shift"} and position is None:
            raise InputError("Constructed change case needs its operation position", code="invalid_synthetic_truth", location=case)
        if position is not None and (type(position) is not int or not 1 <= position < len(features)):
            raise InputError("Construction boundary position is outside the supplied history", code="invalid_synthetic_truth", location=case)
        try:
            fixture_checks = _fixture_checks(case, truth, result, features, thaw(analysis.ingest_receipt), config)
        except (KeyError, TypeError, ZeroDivisionError) as exc:
            raise InputError("Malformed scenario-specific construction facts", code="invalid_synthetic_truth", location=case) from exc
        payloads = {key: value["payload"] for key, value in result["modules"].items()}
        fixture_results.append({"case": case, "canonical_snapshot_sha256": snapshot.canonical_sha256,
            "results_sha256": digest(result), "analysis_exit_code": analysis.exit_code,
            "module_statuses": {key: value["status"] for key, value in sorted(result["modules"].items())},
            "checks": fixture_checks,
            "summary": {"record_count": len(features), "retained_words": payloads["text"]["body"]["counts"]["retained_words"],
                "event_count": payloads["activity"]["event_count"], "eligible_style_records": payloads["coverage"]["eligible_style_records"],
                "exact_reuse_groups": len(payloads["reuse"]["exact_groups"]), "near_reuse_pairs": len(payloads["reuse"]["pairs"]),
                "qualified_primary_windows": sum(stream["qualified_window_count"] for stream in payloads["style"]["streams"]),
                "primary_candidates": sum(len(change["boundaries"]) for change in payloads["style"]["changes"]),
                "findings": len(result["findings"])},
            "construction_boundary": boundary_context(position, payloads["style"], windows)})
        saved_features[case] = features
    cross_checks = []
    stable, topic = saved_features.get("stable_constructed_style"), saved_features.get("constructed_topic_shift")
    for check_id, field in (("topic_substitution_preserves_function_mask", "masked_segments"),
                            ("topic_substitution_preserves_registered_rates", None)):
        from .style import feature_values
        actual = None if stable is None or topic is None else len(stable) == len(topic) and all(
            (a[field] == b[field] if field else feature_values(a) == feature_values(b)) for a, b in zip(stable, topic, strict=True))
        cross_checks.append(_check(check_id, True, actual, level="synthetic_signal",
                                   skip="required_fixture_not_indexed" if actual is None else None))
    fp, env, _ = implementation_identity()
    all_checks = checks + cross_checks + [check for fixture in fixture_results for check in fixture["checks"]]
    output = {"schema_version": "1.0.0", "suite": "synthetic", "method_id": "synthetic_construction_evaluation_v1",
        "method_version": "1.0.0", "status": "failed" if any(check["status"] == "failed" for check in all_checks) else "passed",
        "real_world_validation": "not_established", "external_data": "not_evaluated", "label_definition": "construction_operations_only",
        "config_sha256": digest(config.analytical()), "implementation_fingerprint": fp, "reference_environment": env,
        "dataset": {"fixture_version": index["fixture_version"], "index_sha256": index_hash, "content_sha256": digest(inventory),
                    "files": inventory, "shipped_scenarios_complete": SHIPPED_CASES <= set(cases),
                    "missing_shipped_scenarios": sorted(SHIPPED_CASES - set(cases))},
        "numerical_checks": checks, "fixtures": fixture_results, "cross_fixture_checks": cross_checks,
        "check_counts": {status: sum(check["status"] == status for check in all_checks) for status in ("passed", "failed", "not_evaluated")},
        "limitations": ["formulaic_construction_fixtures_are_not_a_real_world_accuracy_benchmark",
            "construction_labels_are_not_authorship_bot_human_or_ai_ground_truth",
            "boundary_locations_are_descriptive_overlap_and_neighbor_observations_without_accuracy_target",
            "parameter_stability_is_not_confidence", "external_data_not_supplied_to_this_suite",
            "cross_platform_byte_identity_not_established"]}
    from .schemas import validate
    validate(output, "evaluation_synthetic", location="synthetic evaluation")
    return output
