"""Independent metadata-only reconstruction of the registered Pilot6 search.

No source prose, preprocessing, grids, styles or analyzer outcomes are read.
Prefix, window, cost, exclusion and enumeration arithmetic below is independent
of the selector. Only the previously verified exact matching backend is shared.
Public receipts contain aggregate counts and hashes, never account/record IDs.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from fractions import Fraction
import hashlib
from itertools import combinations, groupby
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

PAIRS = [['AskAcademia', 'GradSchool'], ['AskPhysics', 'Physics'], ['math', 'learnmath'],
         ['linux', 'linuxquestions'], ['programming', 'learnprogramming']]
CUTS = [f'{y}-{m:02d}-01T00:00:00Z' for y in range(2010, 2019) for m in range(1, 13)
        if (y, m) <= (2018, 5)]
DESIGN = {'half_band_days': 180, 'half_target_words': 5000, 'half_min_records': 40,
          'half_max_words': 5500, 'half_max_records': 200, 'record_word_min': 20, 'record_word_max': 500}
BOUNDS = {'wall_seconds': 1800, 'address_space_bytes': 4 * 1024**3,
          'metadata_rows': 3000000, 'metadata_bytes': 1024**3,
          'directional_evaluations': 2000000, 'private_output_bytes': 256 * 1024**2}


def require(value, label):
    if not value:
        raise ValueError(label)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def rational(value):
    if isinstance(value, Fraction):
        return {'numerator': value.numerator, 'denominator': value.denominator}
    if isinstance(value, dict):
        return {k: rational(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [rational(v) for v in value]
    return value


def timestamp(text):
    date = datetime.fromisoformat(text.replace('Z', '+00:00'))
    require(date.utcoffset() is not None, 'Naive metadata timestamp')
    return int(date.timestamp())


def account_order(account):
    return hashlib.sha256(b'pilot6-anchor-order-v1\0' + account.casefold().encode()).hexdigest()


def direction_order(row):
    return (row['stratum_id'], row['cut'], account_order(row['account_a']),
            account_order(row['account_b']), row['community_x'], row['community_y'])


def edge(row):
    return tuple(sorted((row['account_a'], row['account_b']), key=account_order))


def prefix(rows, cut, early):
    """Rows are (timestamp, original ID, words); return a whole-record prefix."""
    low, high = (cut - 180 * 86400, cut) if early else (cut, cut + 180 * 86400)
    ordered = sorted((r for r in rows if low <= r[0] < high and 20 <= r[2] <= 500),
                     key=lambda r: (abs(r[0] - cut), r[0], r[1]))
    chosen, words = [], 0
    for row in ordered:
        chosen.append(row)
        words += row[2]
        if words > 5500 or len(chosen) > 200:
            return None
        if words >= 5000 and len(chosen) >= 40:
            chosen.sort()
            n = len(chosen)
            median = Fraction(chosen[(n - 1) // 2][0] + chosen[n // 2][0], 2)
            return {'rows': chosen, 'records': n, 'words': words, 'median': median}
    return None


def qualified_windows(rows):
    """Count closed primary windows; the residual never qualifies by itself."""
    words = count = windows = 0
    for row in rows:
        words += row[2]
        count += 1
        if words >= 1000 and count >= 8:
            windows += 1
            words = count = 0
    return windows


def metrics(cells):
    anchor, *late = cells
    words = [c['words'] for c in cells]
    counts = [c['records'] for c in cells]
    dates = [c['median'] for c in late]
    wr, cr = Fraction(max(words), min(words)), Fraction(max(counts), min(counts))
    span = max(dates) - min(dates)
    windows = [qualified_windows(anchor['rows'] + c['rows']) for c in late]
    reasons = []
    for failed, reason in ((wr > Fraction(11, 10), 'five_sample_word_ratio_above_11_over_10'),
                           (cr > Fraction(5, 4), 'five_sample_record_ratio_above_5_over_4'),
                           (span > 30 * 86400, 'four_late_median_span_above_30_days'),
                           (min(windows) < 8, 'fewer_than_eight_qualified_windows')):
        if failed:
            reasons.append(reason)
    cost = sum((abs(a - b) / (180 * 86400) for a, b in combinations(dates, 2)), Fraction())
    cost += sum((Fraction(abs(words[i] - words[j]), 5000) + Fraction(abs(counts[i] - counts[j]), 40)
                 for i, j in combinations(range(5), 2)), Fraction())
    return {'valid': not reasons, 'reason_codes': reasons, 'cost': cost,
            'qualified_window_counts': windows, 'late_median_span_days': span / 86400,
            'five_sample_word_ratio': wr, 'five_sample_record_ratio': cr}


def exclusions(flags, pilot5):
    names = set()
    old, scored, capacity = set(), set(), set()
    fields = ('pilot1_or_pilot2_or_private_mandatory_exclusion',
              'pilot3_selected_scored_exposure', 'prior_capacity_only_exposure')
    for row in flags['accounts']:
        name = row['account_key']
        require(isinstance(name, str) and name and name == name.casefold() and name not in names,
                'Invalid exposure identities')
        require(all(type(row[f]) is bool for f in fields), 'Non-Boolean exposure flag')
        names.add(name)
        for target, flag in zip((old, scored, capacity), fields):
            if row[flag]:
                target.add(name)
    five = {pilot5['selected'][k] for k in ('account_a', 'account_b')}
    require(all(isinstance(a, str) and a and a == a.casefold() for a in five), 'Invalid Pilot5 identities')
    require((len(old), len(scored), len(five), len(old | scored | five)) == (57, 60, 2, 119),
            'Incorrect protected account union')
    return old | scored | five, capacity


def checked_sources(plan, excluded, check):
    timelines, counts, seen, verified = defaultdict(list), Counter(), set(), []
    communities = {c for pair in PAIRS for c in pair}
    sources = plan['source_metadata']
    require(len({str(Path(s['path']).resolve()) for s in sources}) == len(sources), 'Duplicate source paths')
    for source in sources:
        require(type(source['bytes']) is int and source['bytes'] >= 0, 'Invalid source byte count')
        digest, size, rows = hashlib.sha256(), 0, 0
        with Path(source['path']).open('rb') as stream:
            for line in stream:
                rows += 1
                size += len(line)
                digest.update(line)
                counts['metadata_rows'] += 1
                counts['metadata_bytes'] += len(line)
                require(counts['metadata_rows'] <= BOUNDS['metadata_rows'] and counts['metadata_bytes'] <= BOUNDS['metadata_bytes'],
                        'Metadata check resource ceiling')
                if rows % 10000 == 0:
                    check()
                row = json.loads(line)
                rid, account, words = row['record_id'], row['account_key'], row['retained_words']
                require(isinstance(rid, str) and rid and rid not in seen, 'Invalid or repeated original ID')
                seen.add(rid)
                require(isinstance(account, str) and account and account == account.casefold(), 'Invalid metadata identity')
                require((words is None and row['reason'] is not None) or (type(words) is int and words >= 0),
                        'Invalid retained-word integer or unqualified null')
                if account in excluded:
                    counts['excluded_rows'] += 1
                elif row['community'] not in communities:
                    counts['outside_registered_communities'] += 1
                elif row['reason'] is not None or not 20 <= words <= 500:
                    counts['ineligible_rows'] += 1
                else:
                    timelines[account, row['community']].append((timestamp(row['created_utc']), rid, words))
                    counts['eligible_rows'] += 1
        require(size == source['bytes'] and digest.hexdigest() == source['sha256'], 'Source metadata hash or bytes changed')
        verified.append({'source_index': len(verified) + 1, 'bytes': size, 'rows': rows, 'sha256': digest.hexdigest()})
    for rows in timelines.values():
        rows.sort()
    return timelines, counts, verified


def registered_matcher(config, check):
    # Backend proof and all dependency bytes are verified by this frozen helper.
    folder = Path(__file__).resolve().parents[2] / 'pilot4_chronological_controls/scripts'
    sys.path.insert(0, str(folder))
    from metadata_feasibility_v2 import verify_matching_backend
    return verify_matching_backend(config, check)


def saved_directions(path):
    require(Path(path).stat().st_size <= BOUNDS['private_output_bytes'], 'Directional file byte ceiling')
    with Path(path).open('rb') as stream:
        for number, line in enumerate(stream, 1):
            require(number <= BOUNDS['directional_evaluations'], 'Directional file row ceiling')
            yield json.loads(line)


def verify(plan_path, public, private, *, matching_factory=registered_matcher, check=lambda: None):
    """Reconstruct every cut and direction; return an aggregate-only receipt."""
    started = time.monotonic()
    plan_path, public, private = Path(plan_path), Path(public), Path(private)
    plan = read(plan_path)
    require(plan['phase'] == 'frozen_before_replication_metadata', 'Incorrect metadata phase')
    require(plan['community_pairs'] == PAIRS and plan['cuts'] == CUTS and plan['design'] == DESIGN and plan['limits'] == BOUNDS,
            'Registered metadata rules changed')
    bindings = {str(Path(r['path']).resolve()): r['sha256'] for r in plan['bindings']}
    require(len(bindings) == len(plan['bindings']), 'Duplicate plan binding')
    for path, digest in bindings.items():
        require(sha(path) == digest, 'Changed bound metadata input')
    selector = Path(__file__).with_name('metadata_replication.py')
    required = [selector, plan['protocol'], plan['exposure_flags'], plan['pilot5_selection']]
    required += [s['path'] for s in plan['source_metadata']]
    require(all(str(Path(p).resolve()) in bindings for p in required), 'Missing metadata input binding')
    require(plan['script_sha256'] == bindings[str(selector.resolve())], 'Selector code binding changed')
    require(all(s['sha256'] == bindings[str(Path(s['path']).resolve())] for s in plan['source_metadata']), 'Declared source binding changed')
    excluded, capacity = exclusions(read(plan['exposure_flags']), read(plan['pilot5_selection']))
    matcher = matching_factory(plan['matching_backend'], check)
    files = [public / n for n in ('start-binding.json', 'all-calendar-cuts.json', 'feasibility-summary.json')]
    files += [private / n for n in ('directional-evaluations.jsonl', 'best-edge-directions.json', 'provisional-pairs.json')]
    require(sum(p.stat().st_size for p in files[3:]) <= BOUNDS['private_output_bytes'], 'Private metadata output ceiling')
    before = {p.name: sha(p) for p in files}
    start = read(files[0])
    require(start['phase'] == plan['phase'] and start['plan_sha256'] == sha(plan_path) and
            start['script_sha256'] == plan['script_sha256'] and start['style_calls'] == 0 and
            start['grid_localization_evaluated'] is False, 'Incorrect original start binding')
    timelines, counts, sources = checked_sources(plan, excluded, check)
    cuts, best, reason_counts = [], {}, Counter()
    groups = iter(groupby(saved_directions(files[3]), key=lambda r: (r['stratum_id'], r['cut'])))
    pending = next(groups, None)
    for index, (x, y) in enumerate(PAIRS, 1):
        sid = f'stratum-{index:02d}'
        accounts = sorted({a for a, c in timelines if c in (x, y)})
        possible = [a for a in accounts if all(len(timelines.get((a, c), [])) >= 40 and
                    sum(r[2] for r in timelines.get((a, c), [])) >= 5000 for c in (x, y))]
        for cut_text in CUTS:
            check()
            cut = timestamp(cut_text)
            cells = {(a, c, early): prefix(timelines.get((a, c), []), cut, early)
                     for a in possible for c in (x, y) for early in (True, False)}
            failures = Counter(c + ('/early' if early else '/late') for (a, c, early), cell in cells.items() if cell is None)
            late_ok = [a for a in possible if all(cells[a, c, False] for c in (x, y))]
            stats = Counter(all_possible_ordered_directions=2 * len(possible) * (len(possible) - 1),
                            directions_without_two_late_accounts=2 * (len(possible) * (len(possible) - 1) - len(late_ok) * (len(late_ok) - 1)),
                            directions_without_anchor=0, evaluated_directions=0, valid_directions=0, invalid_evaluated_directions=0)
            actual = {}
            if pending is not None and pending[0] == (sid, cut_text):
                for row in pending[1]:
                    key = (row['account_a'], row['account_b'], row['community_x'], row['community_y'])
                    require(key not in actual, 'Duplicate saved direction')
                    actual[key] = row
                pending = next(groups, None)
            # Unordered combinations then the four orientations differ from the
            # selector's nested account traversal; comparison ignores row order.
            for first, second in combinations(late_ok, 2):
                for a, b, cx, cy in ((first, second, x, y), (first, second, y, x),
                                     (second, first, x, y), (second, first, y, x)):
                    if cells[a, cx, True] is None:
                        stats['directions_without_anchor'] += 1
                        continue
                    samples = [cells[a, cx, True], cells[a, cx, False], cells[b, cx, False],
                               cells[a, cy, False], cells[b, cy, False]]
                    result = metrics(samples)
                    expected = dict(stratum_id=sid, cut=cut_text, account_a=a, account_b=b,
                                    community_x=cx, community_y=cy, **result)
                    observed = actual.pop((a, b, cx, cy), None)
                    require(observed == rational(expected), 'Saved directional arithmetic or membership mismatch')
                    stats['evaluated_directions'] += 1
                    counts['directional_evaluations'] += 1
                    require(counts['directional_evaluations'] <= BOUNDS['directional_evaluations'], 'Independent direction ceiling')
                    stats.update(result['reason_codes'])
                    reason_counts.update(result['reason_codes'])
                    stats['valid_directions' if result['valid'] else 'invalid_evaluated_directions'] += 1
                    if result['valid']:
                        key = edge(expected)
                        if key not in best or (result['cost'], direction_order(expected)) < (best[key]['cost'], direction_order(best[key])):
                            best[key] = expected
            require(not actual, 'Extra saved directions at a calendar cut')
            for field in ('all_possible_ordered_directions', 'directions_without_two_late_accounts', 'directions_without_anchor'):
                counts[field] += stats[field]
            cuts.append(dict(stratum_id=sid, communities=[x, y], cut=cut_text,
                             whole_history_necessary_accounts=len(possible), accounts_with_two_late_prefixes=len(late_ok),
                             unavailable_prefix_counts=dict(failures), **dict(stats)))
    require(pending is None, 'Extra or out-of-order saved calendar direction group')
    require(read(files[1]) == cuts, 'All-cut coverage or gate counts mismatch')
    saved_best = read(files[4])
    require(len(saved_best) == len(best) and len({edge(r) for r in saved_best}) == len(saved_best), 'Best-edge inventory mismatch')
    require({edge(r): r for r in saved_best} == {k: rational(v) for k, v in best.items()}, 'Best-edge exact cost or calendar tie mismatch')
    nodes = sorted({a for e in best for a in e}, key=account_order)
    matched = matcher(nodes, {e: r['cost'] for e, r in best.items()}, check)
    selected = sorted((best[tuple(p)] for p in matched['pairs']), key=lambda r: (r['cost'], direction_order(r)))[:20]
    pairs = [dict(r, pair_id=f'pilot6-pair-{i:02d}', prior_capacity_only_accounts=sum(a in capacity for a in edge(r)))
             for i, r in enumerate(selected, 1)]
    require(len({a for row in pairs for a in edge(row)}) == 2 * len(pairs), 'Global pair account reuse')
    saved_pool = read(files[5])
    require(saved_pool['plan_sha256'] == sha(plan_path) and saved_pool['unique_valid_edges'] == len(best), 'Provisional pool binding mismatch')
    require(saved_pool['pairs'] == rational(pairs), 'Whole-matching cost ordering or first-20 provisional selection mismatch')
    for field in ('cardinality', 'cost', 'pairs'):
        require(saved_pool['matching'][field] == rational(matched[field]), 'Global exact matching mismatch')
    summary = read(files[2])
    expected_summary = {'status': 'completed_score_free_metadata', 'plan_sha256': sha(plan_path), 'counts': dict(counts),
        'pair_cut_count': 505, 'verified_source_metadata': sources, 'global_maximum_matching_pairs': matched['cardinality'],
        'matching_exact_cost': rational(matched['cost']), 'provisional_pairs': len(pairs), 'target_new_pairs': 10,
        'pool_ceiling': 20, 'source_accounts_in_provisional_pool': 2 * len(pairs), 'unique_valid_unordered_edges': len(best),
        'provisional_pairs_sha256': before['provisional-pairs.json'], 'directional_enumeration_sha256': before['directional-evaluations.jsonl'],
        'style_calls': 0, 'grid_localization_evaluated': False, 'cohort_finalized': False,
        'provisional_pair_metadata': [{k: rational(v) for k, v in r.items() if k not in ('account_a', 'account_b')} for r in pairs]}
    require(all(summary.get(k) == v for k, v in expected_summary.items()), 'Public capacity summary mismatch')
    require(all(sha(p) == before[p.name] for p in files), 'Saved selection changed during verification')
    return {'status': 'passed', 'checker_sha256': sha(__file__), 'plan_sha256': sha(plan_path),
            'checked_artifact_hashes': before, 'source_metadata': sources, 'counts': dict(counts),
            'calendar_pair_cuts_verified': len(cuts), 'direction_reason_counts': dict(reason_counts),
            'unique_valid_edges_verified': len(best), 'global_maximum_matching_pairs': matched['cardinality'],
            'matching_exact_cost': rational(matched['cost']), 'provisional_pairs_verified': len(pairs),
            'protected_accounts_excluded': len(excluded), 'source_accounts_globally_disjoint': True,
            'matching_backend': 'Shared preverified exact blossom backend; all graph edges/costs/directions reconstructed independently.',
            'selection_rule': 'First 20 cost-ordered edges from the exact whole-graph matching; no separate capped optimization.',
            'original_source_prose_reads': 0, 'preprocessor_calls': 0, 'style_calls': 0, 'grid_localization_evaluated': False,
            'wall_seconds': time.monotonic() - started,
            'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024}


def main():
    p = argparse.ArgumentParser()
    for name in ('plan', 'public', 'private', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    args = p.parse_args()
    require(os.environ.get('AHAS_NETWORK_ISOLATION') == 'linux_seccomp_socket_denial', 'Offline wrapper required')
    require(not args.out.exists(), 'Refusing to overwrite a check receipt')
    resource.setrlimit(resource.RLIMIT_AS, (BOUNDS['address_space_bytes'],) * 2)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Independent metadata wall ceiling')))
    signal.alarm(BOUNDS['wall_seconds'])
    started = time.monotonic()
    def check():
        require(time.monotonic() - started < BOUNDS['wall_seconds'], 'Independent metadata wall ceiling')
    try:
        result = verify(args.plan, args.public, args.private, check=check)
    except Exception as exc:
        result = {'status': 'failed', 'error_type': type(exc).__name__, 'checker_sha256': sha(__file__),
                  'plan_sha256': sha(args.plan), 'style_calls': 0, 'preprocessor_calls': 0,
                  'wall_seconds': time.monotonic() - started}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('x') as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write('\n')
        raise
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('x') as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write('\n')
        print(json.dumps({k: result[k] for k in ('status', 'calendar_pair_cuts_verified', 'provisional_pairs_verified', 'wall_seconds')}))
    finally:
        signal.alarm(0)


if __name__ == '__main__':
    main()
