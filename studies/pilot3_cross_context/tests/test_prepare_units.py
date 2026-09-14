"""Synthetic adapter tests. No real candidate prose or distance scores are read."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import itertools
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prepare_units as units
from account_history_analyzer.io import load_snapshot
from account_history_analyzer.schemas import validate
from study_math import comparison_design, omit_record_ids


PERIODS = {'early': ['2017-01-01', '2018-01-01'], 'late': ['2018-01-01', '2019-01-01']}


def entry(identifier, words=250, *, account='source-A', community='community-X', year=2017, day=1):
    record = {'schema_version': '1.0.0', 'id': identifier, 'account_id': account,
              'kind': 'comment', 'status': 'present', 'text': 'word ' * words,
              'created_utc': f'{year}-07-{day:02d}T00:00:00Z', 'subreddit': community,
              'language': None, 'edit_state': 'unknown',
              'thread_id': 'thread-' + identifier, 'parent_id': 'parent-' + identifier}
    # Preserve intentionally noncanonical whitespace rather than reserializing.
    raw = (json.dumps(record, ensure_ascii=False, separators=(', ', ': ')) + '\n').encode()
    return {'record': record, 'retained_words': words, 'record_jsonl': raw}


def full_block():
    return {key: [entry(key + '/' + str(index), account='source-' + key[0],
                       community='community-' + key[2], year=2017 if key.endswith('early') else 2018,
                       day=index + 1) for index in range(8)] for key in units.BLOCK_CELL_KEYS}


def test_whole_record_midpoint_prefix_preserves_original_entry_objects_and_bytes():
    rows = [entry(str(i), day=i + 1) for i in range(10)]
    before = deepcopy(rows)
    selected = units.select_cell(list(reversed(rows)), PERIODS['early'])
    assert len(selected) == 8
    assert [row['record']['id'] for row in selected] == [str(i) for i in range(8)]
    assert rows == before
    assert all(any(row is original for original in rows) for row in selected)


def test_midpoint_equal_distance_uses_timestamp_then_original_id():
    bounds = ['2017-07-01T00:00:00Z', '2017-07-03T00:00:00Z']
    rows = [entry(f'{i:02d}', day=2) for i in range(9)]
    chosen = units.select_cell(list(reversed(rows)), bounds)
    assert [row['record']['id'] for row in chosen] == [f'{i:02d}' for i in range(8)]


def test_select_cell_requires_both_thresholds_and_keeps_overshoot():
    rows = [entry('dominant', words=2000)] + [entry(str(i), words=20, day=i + 2) for i in range(7)]
    selected = units.select_cell(rows, PERIODS['early'])
    assert len(selected) == 8
    assert units.cell_statistics(selected)['word_overshoot'] == 140
    with pytest.raises(ValueError, match='cannot supply'):
        units.select_cell(rows[:-1], PERIODS['early'])
    with pytest.raises(ValueError, match='cannot supply'):
        units.select_cell([entry(str(i), words=249) for i in range(8)], PERIODS['early'])


@pytest.mark.parametrize('change', ['below_guard', 'missing_time', 'outside_period', 'duplicate', 'mixed_account', 'wrong_language'])
def test_ineligible_or_misgrouped_input_is_rejected_without_silent_filtering(change):
    rows = [entry(str(i)) for i in range(8)]
    if change == 'below_guard':
        rows[0]['retained_words'] = 19
    elif change == 'missing_time':
        rows[0]['record']['created_utc'] = None
    elif change == 'outside_period':
        rows[0]['record']['created_utc'] = '2018-01-01T00:00:00Z'
    elif change == 'duplicate':
        rows[1]['record']['id'] = rows[0]['record']['id']
    elif change == 'mixed_account':
        rows[0]['record']['account_id'] = 'another-account'
    else:
        rows[0]['record']['language'] = 'es'
    with pytest.raises(ValueError):
        units.select_cell(rows, PERIODS['early'])


def test_statistics_use_nearest_rank_lengths_and_exact_median_time():
    rows = [entry(str(i), words=20 * (i + 1), day=i + 1) for i in range(4)]
    stats = units.cell_statistics(rows)
    assert stats['retained_words'] == 200
    assert stats['nearest_rank_word_quantiles'] == {'q25': 20, 'q50': 40, 'q75': 60, 'q90': 80}
    assert stats['median_utc'] == '2017-07-02T12:00:00Z'
    assert stats['longest_record_share'] == {'numerator': 2, 'denominator': 5}
    assert stats['word_shortfall'] == 1800 and stats['record_shortfall'] == 4
    empty = units.cell_statistics([])
    assert empty['records'] == empty['retained_words'] == 0
    assert empty['median_timestamp'] is None and not empty['ordinary_volume_guards_met']


def test_four_cells_retain_date_gaps_and_reject_overlap():
    block = full_block()
    cells = {key: block['A/' + key] for key in units.CELL_KEYS}
    stats = units.four_cell_statistics(cells, PERIODS)
    assert stats['early_late_gaps']['X']['median_gap_seconds'] == {'numerator': 365 * 86400, 'denominator': 1}
    invalid = {'early': ['2017-01-01', '2018-06-01'], 'late': PERIODS['late']}
    with pytest.raises(ValueError, match='overlap'):
        units.four_cell_statistics(cells, invalid)


def matching_stats(offset, words=2000, records=8):
    return {key: {'median_timestamp': units.rational(1500000000 + offset),
                  'retained_words': words, 'records': records} for key in units.CELL_KEYS}


def all_matchings(accounts):
    if not accounts:
        yield []
        return
    first = accounts[0]
    for index in range(1, len(accounts)):
        second = accounts[index]
        remainder = accounts[1:index] + accounts[index + 1:]
        for rest in all_matchings(remainder):
            yield [(first, second)] + rest


def test_pair_cost_matches_hand_checked_exact_arithmetic():
    left, right = matching_stats(0), matching_stats(86400, words=2250, records=9)
    # Four cells, each with 1/365 time imbalance + 1/8 word + 1/8 record imbalance.
    assert units.pair_cost(left, right, PERIODS) == 4 * (Fraction(1, 365) + Fraction(1, 8) + Fraction(1, 8))


def test_subset_dp_matches_independent_exhaustive_six_account_oracle():
    accounts = {name: matching_stats(offset, words=2000 + i * 100, records=8 + i)
                for i, (name, offset) in enumerate(zip('ABCDEF', (0, 11, 19, 101, 130, 900)))}
    expected = min((sum((units.pair_cost(accounts[a], accounts[b], PERIODS) for a, b in pairs), Fraction()),
                    tuple(sorted(tuple(sorted((units.account_hash(a), units.account_hash(b)))) for a, b in pairs)))
                   for pairs in all_matchings(list(accounts)))
    result = units.minimum_cost_perfect_matching(accounts, PERIODS, expected_accounts=6)
    actual = (units._fraction(result['cost']), tuple(tuple(pair['account_hashes']) for pair in result['pairs']))
    assert actual == expected
    assert units.minimum_cost_perfect_matching(dict(reversed(list(accounts.items()))), PERIODS, expected_accounts=6) == result


def test_twenty_account_equal_cost_matching_uses_hash_ties_without_reduced_design():
    accounts = {f'account-{i}': matching_stats(0) for i in range(20)}
    result = units.minimum_cost_perfect_matching(accounts, PERIODS)
    hashes = sorted(units.account_hash(account) for account in accounts)
    assert [pair['account_hashes'] for pair in result['pairs']] == [hashes[i:i + 2] for i in range(0, 20, 2)]
    assert result['cost'] == {'numerator': 0, 'denominator': 1}
    assert len({account for pair in result['pairs'] for account in pair['accounts']}) == 20
    with pytest.raises(ValueError, match='target'):
        units.minimum_cost_perfect_matching(dict(list(accounts.items())[:-2]), PERIODS)
    broken = deepcopy(accounts)
    broken['account-0']['X/early']['median_timestamp'] = None
    with pytest.raises(ValueError, match='Missing median'):
        units.minimum_cost_perfect_matching(broken, PERIODS)


def test_omissions_delegate_fixed_identity_rule_preserve_bytes_and_never_refill():
    rows = [entry(str(i), day=i + 1) for i in range(12)]
    subsets = {}
    for arm in units.ARMS:
        subset = units.omit_cell(list(reversed(rows)), arm)
        assert [row['record']['id'] for row in subset] == omit_record_ids([str(i) for i in range(12)], arm, units.OMISSION_SALT)
        assert all(any(row is original for original in rows) for row in subset)
        subsets[arm] = {row['record']['id'] for row in subset}
    assert subsets['hash50'] <= subsets['hash75'] <= subsets['full']
    assert subsets['middle50'] == {'0', '1', '2', '9', '10', '11'}


def test_eight_units_and_sixteen_fixed_contrasts_remain_in_omission_denominators():
    full = full_block()
    result = units.prepare_block(full, 'synthetic-block', PERIODS, 'middle50')
    assert len(result['units']) == 8 and len(result['comparisons']) == 16
    assert result['comparisons'] == comparison_design('synthetic-block')
    assert all(len(rows) == 4 for rows in result['units'].values())
    assert all(not stats['ordinary_volume_guards_met'] for stats in result['statistics'].values())
    assert sum(row['label'] == 'same_author' for row in result['comparisons']) == 8


def test_source_account_case_variants_cannot_form_an_independent_block():
    full = full_block()
    for key, entries in full.items():
        if key.startswith('B/'):
            for row in entries:
                row['record']['account_id'] = 'SOURCE-A'
    with pytest.raises(ValueError, match='Case variants'):
        units.prepare_block(full, 'synthetic-block', PERIODS)


def export_metadata(block):
    manifests, groups = {}, {}
    for key in units.BLOCK_CELL_KEYS:
        manifests[key] = {'schema_version': '1.0.0', 'snapshot_id': 'synthetic/' + key,
                          'account_id': block['source_accounts'][key[0]], 'source_category': 'synthetic',
                          'text_format': 'markdown', 'default_language': 'en',
                          'source_notes': 'Constructed fixture; English assumption, no empirical claim.',
                          'coverage': {'status': 'sampled', 'notes': 'Subset only; omissions are not refilled.'}}
        groups[key] = {'author': [block['source_accounts'][key[0]]],
                       'related_sample': [block['block_id']]}
    registration = {'registered_before_evaluation': True,
                    'preregistration_provenance': 'Fixed synthetic test fixture only; not an empirical registration.',
                    'protocol_sha256': 'a' * 64}
    return dict(manifests=manifests, groups=groups, provenance='Constructed adapter fixture; not empirical study data.', registration=registration)


@pytest.mark.parametrize('method', units.METHODS)
@pytest.mark.parametrize('arm', units.ARMS)
def test_export_is_schema_conforming_subset_only_and_never_scores(tmp_path, method, arm):
    block = units.prepare_block(full_block(), 'synthetic-block', PERIODS, arm)
    path = tmp_path / 'batch'
    report = units.export_paired_batch(path, block, method, **export_metadata(block))
    dataset = json.loads((path / 'dataset.json').read_bytes())
    validate(dataset, 'evaluation_paired_text')
    assert report['status'] == 'prepared_not_scored' and report['scores_computed'] is False
    assert 'source-account' in dataset['label_definition']
    assert dataset['protocol']['frozen_threshold'] is None
    assert all('selector' not in text for text in dataset['texts'])
    assert len(dataset['texts']) == 8 and len(dataset['pairs']) == 16
    for text in dataset['texts']:
        rows = block['units'][text['text_id']]
        assert (path / text['input']).read_bytes() == b''.join(row['record_jsonl'] for row in rows)
        snapshot = load_snapshot(path / text['input'], path / text['manifest'], units.frozen_config())
        assert {row['id'] for row in snapshot.records} == {row['record']['id'] for row in rows}
    assert report['invocation_input_bytes'] == sum((path / name).stat().st_size for name in report['input_hashes'])


def test_export_refuses_unregistered_inputs_or_changed_original_bytes_before_writing(tmp_path):
    block = units.prepare_block(full_block(), 'synthetic-block', PERIODS)
    kwargs = export_metadata(block)
    kwargs['registration']['registered_before_evaluation'] = False
    with pytest.raises(ValueError, match='registration'):
        units.export_paired_batch(tmp_path / 'unregistered', block, units.METHODS[0], **kwargs)
    kwargs = export_metadata(block)
    block['units']['A/X/early'][0]['record_jsonl'] = b'{}\n'
    with pytest.raises(ValueError, match='disagree'):
        units.export_paired_batch(tmp_path / 'changed', block, units.METHODS[0], **kwargs)
    assert not (tmp_path / 'changed').exists()


def test_export_checks_aggregate_unchanged_record_ceiling_before_writing(tmp_path):
    block = units.prepare_block(full_block(), 'synthetic-block', PERIODS)
    # Construct original whole synthetic eligible records, not a real cohort.
    block['units'] = {key: [entry(key + '-' + str(i), words=20, account=block['source_accounts'][key[0]],
                                  community='community-' + key[2], year=2017 if key.endswith('early') else 2018)
                           for i in range(1251)] for key in units.BLOCK_CELL_KEYS}
    with pytest.raises(ValueError, match='10000-record'):
        units.export_paired_batch(tmp_path / 'oversize', block, units.METHODS[0], **export_metadata(block))
    assert not (tmp_path / 'oversize').exists()


def test_original_codepoint_ceiling_is_unchanged():
    row = entry('oversize')
    row['record']['text'] = 'x' * 200001
    with pytest.raises(ValueError, match='200000-codepoint'):
        units.cell_statistics([row])
