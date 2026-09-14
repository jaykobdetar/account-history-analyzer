"""Synthetic cross-implementation arithmetic checks; no source prose or scores."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_analysis_results as checker
import analyze_cases as analysis
from test_analyze_cases import fixture, STRATA


def compare(data, per_stratum=2, repetitions=100):
    expected = checker.recompute(*data, STRATA, per_stratum=per_stratum, repetitions=repetitions)
    actual = analysis.analyze_cases(*data, STRATA, synthetic_blocks_per_stratum=per_stratum, bootstrap_repetitions=repetitions)
    mismatches = [error for key, value in expected.items() for error in checker.differences(value, actual[key], key)]
    assert not mismatches, mismatches[:20]
    return expected, actual


def test_literal_ordering_retains_null_and_exact_tie_without_rounding():
    assert checker.order(.1, .2) == 1 and checker.order(.2, .1) == 0
    assert checker.order(.2, .2) == .5 and checker.order(None, .2) is None
    assert checker.order(.2, .20000000000000004) == 1


def test_tied_group_ap_is_noninterpolated_and_pairwise_auc_counts_half_ties():
    result = checker.ranking([(.5, 'different_author'), (.5, 'same_author'), (.4, 'different_author'), (None, 'same_author')])
    assert result['roc_auc'] == .25
    assert result['average_precision'] == float(Fraction(7, 12))
    assert result['planned_class_counts'] == {'same_author': 2, 'different_author': 2}
    assert result['qualified_pairs'] == 3 and result['abstained_pairs'] == 1


def test_single_label_and_empty_rank_sets_retain_explicit_null_reasons():
    result = checker.ranking([(.5, 'same_author')])
    assert result['roc_auc'] is None and result['average_precision'] is None
    assert result['average_precision_reason'] == 'no_scored_positive_pairs'
    result = checker.ranking([(.5, 'different_author')])
    assert result['roc_auc'] is None and result['average_precision'] == 1


def test_all_planned_rows_coverage_and_secondary_metrics_match():
    expected, _ = compare(fixture())
    assert len(expected['summaries']) == 36 and len(expected['omission_intersections']) == 27
    assert len(expected['equal_stratum_macros']) == 12


def test_missing_anchors_ties_paired_intersection_and_raw_unqualified_distance():
    data = fixture()
    for row in data[0]:
        if row['block_id'] == 's1-b0' and row['category'] == checker.CATEGORIES[3]:
            row['score'] = row['raw_distance'] = .2
        if row['block_id'] == 's1-b1' and row['anchor_id'] == 'A/X' and row['category'] == checker.CATEGORIES[1]:
            row.update(score=None, status='abstained', reason_codes=['within_unavailable'])
        if row['block_id'] == 's2-b0' and row['arm'] == 'hash50' and row['category'] == checker.CATEGORIES[3]:
            row.update(score=None, status='abstained', reason_codes=['method_unavailable', 'insufficient_features'])
    expected, _ = compare(data)
    assert any(r['raw_distance'] is not None and r['score'] is None for r in expected['case_rows'])
    paired = expected['summaries'][0]['paired_context']
    assert paired['complete_blocks'] == 1 and paired['cross_minus_within_mean'] == -.5


def test_no_quiet_macro_reweighting_when_one_planned_stratum_has_no_scores():
    data = fixture()
    for row in data[0]:
        if row['stratum_id'] == 's3':
            row.update(score=None, raw_distance=None, status='abstained', reason_codes=['unavailable'])
    expected, _ = compare(data)
    assert expected['equal_stratum_macros'][0]['primary_cross_equal_stratum_macro']['value'] is None
    assert expected['equal_stratum_macros'][0]['primary_cross_equal_stratum_macro']['missing_strata'] == ['s3']


def test_frequency_percentile_matches_literal_order_statistics():
    frequencies = {Fraction(0): 1, Fraction(1, 2): 2, Fraction(1): 1}
    assert checker.frequency_percentile(frequencies, Fraction(1, 4)) == .375
    assert checker.frequency_percentile(frequencies, Fraction(3, 4)) == .625


def test_ten_thousand_cross_stratum_group_draws_and_missing_replicates_match():
    blocks = {f'b{i:02}': STRATA[i % 3] for i in range(20)}
    deps = {b: 'joint' if b in ('b00', 'b01') else 'g' + b for b in blocks}
    series = {'full': {b: (i % 9)/8 for i, b in enumerate(blocks)},
              'scarce': {b: 1 for b in list(blocks)[:4]}, 'sparse': {b: .5 for b in list(blocks)[2:7]}, 'empty': {}}
    actual_intervals, actual_shared = analysis.shared_bootstrap(series, blocks, deps)
    expected_intervals, expected_shared = checker.bootstrap(series, blocks, deps)
    assert expected_intervals == actual_intervals
    assert expected_shared == actual_shared
    assert expected_shared['cross_stratum_dependency_units'] == 1
    assert expected_intervals['scarce']['percentile_interval_95'] is None
    assert expected_intervals['sparse']['missing_replicates'] > 0
    assert expected_intervals['sparse']['percentile_interval_95'] is None


def test_no_draw_stream_when_every_metric_has_fewer_than_five_contributing_units():
    blocks = {f'b{i}': 's1' for i in range(8)}
    deps = {b: 'g' + b for b in blocks}
    series = {'scarce': {b: .5 for b in list(blocks)[:4]}}
    assert checker.bootstrap(series, blocks, deps) == analysis.shared_bootstrap(series, blocks, deps)


def test_full_5760_case_design_and_all171_intervals_independently_recomputed(tmp_path):
    data = fixture(10)
    for row in data[0]:
        block = int(row['block_id'].split('-b')[1])
        anchor = checker.ANCHORS.index(row['anchor_id'])
        category = checker.CATEGORIES.index(row['category'])
        arm = checker.ARMS.index(row['arm'])
        row['score'] = row['raw_distance'] = ((3*category + 5*anchor + block + arm) % 11) / 10
        if row['arm'] == 'hash50' and block >= 5 and row['stratum_id'] == 's2':
            row.update(score=None, status='abstained', reason_codes=['insufficient_windows'])
    expected, actual = compare(data, 10, 10000)
    assert expected['planned']['case_rows'] == 5760
    assert expected['shared_bootstrap']['executed_repetitions'] == 10000
    assert len(expected['summaries'])*4 + len(expected['omission_intersections']) == 171
    # Exercise the actual saved-output checker against a full synthetic file set.
    for name, value in zip(('cases', 'units', 'dependencies'), data):
        (tmp_path / (name + '.json')).write_text(json.dumps(value))
    code = {key: checker.fp(Path(analysis.__file__).with_name(name))['sha256'] for key, name in (('analysis_sha256', 'analyze_cases.py'), ('study_math_sha256', 'study_math.py'))}
    plan = {'planned_strata': STRATA, 'registered_before_scoring': True, 'registered_protocol_sha256': '0'*64, **code}
    (tmp_path / 'plan.json').write_text(json.dumps(plan))
    actual['scope'] = 'normalized_registered_study_cases'
    actual['code_bindings'] = code
    actual['input_bindings'] = {key: checker.fp(tmp_path / (name + '.json'))['sha256'] for key, name in (('cases_sha256', 'cases'), ('units_sha256', 'units'), ('dependencies_sha256', 'dependencies'), ('analysis_plan_sha256', 'plan'))}
    analysis.write_outputs(actual, tmp_path / 'results')
    args = SimpleNamespace(**{name: tmp_path / (name + '.json') for name in ('cases', 'units', 'dependencies', 'plan')}, results=tmp_path / 'results')
    report = checker.verify(args)
    assert report['status'] == 'pass', report['failed_checks'][:10]
    assert report['bootstrap_series_recomputed'] == 171
    csv = tmp_path / 'results' / 'summaries.csv'
    csv.write_text(csv.read_text().replace('retained_prose', 'changed_view', 1))
    assert checker.verify_csv(csv, expected['summaries'])
    target = next(r['uncertainty']['cross'] for r in actual['summaries'] if r['uncertainty']['cross']['percentile_interval_95'] is not None)
    target['percentile_interval_95'][0] += .125
    assert checker.differences(expected['summaries'], actual['summaries'])


@pytest.mark.parametrize('mutation', ['case_removed', 'case_duplicate', 'missing_dependency', 'guard_bypass', 'omission_refill'])
def test_invalid_complete_design_is_rejected_independently(mutation):
    data = deepcopy(fixture())
    if mutation == 'case_removed':
        data[0].pop()
    elif mutation == 'case_duplicate':
        data[0].append(deepcopy(data[0][0]))
    elif mutation == 'missing_dependency':
        data[2].pop('s1-b0')
    elif mutation == 'guard_bypass':
        data[1][0]['ordinary_volume_guards_met'] = False
    else:
        next(row for row in data[1] if row['arm'] == 'hash50')['records'] = 999
    with pytest.raises(ValueError):
        checker.recompute(*data, STRATA, per_stratum=2, repetitions=1)


def test_checker_does_not_import_analyzer_arithmetic_or_ahas():
    import ast
    tree = ast.parse(Path(checker.__file__).read_text())
    names = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    names += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
    assert not set(names) & {'analyze_cases', 'study_math', 'account_history_analyzer'}
