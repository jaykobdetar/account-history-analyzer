"""Synthetic census guards and independent checker corruption regressions."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import zipfile

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import census
import check_census


SCHEME = {'id': 'cut', 'early': ['2017-01-01', '2018-01-01'], 'late': ['2018-01-01', '2019-01-01']}


def metadata(account, community, day, count=8, words=250):
    return [{'account_key': account, 'community': community, 'created_utc': day + 'T00:00:00Z',
             'retained_words': words} for _ in range(count)]


@pytest.mark.parametrize('raw, expected', [(None, None), (True, None), ('1483228800', None),
                                         (1483228800.0, None), (1483228800, '2017-01-01T00:00:00Z')])
def test_stamp_accepts_original_integer_utc_only(raw, expected):
    assert census.stamp(raw) == expected


@pytest.mark.parametrize('value, expected', [
    ('2016-12-31T23:59:59Z', None), ('2017-01-01T00:00:00Z', 'early'),
    ('2017-12-31T23:59:59Z', 'early'), ('2018-01-01T00:00:00Z', 'late'),
    ('2018-12-31T23:59:59Z', 'late'), ('2019-01-01T00:00:00Z', None), (None, None),
])
def test_periods_use_half_open_boundaries(value, expected):
    assert census.period(value, SCHEME) == expected


def test_stamp_utc_is_independent_of_local_timezone(monkeypatch):
    monkeypatch.setenv('TZ', 'America/Los_Angeles')
    boundary = int(datetime(2018, 1, 1, tzinfo=timezone.utc).timestamp())
    assert census.period(census.stamp(boundary - 1), SCHEME) == 'early'
    assert census.period(census.stamp(boundary), SCHEME) == 'late'


def test_necessary_prefilter_requires_16_present_timestamped_comments_in_two_communities():
    def cell(n, **extra):
        return Counter(present_timestamped_comments=n, **extra)
    frame = {
        'qualified': {'X': cell(16), 'Y': cell(16)},
        'short_one_side': {'X': cell(16), 'Y': cell(15, comments=500)},
        'one_community': {'X': cell(1000)},
        'huge_raw_counts': {'X': cell(0, comments=1000, present_comments=1000), 'Y': cell(16)},
        'any_two': {'X': cell(0), 'Y': cell(16), 'Z': cell(16)},
    }
    assert census.necessary_accounts(frame) == {'qualified', 'any_two'}


def test_all_four_cells_require_both_experimental_word_and_existing_record_guards():
    good = sum((metadata('good', community, day) for community in ('X', 'Y')
                for day in ('2017-06-01', '2018-06-01')), [])
    short_records = sum((metadata('short_records', community, day, count=7, words=400)
                         for community in ('X', 'Y') for day in ('2017-06-01', '2018-06-01')), [])
    short_words = sum((metadata('short_words', community, day, words=249)
                       for community in ('X', 'Y') for day in ('2017-06-01', '2018-06-01')), [])
    upper, qualified, table, _ = census.capacities(good + short_records + short_words, [('X', 'Y')], [SCHEME])
    assert qualified['X / Y', 'cut'] == {'good'}
    assert upper['X / Y'] == {'good'}
    assert table == [{'community_pair': 'X / Y', 'period_scheme': 'cut', 'four_cell_accounts': 1,
                      'pairwise_blocks_upper_bound': 0}]


def test_all_history_upper_bound_does_not_invent_disjoint_period_capacity():
    rows = metadata('early_only', 'X', '2017-06-01', count=16) + metadata('early_only', 'Y', '2017-06-01', count=16)
    rows += metadata('outside', 'X', '2010-01-01', count=16) + metadata('outside', 'Y', '2020-01-01', count=16)
    upper, qualified, _, _ = census.capacities(rows, [('X', 'Y')], [SCHEME])
    assert upper['X / Y'] == {'early_only', 'outside'}
    assert qualified['X / Y', 'cut'] == set()


def test_period_choice_ties_use_duration_then_id():
    schemes = [
        {'id': 'unbalanced', 'early': ['2016-01-01', '2018-01-01'], 'late': ['2018-01-01', '2019-01-01']},
        {'id': 'z_balanced', 'early': ['2017-01-01', '2018-01-01'], 'late': ['2018-01-01', '2019-01-01']},
        {'id': 'a_balanced', 'early': ['2017-01-01', '2018-01-01'], 'late': ['2018-01-01', '2019-01-01']},
    ]
    equal = {('X / Y', scheme['id']): {'synthetic'} for scheme in schemes}
    assert census.choose_schemes(equal, [('X', 'Y')], schemes)['X / Y']['id'] == 'a_balanced'


@pytest.fixture
def synthetic_census(tmp_path, monkeypatch, capsys):
    source = tmp_path / 'sources'
    source.mkdir()
    private = tmp_path / 'private'
    private.mkdir()
    out = tmp_path / 'synthetic-run'
    plan = json.loads((SCRIPTS.parent / 'protocol/gate_a_plan.json').read_bytes())
    plan['sources'] = []
    plan['community_pairs'] = [['X', 'Y'], ['X', 'Z'], ['Y', 'Z']]
    plan['period_schemes'] = [SCHEME]
    for community in ('X', 'Y', 'Z'):
        rows = []
        if community != 'Z':
            for account in ('good', 'early_only', 'below_guard', 'prefiltered', 'protected'):
                for index in range(15 if account == 'prefiltered' else 16):
                    year = 2017 if index < 8 or account == 'early_only' else 2018
                    text = 'word ' * 250
                    if account == 'below_guard':
                        text = 'word ' * 19 + '`' + 'hidden ' * 400 + '`'
                    rows.append({'id': f'{community}-{account}-{index}', 'root': 'synthetic-thread',
                                 'reply_to': 'synthetic-parent', 'user': account, 'text': text,
                                 'timestamp': int(datetime(year, 6, 1, tzinfo=timezone.utc).timestamp()),
                                 'meta': {'subreddit': community}})
        else:
            rows.append({'id': 'Z-comment', 'root': 'synthetic-thread', 'reply_to': 'synthetic-parent',
                         'user': 'one-community-only', 'text': 'word ' * 250,
                         'timestamp': 1496275200, 'meta': {'subreddit': community}})
        rows.append({'id': community + '-submission', 'root': community + '-submission', 'reply_to': None,
                     'user': 'good', 'text': 'word ' * 250, 'timestamp': 1496275200,
                     'meta': {'subreddit': community}})
        archive = source / (community + '.zip')
        with zipfile.ZipFile(archive, 'w') as handle:
            handle.writestr('utterances.jsonl', b''.join(census.canonical(row) for row in rows))
        plan['sources'].append({'community': community, 'archive': archive.name,
                                'sha256': census.sha(archive), 'bytes': archive.stat().st_size})
    exclusion = {'complete_for_known_pilot_sources': True,
                 'accounts': [{'account_key': 'protected', 'reasons': ['protected_reserve']}],
                 'reason_counts': {'protected_reserve': 1}, 'prior_capacity_only_accounts': []}
    (private / 'exclusions-mandatory.json').write_text(json.dumps(exclusion))
    plan_path = tmp_path / 'plan.json'
    plan_path.write_text(json.dumps(plan))
    monkeypatch.setenv('AHAS_NETWORK_ISOLATION', 'linux_seccomp_socket_denial')
    monkeypatch.setattr(census.resource, 'setrlimit', lambda *args: None)
    monkeypatch.setattr(sys, 'argv', ['census.py', '--plan', str(plan_path), '--source-root', str(source),
                                     '--private-root', str(private), '--out', str(out)])
    census.main()
    stdout = capsys.readouterr().out
    prefix = tmp_path / 'synthetic-command'
    Path(str(prefix) + '.stdout.log').write_text(stdout)
    Path(str(prefix) + '.stderr.log').write_text('')
    receipt_path = Path(str(prefix) + '.receipt.json')
    receipt_path.write_text(json.dumps({'exit_code': 0, 'synthetic_fixture': True,
                                      'outputs': {suffix: check_census.fingerprint(str(prefix) + '.' + suffix)
                                                  for suffix in ('stdout.log', 'stderr.log')}}))
    return plan_path, out, private, receipt_path, source


def test_synthetic_full_census_uses_frozen_preprocessing_and_excludes_protected_accounts(synthetic_census):
    plan, out, private, receipt, source = synthetic_census
    rows = list(check_census.jsonlines(private / out.name / 'record-eligibility.jsonl'))
    assert {row['account_key'] for row in rows} == {'good', 'early_only', 'below_guard'}
    below = [row for row in rows if row['account_key'] == 'below_guard']
    assert len(below) == 32
    assert all(row['retained_words'] == 19 and row['reason'] == 'below_frozen_record_word_guard' for row in below)
    capacity = check_census.read(out / 'capacity.json')
    assert capacity['all_history_necessary_capacity']['X / Y']['accounts'] == 2
    assert capacity['period_capacity_table'][0]['four_cell_accounts'] == 1
    report = check_census.reconcile(plan, out, private, receipt, source)
    assert report['status'] == 'pass', report['failed_checks']


def test_independent_checker_rejects_invented_capacity(synthetic_census):
    plan, out, private, receipt, source = synthetic_census
    capacity = check_census.read(out / 'capacity.json')
    capacity['period_capacity_table'][0]['four_cell_accounts'] = 99
    (out / 'capacity.json').write_text(json.dumps(capacity))
    report = check_census.reconcile(plan, out, private, receipt, source)
    assert report['status'] == 'fail'
    assert 'Entire period capacity table independently recomputed' in report['failed_checks']


def test_independent_checker_rejects_private_record_duplication_even_if_digest_updated(synthetic_census):
    plan, out, private, receipt, source = synthetic_census
    record_path = private / out.name / 'record-eligibility.jsonl'
    with record_path.open('ab') as handle:
        handle.write(record_path.read_bytes().splitlines(keepends=True)[0])
    manifest = check_census.read(out / 'private-artifact-hashes.json')
    manifest['record-eligibility.jsonl'] = check_census.fingerprint(record_path)
    (out / 'private-artifact-hashes.json').write_text(json.dumps(manifest))
    report = check_census.reconcile(plan, out, private, receipt, source)
    assert report['status'] == 'fail'
    assert 'Every candidate original record ID appears at most once' in report['failed_checks']
