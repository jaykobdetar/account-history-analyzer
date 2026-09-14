"""Descriptive family-scaled L2 segmentation using the pinned PR #383 backport.

The exact upstream delayed-pruning method is isolated in _vendor. This wrapper
validates AHAS inputs and exports SSE plus a penalty per internal boundary.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from ._vendor.ruptures_pr383 import PeltMinSize

from .errors import InputError, ComputationError
from .io import digest
from .style import feature_values
from .text import function_words

OPTIMIZER = "ruptures_pelt_pr383_a28574d_v1"
OBJECTIVE = "sum_segment_within_segment_squared_euclidean_residuals_plus_beta_times_internal_change_count"
SURFACE_FEATURES = tuple(f"punctuation.{name}.per_1000_word_tokens" for name in (
    "comma", "period", "question_mark", "exclamation_mark", "semicolon", "colon",
    "ascii_apostrophe", "curly_apostrophe", "em_dash", "ellipsis",
)) + ("uppercase_fraction", "average_word_length")


def standardize(window_features: Sequence[Mapping[str, Any]], *, epsilon: float = 1e-12) -> dict[str, Any]:
    """Scale the prescribed surface/function coordinates over the complete stream.

    A missing value in any window excludes its coordinate. Population SD <=
    epsilon excludes a coordinate. Remaining z-scores divide by sqrt(retained
    coordinates in their family) and sqrt(nonempty families). No values are
    imputed. Feature order, means, SDs, divisors, exclusions and rows are retained.
    """
    if not math.isfinite(epsilon) or epsilon < 0:
        raise InputError("Scaling epsilon must be finite and nonnegative", code="invalid_scaling_epsilon")
    values = [feature_values(features) for features in window_features]
    family_order = {"surface": SURFACE_FEATURES,
                    "function": tuple(f"function_word.{word}.per_1000_word_tokens" for word in sorted(function_words()))}
    selected = []
    excluded = []
    for family, features in family_order.items():
        for feature_id in features:
            column = [row[feature_id] for row in values]
            if any(value is not None and not math.isfinite(value) for value in column):
                raise InputError("Nonfinite scaling coordinate", code="nonfinite_scaling_input", location=feature_id)
            if not column or any(value is None for value in column):
                excluded.append({"feature_id": feature_id, "family": family,
                                 "reason": "missing_in_some_windows" if column else "no_windows",
                                 "mean": None, "standard_deviation": None})
                continue
            array = np.asarray(column, dtype=np.float64)
            mean = float(np.mean(array))
            sd = float(np.std(array, ddof=0))
            if not math.isfinite(mean) or not math.isfinite(sd):
                raise ComputationError("Scaling arithmetic overflow", code="nonfinite_scaling_result")
            if sd <= epsilon:
                excluded.append({"feature_id": feature_id, "family": family,
                                 "reason": "standard_deviation_at_or_below_epsilon",
                                 "mean": mean, "standard_deviation": sd})
            else:
                selected.append((feature_id, family, mean, sd, array))
    family_counts = {family: sum(item[1] == family for item in selected) for family in family_order}
    nonempty = sum(count > 0 for count in family_counts.values())
    divisors = {family: math.sqrt(count) * math.sqrt(nonempty) if count else None for family, count in family_counts.items()}
    rows = np.empty((len(values), len(selected)), dtype=np.float64)
    for index, (_, family, mean, sd, column) in enumerate(selected):
        rows[:, index] = ((column - mean) / sd) / math.sqrt(family_counts[family]) / math.sqrt(nonempty)
    return {
        "feature_order": [item[0] for item in selected], "feature_families": [item[1] for item in selected],
        "means": [item[2] for item in selected], "standard_deviations": [item[3] for item in selected],
        "family_counts": family_counts, "nonempty_family_count": nonempty,
        "family_weight_divisors": divisors, "ddof": 0, "epsilon": epsilon,
        "excluded_features": excluded, "standardized_rows": rows.tolist(),
    }


def pelt_l2(sequence: Sequence[Sequence[float]] | Sequence[float], penalty: float, *, min_size: int = 3, jump: int = 1) -> dict[str, Any]:
    """Apply PR #383's exact optimizer with the AHAS objective convention.

    The private backport retains a dominated start until the witness can form
    a legal min_size segment. It uses strict upstream comparisons (no local
    pruning slack) and first-in-candidate-order ties. AHAS keeps jump=1.
    """
    if not isinstance(min_size, int) or isinstance(min_size, bool) or min_size < 1:
        raise InputError("Minimum segment size must be a positive integer", code="invalid_segment_size")
    if jump != 1 or isinstance(jump, bool):
        raise InputError("V1 segmentation uses jump=1", code="unsupported_segmentation_jump")
    if not isinstance(penalty, (int, float)) or isinstance(penalty, bool) or not math.isfinite(penalty) or penalty < 0:
        raise InputError("Penalty must be finite and nonnegative", code="invalid_segmentation_penalty")
    try:
        signal = np.asarray(sequence, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise InputError("Expected finite rectangular numerical sequence", code="invalid_segmentation_input") from exc
    if signal.ndim == 1:
        signal = signal.reshape(-1, 1)
    if signal.ndim != 2 or signal.shape[1] == 0 or not np.isfinite(signal).all():
        raise InputError("Expected nonempty finite feature dimension", code="invalid_segmentation_input")
    count = signal.shape[0]
    if count < min_size:
        raise InputError("Sequence is shorter than a legal segment", code="insufficient_segmentation_input")
    try:
        # The upstream method sums penalties per segment. Recompute the export
        # independently so the terminal endpoint never adds an AHAS penalty.
        with np.errstate(over="raise", invalid="raise"):
            # The public wrapper historically also accepts the numeric value
            # 1.0; the dependency's grid requires an integer range step.
            optimizer = PeltMinSize(model="l2", min_size=min_size, jump=1).fit(signal)
            endpoints = optimizer.predict(pen=float(penalty))
            starts = [0] + endpoints[:-1]
            sse = math.fsum(float(optimizer.cost.error(start, end))
                            for start, end in zip(starts, endpoints, strict=True))
            internal = endpoints[:-1]
            objective = sse + penalty * len(internal)
    except (FloatingPointError, OverflowError) as exc:
        raise ComputationError("Segmentation cost overflow", code="nonfinite_segmentation_objective") from exc
    if not math.isfinite(sse) or not math.isfinite(objective):
        raise ComputationError("Segmentation cost overflow", code="nonfinite_segmentation_objective")
    return {"internal_boundaries": internal, "endpoints": endpoints, "sse": sse,
            "objective": objective, "optimizer": OPTIMIZER,
            "min_size": min_size, "jump": jump}



def analyze_changes(stream: Mapping[str, Any], windows: Sequence[Mapping[str, Any]], config: Any,
                    *, penalty_lambda: float | None = None) -> dict[str, Any]:
    """Segment qualified windows and map boundaries to their actual source ranges.

    At least eight qualified windows are required before scaling/optimization.
    Remainders never participate. The returned interval spans the last record on
    the left and first record on the right; it is not an inferred event timestamp.
    """
    qualified = sorted((window for window in windows if window["stream_id"] == stream["stream_id"] and window["qualified"]),
                       key=lambda window: window["first_record_position"])
    multiplier = config["changes"]["primary_lambda"] if penalty_lambda is None else penalty_lambda
    if not isinstance(multiplier, (int, float)) or isinstance(multiplier, bool) or not math.isfinite(multiplier) or multiplier <= 0:
        raise InputError("Penalty lambda must be finite and positive", code="invalid_penalty_lambda")
    min_size = config["changes"]["minimum_segment_windows"]
    result = {"stream_id": stream["stream_id"], "window_ids": [window["window_id"] for window in qualified],
              "status": "insufficient_data", "reason_codes": ["fewer_than_required_qualified_windows"],
              "scaling": None, "penalty_lambda": multiplier, "penalty_beta": None,
              "objective": None, "sse": None, "internal_boundaries": [], "boundaries": [],
              "optimizer": OPTIMIZER, "min_size": min_size, "jump": config["changes"]["jump"],
              "objective_definition": OBJECTIVE}
    if len(qualified) < max(config["changes"]["minimum_windows"], min_size):
        return result
    scaling = standardize([window["features"] for window in qualified], epsilon=config["changes"]["scale_epsilon"])
    beta = multiplier * math.log(len(qualified))
    if not math.isfinite(beta):
        raise InputError("Penalty lambda produces a nonfinite penalty", code="invalid_penalty_lambda")
    result.update(scaling=scaling, penalty_beta=beta)
    if not scaling["feature_order"]:
        result.update(status="no_measurable_variation", reason_codes=["no_nonconstant_complete_dimensions"])
        return result
    segmented = pelt_l2(scaling["standardized_rows"], result["penalty_beta"], min_size=min_size, jump=config["changes"]["jump"])
    result.update(status="ok", reason_codes=[], objective=segmented["objective"], sse=segmented["sse"],
                  internal_boundaries=segmented["internal_boundaries"])
    for index in segmented["internal_boundaries"]:
        left, right = qualified[index - 1], qualified[index]
        boundary = {
            "window_index": index, "left_window_id": left["window_id"], "right_window_id": right["window_id"],
            "left_record_id": left["last_record_id"], "right_record_id": right["first_record_id"],
            "left_utc": left["last_utc"], "right_utc": right["first_utc"],
            "left_window_first_utc": left["first_utc"], "left_window_last_utc": left["last_utc"],
            "right_window_first_utc": right["first_utc"], "right_window_last_utc": right["last_utc"],
            "record_interval": [left["last_record_position"], right["first_record_position"]],
            "left_window_record_ids": list(left["record_ids"]), "right_window_record_ids": list(right["record_ids"]),
        }
        boundary["boundary_id"] = "boundary_" + digest({"stream_id": stream["stream_id"], **boundary})[:24]
        result["boundaries"].append(boundary)
    return result
