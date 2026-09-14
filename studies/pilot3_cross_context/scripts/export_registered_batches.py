"""Registered, evaluation-only export adapter; never run the distance evaluator.

Pre-score review found that the unexecuted export prototype in the already
executed finalizer omitted source_document groups. This new adapter adds actual
retained record IDs, fixed sampled-period bounds and local-use license notes.
The executed finalizer and prepared-cell selection remain byte-identical.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import time

import finalize_cohort as frozen_finalizer
import prepare_units as units

VERSION = 'pilot3-registered-batch-export-v1'
FINALIZER_SHA256 = '22132229bf069c5d55775ed3ac3235a73d06886413b18ad1878a29922084fa1e'
REVIEW_CHANGE = ('Pre-score review of the unexecuted prototype export found missing source_document '
                 'groups. This separate adapter adds retained original record IDs and sampled-period '
                 'manifest metadata; the executed cohort finalizer is unchanged.')
GROUP_SCOPE = ('Every batch contains evaluation units only. The frozen evaluator cannot audit '
               'development/evaluation disjointness without both splits, even when all five grouping '
               'dimensions are supplied. The separate Gate B audit protects historical boundaries. '
               'Empty omission units honestly lack record-derived grouping labels.')
LICENSE_NOTES = 'Authorized by the user for local evaluation only; source prose is private and must not be redistributed.'
canonical = frozen_finalizer.canonical
sha_file = frozen_finalizer.sha_file
write_new = frozen_finalizer.write_new


class ExportFailure(ValueError):
    """Public-safe error code; source prose and identities never enter messages."""


def require(condition, code):
    if not condition:
        raise ExportFailure(code)


def unit_metadata(cohort, block, prepared, *, source_category):
    """Record-derived groups describe the current arm, including honest emptiness."""
    manifests, groups = {}, {}
    for key, rows in prepared['units'].items():
        start, end = units._period(block['period_bounds'][key.split('/')[2]])
        manifests[key] = {'schema_version': '1.0.0',
            'snapshot_id': block['block_id'] + '/' + prepared['arm'] + '/' + key,
            'account_id': prepared['source_accounts'][key[0]], 'source_category': source_category,
            'text_format': 'markdown', 'default_language': 'en',
            'source_notes': 'Original supplied comments; English eligibility is a declared corpus assumption.',
            'license_notes': LICENSE_NOTES,
            'coverage': {'status': 'sampled', 'start_utc': units._utc(start), 'end_utc': units._utc(end),
                         'notes': 'Frozen half-open calendar interval; sampled whole-record subset; omissions are never refilled.'}}
        groups[key] = {'author': [block['account_keys'][key[0]]],
                       'related_sample': [cohort['groups']['unit_by_block'][block['block_id']]]}
        if rows:
            ids = [entry['record']['id'] for entry in rows]
            threads = [entry['record'].get('thread_id') for entry in rows]
            require(all(isinstance(t, str) and t for t in threads), 'retained_thread_metadata_missing')
            clusters = [cohort['groups']['content_component_by_record'].get(rid) for rid in ids]
            require(all(isinstance(c, str) and c for c in clusters), 'retained_content_group_missing')
            groups[key].update(source_document=sorted(set(ids)), thread=sorted(set(threads)),
                               near_duplicate_cluster=sorted(set(clusters)))
    return manifests, groups


def validate_registration(cohort, registration):
    require(sha_file(frozen_finalizer.__file__) == FINALIZER_SHA256, 'executed_finalizer_identity_changed')
    require(registration.get('phase') == 'registered_pre_score_batch_export' and
            registration.get('registered_before_evaluation') is True and
            isinstance(registration.get('preregistration_provenance'), str) and
            bool(registration['preregistration_provenance']) and
            re.fullmatch(r'[0-9a-f]{64}', registration.get('protocol_sha256', '')) is not None,
            'frozen_export_registration_required')
    require(isinstance(registration.get('provenance'), str) and registration['provenance'],
            'literal_dataset_provenance_required')
    require(registration.get('source_category') in ('research_corpus', 'synthetic'),
            'explicit_source_category_required')
    require(registration.get('final_cohort_sha256') == hashlib.sha256(canonical(cohort)).hexdigest(),
            'registered_final_cohort_hash_mismatch')
    require(sha_file(registration['protocol_path']) == registration['protocol_sha256'],
            'registered_protocol_file_changed')
    dependencies = {'exporter': Path(__file__), 'prepare_units': Path(units.__file__),
                    'finalize_cohort': Path(frozen_finalizer.__file__),
                    'study_math': Path(__file__).with_name('study_math.py')}
    for key, path in dependencies.items():
        require(sha_file(path) == registration.get(key + '_sha256'), 'registered_export_dependency_changed')
    require(cohort['summary']['status'] == 'cohort_selected_not_scored' and
            cohort['summary']['selected_accounts'] == 60 and cohort['summary']['selected_blocks'] == 30 and
            len(cohort['blocks']) == 30 and len({b['block_id'] for b in cohort['blocks']}) == 30 and
            len({b['stratum_id'] for b in cohort['blocks']}) == 3,
            'complete_fixed_final_cohort_required')
    require(all(n == 10 for n in Counter(b['stratum_id'] for b in cohort['blocks']).values()),
            'ten_blocks_in_every_stratum_required')


def export_all_batches(output_root, cohort, *, registration):
    """Export all fixed method/arm batches; return no scored result."""
    validate_registration(cohort, registration)
    output_root = Path(output_root)
    output_root.mkdir(parents=True, mode=0o700, exist_ok=False)
    output_root.chmod(0o700)
    write_new(output_root/'export-start-binding.json', {'status': 'started_not_scored', 'version': VERSION,
        'registration': registration, 'review_change': REVIEW_CHANGE, 'group_scope': GROUP_SCOPE,
        'exporter_sha256': sha_file(__file__), 'unchanged_finalizer_sha256': FINALIZER_SHA256}, private=True)
    receipts, unit_rows = [], []
    for block in cohort['blocks']:
        for arm in units.ARMS:
            prepared = units.prepare_block(block['cells'], block['block_id'], block['period_bounds'], arm)
            unit_rows.extend({'stratum_id': block['stratum_id'], 'block_id': block['block_id'],
                              'arm': arm, 'cell_id': key, **stats}
                             for key, stats in prepared['statistics'].items())
            manifests, groups = unit_metadata(cohort, block, prepared, source_category=registration['source_category'])
            for method_index, method in enumerate(units.METHODS, 1):
                batch_id = block['block_id'] + '-' + arm + f'-method-{method_index:02d}'
                require(re.fullmatch(r'[a-z0-9_-]+', batch_id) is not None, 'unsafe_batch_identifier')
                receipt = units.export_paired_batch(output_root/batch_id, prepared, method,
                    manifests=manifests, groups=groups, provenance=registration['provenance'], registration=registration)
                receipts.append({**receipt, 'batch_id': batch_id, 'block_id': block['block_id'],
                    'stratum_id': block['stratum_id'], **method,
                    'resampling_unit_id': cohort['groups']['unit_by_block'][block['block_id']],
                    'dataset': batch_id + '/dataset.json',
                    'dataset_sha256': receipt['input_hashes']['dataset.json']['sha256'],
                    'input_file_receipts': receipt['input_hashes'],
                    'input_hashes': {batch_id + '/' + name: value['sha256']
                                     for name, value in receipt['input_hashes'].items()}})
    require(len(receipts) == 360 and len(unit_rows) == 960, 'incomplete_fixed_export_count')
    summary = {'status': 'all_batches_prepared_not_scored', 'version': VERSION, 'scores_computed': False,
               'batches': 360, 'method_arm_comparisons': sum(r['pairs'] for r in receipts),
               'protocol_sha256': registration['protocol_sha256'], 'final_cohort_sha256': registration['final_cohort_sha256'],
               'exporter_sha256': sha_file(__file__), 'unchanged_finalizer_sha256': FINALIZER_SHA256,
               'max_batch_bytes': max(r['invocation_input_bytes'] for r in receipts),
               'max_batch_unique_records': max(r['unique_records'] for r in receipts),
               'arm_batch_counts': dict(Counter(r['arm'] for r in receipts)),
               'empty_omission_units': sum(not r['nonempty'] for r in unit_rows),
               'review_change': REVIEW_CHANGE, 'group_scope': GROUP_SCOPE,
               'group_dimensions_for_nonempty_units': ['author', 'thread', 'source_document', 'near_duplicate_cluster', 'related_sample']}
    write_new(output_root/'batch-index.json', receipts, private=True)
    write_new(output_root/'unit-metadata.json', unit_rows, private=True)
    write_new(output_root/'dependency-units.json', cohort['groups']['unit_by_block'], private=True)
    write_new(output_root/'export-summary.json', summary, private=True)
    return {'summary': summary, 'batches': receipts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('cohort', 'registration', 'out'):
        parser.add_argument('--' + flag, type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3,) * 2)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError()))
    signal.alarm(1800)
    try:
        require(os.environ.get('AHAS_NETWORK_ISOLATION') == 'linux_seccomp_socket_denial', 'offline_runner_required')
        require(not args.out.exists(), 'output_already_exists')
        require(args.cohort.stat().st_size <= 256 * 1024**2, 'cohort_input_byte_ceiling')
        registration = json.loads(args.registration.read_bytes())
        require(sha_file(args.cohort) == registration.get('final_cohort_sha256'), 'frozen_cohort_file_changed')
        cohort = json.loads(args.cohort.read_bytes())
        result = export_all_batches(args.out, cohort, registration=registration)
        public = {**result['summary'], 'registration_sha256': sha_file(args.registration),
                  'batch_index_sha256': sha_file(args.out/'batch-index.json'),
                  'unit_metadata_sha256': sha_file(args.out/'unit-metadata.json'),
                  'dependency_units_sha256': sha_file(args.out/'dependency-units.json')}
    except Exception as error:
        code = str(error) if type(error) is ExportFailure else {
            MemoryError: 'memory_allocation_failed', TimeoutError: 'wall_time_exceeded'
        }.get(type(error), 'unexpected_' + type(error).__name__)
        public = {'status': 'export_failed', 'reason_codes': [code], 'scores_computed': False}
    public.update(wall_seconds=time.monotonic() - started, peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    try:
        print(json.dumps(public, sort_keys=True), flush=True)
    finally:
        signal.alarm(0)
    return 0 if public['status'] == 'all_batches_prepared_not_scored' else 4


if __name__ == '__main__':
    raise SystemExit(main())
