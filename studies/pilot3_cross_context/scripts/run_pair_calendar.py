#!/usr/bin/env python3
"""Metadata-only final pair calendar and fixed three-stratum feasibility gate."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import time

from calendar_capacity import best_calendar_pairs
from study_math import maximum_disjoint_capacity


START, END = '2008-01-01', '2018-11-01'
FIXED_PRIOR_CUTS = {'AskAcademia / GradSchool': '2015-10-06', 'AskPhysics / Physics': '2015-09-20'}
NEW_PAIR = 'learnmath / math'
EXPECTED_IMPLEMENTATION = 'bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179'
EXPECTED_CONFIG = '8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925'
EXPECTED_AMENDMENT_SHA256 = '7ebc758e387f51dc80890e39a1e9b8ede3a87d05175e00a329db5f823a00a821'
EXPECTED_RESOURCE_AMENDMENT_SHA256 = 'd664743e08402cd044714c4846263dd6b97c097b9200afbca522f80f875e2e31'
FROZEN_PRIOR_PUBLIC_HASHES = {
    'capacity.json': '70ac02bd576ac4cb6ef2cbbea47c8143736c0bef5a5816005d970ea019d2ee4f',
    'start-binding.json': 'c940a823be921af1ed5cac47bbfc1172147561d21f11bb8b6f14c331e88918e0',
    'private-artifact-hashes.json': 'ed91087389ce805ececeb3917abefbffbba0f40fa5592044b1ef2d5aeebcd96d',
    'resources.json': '502fda4624b2c5b12897b8d3619f258ee70460761140d62e174b9c567eb41f59',
}
LIMITS = {'metadata_rows': 500_000, 'wall_seconds': 300, 'address_space_bytes': 4 * 1024**3,
          'private_output_bytes': 100 * 1024**2}


def read(path):
    return json.loads(Path(path).read_bytes())


def fingerprint(path):
    with Path(path).open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    return {'sha256': digest, 'bytes': Path(path).stat().st_size}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write(path, value, *, private=False, remaining_bytes=None):
    payload = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    if remaining_bytes is not None and len(payload) > remaining_bytes:
        raise RuntimeError('Predeclared private output budget exhausted')
    with Path(path).open('xb') as handle:
        handle.write(payload)
    if private:
        Path(path).chmod(0o600)
    return len(payload)


def scheme(cut):
    return {'id': 'utc_midnight_' + cut, 'early': [START, cut], 'late': [cut, END]}


def load_fixed_prior(prior_calendar, private_root, exclusion_sha, excluded):
    """Read hash-bound prior metadata only; never choose new prior dates/accounts."""
    prior_calendar, private_root = Path(prior_calendar), Path(private_root)
    for name, expected in FROZEN_PRIOR_PUBLIC_HASHES.items():
        require(fingerprint(prior_calendar / name)['sha256'] == expected,
                'Frozen prior calendar public artifact changed: ' + name)
    public = read(prior_calendar / 'capacity.json')
    binding = read(prior_calendar / 'start-binding.json')
    require(public['style_scores_computed'] == 0 and public['final_cohort_selected'] is False,
            'Prior calendar is not score-free capacity evidence')
    require(read(prior_calendar / 'resources.json')['resource_outcome'] == 'completed_within_predeclared_limits',
            'Prior calendar did not complete its resource gate')
    manifest = read(prior_calendar / 'private-artifact-hashes.json')
    require(set(manifest) == {'calendar-capacities.json', 'capacity-witness.json'}, 'Unexpected prior private artifact inventory')
    private_prior = private_root / prior_calendar.name
    for name, expected in manifest.items():
        require(fingerprint(private_prior / name) == expected, 'Prior private calendar bytes changed: ' + name)
    choices = read(private_prior / 'calendar-capacities.json')
    require(choices['start'] == START and choices['end'] == END,
            'Prior calendar family differs from amendment 03')
    source_name = binding['source_census']
    require(Path(source_name).name == source_name, 'Prior source census must be a local directory name')
    source_census = prior_calendar.parent / source_name
    source_binding = read(source_census / 'start-binding.json')
    require(source_binding['plan_sha256'] == binding['plan_sha256'], 'Prior calendar/census plan bindings disagree')
    require(source_binding['exclusions_sha256'] == exclusion_sha, 'Mandatory exclusions differ from prior census')
    require(source_binding['implementation_fingerprint'] == EXPECTED_IMPLEMENTATION and
            source_binding['analysis_config_sha256'] == EXPECTED_CONFIG, 'Prior census numerical baseline changed')
    require(fingerprint(source_census / 'source-inventory.json')['sha256'] == binding['source_inventory_sha256'],
            'Prior source inventory bytes changed')
    prior_metadata = private_root / source_name / 'record-eligibility.jsonl'
    prior_metadata_fp = fingerprint(prior_metadata)
    source_manifest = read(source_census / 'private-artifact-hashes.json')
    require(prior_metadata_fp == source_manifest['record-eligibility.jsonl'] and
            prior_metadata_fp['sha256'] == binding['eligibility_metadata_sha256'], 'Prior eligibility metadata binding changed')
    fixed = {}
    for name, cut in FIXED_PRIOR_CUTS.items():
        item = choices['pairs'][name]
        summary = public['pair_capacities'][name]
        require(item['scheme'] == summary['chosen_calendar_scheme'] == scheme(cut),
                'Frozen prior pair dates changed: ' + name)
        accounts = item['accounts']
        require(len(accounts) == len(set(accounts)) == item['maximum_accounts'] == summary['maximum_four_cell_accounts'],
                'Prior public/private capacity counts disagree: ' + name)
        require(not set(accounts) & excluded, 'Excluded account appears in frozen prior capacity')
        intervals = {r['account_key']: r for r in item['account_cut_intervals_private']}
        require(all(a in intervals and intervals[a]['first_cut'] <= cut <= intervals[a]['last_cut'] for a in accounts),
                'Prior chosen account lies outside its frozen valid cut interval')
        fixed[name] = set(accounts)
    return fixed, {'public_hashes': FROZEN_PRIOR_PUBLIC_HASHES, 'private_manifest': manifest,
                   'source_census': source_name, 'eligibility_metadata': prior_metadata_fp,
                   'prior_metadata_rows_parsed': 0, 'fixed_schemes': {p: scheme(c) for p, c in FIXED_PRIOR_CUTS.items()}}


def run(plan_path, amendment_path, census, prior_calendar, private_root, out):
    started = time.monotonic()
    plan_path, amendment_path, census, prior_calendar, private_root, out = map(Path,
        (plan_path, amendment_path, census, prior_calendar, private_root, out))
    resource.setrlimit(resource.RLIMIT_AS, (LIMITS['address_space_bytes'],) * 2)
    out.mkdir(parents=True, exist_ok=False)
    private_out = private_root / out.name
    private_out.mkdir(mode=0o700, exist_ok=False)

    def bounded(total=0):
        if total > LIMITS['metadata_rows'] or time.monotonic() - started > LIMITS['wall_seconds']:
            raise RuntimeError('Predeclared metadata-row or wall-time budget exhausted')

    plan = read(plan_path)
    amendment_hash = fingerprint(amendment_path)['sha256']
    require(plan.get('amendment') == amendment_path.name, 'Plan and supplied amendment differ')
    if amendment_path.name == 'AMENDMENT_04_METADATA_LIMIT_CORRECTION.md':
        require(amendment_hash == EXPECTED_RESOURCE_AMENDMENT_SHA256,
                'Amendment 04 bytes changed before final pair refinement')
        require(fingerprint(amendment_path.with_name('AMENDMENT_03_FINAL_MATH_PAIR.md'))['sha256'] == EXPECTED_AMENDMENT_SHA256,
                'Underlying amendment 03 pair/calendar rules changed')
    else:
        require(amendment_path.name == 'AMENDMENT_03_FINAL_MATH_PAIR.md' and amendment_hash == EXPECTED_AMENDMENT_SHA256,
                'Amendment 03 bytes changed before final pair refinement')
    target = plan['target']
    require(target == {'accounts': 20, 'blocks': 10, 'strata': 1, 'accounts_per_stratum': 20,
                       'blocks_per_stratum': 10, 'words_per_cell': 2000, 'eligible_records_per_cell': 8},
            'Input must be the unchanged twenty-account single-pair intake')
    communities = [source['community'] for source in plan['sources']]
    require(len(communities) == 2 and set(communities) == {'math', 'learnmath'} and
            len(plan['community_pairs']) == 1 and set(plan['community_pairs'][0]) == set(communities),
            'Only the predeclared math/learnmath intake is permitted')
    require(plan['implementation_fingerprint'] == EXPECTED_IMPLEMENTATION and plan['analysis_config_sha256'] == EXPECTED_CONFIG,
            'Plan differs from the frozen AHAS numerical baseline')
    exclusions_path = private_root / 'exclusions-mandatory.json'
    exclusions_fp = fingerprint(exclusions_path)
    exclusions = read(exclusions_path)
    require(exclusions.get('complete_for_known_pilot_sources') is True, 'Known mandatory exclusions are incomplete')
    excluded = {r['account_key'].casefold() for r in exclusions['accounts']}
    earlier_capacity = {r['account_key'].casefold() for r in exclusions.get('prior_capacity_only_accounts', [])}
    binding = read(census / 'start-binding.json')
    require(binding['plan_sha256'] == fingerprint(plan_path)['sha256'], 'New census plan binding changed')
    require(binding['script_sha256'] == fingerprint(Path(__file__).with_name('census_pair.py'))['sha256'],
            'New census is not bound to the single-pair intake implementation')
    require(binding['exclusions_sha256'] == exclusions_fp['sha256'], 'New census mandatory exclusions changed')
    require(binding['implementation_fingerprint'] == EXPECTED_IMPLEMENTATION and
            binding['analysis_config_sha256'] == EXPECTED_CONFIG, 'New census numerical identity changed')
    require(binding['scores_computed'] is False, 'New census has unexpected score status')
    capacity = read(census / 'capacity.json')
    require(capacity['gate_a_status'] in {'pair_capacity_pass', 'pair_capacity_failed'} and
            capacity['scoring_permitted'] is False and capacity['final_cohort_selected'] is False,
            'Input is not completed score-free single-pair capacity evidence')
    require(read(census / 'resources.json')['resource_outcome'] == 'completed_within_predeclared_limits',
            'New census resource gate did not complete')
    inventory = read(census / 'source-inventory.json')
    require(inventory['scores_computed'] is False, 'New inventory has unexpected score status')
    require([{key: source[key] for key in ('community', 'archive', 'sha256', 'bytes')} for source in inventory['sources']] == plan['sources'],
            'New source inventory differs from frozen source plan')
    new_manifest = read(census / 'private-artifact-hashes.json')
    records_path = private_root / census.name / 'record-eligibility.jsonl'
    records_fp = fingerprint(records_path)
    require(records_fp == new_manifest['record-eligibility.jsonl'], 'New eligibility metadata bytes changed')
    fixed, prior_binding = load_fixed_prior(prior_calendar, private_root, exclusions_fp['sha256'], excluded)
    bounded()
    start = {'phase': 'before_final_pair_metadata_calendar_refinement', 'utc': datetime.now(timezone.utc).isoformat(),
             'plan': fingerprint(plan_path), 'amendment': fingerprint(amendment_path),
             'source_census': census.name, 'new_eligibility_metadata': records_fp,
             'source_census_public_hashes': {p.name: fingerprint(p) for p in sorted(census.glob('*.json'))},
             'mandatory_exclusions': exclusions_fp, 'prior_calendar': prior_binding,
             'scripts': {name: fingerprint(Path(__file__).with_name(name))['sha256'] for name in
                         ('run_pair_calendar.py', 'calendar_capacity.py', 'study_math.py', 'census_pair.py')},
             'limits': LIMITS, 'source_prose_reads': 0, 'new_preprocessing_calls': 0, 'style_scores_computed': 0}
    write(out / 'start-binding.json', start)
    rows, total = [], 0
    with records_path.open() as handle:
        for line in handle:
            total += 1
            bounded(total)
            row = json.loads(line)
            require(row['account_key'] not in excluded, 'Excluded account reached new calendar metadata')
            if row['reason'] is None:
                rows.append(row)
    require(fingerprint(records_path) == records_fp, 'New metadata changed during reading')
    choices = best_calendar_pairs(rows, communities, START, END)
    require(set(choices['pairs']) == {NEW_PAIR}, 'Unexpected pair generated by calendar refinement')
    new = choices['pairs'][NEW_PAIR]
    all_pairs = {**fixed, NEW_PAIR: set(new['accounts'])}
    allocation = maximum_disjoint_capacity(all_pairs, limit_per_stratum=20)
    passed = (allocation['total_accounts'] == 60 and allocation['total_blocks'] == 30 and
              len(allocation['quota_counts']) == 3 and all(q == 20 for q in allocation['quota_counts'].values()))
    schemes = {**{pair: scheme(cut) for pair, cut in FIXED_PRIOR_CUTS.items()}, NEW_PAIR: new['scheme']}
    witness = {'selected_pairs': sorted(all_pairs), 'capacity': allocation, 'feasible_target': passed,
               'eligible_accounts_by_pair': {p: sorted(accounts) for p, accounts in sorted(all_pairs.items())},
               'proposed_period_schemes': schemes, 'fixed_prior_pair_strata': sorted(FIXED_PRIOR_CUTS),
               'new_pair': NEW_PAIR, 'final_cohort_selected': False}
    bounded(total)
    private_bytes = write(private_out / 'calendar-capacities.json', choices, private=True,
                          remaining_bytes=LIMITS['private_output_bytes'])
    private_bytes += write(private_out / 'capacity-witness.json', witness, private=True,
                           remaining_bytes=LIMITS['private_output_bytes'] - private_bytes)
    summary = {'phase': 'fixed_two_prior_strata_plus_final_math_pair_metadata_calendar',
               'gate_a_status': 'capacity_pass_requires_contamination_audit' if passed else 'failed_capacity',
               'scoring_permitted': False, 'planned_accounts': 60, 'planned_blocks': 30,
               'selected_pair_strata': sorted(all_pairs), 'proposed_period_schemes': schemes,
               'fixed_prior_pair_strata': sorted(FIXED_PRIOR_CUTS), 'new_pair': NEW_PAIR,
               'disjoint_capacity': {k: v for k, v in allocation.items() if k != 'assigned'},
               'pair_capacities': {p: {'maximum_four_cell_accounts': len(accounts), 'chosen_calendar_scheme': schemes[p],
                                     'fixed_from_prior_calendar': p in FIXED_PRIOR_CUTS,
                                     'prior_capacity_inspected_accounts': len(accounts & earlier_capacity)}
                                   for p, accounts in sorted(all_pairs.items())},
               'metadata_rows_read': total, 'eligible_metadata_rows': len(rows),
               'new_pair_calendar_cuts_considered': new['all_internal_day_cuts_considered'],
               'prior_metadata_rows_parsed': 0, 'prior_metadata_bytes_rehashed': prior_binding['eligibility_metadata']['bytes'],
               'final_cohort_selected': False, 'style_scores_computed': 0, 'source_prose_reads': 0, 'preprocessing_calls': 0,
               'leakage_audit_status': 'not_run; capacities precede contamination filtering',
               'scope': 'Exactly two frozen prior pair/date sets and the exhaustive shared-midnight math/learnmath pair; no other community combinations considered.'}
    bounded(total)
    write(out / 'capacity.json', summary)
    write(out / 'private-artifact-hashes.json', {p.name: fingerprint(p) for p in sorted(private_out.iterdir())})
    write(out / 'resources.json', {'wall_seconds': time.monotonic() - started,
        'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        'metadata_rows': total, 'prior_metadata_bytes_rehashed': prior_binding['eligibility_metadata']['bytes'],
        'private_output_bytes': private_bytes, 'limits': LIMITS, 'source_prose_reads': 0, 'preprocessing_calls': 0,
        'resource_outcome': 'completed_within_predeclared_limits'})
    return summary


def main():
    parser = argparse.ArgumentParser()
    for name in ('plan', 'amendment', 'census', 'prior-calendar', 'private-root', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.plan, args.amendment, args.census, args.prior_calendar, args.private_root, args.out)), flush=True)


if __name__ == '__main__':
    main()
