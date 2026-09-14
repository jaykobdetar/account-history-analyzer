"""Synthetic-only independent-check fixtures; never inspect real corpus text."""
from copy import deepcopy
from fractions import Fraction
import itertools
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import check_prepared_study as check
import finalize_cohort as producer
import export_registered_batches as exporter
from test_finalize_cohort import fixture
from test_export_registered_batches import registered


@pytest.fixture(scope='module')
def inputs():
    pool, audit, strata = fixture()
    result = producer.finalize(pool, audit, strata)
    exclusions = {'complete_for_known_pilot_sources': True,
                  'accounts': [{'account_key': f'old-protected-{i}'} for i in range(57)]}
    return pool, audit, strata, exclusions, result


def verify(values):
    return check.check_cohort(*values)


def test_whole_sixty_account_fixture_passes_independent_reconstruction(inputs):
    report = verify(inputs)
    assert report['accounts'] == 60 and report['blocks'] == 30
    assert report['selected_records'] == 1920 and report['exact_matchings_verified'] == 3
    assert report['style_scores_computed'] == report['preprocessor_calls'] == 0
    assert 'private-source' not in json.dumps(report)


@pytest.mark.parametrize('change,expected', [
    ('prose', 'selected_whole_record_prefix_or_fidelity_mismatch'),
    ('wrong_prefix', 'selected_whole_record_prefix_or_fidelity_mismatch'),
    ('protected', 'protected_or_changed_account'),
    ('audit_partition', 'audit_partition_mismatch'),
    ('pair_cost', 'nonminimal_or_changed_matching'),
    ('cell_stat', 'full_cell_statistics_mismatch'),
    ('group', 'dependency_group_mismatch'),
    ('contrast', 'block_design_mismatch'),
])
def test_material_corruptions_are_rejected(inputs, change, expected):
    pool, audit, strata, excluded, result = deepcopy(inputs)
    first = result['blocks'][0]
    if change == 'prose':
        first['cells']['A/X/early'][0] = deepcopy(first['cells']['A/X/early'][0])
        first['cells']['A/X/early'][0]['record']['text'] += ' altered'
    elif change == 'wrong_prefix':
        first['cells']['A/X/early'].reverse()
    elif change == 'protected':
        excluded['accounts'][0]['account_key'] = pool[0]['account_key']
    elif change == 'audit_partition':
        audit['purge_record_ids'] = [pool[0]['record']['id']]
    elif change == 'pair_cost':
        result['matching'][first['stratum_id']]['cost']['numerator'] += 1
    elif change == 'cell_stat':
        result['summary']['final_cell_statistics'][0]['cell_statistics']['A/X/early']['retained_words'] += 1
    elif change == 'group':
        result['groups']['unit_by_block'][first['block_id']] = 'resampling-unit-invented'
    elif change == 'contrast':
        first['comparisons'][0]['right_cell_id'] = 'B/Y/late'
    with pytest.raises(check.CheckFailure, match=expected):
        verify((pool, audit, strata, excluded, result))


def test_exact_rational_matching_agrees_with_exhaustive_six_account_search(inputs):
    pool, _, strata, _, _ = inputs
    accounts = sorted({e['account_key'] for e in pool if e['stratum_id'] == strata[0]['id']})[:6]
    cells = {a: {f'{c}/{p}': [] for c in 'XY' for p in ('early','late')} for a in accounts}
    for e in deepcopy(pool):
        if e['account_key'] in cells:
            c = 'X' if e['community'] == strata[0]['communities'][0] else 'Y'
            e['retained_words'] += accounts.index(e['account_key']) * 3
            cells[e['account_key']][c+'/'+e['period']].append(e)
    bounds = strata[0]['scheme']
    answer = check.exact_matching(cells, bounds)
    names = sorted(accounts, key=check.identity)
    def enumerate_pairings(seq):
        if not seq:
            yield ()
        else:
            for partner in seq[1:]:
                rest = [a for a in seq[1:] if a != partner]
                for pairs in enumerate_pairings(rest):
                    yield ((seq[0],partner),)+pairs
    expected = min((sum((check.cost(cells[a],cells[b],bounds) for a,b in pairs),Fraction()), pairs)
                   for pairs in enumerate_pairings(names))
    assert check.frac(answer['cost']) == expected[0]
    assert [p['accounts'] for p in answer['pairs']] == [list(p) for p in expected[1]]


def test_midpoint_prefix_halfopen_ties_both_guards_and_odd_median():
    rows = [{'record': {'id': str(i), 'created_utc': f'2017-07-{i:02d}T00:00:00Z'},
             'retained_words': 225} for i in range(1,13)]
    chosen = check.select_prefix(rows, ['2017-01-01','2018-01-01'])
    assert len(chosen) == 9 and sum(r['retained_words'] for r in chosen) == 2025
    stats = check.statistics(chosen)
    assert stats['word_overshoot'] == 25 and stats['records'] == 9
    assert stats['nearest_rank_word_quantiles'] == dict.fromkeys(('q25','q50','q75','q90'),225)
    rows[0]['record']['created_utc'] = '2018-01-01T00:00:00Z'
    with pytest.raises(check.CheckFailure, match='record_outside_period'):
        check.select_prefix(rows, ['2017-01-01','2018-01-01'])
    rows[0]['record']['created_utc'] = '2017-01-01T00:00:00Z'
    rows[0]['retained_words'] = 19
    with pytest.raises(check.CheckFailure, match='record_word_guard'):
        check.select_prefix(rows, ['2017-01-01','2018-01-01'])


def test_omission_nested_hash_and_middle_floor_without_refill(inputs):
    rows = inputs[4]['blocks'][0]['cells']['A/X/early']
    for n in (1,2,3,5,7,8):
        part = rows[:n]
        ids = lambda values: {e['record']['id'] for e in values}
        assert ids(check.omission(part,'hash50')) <= ids(check.omission(part,'hash75')) <= ids(part)
        assert check.omission(part,'middle50') == part[:n//4]+part[3*n//4:]
    assert check.statistics([])['median_timestamp'] is None
    assert check.statistics(rows[:4])['ordinary_volume_guards_met'] is False


def test_transitive_cross_stratum_thread_and_content_components(inputs):
    cohort = deepcopy(inputs[4]); audit = deepcopy(inputs[1])
    a,b,c = cohort['blocks'][0],cohort['blocks'][10],cohort['blocks'][20]
    ea,eb,ec = [x['cells']['A/X/early'][0] for x in (a,b,c)]
    selected_ids = {ea['record']['id'],eb['record']['id']}
    audit['engine_audit']['components'] = [comp for comp in audit['engine_audit']['components']
                                           if not selected_ids.intersection(comp['record_ids'])]
    audit['engine_audit']['components'].append({'cluster_id':'linked-synthetic','record_ids':sorted(selected_ids)})
    eb['record']['thread_id'] = ec['record']['thread_id'] = 'shared-synthetic-thread'
    groups = check.independent_groups(cohort['blocks'],audit)
    assert len({groups['unit_by_block'][x['block_id']] for x in (a,b,c)}) == 1
    assert len(groups['units']) == 28


@pytest.fixture(scope='module')
def exports(tmp_path_factory, inputs):
    folder = tmp_path_factory.mktemp('prepared-independent')
    root = folder/'batches'
    cohort = inputs[4]
    exporter.export_all_batches(root, cohort, registration=registered(folder,cohort))
    return root


def test_all360_exports_and5760_contrasts_are_verified(exports,inputs):
    result = check.check_exports(exports,inputs[4])
    assert result['prepared_batches_verified'] == 360 and result['comparisons_verified'] == 5760
    assert result['omission_unit_statistics_verified'] == 960


@pytest.mark.parametrize('change,reason', [('source','export_original_record_bytes_mismatch'),
                                        ('selector','hidden_selector_or_text_field'),
                                        ('group','export_observed_group_mismatch'),
                                        ('pair','export_contrast_identity_mismatch')])
def test_export_mutations_do_not_pass_even_with_updated_hash(exports,inputs,change,reason):
    index_path = exports/'batch-index.json'; index_bytes = index_path.read_bytes()
    index = json.loads(index_bytes); first = index[0]
    data_path = exports/first['dataset']; data_bytes = data_path.read_bytes(); data = json.loads(data_bytes)
    source_path = data_path.parent/data['texts'][0]['input']; source_bytes = source_path.read_bytes()
    try:
        if change == 'source':
            source_path.write_bytes(source_bytes.replace(b'synthetic prose', b'altered prose',1))
        elif change == 'selector':
            data['texts'][0]['selector'] = {'limit':1}
        elif change == 'group':
            data['texts'][0]['groups']['thread'] = ['invented-group']
        elif change == 'pair':
            data['pairs'][0]['label'] = 'different_author'
        data_path.write_bytes(check.canonical(data))
        first['dataset_sha256'] = first['input_hashes'][first['dataset']] = check.sha_file(data_path)
        index_path.write_bytes(check.canonical(index))
        with pytest.raises(check.CheckFailure,match=reason):
            check.check_exports(exports,inputs[4])
    finally:
        index_path.write_bytes(index_bytes); data_path.write_bytes(data_bytes); source_path.write_bytes(source_bytes)


def test_checker_imports_no_shared_implementation_algorithms():
    source = Path(check.__file__).read_text()
    for forbidden in ('import prepare_units','import finalize_cohort','from study_math','import account_history_analyzer','import cohort_selection'):
        assert forbidden not in source
