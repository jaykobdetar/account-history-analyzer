"""Synthetic normalized-case arithmetic; no real scores or source identities."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import analyze_cases as analysis
from study_math import clustered_block_bootstrap

STRATA = ['s1', 's2', 's3']


def fixture(per_stratum=2):
    cases, units, dependencies = [], [], {}
    for stratum in STRATA:
        for i in range(per_stratum):
            block = f'{stratum}-b{i}'
            dependencies[block] = 'unit-' + block
            for arm, count in zip(analysis.ARMS, (16, 12, 8, 8)):
                for cell in analysis.CELLS:
                    units.append({'stratum_id': stratum, 'block_id': block, 'arm': arm,
                                  'cell_id': cell, 'records': count, 'retained_words': 125 * count,
                                  'nonempty': True, 'ordinary_volume_guards_met': True})
                for method in analysis.METHODS:
                    for anchor in analysis.ANCHORS:
                        for category, score in zip(analysis.CATEGORIES, (.1, .4, .2, .5)):
                            cases.append({'method_id': method[0], 'view': method[1], 'n': method[2],
                                          'arm': arm, 'stratum_id': stratum, 'block_id': block,
                                          'anchor_id': anchor, 'category': category, 'score': score,
                                          'raw_distance': score, 'status': 'ok', 'reason_codes': []})
    return cases, units, dependencies


def analyze(data):
    return analysis.analyze_cases(*data, STRATA, synthetic_blocks_per_stratum=2, bootstrap_repetitions=100)


def summary(report, *, arm='full', stratum='s1', view='retained_prose'):
    return next(row for row in report['summaries'] if row['arm'] == arm and row['stratum_id'] == stratum and row['view'] == view)


def test_complete_design_preserves_fixed_methods_arms_case_and_unit_denominators():
    result = analyze(fixture())
    assert result['planned']['case_rows'] == 3 * 4 * 6 * 16
    assert result['planned']['unit_rows'] == 6 * 4 * 8
    assert len(result['summaries']) == 3 * 4 * 3
    assert len(result['anchor_rows']) == 3 * 4 * 6 * 4
    assert len(result['block_rows']) == 3 * 4 * 6
    row = summary(result)
    assert row['primary_cross']['mean'] == 1
    assert row['paired_context']['cross_minus_within_mean'] == 0
    assert row['comparisons']['planned_class_counts'] == {'same_author': 16, 'different_author': 16}
    for context in ('within_community', 'cross_community'):
        metrics = row['context_rankings'][context]
        assert metrics['planned_pairs'] == 16
        assert metrics['planned_class_counts'] == {'same_author': 8, 'different_author': 8}
        assert metrics['roc_auc'] == metrics['average_precision'] == 1
    assert row['uncertainty']['cross']['reason'] == 'inadequate_independent_units_for_uncertainty'


def test_ties_are_half_and_raw_unqualified_distance_never_becomes_score():
    cases, units, dependencies = fixture()
    for row in cases:
        if row['block_id'] == 's1-b0' and row['category'] == analysis.CATEGORIES[3]:
            row['score'] = row['raw_distance'] = .2
        if row['block_id'] == 's1-b1' and row['anchor_id'] == 'A/X' and row['category'] == analysis.CATEGORIES[3]:
            row['score'], row['status'], row['reason_codes'] = None, 'abstained', ['method_unavailable']
    result = analyze((cases, units, dependencies))
    row = summary(result)
    assert row['primary_cross'] == {'mean': .5, 'complete_blocks': 1, 'incomplete_blocks': 1}
    assert row['available_anchor_secondary']['available_anchors'] == 7
    assert row['available_anchor_secondary']['mean'] == pytest.approx(5 / 7)
    assert row['comparisons']['qualified'] == 31
    assert row['comparisons']['abstention_reason_counts'] == {'method_unavailable': 1}
    assert any(case['score'] is None and case['raw_distance'] == .5 for case in result['case_rows'])


def test_within_cross_change_uses_exact_same_complete_blocks():
    cases, units, dependencies = fixture()
    for row in cases:
        if row['block_id'] == 's1-b0' and row['category'] == analysis.CATEGORIES[3]:
            row['score'] = row['raw_distance'] = .1
        if row['block_id'] == 's1-b1' and row['category'] == analysis.CATEGORIES[1]:
            row['score'], row['status'], row['reason_codes'] = None, 'abstained', ['within_unavailable']
    row = summary(analyze((cases, units, dependencies)))
    assert row['primary_cross']['mean'] == .5
    assert row['paired_context'] == {'complete_blocks': 1, 'within_mean': 1, 'cross_mean': 0, 'cross_minus_within_mean': -1}


def test_missing_planned_stratum_keeps_macro_unavailable_instead_of_reweighting():
    cases, units, dependencies = fixture()
    for row in cases:
        if row['stratum_id'] == 's3':
            row.update(score=None, raw_distance=None, status='abstained', reason_codes=['stratum_unavailable'])
    for row in units:
        if row['stratum_id'] == 's3':
            row.update(records=0, retained_words=0, nonempty=False, ordinary_volume_guards_met=False)
    result = analyze((cases, units, dependencies))
    macro = result['equal_stratum_macros'][0]['primary_cross_equal_stratum_macro']
    assert macro['value'] is None and macro['missing_strata'] == ['s3']
    assert summary(result, stratum='s3')['units']['planned'] == 16
    assert summary(result, stratum='s3')['units']['nonempty'] == 0


def test_omission_apparent_improvement_is_separated_from_common_block_change():
    cases, units, dependencies = fixture()
    for row in cases:
        if row['block_id'] == 's1-b1' and row['arm'] == 'full' and row['category'] == analysis.CATEGORIES[3]:
            row['score'] = row['raw_distance'] = .1
        if row['block_id'] == 's1-b1' and row['arm'] == 'hash50':
            row.update(score=None, status='abstained', reason_codes=['insufficient_records'])
    for row in units:
        if row['block_id'] == 's1-b1' and row['arm'] == 'hash50':
            row.update(records=0, retained_words=0, nonempty=False, ordinary_volume_guards_met=False)
    result = analyze((cases, units, dependencies))
    assert summary(result)['primary_cross']['mean'] == .5
    assert summary(result, arm='hash50')['primary_cross']['mean'] == 1
    common = next(row for row in result['omission_intersections'] if row['view'] == 'retained_prose' and row['arm'] == 'hash50' and row['stratum_id'] == 's1')
    assert common['intersection_complete_blocks'] == 1
    assert common['full_mean_on_intersection'] == common['arm_mean_on_intersection'] == 1
    assert common['arm_minus_full_mean_on_intersection'] == 0


@pytest.mark.parametrize('corruption', ['missing_case', 'duplicate_case', 'extra_method', 'raw_as_score', 'score_below_guard', 'lower_guards', 'refill', 'missing_dependency', 'private_field', 'missing_block'])
def test_rejects_quiet_drops_unplanned_inputs_and_guard_bypasses(corruption):
    cases, units, dependencies = fixture()
    if corruption == 'missing_case':
        cases.pop()
    elif corruption == 'duplicate_case':
        cases.append(deepcopy(cases[0]))
    elif corruption == 'extra_method':
        cases[0]['n'] = 3
    elif corruption == 'raw_as_score':
        cases[0]['status'] = 'abstained'
    elif corruption == 'score_below_guard':
        for row in units:
            if row['block_id'] == 's1-b0':
                row.update(records=0, retained_words=0, nonempty=False, ordinary_volume_guards_met=False)
    elif corruption == 'lower_guards':
        units[0]['ordinary_volume_guards_met'] = False
    elif corruption == 'refill':
        next(row for row in units if row['arm'] == 'hash75')['retained_words'] = 99999
    elif corruption == 'missing_dependency':
        dependencies.pop('s1-b0')
    elif corruption == 'private_field':
        cases[0]['source_account_id'] = 'should-not-publish'
    else:
        units = [row for row in units if row['block_id'] != 's1-b0']
    with pytest.raises(ValueError):
        analyze((cases, units, dependencies))


def test_empirical_defaults_enforce_thirty_blocks_and_ten_thousand_repetitions():
    with pytest.raises(ValueError, match='Planned blocks missing'):
        analysis.analyze_cases(*fixture(), STRATA)
    with pytest.raises(ValueError, match='10000'):
        analysis.analyze_cases(*fixture(10), STRATA, bootstrap_repetitions=100)


def test_shared_ten_thousand_draws_keep_cross_stratum_clusters_and_all_arms_together():
    blocks = {f'b{i}': STRATA[i % 3] for i in range(6)}
    dependencies = {block: 'g0' if block in ('b0', 'b1') else 'g' + block[1:] for block in blocks}
    values = {block: i / 8 for i, block in enumerate(blocks)}
    results, driver = analysis.shared_bootstrap({'full': values, 'hash50': values, 'scarce': dict(list(values.items())[:4])}, blocks, dependencies)
    scalar = clustered_block_bootstrap({block: [{'value': value}] for block, value in values.items()},
                                       lambda rows: float(sum((Fraction(row['value']) for row in rows), Fraction()) / len(rows)),
                                       group_by_block=dependencies, stratum_by_block=blocks)
    assert driver['executed_repetitions'] == 10000
    assert driver['cross_stratum_dependency_units'] == 1
    assert results['full']['shared_draws_sha256'] == results['hash50']['shared_draws_sha256'] == scalar['draws_sha256']
    assert results['full']['percentile_interval_95'] == results['hash50']['percentile_interval_95'] == scalar['percentile_interval_95']
    assert results['scarce']['percentile_interval_95'] is None
    assert results['scarce']['reason'] == 'inadequate_independent_units_for_uncertainty'


def test_missing_bootstrap_replicates_are_counted_and_do_not_get_discarded():
    blocks = {f'b{i:02d}': 's1' for i in range(20)}
    dependencies = {block: 'g' + block for block in blocks}
    values = {block: 1 for block in list(blocks)[:5]}
    results, driver = analysis.shared_bootstrap({'sparse': values}, blocks, dependencies)
    assert results['sparse']['missing_replicates'] > 0
    assert results['sparse']['percentile_interval_95'] is None
    assert results['sparse']['reason'] == 'missing_bootstrap_statistics_no_silent_reweighting'


def test_public_csv_json_outputs_preserve_all_rows_and_hash_every_artifact(tmp_path):
    result = analyze(fixture())
    hashes = analysis.write_outputs(result, tmp_path / 'analysis')
    assert len(hashes) == 15
    assert len(json.loads((tmp_path / 'analysis' / 'case_rows.json').read_bytes())) == 1152
    assert len((tmp_path / 'analysis' / 'case_rows.csv').read_text().splitlines()) == 1153
    assert (tmp_path / 'analysis' / 'output-hashes.json').exists()
    assert analysis.analyze_cases(*tuple(reversed(value) if isinstance(value, list) else value for value in fixture()), STRATA,
                                   synthetic_blocks_per_stratum=2, bootstrap_repetitions=100) == result
