"""Post-registration privacy reporting; no scoring or protected prose reads.

Only known identifier metadata and automated exact phrase hashes from the new
candidate pool are compared. No matching private value is emitted.
"""
from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import re


def digest(data):
    return hashlib.sha256(data).hexdigest()


def phrases(text):
    words = re.findall(r'[a-z]+', text.lower())
    for i in range(len(words) - 19):
        yield hashlib.sha256(' '.join(words[i:i+20]).encode()).digest()


def review(study, private, output):
    start = datetime.now(timezone.utc).isoformat()
    exclusions = json.loads((private/'exclusions.json').read_bytes())
    selection = json.loads((private/'candidates-01/candidate-selection.json').read_bytes())
    history = json.loads((private/'historical-audit-source-inventory.json').read_bytes())
    accounts = {r['account_key'].lower() for r in exclusions['accounts']}
    for values in selection['considered_accounts_by_stratum'].values():
        accounts.update(v.lower() for v in values)
    for values in selection['allocation']['assigned'].values():
        accounts.update(v.lower() for v in values)
    record_ids = {k.lower() for k in selection['selected_record_metadata']}
    historical_threads = set()
    for source in history['files']:
        for row in source['records_metadata']:
            accounts.add(row['account_key'].lower())
            record_ids.add(row['record_id'].lower())
            if row.get('thread_id'):
                historical_threads.add(row['thread_id'].lower())
    candidate_threads, candidate_phrases = set(), set()
    candidate_count = 0
    with (private/'candidates-01/candidate-pool.jsonl').open() as handle:
        for line in handle:
            row = json.loads(line)
            candidate_count += 1
            candidate_threads.add(row['record']['thread_id'].lower())
            candidate_phrases.update(phrases(row['record']['text']))
    ids = record_ids | historical_threads | candidate_threads
    # Both original plain IDs and standard Reddit kind-prefixed IDs are covered.
    ids |= {x.split('_', 1)[1] for x in tuple(ids) if x.startswith(('t1_', 't3_'))}
    credentials = re.compile(r'(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|xox[baprs]-[0-9A-Za-z-]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{40,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|https?://[^\s/:]+:[^\s/@]+@)')
    profiles = re.compile(r'(?:https?://)?(?:www\.)?reddit\.com/(?:u|user)/[^\s/]+', re.I)
    fields = {'account_key', 'account_id', 'username', 'author', 'original_record_id', 'record_id', 'source_account_map', 'source_account_keys'}
    prose_fields = {'text', 'body', 'selftext', 'original_text', 'source_text'}
    findings = Counter({k: 0 for k in ('known_source_account_matches', 'known_record_or_thread_id_matches', 'known_credential_syntax_matches', 'reddit_profile_urls', 'sensitive_json_values', 'long_source_text_fields', 'candidate_exact_twenty_alphabetic_word_phrase_matches')})
    finding_files, home_files, inventory = {}, [], []
    changes = []
    files = sorted(p for p in study.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts and p.resolve() != output.resolve())
    for path in files:
        if path.is_symlink():
            raise ValueError('Public tree contains an unresolved symbolic link')
        data = path.read_bytes()
        value = data.decode('utf-8')
        rel = path.relative_to(study).as_posix()
        inventory.append({'path': rel, 'bytes': len(data), 'sha256': digest(data)})
        tokens = set(re.findall(r'[A-Za-z0-9_-]+', value.lower()))
        found = Counter()
        found['known_source_account_matches'] = len(tokens & accounts)
        found['known_record_or_thread_id_matches'] = len(tokens & ids)
        found['known_credential_syntax_matches'] = len(credentials.findall(value))
        found['reddit_profile_urls'] = len(profiles.findall(value))
        found['candidate_exact_twenty_alphabetic_word_phrase_matches'] = sum(h in candidate_phrases for h in phrases(value))
        if path.suffix == '.json':
            obj = json.loads(value)
            def walk(node):
                if isinstance(node, dict):
                    for key, child in node.items():
                        if key in fields and child not in (None, [], {}, ''):
                            found['sensitive_json_values'] += 1
                        if key in prose_fields and isinstance(child, str) and len(re.findall('[A-Za-z]+', child)) >= 20:
                            found['long_source_text_fields'] += 1
                        walk(child)
                elif isinstance(node, list):
                    for child in node:
                        walk(child)
            walk(obj)
        counts = {k: v for k, v in found.items() if v}
        if counts:
            finding_files[rel] = counts
        findings.update(found)
        count = len(re.findall(r'/home/[^\s/]+/', value))
        if count:
            home_files.append({'path': rel, 'occurrences': count})
    for item in inventory:
        if digest((study/item['path']).read_bytes()) != item['sha256']:
            changes.append(item['path'])
    report = {
        'status': 'completed_without_pattern_findings' if not any(findings.values()) and not changes else 'findings_or_changed_files_require_review',
        'started_utc': start, 'finished_utc': datetime.now(timezone.utc).isoformat(),
        'registration_relationship': 'Post-registration privacy reporting only; no existing frozen files changed.',
        'scope': {'public_files': len(inventory), 'public_bytes': sum(r['bytes'] for r in inventory), 'known_source_accounts': len(accounts), 'known_source_record_ids': len(record_ids), 'known_historical_thread_ids': len(historical_threads), 'known_candidate_thread_ids': len(candidate_threads), 'new_candidate_records_automatically_compared': candidate_count, 'historical_or_reserve_prose_read': False, 'feature_vectors_read': False, 'source_prose_displayed': False},
        'findings': dict(findings), 'finding_paths_and_counts_only': finding_files,
        'changed_during_review': changes,
        'operational_home_paths': {'files': len(home_files), 'occurrences': sum(r['occurrences'] for r in home_files), 'paths_and_counts': home_files, 'interpretation': 'Immutable operational receipts retain local root paths. Preserve originals; sanitize logical roots in a separately declared release copy if public redistribution is later requested. Sanitized execution resource argv already marks every path substitution.'},
        'limitations': ['Known identifier metadata only; absence of matches is not a proof that arbitrary personal data or secrets cannot occur.', 'Phrase comparison covers exact sequences of twenty alphabetic words from the new candidate pool. Shorter excerpts, paraphrases, historical writing and private-export writing are outside this phrase test.', 'No historical or reserve writing was read. New candidate prose was processed automatically into hashes and never displayed.', 'This report binds the listed snapshot. Later-added integrity manifests should contain only paths, sizes and hashes and require their own metadata review.'],
        'inventory': inventory,
    }
    with output.open('x') as handle:
        json.dump(report, handle, sort_keys=True, indent=2)
        handle.write('\n')
    print(json.dumps({k: report[k] for k in ('status', 'scope', 'findings', 'changed_during_review')}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--study', required=True, type=Path)
    parser.add_argument('--private', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    review(args.study.resolve(), args.private.resolve(), args.out.resolve())
