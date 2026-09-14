"""Descriptive text representations and distances, independent of report/CLI code.

Numerical helpers work below product sample guards for arithmetic validation.
``compare_features`` always exposes sample context and keeps qualification apart
from calculable raw distances. No distance is an authorship probability.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import math
from typing import Any

from .config import AnalysisConfig
from .errors import ComputationError, InputError
from .features import pooled
from .io import thaw
from .registry import METHOD_VERSION, PUNCTUATION
from .text import LEXICAL_RE, function_words, normalized_token

NUMERICAL_TOLERANCE = 1e-12
REFERENCE_SIGMA_EPSILON = 1e-12


def _vector(values: Sequence[float], *, nonnegative: bool = True) -> list[float]:
    try:
        vector = [float(value) for value in values]
    except (TypeError, ValueError, OverflowError) as exc:
        raise InputError("Expected a finite numerical vector", code="invalid_vector") from exc
    if any(not math.isfinite(value) or (nonnegative and value < 0) for value in vector):
        raise InputError("Vector entries must be finite and nonnegative", code="invalid_vector")
    return vector


def _matching_vectors(left: Sequence[float], right: Sequence[float]) -> tuple[list[float], list[float]]:
    x, y = _vector(left), _vector(right)
    if len(x) != len(y):
        raise InputError("Compared vectors have different coordinate counts", code="incompatible_vectors")
    return x, y


def _clamp_excursion(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    if value < lower:
        if lower - value <= NUMERICAL_TOLERANCE:
            return lower
        raise ComputationError("Numerical value fell outside its mathematical range", code="numerical_range_error")
    if value > upper:
        if value - upper <= NUMERICAL_TOLERANCE:
            return upper
        raise ComputationError("Numerical value exceeded its mathematical range", code="numerical_range_error")
    return value


def cosine_distance(left: Sequence[float], right: Sequence[float]) -> float | None:
    """Cosine distance for nonnegative finite vectors; either zero norm → None.

    Each vector is rescaled by its maximum to avoid overflow. Sorted coordinate
    alignment belongs to the caller; deterministic ``math.fsum`` reductions are
    used. Only impossible excursions of at most 1e-12 are clamped.
    """
    x, y = _matching_vectors(left, right)
    maximum_x, maximum_y = max(x, default=0), max(y, default=0)
    if maximum_x == 0 or maximum_y == 0:
        return None
    if x == y:
        return 0.0
    x = [value / maximum_x for value in x]
    y = [value / maximum_y for value in y]
    dot = math.fsum(a * b for a, b in zip(x, y, strict=True))
    norms = math.sqrt(math.fsum(a * a for a in x)) * math.sqrt(math.fsum(b * b for b in y))
    return _clamp_excursion(1.0 - dot / norms)


def js_contributions(left: Sequence[float], right: Sequence[float]) -> list[float] | None:
    """Base-2 category contributions to divergence, before square root.

    Nonnegative vectors are normalized by their total masses, matching SciPy's
    distribution interface. Either zero mass returns None; no pseudocounts are
    added. Contributions are nonnegative except clamped tiny roundoff excursions.
    """
    x, y = _matching_vectors(left, right)
    # Max rescaling handles large finite user vectors without overflowing totals.
    mx, my = max(x, default=0), max(y, default=0)
    if mx == 0 or my == 0:
        return None
    x, y = [value / mx for value in x], [value / my for value in y]
    sx, sy = math.fsum(x), math.fsum(y)
    p, q = [value / sx for value in x], [value / sy for value in y]
    result = []
    for a, b in zip(p, q, strict=True):
        if not a or not b:
            # With a one-sided category log2(2)=1 exactly. Avoid midpoint
            # underflow for the smallest positive subnormal category mass.
            value = 0.5 * (a + b)
        else:
            midpoint = (a + b) / 2
            value = math.fsum((0.5 * a * math.log2(a / midpoint),
                               0.5 * b * math.log2(b / midpoint)))
        result.append(_clamp_excursion(value))
    return result


def jensen_shannon(left: Sequence[float], right: Sequence[float]) -> float | None:
    """Square-root Jensen–Shannon distance with logarithm base 2, or None."""
    contributions = js_contributions(left, right)
    return math.sqrt(_clamp_excursion(math.fsum(contributions))) if contributions is not None else None


def chargrams(segments: Sequence[str], n: int) -> Counter[str]:
    """Count overlapping case-sensitive n-code-point strings within segments."""
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise InputError("Character n-gram length must be a positive integer", code="invalid_ngram_length")
    return Counter(segment[index:index+n] for segment in segments for index in range(len(segment)-n+1))


def classic_delta(left: Sequence[float], right: Sequence[float], reference: Mapping[str, Any] | None,
                  *, frequency_unit: str = "per_1000_word_tokens", allow_toy_reference: bool = False) -> dict[str, Any]:
    """Classic Delta with a validated externally frozen reference.

    Missing reference is a normal not-run result. Toy use needs an explicit test
    override. Coordinates with sigma <= 1e-12 are excluded, never replaced by 1.
    No means, deviations or vocabulary are learned from compared texts.
    """
    empty = {"status": "not_run", "reason": "not_run_missing_reference", "value": None,
             "reference_id": None, "reference_kind": None, "excluded_coordinates": [], "contributions": []}
    if reference is None:
        return empty
    from .schemas import validate
    validate(thaw(reference), "delta_reference", location="delta reference")
    if frequency_unit != reference["frequency_unit"]:
        raise InputError("Delta frequencies and reference use incompatible units", code="incompatible_frequency_unit")
    if reference["reference_kind"] == "toy" and not allow_toy_reference:
        raise InputError("Toy reference requires explicit test override", code="toy_reference_forbidden")
    x, y = _matching_vectors(left, right)
    means = _vector(reference["means"])
    deviations = _vector(reference["standard_deviations"])
    vocabulary = reference["vocabulary"]
    if any(LEXICAL_RE.fullmatch(word) is None or word.isdigit() or word != normalized_token(word) for word in vocabulary):
        raise InputError("Delta vocabulary must contain normalized word tokens", code="invalid_reference_vocabulary")
    if len(x) != len(vocabulary) or len(means) != len(vocabulary) or len(deviations) != len(vocabulary):
        raise InputError("Delta vectors and reference have incompatible lengths", code="incompatible_reference_lengths")
    contributions = []
    excluded = []
    for word, a, b, mean, sigma in zip(vocabulary, x, y, means, deviations, strict=True):
        if sigma <= REFERENCE_SIGMA_EPSILON:
            excluded.append(word)
            continue
        # The identical reference mean cancels algebraically. Subtracting
        # frequencies first avoids catastrophic cancellation for large means;
        # this is the classic absolute z-difference, not a Delta variant.
        difference = abs(a - b) / sigma
        if not math.isfinite(difference):
            raise ComputationError("Delta standardization overflowed", code="nonfinite_delta")
        contributions.append({"feature_id": f"reference_word.{word}", "left_rate": a, "right_rate": b,
                              "absolute_rate_change": abs(a - b), "contribution": difference,
                              "contribution_kind": "absolute_standardized_difference", "left_count": None, "right_count": None})
    contributions.sort(key=lambda item: (-item["contribution"], item["feature_id"]))
    return {"status": "ok" if contributions else "not_computable",
            "reason": None if contributions else "no_valid_reference_coordinates",
            "value": math.fsum(item["contribution"] for item in contributions) / len(contributions) if contributions else None,
            "reference_id": reference["reference_id"], "reference_kind": reference["reference_kind"],
            "excluded_coordinates": excluded, "contributions": contributions}


def feature_values(record_or_pooled: Mapping[str, Any]) -> dict[str, float | None]:
    """Return registry-named pooled/record rates for evidence and scaling.

    These are explicit values, with None preserved; no missing-rate imputation
    occurs. Function-word rates use only the English scope's word denominator.
    """
    result = {f"punctuation.{name}.per_1000_word_tokens": value
              for name, value in record_or_pooled["rates"]["punctuation_per_1000_words"].items()}
    result.update({name: record_or_pooled["rates"][name] for name in ("uppercase_fraction", "average_word_length")})
    result.update({f"function_word.{word}.per_1000_word_tokens": value
                   for word, value in record_or_pooled["function_rates"].items()})
    return dict(sorted(result.items()))


def feature_units() -> dict[str, str]:
    """Units corresponding to every key returned by :func:`feature_values`."""
    result = {f"punctuation.{name}.per_1000_word_tokens": "per_1000_word_tokens"
              for name in (*PUNCTUATION, "ascii_period_runs")}
    result.update({"uppercase_fraction": "fraction", "average_word_length": "alphabetic_codepoints_per_word"})
    result.update({f"function_word.{word}.per_1000_word_tokens": "per_1000_word_tokens" for word in function_words()})
    return dict(sorted(result.items()))


def _sample(records: Sequence[Mapping[str, Any]], config: AnalysisConfig) -> dict[str, Any]:
    summary = pooled(records, config)
    eligible = [record for record in records if record["usable"] and record["language"] == "en"
                and record["counts"]["retained_words"] >= config["style"]["minimum_record_words"]]
    communities: dict[str | None, list[Mapping[str, Any]]] = {}
    for record in records:
        communities.setdefault(record["subreddit"], []).append(record)
    largest = max((record["counts"]["retained_words"] or 0 for record in records), default=0)
    return {"record_count": len(records), "word_count": summary["counts"]["retained_words"],
            "eligible_record_count": len(eligible), "eligible_word_count": sum(record["counts"]["retained_words"] for record in eligible),
            "usable_record_count": summary["usable_record_count"],
            "missing_timestamps": sum(record["created_utc"] is None for record in records),
            "kinds": sorted({record["kind"] for record in records}),
            "languages": sorted({record["language"] for record in records}),
            "community_distribution": [{"subreddit": community, "record_count": len(group),
                                         "word_count": sum(record["counts"]["retained_words"] or 0 for record in group)}
                                        for community, group in sorted(communities.items(), key=lambda item: (item[0] is not None, item[0] or ""))],
            "edit_state_counts": {state: sum(record["edit_state"] == state for record in records) for state in ("edited", "not_edited", "unknown")},
            "length": summary["words_per_record"],
            "largest_record_share": largest / summary["counts"]["retained_words"] if summary["counts"]["retained_words"] else None}


def _distance(method_id: str, view: str, n: int | None, unit: str, rate_unit: str,
              left_denominator: int, right_denominator: int, denominator_unit: str) -> dict[str, Any]:
    return {"method_id": method_id, "method_version": METHOD_VERSION, "view": view, "n": n,
            "status": "not_computable", "reason": "empty_representation", "value": None,
            "unit": unit, "rate_unit": rate_unit, "left_denominator": left_denominator,
            "right_denominator": right_denominator, "denominator_unit": denominator_unit,
            "reference_id": None, "reference_kind": None, "excluded_coordinates": [], "contributions": []}


def _segments(records: Sequence[Mapping[str, Any]], view: str) -> list[str]:
    if view == "function_mask_v1":
        return [value for record in records if record["usable"] for value in record["masked_segments"]]
    return [segment["text"] for record in records if record["usable"] for segment in record["segments"]]


def _word_counts(records: Sequence[Mapping[str, Any]]) -> Counter[str]:
    return Counter(word for record in records if record["usable"] for segment in record["word_tokens"] for word in segment)


def compare_features(left: Sequence[Mapping[str, Any]], right: Sequence[Mapping[str, Any]],
                     config: AnalysisConfig) -> dict[str, Any]:
    """Compare selected supplied text, with qualified status and complete context.

    Raw distances use all usable text in each supplied selection. Qualification
    additionally requires the configured number/word guards on English records
    meeting the record minimum, and a single matching kind/language scope. Missing
    timestamps are allowed for manual pooled comparisons and reported explicitly;
    chronological-window construction enforces its separate timestamp guard.
    """
    samples = {"left": _sample(left, config), "right": _sample(right, config)}
    reasons = []
    for side in ("left", "right"):
        sample = samples[side]
        if (sample["eligible_record_count"] < config["style"]["minimum_comparison_records_per_side"]
                or sample["eligible_word_count"] < config["style"]["minimum_comparison_words_per_side"]):
            reasons.append("insufficient_comparable_text")
    if (len(samples["left"]["kinds"]) != 1 or samples["left"]["kinds"] != samples["right"]["kinds"]):
        reasons.append("incompatible_kind_scope")
    english = samples["left"]["languages"] == ["en"] and samples["right"]["languages"] == ["en"]
    if not english:
        reasons.append("english_not_declared_for_both_scopes")
    limitations = ["distance_is_not_authorship_probability", "parameter_defaults_uncalibrated",
                   "context_controls_incomplete", "correlated_representations"]
    if reasons:
        limitations.append("raw_measurements_below_qualified_sample_guards")
    for sample in samples.values():
        if sample["edit_state_counts"]["edited"]:
            limitations.append("known_edited_observed_text")
        if sample["edit_state_counts"]["unknown"]:
            limitations.append("unknown_edit_history")
        if sample["missing_timestamps"]:
            limitations.append("missing_timestamps_in_pooled_comparison")
        if sample["largest_record_share"] is not None and sample["largest_record_share"] > config["windows"]["single_record_dominance_fraction"]:
            limitations.append("single_record_dominance")
    distances = []
    for view in config["style"]["views"]:
        for n in config["style"]["ngram_lengths"]:
            x, y = chargrams(_segments(left, view), n), chargrams(_segments(right, view), n)
            total_x, total_y = sum(x.values()), sum(y.values())
            result = _distance("cosine_distance_v1", view, n, "cosine_distance", "fraction_of_character_ngrams",
                               total_x, total_y, "character_ngrams")
            if view == "function_mask_v1" and not english:
                result.update(status="not_run", reason="english_not_declared_for_both_scopes")
            else:
                vocabulary = sorted(x.keys() | y.keys())
                value = cosine_distance([x[key] for key in vocabulary], [y[key] for key in vocabulary])
                if value is not None:
                    result.update(status="ok", reason=None, value=value)
                    result["contributions"] = [{"feature_id": key, "left_rate": x[key] / total_x, "right_rate": y[key] / total_y,
                                                "absolute_rate_change": abs(x[key] / total_x - y[key] / total_y),
                                                "contribution": None, "contribution_kind": "normalized_frequency_difference",
                                                "left_count": x[key], "right_count": y[key]} for key in vocabulary]
                    result["contributions"].sort(key=lambda item: (-item["absolute_rate_change"], item["feature_id"]))
            distances.append(result)
    words_x, words_y = _word_counts(left), _word_counts(right)
    total_x, total_y = sum(words_x.values()), sum(words_y.values())
    fixed_words = sorted(function_words())
    counts_x = [words_x[word] for word in fixed_words] + [total_x - sum(words_x[word] for word in fixed_words)]
    counts_y = [words_y[word] for word in fixed_words] + [total_y - sum(words_y[word] for word in fixed_words)]
    js = _distance("function_word_js_v1", "lexical_tokens", None, "base_2_js_distance", "per_1000_word_tokens",
                   total_x, total_y, "retained_word_tokens")
    if not english:
        js.update(status="not_run", reason="english_not_declared_for_both_scopes")
    elif total_x and total_y:
        contributions = js_contributions(counts_x, counts_y)
        assert contributions is not None
        js.update(status="ok", reason=None, value=math.sqrt(_clamp_excursion(math.fsum(contributions))))
        js["contributions"] = [{"feature_id": f"function_word.{word}", "left_rate": 1000 * a / total_x, "right_rate": 1000 * b / total_y,
                                "absolute_rate_change": abs(1000 * a / total_x - 1000 * b / total_y),
                                "contribution": value, "contribution_kind": "js_divergence", "left_count": a, "right_count": b}
                               for word, a, b, value in zip(fixed_words + ["OTHER_WORD"], counts_x, counts_y, contributions, strict=True)]
        js["contributions"].sort(key=lambda item: (-item["contribution"], item["feature_id"]))
    distances.append(js)
    delta = _distance("classic_delta_v1", "lexical_tokens", None, "mean_absolute_standardized_frequency_difference",
                      "per_1000_word_tokens", total_x, total_y, "retained_word_tokens")
    if config.reference is None or not config["delta"]["enabled_when_reference_supplied"]:
        delta.update(status="not_run", reason="not_run_missing_reference" if config.reference is None else "disabled_by_configuration")
    elif not english:
        delta.update(status="not_run", reason="english_not_declared_for_both_scopes")
    elif total_x and total_y:
        delta.update(classic_delta([1000 * words_x[word] / total_x for word in config.reference["vocabulary"]],
                                   [1000 * words_y[word] / total_y for word in config.reference["vocabulary"]],
                                   config.reference, allow_toy_reference=config["delta"]["allow_toy_reference"]))
        for contribution in delta["contributions"]:
            word = contribution["feature_id"].removeprefix("reference_word.")
            contribution.update(left_count=words_x[word], right_count=words_y[word])
    if config.reference is not None:
        delta.update(reference_id=config.reference["reference_id"], reference_kind=config.reference["reference_kind"])
        if config.reference["reference_kind"] == "toy":
            limitations.append("toy_reference")
    distances.append(delta)
    left_values, right_values = feature_values(pooled(left, config)), feature_values(pooled(right, config))
    if not english:
        # Pooled direct summaries can legitimately contain an English subset,
        # but mixed/other-language comparison scopes do not qualify for an
        # English function-profile comparison. Keep those coordinates missing.
        for key in left_values:
            if key.startswith("function_word."):
                left_values[key] = right_values[key] = None
    units = feature_units()
    changes = [{"feature_id": key, "left_value": value, "right_value": right_values[key],
                "absolute_change": abs(value - right_values[key]) if value is not None and right_values[key] is not None else None,
                "unit": units[key]} for key, value in left_values.items()]
    changes.sort(key=lambda item: (item["absolute_change"] is None, -(item["absolute_change"] or 0), item["feature_id"]))
    return {"status": "insufficient_data" if reasons else "ok", "reason_codes": sorted(set(reasons)),
            "samples": samples, "distances": distances, "surface_changes": changes, "limitations": sorted(set(limitations))}
