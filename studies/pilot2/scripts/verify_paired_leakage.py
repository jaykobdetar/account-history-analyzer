"""Independently verify completed pilot-2 audit coverage and every reported match.

This verifier does not import the audit implementation, enumerate stylistic
distances, or claim an independent all-nonmatching-pairs scan of the large pool.
"""
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from account_history_analyzer import AnalysisConfig
from account_history_analyzer.text import preprocess

ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode()
    return hashlib.sha256(data).hexdigest()


def main():
    pool_path = ROOT / 'prepared/paired/private/candidate-pool.jsonl'
    audit_path = ROOT / 'prepared/paired/private/leakage-audit.json'
    output_path = ROOT / 'review/paired-leakage-independent-check.json'
    if output_path.exists():
        raise SystemExit('Refusing to replace earlier verification')
    pool = [json.loads(line) for line in pool_path.read_text().splitlines()]
    audit = json.loads(audit_path.read_text())
    assert audit['status'] == 'audited' and audit['summary']['complete'] is True
    assert hashlib.sha256(pool_path.read_bytes()).hexdigest() == audit['candidate_pool_sha256']
    rows = {r['record']['id']: r for r in pool}
    assert len(rows) == len(pool) == 33190
    components = audit['near_duplicate_clusters']
    members = [i for c in components for i in c['record_ids']]
    assert len(members) == len(set(members)) == len(rows)
    assert set(members) == set(rows)
    expected_purge = set()
    for component in components:
        ids = component['record_ids']
        assert ids == sorted(set(ids))
        assert component['cluster_id'] == 'cluster-' + digest({
            'definition_sha256': audit['summary']['method']['definition_sha256'], 'record_ids': ids})
        splits = sorted({rows[i]['split'] for i in ids})
        assert component['split_memberships'] == splits
        assert component['account_count'] == len({rows[i]['account_key'] for i in ids})
        if len(splits) > 1:
            expected_purge.update(ids)
    assert set(audit['purge_record_ids']) == expected_purge
    assert len(expected_purge) == 6
    assert dict(Counter(rows[i]['split'] for i in expected_purge)) == {
        'development': 2, 'evaluation': 1, 'confirmation': 3}

    # Independently rebuild connected components from the exported relation
    # graph. This detects missing or spurious component unions and singletons.
    graph = defaultdict(set)
    for relation in audit['relations']:
        ids = relation['record_ids']
        assert ids == sorted(set(ids)) and set(ids) <= set(rows)
        assert len(ids) >= 2
        for identifier in ids[1:]:
            graph[ids[0]].add(identifier)
            graph[identifier].add(ids[0])
    unseen = set(rows)
    expected_components = set()
    while unseen:
        pending = [min(unseen)]
        group = set()
        while pending:
            identifier = pending.pop()
            if identifier in group:
                continue
            group.add(identifier)
            pending.extend(graph[identifier] - group)
        unseen -= group
        expected_components.add(frozenset(group))
    assert expected_components == {frozenset(c['record_ids']) for c in components}

    config = AnalysisConfig.from_toml()
    prepared = {}
    def observed(identifier):
        if identifier not in prepared:
            record = rows[identifier]['record']
            # Supplier identities/splits are deliberately not passed through.
            body = preprocess({'id': 'opaque', 'kind': 'comment', 'status': record['status'],
                'text': record['text'], 'language': 'en'},
                {'text_format': 'markdown', 'default_language': 'en'}, config)
            segments = tuple(tuple(segment) for segment in body['tokens'])
            shingles = set()
            for segment in segments:
                for start in range(len(segment) - 4):
                    shingles.add(tuple(segment[start:start + 5]))
            prepared[identifier] = (segments, sum(map(len, body['word_tokens'])), shingles)
        return prepared[identifier]
    counts = Counter()
    for relation in audit['relations']:
        kind = relation['kind']
        counts[kind] += 1
        if kind == 'exact':
            sequences = [observed(i)[0] for i in relation['record_ids']]
            assert any(sequences[0]) and all(s == sequences[0] for s in sequences)
        elif kind == 'near':
            a, b = relation['record_ids']
            _, na, sa = observed(a)
            _, nb, sb = observed(b)
            intersection = len(sa.intersection(sb))
            union = len(sa.union(sb))
            assert na >= 20 and nb >= 20 and intersection >= 5
            expected_rules = []
            if Fraction(intersection, union) >= Fraction(4, 5):
                expected_rules.append('jaccard_80_100')
            if Fraction(intersection, len(sa)) >= Fraction(9, 10):
                expected_rules.append('left_containment_90_100')
            if Fraction(intersection, len(sb)) >= Fraction(9, 10):
                expected_rules.append('right_containment_90_100')
            assert expected_rules and relation['match_rules'] == expected_rules
            assert (relation['left_shingles'], relation['right_shingles'],
                    relation['shared_unique_shingles'], relation['union_unique_shingles']) == (
                    len(sa), len(sb), intersection, union)
        else:
            raise AssertionError('New nonzero template/quote results need independent verification')
    assert counts == Counter(exact=57, near=2474)
    aggregate = json.dumps(audit['summary'], sort_keys=True)
    assert all(r['record']['text'] not in aggregate for r in pool if len(r['record']['text']) >= 40)
    assert all(key not in aggregate for key in ('"text":', '"account_key":', '"record_ids":'))
    result = {'status': 'passed', 'pool_sha256': audit['candidate_pool_sha256'],
        'audit_sha256': hashlib.sha256(audit_path.read_bytes()).hexdigest(),
        'audit_definition_sha256': audit['summary']['method']['definition_sha256'],
        'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'record_count': len(rows), 'component_count': len(components),
        'all_records_once_in_components': True, 'independent_graph_components_equal': True,
        'symmetrically_purged_records': len(expected_purge),
        'all_reported_exact_groups_verified': counts['exact'],
        'all_reported_near_pairs_verified_with_fraction_oracle': counts['near'],
        'public_aggregate_no_source_prose': True, 'style_distances_calculated': False,
        'limitation': 'Large-pool nonmatching pairs were not independently exhaustively enumerated; synthetic all-pairs oracles test that path.',
        'aggregate': audit['summary']}
    output_path.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'aggregate'}, sort_keys=True))


if __name__ == '__main__':
    main()
