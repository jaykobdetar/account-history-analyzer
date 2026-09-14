import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from normalize_evaluations import extract_batch, sample_totals
from study_math import comparison_design


def fixture():
    item = {'block_id': 'stratum-01-block-01', 'arm': 'hash50',
            'method_id': 'cosine_distance_v1', 'view': 'retained_prose', 'n': 4}
    rows = [{'pair_id': r['pair_id'], 'label': r['label'], 'left_text_id': r['left_cell_id'],
             'right_text_id': r['right_cell_id'], 'split': 'evaluation', 'score': None,
             'raw_distance': .35, 'status': 'abstained', 'reason_codes': ['insufficient_records'],
             'samples': {'private_extra': 'never publish this'}} for r in comparison_design(item['block_id'])]
    doc = {'distance': {k: item[k] for k in ('method_id', 'view', 'n')}, 'exit_code': 0,
           'dataset_id': item['block_id'] + '/' + item['arm'] + '/' + item['view'],
           'private_group_map': ['never publish this'],
           'partitions': {'evaluation': {'rows': rows}, 'development': {'rows': []}}}
    return item, doc


def test_all_rows_raw_values_and_missingness_preserved_without_private_fields():
    item, doc = fixture()
    original = copy.deepcopy(doc)
    rows = extract_batch(item, doc, 'stratum-01')
    assert len(rows) == 16
    assert all(r['score'] is None and r['raw_distance'] == .35 for r in rows)
    assert 'private' not in repr(rows)
    assert doc == original


@pytest.mark.parametrize('defect', ['missing', 'duplicate', 'label', 'side', 'split', 'method', 'development', 'failed', 'wrong_arm'])
def test_changed_comparison_contract_is_rejected(defect):
    item, doc = fixture()
    rows = doc['partitions']['evaluation']['rows']
    if defect == 'missing': rows.pop()
    if defect == 'duplicate': rows[-1] = copy.deepcopy(rows[0])
    if defect == 'label': rows[0]['label'] = 'different_author'
    if defect == 'side': rows[0]['right_text_id'] = 'B/Y/early'
    if defect == 'split': rows[0]['split'] = 'confirmation'
    if defect == 'method': doc['distance']['n'] = 5
    if defect == 'development': doc['partitions']['development']['rows'] = [rows[0]]
    if defect == 'failed': doc['exit_code'] = 4
    if defect == 'wrong_arm': doc['dataset_id'] = doc['dataset_id'].replace('/hash50/', '/full/')
    with pytest.raises(ValueError):
        extract_batch(item, doc, 'stratum-01')


def test_repeated_anchors_are_not_repeated_input_counts():
    _, doc = fixture()
    for row in doc['partitions']['evaluation']['rows']:
        row['samples'] = {side: {'record_count': 8, 'word_count': 2000, 'eligible_record_count': 8,
                                'eligible_word_count': 2000, 'usable_record_count': 8}
                          for side in ('left', 'right')}
    counts = sample_totals(doc)
    assert counts['record_count'] == 64
    assert counts['word_count'] == counts['eligible_word_count'] == 16000
    doc['partitions']['evaluation']['rows'][0]['samples']['left']['word_count'] = 2001
    with pytest.raises(ValueError, match='inconsistent'):
        sample_totals(doc)
