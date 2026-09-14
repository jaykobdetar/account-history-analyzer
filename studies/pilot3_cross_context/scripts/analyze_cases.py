#!/usr/bin/env python3
"""Preparatory normalized-case analysis; no evaluator calls or source-text reads.

Input uses opaque public block/stratum/dependency IDs, never source account IDs,
paths, or prose. Complete planned rows are required, including explicit null-score
rows for unavailable cases. Only synthetic cases have tested this draft adapter.
This module does not authorize scoring, claim registration, or select a method.

API: analyze_cases(case_rows, unit_rows, dependency_blocks, planned_strata).
Cases and units are JSON arrays with the exact CASE_FIELDS/UNIT_FIELDS below;
dependencies map public block IDs to audited public resampling-unit IDs. The
real CLI plan requires registered_before_scoring=true, registered_protocol_sha256,
analysis_sha256, study_math_sha256, and exactly three planned_strata IDs. The
analysis/code hashes must have been bound before any new score was computed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from fractions import Fraction
import hashlib
import io
import json
import math
from pathlib import Path
import re

from study_math import (ANCHORS, CATEGORIES, BOOTSTRAP_SEED, block_outcomes,
                        clustered_block_bootstrap, equal_stratum_macro,
                        rank_metrics, _percentile)

VERSION = 'pilot3-normalized-analysis-draft-v1'
METHODS = (('cosine_distance_v1', 'retained_prose', 4),
           ('cosine_distance_v1', 'function_mask_v1', 4),
           ('function_word_js_v1', 'lexical_tokens', None))
ARMS = ('full', 'hash75', 'hash50', 'middle50')
CELLS = tuple(f'{account}/{community}/{period}' for account in ('A', 'B') for community in ('X', 'Y') for period in ('early', 'late'))
CASE_FIELDS = {'method_id', 'view', 'n', 'arm', 'stratum_id', 'block_id', 'anchor_id',
               'category', 'score', 'raw_distance', 'status', 'reason_codes'}
UNIT_FIELDS = {'stratum_id', 'block_id', 'arm', 'cell_id', 'records', 'retained_words',
               'nonempty', 'ordinary_volume_guards_met'}


def _opaque(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value) is not None


def _number(value):
    return value is None or (type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1)


def _mean(values):
    values = [Fraction(value) for value in values if value is not None]
    return float(sum(values, Fraction()) / len(values)) if values else None


def _method(value):
    return {'method_id': value[0], 'view': value[1], 'n': value[2]}


def _sides(anchor, category):
    account, community = anchor.split('/')
    other_account = 'B' if account == 'A' else 'A'
    other_community = 'Y' if community == 'X' else 'X'
    destination = ((account, community), (other_account, community),
                   (account, other_community), (other_account, other_community))[CATEGORIES.index(category)]
    return anchor + '/early', '/'.join(destination) + '/late'


def validate_inputs(cases, units, dependencies, planned_strata, *, synthetic_blocks_per_stratum=None):
    if len(planned_strata) != 3 or len(set(planned_strata)) != 3 or not all(_opaque(value) for value in planned_strata):
        raise ValueError('Three distinct opaque planned stratum IDs are required')
    per_stratum = 10 if synthetic_blocks_per_stratum is None else synthetic_blocks_per_stratum
    if type(per_stratum) is not int or per_stratum < 1 or per_stratum > 10:
        raise ValueError('Explicit synthetic block count must be between one and ten')
    unit_index, block_strata = {}, {}
    for row in units:
        if set(row) != UNIT_FIELDS:
            raise ValueError('Unit metadata fields must match the public normalized schema exactly')
        block, stratum = row['block_id'], row['stratum_id']
        if not _opaque(block) or stratum not in planned_strata or row['arm'] not in ARMS or row['cell_id'] not in CELLS:
            raise ValueError('Invalid planned unit identity')
        if block in block_strata and block_strata[block] != stratum:
            raise ValueError('A block cannot belong to two strata')
        block_strata[block] = stratum
        key = block, row['arm'], row['cell_id']
        if key in unit_index:
            raise ValueError('Duplicate planned unit')
        records, words = row['records'], row['retained_words']
        if type(records) is not int or type(words) is not int or records < 0 or words < 20 * records or (records == 0 and words != 0):
            raise ValueError('Unit counts must describe surviving eligible whole records')
        if type(row['nonempty']) is not bool or row['nonempty'] != (records > 0):
            raise ValueError('Unit nonempty flag disagrees with record count')
        if type(row['ordinary_volume_guards_met']) is not bool or row['ordinary_volume_guards_met'] != (records >= 8 and words >= 1000):
            raise ValueError('Ordinary unit qualification guard was changed or mislabeled')
        unit_index[key] = dict(row)
    counts = Counter(block_strata.values())
    if any(counts[stratum] != per_stratum for stratum in planned_strata):
        raise ValueError('Planned blocks missing: provide every block, including explicit unavailable rows')
    if set(dependencies) != set(block_strata) or not all(_opaque(value) for value in dependencies.values()):
        raise ValueError('Opaque dependency map must cover every planned block exactly')
    for block in block_strata:
        for cell in CELLS:
            if any((block, arm, cell) not in unit_index for arm in ARMS):
                raise ValueError('Every planned unit must remain present in all four arms')
            full, h75, h50, middle = (unit_index[block, arm, cell] for arm in ARMS)
            for field in ('records', 'retained_words'):
                if not h50[field] <= h75[field] <= full[field] or middle[field] > full[field]:
                    raise ValueError('Omission counts contradict nested deletion or imply refill')
            n = full['records']
            if middle['records'] != n - (3 * n // 4 - n // 4):
                raise ValueError('Middle-half record count contradicts the fixed rounding rule')
    case_index = {}
    for row in cases:
        if set(row) != CASE_FIELDS:
            raise ValueError('Case fields must match the public normalized schema exactly; no source identities or paths')
        method = row['method_id'], row['view'], row['n']
        if method not in METHODS or (row['n'] is not None and type(row['n']) is not int) or row['arm'] not in ARMS:
            raise ValueError('Unplanned method or omission arm')
        if block_strata.get(row['block_id']) != row['stratum_id'] or row['anchor_id'] not in ANCHORS or row['category'] not in CATEGORIES:
            raise ValueError('Unplanned case identity')
        if not _number(row['score']) or not _number(row['raw_distance']):
            raise ValueError('Scores must be finite normalized distances or explicit null')
        if row['status'] not in ('ok', 'abstained') or (row['status'] == 'ok') != (row['score'] is not None):
            raise ValueError('Score qualification contradicts status')
        if row['score'] is not None and row['score'] != row['raw_distance']:
            raise ValueError('Qualified score must preserve the evaluator raw distance')
        reasons = row['reason_codes']
        if not isinstance(reasons, list) or len(set(reasons)) != len(reasons) or any(not isinstance(reason, str) or re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', reason) is None for reason in reasons):
            raise ValueError('Reason codes must be unique public codes, not arbitrary text')
        if row['score'] is None and not reasons:
            raise ValueError('Unavailable planned cases require explicit reason codes')
        if row['score'] is not None:
            sides = _sides(row['anchor_id'], row['category'])
            if not all(unit_index[row['block_id'], row['arm'], side]['ordinary_volume_guards_met'] for side in sides):
                raise ValueError('A qualified score cannot bypass an ordinary unit volume guard')
        key = method, row['arm'], row['block_id'], row['anchor_id'], row['category']
        if key in case_index:
            raise ValueError('Duplicate planned comparison')
        case_index[key] = dict(row)
    expected = {(method, arm, block, anchor, category) for method in METHODS for arm in ARMS
                for block in block_strata for anchor in ANCHORS for category in CATEGORIES}
    if set(case_index) != expected:
        raise ValueError('Every planned block/method/arm requires all sixteen comparison rows; no quiet dropping')
    return case_index, unit_index, block_strata


def shared_bootstrap(series, block_strata, dependencies, *, repetitions=10000):
    """One tested cluster-bootstrap draw stream drives every method/arm metric.

    Global audited dependency units preserve cross-stratum dependencies. A
    statistic uses only its complete contributing blocks within each draw.
    Fewer than five contributing units withholds its interval. Any empty-draw
    statistic also withholds the interval; missing replicates are never discarded.
    """
    names = list(series)
    contributors = {name: len({dependencies[block] for block in values}) for name, values in series.items()}
    intervals = {name: [] for name in names if contributors[name] >= 5 and series[name]}
    by_block = defaultdict(list)
    for name in intervals:
        for block, value in series[name].items():
            exact = Fraction(value) * 8
            if exact.denominator != 1:
                raise ValueError('Complete four-anchor outcomes must be exact eighth increments')
            by_block[block].append((name, exact.numerator))
    def collect(rows):
        if not intervals:
            return None
        numerators, denominators = Counter(), Counter()
        for block, multiplicity in Counter(row['block_id'] for row in rows).items():
            for name, value in by_block[block]:
                numerators[name] += multiplicity * value
                denominators[name] += multiplicity
        for name in intervals:
            intervals[name].append(Fraction(numerators[name], 8 * denominators[name]) if denominators[name] else None)
        return 0  # Driver only: vector estimates are retained above, never zero-imputed.
    driver = clustered_block_bootstrap(
        {block: [{'block_id': block}] for block in block_strata}, collect,
        group_by_block=dependencies, stratum_by_block=block_strata,
        seed=BOOTSTRAP_SEED, repetitions=repetitions, minimum_independent_units=5)
    results = {}
    for name, values in series.items():
        result = {'estimate': _mean(values.values()), 'contributing_blocks': len(values),
                  'contributing_independent_units': contributors[name], 'minimum_independent_units': 5,
                  'requested_repetitions': repetitions, 'executed_repetitions': 0,
                  'missing_replicates': 0, 'percentile_interval_95': None,
                  'shared_draws_sha256': driver['draws_sha256'], 'reason': None}
        if not values:
            result['reason'] = 'descriptive_statistic_unavailable'
        elif contributors[name] < 5:
            result['reason'] = 'inadequate_independent_units_for_uncertainty'
        else:
            replicates = intervals[name][1:]  # First callback is the observed point, not a draw.
            result['executed_repetitions'] = len(replicates)
            result['missing_replicates'] = sum(value is None for value in replicates)
            if len(replicates) != repetitions:
                result['reason'] = 'bootstrap_draws_not_executed'
            elif result['missing_replicates']:
                result['reason'] = 'missing_bootstrap_statistics_no_silent_reweighting'
            else:
                replicates.sort()
                result['percentile_interval_95'] = [float(_percentile(replicates, Fraction(1, 40))), float(_percentile(replicates, Fraction(39, 40)))]
        results[name] = result
    shared = {key: value for key, value in driver.items() if key not in ('estimate', 'percentile_interval_95', 'reason', 'missing_replicates')}
    shared['driver_statistic'] = 'constant used only to drive shared resampling; no outcome is imputed'
    shared['cross_stratum_dependency_units'] = sum(len({block_strata[block] for block in blocks}) > 1 for blocks in driver['group_memberships'].values())
    return results, shared


def analyze_cases(cases, units, dependency_blocks, planned_strata, *, synthetic_blocks_per_stratum=None, bootstrap_repetitions=10000):
    if synthetic_blocks_per_stratum is None and bootstrap_repetitions != 10000:
        raise ValueError('Empirical analysis requires the fixed 10000 bootstrap repetitions')
    indexed, unit_index, block_strata = validate_inputs(cases, units, dependency_blocks, planned_strata,
                                                       synthetic_blocks_per_stratum=synthetic_blocks_per_stratum)
    blocks = sorted(block_strata)
    case_rows, anchor_rows, block_rows, summaries, omissions, macros = [], [], [], [], [], []
    block_values = {}
    for method in METHODS:
        for arm in ARMS:
            for block in blocks:
                distances = {anchor: {category: indexed[method, arm, block, anchor, category]['score'] for category in CATEGORIES} for anchor in ANCHORS}
                outcome = block_outcomes(distances)
                scope = {**_method(method), 'arm': arm, 'stratum_id': block_strata[block], 'block_id': block}
                for anchor in ANCHORS:
                    raw_cases = [indexed[method, arm, block, anchor, category] for category in CATEGORIES]
                    case_rows.extend({**row, 'context_condition': 'within_community' if row['category'] in CATEGORIES[:2] else 'cross_community',
                                      'label': 'same_author' if row['category'] in (CATEGORIES[0], CATEGORIES[2]) else 'different_author'} for row in raw_cases)
                    reasons = {condition: sorted({reason for row in raw_cases if row['category'] in categories and row['score'] is None for reason in row['reason_codes']})
                               for condition, categories in (('cross', CATEGORIES[2:]), ('within', CATEGORIES[:2]), ('stress', (CATEGORIES[1], CATEGORIES[2])))}
                    anchor_rows.append({**scope, 'anchor_id': anchor, **outcome['anchors'][anchor], 'unavailability_reason_codes': reasons})
                values = {'cross': outcome['cross_community']['complete_block_score'],
                          'within': outcome['within_community']['complete_block_score'],
                          'stress': outcome['stress_different_same_over_same_cross']['complete_block_score'],
                          'cross_minus_within': outcome['cross_minus_within_complete_block']}
                block_values[method, arm, block] = values
                block_rows.append({**scope, **values, 'cross_available_anchors': outcome['cross_community']['available_anchors'],
                                   'cross_missing_anchor_ids': outcome['cross_community']['missing_anchors'],
                                   'cross_available_anchor_mean_secondary': outcome['cross_community']['available_anchor_mean_secondary'],
                                   'within_missing_anchor_ids': outcome['within_community']['missing_anchors'],
                                   'stress_missing_anchor_ids': outcome['stress_different_same_over_same_cross']['missing_anchors']})
    series = {}
    for method_index, method in enumerate(METHODS):
        for arm in ARMS:
            for stratum in planned_strata:
                selected_blocks = [block for block in blocks if block_strata[block] == stratum]
                pairs = [row for row in case_rows if (row['method_id'], row['view'], row['n']) == method and row['arm'] == arm and row['stratum_id'] == stratum]
                anchors = [row for row in anchor_rows if (row['method_id'], row['view'], row['n']) == method and row['arm'] == arm and row['stratum_id'] == stratum]
                cross = {block: block_values[method, arm, block]['cross'] for block in selected_blocks if block_values[method, arm, block]['cross'] is not None}
                common = [block for block in selected_blocks if block_values[method, arm, block]['cross_minus_within'] is not None]
                within = {block: block_values[method, arm, block]['within'] for block in common}
                difference = {block: block_values[method, arm, block]['cross_minus_within'] for block in common}
                stress = {block: block_values[method, arm, block]['stress'] for block in selected_blocks if block_values[method, arm, block]['stress'] is not None}
                prefix = f'm{method_index}:{arm}:{stratum}'
                for metric, values in (('cross', cross), ('within_paired', within), ('cross_minus_within', difference), ('stress', stress)):
                    series[prefix + ':' + metric] = values
                context_metrics = {context: rank_metrics([(row['score'], row['label']) for row in pairs if row['context_condition'] == context]) for context in ('within_community', 'cross_community')}
                unit_rows = [unit_index[block, arm, cell] for block in selected_blocks for cell in CELLS]
                summary = {**_method(method), 'arm': arm, 'stratum_id': stratum,
                           'primary_method': method_index == 0, 'planned_blocks': len(selected_blocks),
                           'primary_cross': {'mean': _mean(cross.values()), 'complete_blocks': len(cross), 'incomplete_blocks': len(selected_blocks) - len(cross)},
                           'available_anchor_secondary': {'mean': _mean(row['cross_community'] for row in anchors),
                                                          'available_anchors': sum(row['cross_community'] is not None for row in anchors), 'planned_anchors': len(anchors)},
                           'paired_context': {'complete_blocks': len(common), 'within_mean': _mean(within.values()),
                                              'cross_mean': _mean(block_values[method, arm, block]['cross'] for block in common),
                                              'cross_minus_within_mean': _mean(difference.values())},
                           'hard_stress': {'mean': _mean(stress.values()), 'complete_blocks': len(stress)},
                           'comparisons': {'planned': len(pairs), 'qualified': sum(row['score'] is not None for row in pairs),
                                           'abstained': sum(row['score'] is None for row in pairs),
                                           'planned_class_counts': dict(Counter(row['label'] for row in pairs)),
                                           'qualified_class_counts': {label: sum(row['score'] is not None and row['label'] == label for row in pairs) for label in ('same_author', 'different_author')},
                                           'status_counts': dict(Counter(row['status'] for row in pairs)),
                                           'abstention_reason_counts': dict(Counter(reason for row in pairs if row['score'] is None for reason in row['reason_codes']))},
                           'context_rankings': context_metrics,
                           'units': {'planned': len(unit_rows), 'nonempty': sum(row['nonempty'] for row in unit_rows),
                                     'ordinary_volume_qualified': sum(row['ordinary_volume_guards_met'] for row in unit_rows),
                                     'retained_words': sum(row['retained_words'] for row in unit_rows), 'records': sum(row['records'] for row in unit_rows)},
                           'bootstrap_keys': {metric: prefix + ':' + metric for metric in ('cross', 'within_paired', 'cross_minus_within', 'stress')}}
                summaries.append(summary)
            if arm != 'full':
                for stratum in planned_strata:
                    selected_blocks = [block for block in blocks if block_strata[block] == stratum]
                    common = [block for block in selected_blocks if all(block_values[method, selected_arm, block]['cross'] is not None for selected_arm in ('full', arm))]
                    changes = {block: block_values[method, arm, block]['cross'] - block_values[method, 'full', block]['cross'] for block in common}
                    key = f'm{method_index}:{arm}:{stratum}:omission_change'
                    series[key] = changes
                    omissions.append({**_method(method), 'arm': arm, 'stratum_id': stratum, 'planned_blocks': len(selected_blocks),
                                      'full_complete_blocks': sum(block_values[method, 'full', block]['cross'] is not None for block in selected_blocks),
                                      'arm_complete_blocks': sum(block_values[method, arm, block]['cross'] is not None for block in selected_blocks),
                                      'intersection_complete_blocks': len(common),
                                      'full_mean_on_intersection': _mean(block_values[method, 'full', block]['cross'] for block in common),
                                      'arm_mean_on_intersection': _mean(block_values[method, arm, block]['cross'] for block in common),
                                      'arm_minus_full_mean_on_intersection': _mean(changes.values()), 'bootstrap_key': key})
    intervals, shared = shared_bootstrap(series, block_strata, dependency_blocks, repetitions=bootstrap_repetitions)
    for summary in summaries:
        summary['uncertainty'] = {metric: intervals[key] for metric, key in summary.pop('bootstrap_keys').items()}
    for row in omissions:
        row['uncertainty'] = intervals[row.pop('bootstrap_key')]
    for method in METHODS:
        for arm in ARMS:
            matching = [row for row in summaries if (row['method_id'], row['view'], row['n']) == method and row['arm'] == arm]
            macros.append({**_method(method), 'arm': arm,
                           'primary_cross_equal_stratum_macro': equal_stratum_macro({row['stratum_id']: row['primary_cross']['mean'] for row in matching}, planned_strata),
                           'paired_context_change_equal_stratum_macro': equal_stratum_macro({row['stratum_id']: row['paired_context']['cross_minus_within_mean'] for row in matching}, planned_strata)})
    return {'schema_version': 'pilot3-normalized-analysis-v1', 'analysis_version': VERSION,
            'scope': 'synthetic_test_only' if synthetic_blocks_per_stratum is not None else 'normalized_registered_study_cases',
            'planned': {'strata': list(planned_strata), 'blocks': len(blocks), 'source_account_slots': 2 * len(blocks),
                        'case_rows': len(case_rows), 'unit_rows': len(unit_index), 'methods': [_method(method) for method in METHODS], 'arms': list(ARMS)},
            'case_rows': case_rows, 'anchor_rows': anchor_rows, 'block_rows': block_rows,
            'unit_rows': [unit_index[key] for key in sorted(unit_index)], 'summaries': summaries,
            'omission_intersections': omissions, 'equal_stratum_macros': macros,
            'shared_bootstrap': shared, 'source_text_read': False, 'new_distances_computed': False,
            'limitations': ['Source-account labels are proxies, not verified human authorship or bot/human identities.',
                            'Global cluster draws preserve audited cross-stratum dependence; stratum counts may vary within draws.',
                            'Intervals require five contributing audited independent units and no unavailable replicate statistics.',
                            'Available-anchor summaries and omission intersections are selected-case diagnostics, not unconditional performance.',
                            'Whole-record identity, contamination audits and the truth of supplied normalized metadata require separate verification.',
                            'All planned unavailable cases remain present; no raw unqualified distance is substituted for a null score.']}


def _csv(rows):
    out = io.StringIO(newline='')
    if not rows:
        return b''
    fields = list(rows[0])
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json.dumps(value, sort_keys=True, separators=(',', ':')) if isinstance(value, (list, dict)) else value for key, value in row.items()})
    return out.getvalue().encode()


def write_outputs(report, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    artifacts = {}
    for key in ('case_rows', 'anchor_rows', 'block_rows', 'unit_rows', 'summaries', 'omission_intersections', 'equal_stratum_macros'):
        artifacts[key + '.json'] = (json.dumps(report[key], sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
        artifacts[key + '.csv'] = _csv(report[key])
    artifacts['analysis.json'] = (json.dumps({key: value for key, value in report.items() if key not in ('case_rows', 'anchor_rows', 'block_rows', 'unit_rows')}, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    for name, raw in artifacts.items():
        (output_dir / name).write_bytes(raw)
    hashes = {name: {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)} for name, raw in artifacts.items()}
    (output_dir / 'output-hashes.json').write_text(json.dumps(hashes, sort_keys=True, indent=2) + '\n')
    return hashes


def main():
    parser = argparse.ArgumentParser()
    for name in ('cases', 'units', 'dependencies', 'plan', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    def load(path):
        return json.loads(path.read_bytes(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON input')))
    plan = load(args.plan)
    if plan.get('registered_before_scoring') is not True or not re.fullmatch(r'[0-9a-f]{64}', plan.get('registered_protocol_sha256', '')):
        raise ValueError('Real analysis CLI requires explicit supplied prior scoring registration')
    current_code = {'analysis_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    'study_math_sha256': hashlib.sha256(Path(__file__).with_name('study_math.py').read_bytes()).hexdigest()}
    if any(plan.get(key) != value for key, value in current_code.items()):
        raise ValueError('Analysis implementation differs from supplied preregistered code bindings')
    report = analyze_cases(load(args.cases), load(args.units), load(args.dependencies), plan['planned_strata'])
    report['input_bindings'] = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in (
        ('cases_sha256', args.cases), ('units_sha256', args.units), ('dependencies_sha256', args.dependencies), ('analysis_plan_sha256', args.plan))}
    report['code_bindings'] = current_code
    hashes = write_outputs(report, args.out)
    print(json.dumps({'status': 'normalized_analysis_complete', 'planned': report['planned'], 'artifact_count': len(hashes)}))


if __name__ == '__main__':
    main()
