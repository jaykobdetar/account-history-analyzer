"""Frozen-design, evaluation-only arithmetic for the pilot 4 chronology study.

This module imports no analyzer and computes no writing features or distances.
All positions refer to the complete supplied snapshot in canonical order. A
truth split k means records [0, k) precede records [k, n). A production boundary
between original record positions a and b represents inclusive splits [a+1, b].
Ten supplied-record positions is the fixed primary tolerance, including equality.
Control junctions are construction diagnostics, never annotated style boundaries.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from fractions import Fraction
from typing import Any

SCHEMA_VERSION = "pilot4-chronology-math-v1"
TOLERANCE_RECORDS = 10
MINIMUM_QUALIFIED_WINDOWS = 8
MINIMUM_SEGMENT_WINDOWS = 3
CONDITIONS = (
    "continuity_same_community",
    "switch_same_community",
    "continuity_changed_community",
    "switch_changed_community",
)
EXECUTED_STATUSES = frozenset(("ok", "no_measurable_variation"))


def _integer(value: Any, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def factorial_cases(block_id: str) -> list[dict[str, Any]]:
    """All 16 fixed contrasts from A/B accounts, X/Y communities, early/late.

    IDs are study-local opaque labels. Each anchor's early cell is reused for
    the four factorial conditions; no observed score affects the descriptors.
    """
    if not isinstance(block_id, str) or not block_id:
        raise ValueError("A nonempty opaque block ID is required")
    rows = []
    for account in ("A", "B"):
        for community in ("X", "Y"):
            for condition in CONDITIONS:
                switch = condition.startswith("switch_")
                changed = condition.endswith("changed_community")
                other_account = ({"A": "B", "B": "A"}[account] if switch else account)
                other_community = ({"X": "Y", "Y": "X"}[community] if changed else community)
                anchor = account + community
                rows.append({
                    "case_id": f"{block_id}:{anchor}:{condition}",
                    "block_id": block_id,
                    "anchor_id": anchor,
                    "condition": condition,
                    "source_switch": switch,
                    "community_change": changed,
                    "left_cell_id": f"{block_id}:{account}:{community}:early",
                    "right_cell_id": f"{block_id}:{other_account}:{other_community}:late",
                })
    return rows


def _interval(interval: Sequence[int]) -> tuple[int, int]:
    if not isinstance(interval, (list, tuple)) or len(interval) != 2:
        raise ValueError("An inclusive two-position split interval is required")
    lo, hi = (_integer(x, "split position", 1) for x in interval)
    if lo > hi:
        raise ValueError("Split interval endpoints are reversed")
    return lo, hi


def record_boundary_to_split_interval(record_interval: Sequence[int]) -> list[int]:
    """Convert zero-based bounding records [a,b] to inclusive split [a+1,b]."""
    if not isinstance(record_interval, (list, tuple)) or len(record_interval) != 2:
        raise ValueError("Exactly two original record positions are required")
    a, b = (_integer(x, "record position") for x in record_interval)
    if a >= b:
        raise ValueError("The right bounding record must follow the left record")
    return [a + 1, b]


def interval_error(interval: Sequence[int], k: int) -> int:
    """Minimum absolute error from an inclusive interval to an interior split."""
    lo, hi = _interval(interval)
    _integer(k, "truth or control-junction split", 1)
    return max(lo - k, k - hi, 0)


def reconstruct_windows(metadata_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Independently reconstruct frozen primary pooled-comment whole-record windows.

    Rows must already be in complete canonical order. They contain retained_words
    plus an explicit boolean style_eligible, or the non-text fields kind, usable,
    language, created_utc, and retained_words (counts.retained_words is accepted).
    The explicit eligibility form is intended for a separately checked metadata
    projection; its eligibility must not be inferred from candidate output.
    Supplied positions survive exclusions. Titles never enter the body budget.
    """
    output: list[dict[str, Any]] = []
    positions: list[int] = []
    words = 0

    def close() -> None:
        output.append({
            "qualified": words >= 1000 and len(positions) >= 8,
            "first_record_position": positions[0],
            "last_record_position": positions[-1],
            "record_positions": list(positions),
            "record_count": len(positions),
            "word_count": words,
        })

    for ordinal, row in enumerate(metadata_rows):
        count = row.get("retained_words", row.get("counts", {}).get("retained_words"))
        _integer(count, "retained_words")
        if "style_eligible" in row:
            if type(row["style_eligible"]) is not bool:
                raise ValueError("style_eligible must be boolean")
            eligible = row["style_eligible"] and row.get("kind", "comment") == "comment"
            if eligible and count < 20:
                raise ValueError("An eligible record cannot have fewer than 20 words")
        else:
            if type(row["usable"]) is not bool:
                raise ValueError("usable must be boolean")
            eligible = (row["kind"] == "comment" and row["usable"]
                        and row["language"] == "en" and row["created_utc"] is not None
                        and count >= 20)
        if eligible:
            positions.append(ordinal)
            words += count
            if words >= 1000 and len(positions) >= 8:
                close()
                positions = []
                words = 0
    if positions:
        close()
    return output


def _qualified(windows: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    qualified = []
    previous = -1
    for window in windows:
        if type(window["qualified"]) is not bool:
            raise ValueError("Window qualification must be boolean")
        first = _integer(window["first_record_position"], "first record position")
        last = _integer(window["last_record_position"], "last record position")
        if first > last or first <= previous:
            raise ValueError("Windows must be ordered, nonoverlapping original-position intervals")
        for field in ("record_count", "word_count"):
            if field in window:
                _integer(window[field], field, 1)
        if "record_count" in window and window["record_count"] > last - first + 1:
            raise ValueError("Window count exceeds its original-position span")
        previous = last
        if window["qualified"]:
            qualified.append(window)
    return qualified


def legal_grid(windows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Every admissible single-boundary position for an otherwise adequate stream.

    The minimum eight qualified windows is enforced before enumerating boundaries
    with at least three windows on each side. No writing vector or selected
    boundary is used. Gaps between eligible records retain original positions.
    """
    qualified = _qualified(windows)
    if len(qualified) < MINIMUM_QUALIFIED_WINDOWS:
        return []
    return [{
        "window_index": j,
        "split_interval": record_boundary_to_split_interval([
            qualified[j - 1]["last_record_position"],
            qualified[j]["first_record_position"],
        ]),
    } for j in range(MINIMUM_SEGMENT_WINDOWS,
                     len(qualified) - MINIMUM_SEGMENT_WINDOWS + 1)]


def _timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Record timestamps must be ISO timestamps or null")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Record timestamps must have an explicit timezone")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value is not None else None


def _time_bracket(interval: Sequence[int], times: Sequence[datetime | None]) -> dict[str, Any]:
    lo, hi = _interval(interval)
    left, right = times[lo - 1], times[hi]
    return {
        "split_interval": [lo, hi],
        "possible_split_position_count": hi - lo + 1,
        "record_gap_positions": hi - lo,
        "left_record_position": lo - 1,
        "right_record_position": hi,
        "left_utc": _iso(left),
        "right_utc": _iso(right),
        "elapsed_seconds": (right - left).total_seconds() if left is not None and right is not None else None,
    }


def _localization(intervals: list[list[int]] | None, k: int, best_grid_error: int | None,
                  times: Sequence[datetime | None]) -> dict[str, Any]:
    nearest = (min(intervals, key=lambda x: (interval_error(x, k), x)) if intervals else None)
    error = interval_error(nearest, k) if nearest is not None else None
    matched = (error is not None and error <= TOLERANCE_RECORDS) if intervals is not None else None
    return {
        "reference_split_k": k,
        "matched_within_tolerance": matched,
        "exact_interval_containment": (error == 0) if intervals is not None else None,
        "nearest_interval_error_records": error,
        "nearest_interval": _time_bracket(nearest, times) if nearest is not None else None,
        "excess_error_over_best_grid_records": error - best_grid_error if error is not None and best_grid_error is not None else None,
        "matched_candidate_count": int(matched) if matched is not None else None,
        "unmatched_candidate_count": len(intervals) - int(matched) if intervals is not None else None,
    }


def score_case(*, candidate_intervals: Sequence[Sequence[int]] | None, status: str,
               reason_codes: Sequence[str], truth_k: int | None,
               control_junction_k: int | None, windows: Sequence[Mapping[str, Any]],
               record_timestamps: Sequence[str | None]) -> dict[str, Any]:
    """Score one saved primary analysis without executing or selecting an analyzer.

    candidate_intervals are already inclusive split intervals, not production
    bounding-record intervals. Exactly one truth or control junction is required.
    The adapter must set unavailable status on a failed full-pipeline execution,
    even if a partial primary artifact happens to contain boundaries. Status
    no_measurable_variation is an executed zero-candidate outcome. Other native
    statuses remain unavailable; partial candidate measurements are not exposed.
    """
    if not isinstance(status, str) or not status:
        raise ValueError("A saved primary/full-pipeline status is required")
    if not isinstance(reason_codes, (list, tuple)) or any(not isinstance(x, str) or not x for x in reason_codes):
        raise ValueError("Reason codes must be a list of nonempty strings")
    if (truth_k is None) == (control_junction_k is None):
        raise ValueError("Supply exactly one switch truth or control construction junction")
    times = [_timestamp(value) for value in record_timestamps]
    n = len(times)
    k = truth_k if truth_k is not None else control_junction_k
    _integer(k, "truth or control-junction split", 1)
    if k >= n:
        raise ValueError("The reference split must be interior to the supplied snapshot")
    observed_times = [time for time in times if time is not None]
    if observed_times != sorted(observed_times):
        raise ValueError("Timestamps must be in canonical nondecreasing order")
    if any(time is not None for time in times[next((i for i, time in enumerate(times) if time is None), n):]):
        raise ValueError("Missing timestamps must follow all observed timestamps")
    qualified = _qualified(windows)
    if any(window["last_record_position"] >= n for window in windows):
        raise ValueError("A window lies outside the complete supplied snapshot")
    grid = legal_grid(windows)
    best = min(grid, key=lambda row: (interval_error(row["split_interval"], k), row["window_index"])) if grid else None
    best_error = interval_error(best["split_interval"], k) if best else None
    executed = status in EXECUTED_STATUSES
    intervals = None
    if executed:
        if len(qualified) < MINIMUM_QUALIFIED_WINDOWS:
            raise ValueError("Executed primary analysis requires at least eight qualified windows")
        if candidate_intervals is None:
            raise ValueError("Executed analysis must supply an explicit candidate list")
        intervals = [list(_interval(interval)) for interval in candidate_intervals]
        if status == "no_measurable_variation" and intervals:
            raise ValueError("Constant measurable series cannot report primary candidates")
        grid_indices = {tuple(row["split_interval"]): row["window_index"] for row in grid}
        previous_window = 0
        for interval in intervals:
            index = grid_indices.get(tuple(interval))
            if index is None:
                raise ValueError("A candidate does not belong to the independently reconstructed legal grid")
            if index - previous_window < MINIMUM_SEGMENT_WINDOWS:
                raise ValueError("Candidate order or intervening segment size is invalid")
            previous_window = index
    localization = _localization(intervals, k, best_error, times)
    bracket = _time_bracket([k, k], times)
    return {
        "schema_version": SCHEMA_VERSION,
        "tolerance_records": TOLERANCE_RECORDS,
        "status": status,
        "reason_codes": sorted(set(reason_codes)),
        "executed": executed,
        "candidate_occurrence": bool(intervals) if executed else None,
        "candidate_count": len(intervals) if executed else None,
        "candidate_intervals": [_time_bracket(interval, times) for interval in intervals] if executed else None,
        "truth_boundaries": [truth_k] if truth_k is not None else [],
        "switch_localization": localization if truth_k is not None else None,
        "control_junction_diagnostic": localization if control_junction_k is not None else None,
        "grid_resolution": {
            "reference_type": "source_switch_truth" if truth_k is not None else "control_construction_junction",
            "reference_split_k": k,
            "qualified_window_count": len(qualified),
            "minimum_qualified_windows": MINIMUM_QUALIFIED_WINDOWS,
            "minimum_segment_windows": MINIMUM_SEGMENT_WINDOWS,
            "adequate_window_count": len(qualified) >= MINIMUM_QUALIFIED_WINDOWS,
            "legal_boundary_count": len(grid),
            "best_interval_error_records": best_error,
            "attainable_within_tolerance": best_error <= TOLERANCE_RECORDS if best_error is not None else None,
            "exact_containment_attainable": best_error == 0 if best_error is not None else None,
            "nearest_legal_boundary": ({**best, **_time_bracket(best["split_interval"], times)} if best else None),
            "legal_boundaries": [{**row, **_time_bracket(row["split_interval"], times)} for row in grid],
        },
        "temporal_resolution": {
            "supplied_record_count": n,
            "missing_timestamp_count": n - len(observed_times),
            "first_utc": _iso(observed_times[0]) if observed_times else None,
            "last_utc": _iso(observed_times[-1]) if observed_times else None,
            "elapsed_seconds": (observed_times[-1] - observed_times[0]).total_seconds() if observed_times else None,
            "construction_junction": bracket,
            "qualified_windows": [{
                "window_index": index,
                "first_record_position": window["first_record_position"],
                "last_record_position": window["last_record_position"],
                "record_count": window.get("record_count"),
                "word_count": window.get("word_count"),
                "first_utc": _iso(times[window["first_record_position"]]),
                "last_utc": _iso(times[window["last_record_position"]]),
                "straddles_construction_junction": window["first_record_position"] < k <= window["last_record_position"],
            } for index, window in enumerate(qualified)],
        },
    }


def _mean(values: Sequence[int | float | bool]) -> float | None:
    return float(sum((Fraction(value) for value in values), Fraction()) / len(values)) if values else None


_METRIC_PATHS = {
    "candidate_occurrence": ("candidate_occurrence",),
    "candidate_count": ("candidate_count",),
    "switch_matched_within_tolerance": ("switch_localization", "matched_within_tolerance"),
    "switch_exact_interval_containment": ("switch_localization", "exact_interval_containment"),
    "switch_nearest_interval_error_records": ("switch_localization", "nearest_interval_error_records"),
    "switch_excess_error_over_best_grid_records": ("switch_localization", "excess_error_over_best_grid_records"),
    "control_junction_matched_within_tolerance": ("control_junction_diagnostic", "matched_within_tolerance"),
    "control_junction_exact_interval_containment": ("control_junction_diagnostic", "exact_interval_containment"),
    "control_junction_nearest_interval_error_records": ("control_junction_diagnostic", "nearest_interval_error_records"),
    "grid_attainable_within_tolerance": ("grid_resolution", "attainable_within_tolerance"),
    "grid_best_interval_error_records": ("grid_resolution", "best_interval_error_records"),
}


def _get(score: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    value = score
    for key in path:
        if value is None:
            return None
        value = value[key]
    return value


def aggregate_cases(scored_descriptors: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Descriptive four-condition summaries with complete planned blocks retained.

    Input is factorial descriptor fields plus score=score_case(...). Every
    supplied block must contain its exact 16 descriptors, including unavailable
    cases. No case-level IID interval, bootstrap, significance test, or implicit
    independent-account assumption is produced. Up to six blocks are supported.
    Available-value block means are descriptive with explicit denominators;
    complete-block means additionally require all four values for that metric.
    Localization error means condition on having a candidate and are labelled by
    their available counts; zero candidates are not imputed zero error.
    """
    blocks = sorted({row["block_id"] for row in scored_descriptors})
    if not 1 <= len(blocks) <= 6:
        raise ValueError("This registered descriptive design requires one to six complete blocks")
    expected = {row["case_id"]: row for block in blocks for row in factorial_cases(block)}
    observed: dict[str, Mapping[str, Any]] = {}
    for row in scored_descriptors:
        identifier = row["case_id"]
        if identifier in observed or identifier not in expected:
            raise ValueError("Duplicate or unexpected factorial case")
        if any(row[key] != value for key, value in expected[identifier].items()):
            raise ValueError("The supplied descriptor differs from the frozen factorial design")
        score = row["score"]
        if score["schema_version"] != SCHEMA_VERSION or score["tolerance_records"] != TOLERANCE_RECORDS:
            raise ValueError("Unknown score schema or changed tolerance")
        if bool(score["truth_boundaries"]) != row["source_switch"]:
            raise ValueError("Control/switch designation differs from score truth")
        observed[identifier] = row
    if set(observed) != set(expected):
        raise ValueError("All 16 planned cases per block must remain in the aggregate")
    per_block = []
    for block in blocks:
        for condition in CONDITIONS:
            rows = [row for row in observed.values() if row["block_id"] == block and row["condition"] == condition]
            scores = [row["score"] for row in rows]
            metrics = {}
            for name, path in _METRIC_PATHS.items():
                available = [_get(score, path) for score in scores if _get(score, path) is not None]
                metrics[name] = {"available_cases": len(available), "planned_cases": 4,
                                 "available_mean": _mean(available),
                                 "complete_mean": _mean(available) if len(available) == 4 else None}
            per_block.append({
                "block_id": block, "condition": condition, "planned_cases": 4,
                "executed_cases": sum(score["executed"] for score in scores),
                "unavailable_cases": sum(not score["executed"] for score in scores),
                "status_counts": dict(sorted(Counter(score["status"] for score in scores).items())),
                "reason_code_case_counts": dict(sorted(Counter(reason for score in scores for reason in set(score["reason_codes"])).items())),
                "metrics": metrics,
            })
    conditions = []
    for condition in CONDITIONS:
        rows = [row for row in per_block if row["condition"] == condition]
        metrics = {}
        for name in _METRIC_PATHS:
            available = [row["metrics"][name]["available_mean"] for row in rows
                         if row["metrics"][name]["available_mean"] is not None]
            complete = [row["metrics"][name]["complete_mean"] for row in rows
                        if row["metrics"][name]["complete_mean"] is not None]
            metrics[name] = {
                "planned_cases": 4 * len(blocks),
                "available_cases": sum(row["metrics"][name]["available_cases"] for row in rows),
                "planned_blocks": len(blocks), "available_blocks": len(available),
                "complete_blocks": len(complete),
                "available_block_equal_mean": _mean(available),
                "complete_block_equal_mean": _mean(complete),
            }
        statuses: Counter[str] = Counter()
        reasons: Counter[str] = Counter()
        for row in rows:
            statuses.update(row["status_counts"])
            reasons.update(row["reason_code_case_counts"])
        conditions.append({
            "condition": condition, "planned_blocks": len(blocks), "planned_cases": 4 * len(blocks),
            "executed_cases": sum(row["executed_cases"] for row in rows),
            "unavailable_cases": sum(row["unavailable_cases"] for row in rows),
            "status_counts": dict(sorted(statuses.items())),
            "reason_code_case_counts": dict(sorted(reasons.items())), "metrics": metrics,
        })
    return {"schema_version": SCHEMA_VERSION, "analysis_type": "descriptive_only",
            "confidence_intervals": None, "confidence_interval_reason": "no_registered_interval_procedure_small_related_block_design",
            "tolerance_records": TOLERANCE_RECORDS, "planned_blocks": len(blocks),
            "planned_cases": len(expected), "per_block": per_block, "conditions": conditions}
