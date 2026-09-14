"""Preparatory adapters, NOT an executed or registered empirical study.

Only synthetic inputs have exercised this module. No acquisition, cohort choice,
contamination audit, registration, AHAS scoring, or evaluator invocation occurs
here. Callers must complete the separate feasibility and registration gates.

An eligibility entry wraps an unchanged conforming AHAS ``record`` mapping and
its frozen-preprocessor ``retained_words``. Optional ``record_jsonl`` bytes are
preserved exactly during export and must decode to that same record mapping.
Entries and their records are never edited. Every export contains subsets only.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
import json
import math
from pathlib import Path
import re

from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import canonical_bytes, digest, load_snapshot, parse_json
from account_history_analyzer.schemas import validate
from study_math import comparison_design, omit_record_ids

VERSION = 'pilot3-preparation-draft-v1'
CONFIG_SHA256 = '8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925'
OMISSION_SALT = 'ahas-pilot3-omission-v1'
ACCOUNT_SALT = 'ahas-pilot3-account-rank-v1:'
ARMS = ('full', 'hash75', 'hash50', 'middle50')
METHODS = (
    {'method_id': 'cosine_distance_v1', 'view': 'retained_prose', 'n': 4},
    {'method_id': 'cosine_distance_v1', 'view': 'function_mask_v1', 'n': 4},
    {'method_id': 'function_word_js_v1', 'view': 'lexical_tokens', 'n': None},
)
CELL_KEYS = ('X/early', 'X/late', 'Y/early', 'Y/late')
BLOCK_CELL_KEYS = tuple(account + '/' + cell for account in ('A', 'B') for cell in CELL_KEYS)
LABEL_DEFINITION = (
    'same_author and different_author are required evaluator enums meaning '
    'same-source-account and different-source-account identity proxies. They do '
    'not establish individual human authorship, bot/human identity, account '
    'takeover, or whether several accounts belong to one person.'
)
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def frozen_config():
    config = AnalysisConfig.from_toml()
    if digest(config.analytical()) != CONFIG_SHA256:
        raise ValueError('Preparatory adapters require the frozen default configuration')
    return config


def _seconds(value, *, period_boundary=False):
    if not isinstance(value, str):
        raise ValueError('Original UTC timestamps are required')
    if period_boundary and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        value += 'T00:00:00Z'
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value):
        raise ValueError('Integer-second UTC timestamp required; no imputed times')
    moment = datetime.fromisoformat(value.replace('Z', '+00:00'))
    delta = moment - EPOCH
    return delta.days * 86400 + delta.seconds


def _period(bounds):
    if len(bounds) != 2:
        raise ValueError('Exactly two period bounds are required')
    start, end = (_seconds(bound, period_boundary=True) for bound in bounds)
    if start >= end:
        raise ValueError('Calendar period must have positive duration')
    return start, end


def _fraction(value):
    if isinstance(value, Fraction):
        return value
    if type(value) is int:
        return Fraction(value)
    if isinstance(value, Mapping) and set(value) == {'numerator', 'denominator'}:
        if type(value['numerator']) is int and type(value['denominator']) is int and value['denominator'] > 0:
            return Fraction(value['numerator'], value['denominator'])
    raise ValueError('Exact integer or rational value required')


def rational(value):
    value = Fraction(value)
    return {'numerator': value.numerator, 'denominator': value.denominator}


def _utc(value):
    value = Fraction(value)
    micros = value * 1_000_000
    if micros.denominator != 1:
        raise ValueError('Timestamp fraction cannot be represented without rounding')
    return (EPOCH + timedelta(microseconds=micros.numerator)).isoformat().replace('+00:00', 'Z')


def _entry(entry):
    record = entry['record']
    words = entry['retained_words']
    if type(words) is not int or words < 20:
        raise ValueError('Every supplied eligible record must retain at least 20 words')
    if record.get('kind') != 'comment' or record.get('status') != 'present' or not isinstance(record.get('text'), str):
        raise ValueError('Only original present comments are eligible')
    if record.get('language') not in (None, 'en'):
        raise ValueError('Unsupported per-record language cannot become English by assumption')
    if not isinstance(record.get('id'), str) or not record['id']:
        raise ValueError('Original record ID required')
    if not isinstance(record.get('account_id'), str) or not record['account_id']:
        raise ValueError('Original source-account identity required')
    if not isinstance(record.get('subreddit'), str) or not record['subreddit']:
        raise ValueError('Original community required')
    if len(record['text']) > 200000:
        raise ValueError('Original text exceeds the unchanged 200000-codepoint limit')
    return record['id'], _seconds(record.get('created_utc')), words


def _chronology(entries):
    rows = list(entries)
    keys = [_entry(entry) for entry in rows]
    if len({key[0] for key in keys}) != len(keys):
        raise ValueError('Repeated original record IDs are forbidden')
    return sorted(rows, key=lambda entry: (_seconds(entry['record']['created_utc']), entry['record']['id']))


def select_cell(entries, period_bounds):
    """Select a whole-record prefix by midpoint proximity; export chronology.

    Both 2000 retained words and eight records must be available. All inputs must
    already be eligible, from one source account/community and inside the fixed
    half-open period. Unexpected inputs fail rather than silently disappearing.
    """
    start, end = _period(period_bounds)
    rows = _chronology(entries)
    identities = {(entry['record']['account_id'], entry['record']['subreddit']) for entry in rows}
    if len(identities) != 1:
        raise ValueError('One nonempty source-account/community cell is required')
    for entry in rows:
        if not start <= _seconds(entry['record']['created_utc']) < end:
            raise ValueError('Record falls outside the frozen half-open period')
    order = sorted(rows, key=lambda entry: (
        abs(2 * _seconds(entry['record']['created_utc']) - start - end),
        _seconds(entry['record']['created_utc']), entry['record']['id']))
    chosen, words = [], 0
    for entry in order:
        chosen.append(entry)
        words += entry['retained_words']
        if len(chosen) >= 8 and words >= 2000:
            return _chronology(chosen)
    raise ValueError('Cell cannot supply 2000 eligible words and eight whole eligible records')


def cell_statistics(entries):
    """Exact descriptive metadata, including unavailable empty omission units."""
    rows = _chronology(entries)
    lengths = sorted(entry['retained_words'] for entry in rows)
    moments = sorted(_seconds(entry['record']['created_utc']) for entry in rows)
    count, words = len(rows), sum(lengths)
    median = None if not count else Fraction(moments[(count - 1)//2] + moments[count//2], 2)
    quantiles = {label: (None if not count else lengths[(count * numerator + denominator - 1)//denominator - 1])
                 for label, numerator, denominator in (('q25', 1, 4), ('q50', 1, 2), ('q75', 3, 4), ('q90', 9, 10))}
    return {'records': count, 'retained_words': words, 'word_target': 2000,
            'word_overshoot': max(0, words - 2000), 'word_shortfall': max(0, 2000 - words),
            'record_shortfall': max(0, 8 - count),
            'longest_record_words': max(lengths, default=0),
            'longest_record_share': None if not words else rational(Fraction(max(lengths), words)),
            'nearest_rank_word_quantiles': quantiles,
            'first_utc': None if not moments else _utc(moments[0]),
            'last_utc': None if not moments else _utc(moments[-1]),
            'median_utc': None if median is None else _utc(median),
            'median_timestamp': None if median is None else rational(median),
            'nonempty': bool(count),
            'ordinary_volume_guards_met': count >= 8 and words >= 1000,
            'experimental_full_target_met': count >= 8 and words >= 2000}


def four_cell_statistics(cells, period_bounds):
    if set(cells) != set(CELL_KEYS):
        raise ValueError('Exactly X/Y by early/late cells are required')
    early, late = _period(period_bounds['early']), _period(period_bounds['late'])
    if early[1] > late[0]:
        raise ValueError('Early and late periods must not overlap')
    ids, accounts, communities = set(), set(), {}
    result = {}
    for key in CELL_KEYS:
        community, part = key.split('/')
        start, end = _period(period_bounds[part])
        rows = _chronology(cells[key])
        for entry in rows:
            record_id, timestamp, _ = _entry(entry)
            if record_id in ids or not start <= timestamp < end:
                raise ValueError('Cells must contain disjoint original records inside their periods')
            ids.add(record_id)
            accounts.add(entry['record']['account_id'])
            communities.setdefault(community, set()).add(entry['record']['subreddit'])
        result[key] = cell_statistics(rows)
    if len(accounts) != 1 or set(communities) != {'X', 'Y'} or any(len(values) != 1 for values in communities.values()) or communities['X'] == communities['Y']:
        raise ValueError('Four cells require one account and two distinct original communities')
    gaps = {}
    for community in ('X', 'Y'):
        first, second = result[community + '/early'], result[community + '/late']
        gaps[community] = {
            'median_gap_seconds': None if first['median_timestamp'] is None or second['median_timestamp'] is None else rational(_fraction(second['median_timestamp']) - _fraction(first['median_timestamp'])),
            'nearest_writing_gap_seconds': None if first['last_utc'] is None or second['first_utc'] is None else _seconds(second['first_utc']) - _seconds(first['last_utc'])}
    return {'cells': result, 'early_late_gaps': gaps}


def account_hash(account):
    if not isinstance(account, str) or not account:
        raise ValueError('Source account identity is required for deterministic ties')
    return sha256((ACCOUNT_SALT + account.casefold()).encode('utf-8')).hexdigest()


def pair_cost(left, right, period_bounds):
    if set(left) != set(CELL_KEYS) or set(right) != set(CELL_KEYS):
        raise ValueError('Pair cost requires all four prepared cell statistics')
    value = Fraction()
    for key in CELL_KEYS:
        start, end = _period(period_bounds[key.split('/')[1]])
        a, b = left[key], right[key]
        if a['median_timestamp'] is None or b['median_timestamp'] is None:
            raise ValueError('Missing median timestamp blocks account matching')
        if any(type(stats[field]) is not int or stats[field] < 0 for stats in (a, b) for field in ('retained_words', 'records')):
            raise ValueError('Matching volumes must be nonnegative integers')
        value += abs(_fraction(a['median_timestamp']) - _fraction(b['median_timestamp'])) / (end - start)
        value += Fraction(abs(a['retained_words'] - b['retained_words']), 2000)
        value += Fraction(abs(a['records'] - b['records']), 8)
    return value


def minimum_cost_perfect_matching(account_cells, period_bounds, *, expected_accounts=20):
    """Exact subset DP; expected_accounts differs only in explicit synthetic tests.

    Pair ties are sorted source-identity hash pairs. No style score is an input.
    The default requires the full 20-account stratum; no silent reduced design.
    """
    if type(expected_accounts) is not int or expected_accounts < 2 or expected_accounts > 20 or expected_accounts % 2:
        raise ValueError('Expected stratum size must be even and between 2 and 20')
    if _period(period_bounds['early'])[1] > _period(period_bounds['late'])[0]:
        raise ValueError('Matching requires nonoverlapping early and late periods')
    if len(account_cells) != expected_accounts:
        raise ValueError('Prepared account count differs from the explicit stratum target')
    if len({account.casefold() for account in account_cells}) != len(account_cells):
        raise ValueError('Case variants of one account cannot become separate subjects')
    accounts = sorted(account_cells, key=lambda account: (account_hash(account), account))
    hashes = [account_hash(account) for account in accounts]
    costs = {(i, j): pair_cost(account_cells[accounts[i]], account_cells[accounts[j]], period_bounds)
             for i in range(len(accounts)) for j in range(i + 1, len(accounts))}
    denominator = math.lcm(*(value.denominator for value in costs.values()))
    integer_costs = {key: int(value * denominator) for key, value in costs.items()}

    @lru_cache(None)
    def solve(mask):
        if not mask:
            return 0, ()
        i = (mask & -mask).bit_length() - 1
        remainder = mask ^ (1 << i)
        best = None
        for j in range(i + 1, len(accounts)):
            if remainder & (1 << j):
                cost, pairs = solve(remainder ^ (1 << j))
                candidate = (cost + integer_costs[i, j], ((i, j),) + pairs)
                if best is None or candidate < best:
                    best = candidate
        return best

    total, pairs = solve((1 << len(accounts)) - 1)
    return {'status': 'preparatory_matching_only', 'account_count': len(accounts),
            'cost': rational(Fraction(total, denominator)), 'tie_rule': 'sorted_source_identity_hash_pairs',
            'pairs': [{'accounts': [accounts[i], accounts[j]], 'account_hashes': [hashes[i], hashes[j]],
                       'cost': rational(costs[i, j])} for i, j in pairs],
            'dp_states': solve.cache_info().currsize}


def omit_cell(entries, arm):
    if arm not in ARMS:
        raise ValueError('Only the four fixed omission arms are defined')
    rows = _chronology(entries)
    selected = set(omit_record_ids([entry['record']['id'] for entry in rows], arm, OMISSION_SALT))
    return [entry for entry in rows if entry['record']['id'] in selected]


def prepare_block(cells, block_id, period_bounds, arm='full'):
    if set(cells) != set(BLOCK_CELL_KEYS):
        raise ValueError('Exactly eight account/community/period cells are required')
    for account in ('A', 'B'):
        statistics = four_cell_statistics({key: cells[account + '/' + key] for key in CELL_KEYS}, period_bounds)
        if any(not row['experimental_full_target_met'] for row in statistics['cells'].values()):
            raise ValueError('Every prepared full cell must meet the unchanged experimental 2000-word/eight-record target before omissions')
    seen, account_roles, community_roles = set(), {'A': set(), 'B': set()}, {'X': set(), 'Y': set()}
    for key in BLOCK_CELL_KEYS:
        account, community, _ = key.split('/')
        for entry in _chronology(cells[key]):
            if entry['record']['id'] in seen:
                raise ValueError('One original record cannot belong to two prepared cells')
            seen.add(entry['record']['id'])
            account_roles[account].add(entry['record']['account_id'])
            community_roles[community].add(entry['record']['subreddit'])
    if any(len(values) != 1 for values in (*account_roles.values(), *community_roles.values())) or account_roles['A'] == account_roles['B'] or community_roles['X'] == community_roles['Y']:
        raise ValueError('Block roles must map to two distinct accounts and communities')
    if next(iter(account_roles['A'])).casefold() == next(iter(account_roles['B'])).casefold():
        raise ValueError('Case variants of one source account cannot form a two-account block')
    units = {key: omit_cell(cells[key], arm) for key in BLOCK_CELL_KEYS}
    return {'block_id': block_id, 'arm': arm, 'units': units,
            'source_accounts': {key: next(iter(value)) for key, value in account_roles.items()},
            'comparisons': comparison_design(block_id),
            'statistics': {key: cell_statistics(rows) for key, rows in units.items()}}


def _record_bytes(entry):
    record = entry['record']
    validate(record, 'record')
    raw = entry.get('record_jsonl')
    if raw is None:
        return canonical_bytes(record)
    if not isinstance(raw, bytes) or not raw.endswith(b'\n') or len(raw.splitlines()) != 1:
        raise ValueError('Preserved record JSONL must be exactly one complete byte line')
    if parse_json(raw) != record:
        raise ValueError('Preserved JSONL bytes disagree with unchanged supplied record mapping')
    return raw


def export_paired_batch(output_dir, block, method, *, manifests, groups, provenance, registration):
    """Export one explicit eight-unit/16-pair method/arm batch, without scoring.

    Registration must be supplied by a caller that completed Gate B. Synthetic
    callers use explicit fixture provenance; this helper invents no registration.
    Metadata inputs include templates for all eight snapshots and observed group
    dimensions. Missing grouping stays missing; this is not a contamination audit.
    """
    config = frozen_config()
    if method not in METHODS or block['arm'] not in ARMS:
        raise ValueError('Method and arm must be one of the three/four fixed choices')
    if set(block['units']) != set(BLOCK_CELL_KEYS) or len(block['comparisons']) != 16:
        raise ValueError('One batch requires exactly eight units and 16 contrasts')
    if set(manifests) != set(BLOCK_CELL_KEYS) or set(groups) != set(BLOCK_CELL_KEYS):
        raise ValueError('Explicit snapshot and observed-group metadata required for every unit')
    if registration.get('registered_before_evaluation') is not True or not registration.get('preregistration_provenance'):
        raise ValueError('Actual prior registration or explicit synthetic-fixture provenance required')
    if not re.fullmatch(r'[0-9a-f]{64}', registration.get('protocol_sha256', '')):
        raise ValueError('Caller must bind an explicit protocol artifact hash')
    dataset = {'schema_version': '1.0.0', 'format': 'paired_text',
               'dataset_id': block['block_id'] + '/' + block['arm'] + '/' + method['view'],
               'provenance': provenance, 'label_definition': LABEL_DEFINITION,
               'protocol': {'analysis_config_sha256': CONFIG_SHA256, 'registered_before_evaluation': True,
                            'preregistration_provenance': registration['preregistration_provenance'] + '; protocol_sha256=' + registration['protocol_sha256'],
                            'distance': dict(method), 'frozen_threshold': None}, 'texts': [], 'pairs': []}
    files, seen, unit_ids = {}, set(), {}
    for index, key in enumerate(BLOCK_CELL_KEYS):
        rows = _chronology(block['units'][key])
        manifest = manifests[key]
        validate(manifest, 'snapshot')
        if manifest['text_format'] != 'markdown' or manifest['default_language'] != 'en' or manifest['coverage']['status'] != 'sampled':
            raise ValueError('Subset manifests require markdown, explicit English assumption, and sampled coverage')
        if manifest['account_id'] != block['source_accounts'][key[0]]:
            raise ValueError('Snapshot account does not match the prepared block role')
        input_name, manifest_name = f'unit-{index:02d}.jsonl', f'unit-{index:02d}.snapshot.json'
        raw_parts = []
        for entry in rows:
            identifier, _, _ = _entry(entry)
            if identifier in seen:
                raise ValueError('Batch contains repeated original record IDs')
            if entry['record']['account_id'] != manifest['account_id']:
                raise ValueError('Original record account disagrees with subset manifest')
            seen.add(identifier)
            raw_parts.append(_record_bytes(entry))
        files[input_name] = b''.join(raw_parts)
        files[manifest_name] = canonical_bytes(manifest)
        unit_ids[key] = key
        dataset['texts'].append({'text_id': key, 'input': input_name, 'manifest': manifest_name, 'groups': dict(groups[key])})
    expected_comparisons = comparison_design(block['block_id'])
    if block['comparisons'] != expected_comparisons:
        raise ValueError('Caller changed the fixed 16-contrast design')
    for row in expected_comparisons:
        dataset['pairs'].append({'pair_id': row['pair_id'], 'left_text_id': unit_ids[row['left_cell_id']],
                                 'right_text_id': unit_ids[row['right_cell_id']], 'split': 'evaluation', 'label': row['label']})
    validate(dataset, 'evaluation_paired_text')
    files['dataset.json'] = canonical_bytes(dataset)
    total_bytes = sum(map(len, files.values()))
    if total_bytes > config['input']['max_input_bytes']:
        raise ValueError('Dataset plus all unique source files exceeds the unchanged 50 MiB invocation limit')
    if len(seen) > config['input']['max_unique_records']:
        raise ValueError('Batch exceeds the unchanged 10000-record invocation limit')
    output_dir = Path(output_dir)
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, raw in files.items():
        path = output_dir / name
        with path.open('xb') as handle:
            handle.write(raw)
        path.chmod(0o600)
    # Run only the existing input/schema loader: no features or distances.
    for text in dataset['texts']:
        load_snapshot(output_dir / text['input'], output_dir / text['manifest'], config)
    report = {'status': 'prepared_not_scored', 'adapter_version': VERSION,
              'method': dict(method), 'arm': block['arm'], 'units': 8, 'pairs': 16,
              'unique_records': len(seen), 'invocation_input_bytes': total_bytes,
              'configuration_sha256': CONFIG_SHA256, 'protocol_sha256': registration['protocol_sha256'],
              'contains_private_source_identities': True, 'scores_computed': False,
              'input_hashes': {name: {'sha256': sha256(raw).hexdigest(), 'bytes': len(raw)} for name, raw in files.items()}}
    (output_dir / 'preparation-receipt.json').write_bytes(canonical_bytes(report))
    (output_dir / 'preparation-receipt.json').chmod(0o600)
    return report
