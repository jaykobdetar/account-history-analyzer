#!/usr/bin/env python3
"""Independent registered paired selection audit; no comparison/scoring API.

Metadata selection and ranking are reconstructed here without importing the
preparation adapter. The frozen AHAS preprocessor is the sole lexical primitive.
Original prose is read locally but never written to the audit summaries.
"""
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, os, resource, time, zipfile

from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import canonical_bytes, digest
from account_history_analyzer.pipeline import implementation_identity
from account_history_analyzer.text import preprocess

ROOT = Path(__file__).resolve().parents[1]
PLAN_HASH = '26f4d551b4557886c6f67fe7484cd3d139b301ea68fa911a25f4c020f0ab82d8'


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def h(salt, value):
    return hashlib.sha256((salt + ':' + value).encode()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open('xb') as handle:
        handle.write(canonical_bytes(value))
    path.chmod(0o600)


def main():
    started = time.monotonic()
    assert os.environ.get('AHAS_NETWORK_ISOLATION') == 'linux_seccomp_socket_denial'
    plan_path = ROOT / 'protocol/plan.json'
    assert sha(plan_path) == PLAN_HASH
    plan = json.loads(plan_path.read_bytes())
    registration = json.loads((ROOT / 'protocol/registration.json').read_bytes())
    assert registration['status'] == 'registered' and registration['scoring_authorized'] is False
    for name, expected in registration['files'].items():
        assert sha(ROOT / name) == expected, 'Registered resource hash changed'
    assert implementation_identity()[0] == plan['implementation_fingerprint']
    config = AnalysisConfig.from_toml()
    assert digest(config.analytical()) == plan['analysis_config_sha256']
    private = ROOT / 'prepared/paired/private'
    selection = json.loads((private / 'selection.json').read_bytes())
    assert selection['plan_sha256'] == PLAN_HASH
    pool_path = private / 'candidate-pool.jsonl'
    assert sha(pool_path) == selection['candidate_pool_sha256']
    pool = {}
    with pool_path.open() as handle:
        for line in handle:
            row = json.loads(line)
            assert row['record']['id'] not in pool
            pool[row['record']['id']] = (row['account_key'], row['cell'], row['retained_words'])
    old = json.loads((ROOT.parent / 'ahas-realworld-review/inputs/public/source-map.json').read_bytes())
    excluded = {row['source_account'].casefold() for row in old['accounts']}
    excluded |= {'', 'anonymous', '[anonymous]', 'unknown', '[unknown]', '[deleted]', '[removed]', '[missing]', 'automoderator'}
    frame = ROOT / 'inventory/private/source-frame.jsonl'
    assert sha(frame) == selection['source_frame_sha256']
    raw = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    with frame.open() as handle:
        for line in handle:
            row = json.loads(line)
            author = row['source_account'].casefold()
            if author.strip() in excluded or author in excluded or row['community'] not in plan['communities']:
                continue
            for pos, year in enumerate(('2017', '2018')):
                raw[author][row['community']][pos] += row['years'].get(year, {}).get('present_raw_codepoints', 0)
    groups = defaultdict(list)
    for author, cells in raw.items():
        home = sorted(cells, key=lambda c: (-sum(cells[c]), c))[0]
        rank_hash = h(plan['salts']['author_rank'], author)
        split = plan['splits'][int(h(plan['salts']['author_split'], author), 16) % 3]
        groups[home, split].append((min(cells[home]), rank_hash, author))
    expected_shortlist = {}
    for (home, split), members in groups.items():
        for i, (volume, rank_hash, author) in enumerate(sorted(members, key=lambda x: (-x[0], x[1]))[:20]):
            expected_shortlist[author] = {'account_key': author, 'home_community': home, 'split': split,
                'author_rank_hash': rank_hash, 'pre_shortlist_rank': i + 1,
                'pre_shortlist_capacity': volume}
    observed_shortlist = {row['account_key']: row for row in selection['shortlist']}
    assert set(expected_shortlist) == set(observed_shortlist)
    for author, expected in expected_shortlist.items():
        assert all(observed_shortlist[author][key] == value for key, value in expected.items()), 'Metadata shortlist mismatch'
    selected = {row['account_key']: row for row in selection['accounts']}
    capacities = defaultdict(Counter)
    records_seen = set()
    counts = Counter()
    for community, source in plan['source_archives'].items():
        path = (ROOT / source['path']).resolve()
        assert sha(path) == source['sha256']
        with zipfile.ZipFile(path) as archive, archive.open('utterances.jsonl') as handle:
            for line in handle:
                source_row = json.loads(line)
                counts['source_rows'] += 1
                author = source_row.get('user')
                if not isinstance(author, str) or author.casefold() not in expected_shortlist:
                    continue
                author = author.casefold()
                if source_row['root'] == source_row['id']:
                    continue
                timestamp = source_row.get('timestamp')
                if type(timestamp) is not int:
                    continue
                instant = datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
                cell = next((c for c in ('early', 'late') if plan['paired'][c]['start_utc'] <= instant < plan['paired'][c]['end_utc']), None)
                text = source_row.get('text')
                if cell is None or not isinstance(text, str) or text.strip() in {'[removed]', '[deleted]'}:
                    continue
                # Account IDs, labels, rank and split metadata are deliberately absent.
                record = {'id': source_row['id'], 'kind': 'comment', 'text': text,
                    'status': 'present', 'title': None, 'language': None}
                view = preprocess(record, {'default_language': 'en', 'text_format': 'markdown'}, config)
                words = sum(map(len, view['word_tokens']))
                counts['shortlist_records_preprocessed'] += 1
                if not view['usable'] or words < 20:
                    counts['shortlist_records_below_guard'] += 1
                    continue
                source_community = source_row['meta']['subreddit']
                if source_community == expected_shortlist[author]['home_community']:
                    capacities[author][cell] += words
                if author in selected:
                    identifier = source_row['id']
                    assert identifier not in records_seen
                    records_seen.add(identifier)
                    assert pool.get(identifier) == (author, cell, words), 'Candidate eligibility/word count mismatch'
    assert records_seen == set(pool), 'Candidate population differs from the registered selection'
    details = []
    for home in plan['communities']:
        for split in plan['splits']:
            members = [row for row in expected_shortlist.values() if row['home_community'] == home and row['split'] == split]
            members.sort(key=lambda row: (-min(capacities[row['account_key']][c] for c in ('early', 'late')), row['author_rank_hash']))
            assert {row['account_key'] for row in members[:4]} == {key for key, row in selected.items() if row['home_community'] == home and row['split'] == split}
            for rank, row in enumerate(members, 1):
                author = row['account_key']
                words = {c: capacities[author][c] for c in ('early', 'late')}
                if author in selected:
                    assert selected[author]['selected_rank'] == rank and selected[author]['eligible_words_by_cell'] == words
                details.append({**row, 'eligible_words_by_cell': words, 'capacity_rank': rank,
                    'selected_before_purge': author in selected,
                    'exclusion_reason': None if author in selected else 'not_in_top4_pre_purge'})
    detail_path = ROOT / 'inventory/private/paired-shortlist-capacities.json'
    save(detail_path, details)
    summary = {'status': 'passed', 'protocol_plan_sha256': PLAN_HASH,
        'candidate_pool_sha256': sha(pool_path), 'selection_sha256': sha(private / 'selection.json'),
        'independent_script_sha256': sha(Path(__file__)), 'private_capacity_audit_sha256': sha(detail_path),
        'shortlisted_accounts_verified': len(details), 'selected_accounts_verified': len(selected),
        'rejected_shortlisted_accounts_with_capacity_audit': sum(not row['selected_before_purge'] for row in details),
        'candidate_records_verified': len(records_seen), 'candidate_retained_words_verified': sum(row[2] for row in pool.values()),
        'counts': dict(counts), 'checks': ['registered_hashes', 'frozen_implementation_and_config',
            'global_casefold_identity', 'old_and_placeholder_exclusions', 'home_assignment', 'salted_split',
            'metadata_shortlist_rank', 'eligible_word_capacity_rank', 'no_post_purge_replacements',
            'entire_pre_purge_candidate_population', 'account_metadata_absent_from_preprocessing'],
        'elapsed_seconds': time.monotonic() - started, 'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        'scores_computed': False, 'language': 'English corpus assumption, not individually verified'}
    save(ROOT / 'inventory/paired-preflight.json', summary)
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()
