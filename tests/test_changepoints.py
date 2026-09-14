"""WIN-05/06/07/08/09 plus exhaustive independent penalized-L2 oracles."""
from __future__ import annotations

import itertools
import json
import math
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from ruptures import Pelt

from account_history_analyzer.changepoints import SURFACE_FEATURES, analyze_changes, pelt_l2, standardize
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.errors import InputError
from account_history_analyzer.registry import PUNCTUATION
from account_history_analyzer.text import function_words

ROOT = Path(__file__).resolve().parents[1]
CONFIG = AnalysisConfig.from_toml()


def independent_sse(sequence, start, end):
    segment = sequence[start:end]
    dimensions = len(segment[0])
    total = 0.0
    for dimension in range(dimensions):
        column = [row[dimension] for row in segment]
        mean = math.fsum(column) / len(column)
        total += math.fsum((value - mean) ** 2 for value in column)
    return total


def partition_objective(sequence, ends, penalty):
    return math.fsum(independent_sse(sequence, start, end) for start, end in zip([0] + ends[:-1], ends)) + penalty * (len(ends) - 1)


def exhaustive_oracle(sequence, penalty, minimum):
    n = len(sequence)
    possibilities = []
    for count in range(n):
        for internal in itertools.combinations(range(1, n), count):
            ends = list(internal) + [n]
            if all(end - start >= minimum for start, end in zip([0] + ends[:-1], ends)):
                possibilities.append(partition_objective(sequence, ends, penalty))
    return min(possibilities)


def dynamic_programming_oracle(sequence, penalty, minimum):
    n = len(sequence)
    # Independent unpruned recurrence uses internal-boundary penalty directly.
    values = [None] * (n + 1)
    values[0] = 0.0
    for end in range(minimum, n + 1):
        possibilities = []
        for start in range(end - minimum + 1):
            if values[start] is not None:
                possibilities.append(values[start] + independent_sse(sequence, start, end) + (penalty if start else 0))
        values[end] = min(possibilities)
    return values[n]


def test_NUM_PELT_supplied_unique_optimum_and_terminal_endpoint():
    oracle = json.loads((ROOT / "fixtures/numerical_oracles.json").read_text())["pelt_unscaled_l2"]
    result = pelt_l2(oracle["series"], oracle["penalty_per_internal_change"], min_size=3, jump=1)
    assert result["internal_boundaries"] == [4]
    assert result["endpoints"] == [4, 8]
    assert result["objective"] == 1
    assert result["sse"] == 0
    assert partition_objective([[v] for v in oracle["series"]], [8], 1) == 200


def test_regression_pinned_library_prunes_before_replacement_segment_is_legal():
    sequence = [[0.0], [9.0], [2.0], [8.0], [3.0], [0.0], [10.0]]
    upstream = Pelt(model="l2", min_size=3, jump=1).fit(np.asarray(sequence)).predict(pen=.1)
    exact = exhaustive_oracle(sequence, .1, 3)
    # Captures the real observed upstream regression, rather than treating its
    # output as truth. Our registered control-flow correction retains SSE units.
    assert upstream == [4, 7]
    assert partition_objective(sequence, upstream, .1) > exact
    result = pelt_l2(sequence, .1)
    assert result["internal_boundaries"] == [3]
    assert result["objective"] == pytest.approx(107.51666666666667)
    assert result["objective"] == pytest.approx(exact)


def test_NUM_PELT_320_small_sequences_match_exhaustive_cost_not_tie_partition():
    rng = random.Random(719)
    for n in range(3, 11):
        for _ in range(10):
            sequence = [[rng.randrange(11)] for _ in range(n)]
            for penalty in (.1, 1, 5, 10):
                result = pelt_l2(sequence, penalty)
                assert result["objective"] == pytest.approx(exhaustive_oracle(sequence, penalty, 3), abs=1e-9)
                assert all(end - start >= 3 for start, end in zip([0] + result["endpoints"][:-1], result["endpoints"]))


def test_NUM_PELT_multivariate_longer_sequences_match_unpruned_DP():
    rng = random.Random(6183)
    for n in (11, 20, 50):
        sequence = [[rng.randrange(11), rng.randrange(7)] for _ in range(n)]
        for minimum in (1, 2, 3, 4):
            for penalty in (.1, 2.5, 10):
                result = pelt_l2(sequence, penalty, min_size=minimum)
                assert result["objective"] == pytest.approx(dynamic_programming_oracle(sequence, penalty, minimum), abs=1e-8)


def test_NUM_PELT_constant_positive_penalty_and_invalid_inputs():
    result = pelt_l2([4] * 10, 1)
    assert result["internal_boundaries"] == []
    assert result["objective"] == result["sse"] == 0
    for sequence in ([], [1, 2], [[1], [2, 3]], [1, float("nan"), 3], [[], [], []]):
        with pytest.raises(InputError):
            pelt_l2(sequence, 1)
    with pytest.raises(InputError):
        pelt_l2([1, 2, 3], -1)
    with pytest.raises(InputError):
        pelt_l2([1, 2, 3], 1, jump=2)


def summary(comma=0.0, uppercase=0.0, function_value=0.0):
    punctuation = {key: 0.0 for key in [*PUNCTUATION, "ascii_period_runs"]}
    punctuation["comma"] = comma
    functions = {word: 0.0 for word in function_words()}
    functions["the"] = function_value
    return {"rates": {"punctuation_per_1000_words": punctuation, "uppercase_fraction": uppercase, "average_word_length": 4.0}, "function_rates": functions}


def test_WIN_06_missing_and_zero_variance_coordinates_dropped_explicitly():
    rows = [summary(comma=value, uppercase=value / 10) for value in (1, 2, 3)]
    rows[1]["rates"]["uppercase_fraction"] = None
    result = standardize(rows)
    assert result["feature_order"] == ["punctuation.comma.per_1000_word_tokens"]
    excluded = {item["feature_id"]: item for item in result["excluded_features"]}
    assert excluded["uppercase_fraction"]["reason"] == "missing_in_some_windows"
    assert excluded["uppercase_fraction"]["mean"] is None
    assert excluded["average_word_length"]["reason"] == "standard_deviation_at_or_below_epsilon"
    assert result["family_counts"] == {"surface": 1, "function": 0}
    assert result["family_weight_divisors"] == {"surface": 1.0, "function": None}
    assert all(len(row) == 1 for row in result["standardized_rows"])
    tiny = standardize([summary(comma=value) for value in (0, 1e-13, 2e-13)])
    assert tiny["feature_order"] == []


def test_WIN_07_exact_population_scaling_and_family_coordinate_weights():
    result = standardize([summary(comma=value, uppercase=value / 10, function_value=value * 100) for value in (1, 2, 3)])
    assert len(SURFACE_FEATURES) == 12
    assert result["feature_order"] == ["punctuation.comma.per_1000_word_tokens", "uppercase_fraction", "function_word.the.per_1000_word_tokens"]
    assert result["family_counts"] == {"surface": 2, "function": 1}
    assert result["nonempty_family_count"] == 2
    assert result["means"] == pytest.approx([2, .2, 200])
    assert result["standard_deviations"] == pytest.approx([math.sqrt(2 / 3), math.sqrt(2 / 3) / 10, math.sqrt(2 / 3) * 100])
    expected_z = math.sqrt(3 / 2)
    assert result["standardized_rows"][0] == pytest.approx([-expected_z / 2, -expected_z / 2, -expected_z / math.sqrt(2)])
    assert result["standardized_rows"][1] == pytest.approx([0, 0, 0], abs=1e-15)
    assert result["standardized_rows"][2] == pytest.approx([expected_z / 2, expected_z / 2, expected_z / math.sqrt(2)])
    assert not any("OTHER_WORD" in name for name in result["feature_order"])
    assert not any("ascii_hyphen" in item["feature_id"] for item in result["excluded_features"])


def synthetic_windows(values):
    windows = []
    for i, value in enumerate(values):
        windows.append({"stream_id": "stream", "window_id": f"window{i}", "qualified": True,
                        "features": summary(comma=value), "record_ids": [f"record{i}a", f"record{i}b"],
                        "first_record_id": f"record{i}a", "last_record_id": f"record{i}b",
                        "first_record_position": 3 * i, "last_record_position": 3 * i + 1,
                        "first_utc": f"2025-01-01T00:{i:02}:00Z", "last_utc": f"2025-01-01T00:{i:02}:30Z"})
    return windows


def test_WIN_05_WIN_08_minimum_windows_and_constant_abstention():
    short = analyze_changes({"stream_id": "stream"}, synthetic_windows(range(7)), CONFIG)
    assert short["status"] == "insufficient_data"
    assert short["scaling"] is short["objective"] is short["penalty_beta"] is None
    constant = analyze_changes({"stream_id": "stream"}, synthetic_windows([1] * 8), CONFIG)
    assert constant["status"] == "no_measurable_variation"
    assert constant["scaling"]["feature_order"] == []
    assert constant["internal_boundaries"] == []
    assert constant["objective"] is None
    config = AnalysisConfig.from_mapping({"changes": {"minimum_segment_windows": 10}})
    impossible = analyze_changes({"stream_id": "stream"}, synthetic_windows(range(9)), config)
    assert impossible["status"] == "insufficient_data"
    # Even a no-variation early return cannot export Infinity from an otherwise
    # finite but impractically large supplied lambda.
    with pytest.raises(InputError, match="invalid_penalty_lambda"):
        analyze_changes({"stream_id": "stream"}, synthetic_windows([1] * 8), CONFIG, penalty_lambda=1e308)


def test_WIN_09_actual_boundary_mapping_retains_full_ranges_and_record_intervals():
    windows = synthetic_windows([0, 0, 0, 0, 10, 10, 10, 10])
    remainder = {**windows[-1], "window_id": "remainder", "qualified": False, "first_record_position": 99}
    result = analyze_changes({"stream_id": "stream"}, windows + [remainder], CONFIG)
    assert result["status"] == "ok"
    assert result["internal_boundaries"] == [4]
    assert result["penalty_beta"] == math.log(8)
    assert result["objective"] == pytest.approx(math.log(8))
    assert len(result["window_ids"]) == 8
    boundary = result["boundaries"][0]
    assert boundary["left_window_id"] == "window3" and boundary["right_window_id"] == "window4"
    assert boundary["left_record_id"] == "record3b" and boundary["right_record_id"] == "record4a"
    assert boundary["record_interval"] == [10, 12]
    assert boundary["left_utc"] == "2025-01-01T00:03:30Z"
    assert boundary["right_utc"] == "2025-01-01T00:04:00Z"
    assert boundary["left_window_record_ids"] == ["record3a", "record3b"]
    assert boundary["right_window_record_ids"] == ["record4a", "record4b"]


def test_OUT_09_PELT_separate_process_determinism():
    source = "from account_history_analyzer.changepoints import pelt_l2; from account_history_analyzer.io import canonical_bytes; import sys; sys.stdout.buffer.write(canonical_bytes(pelt_l2([0,9,2,8,3,0,10,7,3,1],.1)))"
    first = subprocess.run([sys.executable, "-c", source], capture_output=True, check=True).stdout
    second = subprocess.run([sys.executable, "-c", source], capture_output=True, check=True).stdout
    assert first == second
