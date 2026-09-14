#!/usr/bin/env python3
"""Independent pre-score verification of the frozen study's prepared inputs.

Preparatory checker: no real checking is authorized until the root run declares
the immutable inputs ready. No preparation, selection, matching, study-math, or
AHAS modules are imported. Original mappings are compared privately, never
printed. This verifies candidate-pool fidelity, not the original source audit.
"""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
import argparse
import json
import math
import os
from pathlib import Path
import re
import resource
import signal
import time

METHODS = (('cosine_distance_v1', 'retained_prose', 4),
           ('cosine_distance_v1', 'function_mask_v1', 4),
           ('function_word_js_v1', 'lexical_tokens', None))
ARMS = ('full', 'hash75', 'hash50', 'middle50')
CELLS = tuple(f'{a}/{c}/{p}' for a in 'AB' for c in 'XY' for p in ('early', 'late'))
CONFIG = '8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925'
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class CheckFailure(ValueError):
    """Only a fixed public-safe code is allowed in failures."""


def need(value, code):
    if not value:
        raise CheckFailure(code)


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode()


def sha_file(path):
    with Path(path).open('rb') as handle:
        return __import__('hashlib').file_digest(handle, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def seconds(value):
    need(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?', value), 'utc_integer_seconds_required')
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (dt - EPOCH).days * 86400 + (dt - EPOCH).seconds


def rational(x):
    x = Fraction(x)
    return {'numerator': x.numerator, 'denominator': x.denominator}


def frac(value):
    need(set(value) == {'numerator', 'denominator'} and type(value['numerator']) is int and
         type(value['denominator']) is int and value['denominator'] > 0, 'invalid_rational')
    return Fraction(value['numerator'], value['denominator'])


def utc(value):
    return (EPOCH + timedelta(microseconds=int(Fraction(value) * 1000000))).isoformat().replace('+00:00', 'Z')


def identity(account):
    return sha256(('ahas-pilot3-account-rank-v1:' + account.casefold()).encode()).hexdigest()


def chronology(rows):
    return sorted(rows, key=lambda e: (seconds(e['record']['created_utc']), e['record']['id']))


def select_prefix(rows, bounds):
    start, end = map(seconds, bounds)
    need(start < end, 'invalid_period')
    need(len({e['record']['id'] for e in rows}) == len(rows), 'duplicate_cell_record')
    for e in rows:
        need(type(e['retained_words']) is int and e['retained_words'] >= 20, 'record_word_guard')
        need(start <= seconds(e['record']['created_utc']) < end, 'record_outside_period')
    ranked = sorted(rows, key=lambda e: (abs(seconds(e['record']['created_utc']) * 2 - start - end),
                                         seconds(e['record']['created_utc']), e['record']['id']))
    total, chosen = 0, []
    for e in ranked:
        total += e['retained_words']
        chosen.append(e)
        if total >= 2000 and len(chosen) >= 8:
            return chronology(chosen)
    return None


def statistics(rows):
    words = sorted(e['retained_words'] for e in rows)
    dates = sorted(seconds(e['record']['created_utc']) for e in rows)
    n, total = len(words), sum(words)
    middle = Fraction(dates[(n-1)//2] + dates[n//2], 2) if n else None
    return {'records': n, 'retained_words': total, 'word_target': 2000,
            'word_overshoot': max(0, total-2000), 'word_shortfall': max(0, 2000-total),
            'record_shortfall': max(0, 8-n), 'longest_record_words': max(words, default=0),
            'longest_record_share': rational(Fraction(max(words), total)) if total else None,
            'nearest_rank_word_quantiles': {f'q{q}': words[math.ceil(n*q/100)-1] if n else None for q in (25, 50, 75, 90)},
            'first_utc': utc(dates[0]) if n else None, 'last_utc': utc(dates[-1]) if n else None,
            'median_utc': utc(middle) if n else None, 'median_timestamp': rational(middle) if n else None,
            'nonempty': bool(n), 'ordinary_volume_guards_met': n >= 8 and total >= 1000,
            'experimental_full_target_met': n >= 8 and total >= 2000}


def cost(left, right, bounds):
    total = Fraction(0)
    for cell in ('X/early', 'X/late', 'Y/early', 'Y/late'):
        a, b = statistics(left[cell]), statistics(right[cell])
        start, end = map(seconds, bounds[cell.split('/')[1]])
        total += abs(frac(a['median_timestamp'])-frac(b['median_timestamp'])) / (end-start)
        total += Fraction(abs(a['retained_words']-b['retained_words']), 2000)
        total += Fraction(abs(a['records']-b['records']), 8)
    return total


def exact_matching(cells, bounds):
    """Separate exhaustive pairing recurrence; exact Fraction costs and ties."""
    names = sorted(cells, key=lambda a: (identity(a), a))
    need(len(names) > 0 and len(names) % 2 == 0 and len(names) <= 20, 'matching_size')
    need(len({a.casefold() for a in names}) == len(names), 'matching_duplicate_identity')
    costs = {(i, j): cost(cells[a], cells[b], bounds) for i, a in enumerate(names)
             for j, b in enumerate(names) if i < j}
    scale = math.lcm(*(v.denominator for v in costs.values()))
    integers = {k: int(v*scale) for k, v in costs.items()}

    @lru_cache(None)
    def pair(remaining):
        if not remaining:
            return 0, ()
        first = (remaining & -remaining).bit_length()-1
        rest = remaining ^ (1 << first)
        best = None
        for second in range(first+1, len(names)):
            if rest & (1 << second):
                subcost, subpairs = pair(rest ^ (1 << second))
                candidate = integers[first, second] + subcost, ((first, second),) + subpairs
                if best is None or candidate < best:
                    best = candidate
        return best
    total, pairs = pair((1 << len(names))-1)
    return {'cost': rational(Fraction(total, scale)),
            'pairs': [{'accounts': [names[i], names[j]],
                       'account_hashes': [identity(names[i]), identity(names[j])],
                       'cost': rational(costs[i, j])} for i, j in pairs]}


def omission(rows, arm):
    rows = chronology(rows)
    need(arm in ARMS, 'unknown_omission_arm')
    if arm == 'full':
        return rows
    if arm == 'middle50':
        return rows[:len(rows)//4] + rows[3*len(rows)//4:]
    numerator, denominator = (3, 4) if arm == 'hash75' else (1, 2)
    return [e for e in rows if denominator * int.from_bytes(sha256(
        ('ahas-pilot3-omission-v1:' + e['record']['id']).encode()).digest(), 'big') < numerator * 2**256]


def design(block_id):
    result = []
    for a in 'AB':
        for c in 'XY':
            for same_community in (True, False):
                for same_account in (True, False):
                    category = ('same_account' if same_account else 'different_account') + '_' + (
                        'same_community' if same_community else 'different_community')
                    other_a = a if same_account else ('B' if a == 'A' else 'A')
                    other_c = c if same_community else ('Y' if c == 'X' else 'X')
                    result.append({'pair_id': f'{block_id}/{a}/{c}/{category}', 'block_id': block_id,
                        'anchor_id': f'{a}/{c}', 'left_cell_id': f'{a}/{c}/early',
                        'right_cell_id': f'{other_a}/{other_c}/late', 'category': category,
                        'context_condition': 'within_community' if same_community else 'cross_community',
                        'label': 'same_author' if same_account else 'different_author',
                        'label_meaning': 'source_account_identity_proxy'})
    return result


def independent_groups(blocks, audit):
    """Graph connected components, including transitive cross-stratum edges."""
    record_block, threads = {}, defaultdict(set)
    graph = {b['block_id']: set() for b in blocks}
    for b in blocks:
        for rows in b['cells'].values():
            for e in rows:
                rid = e['record']['id']
                need(rid not in record_block, 'record_reused_across_cells')
                record_block[rid] = b['block_id']
                threads[e['record']['thread_id']].add(b['block_id'])
    components, content = {}, {}
    for row in audit['engine_audit']['components']:
        members = set()
        for rid in row['record_ids']:
            if rid in record_block:
                need(rid not in content, 'repeated_content_component')
                content[rid] = row['cluster_id']
                members.add(record_block[rid])
        components[row['cluster_id']] = members
    need(set(content) == set(record_block), 'content_components_incomplete')
    edges = []
    for kind, groups in (('content', components), ('thread', threads)):
        for group, members in groups.items():
            for member in members:
                graph[member].update(members - {member})
            if len(members) > 1:
                edges.append({'kind': kind, 'group_id': group, 'block_ids': sorted(members)})
    connected, unseen = [], set(graph)
    while unseen:
        component, queue = set(), [min(unseen)]
        while queue:
            member = queue.pop()
            if member in component:
                continue
            component.add(member)
            queue.extend(graph[member] - component)
        unseen -= component
        connected.append(sorted(component))
    connected.sort()
    memberships = {f'resampling-unit-{i:02d}': c for i, c in enumerate(connected, 1)}
    mapping = {b: g for g, members in memberships.items() for b in members}
    effective = {s: len({mapping[b['block_id']] for b in blocks if b['stratum_id'] == s})
                 for s in {b['stratum_id'] for b in blocks}}
    return {'units': memberships, 'unit_by_block': mapping, 'effective_units_by_stratum': effective,
            'content_component_by_record': content, 'original_records_by_block': record_block,
            'cross_block_edges': sorted(edges, key=lambda e: (e['kind'], e['group_id']))}


def check_cohort(pool, audit, strata, exclusions, cohort, selection=None, *, synthetic_accounts=None):
    per_stratum = 20 if synthetic_accounts is None else synthetic_accounts
    need(type(per_stratum) is int and 0 < per_stratum <= 20 and per_stratum % 2 == 0, 'invalid_synthetic_size')
    need(len(strata) == 3 and len({s['id'] for s in strata}) == 3, 'three_strata_required')
    definitions = {s['id']: s for s in strata}
    excluded = {r['account_key'].casefold() for r in exclusions['accounts']}
    need(exclusions.get('complete_for_known_pilot_sources') is True, 'incomplete_historical_exclusions')
    if synthetic_accounts is None:
        need(len(excluded) == 57, 'historical_exclusion_count_changed')
    need(audit['summary']['status'] == 'audited' and audit['summary']['gate_b_ready'] is True and
         audit['summary']['available_content_and_grouping_audit_complete'] is True and
         audit['actionable'] is True and audit['engine_audit']['status'] == 'audited', 'audit_not_complete')
    by_id, account_strata, cells = {}, defaultdict(set), defaultdict(list)
    for e in pool:
        r = e['record']; rid, a, sid = r['id'], e['account_key'], e['stratum_id']
        need(rid not in by_id, 'duplicate_pool_record')
        need(a == a.casefold() == r['account_id'].casefold() and a not in excluded, 'protected_or_changed_account')
        need(sid in definitions and e['community'] == r['subreddit'] and
             e['community'] in definitions[sid]['communities'], 'pool_community_mismatch')
        need(r['kind'] == 'comment' and r['status'] == 'present' and r.get('language') in (None, 'en') and
             isinstance(r['text'], str) and isinstance(r.get('thread_id'), str) and r['thread_id'], 'ineligible_pool_record')
        need(type(e['retained_words']) is int and e['retained_words'] >= 20, 'pool_record_word_guard')
        need(e['period'] in ('early', 'late'), 'pool_period_mismatch')
        start, end = map(seconds, definitions[sid]['scheme'][e['period']])
        need(start <= seconds(r['created_utc']) < end, 'pool_record_outside_period')
        p = audit['record_provenance'][rid]
        need(p['historical'] is False and p['source_record_id'] == rid and p['source_kind'] == 'comment' and
             p['account_key'] == a and p['stratum_id'] == sid and p['cell'] == [a, e['community'], e['period']] and
             p['declared_retained_words'] == e['retained_words'] and p['thread_id'] == r['thread_id'], 'audit_provenance_mismatch')
        by_id[rid] = e; account_strata[a].add(sid)
        cells[sid, a, e['community'], e['period']].append(e)
    need(all(len(s) == 1 for s in account_strata.values()), 'candidate_account_assigned_multiple_strata')
    if selection is not None:
        need(set(selection['selected_record_metadata']) == set(by_id), 'candidate_selection_membership_mismatch')
        for rid, e in by_id.items():
            metadata = selection['selected_record_metadata'][rid]
            need(metadata['record_id'] == rid and metadata['created_utc'] == e['record']['created_utc'] and
                 all(metadata[k] == e[k] for k in ('account_key','stratum_id','community','period','retained_words')),
                 'candidate_selection_metadata_mismatch')
        assigned = {a: sid for sid, names in selection['allocation']['assigned'].items() for a in names}
        need(assigned == {a: next(iter(s)) for a, s in account_strata.items()}, 'candidate_selection_assignment_mismatch')
    survivors, purged = audit['surviving_candidate_ids'], audit['purge_record_ids']
    need(len(survivors) == len(set(survivors)) and len(purged) == len(set(purged)) and
         set(survivors).isdisjoint(purged) and set(survivors) | set(purged) == set(by_id), 'audit_partition_mismatch')
    survivors = set(survivors)
    eligible, selected = defaultdict(dict), {}
    for a, memberships in account_strata.items():
        sid = next(iter(memberships)); s = definitions[sid]
        need(seconds(s['scheme']['early'][1]) <= seconds(s['scheme']['late'][0]), 'overlapping_periods')
        candidate = {f'{role}/{period}': select_prefix([e for e in cells[sid,a,c,period] if e['record']['id'] in survivors],
                    s['scheme'][period]) for role, c in zip('XY', s['communities']) for period in ('early','late')}
        if all(v is not None for v in candidate.values()):
            eligible[sid][a] = candidate
    for sid in definitions:
        need(len(eligible[sid]) >= per_stratum, 'insufficient_surviving_capacity')
        selected[sid] = sorted(eligible[sid], key=identity)[:per_stratum]
    need(cohort['allocation']['assigned'] == selected, 'final_hash_quota_assignment_mismatch')
    need(cohort['allocation']['quota_counts'] == {s: per_stratum for s in definitions}, 'quota_counts_mismatch')
    blocks = cohort['blocks']
    need(len(blocks) == 3*per_stratum//2 and len({b['block_id'] for b in blocks}) == len(blocks), 'block_count_or_identity_mismatch')
    need(Counter(b['stratum_id'] for b in blocks) == Counter({s: per_stratum//2 for s in definitions}), 'stratum_block_count_mismatch')
    need(len({a for b in blocks for a in b['account_keys'].values()}) == 3*per_stratum, 'accounts_not_globally_distinct')
    public_stats = {b['block_id']: b for b in cohort['summary']['final_cell_statistics']}
    selected_ids = set()
    for i, sid in enumerate(sorted(definitions), 1):
        s = definitions[sid]
        expected_matching = exact_matching({a: eligible[sid][a] for a in selected[sid]}, s['scheme'])
        actual_matching = cohort['matching'][sid]
        need(actual_matching['cost'] == expected_matching['cost'] and actual_matching['pairs'] == expected_matching['pairs'],
             'nonminimal_or_changed_matching')
        for j, pair in enumerate(expected_matching['pairs'], 1):
            block_id = f'stratum-{i:02d}-block-{j:02d}'
            candidates = [b for b in blocks if b['block_id'] == block_id]
            need(len(candidates) == 1, 'block_identity_mismatch')
            b = candidates[0]
            need(b['stratum_id'] == sid and b['stratum_public_id'] == f'stratum-{i:02d}' and b['communities'] == s['communities'] and
                 b['period_bounds'] == s['scheme'] and b['account_keys'] == dict(zip('AB', pair['accounts'])), 'block_role_or_calendar_mismatch')
            need(set(b['cells']) == set(CELLS) and b['comparisons'] == design(block_id) and b['matching_cost'] == pair['cost'], 'block_design_mismatch')
            stats, gaps = {}, {}
            for role, account in b['account_keys'].items():
                gaps[role] = {}
                for cell, expected in eligible[sid][account].items():
                    key = role+'/'+cell; rows = b['cells'][key]
                    need(rows == expected, 'selected_whole_record_prefix_or_fidelity_mismatch')
                    ids = [e['record']['id'] for e in rows]
                    need(b['record_ids'][key] == ids and not selected_ids.intersection(ids), 'selected_record_identity_or_reuse')
                    selected_ids.update(ids)
                    need(all(e['record']['account_id'] == b['source_accounts'][role] for e in rows), 'original_account_case_mismatch')
                    stats[key] = statistics(rows)
                for community in 'XY':
                    early, late = stats[f'{role}/{community}/early'], stats[f'{role}/{community}/late']
                    gaps[role][community] = {'median_gap_seconds': rational(frac(late['median_timestamp'])-frac(early['median_timestamp'])),
                        'nearest_writing_gap_seconds': seconds(late['first_utc'])-seconds(early['last_utc'])}
            need(public_stats[block_id] == {'block_id': block_id, 'stratum_id': sid, 'cell_statistics': stats,
                 'matching_cost': pair['cost'], 'early_late_gaps': gaps}, 'full_cell_statistics_mismatch')
    need(cohort['selected_record_ids'] == sorted(selected_ids) and cohort['unselected_surviving_record_ids'] == sorted(survivors-selected_ids) and
         cohort['purged_record_ids'] == audit['purge_record_ids'], 'final_candidate_partition_mismatch')
    groups = independent_groups(blocks, audit)
    for key, value in groups.items():
        actual = cohort['groups'][key]
        if key == 'cross_block_edges':
            actual = sorted(actual, key=lambda e: (e['kind'], e['group_id']))
        need(actual == value, 'dependency_group_mismatch')
    need(cohort['summary']['status'] == 'cohort_selected_not_scored' and cohort['summary']['scores_computed'] is False,
         'cohort_state_mismatch')
    need(cohort['summary']['selected_accounts'] == 3*per_stratum and cohort['summary']['selected_blocks'] == len(blocks), 'cohort_summary_counts_mismatch')
    return {'status': 'passed', 'accounts': 3*per_stratum, 'blocks': len(blocks), 'full_cells': 8*len(blocks),
            'selected_records': len(selected_ids), 'candidate_records': len(pool), 'audited_survivors': len(survivors),
            'exact_matchings_verified': 3, 'resampling_units': len(groups['units']),
            'effective_units_by_stratum': groups['effective_units_by_stratum'], 'style_scores_computed': 0,
            'preprocessor_calls': 0, 'original_archives_read': 0, 'private_source_values_published': False}


def child(root, name):
    path = Path(name)
    need(not path.is_absolute() and '..' not in path.parts, 'unregistered_input_path')
    resolved = (root/path).resolve()
    need(resolved.is_relative_to(root.resolve()), 'input_outside_prepared_root')
    return resolved


def check_exports(prepared, cohort, *, synthetic=False):
    prepared = Path(prepared).resolve()
    index, metadata = read(prepared/'batch-index.json'), read(prepared/'unit-metadata.json')
    blocks = {b['block_id']: b for b in cohort['blocks']}
    expected = {(b, arm, method) for b in blocks for arm in ARMS for method in METHODS}
    if not synthetic:
        need(len(blocks) == 30, 'full_export_design_required')
    need(len(index) == len(expected), 'export_batch_count_mismatch')
    need(read(prepared/'dependency-units.json') == cohort['groups']['unit_by_block'], 'export_dependency_mismatch')
    unit_lookup = {(r['block_id'], r['arm'], r['cell_id']): r for r in metadata}
    need(len(unit_lookup) == len(metadata) == len(blocks)*32, 'export_unit_metadata_count_mismatch')
    byte_total = 0
    for item in index:
        method = tuple(item[k] for k in ('method_id','view','n'))
        key = item['block_id'], item['arm'], method
        need(key in expected, 'duplicate_or_unplanned_export_batch')
        expected.remove(key)
        block, arm = blocks[item['block_id']], item['arm']
        need(item['stratum_id'] == block['stratum_id'] and item['resampling_unit_id'] == cohort['groups']['unit_by_block'][block['block_id']],
             'export_block_group_mismatch')
        dataset_path = child(prepared, item['dataset']); dataset = read(dataset_path)
        need(sha_file(dataset_path) == item['dataset_sha256'], 'export_dataset_hash_mismatch')
        need(set(dataset) == {'schema_version','format','dataset_id','provenance','label_definition','protocol','texts','pairs'}, 'unexpected_dataset_fields')
        protocol = dataset['protocol']
        need(dataset['schema_version'] == '1.0.0' and dataset['format'] == 'paired_text' and
             'same-source-account' in dataset['label_definition'] and 'identity proxies' in dataset['label_definition'] and
             protocol['analysis_config_sha256'] == CONFIG and protocol['registered_before_evaluation'] is True and
             protocol['frozen_threshold'] is None and protocol['distance'] == dict(zip(('method_id','view','n'),method)), 'export_protocol_mismatch')
        need(item['protocol_sha256'] in protocol['preregistration_provenance'], 'export_protocol_hash_missing')
        need(len(dataset['texts']) == 8 and {t['text_id'] for t in dataset['texts']} == set(CELLS), 'export_snapshot_count_mismatch')
        planned = [{'pair_id': p['pair_id'], 'left_text_id': p['left_cell_id'], 'right_text_id': p['right_cell_id'],
                    'split': 'evaluation', 'label': p['label']} for p in design(block['block_id'])]
        need(dataset['pairs'] == planned, 'export_contrast_identity_mismatch')
        referenced = {str(dataset_path.relative_to(prepared))}; unique = set()
        for text in dataset['texts']:
            need(set(text) == {'text_id','input','manifest','groups'}, 'hidden_selector_or_text_field')
            cell = text['text_id']; rows = omission(block['cells'][cell], arm)
            for e in rows:
                need(e['record']['id'] not in unique, 'export_record_reuse')
                unique.add(e['record']['id'])
            path = child(dataset_path.parent, text['input']); manifest_path = child(dataset_path.parent, text['manifest'])
            referenced.update((str(path.relative_to(prepared)), str(manifest_path.relative_to(prepared))))
            # Candidate mappings contain original text/code points and all source
            # metadata. Canonical serialization changes no mapping field or text.
            raw = b''.join(e.get('record_jsonl', canonical(e['record'])) for e in rows)
            need(path.read_bytes() == raw, 'export_original_record_bytes_mismatch')
            manifest = read(manifest_path)
            period_start, period_end = map(seconds, block['period_bounds'][cell.split('/')[2]])
            need(manifest['account_id'] == block['source_accounts'][cell[0]] and manifest['text_format'] == 'markdown' and
                 manifest['default_language'] == 'en' and manifest['coverage']['status'] == 'sampled' and
                 manifest['source_category'] in ('research_corpus','synthetic') and
                 manifest['snapshot_id'] == block['block_id']+'/'+arm+'/'+cell and
                 manifest['coverage']['start_utc'] == utc(period_start) and manifest['coverage']['end_utc'] == utc(period_end) and
                 manifest['license_notes'] == 'Authorized by the user for local evaluation only; source prose is private and must not be redistributed.',
                 'export_manifest_mismatch')
            groups = {'author': [block['account_keys'][cell[0]]],
                      'related_sample': [cohort['groups']['unit_by_block'][block['block_id']]]}
            if rows:
                groups['source_document'] = sorted(e['record']['id'] for e in rows)
                groups['thread'] = sorted({e['record']['thread_id'] for e in rows})
                groups['near_duplicate_cluster'] = sorted({cohort['groups']['content_component_by_record'][e['record']['id']] for e in rows})
            need(text['groups'] == groups, 'export_observed_group_mismatch')
            need(unit_lookup[block['block_id'],arm,cell] == {'stratum_id': block['stratum_id'], 'block_id': block['block_id'],
                 'arm': arm, 'cell_id': cell, **statistics(rows)}, 'export_unit_statistics_mismatch')
        need(set(item['input_hashes']) == referenced and len(referenced) == 17, 'export_file_binding_coverage')
        size = 0
        for name in referenced:
            path = child(prepared, name)
            need(sha_file(path) == item['input_hashes'][name], 'export_input_hash_mismatch')
            size += path.stat().st_size
        need(size == item['invocation_input_bytes'] and size <= 50*1024**2 and
             len(unique) == item['unique_records'] and len(unique) <= 10000, 'ordinary_input_resource_limit')
        byte_total += size
    need(not expected, 'missing_export_batch')
    return {'prepared_batches_verified': len(index), 'comparisons_verified': len(index)*16,
            'omission_unit_statistics_verified': len(metadata), 'hash_bound_input_files': len(index)*17,
            'sum_invocation_input_bytes': byte_total, 'all_three_methods_and_four_arms': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('plan','candidate-pool','candidate-selection','audit','exclusions','cohort','prepared','out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (4*1024**3,)*2)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError()))
    signal.alarm(300)
    started = time.monotonic()
    inputs = {name: getattr(args, name.replace('-','_')) for name in
              ('plan','candidate-pool','candidate-selection','audit','exclusions','cohort')}
    binding = {'status': 'frozen_before_independent_input_check', 'checker_sha256': sha_file(__file__),
               'input_sha256': {name: sha_file(path) for name,path in inputs.items()},
               'batch_index_sha256': sha_file(args.prepared/'batch-index.json'),
               'limits': {'wall_seconds': 300, 'address_space_bytes': 4*1024**3,
                          'candidate_records': 100000, 'candidate_bytes': 256*1024**2},
               'style_scores_computed': 0, 'preprocessor_calls': 0}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.with_suffix('.start-binding.json').open('xb') as handle:
        handle.write(canonical(binding))
    try:
        need(not args.out.exists(), 'output_already_exists')
        need(args.candidate_pool.stat().st_size <= 256*1024**2, 'candidate_byte_limit')
        pool = []
        with args.candidate_pool.open('rb') as handle:
            for line in handle:
                pool.append(json.loads(line))
                need(len(pool) <= 100000, 'candidate_record_limit')
        cohort = read(args.cohort)
        report = check_cohort(pool, read(args.audit), read(args.plan)['strata'], read(args.exclusions), cohort,
                              read(args.candidate_selection))
        report.update(check_exports(args.prepared, cohort))
    except Exception as error:
        report = {'status': 'failed', 'reason_codes': [str(error) if type(error) is CheckFailure else 'unexpected_'+type(error).__name__],
                  'style_scores_computed': 0, 'preprocessor_calls': 0, 'private_source_values_published': False}
    report.update(checker_sha256=binding['checker_sha256'], input_sha256=binding['input_sha256'],
                  batch_index_sha256=binding['batch_index_sha256'], wall_seconds=time.monotonic()-started,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    with args.out.open('xb') as handle:
        handle.write(canonical(report))
    signal.alarm(0)
    print(json.dumps(report, sort_keys=True))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
