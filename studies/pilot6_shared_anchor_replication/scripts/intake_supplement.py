"""Pilot6 score-free supplement to the immutable Pilot4 technical intake.

Only missing account/community memberships are preprocessed. The original
comment conversion and engine binding are imported unchanged from Pilot4.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import time
import zipfile

PAIRS = [['linux', 'linuxquestions'], ['programming', 'learnprogramming']]
HARD_LIMITS = {
    'max_address_space_bytes': 4 * 1024**3,
    'max_wall_seconds': 3600,
    'max_preprocessed_records': 2_000_000,
    'max_source_rows_per_pass': 15_000_000,
    'max_source_uncompressed_bytes_per_pass': 16 * 1024**3,
    'max_eligibility_output_bytes': 768 * 1024**2,
    'max_private_output_bytes': 1024**3,
}
FLAG_FIELDS = ('pilot1_or_pilot2_or_private_mandatory_exclusion',
               'pilot3_selected_scored_exposure', 'prior_capacity_only_exposure')
OLD_ROW_FIELDS = {'account_key', 'community', 'created_utc', 'parent_id', 'reason',
                  'record_id', 'retained_words', 'source_line_sha256', 'thread_id'}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def verify_ref(ref):
    path = Path(ref['path'])
    require(path.is_absolute() and path.is_file(), 'bound_file_missing')
    require(path.stat().st_size == ref['bytes'] and sha(path) == ref['sha256'],
            'bound_file_identity_mismatch')
    return path


def bound_json(ref):
    return json.loads(verify_ref(ref).read_bytes())


def load_helper(ref):
    path = verify_ref(ref)
    spec = importlib.util.spec_from_file_location('pilot6_unchanged_intake_helper', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_exclusions(flags, selection):
    rows = flags['accounts']
    require(len({r['account_key'] for r in rows}) == len(rows), 'duplicate_exposure_identity')
    for row in rows:
        require(isinstance(row['account_key'], str) and row['account_key']
                and row['account_key'] == row['account_key'].casefold(), 'noncanonical_exposure_identity')
        require(all(type(row[k]) is bool for k in FLAG_FIELDS), 'nonboolean_exposure_flag')
    mandatory = {r['account_key'] for r in rows if r[FLAG_FIELDS[0]]}
    scored3 = {r['account_key'] for r in rows if r[FLAG_FIELDS[1]]}
    selected = selection['selected']
    require(all(isinstance(selected[k], str) and selected[k] for k in ('account_a', 'account_b')),
            'missing_pilot5_identity')
    scored5 = {selected[k].casefold() for k in ('account_a', 'account_b')}
    require(len(mandatory) == 57 and len(scored3) == 60 and not mandatory & scored3,
            'prior_57_plus_60_not_established')
    require(len(scored5) == 2 and not scored5 & (mandatory | scored3), 'pilot5_two_new_identities_not_established')
    return mandatory | scored3 | scored5, {r['account_key'] for r in rows if r[FLAG_FIELDS[2]]}


def derive_memberships(frame_rows, excluded, pairs, minimum=40, check=lambda: None):
    """Return all old, permitted target and missing membership sets; no pairs of people."""
    require(pairs == PAIRS and minimum == 40, 'supplement_pair_or_prefilter_changed')
    communities = {c for pair in pairs for c in pair}
    seen, old, wanted = set(), set(), set()
    counts, per_pair = Counter(), Counter()
    for row in frame_rows:
        counts['frame_rows'] += 1
        if counts['frame_rows'] % 10000 == 0:
            check()
        require(set(row) == {'account_key', 'capacity_only_exposure', 'preprocess_communities',
                             'present_timestamped_comment_counts'}, 'unexpected_frame_schema')
        account = row['account_key']
        require(isinstance(account, str) and account and account == account.casefold()
                and account not in seen, 'invalid_or_duplicate_frame_identity')
        seen.add(account)
        values = row['present_timestamped_comment_counts']
        previous = row['preprocess_communities']
        require(isinstance(values, dict) and set(values) <= communities and
                all(type(v) is int and v >= 0 for v in values.values()), 'invalid_frame_counts')
        require(isinstance(previous, list) and len(set(previous)) == len(previous)
                and set(previous) <= set(values), 'invalid_old_memberships')
        expected_previous = {c for x, y in pairs
                             if values.get(x, 0) >= 80 and values.get(y, 0) >= 80 for c in (x, y)}
        require(set(previous) == expected_previous, 'old_80_comment_membership_mismatch')
        require(type(row['capacity_only_exposure']) is bool, 'invalid_frame_exposure_flag')
        old.update((account, c) for c in previous)
        if account in excluded:
            counts['excluded_frame_accounts'] += 1
            continue
        for x, y in pairs:
            if values.get(x, 0) >= minimum and values.get(y, 0) >= minimum:
                wanted.update(((account, x), (account, y)))
                per_pair[x + ' / ' + y] += 1
    check()
    missing = wanted - old
    return {'old': old, 'wanted': wanted, 'missing': missing,
            'summary': {**dict(counts), 'target_accounts': len({a for a, c in wanted}),
                        'target_memberships': len(wanted), 'old_memberships': len(old),
                        'reused_target_memberships': len(wanted & old),
                        'supplement_memberships': len(missing),
                        'supplement_accounts': len({a for a, c in missing}),
                        'target_accounts_by_community_pair': dict(per_pair)}}


class Budget:
    def __init__(self, limits):
        require(set(limits) == set(HARD_LIMITS), 'unexpected_resource_limit_schema')
        require(all(type(v) is int and 0 < v <= HARD_LIMITS[k] for k, v in limits.items()),
                'resource_limit_exceeds_registered_ceiling')
        self.limits = limits
        self.started = time.monotonic()
        self.rows = self.calls = self.metadata_bytes = self.private_bytes = 0

    def check(self):
        if time.monotonic() - self.started > self.limits['max_wall_seconds']:
            raise TimeoutError('supplement_wall_limit')

    def row(self):
        if self.rows >= self.limits['max_source_rows_per_pass']:
            raise RuntimeError('supplement_source_row_limit')
        self.rows += 1
        if self.rows % 10000 == 0:
            self.check()

    def call(self):
        self.check()
        if self.calls >= self.limits['max_preprocessed_records']:
            raise RuntimeError('supplement_preprocessing_limit')
        self.calls += 1

    def write_private(self, handle, data, metadata=False):
        self.check()
        if self.private_bytes + len(data) > self.limits['max_private_output_bytes']:
            raise RuntimeError('supplement_private_byte_limit')
        if metadata and self.metadata_bytes + len(data) > self.limits['max_eligibility_output_bytes']:
            raise RuntimeError('supplement_metadata_byte_limit')
        handle.write(data)
        self.private_bytes += len(data)
        if metadata:
            self.metadata_bytes += len(data)


def verify_existing_rows(path, old_memberships, missing, expected_rows, check=lambda: None):
    count = 0
    ids = set()
    with Path(path).open('rb') as handle:
        for line in handle:
            row = json.loads(line)
            require(set(row) == OLD_ROW_FIELDS, 'unexpected_existing_metadata_schema')
            membership = (row['account_key'], row['community'])
            require(membership in old_memberships and membership not in missing,
                    'existing_metadata_membership_mismatch')
            require(isinstance(row['record_id'], str) and row['record_id'] and row['record_id'] not in ids,
                    'duplicate_or_missing_existing_record_id')
            ids.add(row['record_id'])
            count += 1
            require(count <= expected_rows, 'existing_metadata_row_count_mismatch')
            if count % 10000 == 0:
                check()
    require(count == expected_rows, 'existing_metadata_row_count_mismatch')
    check()
    return count


def process_archive(source, helper, excluded, memberships, config, preprocessing,
                    budget, all_comment_ids, metadata_handle):
    """One utterance pass with global comment uniqueness; no submission preprocessing."""
    path = verify_ref(source)
    counts, eligibility, rejections = Counter(), Counter(), Counter()
    digest = hashlib.sha256()
    with zipfile.ZipFile(path) as archive:
        members = [i for i in archive.infolist() if i.filename == 'utterances.jsonl']
        require(len(members) == 1 and members[0].file_size == source['utterances_bytes'],
                'utterances_member_mismatch')
        with archive.open(members[0]) as handle:
            for line in handle:
                budget.row()
                digest.update(line)
                counts['source_rows'] += 1
                require(counts['source_rows'] <= source['source_rows'], 'archive_row_count_mismatch')
                raw = json.loads(line)
                rid = raw.get('id')
                require(isinstance(rid, str) and rid, 'missing_original_record_id')
                require((raw.get('meta') or {}).get('subreddit') == source['community'],
                        'unexpected_source_community')
                if raw.get('root') == rid:
                    counts['submission_rows_outside_comment_id_scope'] += 1
                    continue
                require(rid not in all_comment_ids, 'duplicate_original_comment_id')
                all_comment_ids.add(rid)
                counts['unique_comment_ids'] += 1
                account, instant, reason = helper.comment_metadata(raw, excluded)
                if reason is not None:
                    counts['metadata_rejected_' + reason] += 1
                    continue
                if (account, source['community']) not in memberships:
                    counts['outside_supplement_memberships'] += 1
                    continue
                _, _, reason = helper.present_comment(raw, excluded)
                if reason is not None:
                    rejections[reason] += 1
                    continue
                if len(raw['text']) > config['input']['max_text_codepoints']:
                    rejections['source_record_text_codepoint_limit'] += 1
                    continue
                budget.call()
                row, reason, calls = helper.preprocess_comment(raw, source['community'], excluded,
                                                              config, preprocessing)
                require(calls == 1 and row is not None, 'preprocessing_dispatch_mismatch')
                row['source_line_sha256'] = hashlib.sha256(line).hexdigest()
                require(set(row) == OLD_ROW_FIELDS, 'unexpected_supplement_metadata_schema')
                budget.write_private(metadata_handle, canonical(row), metadata=True)
                counts['eligibility_metadata_rows'] += 1
                if reason is not None:
                    rejections[reason] += 1
                else:
                    eligibility['frozen_eligible_records'] += 1
                    eligibility['frozen_eligible_words'] += row['retained_words']
                    if 20 <= row['retained_words'] <= 500:
                        eligibility['registered_record_bound_records'] += 1
                        eligibility['registered_record_bound_words'] += row['retained_words']
    require(counts['source_rows'] == source['source_rows'] and digest.hexdigest() == source['utterances_sha256'],
            'original_utterance_binding_mismatch')
    budget.check()
    return {'community': source['community'], 'archive_bytes': source['bytes'],
            'archive_sha256': source['sha256'], 'utterances_bytes': source['utterances_bytes'],
            'utterances_sha256': digest.hexdigest(), 'counts': dict(counts),
            'eligibility': dict(eligibility), 'rejections': dict(rejections)}


def write_public(path, value):
    with Path(path).open('xb') as handle:
        handle.write(canonical(value))


def run(plan_path, registration_path, out, private_out):
    plan = json.loads(Path(plan_path).read_bytes())
    budget = Budget(plan['limits'])
    require(os.environ.get('AHAS_NETWORK_ISOLATION') == 'linux_seccomp_socket_denial',
            'offline_runner_required')
    resource.setrlimit(resource.RLIMIT_AS, (budget.limits['max_address_space_bytes'],) * 2)
    out, private_out = Path(out), Path(private_out)
    require(out.resolve() != private_out.resolve() and out.resolve() not in private_out.resolve().parents
            and private_out.resolve() not in out.resolve().parents and not out.exists() and not private_out.exists(),
            'fresh_separate_destinations_required')
    out.mkdir(parents=True)
    private_out.mkdir(parents=True, mode=0o700)
    os.chmod(private_out, 0o700)
    started_utc = datetime.now(timezone.utc).isoformat()
    source_results = []
    try:
        registration = json.loads(Path(registration_path).read_bytes())
        require(registration['plan_sha256'] == sha(plan_path) and
                registration['implementation_sha256'] == sha(__file__), 'supplement_registration_mismatch')
        require(registration['test_files'], 'bound_tests_required')
        for ref in registration['test_files']:
            verify_ref(ref)
        require(plan['community_pairs'] == PAIRS and plan['raw_present_comments_per_community_min'] == 40,
                'supplement_pair_or_prefilter_changed')
        helper = load_helper(plan['original_intake_helper'])
        old_plan = bound_json(plan['original_intake_plan'])
        old_summary = bound_json(plan['original_intake_summary'])
        require(plan['original_intake_helper']['sha256'] == old_summary['implementation_sha256'] and
                plan['original_intake_plan']['sha256'] == old_summary['plan_sha256'],
                'original_implementation_or_plan_binding_mismatch')
        require(old_plan['community_pairs'] == PAIRS and old_plan['raw_present_comments_per_community_min'] == 80
                and old_plan['record_word_min'] == 20 and old_plan['record_word_max'] == 500,
                'original_intake_plan_mismatch')
        require(old_summary['status'] == 'completed_score_free_archive_intake', 'original_intake_incomplete')
        flags = bound_json(plan['exposure_flags'])
        selection = bound_json(plan['pilot5_selection'])
        excluded, capacity_only = load_exclusions(flags, selection)
        frame = verify_ref(plan['account_frame'])
        existing = verify_ref(plan['existing_eligibility'])
        require(plan['existing_eligibility']['sha256'] == old_summary['eligibility_metadata_sha256']
                and plan['existing_eligibility']['bytes'] == old_summary['eligibility_metadata_bytes'],
                'existing_intake_summary_binding_mismatch')
        prior_sources = {s['community']: s for s in old_summary['source_bindings']}
        require(len(plan['sources']) == 4 and {s['community'] for s in plan['sources']} ==
                {c for pair in PAIRS for c in pair}, 'technical_source_set_mismatch')
        for s in plan['sources']:
            old = prior_sources[s['community']]
            require(all(s[k] == old[v] for k, v in [('bytes', 'archive_bytes'), ('sha256', 'archive_sha256'),
                    ('utterances_bytes', 'utterances_bytes'), ('utterances_sha256', 'utterances_sha256')])
                    and s['source_rows'] == old['counts']['rows'], 'original_source_binding_mismatch')
        require(sum(s['utterances_bytes'] for s in plan['sources']) <=
                budget.limits['max_source_uncompressed_bytes_per_pass'], 'declared_uncompressed_limit')
        require(sum(s['source_rows'] for s in plan['sources']) <= budget.limits['max_source_rows_per_pass'],
                'declared_source_row_limit')
        config, preprocessing, engine = helper.load_engine(old_plan)
        write_public(out / 'start-binding.json', {
            'phase': 'before_membership_derivation_and_archive_scan', 'utc': started_utc,
            'plan_sha256': sha(plan_path), 'registration_sha256': sha(registration_path),
            'implementation_sha256': sha(__file__), 'original_intake_helper_sha256': plan['original_intake_helper']['sha256'],
            'source_metadata_hashes': {k: plan[k]['sha256'] for k in ['account_frame', 'existing_eligibility',
                'exposure_flags', 'pilot5_selection', 'original_intake_plan', 'original_intake_summary']},
            'excluded_accounts': 119, 'limits': budget.limits, 'engine': engine,
            'style_distance_calls': 0, 'cohort_selected': False})
        with frame.open('rb') as handle:
            sets = derive_memberships((json.loads(line) for line in handle), excluded, PAIRS, check=budget.check)
        old_rows = verify_existing_rows(existing, sets['old'], sets['missing'],
                                       old_summary['counts']['eligibility_metadata_rows'], budget.check)
        memberships = [{'account_key': a, 'community': c} for a, c in sorted(sets['missing'])]
        with (private_out / 'supplement-memberships.json').open('xb') as handle:
            os.chmod(handle.name, 0o600)
            budget.write_private(handle, canonical({'memberships': memberships}))
        write_public(out / 'membership-summary.json', {
            **sets['summary'], 'existing_metadata_rows_verified': old_rows,
            'excluded_accounts': 119, 'raw_comments_per_community_minimum': 40,
            'supplement_capacity_only_accounts': len({a for a, c in sets['missing']} & capacity_only),
            'member_overlap_with_old': len(sets['missing'] & sets['old']),
            'style_distance_calls': 0, 'calendar_capacity_evaluated': False})
        all_comment_ids = set()
        with (private_out / 'record-eligibility.jsonl').open('xb') as handle:
            os.chmod(handle.name, 0o600)
            for source in plan['sources']:
                result = process_archive(source, helper, excluded, sets['missing'], config, preprocessing,
                                         budget, all_comment_ids, handle)
                source_results.append(result)
                print(json.dumps({'phase': 'supplement_archive_complete', 'community': source['community'],
                                  'source_rows': result['counts']['source_rows'],
                                  'preprocessing_calls': budget.calls}), flush=True)
        budget.check()
        require(sum(s['counts'].get('eligibility_metadata_rows', 0) for s in source_results) == budget.calls,
                'supplement_call_row_count_mismatch')
        for name in ('account_frame', 'existing_eligibility', 'exposure_flags', 'pilot5_selection',
                     'original_intake_helper', 'original_intake_plan', 'original_intake_summary'):
            verify_ref(plan[name])
        require(registration['plan_sha256'] == sha(plan_path) and registration['implementation_sha256'] == sha(__file__),
                'registration_changed_during_intake')
        budget.check()
        result = {'status': 'completed_score_free_supplement', 'source_passes': 1,
                  'plan_sha256': sha(plan_path), 'registration_sha256': sha(registration_path),
                  'implementation_sha256': sha(__file__), 'started_utc': started_utc,
                  'finished_utc': datetime.now(timezone.utc).isoformat(),
                  'wall_seconds': time.monotonic() - budget.started,
                  'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                  'source_rows': budget.rows, 'preprocessing_calls': budget.calls,
                  'existing_metadata_rows': old_rows, 'excluded_accounts': 119,
                  'eligibility_metadata_bytes': budget.metadata_bytes,
                  'eligibility_metadata_sha256': sha(private_out / 'record-eligibility.jsonl'),
                  'private_output_bytes': budget.private_bytes, 'sources': source_results,
                  'membership_summary': sets['summary'], 'limits': budget.limits,
                  'style_distance_calls': 0, 'calendar_capacity_evaluated': False, 'cohort_selected': False,
                  'source_prose_displayed': False,
                  'combined_use': 'Apply all119 exclusions again to every old and supplement metadata input. '
                    'Supplement memberships are disjoint from old preprocessed memberships. '
                    'No eligible comments are silently truncated; above500-word rows remain metadata for the unchanged downstream gate.'}
        write_public(out / 'intake-summary.json', result)
        return 0
    except Exception as exc:
        write_public(out / 'incomplete-intake.json', {
            'status': 'incomplete_not_zero_capacity', 'error_type': type(exc).__name__,
            'source_rows': budget.rows, 'preprocessing_calls': budget.calls,
            'eligibility_metadata_bytes': budget.metadata_bytes, 'private_output_bytes': budget.private_bytes,
            'finished_utc': datetime.now(timezone.utc).isoformat(),
            'completed_source_count': len(source_results), 'style_distance_calls': 0,
            'calendar_capacity_evaluated': False, 'cohort_selected': False})
        return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('plan', 'registration', 'out', 'private-out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        return run(args.plan, args.registration, args.out, args.private_out)
    except Exception as exc:
        print(json.dumps({'status': 'preflight_failed', 'error_type': type(exc).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
