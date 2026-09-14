"""Metadata-only independent expansion checks and synthetic corruption tests."""
from collections import Counter
from itertools import combinations, product
import json
from pathlib import Path
import random
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import check_expanded_census as checker
import census_expanded
import expanded_capacity
from test_census import synthetic_census


def identities(prefix, count):
    return {f'{prefix}-{i}' for i in range(count)}


def test_exact_hall_oracle_separates_raw_pair_counts_from_disjoint_capacity():
    shared = identities('same', 20)
    result = checker.independent_strata_optimum({'a': shared, 'b': shared, 'c': shared})
    assert result['quota_counts'] == {'a': 8, 'b': 6, 'c': 6}
    assert result['total_blocks'] == 10
    assert not result['feasible_target']
    assert result['full_target_feasible_triple_count'] == 0


def test_full_target_and_raw_capacity_alphabetic_ties():
    eligible = {'a': identities('a', 20), 'b': identities('b', 25),
                'c': identities('c', 25), 'd': identities('d', 30), 'e': identities('e', 25)}
    result = checker.independent_strata_optimum(eligible)
    assert result['selected_pairs'] == ['b', 'c', 'd']
    assert result['quota_counts'] == {'b': 20, 'c': 20, 'd': 20}
    assert result['feasible_target']
    assert result['candidate_triples_checked'] == result['full_target_feasible_triple_count'] == 10


def _account_assignment_oracle(eligible):
    """Exhaustively assign tiny account sets, without Hall or quota enumeration."""
    winner = None
    for triple in combinations(sorted(eligible), 3):
        accounts = sorted(set().union(*(eligible[p] for p in triple)))
        possibilities = [[None] + [p for p in triple if a in eligible[p]] for a in accounts]
        best_quotas = (0, 0, 0)
        for assignment in product(*possibilities):
            counts = Counter(assignment)
            quota = tuple(counts[p] for p in triple)
            if any(q % 2 or q > 20 for q in quota):
                continue
            if (sum(quota), tuple(sorted(quota)), quota) > (sum(best_quotas), tuple(sorted(best_quotas)), best_quotas):
                best_quotas = quota
        raw = [len(eligible[p]) for p in triple]
        key = (-sum(best_quotas), tuple(-q for q in sorted(best_quotas)), -min(raw), -sum(raw), triple)
        if winner is None or key < winner[0]:
            winner = key, list(triple), dict(zip(triple, best_quotas))
    return winner[1], winner[2]


def test_independent_hall_checker_matches_exhaustive_account_assignments():
    rng = random.Random(17643)
    for _ in range(15):
        eligible = {pair: {f'u{i}' for i in range(6) if rng.randrange(2)} for pair in ['a', 'b', 'c', 'd']}
        pairs, quota = _account_assignment_oracle(eligible)
        result = checker.independent_strata_optimum(eligible)
        assert result['selected_pairs'] == pairs
        assert result['quota_counts'] == quota


def test_check_all_28_pair_strata_and_all_triples_without_expansion_import(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Independent checker must not call selection implementation')
    monkeypatch.setattr(expanded_capacity, 'choose_three_strata', forbidden)
    result = checker.independent_strata_optimum({f'p{i:02}': identities('shared', 59) for i in range(28)})
    assert result['candidate_triples_checked'] == 3276
    assert result['selected_pairs'] == ['p00', 'p01', 'p02']
    assert result['total_blocks'] == 29
    assert not result['feasible_target']


def test_witness_must_assign_eligible_globally_disjoint_even_quotas():
    eligible = {'a': identities('a', 4), 'b': identities('b', 4), 'c': identities('c', 4)}
    choice = expanded_capacity.choose_three_strata(eligible)
    allocation = choice['capacity']
    public = {k: v for k, v in allocation.items() if k != 'assigned'}
    errors = []
    check = lambda condition, message: errors.append(message) if not condition else None
    checker.check_capacity_choice(eligible, choice['selected_pairs'], public, allocation, check, 'Test')
    assert errors == []
    allocation['assigned']['b'][0] = allocation['assigned']['a'][0]
    checker.check_capacity_choice(eligible, choice['selected_pairs'], public, allocation, check, 'Test')
    assert 'Test: all assigned accounts are disjoint across strata' in errors
    assert 'Test: assigned identities belong to eligible cells' in errors
    errors.clear()
    allocation['quota_counts']['a'] = 3
    checker.check_capacity_choice(eligible, choice['selected_pairs'], public, allocation, check, 'Test')
    assert 'Test: quotas are even integers between zero and twenty' in errors


@pytest.fixture
def synthetic_expanded(synthetic_census, monkeypatch, capsys):
    plan, old_out, private, old_receipt, source = synthetic_census
    out = old_out.with_name('synthetic-expanded-run')
    monkeypatch.setattr(sys, 'argv', ['census_expanded.py', '--plan', str(plan),
        '--source-root', str(source), '--private-root', str(private), '--out', str(out)])
    census_expanded.main()
    stdout = capsys.readouterr().out
    prefix = out.with_name('synthetic-expanded-command')
    Path(str(prefix) + '.stdout.log').write_text(stdout)
    Path(str(prefix) + '.stderr.log').write_text('')
    receipt = Path(str(prefix) + '.receipt.json')
    receipt.write_text(json.dumps({'exit_code': 0, 'synthetic_fixture': True,
        'outputs': {suffix: checker.fingerprint(str(prefix) + '.' + suffix)
                    for suffix in ('stdout.log', 'stderr.log')}}))
    return plan, out, private, receipt, source


def _update_private_digest(out, private, filename):
    path = private / out.name / filename
    manifest = checker.read(out / 'private-artifact-hashes.json')
    old_bytes = manifest[filename]['bytes']
    manifest[filename] = checker.fingerprint(path)
    (out / 'private-artifact-hashes.json').write_text(json.dumps(manifest))
    resources = checker.read(out / 'resources.json')
    resources['private_output_bytes'] += manifest[filename]['bytes'] - old_bytes
    (out / 'resources.json').write_text(json.dumps(resources))


def test_expanded_actual_metadata_reconciliation_and_source_script_binding(synthetic_expanded):
    result = checker.reconcile(*synthetic_expanded)
    assert result['status'] == 'pass', result['failed_checks']
    assert result['independently_recomputed']['global_three_stratum_optimum']['total_blocks'] == 0
    assert result['independently_recomputed']['global_all_history_necessary_optimum']['total_blocks'] == 1
    assert result['corpus_prose_read'] is False
    assert result['distance_scores_computed'] is False


def test_old_script_binding_is_not_accepted_as_expanded_execution(synthetic_expanded):
    plan, out, private, receipt, source = synthetic_expanded
    binding = checker.read(out / 'start-binding.json')
    binding['script_sha256'] = checker.fingerprint(SCRIPTS / 'census.py')['sha256']
    (out / 'start-binding.json').write_text(json.dumps(binding))
    result = checker.reconcile(plan, out, private, receipt, source)
    assert result['status'] == 'fail'
    assert 'Fresh run bound to supplied expanded census script bytes' in result['failed_checks']


def test_checker_rejects_wrong_selected_pair_and_invented_gate_pass(synthetic_expanded):
    plan, out, private, receipt, source = synthetic_expanded
    capacity = checker.read(out / 'capacity.json')
    capacity['selected_pair_strata'] = ['X / Y', 'X / Z', 'not-declared']
    capacity['gate_a_status'] = 'capacity_pass_requires_contamination_audit'
    (out / 'capacity.json').write_text(json.dumps(capacity))
    result = checker.reconcile(plan, out, private, receipt, source)
    assert result['status'] == 'fail'
    assert 'Four-cell allocation: chosen strata obey complete global objective and ties' in result['failed_checks']
    assert 'Four-cell allocation: selected strata are declared candidates' in result['failed_checks']
    assert 'Gate A target status agrees with independent exact Hall/assignment capacity' in result['failed_checks']


def test_checker_rejects_noneligible_witness_identity_after_digest_update(synthetic_expanded):
    plan, out, private, receipt, source = synthetic_expanded
    path = private / out.name / 'capacity-witness.json'
    witness = checker.read(path)
    # The necessary all-history allocation has two accounts in X/Y. Its
    # membership is audited even though this is not a feasible calendar design.
    witness['upper_bound_allocation']['assigned']['X / Y'][0] = 'invented-source-account'
    path.write_text(json.dumps(witness))
    _update_private_digest(out, private, path.name)
    result = checker.reconcile(plan, out, private, receipt, source)
    assert result['status'] == 'fail'
    assert 'All-history necessary upper-bound allocation: assigned identities belong to eligible cells' in result['failed_checks']


def test_checker_still_detects_private_record_duplication_and_cell_inflation(synthetic_expanded):
    plan, out, private, receipt, source = synthetic_expanded
    path = private / out.name / 'record-eligibility.jsonl'
    with path.open('ab') as handle:
        handle.write(path.read_bytes().splitlines(keepends=True)[0])
    _update_private_digest(out, private, path.name)
    result = checker.reconcile(plan, out, private, receipt, source)
    assert result['status'] == 'fail'
    assert 'Every candidate original record ID appears at most once' in result['failed_checks']
    assert 'Private cell table independently reconstructed from record metadata' in result['failed_checks']


def test_checker_output_contains_no_private_account_ids(synthetic_expanded):
    report = checker.reconcile(*synthetic_expanded)
    serialized = json.dumps(report)
    for private_identity in ('protected', 'early_only', 'below_guard', 'prefiltered'):
        assert '"' + private_identity + '"' not in serialized
