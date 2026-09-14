"""Synthetic independent final-calendar witness verification."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_final_calendar as checker


def fixture(shared=False, math_count=20):
    names = sorted(checker.FIXED) + [checker.NEW_PAIR]
    sets = {name: {('common' if shared else str(i)) + '-' + str(j) for j in range(math_count if i == 2 else 20)} for i, name in enumerate(names)}
    optimum = checker.exhaustive_three_strata(sets)
    if shared:
        # The shared-universe Hall limit permits only twenty accounts total.
        available = sorted(set.union(*sets.values()))
        assigned = {}
        for name in names:
            q = optimum['quota_counts'][name]
            assigned[name], available = available[:q], available[q:]
    else:
        assigned = {p: sorted(a)[:optimum['quota_counts'][p]] for p, a in sets.items()}
    allocation = {k: optimum[k] for k in ('quota_counts', 'total_accounts', 'total_blocks')}
    selection = {'selected_pairs': names, 'capacity': {**allocation, 'assigned': assigned},
                 'feasible_target': optimum['feasible_target'],
                 'eligible_accounts_by_pair': {p: sorted(a) for p, a in sorted(sets.items())}}
    public = {'selected_pair_strata': names, 'disjoint_capacity': allocation,
              'gate_a_status': 'capacity_pass_requires_contamination_audit' if optimum['feasible_target'] else 'failed_capacity'}
    return sets, selection, public


def run(values, excluded=frozenset()):
    check = checker.Checks()
    optimum = checker.check_allocation(*values, excluded, check)
    return optimum, check.failures


def test_full_target_requires_twenty_disjoint_accounts_per_registered_stratum():
    optimum, failures = run(fixture())
    assert not failures
    assert optimum['total_accounts'] == 60 and optimum['total_blocks'] == 30
    assert optimum['quota_vectors_checked'] == 1331


def test_three_raw_twenty_account_sets_can_fail_disjoint_full_target():
    optimum, failures = run(fixture(shared=True))
    assert not failures and not optimum['feasible_target']
    assert optimum['total_accounts'] == 20


@pytest.mark.parametrize('mutation,expected', [
    ('duplicate_across_strata', 'globally disjoint'),
    ('duplicate_within_stratum', 'uniqueness'),
    ('ineligible_account', 'eligible in its stratum'),
    ('inflate_quota', 'quota optimum'),
    ('omit_capacity_account', 'Full private capacity sets'),
    ('false_gate_pass', 'Gate A status'),
])
def test_detects_witness_or_gate_corruption(mutation, expected):
    sets, selection, public = deepcopy(fixture(math_count=18 if mutation == 'false_gate_pass' else 20))
    first, second = sorted(sets)[:2]
    if mutation == 'duplicate_across_strata':
        common = selection['capacity']['assigned'][first][0]
        sets[second].add(common)
        selection['eligible_accounts_by_pair'][second] = sorted(sets[second])
        selection['capacity']['assigned'][second][0] = common
    elif mutation == 'duplicate_within_stratum':
        selection['capacity']['assigned'][first][0] = selection['capacity']['assigned'][first][1]
    elif mutation == 'ineligible_account':
        selection['capacity']['assigned'][first][0] = 'outside'
    elif mutation == 'inflate_quota':
        selection['capacity']['total_accounts'] = 62
    elif mutation == 'omit_capacity_account':
        selection['eligible_accounts_by_pair'][first].pop()
    else:
        public['gate_a_status'] = 'capacity_pass_requires_contamination_audit'
    _, failures = run((sets, selection, public))
    assert any(expected in message for message in failures)


def test_protected_account_fails_even_if_not_used_in_saved_assignment():
    values = fixture()
    values[0][checker.NEW_PAIR].add('protected')
    values[1]['eligible_accounts_by_pair'][checker.NEW_PAIR] = sorted(values[0][checker.NEW_PAIR])
    _, failures = run(values, {'protected'})
    assert any('Mandatory exclusions' in message for message in failures)


def test_fixed_dates_are_the_registered_half_open_periods():
    assert checker.scheme('2015-10-06') == {'id': 'utc_midnight_2015-10-06', 'early': ['2008-01-01', '2015-10-06'], 'late': ['2015-10-06', '2018-11-01']}
    assert checker.FIXED == {'AskAcademia / GradSchool': ('2015-10-06', 39), 'AskPhysics / Physics': ('2015-09-20', 36)}


def test_checker_imports_no_execution_or_production_helpers():
    import ast
    tree = ast.parse(Path(checker.__file__).read_text())
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    imports += [name.name for node in ast.walk(tree) if isinstance(node, ast.Import) for name in node.names]
    assert not set(imports) & {'calendar_capacity', 'study_math', 'expanded_capacity', 'run_pair_calendar', 'account_history_analyzer'}
