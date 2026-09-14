"""Pre-score verification of literal cap accounting and newly observed bridges.

No style scores or match thresholds are computed. The only token-derived check
enumerates unique record pairs sharing a five-token shingle under both possible
readings of the distinct-shingle prefilter in the registered cap wording.
"""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from account_history_analyzer import AnalysisConfig
from account_history_analyzer.text import preprocess

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def sha_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cross_pairs(ids, split_by_id):
    counts = Counter(split_by_id[i] for i in ids)
    return (len(ids) * (len(ids) - 1) - sum(n * (n - 1) for n in counts.values())) // 2


def main():
    output = ROOT / 'review/audit-cap-and-joint-bridges.json'
    if output.exists():
        raise SystemExit('Refusing to overwrite historical verification')
    pool_path = ROOT / 'prepared/paired/private/candidate-pool.jsonl'
    initial_path = ROOT / 'prepared/paired/private/leakage-audit.json'
    joint_path = ROOT / 'prepared/streams/private/joint-related-audit.json'
    initial, joint = read(initial_path), read(joint_path)
    assert initial['status'] == joint['status'] == 'audited'
    pool = [json.loads(line) for line in pool_path.read_text().splitlines()]
    paired_ids = {r['record']['id'] for r in pool}
    rows = {r['record']['id']: r['record'] for r in pool}
    split_by_id = {r['record']['id']: r['split'] for r in pool}
    account_paths = sorted((ROOT / 'prepared/streams/accounts').glob('*.jsonl'))
    for path in account_paths:
        for line in path.read_text().splitlines():
            record = json.loads(line)
            assert record['id'] not in rows
            rows[record['id']] = record
    joint_ids = [i for c in joint['components'] for i in c['record_ids']]
    assert len(joint_ids) == len(set(joint_ids)) == len(rows)
    assert set(joint_ids) == set(rows)
    initial_cluster = {i: c['cluster_id'] for c in initial['near_duplicate_clusters'] for i in c['record_ids']}
    bridge_components = 0
    new_cross_split_pair_memberships = 0
    newly_connected_paired_members = set()
    for component in joint['components']:
        ids = sorted(set(component['record_ids']) & paired_ids)
        groups = defaultdict(list)
        for identifier in ids:
            groups[initial_cluster[identifier]].append(identifier)
        previous_cross_pairs = sum(cross_pairs(group, split_by_id) for group in groups.values())
        new_pairs = cross_pairs(ids, split_by_id) - previous_cross_pairs
        assert new_pairs >= 0
        if new_pairs:
            bridge_components += 1
            new_cross_split_pair_memberships += new_pairs
            newly_connected_paired_members.update(ids)
    assert set(joint['excluded_ids']) & paired_ids == set(initial['purge_record_ids'])

    # A neighbor set counts each pair exactly once. Unlike the audit's overlap
    # Counter, this broad index admits records with fewer than five distinct
    # shingles so their precise accounting effect can be measured.
    config = AnalysisConfig.from_toml()
    postings = defaultdict(list)
    unique_count = {}
    counts = Counter()
    for identifier in sorted(rows):
        record = rows[identifier]
        body = preprocess({'id': 'opaque', 'kind': 'comment', 'status': record['status'],
            'text': record['text'], 'language': 'en'},
            {'text_format': 'markdown', 'default_language': 'en'}, config)
        if sum(len(segment) for segment in body['word_tokens']) < 20:
            counts['joint_below_twenty_word_guard_records'] += 1
            if identifier in paired_ids:
                counts['paired_below_twenty_word_guard_records'] += 1
            continue
        shingles = {tuple(segment[i:i + 5]) for segment in body['tokens']
                    for i in range(len(segment) - 4)}
        unique_count[identifier] = len(shingles)
        if len(shingles) < 5:
            counts['joint_records_excluded_only_by_distinct_shingle_prefilter'] += 1
            if identifier in paired_ids:
                counts['paired_records_excluded_only_by_distinct_shingle_prefilter'] += 1
        neighbors = set()
        for shingle in shingles:
            neighbors.update(postings[shingle])
        counts['joint_broad_candidate_pairs'] += len(neighbors)
        for previous in neighbors:
            paired = identifier in paired_ids and previous in paired_ids
            if paired:
                counts['paired_broad_candidate_pairs'] += 1
            if len(shingles) >= 5 and unique_count[previous] >= 5:
                counts['joint_implemented_candidate_pairs'] += 1
                if paired:
                    counts['paired_implemented_candidate_pairs'] += 1
        if counts['joint_broad_candidate_pairs'] > 2_000_000:
            raise AssertionError('Literal broad accounting exceeds registered cap; pre-score work must stop')
        for shingle in shingles:
            postings[shingle].append(identifier)
    assert counts['paired_implemented_candidate_pairs'] == initial['summary']['candidate_pair_count']
    assert counts['joint_implemented_candidate_pairs'] == joint['summary']['candidate_pair_count']
    for scope in ('paired', 'joint'):
        for name in ('records_excluded_only_by_distinct_shingle_prefilter', 'below_twenty_word_guard_records'):
            counts.setdefault(scope + '_' + name, 0)
        counts[scope + '_candidate_cap_count_difference'] = (
            counts[scope + '_broad_candidate_pairs'] - counts[scope + '_implemented_candidate_pairs'])
    result = {'status': 'passed', 'pool_sha256': sha_file(pool_path),
        'initial_audit_sha256': sha_file(initial_path), 'joint_audit_sha256': sha_file(joint_path),
        'verifier_sha256': sha_file(Path(__file__)),
        'source_accounts_files': len(account_paths), 'paired_records': len(paired_ids),
        'joint_records': len(rows), 'joint_graph_all_original_ids_covered': True,
        'joint_components_exposing_new_paired_cross_split_relationships': bridge_components,
        'new_paired_cross_split_pair_memberships': new_cross_split_pair_memberships,
        'paired_records_in_new_cross_split_bridge_components': len(newly_connected_paired_members),
        'joint_paired_cross_split_purge_same_as_initial': True,
        'candidate_cap': 2_000_000, 'candidate_accounting': dict(sorted(counts.items())),
        'broad_accounting_definition': 'Both records at least20 retained words; any shared unique segment-local lexical five-shingle; no minimum distinct-shingle prefilter.',
        'implemented_accounting_definition': 'Same broad definition plus at least5 distinct five-shingles in each record, a necessary condition for the five-shared-shingle match guard.',
        'style_distances_calculated': False,
        'limitation': 'Observed available text only; no claim about unseen prose, semantic paraphrase, unmarked quotation or independent human authors.'}
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
