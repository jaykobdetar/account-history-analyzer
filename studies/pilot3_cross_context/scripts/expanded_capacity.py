"""Score-free three-stratum choice for authorized expansion amendment 01.

This helper consumes account-ID sets only, never source prose or scores. The
returned assignment is a capacity witness, not a frozen cohort or leakage pass.
The initial census's study_math.py is intentionally unmodified.
"""
from __future__ import annotations

from itertools import combinations
from typing import Mapping

from study_math import maximum_disjoint_capacity


VERSION = "pilot3-expanded-capacity-v1"
ACCOUNT_QUOTA = 20
MAX_PAIR_STRATA = 28


def _capped_union_count(sets, cap):
    """Exact union cardinality up to the largest quota that could consume it."""
    if any(len(values) >= cap for values in sets):
        return cap
    return min(cap, len(set().union(*sets)))


def _hall_bounds(sets):
    """All seven exact Hall capacities, capped only above possible demand."""
    singles = tuple(min(ACCOUNT_QUOTA, len(values)) for values in sets)
    pairs = tuple(_capped_union_count((sets[a], sets[b]), 2 * ACCOUNT_QUOTA)
                  for a, b in ((0, 1), (0, 2), (1, 2)))
    all_three = _capped_union_count(sets, 3 * ACCOUNT_QUOTA)
    return singles, pairs, all_three


def _full_target_feasible(sets):
    # Short circuit before constructing unions for deficient individual strata.
    if any(len(values) < ACCOUNT_QUOTA for values in sets):
        return False
    for a, b in ((0, 1), (0, 2), (1, 2)):
        if _capped_union_count((sets[a], sets[b]), 2 * ACCOUNT_QUOTA) < 2 * ACCOUNT_QUOTA:
            return False
    return _capped_union_count(sets, 3 * ACCOUNT_QUOTA) == 3 * ACCOUNT_QUOTA


def _even(value):
    return 2 * (value // 2)


def _account_upper_bound(bounds):
    singles, (pair01, pair02, pair12), all_three = bounds
    a, b, c = map(_even, singles)
    return min(a + b + c, _even(all_three),
               _even(pair01) + c, _even(pair02) + b, _even(pair12) + a)


def _best_quotas(bounds):
    """Exact optimal even quotas, eliminating the third enumeration dimension.

    For fixed q0 and q1, maximal feasible q2 is the even floor of the four
    remaining Hall bounds. A smaller q2 cannot improve any maximum-total tie.
    Tie ordering agrees with maximum_disjoint_capacity.
    """
    singles, (pair01, pair02, pair12), all_three = bounds
    best, best_key = (0, 0, 0), (0, (0, 0, 0), (0, 0, 0))
    for a in range(0, singles[0] + 1, 2):
        for b in range(0, min(singles[1], pair01 - a) + 1, 2):
            maximum_c = min(singles[2], pair02 - a, pair12 - b, all_three - a - b)
            if maximum_c < 0:
                continue
            quotas = (a, b, _even(maximum_c))
            key = (sum(quotas), tuple(sorted(quotas)), quotas)
            if key > best_key:
                best, best_key = quotas, key
    return best


def choose_three_strata(eligible_by_pair: Mapping[str, set[str]]) -> dict:
    """Select three pair strata under amendment 01's exact capacity priorities.

    Full-target triples: larger minimum raw pair capacity, then larger summed
    raw pair capacity, then ascending alphabetic pair names. If none can fill
    20 disjoint accounts in each stratum, first maximize complete blocks, then
    lexicographically maximize sorted ascending account quotas, then use the
    same raw-capacity and name tie rules. No smaller design is approved here.

    At most 28 pair strata (eight communities) are accepted. Fewer than three
    retain all supplied strata with feasible_target=False and an explicit reason.
    The expensive assignment helper is invoked once, on the selected triple.
    """
    if len(eligible_by_pair) > MAX_PAIR_STRATA:
        raise ValueError("Amendment 01 permits at most 28 community-pair strata")
    if any(not isinstance(pair, str) or not pair for pair in eligible_by_pair):
        raise ValueError("Pair identifiers must be nonempty strings")
    eligible = {pair: frozenset(accounts) for pair, accounts in eligible_by_pair.items()}
    if any(not isinstance(a, str) or not a for values in eligible.values() for a in values):
        raise ValueError("Account identifiers must be nonempty strings")
    names = sorted(eligible)
    triples = list(combinations(names, 3))
    feasible = []
    for triple in triples:
        if _full_target_feasible(tuple(eligible[pair] for pair in triple)):
            counts = [len(eligible[pair]) for pair in triple]
            feasible.append(((-min(counts), -sum(counts), triple), triple))
    expected_quotas = None
    considered_fallback = pruned_fallback = 0
    if feasible:
        chosen = min(feasible)[1]
        selection_reason = "full_target_capacity_feasible_before_contamination_audit"
    elif len(names) < 3:
        chosen = tuple(names)
        selection_reason = "fewer_than_three_candidate_strata"
    else:
        chosen, best_key = None, None
        best_total = -1
        for triple in triples:
            sets = tuple(eligible[pair] for pair in triple)
            bounds = _hall_bounds(sets)
            if _account_upper_bound(bounds) < best_total:
                pruned_fallback += 1
                continue
            considered_fallback += 1
            quotas = _best_quotas(bounds)
            counts = [len(values) for values in sets]
            # min(key) implements descending scientific priorities and ascending names.
            key = (-sum(quotas), tuple(-q for q in sorted(quotas)),
                   -min(counts), -sum(counts), triple)
            if best_key is None or key < best_key:
                best_key, chosen, expected_quotas = key, triple, quotas
                best_total = sum(quotas)
        selection_reason = "full_target_infeasible_reduced_capacity_proposal_only"
    capacity = maximum_disjoint_capacity({pair: set(eligible[pair]) for pair in chosen},
                                         limit_per_stratum=ACCOUNT_QUOTA)
    if expected_quotas is not None and tuple(capacity["quota_counts"].values()) != expected_quotas:
        raise AssertionError("Independent quota shortcut disagrees with frozen allocator")
    full_target = len(chosen) == 3 and all(q == ACCOUNT_QUOTA for q in capacity["quota_counts"].values())
    if bool(feasible) != full_target:
        raise AssertionError("Hall target decision disagrees with actual disjoint assignment")
    return {"version": VERSION, "selected_pairs": list(chosen), "capacity": capacity,
            "feasible_target": full_target, "selection_reason": selection_reason,
            "selected_raw_pair_capacities": {pair: len(eligible[pair]) for pair in chosen},
            "candidate_pair_count": len(names), "candidate_triple_count": len(triples),
            "full_target_feasible_triple_count": len(feasible),
            "fallback_quota_triples_evaluated": considered_fallback,
            "fallback_triples_pruned_by_upper_bound": pruned_fallback,
            "target_accounts_per_stratum": ACCOUNT_QUOTA,
            "selection_role": "score_free_feasibility_proposal_not_final_cohort"}
