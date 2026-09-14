#!/usr/bin/env python3
"""Independent actual paired-input checks, without any score calculation."""
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
import argparse, hashlib, json, os

from account_history_analyzer.io import canonical_bytes, load_snapshot
from account_history_analyzer.schemas import validate

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def timestamp(value):
    return datetime.fromisoformat(value).timestamp()


def ordered(records):
    return sorted(records, key=lambda row: (row['record']['created_utc'], row['record']['id']))


def mtime(records):
    return median([timestamp(row['record']['created_utc']) for row in records]) if records else None


def stat(records, target):
    count = len(records)
    words = sum(row['retained_words'] for row in records)
    return {'target_B': target, 'actual_eligible_words': words, 'overshoot_words': max(0, words - target),
        'eligible_records': count, 'largest_record_share': max((row['retained_words'] for row in records), default=0) / words if words else None,
        'first_utc': records[0]['record']['created_utc'] if records else None,
        'last_utc': records[-1]['record']['created_utc'] if records else None,
        'qualified_for_production_comparison': count >= 8 and words >= 1000,
        'target_reached': count >= 8 and words >= target}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--audit', type=Path, required=True)
    args = parser.parse_args()
    OUT = args.prepared.resolve()
    assert os.environ.get('AHAS_NETWORK_ISOLATION') == 'linux_seccomp_socket_denial'
    plan = read(ROOT / 'protocol/plan.json')
    registration = read(ROOT / 'protocol/registration.json')
    assert sha(ROOT / 'protocol/plan.json') == registration['files']['protocol/plan.json']
    pool = {row['record']['id']: row for row in rows(OUT / 'private/candidate-pool.jsonl')}
    audit = read(args.audit)
    purge = read(OUT / 'private/purge.json')
    assert audit['status'] == 'audited'
    assert audit['candidate_pool_sha256'] == sha(OUT / 'private/candidate-pool.jsonl')
    thread_splits = defaultdict(set)
    for row in pool.values():
        thread_splits[row['record']['thread_id']].add(row['split'])
    crossed_threads = {key for key, splits in thread_splits.items() if key and len(splits) > 1}
    thread_removed = {key for key, row in pool.items() if row['record']['thread_id'] in crossed_threads}
    cluster_by_id = {}
    audit_removed = set()
    for cluster in audit['near_duplicate_clusters']:
        identifiers = cluster['record_ids']
        if len({pool[key]['split'] for key in identifiers}) > 1:
            audit_removed.update(identifiers)
        for key in identifiers:
            assert key not in cluster_by_id
            cluster_by_id[key] = cluster['cluster_id']
    assert set(cluster_by_id) == set(pool)
    assert set(audit['purge_record_ids']) == audit_removed
    assert set(purge['thread_purge_record_ids']) == thread_removed
    assert set(purge['audit_purge_record_ids']) == audit_removed
    removed = thread_removed | audit_removed
    assert set(purge['all_purge_record_ids']) == removed
    cells = defaultdict(list)
    for key, row in pool.items():
        if key not in removed:
            cells[row['account_key'], row['source_community'], row['cell']].append(row)
    units = read(OUT / 'private/units.json')
    units_by_id = {unit['text_id']: unit for unit in units}
    blocks = read(OUT / 'private/blocks.json')
    block_by_id = {block['block_id']: block for block in blocks}
    assert len(units_by_id) == len(units)
    groups = {split: defaultdict(set) for split in plan['splits']}
    qualification = defaultdict(Counter)
    occurrence_count = 0
    for unit in units:
        block = block_by_id[unit['block_id']]
        condition = block['conditions'][unit['condition']]
        expected_cells = [cells[author, block['home_community'] if cell == 'early' else condition['late_community'], cell]
            for author in block['account_keys'] for cell in ('early', 'late')]
        expected_budget = max(1000, min(3000, min(sum(row['retained_words'] for row in cell) for cell in expected_cells)))
        assert condition['target_B'] == expected_budget
        available = cells[unit['account_key'], unit['source_community'], unit['cell']]
        center = timestamp(plan['paired'][unit['cell']]['center_utc'])
        ranked = sorted(available, key=lambda row: (abs(timestamp(row['record']['created_utc']) - center), row['record']['created_utc'], row['record']['id']))
        base = []
        words = 0
        for row in ranked:
            base.append(row)
            words += row['retained_words']
            if words >= expected_budget and len(base) >= 8:
                break
        base = ordered(base)
        assert unit['base_record_ids'] == [row['record']['id'] for row in base]
        arm = unit['arm']
        if arm == 'full':
            kept = base
        elif arm == 'hash50':
            kept = [row for row in base if int(hashlib.sha256((plan['salts']['omission'] + ':' + row['record']['id']).encode()).hexdigest(), 16) % 2 == 0]
        elif arm == 'middle50':
            kept = base[:len(base)//4] + base[(3*len(base))//4:]
        elif arm == 'drop_Cornell':
            kept = [row for row in base if row['record']['subreddit'] != 'Cornell']
        else:
            raise AssertionError('Unregistered omission arm')
        expected_records = [row['record'] for row in kept]
        assert rows(OUT / unit['input']) == expected_records
        assert unit['record_ids'] == [row['id'] for row in expected_records]
        assert not set(unit['record_ids']) & removed
        expected_stats = stat(kept, expected_budget)
        assert all(unit['stats'][key] == value for key, value in expected_stats.items())
        assert (timestamp(unit['stats']['median_utc']) if unit['stats']['median_utc'] else None) == mtime(kept)
        snapshot = load_snapshot(OUT / unit['input'], OUT / unit['manifest'])
        assert snapshot.canonical_sha256 == unit['canonical_snapshot_sha256']
        for dimension, values in unit['groups'].items():
            assert values
            groups[unit['split']][dimension].update(values)
        for dimension, expected in [('thread', {row['record']['thread_id'] for row in kept}),
                                    ('source_document', {row['record']['id'] for row in kept}),
                                    ('near_duplicate_cluster', {cluster_by_id[row['record']['id']] for row in kept})]:
            assert set(unit['groups'].get(dimension, [])) == expected
        assert unit['groups']['author'] == [unit['account_key']]
        assert unit['input'].startswith('confirmation/' if unit['split'] == 'confirmation' else 'scored/')
        occurrence_count += len(kept)
        if arm == 'full':
            key = (unit['split'], unit['home_community'], unit['condition'])
            qualification[key]['units'] += 1
            qualification[key]['qualified_units'] += expected_stats['qualified_for_production_comparison']
            qualification[key]['empty_units'] += not kept
    # Verify metadata-only pairing independently over all three perfect matchings.
    selection = read(OUT / 'private/selection.json')
    selected_groups = defaultdict(list)
    for account in selection['accounts']:
        selected_groups[account['home_community'], account['split']].append(account)
    for (home, split), accounts in selected_groups.items():
        accounts.sort(key=lambda row: row['author_rank_hash'])
        times = [[mtime(cells[row['account_key'], home, cell]) for cell in ('early', 'late')] for row in accounts]
        missing = any(value is None for values in times for value in values)
        options = []
        for pairs in [((0,1),(2,3)), ((0,2),(1,3)), ((0,3),(1,2))]:
            cost = 0 if missing else sum(abs(times[a][c] - times[b][c]) for a, b in pairs for c in (0,1))
            hashes = tuple((accounts[a]['author_rank_hash'], accounts[b]['author_rank_hash']) for a,b in pairs)
            options.append((cost, hashes, pairs))
        cost, hashes, pairs = min(options)
        matching = [block for block in blocks if block['home_community'] == home and block['split'] == split]
        assert {tuple(block['account_keys']) for block in matching} == {(accounts[a]['account_key'], accounts[b]['account_key']) for a,b in pairs}
        assert all(block['matching']['summed_cell_median_gap_seconds'] == (None if missing else cost) for block in matching)
    for left, right in [('development','evaluation'), ('development','confirmation'), ('evaluation','confirmation')]:
        for dimension in ('author', 'thread', 'source_document', 'near_duplicate_cluster', 'related_sample'):
            assert not groups[left][dimension] & groups[right][dimension], 'Cross-split observed group overlap'
    for block in blocks:
        for condition in plan['paired']['conditions']:
            members = {(unit['account_key'], unit['cell']): unit for unit in units
                if unit['block_id'] == block['block_id'] and unit['condition'] == condition and unit['arm'] == 'full'}
            a, b = block['account_keys']
            for la, ra in [(a,a), (b,b), (a,b), (b,a)]:
                left, right = members[la,'early'], members[ra,'late']
                key = (block['split'], block['home_community'], condition)
                qualification[key]['planned_proxy_pair_slots'] += 1
                qualification[key]['qualified_pair_slots'] += left['stats']['qualified_for_production_comparison'] and right['stats']['qualified_for_production_comparison']
                if block['split'] != 'confirmation':
                    qualification[key]['scored_dataset_pair_slots'] += 1
    dataset_count = 0
    pair_counts = Counter()
    for path in sorted((OUT / 'scored/datasets').glob('*.json')):
        document = read(path)
        validate(document, 'evaluation_paired_text')
        assert document['protocol']['analysis_config_sha256'] == plan['analysis_config_sha256']
        assert document['protocol']['frozen_threshold'] is None
        for entry in document['texts']:
            unit = units_by_id[entry['text_id']]
            assert unit['split'] != 'confirmation'
            assert (path.parent / entry['input']).resolve() == (OUT / unit['input']).resolve()
            assert (path.parent / entry['manifest']).resolve() == (OUT / unit['manifest']).resolve()
            assert entry['groups'] == unit['groups']
        for pair in document['pairs']:
            left, right = (units_by_id[pair[side]] for side in ('left_text_id','right_text_id'))
            assert left['split'] == right['split'] == pair['split'] != 'confirmation'
            assert pair['label'] == ('same_author' if left['account_key'] == right['account_key'] else 'different_author')
            assert left['block_id'] == right['block_id'] and left['cell'] == 'early' and right['cell'] == 'late'
            pair_counts[pair['label']] += 1
        dataset_count += 1
    for pair in read(OUT / 'private/pair-observations.json'):
        left, right = (units_by_id[pair[side]] for side in ('left_text_id','right_text_id'))
        lt, rt = (timestamp(unit['stats']['median_utc']) if unit['stats']['median_utc'] else None for unit in (left,right))
        assert pair['pair_median_time_gap_seconds'] == (abs(lt-rt) if lt is not None and rt is not None else None)
        assert pair['left'] == left['stats'] and pair['right'] == right['stats']
    for name, expected in read(OUT / 'prepared-sha256.json').items():
        assert sha(OUT / name) == expected
    result = {'status': 'passed', 'scoring_performed': False, 'datasets_schema_verified': dataset_count,
        'units_verified': len(units), 'surviving_record_occurrences_verified': occurrence_count,
        'distinct_surviving_source_records_in_units': len({key for unit in units for key in unit['record_ids']}),
        'thread_purge_records': len(thread_removed), 'cross_split_threads': len(crossed_threads),
        'component_purge_records': len(audit_removed), 'union_purge_records': len(removed),
        'component_and_thread_purge_overlap_records': len(audit_removed & thread_removed),
        'all_pair_label_counts_including_method_repetition': dict(pair_counts),
        'full_arm_qualification': [{'split': key[0], 'home_community': key[1], 'condition': key[2], **value} for key, value in sorted(qualification.items())],
        'checks': ['schemas', 'source_fidelity_to_independently_verified_pool', 'all_omissions_without_refill',
            'registered_centered_whole_record_selection', 'minimum_cost_metadata_blocks', 'shared_B_and_overshoot',
            'guard_and_null_statistics', 'sample_times_and_pair_gaps', 'all_five_group_dimensions_disjoint',
            'physical_confirmation_exclusion', 'source_account_proxy_labels', 'prepared_hash_manifest'],
        'prepared_manifest_sha256': sha(OUT / 'prepared-sha256.json'), 'verifier_sha256': sha(Path(__file__))}
    target = ROOT / 'inventory/paired-prepared-check.json'
    with target.open('xb') as handle:
        handle.write(canonical_bytes(result))
    target.chmod(0o600)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
