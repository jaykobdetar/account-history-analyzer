#!/usr/bin/env python3
"""Verify a fixed 100-record source sample; never emit prose or identifiers.

This is a bounded source-fidelity/preprocessing check, not a style evaluation.
Original archive members are streamed once. Only sample records from nonexcluded
accounts reach preprocessing. No text, per-record IDs or per-record hashes are
written to the aggregate report. Reproduce membership from the private census
metadata and the public fixed hash rule; hashes are not an anonymization claim.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import heapq
import json
import os
from pathlib import Path
import resource
import time
import zipfile

from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import digest
from account_history_analyzer.pipeline import implementation_identity
from account_history_analyzer.text import preprocess

SAMPLE_SIZE = 100
SALT = 'ahas-pilot3-source-check-v1:'
MAX_ROWS = 6_000_000
MAX_UNCOMPRESSED = 4_000_000_000
MAX_SECONDS = 300
MAX_ADDRESS_SPACE = 2 * 1024**3
MANIFEST = {'default_language': 'en', 'text_format': 'markdown'}


class SourceSampleError(ValueError):
    """Messages are fixed error codes and never contain original source content."""


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')) + '\n').encode()


def file_hash(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def _stamp(value):
    if type(value) is not int:
        return None
    try:
        moment = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=value)
    except (ValueError, OverflowError):
        return None
    return moment.isoformat().replace('+00:00', 'Z')


def choose_sample(path, excluded, *, max_rows=MAX_ROWS):
    """Lowest 100 SHA256 ranks over preprocessed metadata, independent of labels."""
    seen, population, all_rows = set(), 0, 0
    def population_rows():
        nonlocal population, all_rows
        with Path(path).open('rb') as handle:
            for raw in handle:
                all_rows += 1
                if all_rows > max_rows:
                    raise SourceSampleError('metadata_row_budget_exhausted')
                row = json.loads(raw)
                account, identifier = row['account_key'], row['record_id']
                if account.casefold() in excluded:
                    raise SourceSampleError('protected_identity_in_preprocessing_metadata')
                if not isinstance(identifier, str) or not identifier or identifier in seen:
                    raise SourceSampleError('invalid_or_duplicate_metadata_record_id')
                seen.add(identifier)
                if row['retained_words'] is None:
                    continue
                if type(row['retained_words']) is not int or row['retained_words'] < 0:
                    raise SourceSampleError('invalid_preprocessed_word_count')
                population += 1
                yield row
    selected = heapq.nsmallest(SAMPLE_SIZE, population_rows(), key=lambda row: (
        hashlib.sha256((SALT + row['record_id']).encode()).digest(), row['record_id']))
    if population < SAMPLE_SIZE:
        raise SourceSampleError('fewer_than_100_preprocessed_rows_no_silent_sample_shrink')
    return selected, population, all_rows


def rederive(raw, community, excluded, config):
    """Use original bytes, independent timestamp arithmetic and token-offset tally."""
    original_line_hash = hashlib.sha256(raw).hexdigest()
    source = json.loads(raw)
    account = source.get('user')
    if not isinstance(account, str):
        raise SourceSampleError('sample_source_account_missing')
    account = account.casefold()
    if account in excluded:
        raise SourceSampleError('protected_identity_never_preprocessed')
    if (source.get('meta') or {}).get('subreddit') != community:
        raise SourceSampleError('sample_source_community_mismatch')
    identifier = source['id']
    if source.get('root') == identifier:
        raise SourceSampleError('sample_source_is_submission')
    stamp = _stamp(source.get('timestamp'))
    # All sampled census rows claim to have reached preprocessing. Refuse to
    # repair changed or malformed source data into a usable sample.
    body = source.get('text')
    if stamp is None or not isinstance(body, str) or body.strip() in {'[removed]', '[deleted]'} or len(body) > config['input']['max_text_codepoints']:
        raise SourceSampleError('sample_source_cannot_have_reached_frozen_preprocessing')
    original_text_hash = hashlib.sha256(body.encode('utf-8')).hexdigest()
    record = {'id': identifier, 'kind': 'comment', 'text': body, 'status': 'present',
              'created_utc': stamp, 'language': None, 'subreddit': community, 'edit_state': 'unknown'}
    view = preprocess(record, MANIFEST, config)
    # Deliberately never read view['word_tokens']: independent tally from kind
    # annotations and bounds in the frozen token-offset representation.
    words = 0
    for segment, offsets in zip(view['segments'], view['token_offsets'], strict=True):
        for token in offsets:
            if segment['text'][token['start']:token['end']] != token['text']:
                raise SourceSampleError('token_offset_text_mismatch')
            words += token['kind'] == 'word'
    if hashlib.sha256(record['text'].encode('utf-8')).hexdigest() != original_text_hash or view['source_sha256'] != original_text_hash:
        raise SourceSampleError('original_source_text_changed')
    reason = None if view['usable'] and words >= config['style']['minimum_record_words'] else 'below_frozen_record_word_guard'
    return {'account_key': account, 'community': community, 'record_id': identifier,
            'created_utc': stamp, 'retained_words': words, 'reason': reason,
            'source_line_sha256': original_line_hash}


def check_sample(plan_path, source_root, private_root, census_name, *, census_root=None):
    started = time.monotonic()
    plan_path, source_root, private_root = map(Path, (plan_path, source_root, private_root))
    if not isinstance(census_name, str) or Path(census_name).name != census_name or census_name in {'.', '..'}:
        raise SourceSampleError('invalid_census_name')
    public = Path(census_root) if census_root is not None else Path(__file__).resolve().parents[1] / 'inventory' / census_name
    plan = load(plan_path)
    config = AnalysisConfig.from_toml()
    fp, environment, resources = implementation_identity()
    if fp != plan['implementation_fingerprint'] or digest(config.analytical()) != plan['analysis_config_sha256']:
        raise SourceSampleError('frozen_installed_implementation_or_config_mismatch')
    binding = load(public / 'start-binding.json')
    exclusion_path = private_root / 'exclusions-mandatory.json'
    metadata_path = private_root / census_name / 'record-eligibility.jsonl'
    hashes = load(public / 'private-artifact-hashes.json')
    if binding['plan_sha256'] != file_hash(plan_path) or binding['exclusions_sha256'] != file_hash(exclusion_path):
        raise SourceSampleError('census_plan_or_exclusion_binding_mismatch')
    if file_hash(metadata_path) != hashes['record-eligibility.jsonl']['sha256']:
        raise SourceSampleError('private_metadata_hash_mismatch')
    exclusion = load(exclusion_path)
    if exclusion.get('complete_for_known_pilot_sources') is not True:
        raise SourceSampleError('protected_exclusion_manifest_incomplete')
    excluded = {row['account_key'].casefold() for row in exclusion['accounts']}
    selected, population, metadata_rows = choose_sample(metadata_path, excluded, max_rows=min(MAX_ROWS, plan['limits']['max_source_rows_per_pass']))
    selected_by_id = {row['record_id']: row for row in selected}
    if len(selected_by_id) != SAMPLE_SIZE:
        raise SourceSampleError('sample_membership_not_unique')
    limits = {'source_passes': 1, 'max_source_rows': min(MAX_ROWS, plan['limits']['max_source_rows_per_pass']),
              'max_source_uncompressed_bytes': min(MAX_UNCOMPRESSED, plan['limits']['max_source_uncompressed_bytes_per_pass']),
              'max_wall_seconds': min(MAX_SECONDS, plan['limits']['max_wall_seconds']),
              'max_address_space_bytes': min(MAX_ADDRESS_SPACE, plan['limits']['max_address_space_bytes']),
              'max_preprocessing_calls': SAMPLE_SIZE}
    inventory = {source['community']: source for source in load(public / 'source-inventory.json')['sources']}
    found, failures, sample_statuses, sources = set(), Counter(), Counter(), []
    rows = raw_bytes = preprocessing_calls = 0

    def budget():
        if rows > limits['max_source_rows'] or raw_bytes > limits['max_source_uncompressed_bytes'] or time.monotonic() - started > limits['max_wall_seconds'] or preprocessing_calls > SAMPLE_SIZE:
            raise SourceSampleError('independent_source_check_budget_exhausted')

    for source in plan['sources']:
        budget()
        archive_path = Path(source['archive'])
        if not archive_path.is_absolute():
            archive_path = source_root / archive_path
        if archive_path.stat().st_size != source['bytes'] or file_hash(archive_path) != source['sha256']:
            raise SourceSampleError('archive_identity_changed_before_source_check')
        member_hash, member_rows, member_bytes = hashlib.sha256(), 0, 0
        with zipfile.ZipFile(archive_path) as archive:
            entries = [entry for entry in archive.infolist() if entry.filename == 'utterances.jsonl']
            if len(entries) != 1:
                raise SourceSampleError('utterances_member_missing_or_duplicated')
            if raw_bytes + entries[0].file_size > limits['max_source_uncompressed_bytes']:
                raise SourceSampleError('independent_source_check_budget_exhausted')
            with archive.open(entries[0]) as stream:
                for raw in stream:
                    rows += 1
                    member_rows += 1
                    member_bytes += len(raw)
                    raw_bytes += len(raw)
                    member_hash.update(raw)
                    if rows % 1000 == 0:
                        budget()
                    source_record = json.loads(raw)
                    identifier = source_record.get('id')
                    if identifier not in selected_by_id:
                        continue
                    if identifier in found:
                        raise SourceSampleError('selected_source_record_occurs_more_than_once')
                    found.add(identifier)
                    account = source_record.get('user')
                    if isinstance(account, str) and account.casefold() in excluded:
                        raise SourceSampleError('protected_identity_never_preprocessed')
                    preprocessing_calls += 1
                    budget()
                    derived = rederive(raw, source['community'], excluded, config)
                    expected = selected_by_id[identifier]
                    for key in ('account_key', 'community', 'record_id', 'created_utc', 'retained_words', 'reason', 'source_line_sha256'):
                        if derived[key] != expected[key]:
                            failures[key + '_mismatch'] += 1
                    sample_statuses['eligible' if derived['reason'] is None else derived['reason']] += 1
        observed = inventory[source['community']]
        if member_rows != observed['counts']['source_records'] or member_hash.hexdigest() != observed['utterances_sha256'] or member_bytes != observed['utterances_bytes']:
            raise SourceSampleError('streamed_source_identity_differs_from_census')
        sources.append({'community': source['community'], 'archive_sha256': source['sha256'],
                        'rows': member_rows, 'utterances_bytes': member_bytes, 'utterances_sha256': member_hash.hexdigest()})
    budget()
    if len(found) != SAMPLE_SIZE or preprocessing_calls != SAMPLE_SIZE:
        raise SourceSampleError('not_all_100_fixed_sample_records_verified')
    check_plan = Path(__file__).resolve().parents[1] / 'protocol' / 'INDEPENDENT_CHECK_PLAN.md'
    return {'status': 'pass' if not failures else 'fail', 'scores_computed': False,
            'sample_rule': 'Lowest SHA256 ranks of UTF8(salt + original record ID), including both eligible and below-guard preprocessed rows; ID tie-break only.',
            'sample_salt': SALT, 'sample_size': SAMPLE_SIZE, 'preprocessed_sampling_population': population,
            'metadata_rows_examined': metadata_rows, 'sample_outcomes': dict(sample_statuses),
            'sample_membership_sha256': hashlib.sha256(canonical([row['record_id'] for row in selected])).hexdigest(),
            'mismatch_counts': dict(failures), 'source_passes': 1, 'source_rows': rows,
            'source_uncompressed_bytes': raw_bytes, 'preprocessing_calls': preprocessing_calls,
            'protected_sample_accounts': 0, 'word_count_representation': 'Count kind=word in token_offsets; never consume word_tokens',
            'original_text_integrity_checked': True, 'source_line_bytes_hashed_before_parsing': True,
            'text_or_record_identifiers_exported': False, 'sources': sources,
            'implementation_fingerprint': fp, 'analysis_config_sha256': digest(config.analytical()),
            'reference_environment': environment, 'resource_hashes': resources,
            'limits': limits, 'wall_seconds': time.monotonic() - started,
            'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            'bindings': {'plan_sha256': file_hash(plan_path), 'exclusions_sha256': file_hash(exclusion_path),
                         'private_record_eligibility_sha256': file_hash(metadata_path),
                         'source_inventory_sha256': file_hash(public / 'source-inventory.json'),
                         'checker_sha256': file_hash(__file__),
                         'check_plan_sha256': file_hash(check_plan) if check_plan.exists() else None},
            'limitations': ['Checks 100 deterministic source records, not every record; no population accuracy claim.',
                            'Uses the same frozen parser/tokenizer with an independent token-offset tally; not an independent preprocessing implementation.',
                            'Original prose remains inside the local verification process and is not emitted; aggregate hashes are integrity bindings, not anonymization.']}


def main():
    parser = argparse.ArgumentParser()
    for name in ('plan', 'source-root', 'private-root', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--census-name', required=True)
    args = parser.parse_args()
    if os.environ.get('AHAS_NETWORK_ISOLATION') != 'linux_seccomp_socket_denial':
        raise SourceSampleError('run_source_check_through_frozen_offline_runner')
    plan = load(args.plan)
    ceiling = min(MAX_ADDRESS_SPACE, plan['limits']['max_address_space_bytes'])
    resource.setrlimit(resource.RLIMIT_AS, (ceiling, ceiling))
    report = check_sample(args.plan, args.source_root, args.private_root, args.census_name)
    with args.out.open('xb') as handle:
        handle.write(canonical(report))
    print(json.dumps({'status': report['status'], 'sample_size': report['sample_size'],
                      'mismatch_counts': report['mismatch_counts'], 'report_sha256': file_hash(args.out)}))
    raise SystemExit(0 if report['status'] == 'pass' else 1)


if __name__ == '__main__':
    main()
