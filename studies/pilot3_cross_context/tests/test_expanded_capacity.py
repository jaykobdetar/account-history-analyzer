"""Synthetic account-set oracles for bounded score-free stratum expansion."""
from itertools import combinations
from pathlib import Path
import random
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import expanded_capacity as expansion
from study_math import maximum_disjoint_capacity


def unique(prefix, count):
    return {f"{prefix}-{i:03}" for i in range(count)}


def test_full_target_uses_disjoint_identity_not_three_raw_counts():
    shared = unique("same", 20)
    result = expansion.choose_three_strata({"XY": shared, "XZ": shared, "YZ": shared})
    assert not result["feasible_target"]
    assert result["capacity"]["total_blocks"] == 10
    assert sorted(result["capacity"]["quota_counts"].values()) == [6, 6, 8]
    assigned = [a for values in result["capacity"]["assigned"].values() for a in values]
    assert len(assigned) == len(set(assigned)) == 20
    assert result["full_target_feasible_triple_count"] == 0


def test_all_seven_hall_constraints_matter():
    first, second, third = unique("a", 20), unique("b", 20), unique("c", 19)
    # Each pair's union contains >=40; all three jointly have only 59 accounts.
    result = expansion.choose_three_strata({"XY": first | second, "XZ": second | third, "YZ": first | third})
    assert not result["feasible_target"]
    assert result["capacity"]["total_blocks"] == 29
    assert sorted(result["capacity"]["quota_counts"].values()) == [18, 20, 20]
    # An individually adequate pair union can itself prevent a 20/20 allocation.
    result = expansion.choose_three_strata({"XY": first, "XZ": first, "YZ": unique("d", 50)})
    assert not result["feasible_target"]
    assert result["capacity"]["total_blocks"] == 20


def test_full_triple_priority_minimum_then_sum_then_alphabetic_names():
    values = {"a": unique("a", 20), "b": unique("b", 25), "c": unique("c", 25),
              "d": unique("d", 30), "e": unique("e", 25)}
    result = expansion.choose_three_strata(values)
    assert result["feasible_target"]
    assert result["selected_pairs"] == ["b", "c", "d"]
    assert result["capacity"]["total_blocks"] == 30
    assert result["full_target_feasible_triple_count"] == 10
    assert result["fallback_quota_triples_evaluated"] == 0


def test_raw_minimum_cannot_outrank_actual_target_feasibility():
    shared = unique("common", 35)
    result = expansion.choose_three_strata({"a": shared, "b": shared, "c": shared,
        "x": unique("x", 20), "y": unique("y", 20), "z": unique("z", 20)})
    assert result["feasible_target"]
    # Two 35-account shared strata cannot jointly supply their required 40.
    assert result["selected_pairs"] == ["a", "x", "y"]


def test_reduced_design_total_blocks_precede_appealing_raw_capacities():
    shared = unique("shared", 20)
    result = expansion.choose_three_strata({"a": shared, "b": shared, "c": shared,
        "x": unique("x", 12), "y": unique("y", 12)})
    assert not result["feasible_target"]
    assert result["selected_pairs"] == ["a", "x", "y"]
    assert result["capacity"]["total_blocks"] == 22
    assert result["selection_reason"] == "full_target_infeasible_reduced_capacity_proposal_only"


def test_reduced_design_prioritizes_balanced_quotas_before_raw_counts():
    # Every triple can assign 40 accounts. a/b/c and a/b/d max out at
    # 10/10/20; a/c/d and b/c/d can balance 12/14/14. Alphabetic names
    # resolve the remaining tie between those two balanced triples.
    common = unique("shared", 20)
    extra = unique("extra", 20)
    values = {"a": common, "b": common, "c": extra, "d": (common | extra)}
    result = expansion.choose_three_strata(values)
    assert not result["feasible_target"]
    assert sorted(result["capacity"]["quota_counts"].values()) == [12, 14, 14]
    assert result["selected_pairs"] == ["a", "c", "d"]


def _oracle_choose(eligible):
    """Full enumeration through the separately frozen allocation implementation."""
    results = []
    for triple in combinations(sorted(eligible), 3):
        capacity = maximum_disjoint_capacity({key: eligible[key] for key in triple})
        counts = [len(eligible[key]) for key in triple]
        full = all(q == 20 for q in capacity["quota_counts"].values())
        key = (-capacity["total_blocks"], tuple(-q for q in sorted(capacity["quota_counts"].values())),
               -min(counts), -sum(counts), triple)
        results.append((full, key, triple, capacity))
    full = [row for row in results if row[0]]
    chosen = min(full or results, key=lambda row: row[1])
    return list(chosen[2]), chosen[3], bool(full)


def test_shortcut_matches_exhaustive_triple_and_quota_oracle():
    rng = random.Random(84711)
    for _ in range(35):
        eligible = {pair: {f"u{i}" for i in range(15) if rng.randrange(3)}
                    for pair in ("a", "b", "c", "d", "e")}
        expected_pairs, expected_capacity, full = _oracle_choose(eligible)
        actual = expansion.choose_three_strata(eligible)
        assert actual["selected_pairs"] == expected_pairs
        assert actual["capacity"] == expected_capacity
        assert actual["feasible_target"] == full


def test_input_order_and_set_iteration_do_not_change_results():
    eligible = {"a": unique("shared", 23), "b": unique("shared", 23),
                "c": unique("different", 14), "d": unique("another", 13)}
    original = expansion.choose_three_strata(eligible)
    reordered = {key: set(reversed(sorted(eligible[key]))) for key in reversed(list(eligible))}
    assert expansion.choose_three_strata(reordered) == original


def test_twenty_eight_pairs_call_expensive_allocator_only_once(monkeypatch):
    real = expansion.maximum_disjoint_capacity
    calls = []
    def spy(*args, **kwargs):
        calls.append(args)
        return real(*args, **kwargs)
    monkeypatch.setattr(expansion, "maximum_disjoint_capacity", spy)
    result = expansion.choose_three_strata({f"pair-{i:02}": unique("shared", 59) for i in range(28)})
    assert result["candidate_triple_count"] == 3276
    assert not result["feasible_target"]
    assert result["capacity"]["total_blocks"] == 29
    assert len(calls) == 1


def test_empty_and_fewer_than_three_pairs_are_explicitly_infeasible():
    result = expansion.choose_three_strata({})
    assert result["selected_pairs"] == []
    assert not result["feasible_target"]
    assert result["capacity"]["total_blocks"] == 0
    result = expansion.choose_three_strata({"XY": unique("x", 20), "XZ": unique("y", 20)})
    assert result["selected_pairs"] == ["XY", "XZ"]
    assert result["capacity"]["total_blocks"] == 20
    assert result["selection_reason"] == "fewer_than_three_candidate_strata"
    assert not result["feasible_target"]


def test_odd_counts_do_not_fabricate_half_blocks_and_bounds_are_enforced():
    result = expansion.choose_three_strata({"a": {"one"}, "b": {"two"}, "c": {"three"}})
    assert result["capacity"]["total_blocks"] == 0
    assert result["capacity"]["quota_counts"] == {"a": 0, "b": 0, "c": 0}
    with pytest.raises(ValueError):
        expansion.choose_three_strata({str(i): set() for i in range(29)})
    with pytest.raises(ValueError):
        expansion.choose_three_strata({"a": {""}})
