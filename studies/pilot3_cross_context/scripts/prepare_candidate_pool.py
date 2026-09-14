#!/usr/bin/env python3
"""Prepare a bounded private candidate audit pool after Gate A, never score it.

This runner needs a separately frozen JSON plan. Source lines are preserved
verbatim in private provenance; AHAS records preserve all supplied text/metadata.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import time
import zipfile

from account_history_analyzer.schemas import validate
from cohort_selection import candidate_prefix, hash_quota_allocation, utc_seconds


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                       allow_nan=False) + '\n').encode()


def write(path, value, private=False):
    with path.open('xb') as f:
        f.write(canonical(value))
    if private:
        path.chmod(0o600)


def convert_source(row, expected):
    """Convert one verified present source comment without rewriting its body."""
    timestamp = datetime.fromtimestamp(row['timestamp'], timezone.utc).isoformat().replace('+00:00', 'Z')
    if (row['id'] != expected['record_id'] or row['user'].casefold() != expected['account_key']
            or row['meta']['subreddit'] != expected['community'] or timestamp != expected['created_utc']
            or row.get('root') == row['id'] or not isinstance(row.get('text'), str)
            or row['text'].strip() in {'[deleted]', '[removed]'}):
        raise ValueError('Source identity, date, kind, community or status differs from census')
    record = {'schema_version': '1.0.0', 'id': row['id'], 'account_id': row['user'],
              'kind': 'comment', 'text': row['text'], 'status': 'present', 'created_utc': timestamp,
              'subreddit': row['meta']['subreddit'], 'language': None, 'edit_state': 'unknown',
              'edited_utc': None, 'title': None, 'parent_id': row.get('reply_to'),
              'thread_id': row.get('root'), 'parent_created_utc': None,
              'permalink': row['meta'].get('permalink')}
    validate(record, 'record')
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--private-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('AHAS_NETWORK_ISOLATION') != 'linux_seccomp_socket_denial':
        raise RuntimeError('Run through the existing offline runner')
    started = time.monotonic()
    resource.setrlimit(resource.RLIMIT_AS, (4294967296,) * 2)
    plan = json.loads(args.plan.read_text())
    if plan['phase'] != 'registered_score_free_candidate_pool' or plan['full_target'] != {'accounts': 60, 'blocks': 30, 'strata': 3}:
        raise ValueError('Explicit full-study candidate preparation plan required')
    limits = plan['limits']
    if limits != {'candidate_account_cap_per_stratum': 40, 'candidate_records': 100000,
                  'candidate_retained_words': 2000000, 'candidate_bytes': 268435456,
                  'source_rows': 6000000, 'source_uncompressed_bytes': 3000000000,
                  'wall_seconds': 1800, 'address_space_bytes': 4294967296}:
        raise ValueError('Candidate preparation requires the declared bounded limits')
    mandatory_bindings = {str(Path(p).resolve()) for p in (
        [plan['exclusion_manifest'], plan['gate_a_report'], __file__,
         Path(__file__).with_name('cohort_selection.py'), Path(__file__).with_name('study_math.py')]
        + plan['eligibility_metadata'] + [s['capacity_file'] for s in plan['strata']])}
    supplied_bindings = {str(Path(a['path']).resolve()) for a in plan['bound_artifacts']}
    if (len(supplied_bindings) != len(plan['bound_artifacts'])
            or not mandatory_bindings <= supplied_bindings):
        raise ValueError('Every consumed metadata, capacity, exclusion, gate and helper file must be uniquely hash-bound')
    for artifact in plan['bound_artifacts']:
        if sha(artifact['path']) != artifact['sha256']:
            raise ValueError('Registered candidate preparation dependency changed')
    if len(plan['strata']) != 3 or len({s['id'] for s in plan['strata']}) != 3:
        raise ValueError('Exactly three distinct fixed strata required')
    gate = json.loads(Path(plan['gate_a_report']).read_text())
    if (gate['gate_a_status'] != 'capacity_pass_requires_contamination_audit'
            or gate['disjoint_capacity']['total_accounts'] != 60
            or gate['disjoint_capacity']['total_blocks'] != 30
            or set(gate['selected_pair_strata']) != {s['id'] for s in plan['strata']}):
        raise ValueError('Verified full Gate A capacity passage required before candidate assembly')
    for s in plan['strata']:
        if len(s['communities']) != 2 or len(set(s['communities'])) != 2 or ' / '.join(sorted(s['communities'])) != s['id']:
            raise ValueError('Each stratum requires its two distinct declared source communities')
        if gate['pair_capacities'][s['id']]['chosen_calendar_scheme'] != s['scheme']:
            raise ValueError('Candidate dates must exactly match the passed Gate A calendar scheme')
    args.out.mkdir(exist_ok=False, parents=True)
    private = args.private_root / args.out.name
    private.mkdir(exist_ok=False, mode=0o700)
    write(args.out / 'start-binding.json', {
        'phase': 'before_candidate_assembly', 'plan_sha256': sha(args.plan),
        'script_sha256': sha(__file__), 'helper_sha256': sha(Path(__file__).with_name('cohort_selection.py')),
        'utc': datetime.now(timezone.utc).isoformat(), 'style_scores_computed': 0})
    excluded = {r['account_key'] for r in json.loads(Path(plan['exclusion_manifest']).read_text())['accounts']}
    eligible = {}
    for stratum in plan['strata']:
        doc = json.loads(Path(stratum['capacity_file']).read_text())
        accounts = set(doc['pairs'][stratum['id']]['accounts'])
        if accounts & excluded:
            raise ValueError('Historical excluded identity in capacity input')
        if doc['pairs'][stratum['id']]['scheme'] != stratum['scheme']:
            raise ValueError('Fixed period scheme changed')
        eligible[stratum['id']] = accounts
    allocation = hash_quota_allocation(eligible, 40)
    if any(n < 20 for n in allocation['quota_counts'].values()):
        raise ValueError('Candidate pool cannot preserve every 20-account final quota')
    assignments = {a: s for s, accounts in allocation['assigned'].items() for a in accounts}
    by_stratum = {s['id']: s for s in plan['strata']}
    cells, metadata_seen = defaultdict(list), set()
    metadata_rows = 0
    for source in plan['eligibility_metadata']:
        with Path(source).open() as f:
            for line in f:
                metadata_rows += 1
                if metadata_rows > 1200000 or time.monotonic() - started > 1800:
                    raise RuntimeError('Candidate metadata/time bound exhausted')
                row = json.loads(line)
                if row['reason'] is not None or row['account_key'] not in assignments:
                    continue
                stratum = by_stratum[assignments[row['account_key']]]
                if row['community'] not in stratum['communities']:
                    continue
                part = next((part for part in ('early', 'late') if
                    utc_seconds(stratum['scheme'][part][0]) <= utc_seconds(row['created_utc'])
                    < utc_seconds(stratum['scheme'][part][1])), None)
                if part is None:
                    continue
                if row['record_id'] in metadata_seen:
                    raise ValueError('Duplicated candidate source identity in census metadata')
                metadata_seen.add(row['record_id'])
                cells[stratum['id'], row['account_key'], row['community'], part].append(row)
    selected = {}
    cell_counts = []
    for s in plan['strata']:
        for account in allocation['assigned'][s['id']]:
            for community in s['communities']:
                for part in ('early', 'late'):
                    key = s['id'], account, community, part
                    chosen = candidate_prefix(cells.get(key, []), s['scheme'][part])
                    for row in chosen:
                        selected[row['record_id']] = {**row, 'stratum_id': s['id'], 'period': part}
                    cell_counts.append({'stratum_id': s['id'], 'account_key': account,
                                        'community': community, 'period': part, 'records': len(chosen),
                                        'retained_words': sum(r['retained_words'] for r in chosen)})
    total_words = sum(r['retained_words'] for r in selected.values())
    if len(selected) > 100000 or total_words > 2000000:
        raise RuntimeError('Whole-record audit pool exceeds declared record/word bound; no trimming')
    write(private / 'candidate-selection.json', {
        'allocation': allocation, 'considered_accounts_by_stratum': {s: sorted(a) for s, a in eligible.items()},
        'cells': cell_counts, 'selected_record_metadata': selected}, True)
    seen, source_rows, source_bytes, written = set(), 0, 0, 0
    source_receipts = []
    with (private / 'candidate-pool.jsonl').open('xb') as pool, (private / 'original-source-lines.jsonl').open('xb') as provenance:
        for src in plan['sources']:
            archive = Path(src['archive'])
            if sha(archive) != src['sha256']:
                raise ValueError('Source archive identity changed')
            count, member_hash = 0, hashlib.sha256()
            with zipfile.ZipFile(archive) as z:
                member = z.getinfo('utterances.jsonl')
                source_bytes += member.file_size
                if source_bytes > 3000000000:
                    raise RuntimeError('Source decompression bound exhausted')
                with z.open(member) as f:
                    for line in f:
                        source_rows += 1
                        count += 1
                        member_hash.update(line)
                        if source_rows > 6000000 or time.monotonic() - started > 1800:
                            raise RuntimeError('Source row/time bound exhausted')
                        row = json.loads(line)
                        if row['id'] not in selected:
                            continue
                        expected = selected[row['id']]
                        if row['id'] in seen or hashlib.sha256(line).hexdigest() != expected['source_line_sha256']:
                            raise ValueError('Repeated or changed original source record')
                        seen.add(row['id'])
                        record = convert_source(row, expected)
                        entry = {k: expected[k] for k in ('account_key', 'community', 'period', 'stratum_id', 'retained_words')}
                        entry['record'] = record
                        raw = canonical(entry)
                        written += len(raw)
                        if written > 268435456:
                            raise RuntimeError('Candidate byte limit exhausted; preserve partial output')
                        pool.write(raw)
                        provenance.write(line)
            source_receipts.append({'community': src['community'], 'source_rows': count,
                                    'utterances_sha256': member_hash.hexdigest()})
            if count != src['source_records'] or member_hash.hexdigest() != src['utterances_sha256']:
                raise ValueError('Original source stream differs from completed census')
    for path in private.iterdir():
        path.chmod(0o600)
    if seen != set(selected):
        raise ValueError('Some planned original source records were not found')
    counts = Counter(r['stratum_id'] for r in selected.values())
    write(args.out / 'private-artifact-hashes.json', {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size}
                                                    for p in private.iterdir()})
    if time.monotonic() - started > 1800:
        raise RuntimeError('Candidate finalization time bound exhausted; no successful preparation receipt')
    write(args.out / 'preparation.json', {
        'status': 'candidate_pool_prepared_not_audited_or_scored',
        'candidate_account_quotas': allocation['quota_counts'], 'candidate_records': len(seen),
        'records_by_stratum': dict(counts), 'candidate_retained_words': total_words,
        'metadata_rows_read': metadata_rows, 'source_passes': 1, 'source_rows': source_rows,
        'source_uncompressed_bytes': source_bytes, 'candidate_pool_bytes': written,
        'candidate_cells': len(cell_counts), 'source_receipts': source_receipts,
        'new_preprocessing_calls': 0, 'style_scores_computed': 0, 'final_cohort_frozen': False,
        'wall_seconds': time.monotonic() - started,
        'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        'privacy': 'All original source records and identities remain private'})
    print(json.dumps({'status': 'candidate_pool_prepared', 'accounts': len(assignments),
                      'records': len(seen), 'retained_words': total_words, 'scores': 0}))


if __name__ == '__main__':
    main()
