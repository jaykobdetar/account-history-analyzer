"""Descriptive offline evaluation arithmetic with explicit observed denominators.

No threshold is fitted here. Labels and grouping metadata belong exclusively to
the evaluator and never enter analyzer representations or measurements.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any

from .errors import InputError

LABELS = ('same_author', 'different_author')


def _ratio(numerator: int | float, denominator: int, missing: str) -> dict[str, Any]:
    return {'status': 'ok' if denominator else 'not_computable',
            'value': numerator / denominator if denominator else None,
            'numerator': numerator, 'denominator': denominator,
            'reason_codes': [] if denominator else [missing]}


def _finite(value: Any) -> bool:
    # Ranking uses ordering, so a finite Python integer need not be narrowed to
    # float (math.isfinite would overflow for an otherwise valid large integer).
    return type(value) is int or isinstance(value, float) and math.isfinite(value)


def paired_metrics(labels: Sequence[str], scores: Sequence[float | None], *,
                   threshold: float | None = None) -> dict[str, Any]:
    """Evaluate larger-distance-positive rankings with whole equal-score groups.

    ROC AUC is the probability a uniformly selected observed positive outranks a
    negative, assigning one-half to ties. Average precision integrates the step
    precision/recall curve after each whole tied-score group, with no interpolation.
    A supplied frozen threshold predicts different_author exactly when score >=
    threshold. Missing scores abstain and are excluded from scored denominators.
    """
    if len(labels) != len(scores) or any(label not in LABELS for label in labels):
        raise InputError('Pair scores require one same_author/different_author label each', code='invalid_evaluation_pairs')
    if any(score is not None and not _finite(score) for score in scores):
        raise InputError('Pair scores must be finite numbers or null abstentions', code='invalid_evaluation_scores')
    if threshold is not None and not _finite(threshold):
        raise InputError('A frozen threshold must be a finite number', code='invalid_evaluation_threshold')
    observed = [(label, score) for label, score in zip(labels, scores, strict=True) if score is not None]
    total_counts = {label: labels.count(label) for label in LABELS}
    scored_counts = {label: sum(item[0] == label for item in observed) for label in LABELS}
    positives, negatives = scored_counts['different_author'], scored_counts['same_author']
    groups: dict[float, list[int]] = {}
    for label, score in observed:
        group = groups.setdefault(score, [0, 0])
        group[label == 'different_author'] += 1
    # Integer doubled-win count avoids rounding each tied pair independently.
    doubled_wins = 0
    lower_negatives = 0
    for score in sorted(groups):
        group_negative, group_positive = groups[score]
        doubled_wins += group_positive * (2 * lower_negatives + group_negative)
        lower_negatives += group_negative
    tp = seen = 0
    ap_terms = []
    for score in sorted(groups, reverse=True):
        group_negative, group_positive = groups[score]
        tp += group_positive
        seen += group_negative + group_positive
        ap_terms.append(group_positive * tp / seen)
    ranking = {
        'roc_auc': _ratio(doubled_wins / 2, positives * negatives, 'both_scored_labels_required'),
        'average_precision': _ratio(math.fsum(ap_terms), positives, 'no_scored_positive_pairs'),
        'average_precision_definition': 'Noninterpolated recall increments after whole equal-score groups',
        'roc_auc_tie_credit': 0.5,
    }
    decisions: dict[str, Any] = {
        'status': 'not_run_missing_threshold' if threshold is None else 'ok',
        'reason_codes': ['frozen_development_threshold_not_supplied'] if threshold is None else [],
        'threshold': threshold, 'positive_rule': 'score >= threshold',
        'scored_pair_count': len(observed),
        'confusion': None, 'false_positive_rate': None, 'recall': None, 'precision': None,
    }
    if threshold is not None:
        confusion = {name: 0 for name in ('true_positive','false_positive','true_negative','false_negative')}
        for label, score in observed:
            positive = label == 'different_author'
            predicted = score >= threshold
            name = ('true_positive' if positive else 'false_positive') if predicted else ('false_negative' if positive else 'true_negative')
            confusion[name] += 1
        decisions.update({
            'confusion': confusion,
            'false_positive_rate': _ratio(confusion['false_positive'], negatives, 'no_scored_negative_pairs'),
            'recall': _ratio(confusion['true_positive'], positives, 'no_scored_positive_pairs'),
            'precision': _ratio(confusion['true_positive'], confusion['true_positive'] + confusion['false_positive'], 'no_predicted_positive_pairs'),
        })
    return {
        'positive_label': 'different_author', 'negative_label': 'same_author',
        'score_direction': 'larger_distance_is_positive', 'total_pair_count': len(labels),
        'scored_pair_count': len(observed), 'abstained_pair_count': len(labels) - len(observed),
        'sample_coverage': _ratio(len(observed), len(labels), 'no_labeled_pairs'),
        'abstention_rate': _ratio(len(labels) - len(observed), len(labels), 'no_labeled_pairs'),
        'total_label_counts': total_counts, 'scored_label_counts': scored_counts,
        'ranking': ranking, 'decisions': decisions,
    }


def boundary_metrics(candidates: Sequence[Sequence[int]], truth: Sequence[int], *,
                     tolerance: int) -> dict[str, Any]:
    """Match interval candidates to annotated split positions exactly one-to-one.

    Split k is the zero-based canonical ordinal of the first record on its right.
    A production boundary between records a and b maps to the inclusive split
    interval [a+1,b]. Distance is zero inside that interval, otherwise displacement
    to its nearest endpoint. Tolerance is inclusive and explicitly preregistered.
    Candidate intervals must be disjoint, as chronological segmentation produces.

    Ordered interval/point distances admit a noncrossing optimum. Dynamic
    programming maximizes count, minimizes total displacement, then chooses the
    lexicographically earliest sequence of interval/truth-position pairs.
    """
    if type(tolerance) is not int or tolerance < 0:
        raise InputError('Boundary tolerance must be a nonnegative integer', code='invalid_boundary_tolerance')
    if (any(type(point) is not int or point < 1 for point in truth)
            or len(set(truth)) != len(truth)):
        raise InputError('Truth split positions must be unique positive integer ordinals', code='invalid_evaluation_boundaries')
    if any(len(interval) != 2 or any(type(point) is not int or point < 1 for point in interval)
           or interval[0] > interval[1] for interval in candidates):
        raise InputError('Candidate split intervals must contain two ordered positive integer ordinals', code='invalid_evaluation_boundaries')
    ordered = sorted((tuple(interval), index) for index, interval in enumerate(candidates))
    if any(left[0][1] >= right[0][0] for left, right in zip(ordered, ordered[1:])):
        raise InputError('Candidate split intervals must be pairwise disjoint', code='invalid_evaluation_boundaries')
    annotated = sorted((point, index) for index, point in enumerate(truth))
    n, m = len(ordered), len(annotated)
    counts = [[0] * (m+1) for _ in range(n+1)]
    costs = [[0] * (m+1) for _ in range(n+1)]

    def distance(i: int, j: int) -> int:
        interval, point = ordered[i][0], annotated[j][0]
        return max(interval[0] - point, point - interval[1], 0)

    for i in range(n-1, -1, -1):
        for j in range(m-1, -1, -1):
            choices = [(counts[i+1][j], costs[i+1][j]), (counts[i][j+1], costs[i][j+1])]
            error = distance(i, j)
            if error <= tolerance:
                choices.append((1+counts[i+1][j+1], error+costs[i+1][j+1]))
            counts[i][j], costs[i][j] = min(choices, key=lambda item: (-item[0], item[1]))
    matched = []
    i = j = 0
    while i < n and j < m and counts[i][j]:
        target = (counts[i][j], costs[i][j])
        chosen = None
        for a in range(i, n):
            for b in range(j, m):
                error = distance(a, b)
                if error <= tolerance and (1+counts[a+1][b+1], error+costs[a+1][b+1]) == target:
                    chosen = a, b, error
                    break
            if chosen is not None:
                break
        assert chosen is not None, 'Optimal matching must admit a reconstructible suffix'
        a, b, error = chosen
        matched.append({'candidate_index': ordered[a][1], 'truth_index': annotated[b][1],
                        'candidate_interval': list(ordered[a][0]), 'truth_position': annotated[b][0],
                        'location_error_records': error})
        i, j = a+1, b+1
    matched_candidate = {row['candidate_index'] for row in matched}
    matched_truth = {row['truth_index'] for row in matched}
    errors = [row['location_error_records'] for row in matched]
    return {
        'coordinate_definition': 'Split k precedes zero-based canonical record ordinal k; inclusive candidate split intervals',
        'matching_rule': 'Maximum count, minimum total interval distance, lexicographic interval/truth-position pairs',
        'tolerance_records': tolerance, 'candidate_count': n, 'truth_count': m, 'matched_count': len(matched),
        'unmatched_candidate_count': n-len(matched), 'unmatched_truth_count': m-len(matched),
        'matches': matched,
        'unmatched_candidate_indices': sorted(set(range(n))-matched_candidate),
        'unmatched_truth_indices': sorted(set(range(m))-matched_truth),
        'precision': _ratio(len(matched), n, 'no_candidate_boundaries'),
        'recall': _ratio(len(matched), m, 'no_annotated_boundaries'),
        'mean_location_error_records': _ratio(sum(errors), len(errors), 'no_matched_boundaries'),
        'maximum_location_error_records': max(errors) if errors else None,
    }


def aggregate_stream_metrics(metrics: Sequence[Mapping[str, Any]], *,
                             abstained_stream_count: int = 0) -> dict[str, Any]:
    """Pool executed streams only, retaining missing-stream coverage explicitly."""
    if type(abstained_stream_count) is not int or abstained_stream_count < 0:
        raise InputError('Abstained stream count must be a nonnegative integer', code='invalid_evaluation_streams')
    candidate_count = sum(row['candidate_count'] for row in metrics)
    truth_count = sum(row['truth_count'] for row in metrics)
    matched_count = sum(row['matched_count'] for row in metrics)
    unchanged = [row for row in metrics if row['truth_count'] == 0]
    errors = [match['location_error_records'] for row in metrics for match in row['matches']]
    total = len(metrics) + abstained_stream_count
    return {
        'total_stream_count': total, 'executed_stream_count': len(metrics),
        'abstained_stream_count': abstained_stream_count,
        'sample_coverage': _ratio(len(metrics), total, 'no_labeled_streams'),
        'candidate_count': candidate_count, 'truth_count': truth_count, 'matched_count': matched_count,
        'unmatched_candidate_count': candidate_count-matched_count, 'unmatched_truth_count': truth_count-matched_count,
        'precision': _ratio(matched_count, candidate_count, 'no_candidate_boundaries'),
        'recall': _ratio(matched_count, truth_count, 'no_annotated_boundaries'),
        'executed_unchanged_stream_count': len(unchanged),
        'false_candidates_per_unchanged_stream': _ratio(sum(row['candidate_count'] for row in unchanged), len(unchanged), 'no_executed_unchanged_streams'),
        'mean_location_error_records': _ratio(sum(errors), len(errors), 'no_matched_boundaries'),
        'maximum_location_error_records': max(errors) if errors else None,
    }
