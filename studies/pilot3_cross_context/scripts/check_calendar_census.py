#!/usr/bin/env python3
"""Independent metadata-only UTC-cut and three-stratum verification.

Does not import calendar_capacity, expanded_capacity, study_math, AHAS, or any
source/text loader. It directly counts prefix/suffix records and words at EVERY
midnight using binary searches, rather than threshold-interval/event-sweep code.
Only sanitized aggregate verification is emitted; private identities stay local.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
from itertools import combinations, product
import json
from pathlib import Path
import resource
import time

MAX_ROWS = 1_000_000
MAX_SECONDS = 300
MAX_OUTPUT_BYTES = 100 * 1024**2
MAX_ADDRESS_SPACE = 4 * 1024**3


def fingerprint(path):
    path = Path(path)
    with path.open('rb') as handle:
        sha = hashlib.file_digest(handle, 'sha256').hexdigest()
    return {'sha256': sha, 'bytes': path.stat().st_size}


def read(path):
    return json.loads(Path(path).read_bytes())


def jsonlines(path):
    with Path(path).open() as handle:
        for line in handle:
            yield json.loads(line)


def instant(value):
    if not isinstance(value, str) or not value.endswith('Z'):
        raise ValueError('Explicit original UTC timestamp required')
    value = datetime.fromisoformat(value[:-1] + '+00:00')
    if value.utcoffset() != timedelta(0):
        raise ValueError('Timestamp is not UTC')
    return value


def direct_calendar_counts(rows, communities, start='2008-01-01', end='2018-11-01', excluded=frozenset()):
    """Enumerate full-span shared midnight cuts via direct prefix counts."""
    started = time.monotonic()
    first = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    final = datetime.fromisoformat(end).replace(tzinfo=timezone.utc)
    days = (final - first).days
    if days < 2 or days > 20000 or len(communities) > 8 or len(set(communities)) != len(communities):
        raise ValueError('Calendar/community bounds exceeded')
    cuts = [first + timedelta(days=offset) for offset in range(1, days)]
    groups = defaultdict(list)
    all_rows = eligible_rows = inside_rows = outside_rows = 0
    seen = set()
    for row in rows:
        all_rows += 1
        if all_rows > MAX_ROWS or time.monotonic() - started > MAX_SECONDS:
            raise ValueError('Independent metadata/time budget exhausted')
        identifier, account, community = row['record_id'], row['account_key'], row['community']
        if identifier in seen:
            raise ValueError('Repeated original record ID in metadata')
        seen.add(identifier)
        if account.casefold() in excluded or account != account.casefold():
            raise ValueError('Protected or noncanonical source account in metadata')
        if community not in communities:
            raise ValueError('Record community outside declared source frame')
        if row['reason'] is not None:
            continue
        words = row['retained_words']
        if type(words) is not int or words < 20:
            raise ValueError('Eligible metadata violates frozen word guard')
        eligible_rows += 1
        moment = instant(row['created_utc'])
        if first <= moment < final:
            inside_rows += 1
            groups[account, community].append((moment, words))
        else:
            outside_rows += 1
    possible = {}
    evaluated_cells = 0
    for (account, community), observations in groups.items():
        observations.sort()
        moments = [moment for moment, _ in observations]
        prefixes = [0]
        for _, words in observations:
            prefixes.append(prefixes[-1] + words)
        if len(moments) < 16 or prefixes[-1] < 4000:
            continue
        evaluated_cells += 1
        bitset = 0
        for index, cut in enumerate(cuts):
            count = bisect_left(moments, cut)
            before_words = prefixes[count]
            if count >= 8 and len(moments) - count >= 8 and before_words >= 2000 and prefixes[-1] - before_words >= 2000:
                bitset |= 1 << index
        if bitset:
            possible[account, community] = bitset
        if time.monotonic() - started > MAX_SECONDS:
            raise ValueError('Independent metadata/time budget exhausted')
    all_accounts = {account for account, _ in possible}
    result = {}
    for left, right in combinations(sorted(communities), 2):
        name = left + ' / ' + right
        by_account = {account: possible.get((account, left), 0) & possible.get((account, right), 0) for account in all_accounts}
        by_account = {account: bits for account, bits in by_account.items() if bits}
        counts = [0] * len(cuts)
        for bits in by_account.values():
            pending = bits
            while pending:
                bit = pending & -pending
                counts[bit.bit_length() - 1] += 1
                pending ^= bit
        chosen = min(range(len(cuts)), key=lambda index: (-counts[index], abs(2 * (index + 1) - days), index))
        maximum = counts[chosen]
        members = {account for account, bits in by_account.items() if bits & (1 << chosen)}
        cut_date = cuts[chosen].date().isoformat()
        ranges = []
        for index, count in enumerate(counts):
            if count == maximum:
                if ranges and index == ranges[-1][1] + 1:
                    ranges[-1][1] = index
                else:
                    ranges.append([index, index])
        positive = [index for index, count in enumerate(counts) if count]
        intervals = [{'account_key': account,
                      'first_cut': cuts[(bits & -bits).bit_length() - 1].date().isoformat(),
                      'last_cut': cuts[bits.bit_length() - 1].date().isoformat()}
                     for account, bits in sorted(by_account.items())]
        result[name] = {
            'maximum_accounts': maximum, 'accounts': members,
            'scheme': {'id': 'utc_midnight_' + cut_date, 'early': [start, cut_date], 'late': [cut_date, end]},
            'pairwise_blocks_upper_bound': maximum // 2,
            'accounts_with_any_feasible_cut': len(by_account),
            'all_internal_day_cuts_considered': len(cuts),
            'day_cuts_with_any_accounts': len(positive),
            'day_cuts_at_maximum': sum(count == maximum for count in counts),
            'available_cut_bounds': None if not positive else {'earliest': cuts[positive[0]].date().isoformat(), 'latest': cuts[positive[-1]].date().isoformat()},
            'maximizing_cut_ranges': [{'first': cuts[a].date().isoformat(), 'last': cuts[b].date().isoformat()} for a, b in ranges],
            'selected_calendar_imbalance_days': abs(2 * (chosen + 1) - days),
            'account_cut_intervals_private': intervals,
        }
    return {'metadata_rows': all_rows, 'eligible_rows': eligible_rows, 'inside_rows': inside_rows,
            'outside_rows': outside_rows, 'candidate_cell_series': evaluated_cells,
            'internal_midnight_cuts': len(cuts), 'pairs': result}


def exhaustive_three_strata(sets):
    """All triples and all even quota combinations, no optimized allocator imports.

    Hall's subset inequalities exactly decide whether distinct accounts can
    fill a proposed quota. An independently checked saved assignment additionally
    demonstrates attainment. No third-coordinate shortcut or search pruning.
    """
    if len(sets) < 3 or len(sets) > 28:
        raise ValueError('Exactly three strata must be chosen from three to 28 candidates')
    best = None
    full_targets = triples = quota_vectors = 0
    for names in combinations(sorted(sets), 3):
        triples += 1
        populations = [set(sets[name]) for name in names]
        capacities = [len(rows) for rows in populations]
        pair_limits = (len(populations[0] | populations[1]), len(populations[0] | populations[2]), len(populations[1] | populations[2]))
        total_limit = len(set.union(*populations))
        best_quotas = (0, 0, 0)
        for quotas in product(*(range(0, min(20, capacity) + 1, 2) for capacity in capacities)):
            quota_vectors += 1
            a, b, c = quotas
            if a + b <= pair_limits[0] and a + c <= pair_limits[1] and b + c <= pair_limits[2] and a + b + c <= total_limit:
                if (sum(quotas), sorted(quotas), quotas) > (sum(best_quotas), sorted(best_quotas), best_quotas):
                    best_quotas = quotas
        full_targets += best_quotas == (20, 20, 20)
        objective = (-sum(best_quotas), tuple(-q for q in sorted(best_quotas)), -min(capacities), -sum(capacities), names)
        if best is None or objective < best[0]:
            best = objective, names, best_quotas
    return {'selected_pairs': list(best[1]), 'quota_counts': dict(zip(best[1], best[2])),
            'total_accounts': sum(best[2]), 'total_blocks': sum(best[2]) // 2,
            'full_target_feasible_triple_count': full_targets,
            'candidate_triples_checked': triples, 'quota_vectors_checked': quota_vectors,
            'feasible_target': best[2] == (20, 20, 20)}


def verify(plan_path, amendment_path, source_census, calendar, private_root, receipt_path):
    started = time.monotonic()
    plan_path, amendment_path, source_census, calendar, private_root, receipt_path = map(Path, (plan_path, amendment_path, source_census, calendar, private_root, receipt_path))
    plan, amendment = read(plan_path), amendment_path.read_bytes()
    binding, summary = read(calendar / 'start-binding.json'), read(calendar / 'capacity.json')
    resources = read(calendar / 'resources.json')
    private = private_root / calendar.name
    metadata = private_root / source_census.name / 'record-eligibility.jsonl'
    exclusions = read(private_root / 'exclusions-mandatory.json')
    protected = {row['account_key'].casefold() for row in exclusions['accounts']}
    previous = {row['account_key'] for row in exclusions.get('prior_capacity_only_accounts', [])}
    failures, count = [], 0
    def check(condition, description):
        nonlocal count
        count += 1
        if not condition:
            failures.append(description)
    check(binding['plan_sha256'] == fingerprint(plan_path)['sha256'], 'Calendar run plan bytes bound')
    check(binding['amendment_sha256'] == hashlib.sha256(amendment).hexdigest(), 'Calendar amendment bytes bound')
    check(binding['eligibility_metadata_sha256'] == fingerprint(metadata)['sha256'] == read(source_census / 'private-artifact-hashes.json')['record-eligibility.jsonl']['sha256'], 'Private metadata matches both original census and calendar binding')
    check(binding['source_inventory_sha256'] == fingerprint(source_census / 'source-inventory.json')['sha256'], 'Source inventory binding unchanged')
    check(exclusions.get('complete_for_known_pilot_sources') is True, 'Mandatory exclusion inventory complete')
    source_binding = read(source_census / 'start-binding.json')
    check(source_binding['exclusions_sha256'] == fingerprint(private_root / 'exclusions-mandatory.json')['sha256'], 'Mandatory exclusions match source census')
    for name, expected in binding['scripts'].items():
        check(fingerprint(Path(__file__).with_name(name))['sha256'] == expected, 'Original calendar execution script identity: ' + name)
    private_hashes = read(calendar / 'private-artifact-hashes.json')
    for name in ('calendar-capacities.json', 'capacity-witness.json'):
        check(fingerprint(private / name) == private_hashes[name], 'Private witness bytes bound: ' + name)
    computed = direct_calendar_counts(jsonlines(metadata), [source['community'] for source in plan['sources']], excluded=protected)
    witness = read(private / 'calendar-capacities.json')
    check(computed['metadata_rows'] == summary['metadata_rows_read'] == resources['metadata_rows'], 'All metadata rows independently counted')
    check(computed['eligible_rows'] == summary['eligible_metadata_rows'] == witness['input_eligible_metadata_rows'], 'Eligible metadata independently counted')
    check(computed['inside_rows'] == witness['rows_inside_calendar_bounds'] and computed['outside_rows'] == witness['rows_outside_calendar_bounds'], 'Calendar inclusion independently counted')
    check(witness['words_per_cell'] == 2000 and witness['eligible_records_per_cell'] == 8, 'Four-cell guards unchanged')
    check(set(computed['pairs']) == set(summary['pair_capacities']) == set(witness['pairs']), 'Every declared community pair retained')
    pair_table = {}
    for name, result in computed['pairs'].items():
        saved = witness['pairs'][name]
        for field, value in result.items():
            actual = set(saved[field]) if field == 'accounts' else saved[field]
            check(actual == value, 'Direct every-midnight recount matches ' + field + ': ' + name)
        public = summary['pair_capacities'][name]
        check(public['maximum_four_cell_accounts'] == result['maximum_accounts'] and public['chosen_calendar_scheme'] == result['scheme'], 'Public best capacity and dates independently recomputed: ' + name)
        check(public['prior_capacity_inspected_accounts'] == len(result['accounts'] & previous), 'Prior capacity-inspection dependency independently counted: ' + name)
        pair_table[name] = {'maximum_four_cell_accounts': result['maximum_accounts'], 'chosen_calendar_scheme': result['scheme']}
    optimum = exhaustive_three_strata({name: row['accounts'] for name, row in computed['pairs'].items()})
    selection = read(private / 'capacity-witness.json')
    allocation = selection['capacity']
    check(optimum['selected_pairs'] == summary['selected_pair_strata'] == selection['selected_pairs'], 'Exact three-stratum selection and ties recomputed')
    for field in ('quota_counts', 'total_accounts', 'total_blocks'):
        check(optimum[field] == summary['disjoint_capacity'][field] == allocation[field], 'Exhaustive even-quota optimum matches: ' + field)
    check(optimum['full_target_feasible_triple_count'] == summary['full_target_feasible_triple_count'] == selection['full_target_feasible_triple_count'], 'All full-target feasible triples independently counted')
    check(optimum['candidate_triples_checked'] == selection['candidate_triple_count'], 'Every candidate triple independently enumerated')
    check(optimum['feasible_target'] == selection['feasible_target'], 'Full target feasibility independently decided')
    assigned = []
    check(set(allocation['assigned']) == set(optimum['selected_pairs']), 'Assignment includes exactly selected strata')
    for name, identities in allocation['assigned'].items():
        check(len(identities) == len(set(identities)) == optimum['quota_counts'][name], 'Assigned stratum identities unique and meet quota: ' + name)
        check(set(identities) <= computed['pairs'][name]['accounts'], 'Every assigned account has four feasible cells: ' + name)
        assigned.extend(identities)
    check(len(assigned) == len(set(assigned)) == optimum['total_accounts'], 'Witness attains optimum with globally disjoint accounts')
    check(summary['disjoint_capacity'] == {key: value for key, value in allocation.items() if key != 'assigned'}, 'Public allocation equals private witness summary')
    receipt = read(receipt_path)
    prefix = str(receipt_path).removesuffix('.receipt.json')
    check(receipt['exit_code'] == 0, 'Original calendar command succeeded')
    for suffix in ('stdout.log', 'stderr.log'):
        check(fingerprint(prefix + '.' + suffix) == receipt['outputs'][suffix], 'Original receipt log hashes match: ' + suffix)
    check(read(prefix + '.stdout.log') == summary, 'Original fresh stdout agrees with saved public summary')
    check(summary['source_prose_reads'] == summary['preprocessing_calls'] == summary['style_scores_computed'] == 0 and not summary['final_cohort_selected'], 'Refinement remains metadata-only and unscored')
    check(resources['private_output_bytes'] <= MAX_OUTPUT_BYTES and resources['wall_seconds'] <= MAX_SECONDS, 'Original calendar resource ceilings respected')
    elapsed = time.monotonic() - started
    check(elapsed <= MAX_SECONDS, 'Independent checker within five-minute limit')
    return {'status': 'pass' if not failures else 'fail', 'checks_performed': count, 'failed_checks': failures,
            'metadata_rows': computed['metadata_rows'], 'eligible_rows': computed['eligible_rows'],
            'calendar_cuts_per_pair': computed['internal_midnight_cuts'], 'pair_capacity_table': pair_table,
            'independent_three_stratum_optimum': optimum,
            'original_prose_reads': 0, 'preprocessing_calls': 0, 'style_scores_computed': 0,
            'identifiers_exported': False, 'wall_seconds': elapsed,
            'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            'checker_sha256': fingerprint(__file__)['sha256'],
            'input_hashes': {path.name: fingerprint(path) for path in (plan_path, amendment_path, metadata, receipt_path)},
            'limitations': ['Direct enumeration verifies the full-span shared-midnight family only.',
                            'The three-stratum optimum uses each pair\'s individually chosen maximum-capacity cut; it does not optimize all combinations of nonmaximal cuts.',
                            'Metadata retained-word counts come from the frozen census; the separate 100-record raw-source check verifies a sample.',
                            'Feasible capacities precede contamination filtering and are not a final cohort or evidence of account discrimination.']}


def main():
    parser = argparse.ArgumentParser()
    for name in ('plan', 'amendment', 'source-census', 'calendar', 'private-root', 'receipt', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (MAX_ADDRESS_SPACE,) * 2)
    binding = args.out.with_suffix('.start-binding.json')
    with binding.open('x') as handle:
        json.dump({'phase': 'before_independent_calendar_check', 'utc': datetime.now(timezone.utc).isoformat(),
                   'checker_sha256': fingerprint(__file__)['sha256'], 'original_prose_reads': 0,
                   'preprocessing_calls': 0, 'style_scores_computed': 0}, handle, indent=2)
        handle.write('\n')
    report = verify(args.plan, args.amendment, args.source_census, args.calendar, args.private_root, args.receipt)
    raw = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode()
    if len(raw) > MAX_OUTPUT_BYTES:
        raise ValueError('Independent output budget exceeded')
    with args.out.open('xb') as handle:
        handle.write(raw)
    print(json.dumps({'status': report['status'], 'failed_checks': report['failed_checks'],
                      'total_accounts': report['independent_three_stratum_optimum']['total_accounts'],
                      'total_blocks': report['independent_three_stratum_optimum']['total_blocks'],
                      'output': fingerprint(args.out)}))
    raise SystemExit(0 if report['status'] == 'pass' else 1)


if __name__ == '__main__':
    main()
