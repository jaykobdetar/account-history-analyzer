"""Independent synthetic integration checks; no distance evaluator is called."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import export_registered_batches as exporter
import finalize_cohort as final
import run_scoring as runner
import normalize_evaluations as normalizer
from study_math import comparison_design
from test_finalize_cohort import fixture
from test_export_registered_batches import registered


@pytest.fixture(scope='module')
def prepared(tmp_path_factory):
    root = tmp_path_factory.mktemp('synthetic-execution-integration')
    cohort = final.finalize(*fixture())
    registration = registered(root, cohort)
    output = root/'prepared'
    result = exporter.export_all_batches(output, cohort, registration=registration)
    return output, result['batches']


def test_real_export_contract_validates_all360_and_exact_fixed120_replay(prepared):
    root, index = prepared
    strata = runner.validate_batches(root, index)
    assert len(strata) == 3
    assert len([row for row in index if row['stratum_id'] == strata[0]]) == 120
    assert len({row['batch_id'] for row in index}) == 360


def test_duplicate_output_identifier_must_fail_before_scoring(prepared):
    root, original = prepared
    index = deepcopy(original)
    index[1]['batch_id'] = index[0]['batch_id']
    with pytest.raises(ValueError):
        runner.validate_batches(root, index)


def test_unsafe_output_identifier_must_fail_before_scoring(prepared):
    root, original = prepared
    index = deepcopy(original)
    index[0]['batch_id'] = '../unregistered-output'
    with pytest.raises(ValueError):
        runner.validate_batches(root, index)


def evaluation(item, dataset_id):
    rows = []
    for expected in comparison_design(item['block_id']):
        rows.append({'pair_id': expected['pair_id'], 'label': expected['label'],
                     'left_text_id': expected['left_cell_id'], 'right_text_id': expected['right_cell_id'],
                     'split': 'evaluation', 'score': None, 'raw_distance': 0.25, 'status': 'abstained',
                     'reason_codes': ['insufficient_records'],
                     'samples': {side: {'record_count': 8, 'word_count': 2000,
                                       'eligible_record_count': 8, 'eligible_word_count': 2000,
                                       'usable_record_count': 8} for side in ('left', 'right')}})
    return {'dataset_id': dataset_id, 'distance': {k: item[k] for k in ('method_id', 'view', 'n')},
            'exit_code': 0, 'partitions': {'development': {'rows': []}, 'evaluation': {'rows': rows}}}


def test_results_from_another_arm_must_not_be_normalized_as_this_arm(prepared):
    _, index = prepared
    item = next(row for row in index if row['arm'] == 'hash50')
    result = evaluation(item, item['block_id'] + '/full/' + item['view'])
    with pytest.raises(ValueError):
        normalizer.extract_batch(item, result, 'stratum-01')


def test_extraction_preserves_all_rows_and_unique_unit_counts(prepared):
    _, index = prepared
    item = next(row for row in index if row['arm'] == 'hash50')
    result = evaluation(item, item['block_id'] + '/' + item['arm'] + '/' + item['view'])
    before = deepcopy(result)
    rows = normalizer.extract_batch(item, result, 'stratum-01')
    assert len(rows) == 16 and all(row['raw_distance'] == 0.25 and row['score'] is None for row in rows)
    assert normalizer.sample_totals(result)['record_count'] == 64
    assert normalizer.sample_totals(result)['eligible_word_count'] == 16000
    assert result == before
    assert 'samples' not in json.dumps(rows) and 'dataset_id' not in json.dumps(rows)


def test_all5760_sanitized_rows_and960_units_keep_fixed_identity_and_missingness(prepared):
    root, index = prepared
    stratum_map = {sid: f'stratum-{number:02d}' for number, sid in enumerate(sorted({i['stratum_id'] for i in index}), 1)}
    private_units = json.loads((root/'unit-metadata.json').read_bytes())
    unit_lookup = {(r['block_id'], r['arm'], r['cell_id']): r for r in private_units}
    cases = []
    for item in index:
        result = evaluation(item, item['block_id'] + '/' + item['arm'] + '/' + item['view'])
        for row in result['partitions']['evaluation']['rows']:
            qualifies = True
            for side in ('left', 'right'):
                unit = unit_lookup[item['block_id'], item['arm'], row[side + '_text_id']]
                row['samples'][side] = {'record_count': unit['records'], 'word_count': unit['retained_words'],
                    'eligible_record_count': unit['records'], 'eligible_word_count': unit['retained_words'],
                    'usable_record_count': unit['records']}
                qualifies &= unit['ordinary_volume_guards_met']
            row.update(score=0.25 if qualifies else None, status='ok' if qualifies else 'abstained',
                       reason_codes=[] if qualifies else ['insufficient_records'])
        cases.extend(normalizer.extract_batch(item, result, stratum_map[item['stratum_id']]))
        totals = normalizer.sample_totals(result)
        expected = [r for r in private_units if r['block_id'] == item['block_id'] and r['arm'] == item['arm']]
        assert totals['record_count'] == sum(r['records'] for r in expected)
        assert totals['eligible_word_count'] == sum(r['retained_words'] for r in expected)
    units = [{**{key: row[key] for key in normalizer.UNIT_FIELDS}, 'stratum_id': stratum_map[row['stratum_id']]}
             for row in private_units]
    dependencies = json.loads((root/'dependency-units.json').read_bytes())
    normalizer.validate_inputs(cases, units, dependencies, sorted(stratum_map.values()))
    assert len(cases) == 5760 and len(units) == 960
    assert any(r['score'] is None and r['raw_distance'] == 0.25 for r in cases)
    assert all(set(r) == normalizer.CASE_FIELDS for r in cases)
    assert 'private-source-' not in json.dumps(cases)
