"""Evaluation-only Gate B wrapper. Real audits require a prior frozen binding.

Source prose stays in memory and existing private input files. The public result
contains aggregate counts only. This module never imports a distance method.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import itertools
import json
import os
from pathlib import Path
import resource
import signal
import time

ENGINE_SHA256 = 'f080682bc5beac251f9fb07404d0c9a9093aab04deff8d53997708d05dd01e92'
IMPLEMENTATION = 'bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179'
CONFIG_SHA256 = '8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925'
PAIR_CAP = 2_000_000
MAX_CANDIDATE_RECORDS = 100_000
MAX_CANDIDATE_WORDS = 2_000_000
MAX_CANDIDATE_BYTES = 256 * 1024**2
MAX_AS_BYTES = 4 * 1024**3
MAX_WALL_SECONDS = 1800
TITLE_PREFIX = '__ahas_pilot3_historical_title_v1__:'
VERSION = 'pilot3-gate-b-audit-draft-v1'


class AuditFailure(ValueError):
    """The code is public-safe; never put source values into it."""


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       allow_nan=False, separators=(',', ':')) + '\n').encode()


def file_sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def require(condition, code):
    if not condition:
        raise AuditFailure(code)


def load_engine(path):
    require(file_sha(path) == ENGINE_SHA256, 'frozen_audit_engine_hash_mismatch')
    spec = importlib.util.spec_from_file_location('_pilot3_frozen_leakage', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(module.PAIR_CAP == PAIR_CAP, 'frozen_audit_cap_mismatch')
    return module


def candidate_rows(entries):
    """Validate private wrappers; derive cells from source identity metadata."""
    entries = list(entries)
    require(len(entries) <= MAX_CANDIDATE_RECORDS, 'candidate_record_ceiling')
    rows, provenance, ids, account_strata = [], {}, set(), defaultdict(set)
    words = 0
    for entry in entries:
        record = entry['record']
        identifier, account = record.get('id'), entry.get('account_key')
        require(isinstance(identifier, str) and identifier and
                not identifier.startswith(TITLE_PREFIX), 'invalid_candidate_id')
        require(identifier not in ids, 'candidate_original_id_repeated')
        ids.add(identifier)
        require(isinstance(account, str) and account and account == account.casefold(),
                'invalid_candidate_source_account')
        stratum = entry.get('stratum_id')
        require(isinstance(stratum, str) and stratum, 'missing_candidate_stratum')
        account_strata[account].add(stratum)
        community, period = entry.get('community'), entry.get('period')
        require(isinstance(community, str) and community and community == record.get('subreddit'),
                'candidate_community_mismatch')
        require(period in ('early', 'late'), 'invalid_candidate_period')
        require(record.get('kind') == 'comment' and record.get('status') == 'present'
                and isinstance(record.get('text'), str), 'candidate_not_present_comment')
        require(len(record['text']) <= 200_000, 'candidate_body_codepoint_ceiling')
        require(record.get('language') in (None, 'en'), 'candidate_language_not_declared_english')
        require(isinstance(record.get('thread_id'), str) and record['thread_id'],
                'candidate_thread_missing')
        require(isinstance(record.get('created_utc'), str) and record['created_utc'],
                'candidate_timestamp_missing')
        retained = entry.get('retained_words')
        require(type(retained) is int and retained >= 20, 'candidate_record_word_guard')
        words += retained
        require(words <= MAX_CANDIDATE_WORDS, 'candidate_word_ceiling')
        rows.append({'id': identifier, 'text': record['text'], 'status': 'present',
                     'language': record.get('language'), 'account_key': account,
                     'split': 'evaluation'})
        provenance[identifier] = {'source_record_id': identifier, 'source_kind': 'comment',
            'text_component': 'body', 'historical': False, 'account_key': account,
            'stratum_id': stratum, 'cell': [account, community, period],
            'thread_id': record['thread_id'], 'declared_retained_words': retained}
    require(all(len(v) == 1 for v in account_strata.values()), 'candidate_account_crosses_strata')
    require(bool(rows), 'empty_candidate_pool')
    return rows, provenance


def historical_rows(entries):
    """Collapse identical original copies; retain separate exact title protection."""
    originals, references = {}, defaultdict(list)
    for entry in entries:
        record, account = entry['record'], entry['account_key'].casefold()
        identifier = record.get('id')
        require(isinstance(identifier, str) and identifier and
                not identifier.startswith(TITLE_PREFIX), 'invalid_historical_id')
        split = 'confirmation' if entry['original_split'] == 'confirmation' else 'development'
        signature = {'account_key': account, 'split': split, 'original_split': entry['original_split'],
            'original_record_sha256': hashlib.sha256(canonical(record)).hexdigest(),
            **{k: record.get(k) for k in
            ('text', 'title', 'status', 'kind', 'created_utc', 'subreddit', 'thread_id',
             'parent_id', 'language', 'edit_state', 'edited_utc')}}
        require(identifier not in originals or originals[identifier] == signature,
                'conflicting_historical_original_id')
        originals[identifier] = signature
        references[identifier].append(entry.get('source_id'))
    rows, provenance = [], {}
    for identifier, value in sorted(originals.items()):
        base = {'account_key': value['account_key'], 'split': value['split'],
                'language': value['language']}
        rows.append({**base, 'id': identifier, 'text': value['text'], 'status': value['status']})
        metadata = {'source_record_id': identifier, 'source_kind': value['kind'],
                    'historical': True, 'account_key': value['account_key'],
                    'audit_split': value['split'], 'original_split': value['original_split'],
                    'thread_id': value['thread_id'], 'original_references': references[identifier]}
        provenance[identifier] = {**metadata, 'text_component': 'body'}
        title = value['title']
        if value['kind'] == 'submission' and isinstance(title, str) and title:
            title_id = TITLE_PREFIX + hashlib.sha256(identifier.encode()).hexdigest()
            require(title_id not in provenance, 'historical_title_id_collision')
            rows.append({**base, 'id': title_id, 'text': title, 'status': 'present'})
            provenance[title_id] = {**metadata, 'text_component': 'title'}
    return rows, provenance


def load_historical_inventory(path):
    inventory = json.loads(Path(path).read_bytes())
    require(inventory.get('complete_for_requested_known_protection_sources') is True,
            'historical_inventory_incomplete')
    entries = []
    for source in inventory['files']:
        location = Path(source['path'])
        require(location.stat().st_size == source['bytes'] and
                file_sha(location) == source['sha256'], 'historical_source_identity_mismatch')
        metadata = source['records_metadata']
        count = 0
        with location.open('rb') as handle:
            for count, line in enumerate(handle, 1):
                require(count <= len(metadata), 'historical_inventory_row_count_mismatch')
                wrapper = json.loads(line)
                record = wrapper['record'] if source['format'] == 'wrapped_record_jsonl' else wrapper
                expected = metadata[count - 1]
                require(record.get('id') == expected['record_id'], 'historical_source_id_mismatch')
                if source['format'] == 'wrapped_record_jsonl':
                    require(wrapper['account_key'].casefold() == expected['account_key'] and
                            wrapper['split'] == expected['original_split'],
                            'historical_wrapper_identity_mismatch')
                entries.append({'record': record, 'account_key': expected['account_key'],
                                'original_split': expected['original_split'],
                                'source_id': source['source_id']})
        require(count == len(metadata) == source['record_count'],
                'historical_inventory_row_count_mismatch')
    return entries


def independent_candidate_pair_count(rows, *, cap=PAIR_CAP):
    """Independent inverted-bucket/all-pairs oracle, including non-near candidates.

    The original audit instead counts incrementally using per-record overlaps.
    Only its frozen preprocessor is shared; no audit helper or near test is used.
    """
    from account_history_analyzer import AnalysisConfig
    from account_history_analyzer.text import preprocess
    config = AnalysisConfig.from_toml()
    postings, word_counts, engine_eligible = defaultdict(set), {}, set()
    for ordinal, row in enumerate(rows):
        prepared = preprocess({'id': 'opaque', 'kind': 'comment', 'text': row['text'],
            'status': row.get('status', 'present'), 'language': row.get('language') or 'en'},
            {'text_format': 'markdown', 'default_language': 'en'}, config)
        words = sum(map(len, prepared['word_tokens']))
        word_counts[row['id']] = words
        shingles = {tuple(segment[start:start + 5]) for segment in prepared['tokens']
                    for start in range(max(0, len(segment) - 4))}
        if words >= 20 and len(shingles) >= 5:
            engine_eligible.add(ordinal)
        if words >= 20:
            for shingle in shingles:
                postings[shingle].add(ordinal)
    pairs, eligible_count = set(), 0
    for members in postings.values():
        for pair in itertools.combinations(sorted(members), 2):
            if pair in pairs:
                continue
            pairs.add(pair)
            if all(i in engine_eligible for i in pair):
                eligible_count += 1
            if len(pairs) > cap:
                return {'complete': False, 'candidate_pairs': len(pairs),
                        'engine_eligible_candidate_pairs': eligible_count,
                        'count_is_lower_bound': True, 'word_counts': word_counts}
    return {'complete': True, 'candidate_pairs': len(pairs),
            'engine_eligible_candidate_pairs': eligible_count,
            'count_is_lower_bound': False, 'word_counts': word_counts}


def purge_components(audit, provenance):
    """Keep content and thread exclusions separate, as in the registered draft."""
    reasons, thread_groups = defaultdict(set), defaultdict(list)
    memberships = [i for c in audit['components'] for i in c['record_ids']]
    require(len(memberships) == len(set(memberships)) and set(memberships) == set(provenance),
            'audit_component_coverage_mismatch')

    def mark(ids, kind):
        candidates = [i for i in ids if not provenance[i]['historical']]
        historical = any(provenance[i]['historical'] for i in ids)
        cells = {tuple(provenance[i]['cell']) for i in candidates}
        if candidates and historical:
            for i in candidates:
                reasons[i].add(kind + '_historical_boundary')
        if len(cells) > 1:
            for i in candidates:
                reasons[i].add(kind + '_cross_candidate_cells')

    for component in audit['components']:
        mark(component['record_ids'], 'content')
    for identifier, item in provenance.items():
        if item['thread_id']:
            thread_groups[item['thread_id']].append(identifier)
    crossed = []
    for thread, ids in sorted(thread_groups.items()):
        before = {i: set(reasons.get(i, ())) for i in ids}
        mark(ids, 'thread')
        if any(set(reasons.get(i, ())) != before[i] for i in ids):
            crossed.append({'thread_id': thread, 'record_ids': sorted(ids)})
    return {i: sorted(r) for i, r in sorted(reasons.items()) if r}, crossed


def run_audit(candidate_entries, historical_entries, engine):
    """Pure synthetic-testable orchestration; no file reads or resource changes."""
    candidates, cp = candidate_rows(candidate_entries)
    historical, hp = historical_rows(historical_entries)
    require(not (set(cp) & set(hp)), 'candidate_original_id_overlaps_history')
    require(not ({p['account_key'] for p in cp.values()} &
                 {p['account_key'] for p in hp.values()}), 'candidate_account_overlaps_history')
    rows, provenance = historical + candidates, {**hp, **cp}
    oracle = independent_candidate_pair_count(rows)
    summary = {'version': VERSION, 'status': 'not_auditable', 'scores_computed': False,
               'candidate_records': len(candidates), 'historical_body_records': len(hp) -
               sum(p['text_component'] == 'title' for p in hp.values()),
               'historical_title_protection_records': sum(p['text_component'] == 'title' for p in hp.values()),
               'historical_missing_thread_records': sum(not p['thread_id'] and p['text_component'] == 'body'
                                                        for p in hp.values()),
               'historical_missing_thread_audit_nodes': sum(not p['thread_id'] for p in hp.values()),
               'independent_candidate_pairs': oracle['candidate_pairs'],
               'independent_engine_eligible_candidate_pairs': oracle['engine_eligible_candidate_pairs'],
               'independent_count_is_lower_bound': oracle['count_is_lower_bound'],
               'max_candidate_pairs': PAIR_CAP}
    if not oracle['complete']:
        return {'summary': {**summary, 'reason_codes': ['independent_candidate_pair_cap_exceeded']},
                'purge_record_ids': [], 'surviving_candidate_ids': [], 'actionable': False}
    require(all(oracle['word_counts'][i] == p['declared_retained_words'] for i, p in cp.items()),
            'candidate_frozen_word_count_mismatch')
    audit = engine.audit_records(rows, max_candidate_pairs=PAIR_CAP)
    if audit['status'] != 'audited':
        return {'summary': {**summary, 'reason_codes': audit['summary']['reason_codes']},
                'purge_record_ids': [], 'surviving_candidate_ids': [], 'actionable': False}
    require(audit['summary']['candidate_pair_count'] == oracle['engine_eligible_candidate_pairs'],
            'independent_candidate_pair_count_disagrees')
    reasons, threads = purge_components(audit, provenance)
    missing_old_threads = summary['historical_missing_thread_records']
    unknown = sorted(set(audit['summary'].get('unknown_scope_flags', [])) |
                     ({'historical_thread_relationships_unknown'} if missing_old_threads else set()))
    summary.update(status='audited', reason_codes=[],
                   independence_scope_complete=not unknown,
                   available_content_and_grouping_audit_complete=missing_old_threads == 0,
                   gate_b_ready=missing_old_threads == 0,
                   unknown_scope_flags=unknown,
                   content_unobservable_record_count=audit['summary']['content_unobservable_record_count'],
                   content_scope=audit['summary']['content_scope'],
                   content_limitations=audit['summary']['limitations'],
                   candidate_retained_words=sum(p['declared_retained_words'] for p in cp.values()),
                   purged_candidate_records=len(reasons), surviving_candidate_records=len(cp) - len(reasons),
                   purge_reason_record_counts=dict(Counter(r for values in reasons.values() for r in values)),
                   content_relation_counts=audit['summary']['relation_counts'],
                   engine_candidate_pair_count=audit['summary']['candidate_pair_count'],
                   content_component_count=len(audit['components']),
                   available_content_only=True)
    return {'summary': summary, 'actionable': True, 'purge_record_ids': sorted(reasons),
            'purge_reasons': reasons, 'surviving_candidate_ids': sorted(set(cp) - set(reasons)),
            'crossing_threads': threads, 'record_provenance': provenance, 'engine_audit': audit}


def write_new(path, value, private=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600 if private else 0o644)
    with os.fdopen(descriptor, 'wb') as handle:
        handle.write(canonical(value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-pool', type=Path, required=True)
    parser.add_argument('--historical-inventory', type=Path, required=True)
    parser.add_argument('--engine-path', type=Path, required=True)
    parser.add_argument('--rules', type=Path, required=True)
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--out-private', type=Path, required=True)
    parser.add_argument('--out-public', type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    resource.setrlimit(resource.RLIMIT_AS, (MAX_AS_BYTES, MAX_AS_BYTES))
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError()))
    signal.alarm(MAX_WALL_SECONDS)
    failure = None
    try:
        require(os.environ.get('AHAS_NETWORK_ISOLATION') == 'linux_seccomp_socket_denial',
                'offline_runner_required')
        require(not args.out_private.exists() and not args.out_public.exists(), 'outputs_already_exist')
        freeze = json.loads(args.freeze.read_bytes())
        require(freeze.get('state') == 'frozen_before_audit', 'audit_freeze_not_registered')
        for name, path in [('candidate_pool', args.candidate_pool),
                           ('historical_inventory', args.historical_inventory),
                           ('engine', args.engine_path), ('wrapper', Path(__file__)),
                           ('rules', args.rules)]:
            require(file_sha(path) == freeze[name + '_sha256'], 'audit_frozen_input_mismatch')
        from account_history_analyzer import AnalysisConfig
        from account_history_analyzer.io import digest
        from account_history_analyzer.pipeline import implementation_identity
        require(implementation_identity()[0] == IMPLEMENTATION and
                digest(AnalysisConfig.from_toml().analytical()) == CONFIG_SHA256,
                'frozen_analyzer_binding_mismatch')
        require(args.candidate_pool.stat().st_size <= MAX_CANDIDATE_BYTES, 'candidate_byte_ceiling')
        candidates = []
        with args.candidate_pool.open('rb') as handle:
            for line in handle:
                candidates.append(json.loads(line))
                require(len(candidates) <= MAX_CANDIDATE_RECORDS, 'candidate_record_ceiling')
        candidate_rows(candidates)
        history = load_historical_inventory(args.historical_inventory)
        result = run_audit(candidates, history, load_engine(args.engine_path))
        args.out_private.mkdir(parents=True, mode=0o700)
        args.out_private.chmod(0o700)
        write_new(args.out_private/'audit.json', result, private=True)
        public = {**result['summary'], 'private_audit_sha256': file_sha(args.out_private/'audit.json'),
                  'freeze_sha256': file_sha(args.freeze), 'engine_sha256': ENGINE_SHA256,
                  'wrapper_sha256': file_sha(__file__), 'rules_sha256': file_sha(args.rules)}
    except Exception as error:
        failure = str(error) if type(error) is AuditFailure else {
            MemoryError: 'memory_allocation_failed', TimeoutError: 'wall_time_exceeded'
        }.get(type(error), 'unexpected_' + type(error).__name__)
        public = {'status': 'not_auditable', 'reason_codes': [failure], 'scores_computed': False}
    public.update(wall_seconds=time.monotonic() - started,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    try:
        if not args.out_public.exists():
            write_new(args.out_public, public)
        print(json.dumps(public, sort_keys=True), flush=True)
    except Exception as error:
        failure = 'result_write_failed_' + type(error).__name__
        print(json.dumps({'status': 'not_auditable', 'reason_codes': [failure],
                          'scores_computed': False}), flush=True)
    finally:
        signal.alarm(0)
    return 0 if public.get('gate_b_ready') is True and not failure else 4


if __name__ == '__main__':
    raise SystemExit(main())
