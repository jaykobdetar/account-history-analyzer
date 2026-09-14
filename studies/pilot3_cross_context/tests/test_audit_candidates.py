"""Synthetic-only Gate B tests. No historical source pool is opened."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import audit_candidates as wrapper

TEXT = 'amber birch cedar dahlia elm fern garden hazel iris jasmine kiwi lavender maple nettle olive pine quince rose sage thyme'
OTHER = 'violet willow xylem yarrow zinnia acacia bamboo clover dogwood elder fig grape heather juniper kelp lilac moss nutmeg orchid parsley'


@pytest.fixture(scope='module')
def engine():
    path = Path(os.environ.get('AHAS_PILOT3_ENGINE_PATH',
        str(Path(__file__).resolve().parents[2] / 'pilot2/scripts/leakage_audit.py')))
    return wrapper.load_engine(path)


def candidate(identifier, text=TEXT, *, account='a', community='X', period='early', thread=None):
    return {'account_key': account, 'stratum_id': 'stratum', 'community': community,
            'period': period, 'retained_words': len(text.split()),
            'record': {'id': identifier, 'account_id': account, 'kind': 'comment',
                'status': 'present', 'text': text, 'title': None, 'language': None,
                'subreddit': community, 'created_utc': '2017-07-01T00:00:00Z',
                'thread_id': thread or 'thread-' + identifier, 'parent_id': 'parent'}}


def historical(identifier, text=OTHER, *, account='old', split='development', thread=None,
               kind='comment', title=None):
    return {'account_key': account, 'original_split': split, 'source_id': 'historical-source',
            'record': {'id': identifier, 'kind': kind, 'status': 'present', 'text': text,
                'title': title, 'language': None, 'subreddit': 'old-community',
                'created_utc': '2016-07-01T00:00:00Z', 'thread_id': thread or 'thread-' + identifier,
                'parent_id': 'old-parent'}}


def test_cross_cell_exact_content_is_symmetrically_purged(engine):
    entries = [candidate('first'), candidate('second', period='late')]
    before = deepcopy(entries)
    result = wrapper.run_audit(entries, [], engine)
    assert result['purge_record_ids'] == ['first', 'second']
    assert result['purge_reasons']['first'] == ['content_cross_candidate_cells']
    assert result['engine_audit']['excluded_ids'] == []  # Engine split-only purge is insufficient.
    assert entries == before


def test_same_cell_content_and_planned_anchor_reuse_are_not_cross_cell_purges(engine):
    result = wrapper.run_audit([candidate('first'), candidate('second')], [], engine)
    assert result['purge_record_ids'] == []
    # The comparison schedule reuses the cell; audit input contains each source record once.
    with pytest.raises(wrapper.AuditFailure, match='candidate_original_id_repeated'):
        wrapper.run_audit([candidate('first'), candidate('first')], [], engine)


def test_cross_cell_threads_are_purged_without_content_similarity(engine):
    result = wrapper.run_audit([candidate('first', thread='shared'),
        candidate('second', OTHER, account='b', thread='shared')], [], engine)
    assert result['purge_record_ids'] == ['first', 'second']
    assert all(v == ['thread_cross_candidate_cells'] for v in result['purge_reasons'].values())


def test_reserve_content_and_historical_threads_protect_new_candidates(engine):
    result = wrapper.run_audit([candidate('new'), candidate('thread-only', OTHER, thread='old-thread')],
        [historical('reserve', TEXT, split='confirmation'),
         historical('old-thread-record', 'short source', account='other-old', thread='old-thread')], engine)
    assert result['purge_record_ids'] == ['new', 'thread-only']
    assert result['purge_reasons']['new'] == ['content_historical_boundary']
    assert result['purge_reasons']['thread-only'] == ['thread_historical_boundary']


def test_historical_overlap_alone_does_not_choose_new_participants(engine):
    result = wrapper.run_audit([candidate('new')],
        [historical('old-one'), historical('old-two', account='another-old', split='confirmation')], engine)
    assert result['purge_record_ids'] == []


def test_template_and_recognized_blockquote_relations_use_frozen_engine(engine):
    phrase = ' '.join(TEXT.split()[:15])
    templates = [candidate('one', phrase + ' ' + ' '.join(OTHER.split()[:5]), account='a'),
                 candidate('two', phrase + ' ' + ' '.join(OTHER.split()[5:10]), account='b'),
                 candidate('three', phrase + ' ' + ' '.join(OTHER.split()[10:15]), account='c')]
    templated = wrapper.run_audit(templates, [], engine)
    assert templated['summary']['content_relation_counts']['template'] > 0
    assert templated['purge_record_ids'] == ['one', 'three', 'two']
    quoted = candidate('quoted', '> ' + phrase + '\n\n' + OTHER)
    quoted['retained_words'] = 20  # Recognized blockquote is excluded from retained candidate words.
    result = wrapper.run_audit([quoted], [historical('old', TEXT)], engine)
    assert result['summary']['content_relation_counts']['quotation'] > 0
    assert result['purge_record_ids'] == ['quoted']


def test_unavailable_historical_body_keeps_unknown_content_disclosure(engine):
    old = historical('unavailable')
    old['record'].update(status='removed', text=None)
    result = wrapper.run_audit([candidate('new')], [old], engine)
    assert result['summary']['content_unobservable_record_count'] == 1
    assert result['summary']['unknown_scope_flags'] == ['unobserved_content_relationships_unknown']
    assert result['summary']['independence_scope_complete'] is False
    assert result['summary']['available_content_and_grouping_audit_complete'] is True


def test_missing_new_thread_fails_and_missing_old_thread_cannot_pass_gate(engine):
    new = candidate('new'); new['record']['thread_id'] = None
    with pytest.raises(wrapper.AuditFailure, match='candidate_thread_missing'):
        wrapper.run_audit([new], [], engine)
    old = historical('old'); old['record']['thread_id'] = None
    result = wrapper.run_audit([candidate('new')], [old], engine)
    assert result['summary']['historical_missing_thread_records'] == 1
    assert result['summary']['gate_b_ready'] is False


def test_submission_titles_are_separate_exact_protection_without_mutation(engine):
    old = historical('post', OTHER, kind='submission', title=TEXT)
    before = deepcopy(old)
    result = wrapper.run_audit([candidate('new', TEXT)], [old], engine)
    assert result['purge_record_ids'] == ['new']
    assert result['summary']['historical_title_protection_records'] == 1
    title_ids = [i for i in result['record_provenance'] if i.startswith(wrapper.TITLE_PREFIX)]
    assert len(title_ids) == 1
    assert result['record_provenance'][title_ids[0]]['source_kind'] == 'submission'
    assert result['record_provenance'][title_ids[0]]['source_record_id'] == 'post'
    assert old == before
    rows, _ = wrapper.historical_rows([historical('short-title', kind='submission', title='short title')])
    assert any(r['text'] == 'short title' for r in rows)  # No 20-word filter discards protection titles.


def test_historical_duplicates_dedupe_and_conflicts_are_fatal():
    old = historical('old')
    rows, _ = wrapper.historical_rows([old, deepcopy(old)])
    assert len(rows) == 1
    for field, changed in [('text', TEXT), ('thread_id', 'changed-thread'), ('created_utc', '2000')]:
        changed_record = deepcopy(old); changed_record['record'][field] = changed
        with pytest.raises(wrapper.AuditFailure, match='conflicting_historical_original_id'):
            wrapper.historical_rows([old, changed_record])
    changed_split = deepcopy(old); changed_split['original_split'] = 'evaluation'
    with pytest.raises(wrapper.AuditFailure, match='conflicting_historical_original_id'):
        wrapper.historical_rows([old, changed_split])


def test_no_original_or_account_reuse_across_history(engine):
    with pytest.raises(wrapper.AuditFailure, match='candidate_original_id_overlaps_history'):
        wrapper.run_audit([candidate('shared')], [historical('shared')], engine)
    with pytest.raises(wrapper.AuditFailure, match='candidate_account_overlaps_history'):
        wrapper.run_audit([candidate('new')], [historical('old', account='a')], engine)


def test_independent_broad_pairs_include_pairs_that_are_not_near(engine):
    second_text = ' '.join(TEXT.split()[:5] + OTHER.split()[5:])
    entries = [candidate('one'), candidate('two', second_text, account='b')]
    result = wrapper.run_audit(entries, [], engine)
    assert result['summary']['independent_candidate_pairs'] == 1
    assert result['summary']['content_relation_counts']['near'] == 0
    assert result['purge_record_ids'] == []
    rows, _ = wrapper.candidate_rows(entries)
    capped = wrapper.independent_candidate_pair_count(rows, cap=0)
    assert capped['complete'] is False and capped['candidate_pairs'] == 1


def test_broad_pairs_include_repetitive_records_ineligible_for_engine_candidates(engine):
    repetitive = ' '.join(['amber'] * 20)
    result = wrapper.run_audit([candidate('one', repetitive), candidate('two', repetitive)], [], engine)
    assert result['summary']['independent_candidate_pairs'] == 1
    assert result['summary']['independent_engine_eligible_candidate_pairs'] == 0
    assert result['summary']['engine_candidate_pair_count'] == 0
    assert result['summary']['gate_b_ready'] is True


def test_engine_failure_and_independent_cap_return_no_actionable_ids(engine, monkeypatch):
    class Capped:
        def audit_records(self, rows, *, max_candidate_pairs):
            assert max_candidate_pairs == 2_000_000
            return {'status': 'not_auditable', 'summary': {'reason_codes': ['candidate_pair_cap_exceeded']}}
    result = wrapper.run_audit([candidate('new')], [], Capped())
    assert result['actionable'] is False and result['purge_record_ids'] == []
    assert result['surviving_candidate_ids'] == []
    monkeypatch.setattr(wrapper, 'independent_candidate_pair_count', lambda rows:
        {'complete': False, 'candidate_pairs': 2_000_001, 'engine_eligible_candidate_pairs': 0,
         'count_is_lower_bound': True, 'word_counts': {}})
    result = wrapper.run_audit([candidate('new')], [], engine)
    assert not result['actionable'] and not result['surviving_candidate_ids']


def test_word_count_binding_and_candidate_limits(engine, monkeypatch):
    new = candidate('new'); new['retained_words'] = 21
    with pytest.raises(wrapper.AuditFailure, match='candidate_frozen_word_count_mismatch'):
        wrapper.run_audit([new], [], engine)
    monkeypatch.setattr(wrapper, 'MAX_CANDIDATE_WORDS', 19)
    with pytest.raises(wrapper.AuditFailure, match='candidate_word_ceiling'):
        wrapper.run_audit([candidate('new')], [], engine)


def test_public_summary_contains_no_text_identity_or_source_ids(engine):
    result = wrapper.run_audit([candidate('sensitive-new-id', account='sensitive-account')],
        [historical('sensitive-old-id')], engine)
    public = json.dumps(result['summary'], sort_keys=True)
    assert all(secret not in public for secret in [TEXT, OTHER, 'sensitive-new-id',
                                                  'sensitive-old-id', 'sensitive-account'])


def test_inventory_loader_checks_hashes_and_projects_only_bound_source_rows(tmp_path):
    old = historical('old')
    source = tmp_path/'source.jsonl'; source.write_bytes(wrapper.canonical(old['record']))
    inventory = {'complete_for_requested_known_protection_sources': True, 'files': [
        {'path': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
         'bytes': source.stat().st_size, 'format': 'record_jsonl', 'record_count': 1,
         'source_id': 'source-one', 'records_metadata': [{'record_id': 'old',
             'account_key': 'old', 'original_split': 'development'}]}]}
    location = tmp_path/'inventory.json'; location.write_bytes(wrapper.canonical(inventory))
    assert wrapper.load_historical_inventory(location)[0]['record'] == old['record']
    source.write_bytes(wrapper.canonical(historical('other')['record']))
    with pytest.raises(wrapper.AuditFailure, match='historical_source_identity_mismatch'):
        wrapper.load_historical_inventory(location)


def test_offline_cli_freeze_bindings_permissions_and_nonoverwrite_are_synthetic(tmp_path, engine):
    candidate_path = tmp_path/'synthetic-candidates.jsonl'
    candidate_path.write_bytes(wrapper.canonical(candidate('private-new', account='private-account')))
    old = historical('private-old')
    source = tmp_path/'synthetic-history.jsonl'; source.write_bytes(wrapper.canonical(old['record']))
    inventory = {'complete_for_requested_known_protection_sources': True, 'files': [
        {'path': str(source), 'sha256': wrapper.file_sha(source),
         'bytes': source.stat().st_size, 'format': 'record_jsonl', 'record_count': 1,
         'source_id': 'synthetic', 'records_metadata': [{'record_id': 'private-old',
             'account_key': 'old', 'original_split': 'development'}]}]}
    inventory_path = tmp_path/'inventory.json'; inventory_path.write_bytes(wrapper.canonical(inventory))
    rules = Path(wrapper.__file__).parents[1]/'protocol/GATE_B_AUDIT_RULES_DRAFT.md'
    bindings = {name + '_sha256': wrapper.file_sha(path) for name, path in
                [('candidate_pool', candidate_path), ('historical_inventory', inventory_path),
                 ('engine', engine.__file__), ('wrapper', wrapper.__file__), ('rules', rules)]}
    freeze = tmp_path/'synthetic-freeze.json'
    freeze.write_bytes(wrapper.canonical({'state': 'frozen_before_audit', **bindings}))
    private, public = tmp_path/'private-output', tmp_path/'public-output.json'
    offline = Path(engine.__file__).parents[3]/'scripts/offline_exec.py'
    command = [sys.executable, str(offline), sys.executable, wrapper.__file__,
        '--candidate-pool', str(candidate_path), '--historical-inventory', str(inventory_path),
        '--engine-path', engine.__file__, '--rules', str(rules), '--freeze', str(freeze),
        '--out-private', str(private), '--out-public', str(public)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ''
    summary = json.loads(result.stdout)
    assert summary['gate_b_ready'] and summary['scores_computed'] is False
    assert private.stat().st_mode & 0o777 == 0o700
    assert (private/'audit.json').stat().st_mode & 0o777 == 0o600
    assert all(secret not in result.stdout for secret in
               (TEXT, OTHER, 'private-account', 'private-new', 'private-old', str(tmp_path)))
    assert TEXT not in (private/'audit.json').read_text()
    before = public.read_bytes()
    rerun = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert rerun.returncode == 4
    assert json.loads(rerun.stdout)['reason_codes'] == ['outputs_already_exist']
    assert public.read_bytes() == before
