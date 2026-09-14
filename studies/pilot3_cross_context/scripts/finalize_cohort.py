"""Evaluation-only cohort finalization and separately registered batch export.

No distance evaluator is imported or called. Real selection requires an exact
frozen binding and a completed Gate B audit of the complete frozen pool.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import time

import prepare_units as units
from cohort_selection import hash_quota_allocation

VERSION = 'pilot3-finalize-cohort-draft-v1'
TARGET = {'accounts': 60, 'blocks': 30, 'strata': 3}


class FinalizationFailure(ValueError):
    """Public-safe failure code only; never include source values."""


def require(condition, code):
    if not condition:
        raise FinalizationFailure(code)


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(',', ':')) + '\n').encode()


def sha_file(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def write_new(path, value, *, private=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600 if private else 0o644)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(canonical(value))


def validate_strata(strata):
    require(len(strata) == 3, 'three_strata_required')
    by_id = {s['id']: s for s in strata}
    require(len(by_id) == 3 and all(isinstance(s, str) and s for s in by_id),
            'distinct_stratum_ids_required')
    for s in by_id.values():
        require(len(s['communities']) == 2 and len(set(s['communities'])) == 2,
                'two_distinct_communities_required')
        require(set(s['scheme']) >= {'early', 'late'}, 'both_periods_required')
        early, late = units._period(s['scheme']['early']), units._period(s['scheme']['late'])
        require(early[1] <= late[0], 'periods_overlap')
    return by_id


def bind_pool_audit(pool, audit, strata, candidate_selection=None):
    summary = audit.get('summary', {})
    require(summary.get('status') == 'audited' and summary.get('gate_b_ready') is True and
            summary.get('available_content_and_grouping_audit_complete') is True and
            audit.get('actionable') is True and audit['engine_audit']['status'] == 'audited',
            'complete_available_content_grouping_audit_required')
    by_id, accounts, cells = {}, defaultdict(set), defaultdict(list)
    for entry in pool:
        record = entry['record']; rid, stamp, _ = units._entry(entry)
        account, sid = entry['account_key'], entry['stratum_id']
        require(rid not in by_id, 'repeated_pool_record_id')
        require(isinstance(account, str) and account == account.casefold() and
                account == record['account_id'].casefold(), 'pool_source_account_mismatch')
        require(sid in strata and entry['community'] in strata[sid]['communities'] and
                entry['community'] == record['subreddit'], 'pool_community_or_stratum_mismatch')
        require(entry['period'] in ('early', 'late'), 'invalid_pool_period')
        start, end = units._period(strata[sid]['scheme'][entry['period']])
        require(start <= stamp < end, 'pool_record_outside_frozen_period')
        require(isinstance(record.get('thread_id'), str) and record['thread_id'],
                'selected_thread_metadata_missing')
        accounts[account].add(sid)
        cells[sid, account, entry['community'], entry['period']].append(entry)
        by_id[rid] = entry
    require(by_id and all(len(s) == 1 for s in accounts.values()), 'invalid_pool_account_assignment')
    purged, survivors = audit['purge_record_ids'], audit['surviving_candidate_ids']
    require(len(set(purged)) == len(purged) and len(set(survivors)) == len(survivors) and
            not set(purged) & set(survivors) and set(purged) | set(survivors) == set(by_id),
            'audit_candidate_partition_mismatch')
    provenance = audit['record_provenance']
    require({rid for rid, row in provenance.items() if not row['historical']} == set(by_id),
            'audit_candidate_provenance_coverage_mismatch')
    for rid, entry in by_id.items():
        old = provenance[rid]
        require(old['source_record_id'] == rid and old['source_kind'] == 'comment' and
                old['account_key'] == entry['account_key'] and old['stratum_id'] == entry['stratum_id'] and
                old['cell'] == [entry['account_key'], entry['community'], entry['period']] and
                old['thread_id'] == entry['record']['thread_id'] and
                old['declared_retained_words'] == entry['retained_words'], 'audit_pool_metadata_mismatch')
    components = audit['engine_audit']['components']
    memberships = [rid for c in components for rid in c['record_ids']]
    require(len(memberships) == len(set(memberships)) and set(memberships) == set(provenance),
            'audit_content_component_coverage_mismatch')
    if candidate_selection is not None:
        selected = candidate_selection['selected_record_metadata']
        require(set(selected) == set(by_id), 'candidate_selection_record_set_mismatch')
        for rid, entry in by_id.items():
            expected = selected[rid]
            require(expected['record_id'] == rid and expected['created_utc'] == entry['record']['created_utc'] and
                    all(expected[k] == entry[k] for k in
                        ('account_key', 'stratum_id', 'community', 'period', 'retained_words')),
                    'candidate_selection_metadata_mismatch')
        assigned = {a: s for s, members in candidate_selection['allocation']['assigned'].items() for a in members}
        require(assigned == {a: next(iter(s)) for a, s in accounts.items()},
                'candidate_selection_account_assignment_mismatch')
    return by_id, set(survivors), cells


def block_groups(blocks, audit):
    """Merge every selected block connected by surviving content or source thread."""
    record_block, thread_blocks = {}, defaultdict(set)
    parent = {block['block_id']: block['block_id'] for block in blocks}
    by_block = {block['block_id']: block for block in blocks}

    def find(block):
        while parent[block] != block:
            parent[block] = parent[parent[block]]
            block = parent[block]
        return block

    def union(members):
        members = sorted(members)
        if members:
            root = min(find(b) for b in members)
            for b in members:
                parent[find(b)] = root

    for block in blocks:
        for entries in block['cells'].values():
            for entry in entries:
                rid, thread = entry['record']['id'], entry['record'].get('thread_id')
                require(rid not in record_block, 'record_reused_across_final_cells')
                require(isinstance(thread, str) and thread, 'selected_thread_metadata_missing')
                record_block[rid] = block['block_id']
                thread_blocks[thread].add(block['block_id'])
    component_by_record, edges = {}, []
    for component in audit['engine_audit']['components']:
        selected = [rid for rid in component['record_ids'] if rid in record_block]
        linked = {record_block[rid] for rid in selected}
        component_by_record.update({rid: component['cluster_id'] for rid in selected})
        union(linked)
        if len(linked) > 1:
            edges.append({'kind': 'content', 'group_id': component['cluster_id'], 'block_ids': sorted(linked)})
    require(set(component_by_record) == set(record_block), 'selected_component_membership_missing')
    for thread, linked in sorted(thread_blocks.items()):
        union(linked)
        if len(linked) > 1:
            edges.append({'kind': 'thread', 'group_id': thread, 'block_ids': sorted(linked)})
    members = defaultdict(list)
    for block in sorted(parent):
        members[find(block)].append(block)
    components = [sorted(v) for v in members.values()]
    components.sort()
    units_by_id = {f'resampling-unit-{i:02d}': values for i, values in enumerate(components, 1)}
    unit_by_block = {b: group for group, values in units_by_id.items() for b in values}
    effective = {s: len({unit_by_block[b] for b in parent if by_block[b]['stratum_id'] == s})
                 for s in sorted({b['stratum_id'] for b in blocks})}
    return {'unit_by_block': unit_by_block, 'units': units_by_id, 'cross_block_edges': edges,
            'content_component_by_record': component_by_record,
            'effective_units_by_stratum': effective, 'original_records_by_block': record_block,
            'anchor_dependence': 'All repeated anchors/methods/arms remain in their original block resampling unit.'}


def finalize(pool, audit, strata, *, candidate_selection=None):
    """Select fixed full quotas from audited survivors; never refill or score."""
    strata = validate_strata(strata)
    pool, survivors, original_cells = bind_pool_audit(pool, audit, strata, candidate_selection)
    eligible, selected_cells, statistics = {s: set() for s in strata}, {}, {}
    candidate_accounts = {s: {e['account_key'] for e in pool.values() if e['stratum_id'] == s} for s in strata}
    surviving_cells = {key: [e for e in rows if e['record']['id'] in survivors]
                       for key, rows in original_cells.items()}
    for sid, stratum in sorted(strata.items()):
        for account in sorted(candidate_accounts[sid]):
            cells = {f'{role}/{period}': surviving_cells.get((sid, account, community, period), [])
                     for role, community in zip(('X', 'Y'), stratum['communities'])
                     for period in ('early', 'late')}
            if any(len(rows) < 8 or sum(e['retained_words'] for e in rows) < 2000 for rows in cells.values()):
                continue
            full = {key: units.select_cell(rows, stratum['scheme'][key.split('/')[1]]) for key, rows in cells.items()}
            stats = units.four_cell_statistics(full, stratum['scheme'])
            eligible[sid].add(account)
            selected_cells[sid, account], statistics[sid, account] = full, stats
    allocation = hash_quota_allocation(eligible, limit=20)
    summary = {'version': VERSION, 'scores_computed': False, 'target': TARGET,
               'status': 'failed_surviving_capacity', 'candidate_records': len(pool),
               'audited_surviving_records': len(survivors), 'purged_records': len(pool) - len(survivors),
               'eligible_accounts_by_stratum': {s: len(a) for s, a in sorted(eligible.items())},
               'candidate_accounts_by_stratum': {s: len(a) for s, a in sorted(candidate_accounts.items())},
               'quota_counts': allocation['quota_counts'], 'selected_accounts': 0, 'selected_blocks': 0,
               'available_capacity_accounts': allocation['total_accounts'],
               'available_capacity_blocks': allocation['total_blocks'],
               'missing_accounts_by_stratum': {s: 20 - n for s, n in allocation['quota_counts'].items()},
               'no_post_audit_refills': True, 'audit_unknown_scope_flags': audit['summary'].get('unknown_scope_flags', [])}
    if allocation['total_accounts'] != 60 or any(n != 20 for n in allocation['quota_counts'].values()):
        return {'summary': summary, 'allocation': allocation, 'blocks': [], 'groups': None}
    blocks, public_blocks, matches = [], [], {}
    for index, (sid, stratum) in enumerate(sorted(strata.items()), 1):
        prepared = {a: statistics[sid, a]['cells'] for a in allocation['assigned'][sid]}
        matching = units.minimum_cost_perfect_matching(prepared, stratum['scheme'])
        matches[sid] = matching
        for number, pair in enumerate(matching['pairs'], 1):
            block_id = f'stratum-{index:02d}-block-{number:02d}'
            accounts = dict(zip(('A', 'B'), pair['accounts']))
            cells = {role + '/' + key: rows for role, account in accounts.items()
                     for key, rows in selected_cells[sid, account].items()}
            block = units.prepare_block(cells, block_id, stratum['scheme'], arm='full')
            blocks.append({'block_id': block_id, 'stratum_id': sid, 'stratum_public_id': f'stratum-{index:02d}',
                           'communities': stratum['communities'], 'period_bounds': stratum['scheme'],
                           'account_keys': accounts, 'source_accounts': block['source_accounts'],
                           'cells': cells, 'record_ids': {key: [e['record']['id'] for e in rows] for key, rows in cells.items()},
                           'comparisons': block['comparisons'], 'matching_cost': pair['cost']})
            public_blocks.append({'block_id': block_id, 'stratum_id': sid,
                                  'cell_statistics': block['statistics'], 'matching_cost': pair['cost'],
                                  'early_late_gaps': {role: statistics[sid, account]['early_late_gaps']
                                                     for role, account in accounts.items()}})
    groups = block_groups(blocks, audit)
    summary.update(status='cohort_selected_not_scored', selected_accounts=60, selected_blocks=30,
                   full_cells=240, planned_comparisons_per_method_arm=480,
                   planned_batches=360, planned_method_arm_comparisons=5760,
                   selected_original_records=len(groups['original_records_by_block']),
                   selected_retained_words=sum(e['retained_words'] for b in blocks for rows in b['cells'].values() for e in rows),
                   effective_units_by_stratum=groups['effective_units_by_stratum'],
                   total_resampling_units=len(groups['units']), residual_cross_block_relations=len(groups['cross_block_edges']),
                   final_cell_statistics=public_blocks)
    return {'summary': summary, 'allocation': allocation, 'matching': matches,
            'blocks': blocks, 'groups': groups, 'selected_record_ids': sorted(groups['original_records_by_block']),
            'unselected_surviving_record_ids': sorted(survivors - set(groups['original_records_by_block'])),
            'purged_record_ids': audit['purge_record_ids']}


def export_all_batches(output_root, cohort, *, registration, provenance, source_category='research_corpus'):
    """Write all 360 fixed batches only after separate protocol/cohort registration."""
    require(cohort['summary']['status'] == 'cohort_selected_not_scored' and len(cohort['blocks']) == 30 and
            cohort['summary']['selected_accounts'] == 60, 'full_final_cohort_required')
    require(registration.get('registered_before_evaluation') is True and
            bool(registration.get('preregistration_provenance')) and
            re.fullmatch(r'[0-9a-f]{64}', registration.get('protocol_sha256', '')) is not None,
            'separate_frozen_scoring_protocol_required')
    require(registration.get('final_cohort_sha256') == hashlib.sha256(canonical(cohort)).hexdigest(),
            'registered_final_cohort_hash_mismatch')
    require(source_category in ('research_corpus', 'synthetic'), 'explicit_source_category_required')
    output_root = Path(output_root)
    output_root.mkdir(parents=True, mode=0o700, exist_ok=False)
    output_root.chmod(0o700)
    write_new(output_root/'export-start-binding.json', {'status': 'started_not_scored',
              'registration': registration, 'exporter_sha256': sha_file(__file__),
              'prepare_units_sha256': sha_file(units.__file__)}, private=True)
    receipts, unit_metadata = [], []
    for block in cohort['blocks']:
        for arm in units.ARMS:
            prepared = units.prepare_block(block['cells'], block['block_id'], block['period_bounds'], arm)
            unit_metadata.extend({'stratum_id': block['stratum_id'], 'block_id': block['block_id'],
                                  'arm': arm, 'cell_id': key, **stats}
                                 for key, stats in prepared['statistics'].items())
            manifests, groups = {}, {}
            for key, rows in prepared['units'].items():
                manifests[key] = {'schema_version': '1.0.0', 'snapshot_id': block['block_id'] + '/' + arm + '/' + key,
                    'account_id': prepared['source_accounts'][key[0]], 'source_category': source_category,
                    'text_format': 'markdown', 'default_language': 'en',
                    'source_notes': 'Original supplied comments; English eligibility is a declared corpus assumption.',
                    'coverage': {'status': 'sampled', 'notes': 'Frozen whole-record subset; omissions are never refilled.'}}
                groups[key] = {'author': [block['account_keys'][key[0]]],
                               'related_sample': [cohort['groups']['unit_by_block'][block['block_id']]]}
                if rows:
                    groups[key]['thread'] = sorted({e['record']['thread_id'] for e in rows})
                    groups[key]['near_duplicate_cluster'] = sorted({cohort['groups']['content_component_by_record'][e['record']['id']] for e in rows})
            for method_index, method in enumerate(units.METHODS, 1):
                batch_id = block['block_id'] + '-' + arm + f'-method-{method_index:02d}'
                receipt = units.export_paired_batch(output_root/batch_id, prepared, method,
                    manifests=manifests, groups=groups, provenance=provenance, registration=registration)
                receipts.append({**receipt, 'batch_id': batch_id, 'block_id': block['block_id'],
                                 'stratum_id': block['stratum_id'], **method,
                                 'resampling_unit_id': cohort['groups']['unit_by_block'][block['block_id']],
                                 'dataset': batch_id + '/dataset.json',
                                 'dataset_sha256': receipt['input_hashes']['dataset.json']['sha256'],
                                 'input_file_receipts': receipt['input_hashes'],
                                 'input_hashes': {batch_id + '/' + name: value['sha256']
                                                  for name, value in receipt['input_hashes'].items()}})
    require(len(receipts) == 360, 'incomplete_fixed_export_count')
    summary = {'status': 'all_batches_prepared_not_scored', 'scores_computed': False,
               'batches': len(receipts), 'method_arm_comparisons': sum(r['pairs'] for r in receipts),
               'protocol_sha256': registration['protocol_sha256'],
               'final_cohort_sha256': registration['final_cohort_sha256'],
               'max_batch_bytes': max(r['invocation_input_bytes'] for r in receipts),
               'max_batch_unique_records': max(r['unique_records'] for r in receipts),
               'arm_batch_counts': dict(Counter(r['arm'] for r in receipts))}
    write_new(output_root/'batch-index.json', receipts, private=True)
    write_new(output_root/'unit-metadata.json', unit_metadata, private=True)
    write_new(output_root/'dependency-units.json', cohort['groups']['unit_by_block'], private=True)
    write_new(output_root/'export-summary.json', summary, private=True)
    return {'summary': summary, 'batches': receipts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('candidate-pool', 'audit', 'candidate-selection', 'candidate-plan', 'freeze', 'out-private', 'out-public'):
        parser.add_argument('--' + flag, type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3,) * 2)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError()))
    signal.alarm(1800)
    try:
        require(os.environ.get('AHAS_NETWORK_ISOLATION') == 'linux_seccomp_socket_denial', 'offline_runner_required')
        require(not args.out_private.exists() and not args.out_public.exists(), 'outputs_already_exist')
        freeze = json.loads(args.freeze.read_bytes())
        require(freeze.get('state') == 'frozen_before_final_selection', 'final_selection_freeze_required')
        bindings = {'candidate_pool': args.candidate_pool, 'audit': args.audit,
                    'candidate_selection': args.candidate_selection, 'candidate_plan': args.candidate_plan,
                    'wrapper': Path(__file__), 'prepare_units': Path(units.__file__),
                    'cohort_selection': Path(__file__).with_name('cohort_selection.py'),
                    'study_math': Path(__file__).with_name('study_math.py')}
        for key, path in bindings.items():
            require(sha_file(path) == freeze[key + '_sha256'], 'final_selection_frozen_input_mismatch')
        require(args.candidate_pool.stat().st_size <= 256 * 1024**2, 'candidate_byte_ceiling')
        pool = []
        with args.candidate_pool.open('rb') as handle:
            for line in handle:
                pool.append(json.loads(line))
                require(len(pool) <= 100000, 'candidate_record_ceiling')
        require(sum(e['retained_words'] for e in pool) <= 2000000, 'candidate_word_ceiling')
        plan = json.loads(args.candidate_plan.read_bytes())
        require(plan['full_target'] == TARGET and plan['phase'] == 'registered_score_free_candidate_pool',
                'full_candidate_plan_required')
        result = finalize(pool, json.loads(args.audit.read_bytes()), plan['strata'],
                          candidate_selection=json.loads(args.candidate_selection.read_bytes()))
        args.out_private.mkdir(parents=True, mode=0o700)
        args.out_private.chmod(0o700)
        write_new(args.out_private/'cohort.json', result, private=True)
        public = {**result['summary'], 'private_cohort_sha256': sha_file(args.out_private/'cohort.json'),
                  'freeze_sha256': sha_file(args.freeze), 'wrapper_sha256': sha_file(__file__)}
    except Exception as error:
        code = str(error) if type(error) is FinalizationFailure else {
            MemoryError: 'memory_allocation_failed', TimeoutError: 'wall_time_exceeded'
        }.get(type(error), 'unexpected_' + type(error).__name__)
        public = {'status': 'finalization_failed', 'reason_codes': [code], 'scores_computed': False}
    public.update(wall_seconds=time.monotonic() - started, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    try:
        if not args.out_public.exists():
            write_new(args.out_public, public)
        print(json.dumps(public, sort_keys=True), flush=True)
    finally:
        signal.alarm(0)
    return 0 if public['status'] == 'cohort_selected_not_scored' else 4


if __name__ == '__main__':
    raise SystemExit(main())
