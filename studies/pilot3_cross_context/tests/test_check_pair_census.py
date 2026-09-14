"""Independent pair-intake checker tests using synthetic fixtures only."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_pair_census as checker
from test_census_pair import run_synthetic_pair


def fixture_contract(n=20):
    plan = {'target': {'accounts': 20, 'blocks': 10, 'strata': 1,
                      'accounts_per_stratum': 20, 'blocks_per_stratum': 10,
                      'words_per_cell': 2000, 'eligible_records_per_cell': 8},
            'sources': [{'community': 'X'}, {'community': 'Y'}], 'community_pairs': [['X', 'Y']]}
    members = {f'account-{i}' for i in range(n)}
    count = min(20, 2 * (n // 2))
    allocation = {'quota_counts': {'X / Y': count}, 'total_accounts': count,
                  'total_blocks': count // 2, 'assigned': {'X / Y': sorted(members)[:count]}}
    public = {key: value for key, value in allocation.items() if key != 'assigned'}
    capacity = {'gate_a_status': 'pair_capacity_pass' if n >= 20 else 'pair_capacity_failed',
                'study_scope': 'single_pair_intake_only', 'scoring_permitted': False,
                'full_study_gate_status': 'not_evaluated_by_single_pair_intake',
                'scores_computed': False, 'final_cohort_selected': False,
                'planned_accounts': 20, 'planned_blocks': 10, 'words_per_cell': 2000, 'records_per_cell': 8,
                'disjoint_capacity': deepcopy(public), 'all_history_disjoint_upper_bound': deepcopy(public)}
    witness = {'allocation': deepcopy(allocation), 'upper_bound_allocation': deepcopy(allocation)}
    return plan, capacity, witness, {'X / Y': members}, {'X / Y': members}


def failed_checks(args):
    failures = []
    checker.check_pair_contract(*args, lambda condition, message: failures.append(message) if not condition else None)
    return failures


@pytest.mark.parametrize('available,expected', [(0, 0), (1, 0), (18, 18), (19, 18), (20, 20), (21, 20), (40, 20)])
def test_largest_even_pair_quota_keeps_twenty_account_target(available, expected):
    args = fixture_contract(available)
    assert failed_checks(args) == []
    assert args[1]['disjoint_capacity']['total_accounts'] == expected
    assert args[1]['planned_accounts'] == 20


@pytest.mark.parametrize('field,value', [('full_study_gate_status', 'passed'), ('scoring_permitted', True),
                                       ('scores_computed', True), ('final_cohort_selected', True),
                                       ('planned_accounts', 18), ('planned_blocks', 9), ('records_per_cell', 7)])
def test_checker_rejects_scope_inflation_or_quiet_target_reduction(field, value):
    args = fixture_contract()
    args[1][field] = value
    assert failed_checks(args)


def test_checker_rejects_repeated_or_ineligible_assignment_even_if_totals_match():
    args = fixture_contract()
    args[2]['allocation']['assigned']['X / Y'][1] = args[2]['allocation']['assigned']['X / Y'][0]
    assert any('distinct feasible' in message for message in failed_checks(args))
    args = fixture_contract()
    args[2]['allocation']['assigned']['X / Y'][0] = 'not-eligible'
    assert any('distinct feasible' in message for message in failed_checks(args))


def fresh_synthetic_receipt(out, stdout):
    prefix = out.parent / 'synthetic-pair-command'
    Path(str(prefix) + '.stdout.log').write_text(''.join(json.dumps(row) + '\n' for row in stdout))
    Path(str(prefix) + '.stderr.log').write_text('')
    receipt = Path(str(prefix) + '.receipt.json')
    receipt.write_text(json.dumps({'exit_code': 0, 'synthetic_fixture': True,
                                  'outputs': {suffix: checker.fingerprint(str(prefix) + '.' + suffix)
                                              for suffix in ('stdout.log', 'stderr.log')}}))
    return receipt


def test_full_independent_reconciliation_of_synthetic_twenty_account_pair(run_synthetic_pair):
    plan, capacity, out, private, stdout = run_synthetic_pair(20)
    receipt = fresh_synthetic_receipt(out, stdout)
    report = checker.reconcile(out.parent / 'plan.json', out, private, receipt, out.parent / 'sources')
    assert report['status'] == 'pass', report['failed_checks']
    assert report['single_pair_contract_checked'] is True and report['full_study_gate_passed'] is False
    assert len(report['independently_recomputed']['period_capacity_table']) == 4
    assert report['independently_recomputed']['preprocessing_candidate_accounts'] == 21
    assert report['independently_recomputed']['eligible_records'] == 640


def test_metadata_checker_detects_invented_four_cell_capacity(run_synthetic_pair):
    plan, capacity, out, private, stdout = run_synthetic_pair(18)
    receipt = fresh_synthetic_receipt(out, stdout)
    capacity['period_capacity_table'][0]['four_cell_accounts'] = 99
    (out / 'capacity.json').write_text(json.dumps(capacity))
    report = checker.reconcile(out.parent / 'plan.json', out, private, receipt)
    assert report['status'] == 'fail'
    assert 'Entire period capacity table independently recomputed' in report['failed_checks']
