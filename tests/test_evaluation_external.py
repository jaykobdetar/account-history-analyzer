"""Local external adapter integration: construction labels test software only."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import weakref

import pytest

from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.errors import InputError, LimitError
from account_history_analyzer.evaluation_external import evaluate_external, freeze_pair_threshold
from account_history_analyzer.io import canonical_bytes, digest
from account_history_analyzer.schemas import load_schema, validate

ROOT = Path(__file__).resolve().parents[1]


def config():
    return AnalysisConfig.from_mapping({'style': {'minimum_record_words': 1,
        'minimum_comparison_words_per_side': 1, 'minimum_comparison_records_per_side': 1},
        'windows': {'target_words': 20, 'minimum_records': 1}})


def snapshot(tmp_path, name, texts):
    manifest = json.loads((ROOT/'fixtures/arithmetic.snapshot.json').read_text())
    manifest.update(account_id=name, snapshot_id=name)
    rows = [{'schema_version': '1.0.0', 'id': f'{name}_{i}', 'account_id': name, 'kind': 'comment',
             'subreddit': 'supplied', 'created_utc': f'2025-01-01T00:{i//60:02d}:{i%60:02d}Z',
             'status': 'present', 'text': text, 'language': 'en', 'edit_state': 'not_edited'}
            for i, text in enumerate(texts)]
    (tmp_path/(name+'.jsonl')).write_bytes(b''.join(canonical_bytes(row) for row in rows))
    (tmp_path/(name+'.snapshot.json')).write_bytes(canonical_bytes(manifest))
    return {'input': name+'.jsonl', 'manifest': name+'.snapshot.json'}


def save(tmp_path, data):
    path = tmp_path/'dataset.json'
    path.write_bytes(canonical_bytes(data))
    return path


def paired(tmp_path):
    cfg = config()
    data = {'schema_version': '1.0.0', 'format': 'paired_text', 'dataset_id': 'constructed_test',
            'provenance': 'Original numerical test construction, not external validation.',
            'label_definition': 'same_author/different_author are supplied test labels, not established authorship.',
            'protocol': {'analysis_config_sha256': digest(cfg.analytical()),
                         'registered_before_evaluation': True, 'preregistration_provenance': 'Fixed unit-test protocol',
                         'distance': {'method_id': 'function_word_js_v1', 'view': 'lexical_tokens', 'n': None},
                         'frozen_threshold': None}, 'texts': [], 'pairs': []}
    for split, prefix, multiplier in [('development', 'd', 1), ('evaluation', 'e', 3)]:
        for suffix, word, count in [('a', 'the', 10), ('b', 'the', 20), ('c', 'cat', 11)]:
            name = prefix+suffix
            data['texts'].append({'text_id': name, **snapshot(tmp_path, name, [' '.join([word]*(count*multiplier))]),
                                  'groups': {key: [name] for key in ('thread', 'source_document', 'near_duplicate_cluster', 'related_sample')}})
            data['texts'][-1]['groups']['author'] = [prefix+('first' if suffix in 'ab' else 'second')]
        data['pairs'].extend([{'pair_id': prefix+'same', 'left_text_id': prefix+'a', 'right_text_id': prefix+'b',
                               'split': split, 'label': 'same_author'},
                              {'pair_id': prefix+'different', 'left_text_id': prefix+'a', 'right_text_id': prefix+'c',
                               'split': split, 'label': 'different_author'}])
    return data, cfg


def test_EVAL_EXT_01_qualified_public_pair_metrics_and_frozen_decisions(tmp_path):
    data, cfg = paired(tmp_path)
    path = save(tmp_path, data)
    threshold = freeze_pair_threshold(path, cfg, value=.5, selection_rule='Midpoint of development class scores',
                                      provenance='Selected from this numerical development construction only')
    data['protocol']['frozen_threshold'] = threshold
    result = evaluate_external(save(tmp_path, data), 'paired_text', cfg)
    heldout = result['partitions']['evaluation']
    assert {row['label']: row['score'] for row in heldout['rows']} == {'same_author': 0, 'different_author': 1}
    assert heldout['metrics']['ranking']['roc_auc']['value'] == 1
    assert heldout['metrics']['ranking']['average_precision']['value'] == 1
    assert heldout['metrics']['decisions']['false_positive_rate']['value'] == 0
    assert heldout['metrics']['decisions']['recall']['value'] == 1
    assert all(item['status'] == 'audited_disjoint' for item in result['leakage_audit'])
    assert result['status'] == 'evaluated' and result['exit_code'] == 0
    assert len(result['dataset_sha256']) == len(result['method_sha256']) == 64


def test_EVAL_EXT_02_default_guards_abstain_despite_raw_distance(tmp_path):
    data, _ = paired(tmp_path)
    cfg = AnalysisConfig.from_mapping()
    data['protocol']['analysis_config_sha256'] = digest(cfg.analytical())
    result = evaluate_external(save(tmp_path, data), 'paired_text', cfg)
    rows = result['partitions']['evaluation']['rows']
    assert all(row['status'] == 'abstained' and row['score'] is None for row in rows)
    assert sorted(row['raw_distance'] for row in rows) == [0, 1]
    assert result['partitions']['evaluation']['metrics']['ranking']['roc_auc']['value'] is None
    assert result['partitions']['evaluation']['metrics']['decisions']['status'] == 'not_run_missing_threshold'


@pytest.mark.parametrize('dimension', ['author', 'thread', 'source_document', 'near_duplicate_cluster', 'related_sample'])
def test_EVAL_EXT_03_observed_group_leakage_rejected(tmp_path, dimension):
    data, cfg = paired(tmp_path)
    data['texts'][3]['groups'][dimension] = data['texts'][0]['groups'][dimension]
    with pytest.raises(InputError, match='evaluation_leakage'):
        evaluate_external(save(tmp_path, data), 'paired_text', cfg)


def test_EVAL_EXT_04_missing_group_metadata_is_unauditable(tmp_path):
    data, cfg = paired(tmp_path)
    for text in data['texts']:
        del text['groups']
    result = evaluate_external(save(tmp_path, data), 'paired_text', cfg)
    assert all(row['status'] == 'not_auditable' for row in result['leakage_audit'])
    assert all(row['missing_development_units'] and row['missing_evaluation_units'] for row in result['leakage_audit'])


def test_EVAL_EXT_05_freezing_reads_no_heldout_files_or_labels(tmp_path):
    data, cfg = paired(tmp_path)
    path = save(tmp_path, data)
    before = freeze_pair_threshold(path, cfg, value=.5, selection_rule='Development-only rule', provenance='test')
    for pair in data['pairs']:
        if pair['split'] == 'evaluation':
            pair['label'] = 'different_author' if pair['label'] == 'same_author' else 'same_author'
    data['texts'][3]['input'] = 'absent-heldout.jsonl'
    after = freeze_pair_threshold(save(tmp_path, data), cfg, value=.5, selection_rule='Development-only rule', provenance='test')
    assert before == after
    with pytest.raises(InputError):
        evaluate_external(save(tmp_path, data), 'paired_text', cfg)


def test_EVAL_EXT_06_heldout_labels_do_not_change_scores_and_development_binding_detects_tamper(tmp_path):
    data, cfg = paired(tmp_path)
    data['protocol']['frozen_threshold'] = freeze_pair_threshold(save(tmp_path, data), cfg, value=.5,
        selection_rule='Development-only rule', provenance='test')
    before = evaluate_external(save(tmp_path, data), 'paired_text', cfg)
    for pair in data['pairs']:
        if pair['split'] == 'evaluation':
            pair['label'] = 'different_author' if pair['label'] == 'same_author' else 'same_author'
    after = evaluate_external(save(tmp_path, data), 'paired_text', cfg)
    assert [r['score'] for r in before['partitions']['evaluation']['rows']] == [r['score'] for r in after['partitions']['evaluation']['rows']]
    assert before['development_dataset_sha256'] == after['development_dataset_sha256']
    assert before['dataset_sha256'] != after['dataset_sha256']
    data['pairs'][0]['label'] = 'different_author'
    with pytest.raises(InputError, match='frozen_threshold_mismatch'):
        evaluate_external(save(tmp_path, data), 'paired_text', cfg)


def test_EVAL_EXT_07_path_independent_source_identity(tmp_path):
    data, cfg = paired(tmp_path)
    before = evaluate_external(save(tmp_path, data), 'paired_text', cfg)
    for i, unit in enumerate(data['texts']):
        for key in ('input', 'manifest'):
            name = f'copy-{i}-{key}.json'
            shutil.copyfile(tmp_path/unit[key], tmp_path/name)
            unit[key] = name
    after = evaluate_external(save(tmp_path, data), 'paired_text', cfg)
    assert canonical_bytes(before) == canonical_bytes(after)


def test_EVAL_EXT_08_absent_dataset_unknown_keys_and_unknown_text(tmp_path):
    with pytest.raises(InputError):
        evaluate_external(tmp_path/'absent.json', 'paired_text')
    data, cfg = paired(tmp_path)
    data['protocol']['unapproved_setting'] = True
    with pytest.raises(InputError, match='schema_validation'):
        evaluate_external(save(tmp_path, data), 'paired_text', cfg)
    del data['protocol']['unapproved_setting']
    data['pairs'][0]['left_text_id'] = 'unknown'
    with pytest.raises(InputError, match='unknown_evaluation_text'):
        evaluate_external(save(tmp_path, data), 'paired_text', cfg)


def stream_dataset(tmp_path):
    cfg = config()
    source = snapshot(tmp_path, 'whole_stream', [' '.join(['the' if i < 4 else 'CAT']*20) for i in range(8)])
    data = {'schema_version': '1.0.0', 'format': 'account_stream', 'dataset_id': 'constructed_stream',
            'provenance': 'Original software test construction only.', 'label_definition': 'Known construction split.',
            'protocol': {'analysis_config_sha256': digest(cfg.analytical()), 'registered_before_evaluation': True,
                         'preregistration_provenance': 'Fixed numerical protocol', 'boundary_tolerance_records': 0},
            'streams': [{'stream_id': 'test_stream', **source, 'split': 'evaluation',
                         'scope': {'scope_type': 'pooled', 'kind': 'comment', 'subreddit': None},
                         'truth_boundaries': [4], 'annotation_provenance': 'Feature transformation after four records'}]}
    return data, cfg


def test_EVAL_EXT_09_stream_runs_whole_pipeline_and_maps_split_coordinates(tmp_path):
    data, cfg = stream_dataset(tmp_path)
    result = evaluate_external(save(tmp_path, data), 'account_stream', cfg)
    row = result['partitions']['evaluation']['rows'][0]
    assert row['status'] == 'ok'
    assert row['candidate_intervals'] == [[4, 4]]
    assert row['metrics']['matched_count'] == 1
    assert row['metrics']['matches'][0]['location_error_records'] == 0
    assert row['metrics']['precision']['value'] == row['metrics']['recall']['value'] == 1
    assert len(row['analysis_results_sha256']) == 64


def test_EVAL_EXT_10_stream_abstention_is_not_zero_false_boundaries(tmp_path):
    data, cfg = stream_dataset(tmp_path)
    data['streams'][0]['scope']['kind'] = 'submission'
    data['streams'][0]['truth_boundaries'] = []
    result = evaluate_external(save(tmp_path, data), 'account_stream', cfg)
    heldout = result['partitions']['evaluation']
    assert heldout['rows'][0]['status'] == 'abstained'
    assert heldout['rows'][0]['metrics'] is None
    assert heldout['known_unchanged_stream_count'] == heldout['abstained_unchanged_stream_count'] == 1
    assert heldout['metrics']['false_candidates_per_unchanged_stream']['value'] is None


def test_EVAL_EXT_11_stream_truth_bounds_and_protocol_hash_are_checked(tmp_path):
    data, cfg = stream_dataset(tmp_path)
    data['streams'][0]['truth_boundaries'] = [8]
    with pytest.raises(InputError, match='invalid_evaluation_boundary'):
        evaluate_external(save(tmp_path, data), 'account_stream', cfg)
    data['streams'][0]['truth_boundaries'] = [4]
    data['protocol']['analysis_config_sha256'] = '0'*64
    with pytest.raises(InputError, match='evaluation_config_mismatch'):
        evaluate_external(save(tmp_path, data), 'account_stream', cfg)


def test_EVAL_EXT_12_installed_input_contracts_are_strict_and_mirrored():
    for name in ('evaluation_paired_text', 'evaluation_account_stream'):
        schema = load_schema(name)
        assert schema['additionalProperties'] is False
        assert schema == json.loads((ROOT/'schemas'/f'{name}.schema.json').read_text())


def test_EVAL_EXT_13_shared_snapshot_and_sample_rejected(tmp_path):
    data, cfg = paired(tmp_path)
    data['pairs'][2]['left_text_id'] = 'da'
    with pytest.raises(InputError, match='evaluation_leakage'):
        evaluate_external(save(tmp_path, data), 'paired_text', cfg)
    data, cfg = paired(tmp_path)
    data['texts'][3].update({k: data['texts'][0][k] for k in ('input', 'manifest')})
    with pytest.raises(InputError, match='evaluation_leakage'):
        evaluate_external(save(tmp_path, data), 'paired_text', cfg)


def test_EVAL_EXT_14_eligible_constant_stream_counts_in_unchanged_denominator(tmp_path):
    data, cfg = stream_dataset(tmp_path)
    snapshot(tmp_path, 'whole_stream', [' '.join(['the']*20)]*8)
    data['streams'][0]['truth_boundaries'] = []
    result = evaluate_external(save(tmp_path, data), 'account_stream', cfg)
    heldout = result['partitions']['evaluation']
    assert heldout['rows'][0]['status'] == 'ok'
    assert heldout['rows'][0]['change_status'] == 'no_measurable_variation'
    assert heldout['rows'][0]['candidate_intervals'] == []
    metric = heldout['metrics']['false_candidates_per_unchanged_stream']
    assert metric['value'] == 0 and metric['denominator'] == 1
    assert heldout['abstained_unchanged_stream_count'] == 0


def test_EVAL_EXT_15_total_snapshot_record_budget_is_explicit(tmp_path):
    data, _ = paired(tmp_path)
    cfg = AnalysisConfig.from_mapping({'input': {'max_unique_records': 4}})
    data['protocol']['analysis_config_sha256'] = digest(cfg.analytical())
    with pytest.raises(LimitError, match='evaluation_record_limit'):
        evaluate_external(save(tmp_path, data), 'paired_text', cfg)


def test_EVAL_EXT_16_frozen_method_binding_is_checked(tmp_path):
    data, cfg = paired(tmp_path)
    frozen = freeze_pair_threshold(save(tmp_path, data), cfg, value=.5,
                                  selection_rule='Fixed numerical rule', provenance='test')
    frozen['method_sha256'] = '0'*64
    data['protocol']['frozen_threshold'] = frozen
    with pytest.raises(InputError, match='frozen_threshold_mismatch'):
        evaluate_external(save(tmp_path, data), 'paired_text', cfg)


def test_EVAL_EXT_17_prior_full_analysis_is_released_before_next_snapshot(tmp_path, monkeypatch):
    from account_history_analyzer import pipeline
    data, cfg = stream_dataset(tmp_path)
    second = deepcopy(data['streams'][0])
    second.update(stream_id='second_stream', **snapshot(tmp_path, 'second',
                  [' '.join(['the' if i < 4 else 'CAT']*20) for i in range(8)]))
    data['streams'].append(second)
    original = pipeline.analyze
    prior = []

    def track(snapshot, config):
        assert all(reference() is None for reference in prior)
        result = original(snapshot, config)
        prior.append(weakref.ref(result))
        return result

    monkeypatch.setattr(pipeline, 'analyze', track)
    result = evaluate_external(save(tmp_path, data), 'account_stream', cfg)
    assert len(prior) == 2 and all(reference() is None for reference in prior)
    assert all(row['metrics']['matched_count'] == 1 for row in result['partitions']['evaluation']['rows'])
