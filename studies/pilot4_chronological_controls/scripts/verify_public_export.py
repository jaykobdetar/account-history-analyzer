"""Check an explicit public export against private new-candidate identifiers/prose.

This is a bounded mechanical release check, not a guarantee of anonymization.
Only aggregate match counts and artifact hashes are emitted publicly.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


def grams(text, n=16):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {tuple(words[i:i+n]) for i in range(max(0, len(words)-n+1))}


def main():
    p = argparse.ArgumentParser()
    for key in ('export', 'pool', 'exposure', 'out'):
        p.add_argument('--'+key, required=True, type=Path)
    args = p.parse_args()
    entries = [json.loads(line) for line in args.pool.read_text().splitlines()]
    accounts = {r['account_key'] for r in json.loads(args.exposure.read_text())['accounts']}
    accounts.update(r['account_key'] for r in entries)
    identifiers = {r['record']['id'] for r in entries}
    identifiers.update(r['record']['thread_id'] for r in entries if r['record']['thread_id'])
    identifiers.update(r['record']['parent_id'] for r in entries if r['record']['parent_id'])
    prose = set().union(*(grams(r['record']['text']) for r in entries))
    counts = Counter(); artifacts = []
    for f in sorted(args.export.rglob('*')):
        if not f.is_file():
            continue
        if f.is_symlink() or f.suffix == '.pyc' or '__pycache__' in f.parts:
            raise ValueError('Export contains a symlink or cache artifact')
        data = f.read_bytes(); text = data.decode('utf-8')
        quoted = set(re.findall(r'''["']([^"'\n]{1,150})["']''', text))
        counts['exact_quoted_account_identifiers'] += len({x.casefold() for x in quoted} & accounts)
        counts['exact_quoted_source_or_group_identifiers'] += len(quoted & identifiers)
        counts['source_prose_sixteen_token_sequences'] += len(grams(text) & prose)
        counts['reddit_user_links'] += len(re.findall(r'(?i)(?:reddit\.com/(?:u|user)/|/u/)[a-z0-9_-]+', text))
        artifacts.append({'path': f.relative_to(args.export).as_posix(), 'bytes': len(data),
                          'sha256': hashlib.sha256(data).hexdigest()})
    report = {'status': 'passed' if not any(counts.values()) else 'review_required',
              'artifact_count': len(artifacts), 'artifact_bytes': sum(r['bytes'] for r in artifacts),
              'match_counts': dict(counts), 'candidate_records_protected': len(entries),
              'account_keys_protected': len(accounts), 'source_and_group_keys_protected': len(identifiers),
              'candidate_prose_sequence_count': len(prose), 'checker_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'private_identifiers_or_prose_emitted': False,
              'scope': 'Mechanical new-candidate exact quoted identity/group IDs,16-token raw-prose sequences, Reddit user links and cache/symlink checks; code and aggregate output also require review.',
              'artifacts': artifacts}
    args.out.open('x').write(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'artifacts'}))
    raise SystemExit(0 if report['status'] == 'passed' else 4)


if __name__ == '__main__':
    main()
