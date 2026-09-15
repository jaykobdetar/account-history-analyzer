"""Synthetic-only tests of score-free missing-membership intake."""
import importlib.util
import io
import json
import os
from pathlib import Path
import zipfile

import pytest

MODULE = Path(os.environ.get('AHAS_PILOT6_SUPPLEMENT_SCRIPT',
              Path(__file__).resolve().parents[1] / 'scripts/intake_supplement.py'))
HELPER = Path(os.environ.get('AHAS_PILOT4_INTAKE_HELPER',
              Path(__file__).resolve().parents[3] / 'studies/pilot4_chronological_controls/scripts/intake_archives_v2.py'))
spec = importlib.util.spec_from_file_location('pilot6_supplement_tests', MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
CONFIG = {'input': {'max_text_codepoints': 200000}, 'style': {'minimum_record_words': 20}}


def ref(path):
    return {'path': str(path.resolve()), 'bytes': path.stat().st_size, 'sha256': m.sha(path)}


def write(path, data):
    path.write_bytes(m.canonical(data))
    return ref(path)


def flags():
    return {'accounts': [{'account_key': f'protected-{i}',
                         'pilot1_or_pilot2_or_private_mandatory_exclusion': i < 57,
                         'pilot3_selected_scored_exposure': i >= 57,
                         'prior_capacity_only_exposure': False} for i in range(117)]}


def selection():
    return {'selected': {'account_a': 'Pilot5-A', 'account_b': 'PILOT5-B'}}


def frame(account, counts, previous=()):
    return {'account_key': account, 'capacity_only_exposure': False,
            'present_timestamped_comment_counts': counts, 'preprocess_communities': list(previous)}


def raw(community='linux', account='new', rid='new-comment', words=20, **extra):
    return {'id': rid, 'root': 'thread-' + community, 'reply_to': 'parent', 'user': account,
            'timestamp': 1451606400, 'text': ' '.join(['word'] * words),
            'meta': {'subreddit': community}, **extra}


def test_exact40_and_missing_membership_logic_preserves_old80_universe():
    rows = [frame('old', {'linux': 80, 'linuxquestions': 80}, ('linux', 'linuxquestions')),
            frame('new', {'linux': 80, 'linuxquestions': 40}),
            frame('b-role-only', {'linux': 40, 'linuxquestions': 40}),
            frame('short', {'linux': 39, 'linuxquestions': 40}),
            frame('wrong-pair', {'linux': 40, 'programming': 40}),
            frame('protected', {'linux': 40, 'linuxquestions': 40})]
    result = m.derive_memberships(rows, {'protected'}, m.PAIRS)
    assert result['missing'] == {(a, c) for a in ('new', 'b-role-only') for c in ('linux', 'linuxquestions')}
    assert result['wanted'] & result['old'] == {('old', 'linux'), ('old', 'linuxquestions')}
    assert not result['missing'] & result['old']


def test_account_can_reuse_one_pair_and_require_the_other_pair_supplement():
    r = frame('both', {'linux': 80, 'linuxquestions': 80, 'programming': 40, 'learnprogramming': 40},
              ('linux', 'linuxquestions'))
    result = m.derive_memberships([r], set(), m.PAIRS)
    assert result['missing'] == {('both', 'programming'), ('both', 'learnprogramming')}


@pytest.mark.parametrize('change', ['duplicate', 'bad_previous', 'noncanonical', 'boolean_count', 'unknown_community'])
def test_bad_frame_fails_instead_of_changing_memberships(change):
    r = frame('new', {'linux': 40, 'linuxquestions': 40})
    rows = [r]
    if change == 'duplicate': rows.append(dict(r))
    elif change == 'bad_previous': r['preprocess_communities'] = ['linux']
    elif change == 'noncanonical': r['account_key'] = 'NEW'
    elif change == 'boolean_count': r['present_timestamped_comment_counts']['linux'] = True
    else: r['present_timestamped_comment_counts']['unknown'] = 40
    with pytest.raises(ValueError): m.derive_memberships(rows, set(), m.PAIRS)


def test119_exclusions_include_casefolded_pilot5_pair():
    excluded, capacity = m.load_exclusions(flags(), selection())
    assert len(excluded) == 119 and {'pilot5-a', 'pilot5-b'} <= excluded and not capacity


@pytest.mark.parametrize('change', ['duplicate', 'not_boolean', 'overlap', 'one_pilot5', 'missing_prior'])
def test_exclusion_partition_cannot_silently_shrink(change):
    f, s = flags(), selection()
    if change == 'duplicate': f['accounts'].append(dict(f['accounts'][0]))
    elif change == 'not_boolean': f['accounts'][0]['prior_capacity_only_exposure'] = 0
    elif change == 'overlap': s['selected']['account_a'] = 'PROTECTED-0'
    elif change == 'one_pilot5': s['selected']['account_b'] = 'pilot5-a'
    else: f['accounts'].pop()
    with pytest.raises(ValueError): m.load_exclusions(f, s)


def helper():
    return m.load_helper(ref(HELPER))


def source(tmp_path, community, rows):
    data = b''.join(m.canonical(r) for r in rows)
    p = tmp_path / (community + '.zip')
    with zipfile.ZipFile(p, 'w') as archive: archive.writestr('utterances.jsonl', data)
    return {**ref(p), 'community': community, 'source_rows': len(rows),
            'utterances_bytes': len(data), 'utterances_sha256': m.hashlib.sha256(data).hexdigest()}


def preprocessing(calls):
    def process(record, manifest, config):
        assert record['kind'] == 'comment' and manifest == {'default_language': 'en', 'text_format': 'markdown'}
        calls.append(record['id'])
        return {'usable': True, 'word_tokens': [record['text'].split()]}
    return process


def test_excluded_body_and_old_membership_never_enter_availability_or_preprocessing(tmp_path, monkeypatch):
    h = helper()
    original = h.present_comment
    def spy(row, excluded):
        assert row['user'] == 'new'
        return original(row, excluded)
    monkeypatch.setattr(h, 'present_comment', spy)
    rows = [raw(account='PILOT5-A', rid='private'), raw(account='old', rid='old'), raw()]
    calls = []
    output = io.BytesIO()
    result = m.process_archive(source(tmp_path, 'linux', rows), h, {'pilot5-a'}, {('new', 'linux')},
                               CONFIG, preprocessing(calls), m.Budget(m.HARD_LIMITS), set(), output)
    assert calls == ['new-comment'] and result['counts']['metadata_rejected_excluded_account'] == 1
    row = json.loads(output.getvalue())
    assert set(row) == m.OLD_ROW_FIELDS and row['record_id'] == 'new-comment'
    assert row['thread_id'] == 'thread-linux' and row['source_line_sha256']


def test_cross_kind_collision_allowed_but_repeated_comment_id_fatal(tmp_path):
    h = helper(); calls = []; ids = set(); budget = m.Budget(m.HARD_LIMITS)
    first = source(tmp_path, 'linux', [raw(rid='shared')])
    m.process_archive(first, h, set(), {('new', 'linux')}, CONFIG, preprocessing(calls), budget, ids, io.BytesIO())
    second = source(tmp_path, 'linuxquestions', [raw('linuxquestions', rid='shared', root='shared')])
    r = m.process_archive(second, h, set(), set(), CONFIG, preprocessing(calls), budget, ids, io.BytesIO())
    assert r['counts']['submission_rows_outside_comment_id_scope'] == 1 and calls == ['shared']
    duplicate = source(tmp_path, 'programming', [raw('programming', rid='shared')])
    with pytest.raises(ValueError, match='duplicate_original_comment_id'):
        m.process_archive(duplicate, h, set(), set(), CONFIG, preprocessing(calls), budget, ids, io.BytesIO())


def test_unusable_oversize_and_short_records_keep_exact_preprocessing_accounting(tmp_path):
    rows = [raw(rid='unavailable', text='[removed]'), raw(rid='oversize', text='x' * 200001),
            raw(rid='short', words=19), raw(rid='long', words=501), raw(rid='normal', words=20)]
    calls = []; output = io.BytesIO(); budget = m.Budget(m.HARD_LIMITS)
    result = m.process_archive(source(tmp_path, 'linux', rows), helper(), set(), {('new', 'linux')},
                               CONFIG, preprocessing(calls), budget, set(), output)
    assert calls == ['short', 'long', 'normal'] and budget.calls == 3
    assert [json.loads(line)['retained_words'] for line in output.getvalue().splitlines()] == [19, 501, 20]
    assert result['eligibility']['registered_record_bound_records'] == 1
    assert result['eligibility']['frozen_eligible_records'] == 2


@pytest.mark.parametrize('kind', ['call', 'row', 'metadata', 'private', 'wall'])
def test_hard_limits_fail_before_next_call_or_write(tmp_path, monkeypatch, kind):
    limits = dict(m.HARD_LIMITS)
    if kind == 'call': limits['max_preprocessed_records'] = 1
    elif kind == 'row': limits['max_source_rows_per_pass'] = 1
    elif kind == 'metadata': limits['max_eligibility_output_bytes'] = 1
    elif kind == 'private': limits['max_private_output_bytes'] = 1
    b = m.Budget(limits)
    if kind == 'wall': b.started -= 3601
    calls = []; output = io.BytesIO()
    with pytest.raises((RuntimeError, TimeoutError)):
        m.process_archive(source(tmp_path, 'linux', [raw(rid='first'), raw(rid='second')]), helper(), set(),
                          {('new', 'linux')}, CONFIG, preprocessing(calls), b, set(), output)
    assert len(calls) <= 1
    if kind in {'metadata', 'private', 'wall'}: assert not output.getvalue()


@pytest.mark.parametrize('change', ['member_hash', 'row_count', 'archive_hash', 'community'])
def test_source_binding_mismatches_fail(tmp_path, change):
    s = source(tmp_path, 'linux', [raw()])
    if change == 'member_hash': s['utterances_sha256'] = '0' * 64
    elif change == 'row_count': s['source_rows'] += 1
    elif change == 'archive_hash': s['sha256'] = '0' * 64
    else: s['community'] = 'linuxquestions'
    with pytest.raises(ValueError):
        m.process_archive(s, helper(), set(), set(), CONFIG, preprocessing([]), m.Budget(m.HARD_LIMITS), set(), io.BytesIO())


def run_fixture(tmp_path, monkeypatch, call_cap=2_000_000):
    monkeypatch.setenv('AHAS_NETWORK_ISOLATION', 'linux_seccomp_socket_denial')
    monkeypatch.setattr(m.resource, 'setrlimit', lambda *a: None)
    h = helper(); calls = []
    monkeypatch.setattr(h, 'load_engine', lambda plan: (CONFIG, preprocessing(calls), {'fixture': True}))
    monkeypatch.setattr(m, 'load_helper', lambda reference: h)
    rows = {}; sources = []; old_metadata = []
    for c in ('linux', 'linuxquestions'):
        rows[c] = [raw(c, 'old', f'{c}-old-{i}') for i in range(80)]
        rows[c] += [raw(c, 'new', f'{c}-new-{i}') for i in range(40)]
        rows[c] += [raw(c, 'PILOT5-A', f'{c}-pilot5-{i}') for i in range(40)]
        for r in rows[c][:80]:
            item, _, _ = h.preprocess_comment(r, c, set(), CONFIG, preprocessing([]))
            item['source_line_sha256'] = m.hashlib.sha256(m.canonical(r)).hexdigest()
            old_metadata.append(item)
    for c in ('programming', 'learnprogramming'):
        rows[c] = [raw(c, rid=c + '-submission', root=c + '-submission')]
    for c in ('linux', 'linuxquestions', 'programming', 'learnprogramming'):
        sources.append(source(tmp_path, c, rows[c]))
    f = tmp_path / 'frame.jsonl'
    f.write_bytes(b''.join(m.canonical(r) for r in [
        frame('old', {'linux': 80, 'linuxquestions': 80}, ('linux', 'linuxquestions')),
        frame('new', {'linux': 40, 'linuxquestions': 40}),
        frame('pilot5-a', {'linux': 40, 'linuxquestions': 40})]))
    e = tmp_path / 'existing.jsonl'; e.write_bytes(b''.join(m.canonical(r) for r in old_metadata))
    old_plan = {'community_pairs': m.PAIRS, 'raw_present_comments_per_community_min': 80,
                'record_word_min': 20, 'record_word_max': 500}
    op = write(tmp_path / 'old-plan.json', old_plan)
    old_summary = {'status': 'completed_score_free_archive_intake', 'implementation_sha256': m.sha(HELPER),
                   'plan_sha256': op['sha256'], 'eligibility_metadata_bytes': e.stat().st_size,
                   'eligibility_metadata_sha256': m.sha(e), 'counts': {'eligibility_metadata_rows': len(old_metadata)},
                   'source_bindings': [{'community': s['community'], 'archive_bytes': s['bytes'],
                     'archive_sha256': s['sha256'], 'utterances_bytes': s['utterances_bytes'],
                     'utterances_sha256': s['utterances_sha256'], 'counts': {'rows': s['source_rows']}} for s in sources]}
    limits = dict(m.HARD_LIMITS, max_preprocessed_records=call_cap)
    plan = {'limits': limits, 'community_pairs': m.PAIRS, 'raw_present_comments_per_community_min': 40,
            'original_intake_helper': ref(HELPER), 'original_intake_plan': op,
            'original_intake_summary': write(tmp_path / 'old-summary.json', old_summary),
            'exposure_flags': write(tmp_path / 'flags.json', flags()),
            'pilot5_selection': write(tmp_path / 'selection.json', selection()),
            'account_frame': ref(f), 'existing_eligibility': ref(e), 'sources': sources}
    pp = tmp_path / 'plan.json';write(pp, plan)
    rp = tmp_path / 'registration.json'
    write(rp, {'plan_sha256': m.sha(pp), 'implementation_sha256': m.sha(MODULE), 'test_files': [ref(Path(__file__))]})
    return (pp, rp, tmp_path / 'public', tmp_path / 'private'), calls


def test_full_synthetic_supplement_reuses_old_metadata_and_preserves_new_source_ids(tmp_path, monkeypatch, capsys):
    args, calls = run_fixture(tmp_path, monkeypatch)
    assert m.run(*args) == 0
    d = json.loads((args[2] / 'intake-summary.json').read_bytes())
    assert d['preprocessing_calls'] == len(calls) == 80 and d['existing_metadata_rows'] == 160
    assert d['source_rows'] == 322 and d['source_passes'] == 1
    assert d['membership_summary']['supplement_memberships'] == 2
    assert d['excluded_accounts'] == 119 and not d['calendar_capacity_evaluated'] and not d['cohort_selected']
    rows = [json.loads(line) for line in (args[3] / 'record-eligibility.jsonl').read_bytes().splitlines()]
    assert len(rows) == 80 and {r['account_key'] for r in rows} == {'new'}
    assert {r['record_id'] for r in rows} == set(calls)
    assert all(set(r) == m.OLD_ROW_FIELDS for r in rows)
    assert (args[3].stat().st_mode & 0o777) == 0o700
    assert all((p.stat().st_mode & 0o777) == 0o600 for p in args[3].iterdir())
    public = ''.join(p.read_text() for p in args[2].iterdir()) + capsys.readouterr().out
    assert 'linux-new-0' not in public and 'pilot5-a' not in public and 'account_key' not in public


def test_incomplete_supplement_is_not_zero_capacity_and_keeps_partial(tmp_path, monkeypatch):
    args, calls = run_fixture(tmp_path, monkeypatch, call_cap=1)
    assert m.run(*args) == 1 and len(calls) == 1
    assert not (args[2] / 'intake-summary.json').exists()
    d = json.loads((args[2] / 'incomplete-intake.json').read_bytes())
    assert d['status'] == 'incomplete_not_zero_capacity' and d['preprocessing_calls'] == 1


@pytest.mark.parametrize('change', ['changed_frame', 'changed_exclusion', 'changed_registration', 'missing_test'])
def test_preflight_binding_failure_runs_no_preprocessing(tmp_path, monkeypatch, change):
    args, calls = run_fixture(tmp_path, monkeypatch)
    p = json.loads(args[0].read_bytes())
    if change == 'changed_frame': Path(p['account_frame']['path']).write_bytes(b'{}\n')
    elif change == 'changed_exclusion': Path(p['exposure_flags']['path']).write_bytes(b'{}\n')
    else:
        r = json.loads(args[1].read_bytes())
        if change == 'changed_registration': r['implementation_sha256'] = '0' * 64
        else: r['test_files'] = []
        write(args[1], r)
    assert m.run(*args) == 1 and not calls
    assert json.loads((args[2] / 'incomplete-intake.json').read_bytes())['status'] == 'incomplete_not_zero_capacity'


def test_preexisting_destinations_not_overwritten(tmp_path, monkeypatch):
    args, calls = run_fixture(tmp_path, monkeypatch)
    args[2].mkdir(); (args[2] / 'sentinel').write_text('keep')
    with pytest.raises(ValueError, match='fresh_separate_destinations_required'): m.run(*args)
    assert (args[2] / 'sentinel').read_text() == 'keep' and not calls
