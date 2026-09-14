#!/usr/bin/env python3
"""Independent Gate B result reconciliation from metadata and relation membership.

Never opens historical source records, imports AHAS/the audit, or recomputes
content features. Candidate JSONL is projected to metadata without inspecting or
exporting its prose. Reported hyperedges are independently joined with graph
traversal, then content and thread purge rules are evaluated separately.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import signal
import time

MAX_ROWS, MAX_SECONDS, MAX_AS, MAX_OUTPUT = 1_000_000, 300, 4 * 1024**3, 100 * 1024**2
PAIR_CAP = 2_000_000
TITLE_PREFIX = '__ahas_pilot3_historical_title_v1__:'


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def fingerprint(path):
    path = Path(path)
    with path.open('rb') as stream:
        hashed = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'sha256': hashed, 'bytes': path.stat().st_size}


def read(path):
    return json.loads(Path(path).read_bytes())


class Checks:
    def __init__(self):
        self.count, self.failures = 0, []

    def __call__(self, condition, message):
        self.count += 1
        if not condition:
            self.failures.append(message)


def graph_components(identifiers, relations):
    """Independent breadth-first traversal, with one star per hyperedge."""
    identifiers = set(identifiers)
    adjacency = {i: set() for i in identifiers}
    for relation in relations:
        members = relation['record_ids']
        if len(members) < 2 or len(members) != len(set(members)) or not set(members) <= identifiers:
            raise ValueError('invalid_relation_membership')
        center = members[0]
        for other in members[1:]:
            adjacency[center].add(other)
            adjacency[other].add(center)
    unseen, components = set(identifiers), []
    for first in sorted(identifiers):
        if first not in unseen:
            continue
        unseen.remove(first)
        pending, found = [first], {first}
        while pending:
            for neighbor in adjacency[pending.pop()] & unseen:
                unseen.remove(neighbor)
                found.add(neighbor)
                pending.append(neighbor)
        components.append(sorted(found))
    return sorted(components)


def independent_purges(provenance, components):
    candidates = {i for i, item in provenance.items() if not item['historical']}
    reasons = defaultdict(set)
    def classify(members, prefix):
        new = set(members) & candidates
        labels = {tuple(provenance[i]['cell']) for i in new}
        flags = ([prefix + '_historical_boundary'] if new and set(members) - candidates else [])
        flags += [prefix + '_cross_candidate_cells'] if len(labels) > 1 else []
        for identifier in new:
            reasons[identifier].update(flags)
        return bool(flags)
    for component in components:
        classify(component, 'content')
    threads = defaultdict(list)
    for identifier, item in provenance.items():
        if item['thread_id']:
            threads[item['thread_id']].append(identifier)
    crossed = []
    for thread, members in sorted(threads.items()):
        if classify(members, 'thread'):
            crossed.append({'thread_id': thread, 'record_ids': sorted(members)})
    reasons = {i: sorted(kinds) for i, kinds in sorted(reasons.items()) if kinds}
    return reasons, crossed, sorted(candidates - set(reasons))


def reconcile(result, candidate_metadata, historical_metadata):
    check = Checks()
    summary, audit, provenance = result['summary'], result['engine_audit'], result['record_provenance']
    check(summary['status'] == audit['status'] == 'audited' and audit['summary']['complete'] is True, 'Both wrapper and engine completed')
    check(len(provenance) <= MAX_ROWS, 'Audited metadata record ceiling')
    candidates = {i for i, p in provenance.items() if not p['historical']}
    history = set(provenance) - candidates
    bodies = {i for i in history if provenance[i]['text_component'] == 'body'}
    titles = history - bodies
    check(candidates == set(candidate_metadata), 'Candidate node coverage matches frozen preparation')
    check(bodies == set(historical_metadata), 'Historical original node coverage matches full protection inventory')
    for identifier in candidates:
        p, metadata = provenance[identifier], candidate_metadata.get(identifier, {})
        check(all(p.get(key) == metadata.get(key) for key in ('account_key', 'stratum_id', 'cell', 'thread_id', 'declared_retained_words')), 'Candidate identity/cell/thread/word metadata binding')
        check(p['source_record_id'] == identifier and p['source_kind'] == 'comment' and p['text_component'] == 'body' and bool(p['thread_id']), 'Candidate source node guard')
    for identifier in bodies:
        p, metadata = provenance[identifier], historical_metadata.get(identifier, {})
        check(all(p.get(key) == metadata.get(key) for key in ('account_key', 'audit_split', 'original_split', 'thread_id', 'source_kind')), 'Historical identity/split/thread/kind metadata binding')
        check(p['source_record_id'] == identifier and sorted(p['original_references']) == sorted(metadata.get('original_references', [])), 'Historical original references preserved')
    for identifier in titles:
        p = provenance[identifier]
        original = p['source_record_id']
        check(identifier == TITLE_PREFIX + hashlib.sha256(original.encode()).hexdigest() and original in bodies and p['text_component'] == 'title' and p['source_kind'] == 'submission', 'Reserved historical title node identity')
        if original in bodies:
            check(all(p[k] == provenance[original][k] for k in ('account_key', 'audit_split', 'original_split', 'thread_id', 'original_references')), 'Title retains original body grouping metadata')
    check(not ({provenance[i]['account_key'] for i in candidates} & {provenance[i]['account_key'] for i in history}), 'No source account crosses candidate/history boundary')
    check(all(p['account_key'] == p['account_key'].casefold() for p in provenance.values()), 'Canonical source account keys')
    account_strata = defaultdict(set)
    for i in candidates:
        account_strata[provenance[i]['account_key']].add(provenance[i]['stratum_id'])
    check(all(len(s) == 1 for s in account_strata.values()), 'Candidate accounts belong to one stratum only')
    components = graph_components(provenance, audit['relations'])
    saved_components = audit['components']
    flattened = [i for component in saved_components for i in component['record_ids']]
    check(len(flattened) == len(set(flattened)) and set(flattened) == set(provenance), 'Saved components partition every body/title/candidate node once')
    check(sorted(sorted(c['record_ids']) for c in saved_components) == components, 'Breadth-first hyperedge graph exactly reconstructs saved components')
    relation_ids, relations_by_kind, incidence = set(), Counter(), {}
    def split(identifier):
        p = provenance[identifier]
        return p['audit_split'] if p['historical'] else 'evaluation'
    for relation in audit['relations']:
        kind, members = relation['kind'], relation['record_ids']
        check(kind in {'exact', 'near', 'template', 'quotation'}, 'Only registered content relation kinds')
        item = {k: v for k, v in relation.items() if k != 'relation_id'}
        check(relation['relation_id'] == 'relation-' + digest({'method': audit['summary']['method']['method_id'], **item}), 'Content relation canonical hash')
        check(relation['relation_id'] not in relation_ids, 'Content relation IDs unique')
        relation_ids.add(relation['relation_id'])
        relations_by_kind[kind] += 1
        if kind == 'near':
            left, right, shared, union = (relation[k] for k in ('left_shingles', 'right_shingles', 'shared_unique_shingles', 'union_unique_shingles'))
            check(len(members) == 2 and shared >= 5 and min(left, right) >= shared and union == left + right - shared, 'Near relation cardinality and set arithmetic')
            rules = (['jaccard_80_100'] if 100 * shared >= 80 * union else []) + (['left_containment_90_100'] if 100 * shared >= 90 * left else []) + (['right_containment_90_100'] if 100 * shared >= 90 * right else [])
            check(bool(rules) and relation['match_rules'] == rules, 'Near relation thresholds unchanged')
        elif kind == 'template':
            check(len({provenance[i]['account_key'] for i in members}) >= 3 and relation['signature_count'] >= 1, 'Template protects at least three distinct source accounts')
        elif kind == 'quotation':
            check(set(relation['quote_record_ids']) | set(relation['retained_record_ids']) == set(members), 'Quotation/retained memberships cover relation')
            check(all(row['record_id'] in relation['quote_record_ids'] and 1 <= row['source_line_range'][0] <= row['source_line_range'][1] for row in relation['quote_source_line_ranges']), 'Quotation source range metadata valid')
    for kind in ('exact', 'near', 'template', 'quotation'):
        count = Counter()
        for relation in audit['relations']:
            if relation['kind'] != kind:
                continue
            members = relation['record_ids']
            split_counts = Counter(split(i) for i in members)
            account_counts = Counter(provenance[i]['account_key'] for i in members)
            pairs = len(members) * (len(members) - 1) // 2
            same_split = sum(n * (n - 1) // 2 for n in split_counts.values())
            same_account = sum(n * (n - 1) // 2 for n in account_counts.values())
            count.update(relation_count=1, record_memberships=len(members), same_split_pair_memberships=same_split,
                         cross_split_pair_memberships=pairs-same_split, same_account_pair_memberships=same_account, cross_account_pair_memberships=pairs-same_account)
        incidence[kind] = {k: count[k] for k in ('relation_count', 'record_memberships', 'same_split_pair_memberships', 'cross_split_pair_memberships', 'same_account_pair_memberships', 'cross_account_pair_memberships')}
    check(audit['summary']['relation_incidence'] == incidence, 'Content hyperedge incidence independently recounted')
    counts = {kind: relations_by_kind[kind] for kind in ('exact', 'near', 'template', 'quotation')}
    check(summary['content_relation_counts'] == audit['summary']['relation_counts'] == counts, 'All content relation counts agree')
    clusters, old_excluded, unobserved = {}, [], []
    for component in saved_components:
        members = component['record_ids']
        expected_cluster = 'cluster-' + digest({'definition_sha256': audit['summary']['method']['definition_sha256'], 'record_ids': sorted(members)})
        check(component['cluster_id'] == expected_cluster, 'Component identity hash')
        clusters.update({i: expected_cluster for i in members})
        memberships = sorted({split(i) for i in members})
        check(component['split_memberships'] == memberships and component['account_count'] == len({provenance[i]['account_key'] for i in members}), 'Component source/split metadata independently counted')
        check(set(component['content_unobservable_record_ids']) <= set(members), 'Unobservable nodes belong to their component')
        unobserved += component['content_unobservable_record_ids']
        if len(memberships) > 1:
            old_excluded += members
    check(audit['cluster_by_id'] == dict(sorted(clusters.items())) and audit['excluded_ids'] == sorted(old_excluded), 'Frozen engine grouping and split-only exclusions reconcile')
    reasons, crossed, survivors = independent_purges(provenance, components)
    check(result['purge_reasons'] == reasons and result['purge_record_ids'] == sorted(reasons), 'Independent symmetric content/thread purge IDs and reasons')
    check(result['crossing_threads'] == crossed, 'Independent crossing thread groups')
    check(result['surviving_candidate_ids'] == survivors, 'Independent survivor IDs exactly complement purges')
    check(set(result['purge_record_ids']).isdisjoint(result['surviving_candidate_ids']) and set(result['purge_record_ids']) | set(result['surviving_candidate_ids']) == candidates, 'No missing or duplicated candidate dispositions')
    missing_bodies = sum(not provenance[i]['thread_id'] for i in bodies)
    missing_nodes = sum(not provenance[i]['thread_id'] for i in history)
    flags = (['unobserved_content_relationships_unknown'] if unobserved else [])
    check(audit['summary']['unknown_scope_flags'] == flags and audit['summary']['content_unobservable_record_count'] == len(unobserved), 'Engine unknown content counts and flags reconcile')
    if missing_bodies:
        flags.append('historical_thread_relationships_unknown')
    check(summary['unknown_scope_flags'] == sorted(flags) and summary['independence_scope_complete'] == (not flags), 'Unknown content/grouping scope remains explicit')
    check(summary['available_content_and_grouping_audit_complete'] == summary['gate_b_ready'] == (missing_bodies == 0), 'Gate B readiness requires complete available grouping')
    check(summary['historical_missing_thread_records'] == missing_bodies and summary['historical_missing_thread_audit_nodes'] == missing_nodes, 'Missing historical grouping counts')
    check(summary['historical_body_records'] == len(bodies) and summary['historical_title_protection_records'] == len(titles) and summary['candidate_records'] == len(candidates), 'All original/title/candidate node counts')
    check(summary['candidate_retained_words'] == sum(provenance[i]['declared_retained_words'] for i in candidates), 'Candidate retained words reconcile')
    check(summary['purged_candidate_records'] == len(reasons) and summary['surviving_candidate_records'] == len(survivors), 'Candidate disposition counts')
    check(summary['purge_reason_record_counts'] == dict(Counter(k for v in reasons.values() for k in v)), 'Purge reason counts independently reconciled')
    check(summary['content_component_count'] == audit['summary']['component_count'] == len(components), 'Content component counts')
    check(summary['independent_engine_eligible_candidate_pairs'] == summary['engine_candidate_pair_count'] == audit['summary']['candidate_pair_count'] <= summary['independent_candidate_pairs'] <= PAIR_CAP, 'Both original pair count checks remain within cap')
    check(summary['max_candidate_pairs'] == audit['summary']['max_candidate_pairs'] == PAIR_CAP and summary['independent_count_is_lower_bound'] is False and audit['summary']['candidate_pair_count_is_lower_bound'] is False, 'Full pair counts and unchanged two-million caps')
    check(summary['scores_computed'] is False and audit['summary']['no_style_distances_calculated'] is True and result['actionable'] is True, 'Completed audit remains unscored')
    return {'status': 'pass' if not check.failures else 'fail', 'checks_performed': check.count, 'failed_checks': sorted(set(check.failures)),
            'audit_nodes': len(provenance), 'candidate_records': len(candidates), 'historical_body_records': len(bodies), 'historical_title_records': len(titles),
            'content_components': len(components), 'content_relation_counts': counts, 'crossing_thread_groups': len(crossed),
            'purged_candidate_records': len(reasons), 'surviving_candidate_records': len(survivors), 'gate_b_ready': summary['gate_b_ready'],
            'unknown_scope_flags': summary['unknown_scope_flags'], 'identifiers_exported': False, 'historical_source_prose_files_opened': 0,
            'style_scores_computed': 0, 'preprocessing_calls': 0}


def verify(args):
    started = time.monotonic()
    check = Checks()
    freeze, public, result = read(args.freeze), read(args.public_audit), read(args.audit)
    check(freeze['state'] == 'frozen_before_audit' and public['freeze_sha256'] == fingerprint(args.freeze)['sha256'], 'Audit freeze hash bound')
    check(public['private_audit_sha256'] == fingerprint(args.audit)['sha256'], 'Private result hash bound')
    for name, path in (('candidate_pool', args.candidate_pool), ('historical_inventory', args.historical_inventory), ('candidate_selection', args.candidate_selection), ('wrapper', args.wrapper), ('engine', args.engine), ('rules', args.rules), ('offline_runner', args.offline_runner)):
        check(fingerprint(path)['sha256'] == freeze[name + '_sha256'], 'Original frozen input bytes: ' + name)
    for name in ('wrapper', 'engine', 'rules'):
        check(public[name + '_sha256'] == freeze[name + '_sha256'], 'Public executed identity: ' + name)
    check(all(public.get(key) == value for key, value in result['summary'].items()), 'Public summary equals private summary')
    receipt = read(args.receipt)
    prefix = str(args.receipt).removesuffix('.receipt.json')
    for suffix in ('stdout.log', 'stderr.log'):
        check(fingerprint(prefix + '.' + suffix) == receipt['outputs'][suffix], 'Original audit execution log hash: ' + suffix)
    check(read(prefix + '.stdout.log') == public, 'Original audit stdout matches saved public result')
    check(receipt['exit_code'] == (0 if public.get('gate_b_ready') else 4), 'Original audit exit agrees with available grouping readiness')
    check(str(args.offline_runner) in receipt['argv'], 'Original execution includes bound socket-denial offline runner')
    historical = read(args.historical_inventory)
    check(historical['complete_for_requested_known_protection_sources'] is True, 'Full registered history metadata inventory')
    hm, rows = {}, 0
    for source in historical['files']:
        for row in source['records_metadata']:
            rows += 1
            if rows > MAX_ROWS:
                raise RuntimeError('metadata_record_limit')
            identifier = row['record_id']
            projected = {k: row[k] for k in ('account_key', 'original_split', 'thread_id', 'audit_split')}
            projected['source_kind'] = row['kind']
            if identifier in hm:
                check(all(hm[identifier][k] == v for k, v in projected.items()), 'Repeated historical metadata agrees')
            else:
                hm[identifier] = {**projected, 'original_references': []}
            hm[identifier]['original_references'].append(source['source_id'])
    selected = read(args.candidate_selection)['selected_record_metadata']
    cm = {}
    with args.candidate_pool.open('rb') as handle:
        for line in handle:
            rows += 1
            if rows > MAX_ROWS:
                raise RuntimeError('metadata_record_limit')
            entry = json.loads(line)
            record = entry['record']
            identifier = record['id']
            check(identifier not in cm and identifier in selected, 'Every pool record appears once in preparation selection')
            p = selected.get(identifier, {})
            check(all(entry.get(k) == p.get(k) for k in ('account_key', 'stratum_id', 'community', 'period', 'retained_words')) and record['created_utc'] == p.get('created_utc') and record['subreddit'] == entry['community'], 'Candidate pool metadata matches frozen preparation')
            cm[identifier] = {'account_key': entry['account_key'], 'stratum_id': entry['stratum_id'], 'cell': [entry['account_key'], entry['community'], entry['period']], 'thread_id': record['thread_id'], 'declared_retained_words': entry['retained_words']}
    check(set(cm) == set(selected), 'No prepared record missing from audited pool')
    report = reconcile(result, cm, hm)
    report['checks_performed'] += check.count
    report['failed_checks'] = sorted(set(report['failed_checks'] + check.failures))
    report['status'] = 'fail' if report['failed_checks'] else 'pass'
    report.update(wall_seconds=time.monotonic()-started, peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                  metadata_rows=rows, checker_sha256=fingerprint(__file__)['sha256'],
                  input_hashes={name: fingerprint(getattr(args, name)) for name in ('freeze', 'public_audit', 'audit', 'candidate_pool', 'candidate_selection', 'historical_inventory', 'receipt')},
                  limitations=['Content relations and unobservable-content declarations are from the frozen audited engine; this check does not recompute prose features or independently discover omitted relations.',
                               'Graph components, grouping metadata, purges, survivors, pair-count reconciliation, and reported scope are independently checked.',
                               'Title-node identities/grouping are checked; title presence and exact content remain covered by the original frozen historical loader and its synthetic tests.',
                               'Available-content audit cannot establish independence from unsupplied, removed, unmarked quoted, short, or paraphrased material.'])
    if report['wall_seconds'] > MAX_SECONDS:
        raise RuntimeError('wall_time_limit')
    return report


def main():
    parser = argparse.ArgumentParser()
    for name in ('audit', 'public-audit', 'freeze', 'candidate-pool', 'candidate-selection', 'historical-inventory', 'receipt', 'wrapper', 'engine', 'rules', 'offline-runner', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (MAX_AS,) * 2)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('independent_check_wall_time')))
    signal.alarm(MAX_SECONDS)
    with args.out.with_suffix('.start-binding.json').open('x') as handle:
        json.dump({'phase': 'before_independent_audit_metadata_reads', 'utc': datetime.now(timezone.utc).isoformat(),
                   'checker': fingerprint(__file__), 'limits': {'metadata_rows': MAX_ROWS, 'wall_seconds': MAX_SECONDS, 'address_space_bytes': MAX_AS, 'output_bytes': MAX_OUTPUT},
                   'historical_source_prose_files_opened': 0, 'preprocessing_calls': 0, 'style_scores_computed': 0}, handle, indent=2)
        handle.write('\n')
    report = verify(args)
    payload = canonical(report) + b'\n'
    if len(payload) > MAX_OUTPUT:
        raise RuntimeError('output_limit')
    with args.out.open('xb') as handle:
        handle.write(payload)
    signal.alarm(0)
    print(json.dumps({'status': report['status'], 'failed_checks': report['failed_checks'], 'checks_performed': report['checks_performed'], 'purged_candidate_records': report['purged_candidate_records'], 'surviving_candidate_records': report['surviving_candidate_records'], 'output': fingerprint(args.out)}))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
