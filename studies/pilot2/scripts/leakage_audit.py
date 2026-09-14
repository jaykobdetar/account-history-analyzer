"""Pilot-2 selection-only content audit; never calculate stylistic distances.

Exact/near edges use normalized lexical tokens, retaining numbers and segment
boundaries. Template/quotation phrases use word tokens. Near containment uses
both-record 20-word guards: this is a declared audit adaptation, distinct from
production's shorter-record 50-word containment guard. A completed graph includes
honest singleton nodes. Any incomplete audit exposes no actionable components.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unicodedata

from markdown_it import MarkdownIt
from account_history_analyzer import AnalysisConfig, __version__
from account_history_analyzer.text import preprocess

METHOD = 'pilot2_leakage_audit_v1'
SPLITS = ('development', 'evaluation', 'confirmation')
PAIR_CAP = 2_000_000
RULES = {
    'method_id': METHOD, 'version': '1.0.0', 'ahas_version': '1.0.4',
    'exact': 'nonempty normalized lexical-token segment sequence; numbers retained',
    'near_shingle_tokens': 5, 'near_minimum_words_each_record': 20,
    'near_minimum_shared_unique_shingles': 5,
    'jaccard_numerator': 80, 'jaccard_denominator': 100,
    'containment_numerator': 90, 'containment_denominator': 100,
    'containment_direction': 'either record; both records satisfy 20-word guard',
    'template_phrase_word_tokens': 15, 'template_minimum_distinct_accounts': 3,
    'quotation_phrase_word_tokens': 15,
    'quotation_scope': 'recognized CommonMark blockquote inline paragraphs with original line maps',
    'segment_boundaries': 'never crossed by exact segmentation, shingles, or phrases',
    'component_rule': 'union all exact, near, template and quotation relationships',
    'purge_rule': 'all records in any component spanning two or more of the three splits',
    'singletons': 'actual nodes in a completed audit graph; empty retained text never exact-matched',
    'missing_content': 'explicit non-present status may have null text; graph covers available content only',
}
LIMITATIONS = [
    'Shared content or a template is not evidence of its cause, authorship, automation, or deception.',
    'The audit covers supplied candidate records only, not the entire source collection.',
    'Unmarked quotations, short phrases, semantic paraphrases, and source attribution remain unknown.',
    'Transitive template and quote connections may exclude records without a direct pairwise match.',
    'Account keys are supplier identities, not verified human authorship.',
    'Audit containment uses a 20-word guard and differs from production containment eligibility.',
    'Non-present or unavailable content has unknown hidden relationships; a graph singleton does not establish independence.',
]


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def audit_definition():
    return {**deepcopy(RULES), 'definition_sha256': sha(RULES),
            'default_max_candidate_pairs': PAIR_CAP,
            'candidate_cap_unit': 'unique pairs sharing at least one unique five-token shingle',
            'incomplete_behavior': 'not_auditable; no actionable clusters or purge IDs',
            'limitations': list(LIMITATIONS)}


def _phrases(segments, size):
    return {tuple(segment[start:start + size]) for segment in segments
            for start in range(max(0, len(segment) - size + 1))}


def _prepared(row, config):
    record = {'id': row['id'], 'text': row['text'], 'status': row.get('status', 'present'),
              'kind': 'comment', 'language': row.get('language') or 'en'}
    manifest = {'text_format': 'markdown', 'default_language': 'en'}
    body = preprocess(record, manifest, config)
    tokens = tuple(tuple(segment) for segment in body['tokens'])
    words = tuple(tuple(segment) for segment in body['word_tokens'])
    return {'tokens': tokens, 'words': words, 'word_count': sum(map(len, words)),
            'shingles': _phrases(tokens, 5), 'content_observable': bool(body['usable'])}


def _quotes(row, config, parser, *, content_observable):
    record = {'id': row['id'], 'text': row['text'], 'status': row.get('status', 'present'),
              'kind': 'comment', 'language': row.get('language') or 'en'}
    manifest = {'text_format': 'markdown', 'default_language': 'en'}
    quotations = defaultdict(set)
    if content_observable:
        source = unicodedata.normalize('NFC', row['text'].replace('\r\n', '\n').replace('\r', '\n'))
        depth = 0
        for token in parser.parse(source):
            if token.type == 'blockquote_open':
                depth += 1
            elif token.type == 'blockquote_close':
                depth -= 1
            elif depth and token.type == 'inline':
                quoted = preprocess({**record, 'text': token.content}, manifest, config)
                line_range = tuple((token.map[0] + 1, token.map[1])) if token.map is not None else None
                for phrase in _phrases(quoted['word_tokens'], 15):
                    quotations[phrase].add(line_range)
    return quotations


def _incomplete(summary, reasons):
    return {'status': 'not_auditable', 'excluded_ids': [], 'cluster_by_id': {}, 'components': [], 'relations': [],
            'summary': {**summary, 'status': 'not_auditable', 'complete': False,
                        'reason_codes': sorted(set(reasons)), 'limitations': list(LIMITATIONS)}}


def audit_records(rows, *, max_candidate_pairs=PAIR_CAP):
    """Audit original {id,text,split,account_key} rows with no label-derived features.

    Optional status/language preserve source preprocessing semantics. Missing or
    conflicting required metadata makes the audit unavailable. The override is
    an explicit execution cap for bounded tests; production uses 2,000,000.
    """
    if type(max_candidate_pairs) is not int or max_candidate_pairs < 0:
        raise ValueError('max_candidate_pairs must be a nonnegative integer')
    rows = list(rows)
    summary = {'method': audit_definition(), 'record_count': len(rows),
               'max_candidate_pairs': max_candidate_pairs, 'candidate_pair_count': 0,
               'candidate_pair_count_is_lower_bound': False, 'pair_comparison_count': 0,
               'no_style_distances_calculated': True}
    reasons = []
    by_id = {}
    accounts = defaultdict(set)
    for row in rows:
        if not isinstance(row, Mapping):
            reasons.append('row_not_mapping')
            continue
        status = row.get('status', 'present')
        valid_text = isinstance(row.get('text'), str) or (
            row.get('text') is None and status in {'deleted', 'removed', 'unavailable'})
        if (not isinstance(row.get('id'), str) or not row['id']
                or not valid_text or status not in {'present', 'deleted', 'removed', 'unavailable'}
                or not isinstance(row.get('account_key'), str) or not row['account_key']
                or row.get('split') not in SPLITS):
            reasons.append('missing_or_invalid_required_metadata')
            continue
        if row['id'] in by_id:
            reasons.append('duplicate_record_id')
        by_id[row['id']] = {**row, 'text': row.get('text')}
        accounts[row['account_key']].add(row['split'])
    if any(len(splits) > 1 for splits in accounts.values()):
        reasons.append('account_key_crosses_splits')
    if __version__ != RULES['ahas_version']:
        reasons.append('unexpected_ahas_preprocessing_version')
    if reasons:
        return _incomplete(summary, reasons)
    ids = sorted(by_id)
    config = AnalysisConfig.from_toml()
    parser = MarkdownIt('commonmark', {'typographer': False, 'html': True, 'linkify': False})
    prepared = {}
    parent = {identifier: identifier for identifier in ids}
    relations = []

    def find(identifier):
        while parent[identifier] != identifier:
            parent[identifier] = parent[parent[identifier]]
            identifier = parent[identifier]
        return identifier

    def relation(kind, members, *, signatures=(), **metadata):
        members = sorted(set(members))
        if len(members) < 2:
            return
        for identifier in members[1:]:
            roots = sorted((find(members[0]), find(identifier)))
            parent[roots[1]] = roots[0]
        item = {'kind': kind, 'record_ids': members, **metadata}
        if signatures:
            item.update(signature_count=len(signatures), signatures_sha256=sha(sorted(signatures)))
        item['relation_id'] = 'relation-' + sha({'method': METHOD, **item})
        relations.append(item)

    # Each record's set enters the inverted index once. A pair is counted on its
    # first shared shingle, not once per posting or once per qualifying rule.
    # Prepare incrementally. Cap exhaustion must not first allocate the much
    # larger fifteen-word phrase index or parse every record's quote content.
    postings = defaultdict(list)
    for identifier in ids:
        value = _prepared(by_id[identifier], config)
        prepared[identifier] = value
        if value['word_count'] < 20 or len(value['shingles']) < 5:
            continue
        overlaps = Counter()
        for shingle in sorted(value['shingles']):
            for previous in postings[shingle]:
                if previous not in overlaps:
                    summary['candidate_pair_count'] += 1
                    if summary['candidate_pair_count'] > max_candidate_pairs:
                        summary['candidate_pair_count_is_lower_bound'] = True
                        return _incomplete(summary, ['candidate_pair_cap_exceeded'])
                overlaps[previous] += 1
        for previous, shared in sorted(overlaps.items()):
            if shared < 5:
                continue
            left, right = prepared[previous]['shingles'], value['shingles']
            intersection, union = len(left & right), len(left | right)
            summary['pair_comparison_count'] += 1
            rules = []
            if 100 * intersection >= 80 * union:
                rules.append('jaccard_80_100')
            if 100 * intersection >= 90 * len(left):
                rules.append('left_containment_90_100')
            if 100 * intersection >= 90 * len(right):
                rules.append('right_containment_90_100')
            if rules:
                relation('near', (previous, identifier), match_rules=rules,
                         left_shingles=len(left), right_shingles=len(right),
                         shared_unique_shingles=intersection, union_unique_shingles=union)
        for shingle in sorted(value['shingles']):
            postings[shingle].append(identifier)

    postings.clear()
    exact = defaultdict(list)
    for identifier in ids:
        value = prepared[identifier]
        del value['shingles']
        if any(value['tokens']):
            exact[value['tokens']].append(identifier)
    for signature, members in sorted(exact.items()):
        relation('exact', members, signatures=[sha(signature)])
    exact.clear()

    phrase_records = defaultdict(set)
    quote_records = defaultdict(set)
    for identifier in ids:
        for phrase in _phrases(prepared[identifier]['words'], 15):
            phrase_records[phrase].add(identifier)
        prepared[identifier]['quotes'] = _quotes(by_id[identifier], config, parser,
            content_observable=prepared[identifier]['content_observable'])
        for phrase in prepared[identifier]['quotes']:
            quote_records[phrase].add(identifier)
    template_groups = defaultdict(list)
    for phrase, members in sorted(phrase_records.items()):
        if len({by_id[identifier]['account_key'] for identifier in members}) >= 3:
            template_groups[tuple(sorted(members))].append(sha(phrase))
    for members, signatures in sorted(template_groups.items()):
        relation('template', members, signatures=signatures)
    quote_groups = defaultdict(lambda: {'signatures': [], 'maps': set()})
    for phrase in sorted(quote_records.keys() & phrase_records.keys()):
        quoters, retainers = quote_records[phrase], phrase_records[phrase]
        if not any(left != right for left in quoters for right in retainers):
            continue
        key = (tuple(sorted(quoters)), tuple(sorted(retainers)))
        quote_groups[key]['signatures'].append(sha(phrase))
        for identifier in quoters:
            for line_range in prepared[identifier]['quotes'][phrase]:
                if line_range is not None:
                    quote_groups[key]['maps'].add((identifier, *line_range))
    for (quoters, retainers), details in sorted(quote_groups.items()):
        relation('quotation', set(quoters) | set(retainers), signatures=details['signatures'],
                 quote_record_ids=list(quoters), retained_record_ids=list(retainers),
                 quote_source_line_ranges=[{'record_id': identifier, 'source_line_range': [first, last]}
                                           for identifier, first, last in sorted(details['maps'])])

    components = defaultdict(list)
    for identifier in ids:
        components[find(identifier)].append(identifier)
    cluster_by_id, excluded, component_rows = {}, [], []
    for members in sorted(components.values()):
        cluster = 'cluster-' + sha({'definition_sha256': sha(RULES), 'record_ids': members})
        cluster_by_id.update({identifier: cluster for identifier in members})
        component_rows.append({'cluster_id': cluster, 'record_ids': members,
                               'split_memberships': sorted({by_id[i]['split'] for i in members}),
                               'account_count': len({by_id[i]['account_key'] for i in members}),
                               'content_unobservable_record_ids': [i for i in members if not prepared[i]['content_observable']]})
        if len({by_id[identifier]['split'] for identifier in members}) > 1:
            excluded.extend(members)
    relations.sort(key=lambda item: (item['kind'], item['record_ids'], item['relation_id']))
    incidence = {}
    for kind in ('exact', 'near', 'template', 'quotation'):
        counts = Counter()
        for item in (item for item in relations if item['kind'] == kind):
            members = item['record_ids']
            split_counts = Counter(by_id[identifier]['split'] for identifier in members)
            author_counts = Counter(by_id[identifier]['account_key'] for identifier in members)
            pairs = len(members) * (len(members) - 1) // 2
            same_split = sum(n * (n - 1) // 2 for n in split_counts.values())
            same_account = sum(n * (n - 1) // 2 for n in author_counts.values())
            counts.update(relation_count=1, record_memberships=len(members),
                          same_split_pair_memberships=same_split, cross_split_pair_memberships=pairs-same_split,
                          same_account_pair_memberships=same_account, cross_account_pair_memberships=pairs-same_account)
        incidence[kind] = {key: counts[key] for key in ('relation_count', 'record_memberships',
            'same_split_pair_memberships', 'cross_split_pair_memberships',
            'same_account_pair_memberships', 'cross_account_pair_memberships')}
    summary.update(status='audited', complete=True, reason_codes=[],
                   records_by_split={split: sum(row['split'] == split for row in by_id.values()) for split in SPLITS},
                   account_count=len(accounts), empty_retained_record_count=sum(not any(p['tokens']) for p in prepared.values()),
                   content_unobservable_record_count=sum(not p['content_observable'] for p in prepared.values()),
                   content_scope='available retained text and recognized supplied blockquotes only',
                   unknown_scope_flags=['unobserved_content_relationships_unknown']
                       if any(not p['content_observable'] for p in prepared.values()) else [],
                   component_count=len(components), singleton_component_count=sum(len(v) == 1 for v in components.values()),
                   purged_record_count=len(excluded),
                   purged_records_by_split={split: sum(by_id[i]['split'] == split for i in excluded) for split in SPLITS},
                   relation_counts={kind: incidence[kind]['relation_count'] for kind in incidence},
                   relation_incidence=incidence,
                   incidence_unit='pair memberships within reported hyperedges, not unique independent pairs',
                   limitations=list(LIMITATIONS))
    return {'status': 'audited', 'excluded_ids': sorted(excluded),
            'cluster_by_id': dict(sorted(cluster_by_id.items())), 'components': component_rows,
            'summary': summary, 'relations': relations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-pool', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--max-candidate-pairs', type=int, default=PAIR_CAP)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit('Refusing to overwrite a prior audit')
    with args.candidate_pool.open('rb') as stream:
        pool_hash = hashlib.file_digest(stream, 'sha256').hexdigest()
    rows = []
    with args.candidate_pool.open(encoding='utf-8') as stream:
        for line in stream:
            wrapper = json.loads(line)
            record = wrapper.get('record', wrapper)
            rows.append({**record, 'split': wrapper.get('split'), 'account_key': wrapper.get('account_key')})
    try:
        result = audit_records(rows, max_candidate_pairs=args.max_candidate_pairs)
    except MemoryError:
        # A launcher may impose an address-space ceiling. Preserve unavailable
        # scope explicitly; no partially constructed graph is actionable.
        result = _incomplete({'method': audit_definition(), 'record_count': len(rows),
            'max_candidate_pairs': args.max_candidate_pairs, 'candidate_pair_count': None,
            'candidate_pair_count_is_lower_bound': False, 'pair_comparison_count': None,
            'no_style_distances_calculated': True}, ['memory_allocation_failed'])
    output = {'candidate_pool_sha256': pool_hash, 'status': result['status'],
              'purge_record_ids': result['excluded_ids'],
              'near_duplicate_clusters': result['components'],
              'summary': result['summary'], 'relations': result['relations'], 'limitations': list(LIMITATIONS)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(canonical(output) + b'\n')
    print(json.dumps(result['summary'], sort_keys=True), flush=True)
    return 0 if result['status'] == 'audited' else 4


if __name__ == '__main__':
    raise SystemExit(main())
