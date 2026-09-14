"""Supplied target-account parent/thread counts and UTC community transitions."""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .io import Snapshot, epoch_us


def analyze_interactions(snapshot: Snapshot, config: Any) -> dict[str, Any]:
    """Describe local structure and creation-time differences without inferred intent.

    A supplied reply is a comment with a non-null parent ID. Internal parent times
    take precedence over optional metadata. Missing parents remain missing context.
    All source statuses can contribute supplied structural/timestamp measurements.
    No traversal of parent chains or network resolution is performed.
    """
    records = snapshot.records
    by_id = {record["id"]: record for record in records}
    replies = [record for record in records if record["kind"] == "comment" and record["parent_id"] is not None]
    parent_linked = [record for record in records if record["parent_id"] is not None]
    grouped = defaultdict(list)
    for record in records:
        if record["thread_id"] is not None:
            grouped[record["thread_id"]].append(record)
    threads = []
    for thread_id, members in sorted(grouped.items()):
        reply_ids = [record["id"] for record in members if record["kind"] == "comment" and record["parent_id"] is not None]
        threads.append({"thread_id": thread_id, "record_count": len(members), "reply_count": len(reply_ids),
                        "repeat_participation": len(members) > 1,
                        "source_record_ids": [record["id"] for record in members], "reply_record_ids": reply_ids})
    differences = []
    for record in records:
        if record["parent_id"] is None and record["parent_created_utc"] is None:
            continue
        parent = by_id.get(record["parent_id"])
        if parent is not None and parent["created_utc"] is not None:
            parent_time, source = parent["created_utc"], "internal_record"
        elif record["parent_created_utc"] is not None:
            parent_time, source = record["parent_created_utc"], "supplied_parent_metadata"
        else:
            parent_time, source = None, "unavailable"
        creation = record["created_utc"]
        reason_codes = []
        if creation is None:
            reason_codes.append("missing_record_creation_timestamp")
        if parent_time is None:
            reason_codes.append("missing_parent_creation_timestamp")
        difference = (epoch_us(creation) - epoch_us(parent_time)) / 1_000_000 if not reason_codes else None
        status = "missing_timestamps" if reason_codes else "negative_unverified_metadata" if difference < 0 else "ok"
        if status == "negative_unverified_metadata":
            reason_codes.append("supplied_parent_metadata_has_later_creation")
        differences.append({"record_id": record["id"], "parent_id": record["parent_id"],
                            "created_utc": creation, "parent_created_utc": parent_time,
                            "creation_to_parent_creation_seconds": difference, "parent_time_source": source,
                            "status": status, "reason_codes": reason_codes})
    events = [record for record in records if record["created_utc"] is not None]
    transitions = []
    counts = Counter()
    for left, right in zip(events, events[1:]):
        counts[(left["subreddit"], right["subreddit"])] += 1
        transitions.append({"left_record_id": left["id"], "right_record_id": right["id"],
                            "left_utc": left["created_utc"], "right_utc": right["created_utc"],
                            "from_subreddit": left["subreddit"], "to_subreddit": right["subreddit"],
                            "changed_label": left["subreddit"] != right["subreddit"]})
    transition_counts = [{"from_subreddit": left, "to_subreddit": right, "count": count,
                          "includes_unknown_label": left is None or right is None}
                         for (left, right), count in sorted(counts.items(), key=lambda item: (
                             item[0][0] is not None, item[0][0] or "", item[0][1] is not None, item[0][1] or ""))]
    return {
        "scope": "distinct_supplied_target_account_records", "record_count": len(records),
        "supplied_reply_records": len(replies),
        "internal_parent_links": sum(record["parent_id"] in by_id for record in parent_linked),
        "unresolved_parent_links": sum(record["parent_id"] not in by_id for record in parent_linked),
        "records_without_parent_id": sum(record["parent_id"] is None for record in records),
        "records_without_thread_id": sum(record["thread_id"] is None for record in records),
        "threads": threads, "repeat_participation_thread_count": sum(thread["repeat_participation"] for thread in threads),
        "parent_differences": differences,
        "parent_difference_available_count": sum(item["creation_to_parent_creation_seconds"] is not None for item in differences),
        "negative_unverified_difference_count": sum(item["status"] == "negative_unverified_metadata" for item in differences),
        "parent_cycles": [{"source_record_ids": list(warning["source_record_ids"])} for warning in snapshot.warnings if warning["code"] == "parent_reference_cycle"],
        "community_sequence": {"timestamped_record_count": len(events), "adjacent_pairs": len(transitions),
                               "changed_label_count": sum(item["changed_label"] for item in transitions),
                               "transition_counts": transition_counts, "transitions": transitions},
        "limitations": ["supplied_target_records_only", "missing_parent_context_is_not_interpreted",
                        "creation_to_parent_creation_is_not_typing_or_read_to_reply_time",
                        "supplied_parent_metadata_is_unverified", "unknown_community_labels_are_missing_context",
                        "simultaneous_events_use_canonical_ID_order_not_verified_interaction_order"],
    }
