"""Observable supplied HTTP(S) hostname distribution, with explicit denominators."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from .errors import ComputationError
from .io import Snapshot, thaw


def _summary(record_ids: Sequence[str], occurrences: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    valid = [occurrence for occurrence in occurrences if occurrence["status"] == "ok"]
    by_host = defaultdict(list)
    for occurrence in valid:
        by_host[occurrence["hostname"]].append(occurrence)
    record_order = {identifier: index for index, identifier in enumerate(record_ids)}
    hosts = []
    for hostname, items in sorted(by_host.items(), key=lambda item: (-len(item[1]), item[0])):
        ids = sorted({item["record_id"] for item in items}, key=record_order.__getitem__)
        hosts.append({"hostname": hostname, "occurrences": len(items), "record_count": len(ids),
                      "share_of_records": len(ids) / len(record_ids) if record_ids else None,
                      "share_of_valid_http_links": len(items) / len(valid) if valid else None,
                      "source_record_ids": ids, "body_occurrences": sum(item["source_field"] == "text" for item in items),
                      "title_occurrences": sum(item["source_field"] == "title" for item in items)})
    records_with_valid_links = len({item["record_id"] for item in valid})
    return {
        "record_count": len(record_ids), "total_link_occurrences": len(occurrences),
        "valid_http_occurrences": len(valid),
        "malformed_occurrences": sum(item["status"] == "malformed" for item in occurrences),
        "unsafe_scheme_occurrences": sum(item["status"] == "unsafe_scheme" for item in occurrences),
        "distinct_hosts": len(hosts), "records_with_any_links": len({item["record_id"] for item in occurrences}),
        "records_with_valid_links": records_with_valid_links,
        "share_records_with_valid_links": records_with_valid_links / len(record_ids) if record_ids else None,
        "hosts": hosts,
    }


def analyze_links(snapshot: Snapshot, features: Sequence[Mapping[str, Any]],
                  windows: Sequence[Mapping[str, Any]], config: Any) -> dict[str, Any]:
    """Aggregate actual preprocessor link occurrences without fetching or reparsing.

    Body/title scope is explicit. Repeat occurrences contribute separately, while
    record-with-host denominators count each supplied record once. Host share of
    links uses valid HTTP(S) occurrences; record share uses all records in scope,
    including supplied records whose body is unavailable. Empty denominators are
    null. Titles are measured separately and are never added to style body text.
    """
    if [record["id"] for record in snapshot.records] != [record["id"] for record in features]:
        raise ComputationError("Link features must match canonical snapshot order", code="feature_snapshot_mismatch")
    occurrences = []
    by_record: dict[str, list[dict[str, Any]]] = defaultdict(list)
    title_record_ids = []
    for feature in features:
        scopes = [("text", feature)]
        if feature.get("title") is not None:
            scopes.append(("title", feature["title"]))
            title_record_ids.append(feature["id"])
        for field, view in scopes:
            for link in view["links"]:
                occurrence = {"record_id": feature["id"], "source_field": field,
                              "source_line_range": thaw(link["source_line_range"]), "hostname": link["hostname"],
                              "url": link["url"], "status": link["status"]}
                occurrences.append(occurrence)
                by_record[feature["id"]].append(occurrence)
    ids = [record["id"] for record in snapshot.records]
    communities: dict[str | None, list[str]] = defaultdict(list)
    for record in snapshot.records:
        communities[record["subreddit"]].append(record["id"])
    by_community = []
    for community, members in sorted(communities.items(), key=lambda item: (item[0] is not None, item[0] or "")):
        selected = [item for identifier in members for item in by_record[identifier]]
        by_community.append({"subreddit": community, "summary": _summary(members, selected)})
    by_window = []
    seen_windows = set()
    for window in windows:
        if window["window_id"] in seen_windows:
            raise ComputationError("Duplicate window ID in link scope", code="duplicate_window_id")
        seen_windows.add(window["window_id"])
        members = list(window["record_ids"])
        if not set(members) <= set(ids):
            raise ComputationError("Link window references absent records", code="unknown_window_record")
        selected = [item for identifier in members for item in by_record[identifier]]
        by_window.append({"window_id": window["window_id"], "summary": _summary(members, selected)})
    return {
        "scope": "supplied_body_and_separate_submission_titles", "summary": _summary(ids, occurrences),
        "by_field": [{"source_field": "text", "summary": _summary(ids, [item for item in occurrences if item["source_field"] == "text"])},
                     {"source_field": "title", "summary": _summary(title_record_ids, [item for item in occurrences if item["source_field"] == "title"])}],
        "by_community": by_community, "by_window": by_window, "occurrences": occurrences,
        "limitations": ["links_are_supplied_not_fetched", "hostnames_are_not_registrable_domains",
                        "repeated_links_do_not_establish_promotion_or_intent", "source_link_occurrences_can_include_excluded_quote_or_code"],
    }
