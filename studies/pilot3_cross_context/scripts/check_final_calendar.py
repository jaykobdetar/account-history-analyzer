#!/usr/bin/env python3
"""Independent final-pair calendar verification; reads metadata and witnesses only.

The imported oracle enumerates every midnight with literal chronological prefix
counts and exhausts all even quota vectors. No production or selection helper is
imported. The already independently checked prior two sets remain frozen.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import time

from check_calendar_census import direct_calendar_counts, exhaustive_three_strata, fingerprint, jsonlines, read

START, END = '2008-01-01', '2018-11-01'
NEW_PAIR = 'learnmath / math'
FIXED = {'AskAcademia / GradSchool': ('2015-10-06', 39), 'AskPhysics / Physics': ('2015-09-20', 36)}
MAX_ROWS, MAX_SECONDS, MAX_BYTES, MAX_AS = 500_000, 300, 100 * 1024**2, 4 * 1024**3
PRIOR_REPORT_SHA = '612c1ea2864691505f9361c20e50eb4bfcd32698c94667305b16a0157f1b4fa1'
ORACLE_SHA = '0fc5552b4a8ffbb14e0c00df18509db3d02633e22c538c3b08ea51c1611b5e0e'
PRIOR_PUBLIC = {
    'capacity.json': '70ac02bd576ac4cb6ef2cbbea47c8143736c0bef5a5816005d970ea019d2ee4f',
    'start-binding.json': 'c940a823be921af1ed5cac47bbfc1172147561d21f11bb8b6f14c331e88918e0',
    'private-artifact-hashes.json': 'ed91087389ce805ececeb3917abefbffbba0f40fa5592044b1ef2d5aeebcd96d',
    'resources.json': '502fda4624b2c5b12897b8d3619f258ee70460761140d62e174b9c567eb41f59',
}


def scheme(cut):
    return {'id': 'utc_midnight_' + cut, 'early': [START, cut], 'late': [cut, END]}


class Checks:
    def __init__(self):
        self.count, self.failures = 0, []

    def __call__(self, condition, description):
        self.count += 1
        if not condition:
            self.failures.append(description)


def check_allocation(sets, selection, summary, protected, check):
    """Independent Hall optimum plus constructive saved-witness validation."""
    optimum = exhaustive_three_strata(sets)
    allocation = selection['capacity']
    check(set(sets) == set(FIXED) | {NEW_PAIR}, 'Exactly the three registered pair strata')
    check(optimum['selected_pairs'] == selection['selected_pairs'] == summary['selected_pair_strata'], 'Registered three-stratum identities agree')
    for field in ('quota_counts', 'total_accounts', 'total_blocks'):
        check(optimum[field] == allocation[field] == summary['disjoint_capacity'][field], 'Independent exhaustive quota optimum: ' + field)
    check(selection['feasible_target'] == optimum['feasible_target'], 'Independent full-target feasibility agrees')
    expected_status = 'capacity_pass_requires_contamination_audit' if optimum['feasible_target'] else 'failed_capacity'
    check(summary['gate_a_status'] == expected_status, 'Gate A status follows exact full-target feasibility')
    check(set(allocation['assigned']) == set(sets), 'Saved allocation has all and only registered strata')
    assigned = []
    for name, accounts in allocation['assigned'].items():
        check(name in sets and set(accounts) <= sets.get(name, set()), 'Every assigned account eligible in its stratum: ' + name)
        check(len(accounts) == len(set(accounts)) == optimum['quota_counts'].get(name), 'Assignment uniqueness and exact even quota: ' + name)
        check(len(accounts) <= 20 and len(accounts) % 2 == 0, 'Twenty-account cap and complete-block quota: ' + name)
        assigned.extend(accounts)
    check(len(assigned) == len(set(assigned)) == optimum['total_accounts'], 'Assignment globally disjoint and attains exact optimum')
    check(not set.union(*sets.values()) & protected, 'Mandatory exclusions absent from every capacity set')
    check(all(a == a.casefold() for a in set.union(*sets.values())), 'All capacity account keys canonical')
    check(selection['eligible_accounts_by_pair'] == {p: sorted(a) for p, a in sorted(sets.items())}, 'Full private capacity sets match independent and frozen sources')
    check(summary['disjoint_capacity'] == {k: v for k, v in allocation.items() if k != 'assigned'}, 'Public allocation equals private witness summary')
    return optimum


def check_receipt(path, check):
    receipt = read(path)
    prefix = str(path).removesuffix('.receipt.json')
    check(receipt['exit_code'] == 0, 'Bound command receipt succeeded: ' + Path(path).name)
    for suffix in ('stdout.log', 'stderr.log'):
        check(fingerprint(prefix + '.' + suffix) == receipt['outputs'][suffix], 'Bound command log unchanged: ' + Path(prefix).name + '.' + suffix)
    return read(prefix + '.stdout.log')


def verify(plan_path, amendment_path, census, calendar, prior_calendar, private_root, receipt_path, prior_report_path, prior_receipt_path):
    started = time.monotonic()
    plan_path, amendment_path, census, calendar, prior_calendar, private_root, receipt_path, prior_report_path, prior_receipt_path = map(Path, (plan_path, amendment_path, census, calendar, prior_calendar, private_root, receipt_path, prior_report_path, prior_receipt_path))
    check = Checks()
    plan, binding, summary = read(plan_path), read(calendar / 'start-binding.json'), read(calendar / 'capacity.json')
    resources = read(calendar / 'resources.json')
    metadata = private_root / census.name / 'record-eligibility.jsonl'
    private = private_root / calendar.name
    exclusion_path = private_root / 'exclusions-mandatory.json'
    exclusions = read(exclusion_path)
    protected = {r['account_key'].casefold() for r in exclusions['accounts']}
    previous = {r['account_key'].casefold() for r in exclusions.get('prior_capacity_only_accounts', [])}
    check(exclusions['complete_for_known_pilot_sources'] is True, 'Known mandatory exclusion inventory complete')
    check(binding['plan'] == fingerprint(plan_path), 'Final calendar plan bytes bound')
    check(binding['amendment'] == fingerprint(amendment_path), 'Final calendar amendment bytes bound')
    check(binding['source_census'] == census.name, 'New metadata source census identity')
    check(binding['mandatory_exclusions'] == fingerprint(exclusion_path), 'Mandatory exclusion bytes bound')
    check(binding['new_eligibility_metadata'] == fingerprint(metadata) == read(census / 'private-artifact-hashes.json')['record-eligibility.jsonl'], 'New metadata bytes agree with census and calendar')
    check(set(s['community'] for s in plan['sources']) == {'math', 'learnmath'} and len(plan['sources']) == 2 and len(plan['community_pairs']) == 1 and sorted(plan['community_pairs'][0]) == ['learnmath', 'math'], 'Only the registered two new sources and pair')
    for name, expected in binding['source_census_public_hashes'].items():
        check(Path(name).name == name and fingerprint(census / name) == expected, 'Bound new census public artifact: ' + name)
    census_binding = read(census / 'start-binding.json')
    check(census_binding['plan_sha256'] == binding['plan']['sha256'] and census_binding['exclusions_sha256'] == binding['mandatory_exclusions']['sha256'], 'Original census plan and exclusions match')
    check(census_binding['scores_computed'] is False and read(census / 'resources.json')['resource_outcome'] == 'completed_within_predeclared_limits', 'New census completed its score-free resource gate')
    for name, expected in binding['scripts'].items():
        check(fingerprint(Path(__file__).with_name(name))['sha256'] == expected, 'Bound original execution helper identity: ' + name)
    check(fingerprint(Path(__file__).with_name('check_calendar_census.py'))['sha256'] == ORACLE_SHA, 'Independent direct oracle identity unchanged')
    manifests = read(calendar / 'private-artifact-hashes.json')
    check(set(manifests) == {'calendar-capacities.json', 'capacity-witness.json'}, 'Exact private calendar artifact inventory')
    for name, expected in manifests.items():
        check(Path(name).name == name and fingerprint(private / name) == expected, 'Bound final private artifact: ' + name)
    prior_binding = binding['prior_calendar']
    check(prior_binding['public_hashes'] == PRIOR_PUBLIC, 'Registered prior public hashes unchanged')
    for name, expected in PRIOR_PUBLIC.items():
        check(fingerprint(prior_calendar / name)['sha256'] == expected, 'Frozen prior public artifact: ' + name)
    prior_manifest = read(prior_calendar / 'private-artifact-hashes.json')
    check(prior_manifest == prior_binding['private_manifest'], 'Prior private manifest matches final binding')
    for name, expected in prior_manifest.items():
        check(fingerprint(private_root / prior_calendar.name / name) == expected, 'Frozen prior private artifact: ' + name)
    prior_metadata = private_root / prior_binding['source_census'] / 'record-eligibility.jsonl'
    check(fingerprint(prior_metadata) == prior_binding['eligibility_metadata'], 'Prior eligibility metadata bytes unchanged; no row parse')
    prior_report = read(prior_report_path)
    check(fingerprint(prior_report_path)['sha256'] == PRIOR_REPORT_SHA and prior_report['status'] == 'pass' and not prior_report['failed_checks'], 'Frozen prior independent calendar review passed')
    check(prior_report['checker_sha256'] == ORACLE_SHA and prior_report['input_hashes']['record-eligibility.jsonl'] == fingerprint(prior_metadata), 'Prior independent review binds same oracle and source metadata')
    prior_stdout = check_receipt(prior_receipt_path, check)
    check(prior_stdout['status'] == 'pass' and prior_stdout['output'] == fingerprint(prior_report_path), 'Prior independent receipt binds exact passing report')
    prior_choices = read(private_root / prior_calendar.name / 'calendar-capacities.json')
    prior_summary = read(prior_calendar / 'capacity.json')
    sets, schemes = {}, {}
    for name, (cut, capacity) in FIXED.items():
        entry = prior_choices['pairs'][name]
        sets[name], schemes[name] = set(entry['accounts']), scheme(cut)
        check(entry['scheme'] == schemes[name] == prior_summary['pair_capacities'][name]['chosen_calendar_scheme'] == prior_report['pair_capacity_table'][name]['chosen_calendar_scheme'], 'Fixed prior dates agree with independently checked dates: ' + name)
        check(len(entry['accounts']) == len(sets[name]) == capacity == entry['maximum_accounts'] == prior_report['pair_capacity_table'][name]['maximum_four_cell_accounts'], 'Fixed prior account set count agrees: ' + name)
        check(prior_binding['fixed_schemes'][name] == schemes[name], 'Final binding retains exact prior scheme: ' + name)
    def bounded_rows():
        for n, row in enumerate(jsonlines(metadata), 1):
            if n > MAX_ROWS or time.monotonic() - started > MAX_SECONDS:
                raise RuntimeError('Independent final calendar metadata/time budget exhausted')
            yield row
    computed = direct_calendar_counts(bounded_rows(), ['math', 'learnmath'], START, END, protected)
    new_choices = read(private / 'calendar-capacities.json')
    check(set(computed['pairs']) == set(new_choices['pairs']) == {NEW_PAIR}, 'Every new-source pair, and only that pair, independently evaluated')
    check(computed['metadata_rows'] == summary['metadata_rows_read'] == resources['metadata_rows'], 'Every new metadata row counted')
    check(computed['eligible_rows'] == summary['eligible_metadata_rows'] == new_choices['input_eligible_metadata_rows'], 'Eligible metadata rows independently counted')
    check(computed['inside_rows'] == new_choices['rows_inside_calendar_bounds'] and computed['outside_rows'] == new_choices['rows_outside_calendar_bounds'], 'Calendar inclusion independently counted')
    check(new_choices['start'] == START and new_choices['end'] == END and new_choices['words_per_cell'] == 2000 and new_choices['eligible_records_per_cell'] == 8, 'Full calendar and four-cell guards unchanged')
    check(computed['internal_midnight_cuts'] == 3956 == summary['new_pair_calendar_cuts_considered'], 'Every one of 3956 interior midnight cuts evaluated')
    new = computed['pairs'][NEW_PAIR]
    for field, expected in new.items():
        actual = new_choices['pairs'][NEW_PAIR][field]
        check((set(actual) if field == 'accounts' else actual) == expected, 'Direct every-midnight result agrees: ' + field)
    sets[NEW_PAIR], schemes[NEW_PAIR] = new['accounts'], new['scheme']
    selection = read(private / 'capacity-witness.json')
    check(summary['proposed_period_schemes'] == selection['proposed_period_schemes'] == schemes, 'All three final proposed periods agree')
    check(summary['fixed_prior_pair_strata'] == selection['fixed_prior_pair_strata'] == sorted(FIXED) and summary['new_pair'] == selection['new_pair'] == NEW_PAIR, 'Fixed versus new pair designation unchanged')
    check(set(summary['pair_capacities']) == set(sets), 'Public pair inventory exact')
    for name, accounts in sets.items():
        public = summary['pair_capacities'][name]
        check(public['maximum_four_cell_accounts'] == len(accounts) and public['chosen_calendar_scheme'] == schemes[name], 'Public capacity and dates independently verified: ' + name)
        check(public['prior_capacity_inspected_accounts'] == len(accounts & previous), 'Prior capacity-inspection exposure count: ' + name)
        check(public['fixed_from_prior_calendar'] == (name in FIXED), 'Prior source role: ' + name)
    optimum = check_allocation(sets, selection, summary, protected, check)
    check(check_receipt(receipt_path, check) == summary, 'Fresh final calendar stdout equals public summary')
    check(summary['source_prose_reads'] == summary['preprocessing_calls'] == summary['style_scores_computed'] == 0 and summary['scoring_permitted'] is False and summary['final_cohort_selected'] is False and selection['final_cohort_selected'] is False, 'Final calendar remains unscored metadata-only capacity evidence')
    check(resources['resource_outcome'] == 'completed_within_predeclared_limits' and resources['wall_seconds'] <= MAX_SECONDS and resources['private_output_bytes'] <= MAX_BYTES and resources['metadata_rows'] <= MAX_ROWS, 'Original calendar resource gate respected')
    check(summary['prior_metadata_rows_parsed'] == prior_binding['prior_metadata_rows_parsed'] == 0, 'Prior rows were not reselected')
    check(fingerprint(metadata) == binding['new_eligibility_metadata'], 'New metadata unchanged during independent verification')
    elapsed = time.monotonic() - started
    check(elapsed <= MAX_SECONDS, 'Independent checker within 300-second limit')
    return {'status': 'pass' if not check.failures else 'fail', 'checks_performed': check.count, 'failed_checks': check.failures,
            'metadata_rows': computed['metadata_rows'], 'eligible_rows': computed['eligible_rows'], 'calendar_cuts_per_new_pair': computed['internal_midnight_cuts'],
            'pair_capacity_table': {p: {'maximum_four_cell_accounts': len(a), 'chosen_calendar_scheme': schemes[p]} for p, a in sorted(sets.items())},
            'independent_three_stratum_optimum': optimum, 'original_prose_reads': 0, 'preprocessing_calls': 0, 'style_scores_computed': 0,
            'identifiers_exported': False, 'prior_metadata_rows_parsed': 0, 'wall_seconds': elapsed,
            'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            'checker_sha256': fingerprint(__file__)['sha256'], 'oracle_sha256': fingerprint(Path(__file__).with_name('check_calendar_census.py'))['sha256'],
            'input_hashes': {str(p): fingerprint(p) for p in (plan_path, amendment_path, metadata, calendar / 'start-binding.json', calendar / 'capacity.json', calendar / 'private-artifact-hashes.json', receipt_path, prior_report_path, prior_receipt_path)},
            'limitations': ['Only the new mathematics pair is directly enumerated here; the two prior sets retain their frozen passing independent calendar-03 verification.',
                            'Verification covers the registered fixed prior dates plus the new pair maximum; it does not optimize combinations of nonmaximal cuts.',
                            'Retained-word counts come from frozen census metadata, with original-writing fidelity checked separately.',
                            'Capacity precedes contamination filtering; this report is neither final cohort selection nor evidence of writing discrimination.']}


def main():
    parser = argparse.ArgumentParser()
    for name in ('plan', 'amendment', 'census', 'calendar', 'prior-calendar', 'private-root', 'receipt', 'prior-report', 'prior-receipt', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (MAX_AS,) * 2)
    with args.out.with_suffix('.start-binding.json').open('x') as handle:
        json.dump({'phase': 'before_independent_final_calendar_input_reads', 'utc': datetime.now(timezone.utc).isoformat(),
                   'scripts': {name: fingerprint(Path(__file__).with_name(name)) for name in ('check_final_calendar.py', 'check_calendar_census.py')},
                   'limits': {'metadata_rows': MAX_ROWS, 'wall_seconds': MAX_SECONDS, 'address_space_bytes': MAX_AS, 'output_bytes': MAX_BYTES},
                   'original_prose_reads': 0, 'preprocessing_calls': 0, 'style_scores_computed': 0}, handle, indent=2)
        handle.write('\n')
    report = verify(args.plan, args.amendment, args.census, args.calendar, args.prior_calendar, args.private_root, args.receipt, args.prior_report, args.prior_receipt)
    payload = (json.dumps(report, indent=2, sort_keys=True) + '\n').encode()
    if len(payload) > MAX_BYTES:
        raise RuntimeError('Independent report exceeds output budget')
    with args.out.open('xb') as handle:
        handle.write(payload)
    print(json.dumps({'status': report['status'], 'failed_checks': report['failed_checks'], 'total_accounts': report['independent_three_stratum_optimum']['total_accounts'],
                      'total_blocks': report['independent_three_stratum_optimum']['total_blocks'], 'output': fingerprint(args.out)}))
    raise SystemExit(0 if report['status'] == 'pass' else 1)


if __name__ == '__main__':
    main()
