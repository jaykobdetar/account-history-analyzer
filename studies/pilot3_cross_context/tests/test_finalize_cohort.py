"""Synthetic metadata fixtures only; no corpus input or distance evaluation."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import finalize_cohort as final
import prepare_units as units


def fixture(accounts=20, records=12):
    strata, pool, provenance, components = [], [], {}, []
    for index in range(3):
        sid = f'synthetic-stratum-{index}'
        communities = [f'community-{index}-x', f'community-{index}-y']
        strata.append({'id': sid, 'communities': communities,
                       'scheme': {'early': ['2017-01-01', '2018-01-01'],
                                  'late': ['2018-01-01', '2019-01-01']}})
        for account_index in range(accounts):
            account = f'private-source-{index}-{account_index:02d}'
            for community in communities:
                for part, year in [('early', 2017), ('late', 2018)]:
                    for r in range(records):
                        rid = f'{account}-{community}-{part}-{r:02d}'
                        record = {'schema_version': '1.0.0', 'id': rid, 'account_id': account,
                                  'kind': 'comment', 'status': 'present', 'text': 'synthetic prose ' * 125,
                                  'created_utc': f'{year}-07-{r+1:02d}T00:00:00Z',
                                  'subreddit': community, 'language': None, 'edit_state': 'unknown',
                                  'thread_id': 'thread-' + rid, 'parent_id': 'parent-' + rid}
                        entry = {'record': record, 'retained_words': 250, 'account_key': account,
                                 'stratum_id': sid, 'community': community, 'period': part}
                        pool.append(entry)
                        provenance[rid] = {'source_record_id': rid, 'source_kind': 'comment', 'historical': False,
                            'account_key': account, 'stratum_id': sid, 'cell': [account, community, part],
                            'thread_id': record['thread_id'], 'declared_retained_words': 250}
                        components.append({'cluster_id': 'synthetic-component-' + str(len(components)), 'record_ids': [rid]})
    # A constructed metadata response tests selection only; it is not a claim that
    # the repeated fixture prose passed the real leakage engine.
    audit = {'summary': {'status': 'audited', 'gate_b_ready': True,
                        'available_content_and_grouping_audit_complete': True,
                        'unknown_scope_flags': ['unobserved_content_relationships_unknown']},
             'actionable': True, 'purge_record_ids': [],
             'surviving_candidate_ids': [r['record']['id'] for r in pool],
             'record_provenance': provenance,
             'engine_audit': {'status': 'audited', 'components': components}}
    return pool, audit, strata


@pytest.fixture(scope='module')
def full_result():
    pool, audit, strata = fixture()
    return final.finalize(pool, audit, strata)


def test_full_sixty_account_selection_has_all_cells_and_fixed_private_pairs(full_result):
    result = full_result
    assert result['summary']['status'] == 'cohort_selected_not_scored'
    assert result['summary']['selected_accounts'] == 60
    assert result['summary']['selected_blocks'] == 30
    assert result['summary']['full_cells'] == 240
    assert result['summary']['selected_original_records'] == 1920
    assert result['summary']['selected_retained_words'] == 480000
    assert len(set(result['selected_record_ids'])) == 1920
    assert len({a for b in result['blocks'] for a in b['account_keys'].values()}) == 60
    assert all(len(b['comparisons']) == 16 for b in result['blocks'])
    assert all(len(rows) == 8 for b in result['blocks'] for rows in b['cells'].values())
    assert result['summary']['effective_units_by_stratum'] == {f'synthetic-stratum-{i}': 10 for i in range(3)}
    assert result['summary']['audit_unknown_scope_flags'] == ['unobserved_content_relationships_unknown']


def test_selection_is_deterministic_and_preserves_original_objects_and_text():
    pool, audit, strata = fixture()
    before = deepcopy(pool)
    first = final.finalize(pool, audit, strata)
    second = final.finalize(list(reversed(pool)), audit, list(reversed(strata)))
    assert first == second
    assert pool == before
    original_by_id = {r['record']['id']: r for r in pool}
    assert all(entry is original_by_id[entry['record']['id']]
               for block in first['blocks'] for rows in block['cells'].values() for entry in rows)
    for match in first['matching'].values():
        hashes = sorted(h for p in match['pairs'] for h in p['account_hashes'])
        assert [p['account_hashes'] for p in match['pairs']] == [hashes[i:i+2] for i in range(0, 20, 2)]


def purge(audit, ids):
    audit['purge_record_ids'] = sorted(ids)
    audit['surviving_candidate_ids'] = sorted(set(audit['surviving_candidate_ids']) - set(ids))


def test_purges_are_exact_and_audited_buffer_records_can_supply_full_targets():
    pool, audit, strata = fixture(accounts=21)
    removed = {pool[0]['record']['id']}
    purge(audit, removed)
    result = final.finalize(pool, audit, strata)
    assert result['summary']['selected_accounts'] == 60
    assert not removed & set(result['selected_record_ids'])
    assert set(result['selected_record_ids']) <= set(audit['surviving_candidate_ids'])
    assert result['summary']['purged_records'] == 1


def test_failed_surviving_capacity_never_produces_a_reduced_cohort_or_refills():
    pool, audit, strata = fixture()
    purge(audit, [e['record']['id'] for e in pool[:5]])  # One required cell has only seven records.
    result = final.finalize(pool, audit, strata)
    assert result['summary']['status'] == 'failed_surviving_capacity'
    assert result['summary']['available_capacity_accounts'] == 58
    assert result['summary']['selected_accounts'] == 0
    assert result['summary']['missing_accounts_by_stratum']['synthetic-stratum-0'] == 2
    assert result['blocks'] == [] and result['groups'] is None
    assert result['summary']['scores_computed'] is False


@pytest.mark.parametrize('field', ['gate_b_ready', 'available_content_and_grouping_audit_complete', 'status'])
def test_failed_or_incomplete_audit_blocks_selection(field):
    pool, audit, strata = fixture(accounts=1)
    audit['summary'][field] = False
    with pytest.raises(final.FinalizationFailure, match='complete_available_content_grouping_audit_required'):
        final.finalize(pool, audit, strata)


@pytest.mark.parametrize('change,code', [
    ('unknown_survivor', 'audit_candidate_partition_mismatch'),
    ('overlap', 'audit_candidate_partition_mismatch'),
    ('metadata', 'audit_pool_metadata_mismatch'),
    ('missing_thread', 'selected_thread_metadata_missing'),
    ('lost_component', 'audit_content_component_coverage_mismatch'),
])
def test_invalid_audit_membership_or_source_metadata_fails(change, code):
    pool, audit, strata = fixture(accounts=1)
    if change == 'unknown_survivor': audit['surviving_candidate_ids'].append('unaudited-new-record')
    if change == 'overlap': audit['purge_record_ids'].append(pool[0]['record']['id'])
    if change == 'metadata': audit['record_provenance'][pool[0]['record']['id']]['declared_retained_words'] = 251
    if change == 'missing_thread': pool[0]['record']['thread_id'] = None
    if change == 'lost_component': audit['engine_audit']['components'].pop()
    with pytest.raises(final.FinalizationFailure, match=code):
        final.finalize(pool, audit, strata)


def test_candidate_selection_metadata_is_checked_without_refilling():
    pool, audit, strata = fixture(accounts=1)
    selected = {e['record']['id']: {'record_id': e['record']['id'], 'created_utc': e['record']['created_utc'],
                                 **{k: e[k] for k in ('account_key', 'stratum_id', 'community', 'period', 'retained_words')}}
                for e in pool}
    selection = {'selected_record_metadata': selected,
                 'allocation': {'assigned': {s['id']: sorted({e['account_key'] for e in pool if e['stratum_id'] == s['id']}) for s in strata}}}
    result = final.finalize(pool, audit, strata, candidate_selection=selection)
    assert result['summary']['status'] == 'failed_surviving_capacity'
    selected[next(iter(selected))]['created_utc'] = '2017-01-01T00:00:00Z'
    with pytest.raises(final.FinalizationFailure, match='candidate_selection_metadata_mismatch'):
        final.finalize(pool, audit, strata, candidate_selection=selection)


def test_residual_content_and_thread_edges_merge_transitively_across_blocks(full_result):
    blocks = deepcopy(full_result['blocks'])
    first, second, third = blocks[:3]
    ids = [b['cells']['A/X/early'][0]['record']['id'] for b in (first, second, third)]
    components = [{'cluster_id': 'component-' + str(n), 'record_ids': [rid]} for n, rid in enumerate(full_result['selected_record_ids'])
                  if rid not in ids[:2]]
    components.append({'cluster_id': 'residual-content', 'record_ids': ids[:2]})
    second['cells']['A/X/early'][1]['record']['thread_id'] = 'residual-thread'
    third['cells']['A/X/early'][1]['record']['thread_id'] = 'residual-thread'
    groups = final.block_groups(blocks, {'engine_audit': {'components': components}})
    assert len({groups['unit_by_block'][b['block_id']] for b in (first, second, third)}) == 1
    assert len(groups['units']) == 28
    assert groups['effective_units_by_stratum']['synthetic-stratum-0'] == 8
    assert {edge['kind'] for edge in groups['cross_block_edges']} == {'content', 'thread'}


def test_public_summary_has_pseudonyms_and_statistics_without_source_identity_or_prose(full_result):
    public = json.dumps(full_result['summary'])
    assert 'stratum-01-block-01' in public
    assert all(secret not in public for secret in ('private-source-', 'synthetic prose', 'thread-private-'))
    assert 'nearest_rank_word_quantiles' in public and 'early_late_gaps' in public


def registration(cohort):
    return {'registered_before_evaluation': True,
            'preregistration_provenance': 'Explicit synthetic fixture registration; no empirical study.',
            'protocol_sha256': 'a' * 64,
            'final_cohort_sha256': hashlib.sha256(final.canonical(cohort)).hexdigest()}


def test_export_requires_separate_scoring_registration_and_same_cohort(tmp_path, full_result):
    with pytest.raises(final.FinalizationFailure, match='separate_frozen_scoring_protocol_required'):
        final.export_all_batches(tmp_path/'missing', full_result, registration={}, provenance='Synthetic fixture.')
    bad = registration(full_result); bad['final_cohort_sha256'] = 'b' * 64
    with pytest.raises(final.FinalizationFailure, match='registered_final_cohort_hash_mismatch'):
        final.export_all_batches(tmp_path/'changed', full_result, registration=bad, provenance='Synthetic fixture.')
    assert not (tmp_path/'missing').exists() and not (tmp_path/'changed').exists()


def test_export_all_360_fixed_batches_and_runner_index_without_evaluator(tmp_path, full_result):
    root = tmp_path/'all-batches'
    result = final.export_all_batches(root, full_result, registration=registration(full_result),
                                     provenance='Constructed synthetic fixture, no empirical data.', source_category='synthetic')
    assert result['summary']['batches'] == 360
    assert result['summary']['method_arm_comparisons'] == 5760
    assert result['summary']['arm_batch_counts'] == {arm: 90 for arm in units.ARMS}
    assert result['summary']['scores_computed'] is False
    index = json.loads((root/'batch-index.json').read_bytes())
    assert isinstance(index, list) and len(index) == 360
    for row in index:
        assert re.fullmatch('[a-z0-9_-]+', row['batch_id'])
        assert row['dataset_sha256'] == final.sha_file(root/row['dataset'])
        assert len(row['input_hashes']) == 17
        assert all(final.sha_file(root/name) == value for name, value in row['input_hashes'].items())
        assert row['unique_records'] <= 10000 and row['invocation_input_bytes'] <= 50 * 1024**2
    unit_rows = json.loads((root/'unit-metadata.json').read_bytes())
    assert len(unit_rows) == 960
    assert all({'stratum_id', 'block_id', 'arm', 'cell_id', 'records', 'retained_words', 'nonempty',
                'ordinary_volume_guards_met'} <= set(r) for r in unit_rows)
    assert all(r['records'] == 4 and not r['ordinary_volume_guards_met'] for r in unit_rows if r['arm'] == 'middle50')
    assert json.loads((root/'dependency-units.json').read_bytes()) == full_result['groups']['unit_by_block']
    assert root.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in root.rglob('*') if p.is_file())
    # Check exported original records and each comparison's disjoint sides in one batch.
    row = next(r for r in index if r['arm'] == 'full')
    dataset = json.loads((root/row['dataset']).read_bytes())
    texts = {t['text_id']: [json.loads(line) for line in (root/Path(row['dataset']).parent/t['input']).read_bytes().splitlines()]
             for t in dataset['texts']}
    assert all(record['text'] == 'synthetic prose ' * 125 for values in texts.values() for record in values)
    for pair in dataset['pairs']:
        assert not {r['id'] for r in texts[pair['left_text_id']]} & {r['id'] for r in texts[pair['right_text_id']]}


def test_offline_cli_selects_full_synthetic_cohort_with_exact_bindings(tmp_path):
    pool, audit, strata = fixture()
    locations = {key: tmp_path/(key + '.json') for key in ('candidate_pool', 'audit', 'candidate_selection', 'candidate_plan')}
    locations['candidate_pool'].write_bytes(b''.join(final.canonical(row) for row in pool))
    locations['audit'].write_bytes(final.canonical(audit))
    selected = {e['record']['id']: {'record_id': e['record']['id'], 'created_utc': e['record']['created_utc'],
                                 **{k: e[k] for k in ('account_key', 'stratum_id', 'community', 'period', 'retained_words')}}
                for e in pool}
    selection = {'selected_record_metadata': selected,
                 'allocation': {'assigned': {s['id']: sorted({e['account_key'] for e in pool if e['stratum_id'] == s['id']}) for s in strata}}}
    locations['candidate_selection'].write_bytes(final.canonical(selection))
    locations['candidate_plan'].write_bytes(final.canonical({'full_target': final.TARGET,
        'phase': 'registered_score_free_candidate_pool', 'strata': strata}))
    dependencies = {**locations, 'wrapper': Path(final.__file__), 'prepare_units': Path(units.__file__),
                    'cohort_selection': Path(final.__file__).with_name('cohort_selection.py'),
                    'study_math': Path(final.__file__).with_name('study_math.py')}
    freeze = tmp_path/'freeze.json'
    freeze.write_bytes(final.canonical({'state': 'frozen_before_final_selection',
                      **{key + '_sha256': final.sha_file(path) for key, path in dependencies.items()}}))
    output, public = tmp_path/'private-cohort', tmp_path/'public-cohort.json'
    offline = os.environ.get('AHAS_PILOT3_OFFLINE_RUNNER', '/tmp/ahas-pilot3-reviewed-repo/scripts/offline_exec.py')
    command = [sys.executable, offline, sys.executable, final.__file__]
    for key, value in {**locations, 'freeze': freeze, 'out_private': output, 'out_public': public}.items():
        command.extend(['--' + key.replace('_', '-'), str(value)])
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ''
    summary = json.loads(result.stdout)
    assert summary['status'] == 'cohort_selected_not_scored' and summary['selected_accounts'] == 60
    assert summary['private_cohort_sha256'] == final.sha_file(output/'cohort.json')
    assert all(secret not in result.stdout for secret in ('private-source-', 'synthetic prose', str(tmp_path)))
    assert output.stat().st_mode & 0o777 == 0o700
    assert (output/'cohort.json').stat().st_mode & 0o777 == 0o600
