#!/usr/bin/env python3
"""Execute only all frozen evaluation batches, or the one fixed replay stratum.

This runner cannot select a method, tune a threshold, access extra histories or
alter prepared units. No real execution is authorized without the final freeze.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

from account_history_analyzer import AnalysisConfig
from account_history_analyzer.io import digest
from account_history_analyzer.pipeline import implementation_identity

METHODS = {('cosine_distance_v1', 'retained_prose', 4),
           ('cosine_distance_v1', 'function_mask_v1', 4),
           ('function_word_js_v1', 'lexical_tokens', None)}
ARMS = {'full', 'hash75', 'hash50', 'middle50'}


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def safe_child(root, relative):
    relative = Path(relative)
    if relative.is_absolute():
        raise ValueError('Only frozen relative input paths are allowed')
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError('A batch reference leaves its registered input root')
    return candidate


def validate_batches(prepared, index):
    """Enforce the complete fixed36-way stratum/method/arm batch design."""
    if len(index) != 360:
        raise ValueError('Exactly360 registered batches are required')
    batch_ids = [item.get('batch_id') for item in index]
    if (any(not isinstance(name, str) or not 1 <= len(name) <= 128
            or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in name) for name in batch_ids)
            or len(set(batch_ids)) != 360):
        raise ValueError('Every output batch ID must be unique, nonempty and safe before execution')
    identities, strata, blocks = set(), set(), {}
    for item in index:
        method = (item['method_id'], item['view'], item['n'])
        if method not in METHODS or item['arm'] not in ARMS:
            raise ValueError('Unregistered method or omission arm')
        key = item['stratum_id'], item['block_id'], item['arm'], method
        if key in identities:
            raise ValueError('Repeated method/arm/block batch')
        identities.add(key)
        strata.add(item['stratum_id'])
        if item['block_id'] in blocks and blocks[item['block_id']] != item['stratum_id']:
            raise ValueError('One account block cannot belong to multiple strata')
        blocks[item['block_id']] = item['stratum_id']
        dataset_path = safe_child(prepared, item['dataset'])
        if sha(dataset_path) != item['dataset_sha256']:
            raise ValueError('Frozen batch dataset changed')
        dataset = json.loads(dataset_path.read_bytes())
        if (dataset['format'] != 'paired_text' or len(dataset['texts']) != 8
                or dataset['dataset_id'] != item['block_id'] + '/' + item['arm'] + '/' + item['view']
                or len(dataset['pairs']) != 16 or {p['split'] for p in dataset['pairs']} != {'evaluation'}
                or dataset['protocol']['frozen_threshold'] is not None
                or dataset['protocol']['distance'] != {'method_id': method[0], 'view': method[1], 'n': method[2]}
                or dataset['protocol']['registered_before_evaluation'] is not True):
            raise ValueError('Dataset differs from the fixed evaluation-only comparison contract')
        expected = item['input_hashes']
        referenced = {str(dataset_path.relative_to(prepared))}
        for unit in dataset['texts']:
            for field in ('input', 'manifest'):
                path = safe_child(dataset_path.parent, unit[field])
                if not path.is_relative_to(prepared.resolve()):
                    raise ValueError('Unregistered source outside prepared inputs')
                referenced.add(str(path.relative_to(prepared)))
        if set(expected) != referenced:
            raise ValueError('Every exact dataset/input/manifest must be hash-bound once')
        for name, checksum in expected.items():
            if sha(safe_child(prepared, name)) != checksum:
                raise ValueError('A frozen unit or manifest changed')
    if len(strata) != 3 or len(blocks) != 30 or any(list(blocks.values()).count(s) != 10 for s in strata):
        raise ValueError('Every planned stratum must retain its ten account blocks')
    if len(identities) != 360:
        raise ValueError('Incomplete method/arm crossing')
    return sorted(strata)


def child_wall_budget(elapsed):
    """Reserve five seconds for forced teardown inside the overall run ceiling."""
    return max(0.0, min(300.0, 7200.0 - elapsed - 5.0))


def failure_row(item, code):
    return {k: item[k] for k in ('batch_id', 'stratum_id', 'block_id', 'method_id', 'view', 'n', 'arm')} | {
        'exit_code': 1, 'status': 'execution_driver_failed', 'failure_code': code,
        'wall_seconds': None, 'peak_rss_mib': None, 'output_files': {}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--prepared', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--replay', action='store_true')
    args = parser.parse_args()
    if os.environ.get('AHAS_NETWORK_ISOLATION') != 'linux_seccomp_socket_denial':
        raise RuntimeError('Actual socket-denial offline runner required')
    freeze = json.loads(args.freeze.read_bytes())
    if freeze.get('status') != 'frozen_before_first_style_score' or freeze.get('scoring_authorized') is not True:
        raise ValueError('A completed pre-score registration is required')
    if freeze['execution_limits'] != {'jobs': 2, 'batch_wall_seconds': 300,
                                      'run_wall_seconds': 7200, 'address_space_bytes': 4294967296}:
        raise ValueError('The complete execution must retain its registered operational bounds')
    resource.setrlimit(resource.RLIMIT_AS, (4294967296,) * 2)
    for item in freeze['bound_artifacts']:
        if sha(item['path']) != item['sha256']:
            raise ValueError('A registered protocol, environment, input or check changed')
    if (implementation_identity()[0] != freeze['implementation_fingerprint']
            or digest(AnalysisConfig.from_toml().analytical()) != freeze['analysis_config_sha256']
            or sha(__file__) != freeze['runner_sha256']):
        raise ValueError('Frozen numerical baseline or execution code changed')
    prepared = args.prepared.resolve()
    index_path = prepared / 'batch-index.json'
    if sha(index_path) != freeze['batch_index_sha256']:
        raise ValueError('The complete prepared batch list changed')
    index = json.loads(index_path.read_text())
    strata = validate_batches(prepared, index)
    if freeze['replay_stratum_id'] != strata[0]:
        raise ValueError('Replay must retain the first sorted registered stratum')
    primary = Path(freeze['primary_prepared_directory']).resolve()
    expected_environment = freeze['replay_environment' if args.replay else 'primary_environment']
    if any(os.environ.get(k) != v for k, v in expected_environment.items()):
        raise ValueError('Process environment differs from the registered main/replay settings')
    if (args.replay and prepared == primary) or (not args.replay and prepared != primary):
        raise ValueError('Replay requires relocated equivalent inputs; primary requires the frozen location')
    selected = [r for r in index if not args.replay or r['stratum_id'] == strata[0]]
    args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    (args.out / 'logs').mkdir(mode=0o700)
    start = time.monotonic()

    def execute(item):
        name = item['batch_id']
        if not name or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in name):
            raise ValueError('Batch identifier is not a safe fixed output name')
        budget = child_wall_budget(time.monotonic() - start)
        if budget <= 0:
            return {k: item[k] for k in ('batch_id', 'stratum_id', 'block_id', 'method_id', 'view', 'n', 'arm')} | {
                'exit_code': 124, 'status': 'not_started_run_wall_budget_exhausted',
                'wall_seconds': 0, 'peak_rss_mib': None, 'output_files': {}}
        command = [sys.executable, str(Path(__file__).with_name('run_logged.py')),
                   '--log-prefix', str(args.out / 'logs' / name), '--',
                   '/usr/bin/timeout', '--kill-after=5', f'{budget:.6f}', sys.executable,
                   '-B', '-m', 'account_history_analyzer', 'evaluate', '--suite', 'paired_text',
                   '--dataset', str(safe_child(prepared, item['dataset'])), '--out', str(args.out / name)]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        receipt = json.loads((args.out / 'logs' / (name + '.receipt.json')).read_text())
        output = args.out / name
        row = {k: item[k] for k in ('batch_id', 'stratum_id', 'block_id', 'method_id', 'view', 'n', 'arm')}
        row.update(exit_code=result.returncode, wall_seconds=receipt['wall_seconds'],
                   peak_rss_mib=receipt['child_peak_rss_mib'],
                   input_bytes=sum(safe_child(prepared, p).stat().st_size for p in item['input_hashes']),
                   output_files={p.name: {'bytes': p.stat().st_size, 'sha256': sha(p)}
                                 for p in output.iterdir()} if output.exists() else {},
                   driver_stdout=result.stdout, driver_stderr=result.stderr)
        print(json.dumps({'batch_id': name, 'exit_code': result.returncode}), flush=True)
        return row

    def safe_execute(item):
        try:
            return execute(item)
        except Exception as error:
            row = failure_row(item, type(error).__name__)
            print(json.dumps({'batch_id': item['batch_id'], 'exit_code': 1,
                              'failure_code': row['failure_code']}), flush=True)
            return row

    with ThreadPoolExecutor(max_workers=2) as executor:
        rows = list(executor.map(safe_execute, selected))
    elapsed = time.monotonic() - start
    status = ('run_wall_budget_exhausted' if elapsed > 7200 else
              'completed' if all(r['exit_code'] == 0 for r in rows) else 'failed_batches_preserved')
    report = {'status': status,
              'freeze_sha256': sha(args.freeze), 'replay': args.replay, 'jobs': 2,
              'registered_batches': len(index), 'executed_batches': len(rows),
              'wall_seconds': elapsed, 'runs': rows}
    with (args.out / 'execution-index.json').open('x') as f:
        json.dump(report, f, sort_keys=True, indent=2)
        f.write('\n')
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    sys.exit(main())
