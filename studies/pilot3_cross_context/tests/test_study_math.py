"""Synthetic oracles only; this file never opens study or reserve observations."""
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import importlib.util
from itertools import product
import json
from pathlib import Path
import random

import pytest


MODULE = Path(__file__).resolve().parents[1] / "scripts" / "study_math.py"
spec = importlib.util.spec_from_file_location("pilot3_study_math", MODULE)
maths = importlib.util.module_from_spec(spec)
spec.loader.exec_module(maths)


def test_all_sixteen_comparison_identities_and_disjoint_sides():
    rows = maths.comparison_design("sample-block")
    assert len(rows) == len({r["pair_id"] for r in rows}) == 16
    assert len({r["left_cell_id"] for r in rows} | {r["right_cell_id"] for r in rows}) == 8
    assert Counter(r["anchor_id"] for r in rows) == {"A/X": 4, "A/Y": 4, "B/X": 4, "B/Y": 4}
    assert Counter(r["category"] for r in rows) == {category: 4 for category in maths.CATEGORIES}
    assert Counter(r["label"] for r in rows) == {"same_author": 8, "different_author": 8}
    for row in rows:
        left_account, left_context, left_time = row["left_cell_id"].split("/")
        right_account, right_context, right_time = row["right_cell_id"].split("/")
        assert (left_time, right_time) == ("early", "late")
        assert row["left_cell_id"] != row["right_cell_id"]
        assert (left_account == right_account) == (row["label"] == "same_author")
        assert (left_context == right_context) == (row["context_condition"] == "within_community")
    anchor = {row["category"]: row["right_cell_id"] for row in rows if row["anchor_id"] == "A/X"}
    assert list(anchor.values()) == ["A/X/late", "B/X/late", "A/Y/late", "B/Y/late"]


@pytest.mark.parametrize("same,different,expected", [(0.2, 0.3, 1), (0.3, 0.2, 0),
    (0.3, 0.3, .5), (None, .5, None), (.5, None, None), (None, None, None),
    (.5, .5000000000000001, 1)])
def test_ordering_exact_ties_and_missing(same, different, expected):
    assert maths.ordering(same, different) == expected


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, "0.2"])
def test_invalid_numbers_are_not_silently_missing(bad):
    with pytest.raises(ValueError):
        maths.ordering(bad, .5)


def test_complete_four_anchor_primary_and_secondary_missingness():
    categories = maths.CATEGORIES
    rows = {anchor: dict(zip(categories, [0.2, 0.4, 0.5, cross]))
            for anchor, cross in zip(maths.ANCHORS, [.7, .4, .5, .8])}
    result = maths.block_outcomes(rows)
    assert result["cross_community"]["complete_block_score"] == .625
    assert result["within_community"]["complete_block_score"] == 1
    assert result["cross_minus_within_complete_block"] == -.375
    assert result["stress_different_same_over_same_cross"]["complete_block_score"] == 0
    rows["A/X"][categories[3]] = None
    result = maths.block_outcomes(rows)
    assert result["cross_community"]["complete_block_score"] is None
    assert result["cross_community"]["available_anchor_mean_secondary"] == .5
    assert result["cross_community"]["missing_anchors"] == ["A/X"]
    assert result["cross_minus_within_complete_block"] is None
    assert result["within_community"]["complete_block_score"] == 1
    del rows["B/Y"]
    assert maths.block_outcomes(rows)["cross_community"]["available_anchors"] == 2


def test_equal_stratum_macro_never_reweights_away_planned_missing_strata():
    assert maths.equal_stratum_macro({"XY": .5, "XZ": 1, "YZ": 0}, ["XY", "XZ", "YZ"])["value"] == .5
    result = maths.equal_stratum_macro({"XY": .5, "XZ": 1}, ["XY", "XZ", "YZ"])
    assert result["value"] is None
    assert result["missing_strata"] == ["YZ"]
    assert (result["available_strata"], result["planned_strata"]) == (2, 3)
    with pytest.raises(ValueError):
        maths.equal_stratum_macro({"extra": .5}, ["XY"])


def test_nested_omissions_against_independent_hex_fraction_reference():
    ids, salt = [f"source-{i}" for i in range(103)], "published-salt-v1"
    results = {arm: maths.omit_record_ids(ids, arm, salt) for arm in ("full", "hash75", "hash50", "middle50")}
    for arm, cutoff in (("hash75", Fraction(3, 4)), ("hash50", Fraction(1, 2))):
        expected = [identifier for identifier in ids if Fraction(int(sha256(f"{salt}:{identifier}".encode()).hexdigest(), 16), 2**256) < cutoff]
        assert results[arm] == expected
    assert set(results["hash50"]) <= set(results["hash75"]) <= set(results["full"])
    assert results["full"] == ids
    assert results["middle50"] == ids[:25] + ids[77:]
    assert ids == [f"source-{i}" for i in range(103)]
    assert len(results["hash50"]) < len(results["hash75"]) < len(ids)


@pytest.mark.parametrize("count,expected", [(0, []), (1, ["0"]), (2, ["1"]),
    (3, ["2"]), (4, ["0", "3"]), (5, ["0", "3", "4"])])
def test_middle_half_exact_rounding(count, expected):
    assert maths.omit_record_ids(list(map(str, range(count))), "middle50", "salt") == expected


def test_hash_omission_full_256bit_strict_boundary(monkeypatch):
    values = {"low": 2**255 - 1, "half": 2**255, "almost75": 3 * 2**254 - 1,
              "exact75": 3 * 2**254, "top": 2**256 - 1}
    class FakeHash:
        def __init__(self, data):
            self.value = values[data.decode().split(":")[1]]
        def digest(self):
            return self.value.to_bytes(32, "big")
    monkeypatch.setattr(maths, "sha256", FakeHash)
    ids = list(values)
    assert maths.omit_record_ids(ids, "hash50", "salt") == ["low"]
    assert maths.omit_record_ids(ids, "hash75", "salt") == ["low", "half", "almost75"]


def test_no_extra_arm_or_duplicate_source_records():
    with pytest.raises(ValueError):
        maths.omit_record_ids(["same", "same"], "full", "salt")
    with pytest.raises(ValueError):
        maths.omit_record_ids(["id"], "adaptive_refill", "salt")


def test_ranking_tie_groups_noninterpolated_ap_and_denominators():
    rows = [(.9, "different_author"), (.7, "same_author"), (.7, "different_author"),
            (.1, "same_author"), (None, "different_author")]
    result = maths.rank_metrics(rows)
    assert result["roc_auc"] == .875
    assert result["average_precision"] == float(Fraction(5, 6))
    assert (result["planned_pairs"], result["qualified_pairs"], result["abstained_pairs"]) == (5, 4, 1)
    assert result["planned_class_counts"] == {"different_author": 3, "same_author": 2}
    assert result["qualified_class_counts"] == {"different_author": 2, "same_author": 2}
    assert maths.rank_metrics(list(reversed(rows))) == result
    assert maths.rank_metrics([(.5, "different_author"), (.5, "same_author")])["average_precision"] == .5


def test_ranking_empty_and_single_class_semantics():
    assert maths.rank_metrics([])["roc_auc"] is None
    assert maths.rank_metrics([])["average_precision"] is None
    all_positive = maths.rank_metrics([(.2, "different_author")])
    assert all_positive["roc_auc"] is None and all_positive["average_precision"] == 1
    all_negative = maths.rank_metrics([(.2, "same_author")])
    assert all_negative["roc_auc"] is None and all_negative["average_precision"] is None
    with pytest.raises(ValueError):
        maths.rank_metrics([(.2, "same_person")])


def _brute_capacity(eligible, cap):
    """Assign each synthetic account to every possible stratum or none."""
    strata = sorted(eligible)
    accounts = sorted(set().union(*eligible.values()))
    choices = [[None] + [s for s in strata if a in eligible[s]] for a in accounts]
    best = (0, tuple(0 for _ in strata), tuple(0 for _ in strata))
    for assignment in product(*choices):
        counts = Counter(assignment)
        quotas = tuple(counts[s] for s in strata)
        if any(q > cap or q % 2 for q in quotas):
            continue
        best = max(best, (sum(quotas), tuple(sorted(quotas)), quotas))
    return best[-1]


def test_allocator_can_reroute_overlap_and_retains_even_complete_blocks():
    eligible = {"XY": {"a", "b", "c", "d"}, "XZ": {"a", "b"}, "YZ": {"e", "f", "g"}}
    result = maths.maximum_disjoint_capacity(eligible, limit_per_stratum=2)
    assert result["quota_counts"] == {"XY": 2, "XZ": 2, "YZ": 2}
    assert result["assigned"]["XY"] == ["c", "d"]
    assert result["assigned"]["XZ"] == ["a", "b"]
    assert result["total_blocks"] == 3
    assert maths.maximum_disjoint_capacity({"XY": {"a", "b", "c"}})["total_blocks"] == 1
    assert maths.maximum_disjoint_capacity({})["total_blocks"] == 0


def test_allocator_matches_independent_exhaustive_account_assignment_oracle():
    rng = random.Random(91173)
    for _ in range(35):
        eligible = {s: {f"a{i}" for i in range(6) if rng.randrange(2)} for s in ["XY", "XZ", "YZ"]}
        cap = rng.choice([2, 3, 4, 6])
        result = maths.maximum_disjoint_capacity(eligible, cap)
        assert tuple(result["quota_counts"].values()) == _brute_capacity(eligible, cap)
        assigned = [a for values in result["assigned"].values() for a in values]
        assert len(assigned) == len(set(assigned)) == result["total_accounts"]
        for stratum, values in result["assigned"].items():
            assert set(values) <= eligible[stratum]
            assert len(values) == result["quota_counts"][stratum]
        reverse_input = {s: set(reversed(sorted(eligible[s]))) for s in reversed(list(eligible))}
        assert maths.maximum_disjoint_capacity(reverse_input, cap) == result


def _average(rows):
    return sum(Fraction(row["value"]) for row in rows) / len(rows) if rows else None


def test_bootstrap_ten_thousand_draws_against_independent_reference():
    blocks = {f"b{i}": [{"value": Fraction(i, 4)}] for i in range(5)}
    result = maths.clustered_block_bootstrap(blocks, _average)
    assert result["executed_repetitions"] == 10_000
    assert result["estimate"] == .5
    # Independent direct SHA256 construction and integer sums, without helper calls.
    totals, digest = [], sha256()
    for replicate in range(10_000):
        draws = []
        for draw in range(5):
            payload = '["sha256-json-counter-rejection-v1","ahas-pilot3-cross-context-block-bootstrap-v1",' + str(replicate) + ',' + str(draw) + ',0]'
            integer = int(sha256(payload.encode()).hexdigest(), 16)
            assert integer < 2**256 - (2**256 % 5)  # No rejection in this fixture.
            draws.append(integer % 5)
        totals.append(sum(draws))
        digest.update((json.dumps(["b" + str(i) for i in draws], separators=(",", ":")) + "\n").encode())
    totals.sort()
    # The registered type-7 positions are 249.975 and 9749.025 for 10,000.
    low = (Fraction(totals[249], 20) * Fraction(1, 40) + Fraction(totals[250], 20) * Fraction(39, 40))
    high = (Fraction(totals[9749], 20) * Fraction(39, 40) + Fraction(totals[9750], 20) * Fraction(1, 40))
    assert result["percentile_interval_95"] == [float(low), float(high)]
    assert result["draws_sha256"] == digest.hexdigest()
    reordered = dict(reversed(list(blocks.items())))
    assert maths.clustered_block_bootstrap(reordered, _average) == result


def test_counter_rejects_modulo_bias_tail(monkeypatch):
    seen = []
    class FakeHash:
        def __init__(self, data):
            seen.append(json.loads(data))
        def digest(self):
            return ((2**256 - 1) if len(seen) == 1 else 8).to_bytes(32, "big")
    monkeypatch.setattr(maths, "sha256", FakeHash)
    assert maths._counter_index(3, "seed", 5, 9) == 2
    assert seen == [[maths.BOOTSTRAP_VERSION, "seed", 5, 9, 0], [maths.BOOTSTRAP_VERSION, "seed", 5, 9, 1]]


def test_merged_units_keep_all_blocks_arms_and_methods_together():
    blocks = {f"b{i}": [{"block": f"b{i}", "row": j, "value": i} for j in range(12)] for i in range(6)}
    groups = {f"b{i}": f"g{max(0, i - 1)}" for i in range(6)}
    samples = []
    def check(rows):
        counts = Counter(row["block"] for row in rows)
        assert counts["b0"] == counts["b1"]
        assert all(count % 12 == 0 for count in counts.values())
        for block in counts:
            assert len({r["row"] for r in rows if r["block"] == block}) == 12
        samples.append(counts)
        return _average(rows)
    result = maths.clustered_block_bootstrap(blocks, check, group_by_block=groups,
        stratum_by_block={f"b{i}": "XY" if i < 3 else "YZ" for i in range(6)}, repetitions=100)
    assert result["independent_unit_count"] == 5
    assert result["block_count"] == 6
    assert result["stratum_block_counts"] == {"XY": 3, "YZ": 3}
    assert len(samples) == 101
    assert result["group_memberships"]["g0"] == ["b0", "b1"]


def test_too_few_independent_units_descriptive_only_and_no_missing_replicate_drop():
    blocks = {f"b{i}": [{"value": i}] for i in range(5)}
    groups = {f"b{i}": "g0" if i < 2 else f"g{i}" for i in range(5)}
    result = maths.clustered_block_bootstrap(blocks, _average, group_by_block=groups)
    assert result["independent_unit_count"] == 4
    assert result["estimate"] == 2
    assert result["percentile_interval_95"] is None
    assert result["executed_repetitions"] == 0
    def needs_every_stratum(rows):
        values = {str(row["value"]): row["value"] for row in rows}
        return maths.equal_stratum_macro(values, list(map(str, range(5))))["value"]
    result = maths.clustered_block_bootstrap(blocks, needs_every_stratum, repetitions=100)
    assert result["estimate"] == 2
    assert result["missing_replicates"] > 0
    assert result["percentile_interval_95"] is None
    assert result["reason"] == "missing_bootstrap_statistics_no_silent_reweighting"
    with pytest.raises(ValueError):
        maths.clustered_block_bootstrap(blocks, _average, group_by_block={"b0": "g0"})
