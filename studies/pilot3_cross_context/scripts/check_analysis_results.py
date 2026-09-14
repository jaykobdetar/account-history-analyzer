#!/usr/bin/env python3
"""Independent sanitized metric arithmetic and bootstrap verification.

No imports from the analyzer, study_math, AHAS, or any prose loader. Orderings,
rank metrics, and draw estimates use exact rational arithmetic. Every planned
row and all unavailable observations remain in their original denominator.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
import csv
import hashlib
from itertools import product
import json
import math
from pathlib import Path
import resource
import signal
import time

METHODS = (('cosine_distance_v1', 'retained_prose', 4), ('cosine_distance_v1', 'function_mask_v1', 4), ('function_word_js_v1', 'lexical_tokens', None))
ARMS = ('full', 'hash75', 'hash50', 'middle50')
ANCHORS = ('A/X', 'A/Y', 'B/X', 'B/Y')
CATEGORIES = ('same_account_same_community', 'different_account_same_community', 'same_account_different_community', 'different_account_different_community')
CELLS = tuple('/'.join(cell) for cell in product(('A', 'B'), ('X', 'Y'), ('early', 'late')))
SEED = 'ahas-pilot3-cross-context-block-bootstrap-v1'
GENERATOR = 'sha256-json-counter-rejection-v1'
MAX_SECONDS, MAX_AS, MAX_OUTPUT = 600, 4 * 1024**3, 20 * 1024**2


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def fp(path):
    path = Path(path)
    with path.open('rb') as handle:
        hashed = hashlib.file_digest(handle, 'sha256').hexdigest()
    return {'sha256': hashed, 'bytes': path.stat().st_size}


def read(path):
    return json.loads(Path(path).read_bytes(), parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite_json')))


def mean(values):
    present = [Fraction(value) for value in values if value is not None]
    return float(sum(present, Fraction()) / len(present)) if present else None


def order(same, different):
    if same is None or different is None:
        return None
    # Comparisons are exact; do not round scores or apply a numerical tolerance.
    return float(Fraction(1) if different > same else Fraction(1, 2) if different == same else Fraction())


def ranking(rows):
    planned = Counter(label for _, label in rows)
    observed = [(score, label) for score, label in rows if score is not None]
    qualified = Counter(label for _, label in observed)
    positive = [s for s, label in observed if label == 'different_author']
    negative = [s for s, label in observed if label == 'same_author']
    twice_wins = sum(2 if p > n else 1 if p == n else 0 for p in positive for n in negative)
    auc = float(Fraction(twice_wins, 2 * len(positive) * len(negative))) if positive and negative else None
    ranked = sorted(observed, reverse=True)
    ap, consumed, tp = Fraction(), 0, 0
    while consumed < len(ranked):
        finish = consumed + 1
        while finish < len(ranked) and ranked[finish][0] == ranked[consumed][0]:
            finish += 1
        gained = sum(label == 'different_author' for _, label in ranked[consumed:finish])
        tp += gained
        ap += Fraction(gained * tp, finish)
        consumed = finish
    ap = float(ap / len(positive)) if positive else None
    return {'planned_pairs': len(rows), 'qualified_pairs': len(observed), 'abstained_pairs': len(rows)-len(observed),
            'planned_class_counts': {k: planned[k] for k in ('same_author', 'different_author')},
            'qualified_class_counts': {k: qualified[k] for k in ('same_author', 'different_author')},
            'roc_auc': auc, 'roc_auc_reason': None if auc is not None else 'both_scored_labels_required',
            'average_precision': ap, 'average_precision_reason': None if ap is not None else 'no_scored_positive_pairs',
            'positive_label': 'different_author', 'positive_label_meaning': 'different_source_account_proxy'}


def macro(values, strata):
    missing = [s for s in strata if values.get(s) is None]
    return {'value': None if missing else mean(values[s] for s in strata), 'planned_strata': len(strata),
            'available_strata': len(strata)-len(missing), 'missing_strata': missing, 'reason': 'planned_strata_missing' if missing else None}


def draw_index(size, replicate, ordinal):
    bound = 2**256 - 2**256 % size
    for retry in range(100):
        data = json.dumps([GENERATOR, SEED, replicate, ordinal, retry], ensure_ascii=False, separators=(',', ':')).encode()
        number = int(hashlib.sha256(data).hexdigest(), 16)
        if number < bound:
            return number % size
    raise RuntimeError('sha256_rejection_bound')


def frequency_percentile(frequencies, probability):
    """Exact type-7 percentile using an independently accumulated frequency map."""
    total = sum(frequencies.values())
    position = (total - 1) * probability
    lower = position.numerator // position.denominator
    upper = min(lower + 1, total - 1)
    lower_value = upper_value = None
    before = 0
    for value, count in sorted(frequencies.items()):
        if before <= lower < before + count:
            lower_value = value
        if before <= upper < before + count:
            upper_value = value
            break
        before += count
    return float(lower_value + (upper_value - lower_value) * (position - lower))


def bootstrap(series, block_strata, dependencies, repetitions=10000):
    groups = defaultdict(list)
    for block in sorted(block_strata):
        groups[dependencies[block]].append(block)
    groups = dict(sorted(groups.items()))
    names = list(groups)
    contributors = {key: len({dependencies[b] for b in values}) for key, values in series.items()}
    active = [key for key in series if contributors[key] >= 5 and series[key]]
    # A vector statistic with no estimable component deliberately executes no draws.
    draws = repetitions if len(groups) >= 5 and active else 0
    frequencies, missing = {k: Counter() for k in active}, Counter()
    group_vectors = {}
    for key in active:
        group_vectors[key] = []
        for name in names:
            present = [Fraction(series[key][b]) * 8 for b in groups[name] if b in series[key]]
            if any(v.denominator != 1 for v in present):
                raise ValueError('non_eighth_complete_block_outcome')
            group_vectors[key].append((sum(v.numerator for v in present), len(present)))
    draw_hash = hashlib.sha256()
    for replicate in range(draws):
        sampled = [draw_index(len(groups), replicate, ordinal) for ordinal in range(len(groups))]
        serialized = json.dumps([names[i] for i in sampled], ensure_ascii=False, separators=(',', ':')) + '\n'
        draw_hash.update(serialized.encode())
        weights = Counter(sampled)
        for key in active:
            numerator = denominator = 0
            vectors = group_vectors[key]
            for index, multiplicity in weights.items():
                value, count = vectors[index]
                numerator += multiplicity * value
                denominator += multiplicity * count
            if denominator:
                frequencies[key][Fraction(numerator, 8 * denominator)] += 1
            else:
                missing[key] += 1
    hashed = draw_hash.hexdigest() if draws else None
    uncertainty = {}
    for key, values in series.items():
        result = {'estimate': mean(values.values()), 'contributing_blocks': len(values), 'contributing_independent_units': contributors[key],
                  'minimum_independent_units': 5, 'requested_repetitions': repetitions, 'executed_repetitions': 0,
                  'missing_replicates': 0, 'percentile_interval_95': None, 'shared_draws_sha256': hashed, 'reason': None}
        if not values:
            result['reason'] = 'descriptive_statistic_unavailable'
        elif contributors[key] < 5:
            result['reason'] = 'inadequate_independent_units_for_uncertainty'
        else:
            result['executed_repetitions'], result['missing_replicates'] = draws, missing[key]
            if draws != repetitions:
                result['reason'] = 'bootstrap_draws_not_executed'
            elif missing[key]:
                result['reason'] = 'missing_bootstrap_statistics_no_silent_reweighting'
            else:
                result['percentile_interval_95'] = [frequency_percentile(frequencies[key], q) for q in (Fraction(1, 40), Fraction(39, 40))]
        uncertainty[key] = result
    shared = {'generator': GENERATOR, 'seed': SEED, 'arithmetic': 'exact Fraction of finite binary-float inputs; type-7 percentiles',
              'resampling': 'global_independent_group_with_replacement', 'requested_repetitions': repetitions,
              'executed_repetitions': draws, 'minimum_independent_units': 5, 'independent_unit_count': len(groups),
              'block_count': len(block_strata), 'group_memberships': groups, 'stratum_block_counts': dict(sorted(Counter(block_strata.values()).items())),
              'draws_sha256': hashed, 'driver_statistic': 'constant used only to drive shared resampling; no outcome is imputed',
              'cross_stratum_dependency_units': sum(len({block_strata[b] for b in blocks}) > 1 for blocks in groups.values())}
    return uncertainty, shared


def inputs(cases, units, dependencies, strata, per_stratum):
    if len(strata) != 3 or len(set(strata)) != 3:
        raise ValueError('three_explicit_planned_strata_required')
    block_strata, unit_index = {}, {}
    for row in units:
        b, s, arm, cell = (row[k] for k in ('block_id', 'stratum_id', 'arm', 'cell_id'))
        if s not in strata or arm not in ARMS or cell not in CELLS or (b in block_strata and block_strata[b] != s):
            raise ValueError('unplanned_unit_identity')
        key = b, arm, cell
        if key in unit_index:
            raise ValueError('duplicate_unit')
        block_strata[b], unit_index[key] = s, row
        n, w = row['records'], row['retained_words']
        if type(n) is not int or type(w) is not int or n < 0 or w < 20*n or (n == 0 and w != 0) or row['nonempty'] != (n > 0) or row['ordinary_volume_guards_met'] != (n >= 8 and w >= 1000):
            raise ValueError('unit_guard_or_volume_mismatch')
    if set(dependencies) != set(block_strata) or any(Counter(block_strata.values())[s] != per_stratum for s in strata):
        raise ValueError('missing_planned_block_or_dependency')
    if set(unit_index) != set(product(block_strata, ARMS, CELLS)):
        raise ValueError('missing_planned_unit')
    for b, cell in product(block_strata, CELLS):
        full, h75, h50, mid = (unit_index[b, arm, cell] for arm in ARMS)
        if any(not h50[k] <= h75[k] <= full[k] or mid[k] > full[k] for k in ('records', 'retained_words')) or mid['records'] != full['records'] - (3*full['records']//4-full['records']//4):
            raise ValueError('omission_counts_or_rounding_mismatch')
    indexed = {}
    for row in cases:
        method = tuple(row[k] for k in ('method_id', 'view', 'n'))
        key = method, row['arm'], row['block_id'], row['anchor_id'], row['category']
        if key in indexed:
            raise ValueError('duplicate_case')
        if method not in METHODS or row['arm'] not in ARMS or row['anchor_id'] not in ANCHORS or row['category'] not in CATEGORIES or block_strata.get(row['block_id']) != row['stratum_id']:
            raise ValueError('unplanned_case_identity')
        for k in ('score', 'raw_distance'):
            value = row[k]
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError('invalid_distance')
        if row['status'] != ('ok' if row['score'] is not None else 'abstained') or (row['score'] is None and not row['reason_codes']) or (row['score'] is not None and row['score'] != row['raw_distance']):
            raise ValueError('qualified_score_or_abstention_mismatch')
        if row['score'] is not None:
            a, c = row['anchor_id'].split('/')
            index = CATEGORIES.index(row['category'])
            late = (('B' if a == 'A' else 'A') if index % 2 else a) + '/' + (('Y' if c == 'X' else 'X') if index >= 2 else c) + '/late'
            if not all(unit_index[row['block_id'], row['arm'], side]['ordinary_volume_guards_met'] for side in (row['anchor_id'] + '/early', late)):
                raise ValueError('score_bypasses_unit_guard')
        indexed[key] = row
    if set(indexed) != set(product(METHODS, ARMS, block_strata, ANCHORS, CATEGORIES)):
        raise ValueError('missing_planned_case')
    return indexed, unit_index, block_strata


def recompute(cases, units, dependencies, strata, *, per_stratum=10, repetitions=10000):
    indexed, unit_index, block_strata = inputs(cases, units, dependencies, strata, per_stratum)
    blocks = sorted(block_strata)
    augmented, anchors, block_rows, block_values = [], [], [], {}
    summaries, omissions, macros, series = [], [], [], {}
    for method, arm, block in product(METHODS, ARMS, blocks):
        scope = dict(zip(('method_id', 'view', 'n'), method)) | {'arm': arm, 'stratum_id': block_strata[block], 'block_id': block}
        outcomes = {}
        for anchor in ANCHORS:
            raw = [indexed[method, arm, block, anchor, c] for c in CATEGORIES]
            for j, row in enumerate(raw):
                augmented.append({**row, 'context_condition': 'cross_community' if j >= 2 else 'within_community', 'label': 'different_author' if j % 2 else 'same_author'})
            values = [row['score'] for row in raw]
            result = {'cross_community': order(values[2], values[3]), 'within_community': order(values[0], values[1]), 'stress_different_same_over_same_cross': order(values[2], values[1])}
            outcomes[anchor] = result
            reasons = {name: sorted({reason for i in positions if raw[i]['score'] is None for reason in raw[i]['reason_codes']}) for name, positions in (('cross', (2, 3)), ('within', (0, 1)), ('stress', (1, 2)))}
            anchors.append({**scope, 'anchor_id': anchor, **result, 'unavailability_reason_codes': reasons})
        fields = {'cross': 'cross_community', 'within': 'within_community', 'stress': 'stress_different_same_over_same_cross'}
        available = {name: [outcomes[a][field] for a in ANCHORS if outcomes[a][field] is not None] for name, field in fields.items()}
        values = {name: mean(v) if len(v) == 4 else None for name, v in available.items()}
        values['cross_minus_within'] = None if values['cross'] is None or values['within'] is None else values['cross']-values['within']
        block_values[method, arm, block] = values
        block_rows.append({**scope, **values, 'cross_available_anchors': len(available['cross']), 'cross_missing_anchor_ids': [a for a in ANCHORS if outcomes[a]['cross_community'] is None],
                           'cross_available_anchor_mean_secondary': mean(available['cross']), 'within_missing_anchor_ids': [a for a in ANCHORS if outcomes[a]['within_community'] is None],
                           'stress_missing_anchor_ids': [a for a in ANCHORS if outcomes[a]['stress_different_same_over_same_cross'] is None]})
    for method_number, method in enumerate(METHODS):
        for arm in ARMS:
            for s in strata:
                selected = [b for b in blocks if block_strata[b] == s]
                pairs = [r for r in augmented if tuple(r[k] for k in ('method_id', 'view', 'n')) == method and r['arm'] == arm and r['stratum_id'] == s]
                observed_anchors = [r for r in anchors if tuple(r[k] for k in ('method_id', 'view', 'n')) == method and r['arm'] == arm and r['stratum_id'] == s]
                cross = {b: block_values[method, arm, b]['cross'] for b in selected if block_values[method, arm, b]['cross'] is not None}
                both = [b for b in selected if block_values[method, arm, b]['cross_minus_within'] is not None]
                within = {b: block_values[method, arm, b]['within'] for b in both}
                delta = {b: block_values[method, arm, b]['cross_minus_within'] for b in both}
                stress = {b: block_values[method, arm, b]['stress'] for b in selected if block_values[method, arm, b]['stress'] is not None}
                prefix = f'm{method_number}:{arm}:{s}'
                for metric, values in (('cross', cross), ('within_paired', within), ('cross_minus_within', delta), ('stress', stress)):
                    series[prefix + ':' + metric] = values
                these_units = [unit_index[b, arm, cell] for b, cell in product(selected, CELLS)]
                summaries.append(dict(zip(('method_id', 'view', 'n'), method)) | {'arm': arm, 'stratum_id': s, 'primary_method': method_number == 0,
                    'planned_blocks': len(selected), 'primary_cross': {'mean': mean(cross.values()), 'complete_blocks': len(cross), 'incomplete_blocks': len(selected)-len(cross)},
                    'available_anchor_secondary': {'mean': mean(r['cross_community'] for r in observed_anchors), 'available_anchors': sum(r['cross_community'] is not None for r in observed_anchors), 'planned_anchors': len(observed_anchors)},
                    'paired_context': {'complete_blocks': len(both), 'within_mean': mean(within.values()), 'cross_mean': mean(block_values[method, arm, b]['cross'] for b in both), 'cross_minus_within_mean': mean(delta.values())},
                    'hard_stress': {'mean': mean(stress.values()), 'complete_blocks': len(stress)},
                    'comparisons': {'planned': len(pairs), 'qualified': sum(r['score'] is not None for r in pairs), 'abstained': sum(r['score'] is None for r in pairs),
                                    'planned_class_counts': dict(Counter(r['label'] for r in pairs)), 'qualified_class_counts': {label: sum(r['score'] is not None and r['label'] == label for r in pairs) for label in ('same_author', 'different_author')},
                                    'status_counts': dict(Counter(r['status'] for r in pairs)), 'abstention_reason_counts': dict(Counter(reason for r in pairs if r['score'] is None for reason in r['reason_codes']))},
                    'context_rankings': {context: ranking([(r['score'], r['label']) for r in pairs if r['context_condition'] == context]) for context in ('within_community', 'cross_community')},
                    'units': {'planned': len(these_units), 'nonempty': sum(r['nonempty'] for r in these_units), 'ordinary_volume_qualified': sum(r['ordinary_volume_guards_met'] for r in these_units), 'retained_words': sum(r['retained_words'] for r in these_units), 'records': sum(r['records'] for r in these_units)},
                    '_keys': {name: prefix + ':' + name for name in ('cross', 'within_paired', 'cross_minus_within', 'stress')}})
            if arm != 'full':
                for s in strata:
                    selected = [b for b in blocks if block_strata[b] == s]
                    overlap = [b for b in selected if all(block_values[method, a, b]['cross'] is not None for a in ('full', arm))]
                    change = {b: block_values[method, arm, b]['cross']-block_values[method, 'full', b]['cross'] for b in overlap}
                    key = f'm{method_number}:{arm}:{s}:omission_change'
                    series[key] = change
                    omissions.append(dict(zip(('method_id', 'view', 'n'), method)) | {'arm': arm, 'stratum_id': s, 'planned_blocks': len(selected),
                        'full_complete_blocks': sum(block_values[method, 'full', b]['cross'] is not None for b in selected), 'arm_complete_blocks': sum(block_values[method, arm, b]['cross'] is not None for b in selected),
                        'intersection_complete_blocks': len(overlap), 'full_mean_on_intersection': mean(block_values[method, 'full', b]['cross'] for b in overlap),
                        'arm_mean_on_intersection': mean(block_values[method, arm, b]['cross'] for b in overlap), 'arm_minus_full_mean_on_intersection': mean(change.values()), '_key': key})
    uncertainty, shared = bootstrap(series, block_strata, dependencies, repetitions)
    for row in summaries:
        row['uncertainty'] = {metric: uncertainty[key] for metric, key in row.pop('_keys').items()}
    for row in omissions:
        row['uncertainty'] = uncertainty[row.pop('_key')]
    for method, arm in product(METHODS, ARMS):
        selected = [r for r in summaries if tuple(r[k] for k in ('method_id', 'view', 'n')) == method and r['arm'] == arm]
        macros.append(dict(zip(('method_id', 'view', 'n'), method)) | {'arm': arm,
            'primary_cross_equal_stratum_macro': macro({r['stratum_id']: r['primary_cross']['mean'] for r in selected}, strata),
            'paired_context_change_equal_stratum_macro': macro({r['stratum_id']: r['paired_context']['cross_minus_within_mean'] for r in selected}, strata)})
    return {'planned': {'strata': list(strata), 'blocks': len(blocks), 'source_account_slots': 2*len(blocks), 'case_rows': len(augmented), 'unit_rows': len(units), 'methods': [dict(zip(('method_id', 'view', 'n'), m)) for m in METHODS], 'arms': list(ARMS)},
            'case_rows': augmented, 'anchor_rows': anchors, 'block_rows': block_rows, 'unit_rows': [unit_index[k] for k in sorted(unit_index)],
            'summaries': summaries, 'omission_intersections': omissions, 'equal_stratum_macros': macros, 'shared_bootstrap': shared}


def differences(expected, actual, prefix='result'):
    """Exact structural comparison; never print a mismatching value."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(expected) != set(actual):
            return [prefix + ':fields']
        return [error for key in expected for error in differences(expected[key], actual[key], prefix + '.' + key)]
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return [prefix + ':rows']
        return [error for i, value in enumerate(expected) for error in differences(value, actual[i], prefix + f'[{i}]')]
    return [] if expected == actual else [prefix + ':value']


def verify_csv(path, expected):
    with Path(path).open(newline='') as handle:
        actual = list(csv.DictReader(handle))
    projected = [{key: json.dumps(value, sort_keys=True, separators=(',', ':')) if isinstance(value, (list, dict)) else '' if value is None else str(value) for key, value in row.items()} for row in expected]
    return differences(projected, actual, Path(path).name)


def verify(args):
    started = time.monotonic()
    cases, units, dependencies, plan = (read(p) for p in (args.cases, args.units, args.dependencies, args.plan))
    if plan.get('registered_before_scoring') is not True:
        raise ValueError('analysis_registration_missing')
    expected = recompute(cases, units, dependencies, plan['planned_strata'])
    analysis = read(args.results / 'analysis.json')
    failures = []
    for key, value in expected.items():
        actual = analysis[key] if key in ('planned', 'shared_bootstrap') else read(args.results / (key + '.json'))
        failures.extend(differences(value, actual, key))
        if key not in ('planned', 'shared_bootstrap'):
            failures.extend(verify_csv(args.results / (key + '.csv'), value))
        if key in analysis:
            failures.extend(differences(value, analysis[key], 'analysis.' + key))
    bindings = {name: fp(path)['sha256'] for name, path in (('cases_sha256', args.cases), ('units_sha256', args.units), ('dependencies_sha256', args.dependencies), ('analysis_plan_sha256', args.plan))}
    failures.extend(differences(bindings, analysis['input_bindings'], 'input_bindings'))
    code = {k: fp(Path(__file__).with_name(name))['sha256'] for k, name in (('analysis_sha256', 'analyze_cases.py'), ('study_math_sha256', 'study_math.py'))}
    failures.extend(differences(code, analysis['code_bindings'], 'code_bindings'))
    failures.extend(differences(code, {k: plan[k] for k in code}, 'plan_code_bindings'))
    hashes = read(args.results / 'output-hashes.json')
    required = {key + suffix for key in ('case_rows', 'anchor_rows', 'block_rows', 'unit_rows', 'summaries', 'omission_intersections', 'equal_stratum_macros') for suffix in ('.json', '.csv')} | {'analysis.json'}
    if set(hashes) != required:
        failures.append('output_hash_inventory')
    for name in sorted(required):
        failures.extend(differences(fp(args.results / name), hashes.get(name), 'output_hash.' + name))
    if analysis['source_text_read'] is not False or analysis['new_distances_computed'] is not False or analysis['scope'] != 'normalized_registered_study_cases':
        failures.append('analysis_scope')
    return {'status': 'pass' if not failures else 'fail', 'failed_checks': failures, 'case_rows_checked': len(cases), 'unit_rows_checked': len(units),
            'anchor_rows_checked': len(expected['anchor_rows']), 'block_rows_checked': len(expected['block_rows']), 'stratum_summaries_checked': len(expected['summaries']),
            'omission_intersections_checked': len(expected['omission_intersections']), 'equal_stratum_macros_checked': len(expected['equal_stratum_macros']),
            'bootstrap_series_recomputed': len(expected['summaries'])*4+len(expected['omission_intersections']), 'bootstrap_repetitions': 10000,
            'bootstrap_draws_sha256': expected['shared_bootstrap']['draws_sha256'], 'independent_dependency_units': expected['shared_bootstrap']['independent_unit_count'],
            'input_hashes': {name: fp(getattr(args, name)) for name in ('cases', 'units', 'dependencies', 'plan')},
            'output_manifest': fp(args.results / 'output-hashes.json'), 'checker_sha256': fp(__file__)['sha256'],
            'wall_seconds': time.monotonic()-started, 'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
            'original_prose_reads': 0, 'new_distances_computed': 0, 'limitations': ['Checks normalized score arithmetic and aggregate output bindings. Source fidelity, evaluator qualification and dependency truth require their separate frozen checks.']}


def main():
    parser = argparse.ArgumentParser()
    for name in ('cases', 'units', 'dependencies', 'results', 'plan', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (MAX_AS,) * 2)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('independent_analysis_wall_limit')))
    signal.alarm(MAX_SECONDS)
    with args.out.with_suffix('.start-binding.json').open('x') as handle:
        json.dump({'phase': 'before_independent_analysis_input_reads', 'utc': datetime.now(timezone.utc).isoformat(), 'checker': fp(__file__),
                   'limits': {'wall_seconds': MAX_SECONDS, 'address_space_bytes': MAX_AS, 'output_bytes': MAX_OUTPUT}, 'original_prose_reads': 0, 'new_distances_computed': 0}, handle, indent=2)
        handle.write('\n')
    report = verify(args)
    payload = canonical(report) + b'\n'
    if len(payload) > MAX_OUTPUT or report['wall_seconds'] > MAX_SECONDS:
        raise RuntimeError('independent_analysis_resource_limit')
    with args.out.open('xb') as handle:
        handle.write(payload)
    signal.alarm(0)
    print(json.dumps({'status': report['status'], 'failed_checks': report['failed_checks'], 'bootstrap_series_recomputed': report['bootstrap_series_recomputed'], 'output': fp(args.out)}))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
