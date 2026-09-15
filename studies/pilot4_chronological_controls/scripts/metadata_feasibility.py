"""Pilot4 score-free metadata feasibility; no source writing or engine imports."""
from __future__ import annotations
import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import resource
import time

DAY = 86400
CELL_KEYS = ('X/early', 'X/late', 'Y/early', 'Y/late')
SALT = 'pilot4-feasibility-identity-order-v1\0'
COST_RULE = 'sum_four_cells(abs(medianA-medianB)/(180*86400)+abs(wordsA-wordsB)/5000+abs(recordsA-recordsB)/40)'
BAND_RULE = '[cut-180days,cut) and [cut,cut+180days)'
TIE_RULE = 'Within a cut: sorted SHA256(salt+casefold(account)) edge tuples; across cuts: maximum cardinality, minimum exact cost, earliest UTC cut.'


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def seconds(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise ValueError('UTC metadata required')
    result = parsed.timestamp()
    if not result.is_integer():
        raise ValueError('Integer-second metadata required')
    return int(result)


def identity_order(value):
    return hashlib.sha256((SALT + value.casefold()).encode()).hexdigest()


def jsonable(value):
    if isinstance(value, Fraction):
        return {'numerator': value.numerator, 'denominator': value.denominator}
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(v) for v in value]
    return value


def write(path, value, *, private=False):
    path = Path(path)
    with path.open('x') as handle:
        json.dump(jsonable(value), handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write('\n')
    if private:
        path.chmod(0o600)


def select_prefix(records, cut, period, plan):
    """Pure metadata prefix. Rows require timestamp,record_id,retained_words."""
    if period not in ('early', 'late'):
        raise ValueError('Unknown period')
    span = plan['half_band_days'] * DAY
    start, end = (cut-span, cut) if period == 'early' else (cut, cut+span)
    candidates = [r for r in records if start <= r['timestamp'] < end and
                  plan['record_word_min'] <= r['retained_words'] <= plan['record_word_max']]
    candidates.sort(key=lambda r: (abs(cut-r['timestamp']), r['timestamp'], r['record_id']))
    selected, words = [], 0
    for row in candidates:
        selected.append(row)
        words += row['retained_words']
        if words > plan['half_max_words'] or len(selected) > plan['half_max_records']:
            return None
        if words >= plan['half_target_words'] and len(selected) >= plan['half_min_records']:
            selected.sort(key=lambda r: (r['timestamp'], r['record_id']))
            n = len(selected)
            median = Fraction(selected[n//2]['timestamp']) if n % 2 else Fraction(
                selected[n//2-1]['timestamp'] + selected[n//2]['timestamp'], 2)
            return {'records': n, 'retained_words': words, 'median_timestamp': median,
                    'first_timestamp': selected[0]['timestamp'], 'last_timestamp': selected[-1]['timestamp'],
                    'rows': selected}
    return None


def compatible(left, right, plan):
    """All four medians per period and all eight volume cells are gated."""
    if set(left) != set(CELL_KEYS) or set(right) != set(CELL_KEYS):
        return False
    cells = list(left.values()) + list(right.values())
    for field, limit in [('retained_words', Fraction(plan['all_eight_cell_word_ratio_max'])),
                         ('records', Fraction(plan['all_eight_cell_record_ratio_max']))]:
        values = [c[field] for c in cells]
        if min(values) <= 0 or Fraction(max(values), min(values)) > limit:
            return False
    for period in ('early', 'late'):
        values = [p[c+'/'+period]['median_timestamp'] for p in (left, right) for c in ('X', 'Y')]
        if max(values) - min(values) > plan['within_period_four_cell_median_span_days_max'] * DAY:
            return False
    return True


def edge_cost(left, right, plan):
    return sum((abs(left[k]['median_timestamp'] - right[k]['median_timestamp']) /
                Fraction(plan['half_band_days'] * DAY) +
                Fraction(abs(left[k]['retained_words'] - right[k]['retained_words']), plan['half_target_words']) +
                Fraction(abs(left[k]['records'] - right[k]['records']), plan['half_min_records'])
                for k in CELL_KEYS), Fraction())


def exact_matching(nodes, edges, check=lambda: None):
    """General-graph exact max-cardinality/min-cost matching, component subset DP.

    edges maps canonical (left,right) tuples to exact Fractions. Input node order
    supplies deterministic ties. Resource exhaustion is an incomplete search.
    """
    nodes = list(nodes)
    index = {n: i for i, n in enumerate(nodes)}
    if len(index) != len(nodes):
        raise ValueError('Duplicate graph vertex')
    costs, adjacent = {}, defaultdict(set)
    for (a, b), cost in edges.items():
        if a == b or a not in index or b not in index:
            raise ValueError('Invalid graph edge')
        a, b = sorted((index[a], index[b]))
        if (a, b) in costs:
            raise ValueError('Duplicate undirected edge')
        costs[a, b] = Fraction(cost)
        adjacent[a].add(b); adjacent[b].add(a)
    unseen = set(range(len(nodes))); components = []
    while unseen:
        seed = min(unseen); stack = [seed]; component = set()
        while stack:
            item = stack.pop()
            if item in component:
                continue
            component.add(item); unseen.discard(item)
            stack.extend(adjacent[item] - component)
        components.append(sorted(component))
    result_pairs, result_cost, visited = [], Fraction(), 0
    for component in components:
        local = {global_i: local_i for local_i, global_i in enumerate(component)}
        neighbor_masks = [sum(1 << local[j] for j in adjacent[i] if j in local) for i in component]
        @lru_cache(None)
        def solve(mask):
            nonlocal visited
            visited += 1
            if visited % 1024 == 0:
                check()
            if not mask:
                return (0, Fraction(), ())
            # Lowest available degree reduces sparse-graph state expansion.
            candidates = [i for i in range(len(component)) if mask & (1 << i)]
            i = min(candidates, key=lambda x: ((neighbor_masks[x] & mask).bit_count(), x))
            rest = mask ^ (1 << i)
            best = solve(rest)
            choices = neighbor_masks[i] & rest
            while choices:
                bit = choices & -choices; choices ^= bit; j = bit.bit_length()-1
                count, cost, pairs = solve(rest ^ bit)
                pair = tuple(sorted((component[i], component[j])))
                candidate = (count+1, cost+costs[pair], tuple(sorted(pairs+(pair,))))
                if (-candidate[0], candidate[1], candidate[2]) < (-best[0], best[1], best[2]):
                    best = candidate
            return best
        count, cost, pairs = solve((1 << len(component))-1)
        result_cost += cost; result_pairs.extend(pairs)
        solve.cache_clear()
    result_pairs.sort()
    return {'cardinality': len(result_pairs), 'cost': result_cost,
            'pairs': [(nodes[a], nodes[b]) for a, b in result_pairs], 'dp_states': visited}


def disjoint_strata_witness(strata_edges, blocks_per_stratum, check=lambda: None):
    """First lexicographic compatible witness; final cohort membership deferred."""
    names = sorted(strata_edges)
    witness = {}
    def choose_stratum(position, used):
        check()
        if position == len(names):
            return dict(witness)
        name = names[position]
        edges = list(strata_edges[name])
        def choose_edges(start, chosen, occupied):
            check()
            if len(chosen) == blocks_per_stratum:
                witness[name] = list(chosen)
                result = choose_stratum(position+1, used | occupied)
                if result is not None:
                    return result
                witness.pop(name, None)
                return None
            for i in range(start, len(edges)):
                edge = edges[i]
                if set(edge) & (used | occupied):
                    continue
                result = choose_edges(i+1, chosen+[edge], occupied | set(edge))
                if result is not None:
                    return result
            return None
        return choose_edges(0, [], set())
    return choose_stratum(0, set())


def run(plan_path, flags_path, registration_path, out, private_out):
    start = time.monotonic(); started_utc = datetime.now(timezone.utc).isoformat()
    plan = json.loads(plan_path.read_bytes()); registration = json.loads(registration_path.read_bytes())
    if registration['plan_sha256'] != sha(plan_path) or registration['implementation_sha256'] != sha(__file__) or \
       registration['exposure_flags_sha256'] != sha(flags_path) or registration['cost_rule'] != COST_RULE or \
       registration['band_rule'] != BAND_RULE or registration['tie_rule'] != TIE_RULE:
        raise ValueError('Pre-run registration does not bind implementation and rules')
    for test in registration['test_files']:
        if sha(plan_path.parent.parent/test['path']) != test['sha256']:
            raise ValueError('Registered test file changed')
    if plan['exposure_flags_sha256'] != sha(flags_path):
        raise ValueError('Exposure flags changed')
    resource.setrlimit(resource.RLIMIT_AS, (plan['address_space_bytes'], plan['address_space_bytes']))
    def check():
        if time.monotonic()-start > plan['census_wall_seconds']:
            raise TimeoutError('Registered metadata search wall budget exhausted')
    out.mkdir(parents=True, exist_ok=False); private_out.mkdir(parents=True, mode=0o700, exist_ok=False)
    flags = json.loads(flags_path.read_bytes())
    flag_rows = flags['accounts']
    flag_keys = [r['account_key'] for r in flag_rows]
    if len(set(flag_keys)) != len(flag_keys) or any(not isinstance(a, str) or not a or a != a.casefold() for a in flag_keys) or \
       any(type(r[k]) is not bool for r in flag_rows for k in ('pilot1_or_pilot2_or_private_mandatory_exclusion',
                                                             'pilot3_selected_scored_exposure', 'prior_capacity_only_exposure')):
        raise ValueError('Exposure identities and Boolean flags must be canonical')
    mandatory = {r['account_key'] for r in flag_rows if r['pilot1_or_pilot2_or_private_mandatory_exclusion']}
    scored3 = {r['account_key'] for r in flag_rows if r['pilot3_selected_scored_exposure']}
    if len(mandatory) != 57 or len(scored3) != 60 or mandatory & scored3:
        raise ValueError('Separate disjoint57 mandatory and60 scored exclusions required')
    excluded = mandatory | scored3
    capacity_only = {r['account_key'] for r in flags['accounts'] if r['prior_capacity_only_exposure']}
    if len(excluded) != 117:
        raise ValueError('Fixed117 exclusions required')
    timeline = defaultdict(list); ids = set(); counts = Counter(); allcuts = []; best = {}; inputs = []
    requested_communities = set(c for pair in plan['community_pairs'] for c in pair)
    try:
        declared_bytes = sum(source['bytes'] for source in plan['source_metadata'])
        if declared_bytes > plan['metadata_bytes_cap']:
            raise ValueError('Metadata byte cap exceeded')
        for source in plan['source_metadata']:
            path = Path(source['path']); digest = hashlib.sha256(); read_bytes = 0
            if path.stat().st_size != source['bytes']:
                raise ValueError('Metadata file size changed')
            with path.open('rb') as handle:
                for line in handle:
                    digest.update(line); read_bytes += len(line); counts['metadata_rows'] += 1
                    if counts['metadata_rows'] > plan['metadata_record_cap']:
                        raise ValueError('Metadata row cap exceeded')
                    if counts['metadata_rows'] % 2048 == 0:
                        check()
                    row = json.loads(line)
                    if row['record_id'] in ids:
                        raise ValueError('Duplicate original record ID')
                    ids.add(row['record_id'])
                    account = row['account_key'].casefold()
                    if account in excluded:
                        counts['excluded_rows'] += 1; continue
                    if row['reason'] is not None:
                        counts['prior_ineligible_rows'] += 1; continue
                    if row['community'] not in requested_communities:
                        counts['outside_registered_communities'] += 1; continue
                    if type(row['retained_words']) is not int or not plan['record_word_min'] <= row['retained_words'] <= plan['record_word_max']:
                        counts['outside_registered_record_word_bounds'] += 1; continue
                    row['timestamp'] = seconds(row['created_utc'])
                    timeline[account, row['community']].append(row)
                    counts['eligible_registered_metadata_rows'] += 1
                    counts['eligible_registered_words'] += row['retained_words']
            if read_bytes != source['bytes'] or digest.hexdigest() != source['sha256']:
                raise ValueError('Metadata hash changed; capacity must not be evaluated')
            inputs.append({'source_index': len(inputs)+1, 'bytes': read_bytes, 'sha256': digest.hexdigest()})
        del ids
        for rows in timeline.values():
            rows.sort(key=lambda r: (r['timestamp'], r['record_id']))
        accounts = sorted({a for a, c in timeline}, key=identity_order)
        for pair_index, (x, y) in enumerate(plan['community_pairs'], 1):
            sid = f'stratum-{pair_index:02d}'
            pair_accounts = [a for a in accounts if (a, x) in timeline and (a, y) in timeline]
            # Whole-history necessary condition only avoids futile repeated scans.
            pair_accounts = [a for a in pair_accounts if all(len(timeline[a, c]) >= 2*plan['half_min_records'] and sum(r['retained_words'] for r in timeline[a, c]) >= 2*plan['half_target_words'] for c in (x, y))]
            for cut_text in plan['cuts']:
                check(); cut = seconds(cut_text); prepared = {}; four_volume = 0
                for account in pair_accounts:
                    cells = {}
                    for letter, community in [('X', x), ('Y', y)]:
                        for period in ('early', 'late'):
                            cell = select_prefix(timeline[account, community], cut, period, plan)
                            if cell is not None:
                                cells[letter+'/'+period] = cell
                    if len(cells) != 4:
                        continue
                    four_volume += 1
                    if compatible(cells, cells, plan):
                        prepared[account] = cells
                nodes = sorted(prepared, key=identity_order)
                edges = {(a, b): edge_cost(prepared[a], prepared[b], plan) for i, a in enumerate(nodes) for b in nodes[i+1:] if compatible(prepared[a], prepared[b], plan)}
                match = exact_matching(nodes, edges, check)
                row = {'stratum_id': sid, 'communities': [x, y], 'cut': cut_text,
                       'whole_history_necessary_accounts': len(pair_accounts), 'accounts_with_four_volume_cells': four_volume,
                       'accounts_passing_internal_gates': len(nodes), 'compatible_edges': len(edges),
                       'maximum_disjoint_blocks': match['cardinality'], 'minimum_exact_matching_cost': match['cost'],
                       'matching_dp_states': match['dp_states'], 'intended_block_deficit': max(0, plan['intended_maximum_blocks_per_stratum']-match['cardinality'])}
                allcuts.append(row)
                key = (-match['cardinality'], match['cost'], cut_text)
                if sid not in best or key < best[sid]['key']:
                    best[sid] = {'key': key, 'public': row, 'cells': prepared, 'edges': edges, 'matching': match,
                                 'capacity_only_accounts': [a for a in nodes if a in capacity_only]}
            print(json.dumps({'completed_stratum': sid, 'cuts': len(plan['cuts']), 'best_blocks': best[sid]['matching']['cardinality']}), flush=True)
        global_witness = disjoint_strata_witness({sid: list(v['edges']) for sid, v in best.items()}, plan['intended_maximum_blocks_per_stratum'], check)
        private_result = {'role': 'Feasibility candidates and witness only; no cohort selected or contamination audit performed.',
                          'registration_sha256': sha(registration_path), 'strata': {sid: {'public': v['public'], 'candidate_cells': v['cells'],
                          'capacity_only_accounts': v['capacity_only_accounts'], 'maximum_matching': v['matching']} for sid, v in best.items()},
                          'globally_disjoint_intended_block_witness': global_witness}
        write(private_out/'candidates-and-witness.json', private_result, private=True)
        summary = {'status': 'feasible_before_contamination_audit' if global_witness is not None else 'fixed_design_capacity_deficit',
                   'version': 'pilot4-score-free-metadata-feasibility-v1', 'plan_sha256': sha(plan_path),
                   'registration_sha256': sha(registration_path), 'implementation_sha256': sha(__file__), 'exposure_flags_sha256': sha(flags_path),
                   'started_utc': started_utc, 'finished_utc': datetime.now(timezone.utc).isoformat(),
                   'wall_seconds': time.monotonic()-start, 'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                   'input_files': inputs, 'counts': dict(counts), 'evaluated_pair_cuts': len(allcuts),
                   'selected_calendar_witnesses': [v['public'] for v in best.values()],
                   'globally_disjoint_intended_blocks_exist': global_witness is not None,
                   'intended_blocks_per_stratum': plan['intended_maximum_blocks_per_stratum'],
                   'capacity_only_exposed_candidate_counts_at_chosen_cuts': {sid: len(v['capacity_only_accounts']) for sid, v in best.items()},
                   'new_download_bytes': 0, 'new_preprocessing_calls': 0, 'new_style_distance_calls': 0,
                   'source_prose_fields_accessed': False, 'cohort_selected': False,
                   'interpretation': 'All 101 cuts per stratum are preserved; exact uncapped maximum matching determines each calendar choice. When a two-block witness exists, it is globally disjoint across selected strata. A deficit is under this fixed prefix/grid/gate design, not proof that all possible designs are infeasible.'}
        write(out/'all-calendar-cuts.json', allcuts)
        with (out/'all-calendar-cuts.csv').open('x', newline='') as handle:
            fields = ['stratum_id', 'communities', 'cut', 'whole_history_necessary_accounts',
                      'accounts_with_four_volume_cells', 'accounts_passing_internal_gates',
                      'compatible_edges', 'maximum_disjoint_blocks', 'cost_numerator',
                      'cost_denominator', 'matching_dp_states', 'intended_block_deficit']
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in allcuts:
                item = {k: v for k, v in row.items() if k != 'minimum_exact_matching_cost'}
                item['communities'] = ' / '.join(row['communities'])
                item['cost_numerator'] = row['minimum_exact_matching_cost'].numerator
                item['cost_denominator'] = row['minimum_exact_matching_cost'].denominator
                writer.writerow(item)
        write(out/'feasibility-summary.json', summary)
        print(json.dumps({'status': summary['status'], 'pair_cuts': len(allcuts), 'wall_seconds': summary['wall_seconds']}), flush=True)
        return 0
    except Exception as error:
        write(out/'incomplete-search.json', {'status': 'incomplete_not_zero_capacity', 'error_type': type(error).__name__,
              'completed_cuts': allcuts, 'plan_sha256': sha(plan_path), 'implementation_sha256': sha(__file__),
              'wall_seconds': time.monotonic()-start, 'counts': dict(counts)})
        print(json.dumps({'status': 'incomplete_not_zero_capacity', 'error_type': type(error).__name__}), flush=True)
        return 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--exposure-flags', type=Path, required=True)
    parser.add_argument('--registration', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--private-out', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.plan, args.exposure_flags, args.registration, args.out, args.private_out))
