"""Synthetic export tests only. No real cohort input or evaluator call."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import export_registered_batches as exporter
import finalize_cohort as final
import prepare_units as units
from test_finalize_cohort import fixture


@pytest.fixture(scope='module')
def cohort():
    return final.finalize(*fixture())


def registered(tmp_path, cohort):
    protocol = tmp_path/'synthetic-protocol.md'
    protocol.write_text('Synthetic fixture registration only. No empirical data or scores.\n')
    registration = {'phase': 'registered_pre_score_batch_export', 'registered_before_evaluation': True,
                    'preregistration_provenance': 'Explicit synthetic fixture only.',
                    'protocol_path': str(protocol), 'protocol_sha256': exporter.sha_file(protocol),
                    'final_cohort_sha256': hashlib.sha256(exporter.canonical(cohort)).hexdigest(),
                    'provenance': 'Constructed synthetic adapter test; no empirical study.',
                    'source_category': 'synthetic'}
    for key, path in [('exporter', exporter.__file__), ('prepare_units', units.__file__),
                      ('finalize_cohort', final.__file__), ('study_math', Path(final.__file__).with_name('study_math.py'))]:
        registration[key + '_sha256'] = exporter.sha_file(path)
    return registration


@pytest.mark.parametrize('arm', units.ARMS)
def test_group_dimensions_use_only_current_arm_original_records(cohort, arm):
    block = cohort['blocks'][0]
    prepared = units.prepare_block(block['cells'], block['block_id'], block['period_bounds'], arm)
    before = deepcopy(prepared)
    manifests, groups = exporter.unit_metadata(cohort, block, prepared, source_category='synthetic')
    for key, rows in prepared['units'].items():
        assert groups[key]['source_document'] == sorted(e['record']['id'] for e in rows)
        assert groups[key]['thread'] == sorted({e['record']['thread_id'] for e in rows})
        assert groups[key]['near_duplicate_cluster'] == sorted({cohort['groups']['content_component_by_record'][e['record']['id']] for e in rows})
        assert groups[key]['author'] == [block['account_keys'][key[0]]]
        assert groups[key]['related_sample'] == [cohort['groups']['unit_by_block'][block['block_id']]]
        start, end = units._period(block['period_bounds'][key.split('/')[2]])
        assert manifests[key]['coverage']['start_utc'] == units._utc(start)
        assert manifests[key]['coverage']['end_utc'] == units._utc(end)
        assert manifests[key]['coverage']['status'] == 'sampled'
        assert manifests[key]['license_notes'] == exporter.LICENSE_NOTES
    assert prepared == before


def test_empty_omission_keeps_known_dependency_but_no_fabricated_record_groups(cohort):
    block = cohort['blocks'][0]
    prepared = units.prepare_block(block['cells'], block['block_id'], block['period_bounds'], 'hash50')
    prepared['units']['A/X/early'] = []  # Explicit constructed empty-arm metadata case.
    manifests, groups = exporter.unit_metadata(cohort, block, prepared, source_category='synthetic')
    assert set(groups['A/X/early']) == {'author', 'related_sample'}
    assert manifests['A/X/early']['coverage']['start_utc'] == '2017-01-01T00:00:00Z'


def test_missing_actual_thread_or_content_group_fails_without_fabrication(cohort):
    mutable = deepcopy(cohort)
    block = mutable['blocks'][0]
    prepared = units.prepare_block(block['cells'], block['block_id'], block['period_bounds'])
    prepared['units']['A/X/early'][0]['record']['thread_id'] = None
    with pytest.raises(exporter.ExportFailure, match='retained_thread_metadata_missing'):
        exporter.unit_metadata(mutable, block, prepared, source_category='synthetic')
    prepared['units']['A/X/early'][0]['record']['thread_id'] = 'known-synthetic-thread'
    rid = prepared['units']['A/X/early'][0]['record']['id']
    del mutable['groups']['content_component_by_record'][rid]
    with pytest.raises(exporter.ExportFailure, match='retained_content_group_missing'):
        exporter.unit_metadata(mutable, block, prepared, source_category='synthetic')


@pytest.mark.parametrize('changed,code', [
    ('phase', 'frozen_export_registration_required'),
    ('protocol_file', 'registered_protocol_file_changed'),
    ('final_cohort_sha256', 'registered_final_cohort_hash_mismatch'),
    ('exporter_sha256', 'registered_export_dependency_changed'),
])
def test_prior_exact_registration_is_required_before_output(tmp_path, cohort, changed, code):
    reg = registered(tmp_path, cohort)
    if changed == 'protocol_file': Path(reg['protocol_path']).write_text('Changed synthetic protocol.\n')
    else: reg[changed] = 'invalid'
    with pytest.raises(exporter.ExportFailure, match=code):
        exporter.export_all_batches(tmp_path/'output', cohort, registration=reg)
    assert not (tmp_path/'output').exists()


def test_offline_full_export_has_complete_observed_groups_but_honest_split_scope(tmp_path, cohort):
    from account_history_analyzer.evaluation_external import GROUP_DIMENSIONS, _group_audit, _paired_units
    reg = registered(tmp_path, cohort)
    cohort_path, reg_path = tmp_path/'cohort.json', tmp_path/'registration.json'
    cohort_path.write_bytes(exporter.canonical(cohort)); reg_path.write_bytes(exporter.canonical(reg))
    output = tmp_path/'prepared'
    offline = os.environ.get('AHAS_PILOT3_OFFLINE_RUNNER', '/tmp/ahas-pilot3-reviewed-repo/scripts/offline_exec.py')
    command = [sys.executable, offline, sys.executable, exporter.__file__, '--cohort', str(cohort_path),
               '--registration', str(reg_path), '--out', str(output)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ''
    summary = json.loads(result.stdout)
    assert summary['batches'] == 360 and summary['method_arm_comparisons'] == 5760
    assert summary['scores_computed'] is False
    assert summary['unchanged_finalizer_sha256'] == exporter.FINALIZER_SHA256
    assert 'unexecuted prototype' in summary['review_change']
    assert all(secret not in result.stdout for secret in ('private-source-', 'synthetic prose', str(tmp_path)))
    assert exporter.sha_file(final.__file__) == exporter.FINALIZER_SHA256
    index = json.loads((output/'batch-index.json').read_bytes())
    assert len(index) == 360
    for row in index:
        dataset_file = output/row['dataset']; dataset = json.loads(dataset_file.read_bytes())
        assert row['dataset_sha256'] == exporter.sha_file(dataset_file)
        assert len(row['input_hashes']) == 17
        for unit in dataset['texts']:
            records = [json.loads(line) for line in (dataset_file.parent/unit['input']).read_bytes().splitlines()]
            if records:
                assert set(unit['groups']) == set(GROUP_DIMENSIONS)
                assert unit['groups']['source_document'] == sorted(r['id'] for r in records)
                assert unit['groups']['thread'] == sorted({r['thread_id'] for r in records})
            else:
                assert set(unit['groups']) == {'author', 'related_sample'}
            manifest = json.loads((dataset_file.parent/unit['manifest']).read_bytes())
            assert manifest['coverage']['start_utc'] and manifest['coverage']['end_utc']
            assert manifest['license_notes'] == exporter.LICENSE_NOTES
        # Metadata-only function; it does not calculate distances or features.
        audits = _group_audit(*_paired_units(dataset))
        assert all(a['status'] == 'not_auditable' and a['development_group_count'] == 0 for a in audits)
        if row['arm'] == 'full': assert all(a['missing_evaluation_units'] == [] for a in audits)
    assert output.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in output.rglob('*') if p.is_file())
    before = exporter.sha_file(output/'batch-index.json')
    rerun = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert rerun.returncode == 4
    assert json.loads(rerun.stdout)['reason_codes'] == ['output_already_exists']
    assert exporter.sha_file(output/'batch-index.json') == before
