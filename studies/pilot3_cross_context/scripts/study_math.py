"""Preparatory, evaluation-only arithmetic; no corpus loading or AHAS scoring.

These definitions are not a registration. A future scoring freeze must bind this
file and its tests. Account identifiers supplied to allocation are private data.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
import math
from typing import Callable, Mapping, Sequence


VERSION = "pilot3-study-math-v1"
BOOTSTRAP_VERSION = "sha256-json-counter-rejection-v1"
BOOTSTRAP_SEED = "ahas-pilot3-cross-context-block-bootstrap-v1"
HASH_SPACE = 1 << 256
ANCHORS = ("A/X", "A/Y", "B/X", "B/Y")
CATEGORIES = (
    "same_account_same_community", "different_account_same_community",
    "same_account_different_community", "different_account_different_community",
)


def _number(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, Fraction)):
        raise ValueError("Expected a finite numeric observation or None")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Nonfinite observations are not missing values")
    return Fraction(value)


def _mean(values):
    values = list(values)
    return sum(values, Fraction()) / len(values) if values else None


def _public(value):
    return float(value) if value is not None else None


def maximum_disjoint_capacity(eligible_by_pair: Mapping[str, set[str]],
                              limit_per_stratum: int = 20) -> dict:
    """Exactly maximize complete two-account blocks across up to three strata.

    Quotas count accounts and must be even. Among maximum-total allocations,
    maximize the sorted ascending quota vector (balanced/leximin quotas), then
    the quota vector in sorted stratum order. Hall's condition is exact for this
    account-to-stratum bipartite matching; deterministic flow assigns accounts.
    This is capacity accounting, not a final cohort-selection rule.
    """
    if type(limit_per_stratum) is not int or not 0 <= limit_per_stratum <= 100:
        raise ValueError("Account cap must be an integer from 0 to 100")
    strata = sorted(eligible_by_pair)
    if len(strata) > 3:
        raise ValueError("This bounded census allocator supports at most three strata")
    if any(not isinstance(key, str) or not key for key in strata):
        raise ValueError("Stratum identifiers must be nonempty strings")
    eligible = {key: set(eligible_by_pair[key]) for key in strata}
    if any(not isinstance(a, str) or not a for values in eligible.values() for a in values):
        raise ValueError("Account identifiers must be nonempty strings")
    hall = []
    for mask in range(1, 1 << len(strata)):
        selected = tuple(i for i in range(len(strata)) if mask & (1 << i))
        union = set().union(*(eligible[strata[i]] for i in selected))
        hall.append((selected, len(union)))
    ranges = [range(0, min(limit_per_stratum, len(eligible[s])) + 1, 2) for s in strata]
    best = tuple(0 for _ in strata)
    best_key = (0, tuple(sorted(best)), best)
    for quotas in product(*ranges):
        key = (sum(quotas), tuple(sorted(quotas)), quotas)
        if key <= best_key:
            continue
        if all(sum(quotas[i] for i in members) <= capacity for members, capacity in hall):
            best, best_key = quotas, key
    # Residual graph ordering is fixed by sorted identifiers, including reroutes.
    graph = defaultdict(list)
    remaining = {}

    def edge(left, right, capacity):
        graph[left].append(right)
        graph[right].append(left)
        remaining[left, right] = capacity
        remaining[right, left] = 0

    source, sink = ("source",), ("sink",)
    accounts = sorted(set().union(*eligible.values()) if eligible else set())
    for account in accounts:
        edge(source, ("account", account), 1)
        for stratum in strata:
            if account in eligible[stratum]:
                edge(("account", account), ("stratum", stratum), 1)
    for stratum, quota in zip(strata, best):
        edge(("stratum", stratum), sink, quota)
    total = 0
    while total < sum(best):
        parent = {source: None}
        queue = deque([source])
        while queue and sink not in parent:
            left = queue.popleft()
            for right in graph[left]:
                if right not in parent and remaining[left, right] > 0:
                    parent[right] = left
                    queue.append(right)
        if sink not in parent:
            raise AssertionError("Hall-feasible quotas failed flow assignment")
        right = sink
        while parent[right] is not None:
            left = parent[right]
            remaining[left, right] -= 1
            remaining[right, left] += 1
            right = left
        total += 1
    assigned = {s: [a for a in accounts if a in eligible[s]
                    and remaining[("stratum", s), ("account", a)] == 1] for s in strata}
    return {"quota_counts": dict(zip(strata, best)), "total_blocks": total // 2,
            "total_accounts": total, "assigned": assigned,
            "assignment_role": "capacity_witness_not_final_cohort_selection",
            "tie_rule": "maximum_accounts_then_leximin_quotas_then_sorted_stratum_quotas"}


def comparison_design(block_id: str = "block") -> list[dict]:
    """Return all 16 fixed identities over the block's eight symbolic cells."""
    if not isinstance(block_id, str) or not block_id:
        raise ValueError("block_id must be a nonempty string")
    rows = []
    for anchor in ANCHORS:
        account, community = anchor.split("/")
        other_account = "B" if account == "A" else "A"
        other_community = "Y" if community == "X" else "X"
        destinations = ((account, community), (other_account, community),
                        (account, other_community), (other_account, other_community))
        for category, (late_account, late_community) in zip(CATEGORIES, destinations):
            rows.append({"pair_id": f"{block_id}/{anchor}/{category}", "block_id": block_id,
                         "anchor_id": anchor, "left_cell_id": f"{anchor}/early",
                         "right_cell_id": f"{late_account}/{late_community}/late",
                         "category": category,
                         "context_condition": "within_community" if late_community == community else "cross_community",
                         "label": "same_author" if late_account == account else "different_author",
                         "label_meaning": "source_account_identity_proxy"})
    return rows


def ordering(same_distance, different_distance):
    """Return 1/0/0.5 when different is greater/less/equal; None if missing."""
    same, different = _number(same_distance), _number(different_distance)
    if same is None or different is None:
        return None
    return 1.0 if different > same else 0.0 if different < same else 0.5


def anchor_outcomes(distances: Mapping[str, float | None]) -> dict:
    if set(distances) - set(CATEGORIES):
        raise ValueError("Unknown comparison category")
    return {"cross_community": ordering(distances.get(CATEGORIES[2]), distances.get(CATEGORIES[3])),
            "within_community": ordering(distances.get(CATEGORIES[0]), distances.get(CATEGORIES[1])),
            "stress_different_same_over_same_cross": ordering(distances.get(CATEGORIES[2]), distances.get(CATEGORIES[1]))}


def block_outcomes(anchor_distances: Mapping[str, Mapping[str, float | None]]) -> dict:
    """Primary means require all four fixed anchors, even when keys are absent."""
    if set(anchor_distances) - set(ANCHORS):
        raise ValueError("Unknown early anchor")
    anchors = {key: anchor_outcomes(anchor_distances.get(key, {})) for key in ANCHORS}
    output = {"anchors": anchors, "planned_anchors": 4}
    for condition in ("cross_community", "within_community", "stress_different_same_over_same_cross"):
        observed = [_number(row[condition]) for row in anchors.values() if row[condition] is not None]
        output[condition] = {"complete_block_score": _public(_mean(observed)) if len(observed) == 4 else None,
                             "available_anchor_mean_secondary": _public(_mean(observed)),
                             "available_anchors": len(observed),
                             "missing_anchors": [key for key, row in anchors.items() if row[condition] is None]}
    cross = output["cross_community"]["complete_block_score"]
    within = output["within_community"]["complete_block_score"]
    output["cross_minus_within_complete_block"] = (cross - within if cross is not None and within is not None else None)
    return output


def equal_stratum_macro(values: Mapping[str, float | None], planned_strata: Sequence[str]) -> dict:
    if len(set(planned_strata)) != len(planned_strata) or not planned_strata:
        raise ValueError("Planned strata must be nonempty and distinct")
    if set(values) - set(planned_strata):
        raise ValueError("Unplanned stratum")
    observed = {s: _number(values.get(s)) for s in planned_strata}
    missing = [s for s, value in observed.items() if value is None]
    return {"value": None if missing else _public(_mean(observed.values())),
            "planned_strata": len(planned_strata), "available_strata": len(planned_strata) - len(missing),
            "missing_strata": missing, "reason": "planned_strata_missing" if missing else None}


def omit_record_ids(canonical_record_ids: Sequence[str], arm: str, salt: str) -> list[str]:
    """Input order is canonical chronology; output is an unchanged subsequence.

    hash75 retains 4*U < 3*2**256; hash50 retains 2*U < 2**256, with
    U=int(SHA256(UTF8(salt + ':' + original_id)),16). The arms are nested.
    """
    ids = list(canonical_record_ids)
    if len(ids) != len(set(ids)) or any(not isinstance(i, str) or not i for i in ids):
        raise ValueError("Original record IDs must be nonempty and unique")
    if not isinstance(salt, str) or not salt:
        raise ValueError("A published nonempty omission salt is required")
    if arm == "full":
        return ids
    if arm == "middle50":
        first, last = len(ids) // 4, (3 * len(ids)) // 4
        return ids[:first] + ids[last:]
    if arm not in {"hash75", "hash50"}:
        raise ValueError("Exactly full/hash75/hash50/middle50 arms are defined")
    multiplier, numerator = (4, 3) if arm == "hash75" else (2, 1)
    return [identifier for identifier in ids
            if multiplier * int.from_bytes(sha256((salt + ":" + identifier).encode("utf-8")).digest(), "big") < numerator * HASH_SPACE]


def rank_metrics(score_labels: Sequence[tuple[float | None, str]]) -> dict:
    """Independent pairwise AUC and exact rational, tied-group step AP."""
    labels = ("same_author", "different_author")
    planned, scored = Counter(), Counter()
    observed = []
    for score, label in score_labels:
        if label not in labels:
            raise ValueError("Expected evaluator enum label")
        planned[label] += 1
        value = _number(score)
        if value is not None:
            scored[label] += 1
            observed.append((value, label))
    positives = [s for s, label in observed if label == "different_author"]
    negatives = [s for s, label in observed if label == "same_author"]
    wins = sum((Fraction(1) if p > n else Fraction(1, 2) if p == n else Fraction())
               for p in positives for n in negatives)
    auc = wins / (len(positives) * len(negatives)) if positives and negatives else None
    groups = defaultdict(Counter)
    for score, label in observed:
        groups[score][label] += 1
    tp = seen = 0
    ap = Fraction()
    for score in sorted(groups, reverse=True):
        group = groups[score]
        newly_positive = group["different_author"]
        tp += newly_positive
        seen += sum(group.values())
        ap += Fraction(newly_positive * tp, seen)
    ap = ap / len(positives) if positives else None
    return {"planned_pairs": len(score_labels), "qualified_pairs": len(observed),
            "abstained_pairs": len(score_labels) - len(observed),
            "planned_class_counts": {label: planned[label] for label in labels},
            "qualified_class_counts": {label: scored[label] for label in labels},
            "roc_auc": _public(auc), "roc_auc_reason": None if auc is not None else "both_scored_labels_required",
            "average_precision": _public(ap), "average_precision_reason": None if ap is not None else "no_scored_positive_pairs",
            "positive_label": "different_author", "positive_label_meaning": "different_source_account_proxy"}


def _counter_index(size: int, seed: str, replicate: int, draw: int) -> int:
    """Unbiased rejection draw; each counter coordinate has an explicit identity."""
    ceiling = HASH_SPACE - HASH_SPACE % size
    attempt = 0
    while True:
        payload = json.dumps([BOOTSTRAP_VERSION, seed, replicate, draw, attempt],
                             ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        integer = int.from_bytes(sha256(payload).digest(), "big")
        if integer < ceiling:
            return integer % size
        attempt += 1


def _percentile(sorted_values: Sequence[Fraction], probability: Fraction) -> Fraction:
    """Type-7 linear interpolation, with exact rational index arithmetic."""
    index = (len(sorted_values) - 1) * probability
    lower = index.numerator // index.denominator
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (index - lower)


def clustered_block_bootstrap(
    block_rows: Mapping[str, Sequence[Mapping]],
    statistic: Callable[[Sequence[Mapping]], float | None], *,
    group_by_block: Mapping[str, str] | None = None,
    stratum_by_block: Mapping[str, str] | None = None,
    seed: str = BOOTSTRAP_SEED, repetitions: int = 10_000,
    minimum_independent_units: int = 5,
) -> dict:
    """Resample independent groups; all rows/methods/arms of a block stay together.

    Supply only blocks in the statistic's declared analysis set (e.g., its
    complete-block intersection), and audit connected dependency groups first.
    Blocks sharing a group are sampled together, including across strata. This
    is a global cluster bootstrap, not stratified resampling; original stratum
    counts and merged units are reported. Stratum-specific calls are preferred.
    A macro statistic must call equal_stratum_macro with all planned strata;
    missing macro replicates are reported and never silently discarded.
    """
    if type(repetitions) is not int or repetitions < 1:
        raise ValueError("repetitions must be a positive integer")
    if type(minimum_independent_units) is not int or minimum_independent_units < 5:
        raise ValueError("At least five independent units are required for an interval")
    if not isinstance(seed, str) or not seed:
        raise ValueError("seed must be a nonempty string")
    blocks = sorted(block_rows)
    if any(not isinstance(block, str) or not block or not block_rows[block] for block in blocks):
        raise ValueError("Block identifiers and their row lists must be nonempty")
    if group_by_block is not None and set(group_by_block) != set(blocks):
        raise ValueError("Dependency map must cover exactly every analysis block")
    if stratum_by_block is not None and set(stratum_by_block) != set(blocks):
        raise ValueError("Stratum map must cover exactly every analysis block")
    grouped = defaultdict(list)
    for block in blocks:
        group = block if group_by_block is None else group_by_block[block]
        if not isinstance(group, str) or not group:
            raise ValueError("Dependency identifiers must be nonempty strings")
        grouped[group].append(block)
    groups = sorted(grouped)
    all_rows = tuple(row for block in blocks for row in block_rows[block])
    point = _number(statistic(all_rows)) if all_rows else None
    result = {"generator": BOOTSTRAP_VERSION, "seed": seed, "arithmetic": "exact Fraction of finite binary-float inputs; type-7 percentiles",
              "resampling": "global_independent_group_with_replacement",
              "requested_repetitions": repetitions, "executed_repetitions": 0,
              "minimum_independent_units": minimum_independent_units,
              "independent_unit_count": len(groups), "block_count": len(blocks),
              "group_memberships": {g: grouped[g] for g in groups},
              "stratum_block_counts": dict(sorted(Counter(stratum_by_block.values()).items())) if stratum_by_block is not None else None,
              "estimate": _public(point), "percentile_interval_95": None,
              "missing_replicates": 0, "draws_sha256": None, "reason": None}
    if point is None:
        result["reason"] = "descriptive_statistic_unavailable"
        return result
    if len(groups) < minimum_independent_units:
        result["reason"] = "inadequate_independent_units_for_uncertainty"
        return result
    values, draw_hash = [], sha256()
    for replicate in range(repetitions):
        sampled = [groups[_counter_index(len(groups), seed, replicate, draw)] for draw in range(len(groups))]
        draw_hash.update((json.dumps(sampled, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
        rows = tuple(row for group in sampled for block in grouped[group] for row in block_rows[block])
        value = _number(statistic(rows))
        if value is None:
            result["missing_replicates"] += 1
        else:
            values.append(value)
    result.update(executed_repetitions=repetitions, draws_sha256=draw_hash.hexdigest())
    if result["missing_replicates"]:
        result["reason"] = "missing_bootstrap_statistics_no_silent_reweighting"
    else:
        values.sort()
        result["percentile_interval_95"] = [_public(_percentile(values, Fraction(1, 40))),
                                              _public(_percentile(values, Fraction(39, 40)))]
    return result
