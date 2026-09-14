"""Predefined temporal sensitivity reruns and deterministic boundary matching.

Execution counts describe parameter stability, never statistical confidence.
Alternative windows are compared in original record-order intervals, not by
unrelated window indices. Primary records/windows and activity are not mutated.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .config import AnalysisConfig
from .errors import ComputationError, InputError
from .io import digest, record_sort_key, thaw
from .registry import METHOD_VERSION
from .windows import build_streams

_EXECUTED = {"ok", "no_measurable_variation"}


def maximum_boundary_matching(left: list[int], right: list[int], tolerance: int = 1) -> list[list[int]]:
    """Maximum-cardinality matching, minimum L1 displacement, lexicographic ties.

    The absolute-distance cost on ordered points admits a noncrossing optimum;
    uncrossing an equally costly match is lexicographically no worse. Dynamic
    programming computes cardinality/cost, then chooses the first lexicographic
    pair admitting the optimal suffix. No recursion or randomized matching is
    used. Duplicate boundaries are invalid, rather than additional observations.
    """
    if type(tolerance) is not int or tolerance < 0:
        raise InputError("Boundary tolerance must be a nonnegative integer", code="invalid_boundary_tolerance")
    for values in (left, right):
        if any(type(value) is not int or value < 0 for value in values) or len(set(values)) != len(values):
            raise InputError("Boundary indices must be unique nonnegative integers", code="invalid_boundaries")
    x, y = sorted(left), sorted(right)
    rows, columns = len(x), len(y)
    cardinality = [[0] * (columns + 1) for _ in range(rows + 1)]
    costs = [[0] * (columns + 1) for _ in range(rows + 1)]
    for i in range(rows - 1, -1, -1):
        for j in range(columns - 1, -1, -1):
            candidates = [(cardinality[i + 1][j], costs[i + 1][j]),
                          (cardinality[i][j + 1], costs[i][j + 1])]
            displacement = abs(x[i] - y[j])
            if displacement <= tolerance:
                candidates.append((1 + cardinality[i + 1][j + 1], displacement + costs[i + 1][j + 1]))
            cardinality[i][j], costs[i][j] = min(candidates, key=lambda score: (-score[0], score[1]))
    pairs: list[list[int]] = []
    i = j = 0
    while i < rows and j < columns and cardinality[i][j]:
        target_count, target_cost = cardinality[i][j], costs[i][j]
        found = False
        for candidate_i in range(i, rows):
            for candidate_j in range(j, columns):
                displacement = abs(x[candidate_i] - y[candidate_j])
                if (displacement <= tolerance
                        and 1 + cardinality[candidate_i + 1][candidate_j + 1] == target_count
                        and displacement + costs[candidate_i + 1][candidate_j + 1] == target_cost):
                    pairs.append([x[candidate_i], y[candidate_j]])
                    i, j = candidate_i + 1, candidate_j + 1
                    found = True
                    break
            if found:
                break
        if not found:
            raise ComputationError("Cannot reconstruct optimal boundary matching", code="matching_reconstruction_failure")
    return pairs


def _interval_relation(left: Sequence[int], right: Sequence[int]) -> tuple[str, int]:
    """Intervals are open spaces between supplied records; endpoint touch is explicit."""
    lower, upper = max(left[0], right[0]), min(left[1], right[1])
    if lower < upper:
        return "overlap", 0
    if lower == upper:
        return "touching", 0
    return "separated", lower - upper


def compare_boundary_intervals(primary: Mapping[str, Any], setting: Mapping[str, Any]) -> dict[str, Any]:
    """Describe interval overlap/touch/separation without matching window indices.

    For each primary interval, export every overlap and touching candidate plus
    the nearest alternate interval. Nearest ties use endpoint displacement, then
    interval endpoints and boundary ID. The nearest separated interval is not
    called a matched boundary. Full candidate intervals remain in change results.
    """
    result = {"stream_id": primary["stream_id"], "status": "not_comparable",
              "primary_status": primary["status"], "setting_status": setting["status"],
              "primary_boundary_count": len(primary["boundaries"]), "setting_boundary_count": len(setting["boundaries"]),
              "comparisons": [], "setting_boundaries_without_overlap": []}
    if primary["status"] not in _EXECUTED or setting["status"] not in _EXECUTED:
        return result
    result["status"] = "ok"
    overlapping_ids: set[str] = set()
    others = sorted(setting["boundaries"], key=lambda boundary: (boundary["record_interval"], boundary["boundary_id"]))
    for boundary in primary["boundaries"]:
        interval = boundary["record_interval"]
        overlapping, touching = [], []
        nearest = None
        if others:
            nearest = min(others, key=lambda other: (
                _interval_relation(interval, other["record_interval"])[1],
                sum(abs(a - b) for a, b in zip(interval, other["record_interval"], strict=True)),
                other["record_interval"], other["boundary_id"]))
        for other in others:
            relation, _ = _interval_relation(interval, other["record_interval"])
            if relation == "overlap":
                overlapping.append(other["boundary_id"])
                overlapping_ids.add(other["boundary_id"])
            elif relation == "touching":
                touching.append(other["boundary_id"])
        if overlapping:
            relation = "overlap"
        elif touching:
            relation = "touching"
        elif nearest is not None:
            relation = "separated"
        else:
            relation = "no_setting_boundaries"
        # An overlapping candidate takes precedence over a touching interval
        # whose endpoint displacement happens to be smaller.
        if overlapping:
            eligible = [other for other in others if other["boundary_id"] in overlapping]
        elif touching:
            eligible = [other for other in others if other["boundary_id"] in touching]
        else:
            eligible = [nearest] if nearest is not None else []
        if eligible:
            nearest = min(eligible, key=lambda other: (
                _interval_relation(interval, other["record_interval"])[1],
                sum(abs(a - b) for a, b in zip(interval, other["record_interval"], strict=True)),
                other["record_interval"], other["boundary_id"]))
        result["comparisons"].append({
            "primary_boundary_id": boundary["boundary_id"], "primary_record_interval": list(interval),
            "overlapping_boundary_ids": overlapping, "touching_boundary_ids": touching,
            "nearest_boundary_id": nearest["boundary_id"] if nearest is not None else None,
            "nearest_record_interval": list(nearest["record_interval"]) if nearest is not None else None,
            "relation": relation,
            "record_position_gap": _interval_relation(interval, nearest["record_interval"])[1] if nearest is not None else None,
        })
    result["setting_boundaries_without_overlap"] = [boundary["boundary_id"] for boundary in others if boundary["boundary_id"] not in overlapping_ids]
    return result


def _stream_summary(stream: Mapping[str, Any]) -> dict[str, Any]:
    return {**{key: thaw(value) for key, value in stream.items() if key != "windows"},
            "window_ids": [window["window_id"] for window in stream["windows"]]}


def _same_window_stability(primary: Sequence[Mapping[str, Any]], settings: Sequence[Mapping[str, Any]],
                           tolerance: int) -> list[dict[str, Any]]:
    summaries = []
    for baseline in primary:
        rows = []
        matched_settings: dict[int, list[str]] = {index: [] for index in baseline["internal_boundaries"]}
        executed = 0
        for setting in settings:
            result = next(item for item in setting["results"] if item["stream_id"] == baseline["stream_id"])
            pairs = []
            if result["status"] in _EXECUTED:
                executed += 1
                if baseline["status"] in _EXECUTED:
                    pairs = maximum_boundary_matching(list(baseline["internal_boundaries"]), list(result["internal_boundaries"]), tolerance)
                for left_index, _ in pairs:
                    matched_settings[left_index].append(setting["setting_id"])
            left_matched, right_matched = {pair[0] for pair in pairs}, {pair[1] for pair in pairs}
            rows.append({"setting_id": setting["setting_id"], "penalty_lambda": setting["penalty_lambda"],
                         "status": result["status"], "reason_codes": list(result["reason_codes"]),
                         "matched_pairs": pairs,
                         "unmatched_primary_boundaries": [index for index in baseline["internal_boundaries"] if index not in left_matched],
                         "unmatched_setting_boundaries": [index for index in result["internal_boundaries"] if index not in right_matched]})
        summaries.append({"stream_id": baseline["stream_id"], "executed_setting_count": executed,
                          "skipped_setting_count": len(settings) - executed, "settings": rows,
                          "boundaries": [{"primary_window_index": index,
                                          "matched_in_k_of_m_executed_settings": len(matched_settings[index]),
                                          "executed_setting_count": executed, "matched_setting_ids": matched_settings[index]}
                                         for index in baseline["internal_boundaries"]]})
    return summaries


def analyze_temporal(features: Sequence[Mapping[str, Any]], primary_style_payload: Mapping[str, Any],
                     primary_windows: Sequence[Mapping[str, Any]], reuse_payload: Mapping[str, Any],
                     config: AnalysisConfig) -> dict[str, Any]:
    """Run primary temporal analysis and the predefined sensitivity constructions.

    Return ``changes`` for primary pooled/community streams, ``sensitivity``
    metadata/results, and ``extra_windows`` with every referenced rerun window.
    Alternative targets/exclusions run pooled streams only; within-community
    control uses primary community streams, avoiding an unspecified Cartesian
    product of community, target and exclusion settings.
    """
    from .changepoints import analyze_changes
    by_window = {window["window_id"]: window for window in primary_windows}
    primary_streams = primary_style_payload["streams"]
    lambdas = list(dict.fromkeys(float(value) for value in (config["changes"]["primary_lambda"], *config["changes"]["sensitivity_lambdas"])))
    penalty_settings = []
    for value in lambdas:
        results = [analyze_changes(stream, [by_window[identifier] for identifier in stream["window_ids"]],
                                   config, penalty_lambda=value) for stream in primary_streams]
        penalty_settings.append({"setting_id": "penalty_" + digest({"lambda": value})[:24],
                                 "penalty_lambda": value, "is_primary": value == float(config["changes"]["primary_lambda"]),
                                 "results": results})
    primary = next(setting["results"] for setting in penalty_settings if setting["is_primary"])
    primary_by_stream = {result["stream_id"]: result for result in primary}
    ordered = sorted(features, key=record_sort_key)
    positions = {record["id"]: index for index, record in enumerate(ordered)}
    extra_windows: dict[str, dict[str, Any]] = {}
    construction_settings = []

    def construction(setting_type: str, target: int, exclusions: Sequence[Mapping[str, Any]],
                     enabled: bool = True, resource_limited: bool = False) -> None:
        excluded_ids = sorted({item["excluded_record_id"] for item in exclusions}, key=lambda identifier: positions[identifier])
        relationships = sorted((thaw(item) for item in exclusions), key=lambda item: (positions[item["excluded_record_id"]], item["reason"]))
        setting_id = "construction_" + digest({"type": setting_type, "target_words": target,
                                                "excluded_ids": excluded_ids})[:24]
        entry = {"setting_id": setting_id, "setting_type": setting_type, "target_words": target,
                 "status": "not_run", "reason_codes": ["disabled_by_configuration"],
                 "excluded_record_ids": excluded_ids, "exclusion_relationships": relationships,
                 "streams": [], "results": [], "interval_comparisons": []}
        if not enabled:
            construction_settings.append(entry)
            return
        if resource_limited:
            entry.update(status="resource_limit", reason_codes=["near_reduction_unavailable_resource_limit"])
            construction_settings.append(entry)
            return
        built = build_streams(features, config, target_words=target, excluded_ids=excluded_ids)
        for stream in built["streams"]:
            if stream["scope_type"] != "pooled":
                continue
            windows = stream["windows"]
            summary = _stream_summary(stream)
            entry["streams"].append(summary)
            result = analyze_changes(summary, windows, config)
            entry["results"].append(result)
            entry["interval_comparisons"].append(compare_boundary_intervals(primary_by_stream[stream["stream_id"]], result))
            for window in windows:
                if window["window_id"] not in by_window:
                    extra_windows.setdefault(window["window_id"], thaw(window))
        enough = any(result["status"] in _EXECUTED for result in entry["results"])
        entry.update(status="executed" if enough else "insufficient_data",
                     reason_codes=[] if enough else ["no_qualified_streams"])
        construction_settings.append(entry)

    for target in config["windows"]["sensitivity_targets"]:
        construction("window_target", target, [])
    edited = [{"excluded_record_id": record["id"], "representative_record_id": None,
               "reason": "known_edited", "source_reference_id": None}
              for record in ordered if record["edit_state"] == "edited"]
    construction("exclude_known_edited", config["windows"]["target_words"], edited,
                 enabled=config["sensitivity"]["exclude_known_edited"])
    exact = [{"excluded_record_id": relation["excluded_record_id"], "representative_record_id": relation["representative_record_id"],
              "reason": relation["reason"], "source_reference_id": relation["match_group_id"]}
             for relation in reuse_payload["exact_reductions"]]
    construction("repeat_reduced_exact", config["windows"]["target_words"], exact,
                 enabled=config["reuse"]["repeat_reduced_exact_sensitivity"])
    near = [{"excluded_record_id": relation["excluded_record_id"], "representative_record_id": relation["representative_record_id"],
             "reason": relation["reason"], "source_reference_id": relation["pair_id"]}
            for relation in reuse_payload["near_reductions"]]
    construction("repeat_reduced_near", config["windows"]["target_words"], exact + near,
                 enabled=config["reuse"]["repeat_reduced_near_sensitivity"],
                 resource_limited=reuse_payload["near_reduction_status"] == "not_run_resource_limit")
    communities = [stream["stream_id"] for stream in primary_streams if stream["scope_type"] == "community"]
    enabled = config["sensitivity"]["within_community"]
    enough_communities = any(primary_by_stream[identifier]["status"] in _EXECUTED for identifier in communities)
    within = {"enabled": enabled, "status": "not_run" if not enabled else "executed" if enough_communities else "insufficient_data",
              "reason_codes": ["disabled_by_configuration"] if not enabled else [] if enough_communities else ["no_qualified_community_streams"],
              "primary_stream_ids": communities if enabled else []}
    sensitivity = {"method_id": "boundary_sensitivity_v1", "method_version": METHOD_VERSION,
                   "interpretation": "parameter_stability_not_confidence",
                   "same_window_boundary_tolerance": config["changes"]["same_window_boundary_tolerance"],
                   "penalty_settings": penalty_settings,
                   "same_window_stability": _same_window_stability(primary, penalty_settings, config["changes"]["same_window_boundary_tolerance"]),
                   "construction_settings": construction_settings, "within_community": within,
                   "limitations": ["parameter_stability_is_not_confidence", "skipped_settings_excluded_from_denominator",
                                   "different_windows_compared_by_record_intervals", "interval_endpoint_touch_not_interior_overlap",
                                   "alternative_constructions_use_pooled_streams", "known_edit_exclusion_does_not_verify_unknown_edits",
                                   "repeat_deweighting_does_not_change_primary_activity"]}
    return {"changes": primary, "sensitivity": sensitivity, "extra_windows": list(extra_windows.values())}
