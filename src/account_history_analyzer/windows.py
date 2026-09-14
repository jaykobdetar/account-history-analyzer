"""Whole-record chronological writing windows and explicit manual selectors."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .errors import InputError
from .features import pooled
from .io import digest, epoch_us, record_sort_key
from .schemas import validate


def style_eligible(record: Mapping[str, Any], config: Any) -> bool:
    """V1 primary body eligibility; supplied language is never inferred."""
    return bool(record["usable"] and record["created_utc"] is not None
                and record["language"] == "en"
                and record["counts"]["retained_words"] >= config["style"]["minimum_record_words"])


def _stream(records: Sequence[Mapping[str, Any]], *, kind: str, subreddit: str | None,
            scope_type: str, positions: Mapping[str, int], target: int,
            config: Any) -> dict[str, Any]:
    minimum = config["windows"]["minimum_records"]
    stream_id = "stream_" + digest({"scope_type": scope_type, "kind": kind, "subreddit": subreddit})[:24]
    selected = [record for record in records if record["kind"] == kind
                and (scope_type == "pooled" or record["subreddit"] == subreddit)]
    windows = []
    buffer = []
    words = 0

    def close() -> None:
        count = len(buffer)
        qualified = words >= target and count >= minimum
        largest = max(record["counts"]["retained_words"] for record in buffer) / words
        reasons = []
        if words < target:
            reasons.append("insufficient_target_words")
        if count < minimum:
            reasons.append("insufficient_record_count")
        if largest > config["windows"]["single_record_dominance_fraction"]:
            reasons.append("single_record_dominance")
        if any(record["edit_state"] == "edited" for record in buffer):
            reasons.append("known_edited_observed_text")
        ids = [record["id"] for record in buffer]
        windows.append({
            "window_id": "window_" + digest({"stream_id": stream_id, "target_words": target,
                                            "minimum_records": minimum, "record_ids": ids})[:24],
            "stream_id": stream_id, "record_ids": ids, "word_count": words, "record_count": count,
            "qualified": qualified, "remainder": not qualified, "reason_codes": sorted(reasons),
            "largest_record_share": largest,
            "first_utc": buffer[0]["created_utc"], "last_utc": buffer[-1]["created_utc"],
            "first_record_id": ids[0], "last_record_id": ids[-1],
            "first_record_position": positions[ids[0]], "last_record_position": positions[ids[-1]],
            "features": pooled(buffer, config),
        })

    for record in selected:
        buffer.append(record)
        words += record["counts"]["retained_words"]
        if words >= target and len(buffer) >= minimum:
            close()
            buffer = []
            words = 0
    if buffer:
        close()
    return {
        "stream_id": stream_id, "scope_type": scope_type, "kind": kind, "subreddit": subreddit,
        "eligible_record_ids": [record["id"] for record in selected],
        "eligible_words": sum(record["counts"]["retained_words"] for record in selected),
        "target_words": target, "minimum_records": minimum, "record_count": len(selected),
        "qualified_window_count": sum(window["qualified"] for window in windows),
        "remainder_word_count": sum(window["word_count"] for window in windows if window["remainder"]),
        "windows": windows,
    }


def build_streams(features: Sequence[Mapping[str, Any]], config: Any, *, target_words: int | None = None,
                  excluded_ids: Iterable[str] = ()) -> dict[str, Any]:
    """Build non-overlapping windows separately in each declared English scope.

    Pooled comment/submission streams always exist, including empty streams. Up
    to ten communities are ranked by total eligible word volume across kinds;
    ties use null first, then the exact supplied label. Each selected community
    receives separate comment/submission streams. Null is its own community.

    Sensitivity exclusions do not mutate features. Position fields are zero-based
    positions in the original canonical full record order before exclusions.
    """
    target = config["windows"]["target_words"] if target_words is None else target_words
    if not isinstance(target, int) or isinstance(target, bool) or target < 1:
        raise InputError("Window target must be a positive integer", code="invalid_window_target")
    ordered = sorted(features, key=record_sort_key)
    positions = {record["id"]: index for index, record in enumerate(ordered)}
    if len(positions) != len(ordered):
        raise InputError("Feature IDs must be unique", code="duplicate_feature_id")
    excluded = set(excluded_ids)
    unknown = excluded - positions.keys()
    if unknown:
        raise InputError(f"Unknown excluded IDs: {sorted(unknown)!r}", code="unknown_record_id")
    eligible = [record for record in ordered if record["id"] not in excluded and style_eligible(record, config)]
    volumes: Counter[str | None] = Counter()
    for record in eligible:
        volumes[record["subreddit"]] += record["counts"]["retained_words"]
    ranked = sorted(volumes, key=lambda label: (-volumes[label], label is not None, label or ""))
    limit = config["windows"]["max_community_streams"]
    streams = [_stream(eligible, kind=kind, subreddit=None, scope_type="pooled", positions=positions,
                       target=target, config=config) for kind in ("comment", "submission")]
    streams.extend(_stream(eligible, kind=kind, subreddit=label, scope_type="community", positions=positions,
                           target=target, config=config) for label in ranked[:limit] for kind in ("comment", "submission"))
    omitted = [{"subreddit": label, "eligible_words": volumes[label]} for label in ranked[limit:]]
    return {"streams": streams, "omitted_communities": omitted}


def select_records(features: Sequence[Mapping[str, Any]], selector: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Intersect exact supplied selectors, returning raw selected measurements.

    Time intervals are start-inclusive/end-exclusive and omit missing timestamps.
    An ID-only selector may include missing-time records. No style guard is applied
    here; comparison code can display raw counts even when text is insufficient.
    """
    validate({"schema_version": "1.0.0", "left": selector, "right": {}}, "comparison", "selector")
    start = epoch_us(selector["start_utc"]) if selector.get("start_utc") is not None else None
    end = epoch_us(selector["end_utc"]) if selector.get("end_utc") is not None else None
    if start is not None and end is not None and start > end:
        raise InputError("Selection start must not follow end", code="inverted_selection_interval")
    ids = set(selector["ids"]) if selector.get("ids") is not None else None
    if ids is not None:
        unknown = ids - {record["id"] for record in features}
        if unknown:
            raise InputError(f"Unknown selection IDs: {sorted(unknown)!r}", code="unknown_record_id")
    selected = []
    for record in sorted(features, key=record_sort_key):
        if ids is not None and record["id"] not in ids:
            continue
        if selector.get("kind") is not None and record["kind"] != selector["kind"]:
            continue
        if selector.get("subreddit") is not None and record["subreddit"] != selector["subreddit"]:
            continue
        if start is not None or end is not None:
            if record["created_utc"] is None:
                continue
            timestamp = epoch_us(record["created_utc"])
            if start is not None and timestamp < start or end is not None and timestamp >= end:
                continue
        selected.append(record)
    return selected


def select_comparison(features: Sequence[Mapping[str, Any]], selection: Mapping[str, Any]) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], bool]:
    """Validate both selectors and reject overlap unless explicitly diagnostic.

    The third return value is true only when the selected sides actually overlap,
    which marks those comparisons dependent even with explicit authorization.
    """
    validate(selection, "comparison", "comparison")
    left = select_records(features, selection["left"])
    right = select_records(features, selection["right"])
    overlap = {record["id"] for record in left}.intersection(record["id"] for record in right)
    if overlap and not selection.get("allow_overlap", False):
        raise InputError(f"Comparison sides overlap: {sorted(overlap)!r}", code="overlapping_comparison")
    return left, right, bool(overlap)
