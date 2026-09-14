#!/usr/bin/env python3
"""Post-registration reporting tables; no source reading, scoring or new inference.

All registered outcomes remain in analyze_cases outputs. These tables expose
their fields, observed input distributions and qualifying-case distance shifts.
No threshold, extra arm, hypothesis test or method selection is introduced.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import statistics
import numpy as np


def distribution(values):
    values = list(values)
    return {'count': len(values), 'mean': statistics.fmean(values) if values else None,
            **{key: float(value) for key, value in zip(('min', 'q25', 'median', 'q75', 'max'),
                                                       np.percentile(values, [0, 25, 50, 75, 100]))}} if values else {
        'count': 0, 'mean': None, 'min': None, 'q25': None, 'median': None, 'q75': None, 'max': None}


def write(root, name, rows):
    with (root / (name + '.json')).open('x') as f:
        json.dump(rows, f, indent=2, sort_keys=True, allow_nan=False)
        f.write('\n')
    with (root / (name + '.csv')).open('x', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v
                         for k, v in row.items()} for row in rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--analysis', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    load = lambda name: json.loads((args.analysis / (name + '.json')).read_bytes())
    summaries, units, cases = load('summaries'), load('unit_rows'), load('case_rows')
    args.out.mkdir(parents=True, exist_ok=False)
    table = []
    for s in summaries:
        row = {k: s[k] for k in ('method_id', 'view', 'n', 'arm', 'stratum_id', 'primary_method')}
        row.update(planned_blocks=s['planned_blocks'], **s['primary_cross'])
        row.update({f'paired_{k}': v for k, v in s['paired_context'].items()})
        row.update({f'stress_{k}': v for k, v in s['hard_stress'].items()})
        row.update({f'comparisons_{k}': v for k, v in s['comparisons'].items()})
        row.update({f'units_{k}': v for k, v in s['units'].items()})
        row.update({f'available_anchor_{k}': v for k, v in s['available_anchor_secondary'].items()})
        for outcome, uncertainty in s['uncertainty'].items():
            row.update({f'{outcome}_{k}': v for k, v in uncertainty.items()})
        for context, rankings in s['context_rankings'].items():
            row.update({f'{context}_{k}': v for k, v in rankings.items()})
        selected = [u for u in units if u['stratum_id'] == s['stratum_id'] and u['arm'] == s['arm']]
        for field in ('records', 'retained_words'):
            row.update({f'unit_{field}_{k}': v for k, v in distribution(u[field] for u in selected).items()})
        table.append(row)
    write(args.out, 'method-context-missingness', table)
    grouped = defaultdict(list)
    for row in cases:
        key = tuple(row[k] for k in ('method_id', 'view', 'n', 'arm', 'stratum_id', 'category'))
        grouped[key].append(row)
    distributions = []
    for key, rows in grouped.items():
        base = dict(zip(('method_id', 'view', 'n', 'arm', 'stratum_id', 'category'), key))
        for kind in ('score', 'raw_distance'):
            distributions.append({**base, 'value_kind': kind, 'planned_cases': len(rows),
                                  'null_values': sum(r[kind] is None for r in rows),
                                  **distribution(r[kind] for r in rows if r[kind] is not None)})
    write(args.out, 'distance-distributions', distributions)
    key_fields = ('method_id', 'view', 'n', 'stratum_id', 'block_id', 'anchor_id', 'category')
    full = {tuple(r[k] for k in key_fields): r for r in cases if r['arm'] == 'full'}
    changes = defaultdict(list)
    for r in cases:
        if r['arm'] == 'full':
            continue
        before = full[tuple(r[k] for k in key_fields)]
        key = tuple(r[k] for k in ('method_id', 'view', 'n', 'stratum_id', 'arm', 'category'))
        changes[key].append((before['score'], r['score']))
    intersections = []
    for key, pairs in changes.items():
        selected = [(a, b) for a, b in pairs if a is not None and b is not None]
        intersections.append({**dict(zip(('method_id', 'view', 'n', 'stratum_id', 'arm', 'category'), key)),
                              'planned_cases': len(pairs), 'full_qualified': sum(a is not None for a, b in pairs),
                              'arm_qualified': sum(b is not None for a, b in pairs),
                              'intersection_cases': len(selected),
                              'full_mean_on_intersection': statistics.fmean(a for a, b in selected) if selected else None,
                              'arm_mean_on_intersection': statistics.fmean(b for a, b in selected) if selected else None,
                              **{f'arm_minus_full_{k}': v for k, v in distribution(b-a for a, b in selected).items()}})
    write(args.out, 'distance-omission-intersections', intersections)
    assert len(table) == 36 and len(distributions) == 288 and len(intersections) == 108
    receipt = {'status': 'reporting_tables_complete', 'post_registration_reporting_only': True,
               'quantiles': 'numpy.percentile default linear/type7; descriptive only',
               'source_text_read': False, 'new_scores_or_inference': False,
               'registered_outcomes_redefined': False,
               'input_hashes': {name: hashlib.sha256((args.analysis/name).read_bytes()).hexdigest()
                                for name in ('summaries.json', 'unit_rows.json', 'case_rows.json')},
               'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'table_rows': {'method-context-missingness': len(table), 'distance-distributions': len(distributions),
                              'distance-omission-intersections': len(intersections)}}
    with (args.out/'reporting-receipt.json').open('x') as f:
        json.dump(receipt, f, indent=2, sort_keys=True); f.write('\n')
    print(json.dumps(receipt['table_rows']))


if __name__ == '__main__':
    main()
