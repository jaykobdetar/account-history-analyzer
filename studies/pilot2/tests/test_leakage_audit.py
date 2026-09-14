"""Independent, synthetic selection-audit oracles; no real corpus or style scores."""
from copy import deepcopy
import hashlib
import itertools
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from leakage_audit import audit_records, audit_definition


def words(start, count):
    return ['w' + chr(97 + i // 676) + chr(97 + (i // 26) % 26) + chr(97 + i % 26)
            for i in range(start, start + count)]


def row(identifier, tokens, split='development', account=None):
    return {'id': identifier, 'text': ' '.join(tokens) if not isinstance(tokens, str) else tokens,
            'split': split, 'account_key': account or 'account-' + identifier}


def near_pairs(result):
    return {tuple(item['record_ids']) for item in result['relations'] if item['kind'] == 'near'}


def test_exact_normalization_preserves_segments_and_numbers():
    result = audit_records([row('a', 'Café I’m HERE 42'), row('b', "Cafe\u0301 i'm here 42", 'evaluation'),
                            row('c', "café i'm here 43"), row('d', "café\n\ni'm here 42")])
    assert result['status'] == 'audited'
    assert result['excluded_ids'] == ['a', 'b']
    assert result['summary']['relation_counts']['exact'] == 1
    assert len(set(result['cluster_by_id'].values())) == 3


def test_hand_oracle_jaccard_exactly_point_eight():
    left = words(0, 22)  # Eighteen distinct five-token shingles.
    right = words(100, 2) + left[2:]  # Sixteen shared; union twenty.
    result = audit_records([row('a', left), row('b', right, 'evaluation')])
    match = next(item for item in result['relations'] if item['kind'] == 'near')
    assert (match['left_shingles'], match['right_shingles'], match['shared_unique_shingles'],
            match['union_unique_shingles']) == (18, 18, 16, 20)
    assert match['match_rules'] == ['jaccard_80_100']
    below = audit_records([row('a', left), row('b', words(100, 3) + left[3:], 'evaluation')])
    assert near_pairs(below) == set()


def test_hand_oracle_directional_containment_exactly_point_nine():
    left = words(0, 24)  # Twenty shingles.
    right = left[2:] + words(100, 4)  # Twenty-two shingles; eighteen shared.
    result = audit_records([row('a', left), row('b', right, 'confirmation')])
    match = next(item for item in result['relations'] if item['kind'] == 'near')
    assert (match['left_shingles'], match['right_shingles'], match['shared_unique_shingles']) == (20, 22, 18)
    assert match['match_rules'] == ['left_containment_90_100']
    assert result['excluded_ids'] == ['a', 'b']


def test_near_guards_require_words_and_five_distinct_shared_shingles():
    result = audit_records([row('a', ['echo'] * 20), row('b', ['echo'] * 21, 'evaluation')])
    assert near_pairs(result) == set()
    short = audit_records([row('a', words(0, 19)), row('b', words(100, 1) + words(1, 18), 'evaluation')])
    assert near_pairs(short) == set()
    numeric = audit_records([row('a', ' '.join(map(str, range(30)))),
                             row('b', ' '.join(map(str, range(2, 32))), 'evaluation')])
    assert near_pairs(numeric) == set()


def test_inverted_index_matches_independent_all_pairs_set_oracle():
    rng = random.Random(329)
    sequences = [words(0, 22)]
    for i in range(1, 15):
        sequence = list(sequences[0])
        count = rng.randrange(1, 8)
        sequence[:count] = words(50 + i * 10, count)
        sequences.append(sequence)
    inputs = [row(f'r{i:02}', sequence) for i, sequence in enumerate(sequences)]
    expected = set()
    for (i, a), (j, b) in itertools.combinations(enumerate(sequences), 2):
        aa = {tuple(a[k:k + 5]) for k in range(len(a) - 4)}
        bb = {tuple(b[k:k + 5]) for k in range(len(b) - 4)}
        common, union = len(aa & bb), len(aa | bb)
        if common >= 5 and (5 * common >= 4 * union or 10 * common >= 9 * len(aa)
                            or 10 * common >= 9 * len(bb)):
            expected.add((f'r{i:02}', f'r{j:02}'))
    assert near_pairs(audit_records(inputs)) == expected


def test_transitive_components_purge_every_split_symmetrically():
    x, y = words(0, 20), words(100, 20)
    result = audit_records([row('a', x), row('b', x + y), row('c', y, 'confirmation')])
    assert near_pairs(result) == {('a', 'b'), ('b', 'c')}
    assert result['excluded_ids'] == ['a', 'b', 'c']
    assert len(result['components']) == 1
    assert result['components'][0]['split_memberships'] == ['confirmation', 'development']


def test_author_membership_alone_does_not_connect_records():
    result = audit_records([row('a', words(0, 21), account='same'), row('b', words(100, 21), account='same')])
    assert result['relations'] == []
    assert result['summary']['singleton_component_count'] == 2


def test_template_hyperedge_needs_three_accounts_and_fifteen_contiguous_words():
    phrase = words(0, 15)
    inputs = [row(letter, words(100 + i * 20, 3) + phrase + words(110 + i * 20, 3), split)
              for i, (letter, split) in enumerate(zip('abc', ('development', 'evaluation', 'confirmation')))]
    result = audit_records(inputs)
    assert result['summary']['relation_counts'] == {'exact': 0, 'near': 0, 'template': 1, 'quotation': 0}
    assert result['excluded_ids'] == ['a', 'b', 'c']
    incidence = result['summary']['relation_incidence']['template']
    assert incidence['cross_split_pair_memberships'] == incidence['cross_account_pair_memberships'] == 3
    assert incidence['same_split_pair_memberships'] == 0
    two_accounts = deepcopy(inputs)
    two_accounts[2].update(account_key=two_accounts[0]['account_key'], split='development')
    assert audit_records(two_accounts)['summary']['relation_counts']['template'] == 0


@pytest.mark.parametrize('separator', ['\n\n', ' `excluded_code` ', ' https://example.test/x '])
def test_templates_never_join_across_excluded_or_paragraph_segments(separator):
    phrase = words(0, 15)
    broken = ' '.join(phrase[:7]) + separator + ' '.join(phrase[7:])
    inputs = [row('a', broken), row('b', phrase, 'evaluation'), row('c', phrase, 'confirmation')]
    result = audit_records(inputs)
    assert result['summary']['relation_counts']['template'] == 0
    assert 'a' not in result['excluded_ids']


def test_recognized_quote_matches_retained_phrase_with_actual_line_map():
    phrase = ' '.join(words(0, 15))
    result = audit_records([row('q', 'preface\n\n> **' + phrase + '**\n\nresponse'),
                            row('r', phrase, 'confirmation')])
    assert result['excluded_ids'] == ['q', 'r']
    match = next(item for item in result['relations'] if item['kind'] == 'quotation')
    assert match['quote_record_ids'] == ['q'] and match['retained_record_ids'] == ['r']
    assert match['quote_source_line_ranges'] == [{'record_id': 'q', 'source_line_range': [3, 3]}]
    assert phrase not in json.dumps(result)


@pytest.mark.parametrize('quote', [
    lambda p: '> ' + ' '.join(p[:7]) + '\n>\n> ' + ' '.join(p[7:]),
    lambda p: '> ```\n> ' + ' '.join(p) + '\n> ```',
    lambda p: '> ' + ' '.join(p[:7]) + ' `excluded_code` ' + ' '.join(p[7:]),
])
def test_quote_audit_respects_paragraph_and_code_boundaries(quote):
    phrase = words(0, 15)
    result = audit_records([row('q', quote(phrase)), row('r', phrase, 'evaluation')])
    assert result['summary']['relation_counts']['quotation'] == 0
    assert result['excluded_ids'] == []


def test_empty_observations_are_distinct_actual_singletons():
    result = audit_records([row('a', ''), row('b', '', 'evaluation')])
    assert result['status'] == 'audited' and result['excluded_ids'] == []
    assert len(set(result['cluster_by_id'].values())) == 2
    assert result['summary']['empty_retained_record_count'] == 2


def test_explicit_missing_content_stays_unknown_without_erasing_metadata_node():
    a = row('a', 'observed')
    b = {**row('b', '', 'confirmation'), 'text': None, 'status': 'unavailable'}
    result = audit_records([a, b])
    assert result['status'] == 'audited'
    assert result['summary']['content_unobservable_record_count'] == 1
    assert result['summary']['unknown_scope_flags'] == ['unobserved_content_relationships_unknown']
    component = next(c for c in result['components'] if 'b' in c['record_ids'])
    assert component['content_unobservable_record_ids'] == ['b']


@pytest.mark.parametrize('field', ['id', 'text', 'split', 'account_key'])
def test_missing_required_metadata_never_becomes_an_audited_singleton(field):
    value = row('a', 'some text')
    del value[field]
    result = audit_records([value])
    assert result['status'] == 'not_auditable'
    assert not result['summary']['complete']
    assert result['cluster_by_id'] == {} and result['components'] == []


def test_conflicting_account_split_and_duplicate_ids_fail_closed():
    for values in ([row('a', 'one', account='shared'), row('b', 'two', 'evaluation', account='shared')],
                   [row('a', 'one'), row('a', 'two')]):
        result = audit_records(values)
        assert result['status'] == 'not_auditable'
        assert result['excluded_ids'] == [] and result['relations'] == []


def test_candidate_cap_discards_partial_actionable_graph():
    values = [row(identifier, words(0, 22), split) for identifier, split in
              zip('abc', ('development', 'evaluation', 'confirmation'))]
    result = audit_records(values, max_candidate_pairs=1)
    assert result['status'] == 'not_auditable'
    assert result['summary']['candidate_pair_count'] == 2
    assert result['summary']['candidate_pair_count_is_lower_bound'] is True
    assert result['summary']['reason_codes'] == ['candidate_pair_cap_exceeded']
    assert result['excluded_ids'] == [] and result['cluster_by_id'] == {} and result['relations'] == []


def test_exact_cap_boundary_completes_all_relationship_phases():
    values = [row('a', words(0, 22)), row('b', words(0, 22), 'confirmation')]
    result = audit_records(values, max_candidate_pairs=1)
    assert result['status'] == 'audited'
    assert result['summary']['candidate_pair_count'] == 1
    assert result['summary']['candidate_pair_count_is_lower_bound'] is False
    assert result['summary']['relation_counts']['exact'] == 1
    assert result['summary']['relation_counts']['near'] == 1


def test_cap_stop_does_not_allocate_or_parse_later_quote_phase(monkeypatch):
    import leakage_audit
    def forbidden(*args, **kwargs):
        raise AssertionError('quote phase ran before pair preflight completed')
    monkeypatch.setattr(leakage_audit, '_quotes', forbidden)
    values = [row('a', words(0, 22)), row('b', words(0, 22), 'confirmation')]
    assert audit_records(values, max_candidate_pairs=0)['status'] == 'not_auditable'


def test_record_and_mapping_permutations_preserve_complete_output():
    values = [row('a', words(0, 22)), row('b', words(0, 22), 'evaluation'),
              row('c', 'preface\n\n> ' + ' '.join(words(0, 15)), 'confirmation'), row('d', 'unrelated')]
    expected = audit_records(values)
    for seed in range(8):
        rng = random.Random(seed)
        shuffled = []
        for value in values:
            items = list(value.items()); rng.shuffle(items); shuffled.append(dict(items))
        rng.shuffle(shuffled)
        assert audit_records(shuffled) == expected


def test_cli_accepts_adapter_wrapper_and_hashes_original_pool(tmp_path):
    pool, out = tmp_path / 'pool.jsonl', tmp_path / 'audit.json'
    values = [row('a', words(0, 22)), row('b', words(0, 22), 'evaluation')]
    wrappers = [{'record': {k: v for k, v in value.items() if k not in {'split', 'account_key'}},
                 'split': value['split'], 'account_key': value['account_key']} for value in values]
    pool.write_text(''.join(json.dumps(value) + '\n' for value in wrappers))
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/leakage_audit.py'),
                             '--candidate-pool', str(pool), '--out', str(out)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    stored = json.loads(out.read_text())
    assert stored['candidate_pool_sha256'] == hashlib.sha256(pool.read_bytes()).hexdigest()
    assert stored['status'] == 'audited' and stored['purge_record_ids'] == ['a', 'b']
    assert stored['near_duplicate_clusters'][0]['record_ids'] == ['a', 'b']
    assert stored['summary']['method'] == audit_definition()


def test_cli_memory_failure_records_unavailable_without_partial_groups(tmp_path, monkeypatch):
    import leakage_audit
    pool, out = tmp_path / 'pool.jsonl', tmp_path / 'audit.json'
    pool.write_text(json.dumps(row('a', words(0, 22))) + '\n')
    def exhausted(*args, **kwargs):
        raise MemoryError('synthetic allocation failure')
    monkeypatch.setattr(leakage_audit, 'audit_records', exhausted)
    monkeypatch.setattr(sys, 'argv', ['leakage_audit.py', '--candidate-pool', str(pool), '--out', str(out)])
    assert leakage_audit.main() == 4
    result = json.loads(out.read_text())
    assert result['status'] == 'not_auditable'
    assert result['summary']['reason_codes'] == ['memory_allocation_failed']
    assert result['summary']['candidate_pair_count'] is None
    assert result['purge_record_ids'] == result['near_duplicate_clusters'] == result['relations'] == []
