#!/usr/bin/env python3
"""Bounded, score-free single-pair intake. This cannot pass the full study gate.

Pass one counts source records and constructs an exhaustive necessary-count
prefilter. Pass two uses only the frozen preprocessor on those accounts.
All account/record identities remain in the separately supplied private root.
Original census.py is preserved. Source scanning, frozen preprocessing, metadata
exclusions and operational limit enforcement retain its implementation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path
import resource
import sys
import time
import zipfile

from account_history_analyzer import AnalysisConfig
from account_history_analyzer.io import digest
from account_history_analyzer.pipeline import implementation_identity
from account_history_analyzer.text import preprocess

PLACEHOLDERS = {'', 'anonymous', '[anonymous]', 'unknown', '[unknown]',
                '[deleted]', '[removed]', '[missing]', 'automoderator'}
MANIFEST = {'default_language': 'en', 'text_format': 'markdown'}


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False,
                       separators=(',', ':'), allow_nan=False) + '\n').encode()


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write(path, obj, private=False):
    path = Path(path)
    with path.open('xb') as f:
        f.write(canonical(obj))
    if private:
        path.chmod(0o600)


def stamp(value):
    if type(value) is not int:
        return None
    try:
        return datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z')
    except (ValueError, OverflowError, OSError):
        return None


def period(instant, scheme):
    if instant is None:
        return None
    day = instant[:10]
    return next((p for p in ('early', 'late') if scheme[p][0] <= day < scheme[p][1]), None)


def necessary_accounts(frame, minimum=16):
    """No account can supply two eight-record cells without this condition."""
    return {a for a, communities in frame.items()
            if sum(v['present_timestamped_comments'] >= minimum for v in communities.values()) >= 2}


def capacities(eligible, pairs, schemes, words=2000, records=8):
    # eligible rows are metadata only: account_key, community, timestamp, words.
    totals = defaultdict(lambda: [0, 0])
    cells = defaultdict(lambda: [0, 0])
    for row in eligible:
        key = (row['account_key'], row['community'])
        totals[key][0] += 1
        totals[key][1] += row['retained_words']
        for scheme in schemes:
            p = period(row['created_utc'], scheme)
            if p:
                cells[(scheme['id'], *key, p)][0] += 1
                cells[(scheme['id'], *key, p)][1] += row['retained_words']
    accounts = sorted({a for a, _ in totals})
    upper, qualified, table = {}, {}, []
    for x, y in pairs:
        name = x + ' / ' + y
        upper[name] = {a for a in accounts if all(totals[a, c][0] >= 2*records
                      and totals[a, c][1] >= 2*words for c in (x, y))}
        for scheme in schemes:
            ok = {a for a in accounts if all(cells[scheme['id'], a, c, p][0] >= records
                  and cells[scheme['id'], a, c, p][1] >= words
                  for c in (x, y) for p in ('early', 'late'))}
            qualified[name, scheme['id']] = ok
            table.append({'community_pair': name, 'period_scheme': scheme['id'],
                          'four_cell_accounts': len(ok), 'pairwise_blocks_upper_bound': len(ok)//2})
    # Avoid defaultdict read-side zero insertion in exported private cell table.
    nonempty = [{'period_scheme': s, 'account_key': a, 'community': c, 'period': p,
                 'eligible_records': counts[0], 'eligible_words': counts[1]}
                for (s, a, c, p), counts in sorted(cells.items()) if counts[0]]
    return upper, qualified, table, nonempty


def choose_schemes(qualified, pairs, schemes):
    def duration(s, p):
        return (datetime.fromisoformat(s[p][1])-datetime.fromisoformat(s[p][0])).days
    result = {}
    for x, y in pairs:
        name = x + ' / ' + y
        chosen = min(schemes, key=lambda s: (-len(qualified[name, s['id']]),
                     (duration(s, 'early')-duration(s, 'late'))**2, s['id']))
        result[name] = chosen
    return result


def validate_pair_intake_plan(plan):
    """Require the explicitly authorized 20-account/10-block single-pair target."""
    target = plan['target']
    required = {'accounts': 20, 'blocks': 10, 'strata': 1,
                'accounts_per_stratum': 20, 'blocks_per_stratum': 10,
                'words_per_cell': 2000, 'eligible_records_per_cell': 8}
    if any(type(target.get(key)) is not int or target[key] != value for key, value in required.items()):
        raise ValueError('Pair intake requires one 20-account/10-block stratum and unchanged 2000-word/eight-record cells')
    sources = [source['community'] for source in plan['sources']]
    pairs = plan['community_pairs']
    if (len(sources) != 2 or len(set(sources)) != 2 or len(pairs) != 1
            or len(pairs[0]) != 2 or set(pairs[0]) != set(sources)):
        raise ValueError('Pair intake requires exactly two distinct declared sources and their one pair')
    return target


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan', type=Path, required=True)
    ap.add_argument('--source-root', type=Path, required=True)
    ap.add_argument('--private-root', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    if os.environ.get('AHAS_NETWORK_ISOLATION') != 'linux_seccomp_socket_denial':
        raise RuntimeError('Run through the frozen offline runner')
    started = time.monotonic()
    plan = json.loads(args.plan.read_bytes())
    target = validate_pair_intake_plan(plan)
    config = AnalysisConfig.from_toml()
    fp, env, resources = implementation_identity()
    if fp != plan['implementation_fingerprint'] or digest(config.analytical()) != plan['analysis_config_sha256']:
        raise ValueError('Frozen installed implementation/config mismatch')
    limits = plan['limits']
    resource.setrlimit(resource.RLIMIT_AS, (limits['max_address_space_bytes'],)*2)
    private = args.private_root
    private.mkdir(mode=0o700, parents=True, exist_ok=True)
    exclusion_path = private/'exclusions-mandatory.json'
    exclusion_doc = json.loads(exclusion_path.read_bytes())
    excluded = {r['account_key'].casefold(): r['reasons'] for r in exclusion_doc['accounts']}
    if not exclusion_doc.get('complete_for_known_pilot_sources'):
        raise ValueError('Exclusion manifest completeness not established')
    args.out.mkdir(parents=True, exist_ok=False)
    private_run = private/args.out.name
    private_run.mkdir(mode=0o700, exist_ok=False)
    initial = {'phase': 'before_source_scan', 'utc': datetime.now(timezone.utc).isoformat(),
               'plan_sha256': sha(args.plan), 'script_sha256': sha(__file__),
               'exclusions_sha256': sha(exclusion_path), 'implementation_fingerprint': fp,
               'analysis_config_sha256': digest(config.analytical()), 'reference_environment': env,
               'resource_hashes': resources, 'scores_computed': False}
    write(args.out/'start-binding.json', initial)

    def check_limits(rows, processed=0):
        if rows > limits['max_source_rows_per_pass'] or processed > limits['max_preprocessed_records']:
            raise RuntimeError('Predeclared record/preprocessing budget exhausted; census incomplete')
        if time.monotonic()-started > limits['max_wall_seconds']:
            raise RuntimeError('Predeclared wall-time budget exhausted; census incomplete')
        private_bytes = sum(p.stat().st_size for p in private_run.iterdir() if p.is_file())
        if private_bytes > limits['max_private_output_bytes']:
            raise RuntimeError('Predeclared private output budget exhausted; census incomplete')

    frame = defaultdict(lambda: defaultdict(Counter))
    sources = []
    ids = set()
    all_accounts = set()
    exclusions_seen = defaultdict(set)
    counts_total = Counter()
    rawbytes = 0
    for src in plan['sources']:
        path = args.source_root/src['archive']
        if path.stat().st_size != src['bytes'] or sha(path) != src['sha256']:
            raise ValueError('Archive identity mismatch: '+src['community'])
        counts, years, fields, community_counts = Counter(), Counter(), Counter(), Counter()
        archive_accounts = set()
        first, last = None, None
        utterance_hash = hashlib.sha256()
        with zipfile.ZipFile(path) as z:
            entries = [v for v in z.infolist() if v.filename == 'utterances.jsonl']
            if len(entries) != 1:
                raise ValueError('Expected exactly one utterances.jsonl member')
            rawbytes += entries[0].file_size
            if rawbytes > limits['max_source_uncompressed_bytes_per_pass']:
                raise RuntimeError('Predeclared uncompressed source budget exhausted')
            with z.open(entries[0]) as f:
                for line in f:
                    utterance_hash.update(line)
                    r = json.loads(line)
                    counts['source_records'] += 1
                    counts_total['source_records'] += 1
                    if counts_total['source_records'] % 10000 == 0:
                        check_limits(counts_total['source_records'])
                    rid = r.get('id')
                    if not isinstance(rid, str) or not rid:
                        raise ValueError('Missing source ID')
                    if rid in ids:
                        raise ValueError('Duplicate source ID; no silent deduplication')
                    ids.add(rid)
                    fields.update(r.keys())
                    meta = r.get('meta') or {}
                    community_counts[str(meta.get('subreddit'))] += 1
                    if meta.get('subreddit') != src['community']:
                        raise ValueError('Unexpected source community')
                    counts['missing_thread'] += not r.get('root')
                    counts['missing_parent'] += r.get('reply_to') is None
                    counts['explicit_language_missing'] += 'language' not in r and 'language' not in meta
                    counts['explicit_edit_history_missing'] += 'edit_state' not in r and 'edit_state' not in meta
                    is_comment = r.get('root') != rid
                    counts['comments' if is_comment else 'submissions'] += 1
                    account = r.get('user')
                    if not isinstance(account, str):
                        counts['missing_account'] += 1
                        continue
                    account = account.casefold()
                    all_accounts.add(account)
                    archive_accounts.add(account)
                    if account.strip() in PLACEHOLDERS:
                        counts['excluded_placeholder_records'] += 1
                        continue
                    if account in excluded:
                        counts['excluded_prior_or_private_records'] += 1
                        for reason in excluded[account]:
                            exclusions_seen[reason].add(account)
                            counts['excluded_records_'+reason] += 1
                        # Do not access excluded writing, retained tokens or capacity.
                        continue
                    instant = stamp(r.get('timestamp'))
                    counts['nonexcluded_missing_timestamp'] += instant is None
                    if instant:
                        first = min(first, instant) if first else instant
                        last = max(last, instant) if last else instant
                        years[instant[:4]] += 1
                    if not is_comment:
                        continue
                    item = frame[account][src['community']]
                    item['comments'] += 1
                    body = r.get('text')
                    if not isinstance(body, str) or body.strip() in {'[removed]', '[deleted]'}:
                        counts['nonexcluded_unavailable_comments'] += 1
                        continue
                    item['present_comments'] += 1
                    if instant:
                        item['present_timestamped_comments'] += 1
        sources.append({**src, 'utterances_sha256': utterance_hash.hexdigest(),
                        'utterances_bytes': entries[0].file_size, 'counts': dict(counts),
                        'distinct_source_account_keys_including_excluded': len(archive_accounts),
                        'nonexcluded_first_utc': first, 'nonexcluded_last_utc': last,
                        'nonexcluded_calendar_year_counts': dict(years),
                        'top_level_field_presence': dict(fields), 'community_labels': dict(community_counts),
                        'duplicate_ids': 0})
        print(json.dumps({'phase': 'metadata', 'community': src['community'], 'rows': counts['source_records']}), flush=True)
    check_limits(counts_total['source_records'])
    del ids
    candidates = necessary_accounts(frame, 2*plan['target']['eligible_records_per_cell'])
    # Preserve private necessary-condition rejection reasons for every account.
    with (private_run/'account-frame.jsonl').open('xb') as f:
        for account, communities in sorted(frame.items()):
            f.write(canonical({'account_key': account, 'communities': dict(communities),
                               'preprocess': account in candidates,
                               'reason': None if account in candidates else 'fewer_than16_present_timestamped_comments_in_two_communities'}))
    (private_run/'account-frame.jsonl').chmod(0o600)
    metadata_summary = {'sources': sources, 'source_records': counts_total['source_records'],
                        'unique_record_ids': counts_total['source_records'],
                        'source_account_keys_including_placeholders': len(all_accounts),
                        'nonexcluded_comment_accounts': len(frame), 'preprocessing_candidate_accounts': len(candidates),
                        'source_pair_any_comment_account_overlaps': {
                            x+' / '+y: sum(x in comm and y in comm for comm in frame.values())
                            for x, y in plan['community_pairs']},
                        'source_pair_16_present_comment_account_overlaps': {
                            x+' / '+y: sum(comm.get(x,{}).get('present_timestamped_comments',0)>=16 and
                                          comm.get(y,{}).get('present_timestamped_comments',0)>=16 for comm in frame.values())
                            for x, y in plan['community_pairs']},
                        'excluded_known_account_counts_in_sources': {k:len(v) for k,v in sorted(exclusions_seen.items())},
                        'exclusion_manifest_reason_counts': exclusion_doc.get('reason_counts'),
                        'exclusion_unique_account_count': len(excluded),
                        'prior_capacity_only_exposed_accounts':len(exclusion_doc.get('prior_capacity_only_accounts', [])),
                        'scores_computed': False}
    write(args.out/'source-inventory.json', metadata_summary)
    del frame

    eligible, rejected, second_pass = [], Counter(), []
    processed, rows = 0, 0
    with (private_run/'record-eligibility.jsonl').open('xb') as log:
        for src in plan['sources']:
            member_hash, member_rows = hashlib.sha256(), 0
            with zipfile.ZipFile(args.source_root/src['archive']) as z, z.open('utterances.jsonl') as f:
                for line in f:
                    member_hash.update(line)
                    member_rows += 1
                    rows += 1
                    if rows % 10000 == 0:
                        check_limits(rows, processed)
                    r = json.loads(line)
                    account = r.get('user')
                    if not isinstance(account, str) or account.casefold() not in candidates:
                        continue
                    account = account.casefold()
                    if account in excluded:
                        raise AssertionError('Excluded account entered preprocessing')
                    rid = r['id']
                    if r.get('root') == rid:
                        rejected['candidate_submissions'] += 1
                        continue
                    instant = stamp(r.get('timestamp'))
                    body = r.get('text')
                    reason = None
                    words = None
                    if instant is None:
                        reason = 'missing_or_invalid_timestamp'
                    elif not isinstance(body, str) or body.strip() in {'[removed]', '[deleted]'}:
                        reason = 'unavailable_source_text'
                    elif len(body) > config['input']['max_text_codepoints']:
                        reason = 'source_record_text_codepoint_limit'
                    else:
                        processed += 1
                        check_limits(rows, processed)
                        converted = {'id':rid, 'kind':'comment', 'text':body, 'status':'present',
                                     'created_utc':instant, 'language':None, 'subreddit':src['community'],
                                     'edit_state':'unknown'}
                        view = preprocess(converted, MANIFEST, config)
                        words = sum(len(segment) for segment in view['word_tokens'])
                        if not view['usable'] or words < config['style']['minimum_record_words']:
                            reason = 'below_frozen_record_word_guard'
                    item = {'account_key':account, 'community':src['community'], 'record_id':rid,
                            'created_utc':instant, 'retained_words':words, 'reason':reason,
                            'source_line_sha256':hashlib.sha256(line).hexdigest()}
                    log.write(canonical(item))
                    if reason:
                        rejected[reason] += 1
                    else:
                        eligible.append(item)
            original = next(s for s in sources if s['community'] == src['community'])
            if member_hash.hexdigest() != original['utterances_sha256'] or member_rows != original['counts']['source_records']:
                raise ValueError('Archive utterances changed between passes')
            second_pass.append({'community':src['community'],'rows':member_rows,
                                'utterances_sha256':member_hash.hexdigest()})
            print(json.dumps({'phase':'preprocessing', 'community':src['community'],
                              'processed':processed, 'eligible':len(eligible)}), flush=True)
    (private_run/'record-eligibility.jsonl').chmod(0o600)
    check_limits(rows, processed)
    if rows != counts_total['source_records']:
        raise AssertionError('Source pass counts differ')
    upper, qualified, table, cells = capacities(eligible, plan['community_pairs'], plan['period_schemes'])
    chosen = choose_schemes(qualified, plan['community_pairs'], plan['period_schemes'])
    eligible_by_pair = {name:qualified[name,scheme['id']] for name,scheme in chosen.items()}
    from study_math import maximum_disjoint_capacity
    allocation = maximum_disjoint_capacity(eligible_by_pair, limit_per_stratum=target['accounts_per_stratum'])
    upper_allocation = maximum_disjoint_capacity(upper, limit_per_stratum=target['accounts_per_stratum'])
    capacity_exposed = {r['account_key'] for r in exclusion_doc.get('prior_capacity_only_accounts', [])}
    write(private_run/'cell-capacities.json', cells, True)
    write(private_run/'capacity-witness.json', {'chosen_period_schemes':chosen,
          'eligible_accounts_by_pair':{k:sorted(v) for k,v in eligible_by_pair.items()},
          'all_history_upper_bound_accounts_by_pair':{k:sorted(v) for k,v in upper.items()},
          'allocation':allocation, 'upper_bound_allocation':upper_allocation}, True)
    quota = allocation['quota_counts']
    gate_pass = all(quota.get(pair,0) == target['accounts_per_stratum'] for pair in eligible_by_pair)
    result = {'gate_a_status': 'pair_capacity_pass' if gate_pass else 'pair_capacity_failed',
              'study_scope':'single_pair_intake_only', 'scoring_permitted':False,
              'full_study_gate_status':'not_evaluated_by_single_pair_intake',
              'scores_computed':False, 'final_cohort_selected':False,
              'planned_accounts':target['accounts'], 'planned_blocks':target['blocks'],
              'words_per_cell':2000, 'records_per_cell':8, 'preprocessed_records':processed,
              'eligible_records':len(eligible), 'eligible_words':sum(r['retained_words'] for r in eligible),
              'record_rejections':dict(rejected), 'period_capacity_table':table,
              'proposed_period_schemes':chosen,
              'all_history_necessary_capacity':{k:{'accounts':len(v), 'blocks_upper_bound':len(v)//2} for k,v in upper.items()},
              'prior_capacity_inspection_dependence':{
                  k:{'four_cell_accounts':len(v),'with_prior_capacity_inspection':len(v & capacity_exposed),
                     'without_prior_capacity_inspection':len(v-capacity_exposed)} for k,v in eligible_by_pair.items()},
              'disjoint_capacity':{k:v for k,v in allocation.items() if k!='assigned'},
              'all_history_disjoint_upper_bound':{k:v for k,v in upper_allocation.items() if k!='assigned'},
              'leakage_audit_status':'not_run_at_pair_intake; counts precede contamination filtering',
              'archives_outside_original_three':sum(s['community'] not in {'Cornell','college','ApplyingToCollege'} for s in plan['sources']),
              'language':'English assumed at corpus level, not individually verified',
              'timing_scope':'Same proposed early and late periods for all four cells in each stratum; long periods do not ensure closely matched realized writing dates.'}
    write(args.out/'capacity.json', result)
    write(args.out/'second-pass-source-binding.json', second_pass)
    write(args.out/'private-artifact-hashes.json', {p.name:{'sha256':sha(p),'bytes':p.stat().st_size}
                                                  for p in sorted(private_run.iterdir())})
    write(args.out/'resources.json', {'wall_seconds':time.monotonic()-started,
          'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
          'source_passes':2,'source_rows_per_pass':rows,'preprocessed_records':processed,
          'public_output_bytes':sum(p.stat().st_size for p in args.out.iterdir()),
          'private_output_bytes':sum(p.stat().st_size for p in private_run.iterdir()),
          'limits':limits,'resource_outcome':'completed_within_predeclared_limits'})
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
