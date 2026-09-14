"""Exact retained-text reuse with rational decisions and source-linked passages.

Python strings/tuples are compared for equality; process hash values are never
stored as feature identities. The inverted index is exact, with no sampling.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence, Set
from fractions import Fraction
from itertools import combinations
from typing import Any

from .errors import ComputationError, InputError
from .io import Snapshot, digest
from .reuse_matching import ReuseLimit, TokenMatcher, WorkMeter

Shingle = tuple[str, ...]


def shingle_set(segments: Sequence[Sequence[str]], n: int = 5) -> frozenset[Shingle]:
    """Distinct n-token tuples, without crossing supplied segment boundaries."""
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise InputError("Shingle length must be a positive integer", code="invalid_shingle_length")
    return frozenset(tuple(segment[i:i + n]) for segment in segments for i in range(len(segment) - n + 1))


def ratio_at_least(numerator: int, denominator: int, threshold_numerator: int, threshold_denominator: int) -> bool:
    """Compare an observed ratio to an exact rational threshold; absent abstains."""
    if threshold_denominator <= 0 or threshold_numerator < 0 or threshold_numerator > threshold_denominator:
        raise InputError("Threshold must be a rational in [0,1]", code="invalid_reuse_threshold")
    return denominator > 0 and numerator * threshold_denominator >= denominator * threshold_numerator


def shingle_metrics(a: Set[Shingle], b: Set[Shingle]) -> dict[str, Any]:
    """Set Jaccard and both directed containments, with explicit empty-set abstention."""
    intersection = len(a & b)
    union = len(a) + len(b) - intersection
    valid = bool(a and b)
    return {
        "status": "ok" if valid else "not_computable",
        "left_shingles": len(a), "right_shingles": len(b), "intersection": intersection, "union": union,
        "jaccard": intersection / union if valid else None,
        "left_in_right": intersection / len(a) if valid else None,
        "right_in_left": intersection / len(b) if valid else None,
    }


def _exact_groups(snapshot: Snapshot, features: Sequence[Mapping[str, Any]], minimum_words: int) -> list[dict[str, Any]]:
    groups = []
    types = ("raw_text_identical", "normalized_prose_identical", "token_sequence_identical")
    for match_type in types:
        index: dict[Any, list[int]] = defaultdict(list)
        for position, (record, feature) in enumerate(zip(snapshot.records, features, strict=True)):
            if not feature["usable"]:
                continue
            if match_type == "raw_text_identical":
                key = record["text"]
                eligible = bool(key and key.strip())
            elif match_type == "normalized_prose_identical":
                key = tuple(segment["text"] for segment in feature["segments"])
                eligible = bool(key)
            else:
                key = tuple(tuple(segment) for segment in feature["tokens"])
                eligible = any(key)
            if eligible:
                index[key].append(position)
        # Index groups traverse first-seen canonical record order. Sort explicitly
        # so changing dictionary internals cannot alter exported group order.
        for key, positions in sorted(index.items(), key=lambda item: item[1][0]):
            if len(positions) < 2:
                continue
            ids = [features[position]["id"] for position in positions]
            counts = [{"record_id": features[position]["id"], "word_count": features[position]["counts"]["retained_words"]} for position in positions]
            substantial = all(item["word_count"] >= minimum_words for item in counts)
            groups.append({
                "group_id": "reuse_exact_" + digest({"type": match_type, "record_ids": ids})[:24],
                "match_type": match_type, "record_ids": ids, "representative_id": ids[0],
                "retained_word_counts": counts, "substantial": substantial,
                "reason_codes": [] if substantial else ["short_common_text"], "match_sha256": digest(key),
            })
    return groups


def _near_shingles(features: Sequence[Mapping], n: int, cfg: Mapping, meter: WorkMeter) -> list[frozenset]:
    """Charge token copying and distinct record/shingle postings before allocation."""
    minimum = min(cfg["minimum_near_duplicate_words"], cfg["minimum_containment_shorter_words"])
    sets = []
    for feature in features:
        meter.charge("work_units")
        distinct = set()
        if feature["usable"] and feature["counts"]["retained_words"] >= minimum:
            for segment in feature["tokens"]:
                meter.charge("work_units")
                for start in range(len(segment)-n+1):
                    meter.charge("work_units", n)
                    shingle = tuple(segment[start:start+n])
                    if shingle not in distinct:
                        meter.charge("index_postings")
                        distinct.add(shingle)
        sets.append(frozenset(distinct))
    return sets


def _sort_reservation(count: int, width: int = 1) -> int:
    # A deterministic conservative comparison reservation, not elapsed CPU work.
    return count * max(1, count.bit_length()) * width


def _candidates(features: Sequence[Mapping], sets: Sequence[frozenset], cfg: Mapping,
                meter: WorkMeter, candidates: set[tuple[int, int]]) -> None:
    eligible = [i for i, shingles in enumerate(sets) if shingles]
    # At zero threshold disjoint nonempty sets can qualify, so enumerate all
    # eligible pairs. Each posting encounter is charged, including repeated pairs.
    if cfg["near_threshold_numerator"] == 0 or cfg["containment_threshold_numerator"] == 0:
        postings = [eligible]
    else:
        inverted: dict[Shingle, list[int]] = defaultdict(list)
        for i in eligible:
            meter.charge("work_units", _sort_reservation(len(sets[i]), cfg["shingle_tokens"]))
            for shingle in sorted(sets[i]):
                meter.charge("work_units", cfg["shingle_tokens"])
                inverted[shingle].append(i)
        meter.charge("work_units", _sort_reservation(len(inverted), cfg["shingle_tokens"]))
        postings = (inverted[shingle] for shingle in sorted(inverted))
    for posting in postings:
        meter.charge("work_units")
        for left, right in combinations(posting, 2):
            meter.charge("work_units")
            candidates.add((left, right))
            if len(candidates) > cfg["max_candidate_pairs"]:
                raise ReuseLimit("max_candidate_pairs")


def _matching_passages(left: Mapping, right: Mapping, n: int, *,
                       matcher: TokenMatcher | None = None, meter: WorkMeter | None = None) -> list[dict[str, Any]]:
    """One exact longest contiguous match, with unchanged segment/offset ties.

    A suffix automaton covers nonidentical as well as identical low-entropy text.
    Ties use left segment, right segment, then left/right token offset. Actual
    retained-source slices can differ in case and punctuation. Reservations occur
    before evidence token-list and string materialization; no truncation is used.
    """
    match = (matcher or TokenMatcher(left["tokens"], n, meter)).find(right["tokens"])
    if match is None:
        return []
    li, ri = match.left_segment, match.right_segment
    def bounds(feature, segment_index, start_token):
        offsets = feature["token_offsets"][segment_index]
        return offsets[start_token]["start"], offsets[start_token+match.size-1]["end"]
    ls, le = bounds(left, li, match.left_start)
    rs, re = bounds(right, ri, match.right_start)
    if meter is not None:
        meter.charge("evidence_tokens", match.size)
        meter.charge("work_units", match.size)
        token_codepoints = sum(len(left["tokens"][li][i]) for i in range(match.left_start, match.left_start+match.size))
        meter.charge("evidence_codepoints", le-ls+re-rs+token_codepoints)
    def source(feature, segment_index, start, end):
        return {"segment_index": segment_index, "normalized_start": start, "normalized_end": end,
                "text": feature["segments"][segment_index]["text"][start:end]}
    return [{"match_type": "contiguous_normalized_lexical_tokens", "token_count": match.size,
             "tokens": list(left["tokens"][li][match.left_start:match.left_start+match.size]),
             "left": source(left, li, ls, le), "right": source(right, ri, rs, re)}]


def _connected_groups(pairs: list[dict[str, Any]], record_ids: list[str]) -> list[dict[str, Any]]:
    positions = {identifier: index for index, identifier in enumerate(record_ids)}
    parent = list(range(len(record_ids)))
    def root(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index
    for pair in pairs:
        a, b = root(positions[pair["left_record_id"]]), root(positions[pair["right_record_id"]])
        parent[max(a, b)] = min(a, b)
    components: dict[int, list[str]] = defaultdict(list)
    for index, identifier in enumerate(record_ids):
        components[root(index)].append(identifier)
    component_pairs: dict[int, list[str]] = defaultdict(list)
    for pair in pairs:
        component_pairs[root(positions[pair["left_record_id"]])].append(pair["pair_id"])
    groups = []
    for component, members in components.items():
        if len(members) < 2:
            continue
        pair_ids = component_pairs[component]
        groups.append({"group_id": "reuse_connected_" + digest(members)[:24], "record_ids": members,
                       "pair_ids": pair_ids, "relationship": "connected_edges_not_pairwise_equivalence"})
    return groups


def analyze_reuse(snapshot: Snapshot, features: Sequence[Mapping[str, Any]], config: Any) -> dict[str, Any]:
    """Exact groups remain complete when any bounded near-search phase abstains.

    No partial pairs, connected groups or near reductions escape a resource limit.
    Candidate count is a lower bound only if candidate generation was incomplete.
    Logical resource reservations are deterministic across hash seeds and paths.
    """
    if [r["id"] for r in snapshot.records] != [f["id"] for f in features]:
        raise ComputationError("Features must match the canonical snapshot order", code="feature_snapshot_mismatch")
    cfg = config["reuse"]
    n = cfg["shingle_tokens"]
    exact = _exact_groups(snapshot, features, cfg["minimum_near_duplicate_words"])
    exact_reductions = []
    if cfg["repeat_reduced_exact_sensitivity"]:
        for group in exact:
            if group["match_type"] == "normalized_prose_identical":
                exact_reductions.extend({"excluded_record_id": identifier, "representative_record_id": group["representative_id"], "reason": "normalized_prose_identical", "match_group_id": group["group_id"]} for identifier in group["record_ids"][1:])
    order = {feature["id"]: index for index, feature in enumerate(features)}
    ids = list(order)
    exact_reductions.sort(key=lambda relation: order[relation["excluded_record_id"]])
    exact_excluded = {relation["excluded_record_id"] for relation in exact_reductions}
    excluded = set(exact_excluded)
    meter = WorkMeter(cfg)
    candidates: set[tuple[int, int]] = set()
    candidates_complete = complete = False
    limit_reason = None
    pairs, groups, near_reductions = [], [], []
    try:
        sets = _near_shingles(features, n, cfg, meter)
        _candidates(features, sets, cfg, meter, candidates)
        candidates_complete = True
        meter.charge("work_units", _sort_reservation(len(candidates), 2))
        previous_left = matcher = None
        for li, ri in sorted(candidates):
            left, right = features[li], features[ri]
            meter.charge("work_units", 1+n*min(len(sets[li]),len(sets[ri])))
            metrics = shingle_metrics(sets[li], sets[ri])
            lw, rw = left["counts"]["retained_words"], right["counts"]["retained_words"]
            near = min(lw, rw) >= cfg["minimum_near_duplicate_words"] and ratio_at_least(metrics["intersection"], metrics["union"], cfg["near_threshold_numerator"], cfg["near_threshold_denominator"])
            left_contained = cfg["minimum_containment_shorter_words"] <= lw <= rw and ratio_at_least(metrics["intersection"], metrics["left_shingles"], cfg["containment_threshold_numerator"], cfg["containment_threshold_denominator"])
            right_contained = cfg["minimum_containment_shorter_words"] <= rw <= lw and ratio_at_least(metrics["intersection"], metrics["right_shingles"], cfg["containment_threshold_numerator"], cfg["containment_threshold_denominator"])
            if near or left_contained or right_contained:
                if previous_left != li:
                    matcher = TokenMatcher(left["tokens"], n, meter)
                    previous_left = li
                pairs.append({
                    "pair_id": "reuse_pair_" + digest([left["id"], right["id"]])[:24],
                    "left_record_id": left["id"], "right_record_id": right["id"],
                    "left_word_count": lw, "right_word_count": rw,
                    "left_token_count": sum(map(len, left["tokens"])), "right_token_count": sum(map(len, right["tokens"])),
                    **metrics, "near_duplicate": near, "left_contained_in_right": left_contained,
                    "right_contained_in_left": right_contained,
                    "matching_passages": _matching_passages(left, right, n, matcher=matcher, meter=meter),
                })
        # Reserve linear graph/reduction traversal. Sparse adjacency avoids the
        # former all-records/all-representatives scan even when few edges exist.
        meter.charge("work_units", 8*(len(features)+len(pairs)))
        groups = _connected_groups(pairs, ids)
        if cfg["repeat_reduced_near_sensitivity"]:
            neighbors: dict[str, list[tuple[str, Mapping]]] = defaultdict(list)
            for pair in pairs:
                if pair["near_duplicate"]:
                    neighbors[pair["right_record_id"]].append((pair["left_record_id"],pair))
            representatives = set()
            for identifier in ids:
                if identifier in excluded:
                    continue
                choices = [(-Fraction(pair["intersection"], pair["union"]), order[representative], representative, pair)
                           for representative,pair in neighbors[identifier] if representative in representatives]
                if choices:
                    _, _, representative, pair = min(choices, key=lambda item: item[:2])
                    near_reductions.append({"excluded_record_id": identifier, "representative_record_id": representative,
                                            "reason": "greedy_retained_representative_near_match", "pair_id": pair["pair_id"],
                                            "intersection": pair["intersection"], "union": pair["union"], "jaccard": pair["jaccard"]})
                    excluded.add(identifier)
                else:
                    representatives.add(identifier)
        complete = True
    except ReuseLimit as exc:
        limit_reason = exc.reason
        pairs, groups, near_reductions = [], [], []
        excluded = exact_excluded
    near_reduction_status = "not_run_disabled"
    if cfg["repeat_reduced_near_sensitivity"]:
        near_reduction_status = "ok" if complete else "not_run_resource_limit"
    return {
        "scope": "body_text", "shingle_tokens": n,
        "eligible_records": sum(bool(feature["usable"]) for feature in features),
        "nonempty_shingle_records": sum(bool(feature["usable"]) and any(len(segment)>=n for segment in feature["tokens"]) for feature in features),
        "exact_groups": exact, "near_status": "ok" if complete else "resource_limit",
        "candidate_pair_count": len(candidates), "candidate_count_is_lower_bound": not candidates_complete,
        "max_candidate_pairs": cfg["max_candidate_pairs"], "budget_complete": complete,
        "resource_usage": {"method": "reuse_work_units_v1", **meter.usage},
        "resource_limits": meter.limits, "resource_limit_reason": limit_reason,
        "pairs": pairs, "connected_groups": groups,
        "exact_reductions": exact_reductions, "near_reductions": near_reductions,
        "repeat_reduced_retained_ids": [identifier for identifier in ids if identifier not in excluded],
        "near_reduction_status": near_reduction_status,
        "matching_passage_method": "one_longest_contiguous_lexical_match_per_pair_v1",
    }
