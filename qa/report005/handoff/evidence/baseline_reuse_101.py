"""Exact retained-text reuse with rational decisions and source-linked passages.

Python strings/tuples are compared for equality; process hash values are never
stored as feature identities. The inverted index is exact, with no sampling.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence, Set
from difflib import SequenceMatcher
from fractions import Fraction
from itertools import combinations
from typing import Any

from .errors import ComputationError, InputError
from .io import Snapshot, digest

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


def _length_eligible(left: Mapping, right: Mapping, cfg: Mapping) -> bool:
    lw, rw = left["counts"]["retained_words"], right["counts"]["retained_words"]
    return min(lw, rw) >= min(cfg["minimum_near_duplicate_words"], cfg["minimum_containment_shorter_words"])


def _candidates(features: Sequence[Mapping], sets: Sequence[frozenset], cfg: Mapping) -> tuple[set[tuple[int, int]], bool]:
    candidates: set[tuple[int, int]] = set()
    eligible = [i for i, feature in enumerate(features) if feature["usable"] and sets[i] and feature["counts"]["retained_words"] >= min(cfg["minimum_near_duplicate_words"], cfg["minimum_containment_shorter_words"])]
    # At a zero threshold, even disjoint nonempty sets can qualify. An inverted
    # index may omit those pairs only when both thresholds are strictly positive.
    if cfg["near_threshold_numerator"] == 0 or cfg["containment_threshold_numerator"] == 0:
        postings = [eligible]
    else:
        inverted: dict[Shingle, list[int]] = defaultdict(list)
        for i in eligible:
            for shingle in sorted(sets[i]):
                inverted[shingle].append(i)
        postings = [inverted[shingle] for shingle in sorted(inverted)]
    for posting in postings:
        for left, right in combinations(posting, 2):
            if not _length_eligible(features[left], features[right], cfg):
                continue
            candidates.add((left, right))
            if len(candidates) > cfg["max_candidate_pairs"]:
                return candidates, False
    return candidates, True


def _matching_passages(left: Mapping, right: Mapping, n: int) -> list[dict[str, Any]]:
    """Select one longest actual contiguous token match, confined to two segments.

    SequenceMatcher with autojunk disabled finds an exact longest contiguous
    block within each segment pair. Ties use left segment, right segment, then
    left/right token offset. This selects evidence; it does not claim to enumerate
    every repeated passage. Retained-source slices can differ in case/punctuation.
    """
    best = None
    for li, ltokens in enumerate(left["tokens"]):
        if len(ltokens) < n:
            continue
        left_shingles = shingle_set([ltokens], n)
        for ri, rtokens in enumerate(right["tokens"]):
            if len(rtokens) < n or not left_shingles.intersection(shingle_set([rtokens], n)):
                continue
            match = SequenceMatcher(None, ltokens, rtokens, autojunk=False).find_longest_match(0, len(ltokens), 0, len(rtokens))
            key = (-match.size, li, ri, match.a, match.b)
            if match.size >= n and (best is None or key < best[0]):
                best = (key, match, li, ri)
    if best is None:
        return []
    _, match, li, ri = best
    def source(feature, segment_index, start_token):
        offsets = feature["token_offsets"][segment_index]
        start = offsets[start_token]["start"]
        end = offsets[start_token + match.size - 1]["end"]
        return {"segment_index": segment_index, "normalized_start": start, "normalized_end": end,
                "text": feature["segments"][segment_index]["text"][start:end]}
    return [{"match_type": "contiguous_normalized_lexical_tokens", "token_count": match.size,
             "tokens": list(left["tokens"][li][match.a:match.a + match.size]),
             "left": source(left, li, match.a), "right": source(right, ri, match.b)}]


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
    groups = []
    for members in components.values():
        if len(members) < 2:
            continue
        selected = set(members)
        pair_ids = [pair["pair_id"] for pair in pairs if pair["left_record_id"] in selected and pair["right_record_id"] in selected]
        groups.append({"group_id": "reuse_connected_" + digest(members)[:24], "record_ids": members,
                       "pair_ids": pair_ids, "relationship": "connected_edges_not_pairwise_equivalence"})
    return groups


def analyze_reuse(snapshot: Snapshot, features: Sequence[Mapping[str, Any]], config: Any) -> dict[str, Any]:
    """Complete exact groups plus exact candidate-indexed near/containment matches.

    On pair-budget exhaustion exact groups and exact reductions remain complete;
    no partly scanned near-pair table is emitted. Candidate count is then a lower
    bound (budget + 1), and the caller must return incomplete-analysis exit code 4.
    """
    if [r["id"] for r in snapshot.records] != [f["id"] for f in features]:
        raise ComputationError("Features must match the canonical snapshot order", code="feature_snapshot_mismatch")
    cfg = config["reuse"]
    n = cfg["shingle_tokens"]
    exact = _exact_groups(snapshot, features, cfg["minimum_near_duplicate_words"])
    sets = [shingle_set(feature["tokens"], n) if feature["usable"] else frozenset() for feature in features]
    candidates, complete = _candidates(features, sets, cfg)
    pairs = []
    if complete:
        for li, ri in sorted(candidates):
            left, right = features[li], features[ri]
            metrics = shingle_metrics(sets[li], sets[ri])
            lw, rw = left["counts"]["retained_words"], right["counts"]["retained_words"]
            near = min(lw, rw) >= cfg["minimum_near_duplicate_words"] and ratio_at_least(metrics["intersection"], metrics["union"], cfg["near_threshold_numerator"], cfg["near_threshold_denominator"])
            left_contained = cfg["minimum_containment_shorter_words"] <= lw <= rw and ratio_at_least(metrics["intersection"], metrics["left_shingles"], cfg["containment_threshold_numerator"], cfg["containment_threshold_denominator"])
            right_contained = cfg["minimum_containment_shorter_words"] <= rw <= lw and ratio_at_least(metrics["intersection"], metrics["right_shingles"], cfg["containment_threshold_numerator"], cfg["containment_threshold_denominator"])
            if near or left_contained or right_contained:
                pairs.append({
                    "pair_id": "reuse_pair_" + digest([left["id"], right["id"]])[:24],
                    "left_record_id": left["id"], "right_record_id": right["id"],
                    "left_word_count": lw, "right_word_count": rw,
                    "left_token_count": sum(map(len, left["tokens"])), "right_token_count": sum(map(len, right["tokens"])),
                    **metrics, "near_duplicate": near, "left_contained_in_right": left_contained,
                    "right_contained_in_left": right_contained, "matching_passages": _matching_passages(left, right, n),
                })
    exact_reductions = []
    if cfg["repeat_reduced_exact_sensitivity"]:
        for group in exact:
            if group["match_type"] == "normalized_prose_identical":
                exact_reductions.extend({"excluded_record_id": identifier, "representative_record_id": group["representative_id"], "reason": "normalized_prose_identical", "match_group_id": group["group_id"]} for identifier in group["record_ids"][1:])
    order = {feature["id"]: index for index, feature in enumerate(features)}
    exact_reductions.sort(key=lambda relation: order[relation["excluded_record_id"]])
    excluded = {relation["excluded_record_id"] for relation in exact_reductions}
    near_reductions = []
    near_reduction_status = "not_run_disabled"
    if cfg["repeat_reduced_near_sensitivity"]:
        near_reduction_status = "ok" if complete else "not_run_resource_limit"
        if complete:
            edges = {frozenset((pair["left_record_id"], pair["right_record_id"])): pair for pair in pairs if pair["near_duplicate"]}
            representatives = []
            for feature in features:
                identifier = feature["id"]
                if identifier in excluded:
                    continue
                choices = []
                for representative in representatives:
                    pair = edges.get(frozenset((identifier, representative)))
                    if pair is not None:
                        choices.append((-Fraction(pair["intersection"], pair["union"]), order[representative], representative, pair))
                if choices:
                    _, _, representative, pair = min(choices, key=lambda item: item[:2])
                    near_reductions.append({"excluded_record_id": identifier, "representative_record_id": representative,
                                            "reason": "greedy_retained_representative_near_match", "pair_id": pair["pair_id"],
                                            "intersection": pair["intersection"], "union": pair["union"], "jaccard": pair["jaccard"]})
                    excluded.add(identifier)
                else:
                    representatives.append(identifier)
    ids = [feature["id"] for feature in features]
    return {
        "scope": "body_text", "shingle_tokens": n,
        "eligible_records": sum(bool(feature["usable"]) for feature in features),
        "nonempty_shingle_records": sum(bool(shingles) for shingles in sets),
        "exact_groups": exact, "near_status": "ok" if complete else "resource_limit",
        "candidate_pair_count": len(candidates), "candidate_count_is_lower_bound": not complete,
        "max_candidate_pairs": cfg["max_candidate_pairs"], "budget_complete": complete,
        "pairs": pairs, "connected_groups": _connected_groups(pairs, ids),
        "exact_reductions": exact_reductions, "near_reductions": near_reductions,
        "repeat_reduced_retained_ids": [identifier for identifier in ids if identifier not in excluded],
        "near_reduction_status": near_reduction_status,
        "matching_passage_method": "one_longest_contiguous_lexical_match_per_pair_v1",
    }
