"""Independent result checks with synthetic source records only."""
from copy import deepcopy
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_audit_result as checker
from test_audit_candidates import candidate, historical, TEXT, OTHER
import audit_candidates as wrapper


@pytest.fixture(scope='module')
def engine():
    return wrapper.load_engine(os.environ.get('AHAS_PILOT3_ENGINE_PATH', '/tmp/ahas-pilot3-reviewed-repo/studies/pilot2/scripts/leakage_audit.py'))


def metadata(new, old):
    cm = {e['record']['id']: {'account_key': e['account_key'], 'stratum_id': e['stratum_id'], 'cell': [e['account_key'], e['community'], e['period']], 'thread_id': e['record']['thread_id'], 'declared_retained_words': e['retained_words']} for e in new}
    hm = {e['record']['id']: {'account_key': e['account_key'], 'original_split': e['original_split'], 'audit_split': 'confirmation' if e['original_split'] == 'confirmation' else 'development', 'source_kind': e['record']['kind'], 'thread_id': e['record']['thread_id'], 'original_references': [e['source_id']]} for e in old}
    return cm, hm


def synthetic_result(engine):
    new = [candidate('new-content'), candidate('new-cross', account='b'), candidate('new-safe', OTHER), candidate('new-thread', ' '.join(reversed(OTHER.split())), account='b', thread='shared-thread')]
    old = [historical('old-thread', 'short available historical body', split='confirmation', thread='shared-thread'), historical('old-title', 'other short body', account='other-old', kind='submission', title='available historical title')]
    result = wrapper.run_audit(new, old, engine)
    return result, *metadata(new, old)


def test_component_graph_has_transitive_hyperedges_and_honest_singletons():
    relations = [{'record_ids': ['a', 'b', 'c']}, {'record_ids': ['c', 'd']}, {'record_ids': ['f', 'g']}]
    assert checker.graph_components('abcdefg', relations) == [['a', 'b', 'c', 'd'], ['e'], ['f', 'g']]


@pytest.mark.parametrize('members', [['a', 'missing'], ['a', 'a'], ['a']])
def test_invalid_hyperedge_coverage_is_fatal(members):
    with pytest.raises(ValueError, match='invalid_relation_membership'):
        checker.graph_components(['a'], [{'record_ids': members}])


def test_content_and_thread_graphs_do_not_introduce_unregistered_transitivity():
    provenance = {'old': {'historical': True, 'thread_id': 'old-thread'},
                  'a': {'historical': False, 'thread_id': 'old-thread', 'cell': ['a', 'X', 'early']},
                  'b': {'historical': False, 'thread_id': 'b-thread', 'cell': ['a', 'X', 'early']}}
    # a and b share content within one cell, while only a shares old's thread.
    reasons, threads, survivors = checker.independent_purges(provenance, [['old'], ['a', 'b']])
    assert reasons == {'a': ['thread_historical_boundary']} and survivors == ['b']
    assert threads == [{'thread_id': 'old-thread', 'record_ids': ['a', 'old']}]


def test_reconciles_complete_synthetic_audit_with_both_purge_types_and_title(engine):
    report = checker.reconcile(*synthetic_result(engine))
    assert report['status'] == 'pass', report['failed_checks']
    assert report['candidate_records'] == 4 and report['historical_title_records'] == 1


@pytest.mark.parametrize('mutation,fragment', [
    ('missing_survivor', 'survivor'), ('missing_purge', 'purge IDs'),
    ('thread_drift', 'metadata binding'), ('graph_drift', 'reconstructs saved components'),
    ('scope_drift', 'Unknown content'), ('cap_drift', 'within cap'),
    ('missing_history', 'Historical original node coverage'), ('relation_hash', 'relation canonical hash'),
])
def test_detects_independent_reconciliation_failures(engine, mutation, fragment):
    result, cm, hm = deepcopy(synthetic_result(engine))
    if mutation == 'missing_survivor':
        result['surviving_candidate_ids'] = []
    elif mutation == 'missing_purge':
        result['purge_record_ids'] = []
    elif mutation == 'thread_drift':
        cm['new-thread']['thread_id'] = 'different-original-thread'
    elif mutation == 'graph_drift':
        result['engine_audit']['relations'] = []
    elif mutation == 'scope_drift':
        result['summary']['independence_scope_complete'] = False
    elif mutation == 'cap_drift':
        result['summary']['independent_candidate_pairs'] = 2_000_001
    elif mutation == 'missing_history':
        hm.pop('old-thread')
    else:
        result['engine_audit']['relations'][0]['relation_id'] = 'changed'
    report = checker.reconcile(result, cm, hm)
    assert report['status'] == 'fail'
    assert any(fragment in message for message in report['failed_checks'])


def test_missing_historical_content_remains_unknown_but_available_grouping_can_pass(engine):
    new, old = [candidate('new')], [historical('old')]
    old[0]['record'].update(status='removed', text=None)
    result = wrapper.run_audit(new, old, engine)
    report = checker.reconcile(result, *metadata(new, old))
    assert report['status'] == 'pass' and report['gate_b_ready']
    assert report['unknown_scope_flags'] == ['unobserved_content_relationships_unknown']


def test_missing_historical_thread_blocks_readiness(engine):
    new, old = [candidate('new')], [historical('old')]
    old[0]['record']['thread_id'] = None
    result = wrapper.run_audit(new, old, engine)
    report = checker.reconcile(result, *metadata(new, old))
    assert report['status'] == 'pass' and not report['gate_b_ready']


def test_checker_uses_no_prose_processor_or_audit_import():
    import ast
    tree = ast.parse(Path(checker.__file__).read_text())
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    imports += [name.name for node in ast.walk(tree) if isinstance(node, ast.Import) for name in node.names]
    assert not set(imports) & {'audit_candidates', 'leakage_audit', 'account_history_analyzer'}
