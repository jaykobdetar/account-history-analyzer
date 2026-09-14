#!/usr/bin/env python3
"""Independent, score-free census reconciliation from metadata and fresh receipts.

Does not import either census, allocation helper, AHAS, or any distance implementation.
Never opens corpus members or reads original prose. Optional source verification
hashes the compressed archive bytes only. Output contains aggregate counts only.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
from itertools import combinations, product
import json
from pathlib import Path
import re


def read(path):
    return json.loads(Path(path).read_bytes())


def fingerprint(path):
    with Path(path).open('rb') as handle:
        value = hashlib.file_digest(handle, 'sha256').hexdigest()
    return {'sha256': value, 'bytes': Path(path).stat().st_size}


def jsonlines(path):
    with Path(path).open() as handle:
        for line in handle:
            yield json.loads(line)


def instant(value):
    if not isinstance(value, str) or not value.endswith('Z'):
        raise ValueError('Timestamp is not explicit UTC')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo != timezone.utc:
        raise ValueError('Timestamp is not UTC')
    return parsed


def independent_strata_optimum(eligible_by_pair):
    """Independent exhaustive quota/Hall oracle over metadata-only memberships.

    All 0,2,...,20 quota vectors are considered, in objective order. Availability
    is represented by exact integer bitsets rather than the selection helper's
    capped unions or algebraic elimination of its third quota dimension.
    """
    names = sorted(eligible_by_pair)
    if len(names) > 28:
        raise ValueError('Expanded census oracle is bounded to 28 pair strata')
    members = sorted(set().union(*(set(eligible_by_pair[p]) for p in names)))
    positions = {account: index for index, account in enumerate(members)}
    bits = {pair: sum(1 << positions[a] for a in set(eligible_by_pair[pair])) for pair in names}
    raw = {pair: len(set(eligible_by_pair[pair])) for pair in names}
    triples = list(combinations(names, 3)) if len(names) >= 3 else [tuple(names)]
    best = None
    feasible_targets = 0
    ordered_quota_cache = {}
    for triple in triples:
        availability = []
        for mask in range(1, 1 << len(triple)):
            combined = 0
            for i, pair in enumerate(triple):
                if mask & (1 << i):
                    combined |= bits[pair]
            availability.append((mask, combined.bit_count()))
        caps = tuple(min(20, raw[pair]) for pair in triple)
        if caps not in ordered_quota_cache:
            vectors = product(*(range(0, cap + 1, 2) for cap in caps))
            ordered_quota_cache[caps] = sorted(vectors,
                key=lambda q: (sum(q), tuple(sorted(q)), q), reverse=True)
        for quota in ordered_quota_cache[caps]:
            if all(sum(q for i, q in enumerate(quota) if mask & (1 << i)) <= available
                   for mask, available in availability):
                break
        else:
            raise AssertionError('Zero quota must always be feasible')
        full = len(triple) == 3 and quota == (20, 20, 20)
        feasible_targets += int(full)
        raw_counts = [raw[p] for p in triple]
        key = (-sum(quota), tuple(-q for q in sorted(quota)),
               -min(raw_counts, default=0), -sum(raw_counts), triple)
        if best is None or key < best[0]:
            best = (key, triple, quota, full)
    return {'selected_pairs': list(best[1]), 'quota_counts': dict(zip(best[1], best[2])),
            'total_accounts': sum(best[2]), 'total_blocks': sum(best[2]) // 2,
            'feasible_target': best[3], 'full_target_feasible_triple_count': feasible_targets,
            'candidate_triples_checked': len(triples) if len(names) >= 3 else 0}


def check_capacity_choice(eligible, selected, public_allocation, private_allocation, check, label):
    """Verify optimal choice and an actual private assignment independently."""
    optimum = independent_strata_optimum(eligible)
    check(selected == optimum['selected_pairs'], label + ': chosen strata obey complete global objective and ties')
    check(len(selected) == min(3, len(eligible)) and len(set(selected)) == len(selected),
          label + ': three distinct candidate strata retained when available')
    check(all(pair in eligible for pair in selected), label + ': selected strata are declared candidates')
    check(public_allocation == {k: v for k, v in private_allocation.items() if k != 'assigned'},
          label + ': public capacity exactly matches private witness summary')
    quotas = private_allocation.get('quota_counts', {})
    check(set(quotas) == set(selected), label + ': quota keys exactly match selected strata')
    check(quotas == optimum['quota_counts'], label + ': account quotas achieve global optimum and registered quota ties')
    valid_quotas = all(type(q) is int and 0 <= q <= 20 and q % 2 == 0 for q in quotas.values())
    check(valid_quotas, label + ': quotas are even integers between zero and twenty')
    if valid_quotas:
        check(private_allocation.get('total_accounts') == sum(quotas.values()) == optimum['total_accounts'],
              label + ': total accounts reconcile and are optimal')
        check(private_allocation.get('total_blocks') == sum(quotas.values()) // 2 == optimum['total_blocks'],
              label + ': total complete blocks reconcile and are optimal')
    assigned = private_allocation.get('assigned', {})
    check(set(assigned) == set(selected), label + ': assignment keys exactly match selected strata')
    all_assigned = []
    for pair in selected:
        values = assigned.get(pair, [])
        check(isinstance(values, list) and len(values) == len(set(values)),
              label + ': assigned identities occur once per stratum')
        check(len(values) == quotas.get(pair), label + ': assigned account counts meet witness quotas')
        check(set(values) <= set(eligible.get(pair, set())), label + ': assigned identities belong to eligible cells')
        all_assigned.extend(values)
    check(len(all_assigned) == len(set(all_assigned)), label + ': all assigned accounts are disjoint across strata')
    return optimum


def reconcile(plan_path, census_root, private_root, receipt_path, source_root=None):
    plan_path, census_root, private_root = map(Path, (plan_path, census_root, private_root))
    receipt_path = Path(receipt_path)
    plan = read(plan_path)
    inventory = read(census_root / 'source-inventory.json')
    capacity = read(census_root / 'capacity.json')
    binding = read(census_root / 'start-binding.json')
    resources = read(census_root / 'resources.json')
    second_pass = read(census_root / 'second-pass-source-binding.json')
    manifest = read(census_root / 'private-artifact-hashes.json')
    exclusion_path = private_root / 'exclusions-mandatory.json'
    exclusion = read(exclusion_path)
    private_run = private_root / census_root.name
    errors = []
    checks_performed = 0

    def check(condition, description):
        nonlocal checks_performed
        checks_performed += 1
        if not condition:
            errors.append(description)

    check(plan['target']['words_per_cell'] == 2000 and plan['target']['eligible_records_per_cell'] == 8,
          'Experimental cell requirements remain 2000 words and 8 records')
    check(binding['plan_sha256'] == fingerprint(plan_path)['sha256'], 'Fresh run bound to supplied plan bytes')
    check(binding['exclusions_sha256'] == fingerprint(exclusion_path)['sha256'], 'Fresh run bound to exclusion bytes')
    check(binding['implementation_fingerprint'] == plan['implementation_fingerprint'] and
          binding['analysis_config_sha256'] == plan['analysis_config_sha256'], 'Frozen implementation and configuration bindings')
    check(binding['script_sha256'] == fingerprint(Path(__file__).with_name('census_expanded.py'))['sha256'], 'Fresh run bound to supplied expanded census script bytes')
    check(exclusion.get('complete_for_known_pilot_sources') is True, 'Known pilot exclusion manifest marked complete')
    excluded = {row['account_key'].casefold() for row in exclusion['accounts']}
    check(len(excluded) == inventory['exclusion_unique_account_count'], 'Excluded account count agrees with manifest')
    check(inventory['exclusion_manifest_reason_counts'] == exclusion.get('reason_counts'), 'Exclusion reason counts agree with manifest')

    expected_private = {'account-frame.jsonl', 'record-eligibility.jsonl', 'cell-capacities.json', 'capacity-witness.json'}
    check(set(manifest) == expected_private, 'All expected private artifacts have public digests')
    for name in expected_private:
        check(fingerprint(private_run / name) == manifest.get(name), 'Private artifact bytes agree: ' + name)

    frames = {}
    candidates = set()
    for row in jsonlines(private_run / 'account-frame.jsonl'):
        account = row['account_key']
        check(account not in frames, 'Account-frame keys are unique')
        check(account == account.casefold() and account not in excluded, 'Account-frame excludes protected source identities')
        frames[account] = row['communities']
        necessary = sum(c.get('present_timestamped_comments', 0) >= 16 for c in row['communities'].values()) >= 2
        check(necessary == row['preprocess'], 'Metadata prefilter is exactly the necessary two-community 16-record condition')
        if necessary:
            candidates.add(account)
    check(len(frames) == inventory['nonexcluded_comment_accounts'], 'Account-frame total matches source inventory')
    check(len(candidates) == inventory['preprocessing_candidate_accounts'], 'Candidate total independently reconciles')
    for left, right in plan['community_pairs']:
        name = left + ' / ' + right
        overlap = sum(left in rows and right in rows for rows in frames.values())
        enough = sum(rows.get(left, {}).get('present_timestamped_comments', 0) >= 16 and
                     rows.get(right, {}).get('present_timestamped_comments', 0) >= 16 for rows in frames.values())
        check(overlap == inventory['source_pair_any_comment_account_overlaps'][name], 'Raw pair overlap reconciles: ' + name)
        check(enough == inventory['source_pair_16_present_comment_account_overlaps'][name], 'Necessary metadata overlap reconciles: ' + name)

    intervals = {}
    for scheme in plan['period_schemes']:
        ranges = {part: tuple(datetime.fromisoformat(x).replace(tzinfo=timezone.utc) for x in scheme[part]) for part in ('early', 'late')}
        check(all(start < end for start, end in ranges.values()), 'Proposed period durations are positive')
        check(ranges['early'][1] <= ranges['late'][0], 'Proposed early and late periods do not overlap')
        intervals[scheme['id']] = ranges
    seen = set()
    observations, totals, cells = Counter(), defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    rejections = Counter()
    processed = eligible_count = eligible_words = 0
    source_processed, source_eligible = Counter(), Counter()
    source_hashes = set()
    for row in jsonlines(private_run / 'record-eligibility.jsonl'):
        account, community = row['account_key'], row['community']
        check(account in candidates and account not in excluded, 'No protected or rejected account reached record eligibility')
        check(row['record_id'] not in seen, 'Every candidate original record ID appears at most once')
        seen.add(row['record_id'])
        observations[account, community] += 1
        check(bool(re.fullmatch(r'[0-9a-f]{64}', row['source_line_sha256'])), 'Original source-line digests have SHA-256 form')
        check(row['source_line_sha256'] not in source_hashes, 'Candidate source lines are distinct')
        source_hashes.add(row['source_line_sha256'])
        words = row['retained_words']
        if words is not None:
            check(type(words) is int and words >= 0, 'Retained counts are nonnegative integers')
            processed += 1
            source_processed[community] += 1
        if row['reason'] is not None:
            rejections[row['reason']] += 1
            if row['reason'] == 'below_frozen_record_word_guard':
                check(words is not None and words < 20, 'Below-guard records remain below the frozen 20-word guard')
            else:
                check(words is None, 'Unpreprocessed rejection has no manufactured retained count')
            continue
        check(words is not None and words >= 20, 'Eligible records meet the frozen 20-word guard')
        date = instant(row['created_utc'])
        eligible_count += 1
        eligible_words += words
        source_eligible[community] += 1
        totals[account, community][0] += 1
        totals[account, community][1] += words
        for scheme, ranges in intervals.items():
            for part, (start, end) in ranges.items():
                if start <= date < end:
                    cells[scheme, account, community, part][0] += 1
                    cells[scheme, account, community, part][1] += words
    expected_observations = {(account, community): counts.get('comments', 0)
                             for account in candidates for community, counts in frames[account].items()}
    check(dict(observations) == expected_observations, 'Every candidate source comment appears exactly once in eligibility metadata')
    check(processed == capacity['preprocessed_records'], 'Preprocessed-record count recomputed from record metadata')
    check(eligible_count == capacity['eligible_records'] and eligible_words == capacity['eligible_words'], 'Eligible record and retained-word totals independently recomputed')
    check(dict(rejections) == {k: v for k, v in capacity['record_rejections'].items() if k != 'candidate_submissions'}, 'All logged comment rejection counts reconcile')

    accounts = {account for account, _ in totals}
    table, upper, by_scheme = [], {}, {}
    pair_names = []
    for left, right in plan['community_pairs']:
        name = left + ' / ' + right
        pair_names.append(name)
        enough = {account for account in accounts if all(totals[account, community][0] >= 16 and totals[account, community][1] >= 4000 for community in (left, right))}
        upper[name] = enough
        check(capacity['all_history_necessary_capacity'][name] == {'accounts': len(enough), 'blocks_upper_bound': len(enough)//2}, 'All-history 4000-word/16-record necessary bound recomputed: ' + name)
        for scheme in plan['period_schemes']:
            feasible = {account for account in accounts if all(cells[scheme['id'], account, community, part][0] >= 8 and cells[scheme['id'], account, community, part][1] >= 2000 for community in (left, right) for part in ('early', 'late'))}
            by_scheme[name, scheme['id']] = feasible
            check(feasible <= enough, 'Four-cell capacity is bounded by all-history capacity: ' + name)
            table.append({'community_pair': name, 'period_scheme': scheme['id'], 'four_cell_accounts': len(feasible), 'pairwise_blocks_upper_bound': len(feasible)//2})
    check(table == capacity['period_capacity_table'], 'Entire period capacity table independently recomputed')
    expected_cells = [{'period_scheme': s, 'account_key': a, 'community': c, 'period': p, 'eligible_records': counts[0], 'eligible_words': counts[1]}
                      for (s, a, c, p), counts in sorted(cells.items()) if counts[0]]
    check(read(private_run / 'cell-capacities.json') == expected_cells, 'Private cell table independently reconstructed from record metadata')
    witness = read(private_run / 'capacity-witness.json')
    capacity_exposed = {row['account_key'] for row in exclusion.get('prior_capacity_only_accounts', [])}
    chosen = {}
    for name in pair_names:
        ranked = []
        for scheme in plan['period_schemes']:
            spans = intervals[scheme['id']]
            imbalance = ((spans['early'][1]-spans['early'][0]).days - (spans['late'][1]-spans['late'][0]).days)**2
            ranked.append((-len(by_scheme[name, scheme['id']]), imbalance, scheme['id'], scheme))
        chosen[name] = sorted(ranked, key=lambda item: item[:3])[0][3]
        check(set(witness['eligible_accounts_by_pair'][name]) == by_scheme[name, chosen[name]['id']], 'Chosen-period private account membership independently reconciles: ' + name)
        check(set(witness['all_history_upper_bound_accounts_by_pair'][name]) == upper[name], 'All-history private membership independently reconciles: ' + name)
        members = by_scheme[name, chosen[name]['id']]
        check(capacity['prior_capacity_inspection_dependence'][name] == {
            'four_cell_accounts': len(members), 'with_prior_capacity_inspection': len(members & capacity_exposed),
            'without_prior_capacity_inspection': len(members - capacity_exposed)}, 'Prior availability-inspection dependency counts independently reconcile: ' + name)
    check(chosen == capacity['proposed_period_schemes'] == witness['chosen_period_schemes'], 'Period selection obeys availability, duration and ID tie rules')

    source_names = [source['community'] for source in plan['sources']]
    expected_pairs = {frozenset(pair) for pair in combinations(source_names, 2)}
    check(len(source_names) <= 8 and len(set(source_names)) == len(source_names),
          'Expansion contains at most eight distinct authorized source communities')
    check(len(plan['community_pairs']) == len(expected_pairs) and
          {frozenset(pair) for pair in plan['community_pairs']} == expected_pairs,
          'Every pair of declared communities is considered exactly once')
    recomputed_eligible = {name: by_scheme[name, chosen[name]['id']] for name in pair_names}
    optimum = check_capacity_choice(recomputed_eligible, capacity['selected_pair_strata'],
        capacity['disjoint_capacity'], witness['allocation'], check, 'Four-cell allocation')
    upper_optimum = check_capacity_choice(upper, capacity['upper_bound_best_pair_strata'],
        capacity['all_history_disjoint_upper_bound'], witness['upper_bound_allocation'], check,
        'All-history necessary upper-bound allocation')
    check(optimum['total_blocks'] <= upper_optimum['total_blocks'],
          'Global calendar-constrained complete blocks do not exceed global all-history necessary bound')
    expected_gate = 'capacity_pass_requires_contamination_audit' if optimum['feasible_target'] else 'failed_capacity'
    check(capacity['gate_a_status'] == expected_gate, 'Gate A target status agrees with independent exact Hall/assignment capacity')
    check(capacity['planned_accounts'] == 60 and capacity['planned_blocks'] == 30,
          'Expansion preserves original sixty-account thirty-block target')

    source_records = 0
    source_by_community = {source['community']: source for source in inventory['sources']}
    second_by_community = {source['community']: source for source in second_pass}
    check(len(source_by_community) == len(plan['sources']), 'Source inventory has one entry per predeclared archive')
    check(len(second_by_community) == len(plan['sources']), 'Second-pass binding has one entry per predeclared archive')
    for source in plan['sources']:
        actual = source_by_community[source['community']]
        check(all(actual[key] == source[key] for key in ('archive', 'bytes', 'sha256', 'community')), 'Source identity matches predeclared archive: ' + source['community'])
        check(actual['duplicate_ids'] == 0, 'First source pass reports no duplicate IDs: ' + source['community'])
        check(actual['counts']['comments'] + actual['counts']['submissions'] == actual['counts']['source_records'], 'Source kind counts partition source records: ' + source['community'])
        source_records += actual['counts']['source_records']
        later = second_by_community.get(source['community'], {})
        check(later.get('rows') == actual['counts']['source_records'] and
              later.get('utterances_sha256') == actual['utterances_sha256'], 'Both complete source passes have identical member counts and digests: ' + source['community'])
        if source_root is not None:
            check(fingerprint(Path(source_root) / source['archive']) == {'sha256': source['sha256'], 'bytes': source['bytes']}, 'Fresh compressed archive digest matches: ' + source['community'])
    check(source_records == inventory['source_records'] == inventory['unique_record_ids'], 'Source totals sum across archives')
    check(resources['source_rows_per_pass'] == source_records and resources['source_passes'] == 2, 'Completed resource receipt reports two complete source passes')
    check(resources['preprocessed_records'] == processed, 'Resource count agrees with independently counted preprocessor results')
    check(source_records <= plan['limits']['max_source_rows_per_pass'] and processed <= plan['limits']['max_preprocessed_records'], 'Observed record effort fits preregistered bounds')
    check(resources['wall_seconds'] <= plan['limits']['max_wall_seconds'] and resources['private_output_bytes'] <= plan['limits']['max_private_output_bytes'], 'Observed wall-time and private output fit preregistered bounds')
    check(resources['private_output_bytes'] == sum(fingerprint(private_run / name)['bytes'] for name in expected_private), 'Private output byte count reconciles')

    receipt = read(receipt_path)
    check(receipt['exit_code'] == 0, 'Fresh census command succeeded')
    prefix = str(receipt_path).removesuffix('.receipt.json')
    for suffix in ('stdout.log', 'stderr.log'):
        check(fingerprint(prefix + '.' + suffix) == receipt['outputs'][suffix], 'Fresh receipt log bytes reconcile: ' + suffix)
    events = list(jsonlines(prefix + '.stdout.log'))
    metadata_events = {event['community']: event for event in events if event.get('phase') == 'metadata'}
    preprocessing_events = [event for event in events if event.get('phase') == 'preprocessing']
    check(len(metadata_events) == len(plan['sources']), 'Fresh progress log records every metadata source pass')
    for community, source in source_by_community.items():
        check(metadata_events.get(community, {}).get('rows') == source['counts']['source_records'], 'Fresh logged source count matches inventory: ' + community)
    check([event['community'] for event in preprocessing_events] == [source['community'] for source in plan['sources']], 'Fresh progress log records every preprocessing source pass')
    cumulative_processed = cumulative_eligible = 0
    for event in preprocessing_events:
        cumulative_processed += source_processed[event['community']]
        cumulative_eligible += source_eligible[event['community']]
        check(event['processed'] == cumulative_processed and event['eligible'] == cumulative_eligible, 'Fresh preprocessing progress recomputed from record metadata: ' + event['community'])
    check(events[-1] == capacity, 'Fresh final stdout agrees with public capacity artifact')
    check(not binding['scores_computed'] and not inventory['scores_computed'] and not capacity['scores_computed'] and not capacity['final_cohort_selected'], 'Gate-A artifacts declare no scoring or final cohort')
    return {
        'status': 'pass' if not errors else 'fail',
        'checks_performed': checks_performed,
        'failed_checks': sorted(set(errors)),
        'independently_recomputed': {
            'source_records': source_records,
            'nonexcluded_comment_accounts': len(frames),
            'preprocessing_candidate_accounts': len(candidates),
            'candidate_comment_rows': len(seen),
            'preprocessed_records': processed,
            'eligible_records': eligible_count,
            'eligible_words': eligible_words,
            'period_capacity_table': table,
            'all_history_necessary_capacity': {name: {'accounts': len(rows), 'blocks_upper_bound': len(rows)//2} for name, rows in upper.items()},
            'global_three_stratum_optimum': optimum,
            'global_all_history_necessary_optimum': upper_optimum,
        },
        'input_hashes': {path.name: fingerprint(path) for path in [plan_path, receipt_path, exclusion_path, *sorted(census_root.glob('*.json'))]},
        'checker_sha256': fingerprint(__file__)['sha256'],
        'corpus_prose_read': False,
        'distance_scores_computed': False,
        'limitations': [
            'Record source-line digests are checked for form and uniqueness; original prose is not reopened to rederive those digests.',
            'Original ZIP-member counts and digests are bound to the fresh census inventory and logs; optional archive verification rehashes compressed bytes only.',
            'Preprocessing retained counts are reconciled from private records, not recomputed from original prose; synthetic tests separately exercise the frozen preprocessor.',
            'Global stratum and even-quota optimality are independently enumerated by exact Hall bitset capacities; private assignment membership and disjointness are checked, but final cohort selection and contamination auditing remain pending.',
            'Excluded identity checks establish absence from published private preprocessing rows, not a runtime access trace.',
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--census', required=True, type=Path)
    parser.add_argument('--private-root', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    report = reconcile(args.plan, args.census, args.private_root, args.receipt, args.source_root)
    with args.out.open('x') as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write('\n')
    print(json.dumps({'status': report['status'], 'checks_performed': report['checks_performed'], 'failed_checks': report['failed_checks'], 'output': fingerprint(args.out)}))
    raise SystemExit(0 if report['status'] == 'pass' else 1)


if __name__ == '__main__':
    main()
