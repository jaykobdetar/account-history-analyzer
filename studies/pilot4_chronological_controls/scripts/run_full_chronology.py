"""Bounded ordinary CLI execution; never changes the frozen analyzer settings.

Inputs and this study adapter must be registered before real execution. Full
artifacts and original writing stay under the private run root.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import resource
from threading import Lock
import signal
import subprocess
import sys
import time

FINGERPRINT = 'bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179'
CONFIG = '8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925'
REFERENCE_ENVIRONMENT = 'CPython-3.12.3;Linux;x86_64;numpy=2.4.2;scipy=1.17.1;ruptures=1.1.10;markdown-it-py=3.0.0;jsonschema=4.26.0'
OPERATIONAL = {'ingest_receipt.json', 'run_receipt.json'}
CASE_ARTIFACT_BYTES = 512 * 1024**2  # The unchanged production artifact envelope.
WORKER_WALL_SECONDS = 630
INSTALLED_ROOT = Path('/tmp/ahas-pilot3-installed')
EXPECTED_LIMITS = {'parallel_cases': 2, 'case_wall_seconds': 600,
                   'process_address_space_bytes': 4294967296, 'dispatch_wall_seconds': 7200,
                   'run_artifact_bytes': 68719476736}


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, sort_keys=True, indent=2, allow_nan=False)
        f.write('\n')


def artifact_inventory(directory):
    return [{'name': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p),
             'canonical': p.name not in OPERATIONAL}
            for p in sorted(Path(directory).iterdir()) if p.is_file()] if Path(directory).is_dir() else []


def extract_primary(results, exit_code):
    """Mirror frozen account_stream availability; preserve native status separately."""
    missing = results is None
    if missing:
        return {'status': 'resource_limit' if exit_code == 4 else 'unavailable',
                'reason_codes': sorted({'no_results_artifact'} |
                    ({'whole_pipeline_incomplete'} if exit_code != 0 else set())),
                'native_change_status': None, 'candidate_intervals': [], 'stream_id': None, 'primary_window_ids':None}
    identity = results['analysis']
    if identity['implementation_fingerprint'] != FINGERPRINT or identity['config_sha256'] != CONFIG:
        raise ValueError('Frozen analysis identity mismatch')
    # Partial failed runs can have no style payload. They remain unavailable.
    style = results.get('modules', {}).get('style', {}).get('payload') or {}
    streams = [s for s in style.get('streams', []) if s['scope_type'] == 'pooled' and
               s['kind'] == 'comment' and s['subreddit'] is None]
    if len(streams) > 1:
        raise ValueError('Ambiguous primary pooled comment stream')
    changes = [c for c in style.get('changes', []) if streams and c['stream_id'] == streams[0]['stream_id']]
    if len(changes) > 1:
        raise ValueError('Ambiguous primary change result')
    change = changes[0] if changes else None
    reasons = []
    if exit_code != 0:
        status = 'resource_limit' if exit_code == 4 else 'unavailable'
        reasons.append('whole_pipeline_incomplete')
    elif change is None:
        status = 'abstained'
        reasons.append('requested_scope_not_selected_or_eligible')
    elif change['status'] not in {'ok', 'no_measurable_variation'}:
        status = 'abstained'
        reasons.extend(change['reason_codes'] + [change['status']])
    else:
        status = 'ok'
    intervals = []
    for boundary in change.get('boundaries', []) if change else []:
        left, right = boundary['record_interval']
        if type(left) is not int or type(right) is not int or not 0 <= left < right:
            raise ValueError('Invalid original-record boundary interval')
        intervals.append([left+1, right])
    if change and change['status'] == 'no_measurable_variation' and intervals:
        raise ValueError('Constant primary series cannot report candidates')
    return {'status': status, 'reason_codes': sorted(set(reasons)),
            'native_change_status': change['status'] if change else None,
            'candidate_intervals': intervals,
            'stream_id': streams[0]['stream_id'] if streams else None,
            'primary_window_ids':streams[0].get('window_ids') if streams else None}


def baseline_identity(environment):
    """Probe the actual fresh-process import under the registered run environment."""
    probe = """
import importlib.metadata as m, json
from pathlib import Path
import account_history_analyzer as a
from account_history_analyzer.pipeline import implementation_identity
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import digest
fp, env, resources = implementation_identity()
dist = m.distribution('account-history-analyzer')
print(json.dumps({'implementation_fingerprint':fp,
 'config_sha256':digest(AnalysisConfig.from_mapping().analytical()),
 'package_file':str(Path(a.__file__).resolve()), 'module_version':a.__version__,
 'distribution_version':dist.version, 'distribution_path':str(dist._path.resolve()),
 'direct_url':json.loads(dist.read_text('direct_url.json') or 'null'),
 'reference_environment':env, 'resource_hashes':resources}, default=dict))
"""
    result = subprocess.run([sys.executable, '-B', '-c', probe],
                            env={**os.environ, **environment}, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError('Actual installed baseline probe failed')
    identity = json.loads(result.stdout)
    if (identity['implementation_fingerprint'] != FINGERPRINT or identity['config_sha256'] != CONFIG or
        identity['reference_environment'] != REFERENCE_ENVIRONMENT or
        identity['module_version'] != '1.0.4' or identity['distribution_version'] != '1.0.4' or
        Path(identity['package_file']) != INSTALLED_ROOT/'account_history_analyzer/__init__.py' or
        Path(identity['distribution_path']).parent != INSTALLED_ROOT or
        (identity.get('direct_url') or {}).get('dir_info', {}).get('editable', False)):
        raise ValueError('Actual installed baseline identity mismatch')
    return identity


def checked_cases(index, replay_block_id, replay):
    """Every registered block must contain precisely its sixteen factorial rows."""
    from chronology_math import factorial_cases
    cases = index['cases']
    if not cases or len(cases) > 96 or len(cases) % 16:
        raise ValueError('Expected one to six complete sixteen-case blocks')
    identifiers = [c['case_id'] for c in cases]
    if len(identifiers) != len(set(identifiers)) or any(
            not isinstance(i, str) or Path(i).name != i or i in {'.', '..'} or '\\' in i
            for i in identifiers):
        raise ValueError('Unsafe or duplicate case identifier')
    blocks = list(dict.fromkeys(c['block_id'] for c in cases))
    for block in blocks:
        expected = {r['case_id']:r for r in factorial_cases(block)}
        actual = [c for c in cases if c['block_id'] == block]
        if len(actual) != 16 or set(expected) != {c['case_id'] for c in actual}:
            raise ValueError('Incomplete factorial block')
        if any(any(c.get(key) != value for key,value in expected[c['case_id']].items()) for c in actual):
            raise ValueError('Registered factorial case identity mismatch')
        if len({c['stratum_id'] for c in actual}) != 1:
            raise ValueError('Block assigned to multiple strata')
    if replay_block_id != blocks[0]:
        raise ValueError('Replay must use the first registered complete block')
    return [c for c in cases if c['block_id'] == replay_block_id] if replay else cases


def kill_group(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def process_start_ticks(pid):
    # Linux /proc start-time protects the outer cleanup from PID reuse.
    try:
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
    except FileNotFoundError:
        return None


def stop_worker(process, case_dir):
    launch = Path(case_dir)/'child-process.json'
    if launch.exists():
        try:
            child = json.loads(launch.read_bytes())
            if child['start_ticks'] is not None and process_start_ticks(child['pid']) == child['start_ticks']:
                kill_group(child['pid'])
        except (ValueError, KeyError, FileNotFoundError):
            pass
    kill_group(process.pid)
    process.wait(timeout=5)


def worker(case, root, limits, environment):
    resource.setrlimit(resource.RLIMIT_AS, (limits['process_address_space_bytes'],)*2)
    case_dir = Path(root) / case['case_id']
    case_dir.mkdir(mode=0o700)
    argv = [sys.executable, '-B', '-m', 'account_history_analyzer', 'analyze',
            '--input', case['input'], '--manifest', case['manifest'], '--out', str(case_dir/'analysis')]
    start = time.monotonic()
    started = datetime.now(timezone.utc).isoformat()
    timed_out = False
    def interrupted(*_):
        raise TimeoutError('Outer worker interruption')
    signal.signal(signal.SIGTERM, interrupted)
    with (case_dir/'stdout.log').open('xb') as stdout, (case_dir/'stderr.log').open('xb') as stderr:
        process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, env={**os.environ, **environment},
                                   start_new_session=True)
        try:
            write(case_dir/'child-process.json', {'pid':process.pid, 'start_ticks':process_start_ticks(process.pid)})
            exit_code = process.wait(timeout=limits['case_wall_seconds'])
        except (subprocess.TimeoutExpired, TimeoutError):
            timed_out = True
            kill_group(process.pid)
            exit_code = process.wait()
        finally:
            # Cleanup any descendants left after the analyzer exits as well.
            kill_group(process.pid)
    artifacts = artifact_inventory(case_dir/'analysis')
    artifact_limit = sum(a['bytes'] for a in artifacts) > CASE_ARTIFACT_BYTES
    analyzer_exit_code = exit_code
    if timed_out or artifact_limit:
        exit_code = 4
    receipt = {'case_id': case['case_id'], 'argv': argv, 'started_utc': started,
               'finished_utc': datetime.now(timezone.utc).isoformat(),
               'wall_seconds': time.monotonic()-start, 'exit_code': exit_code,
               'external_wall_limit_reached': timed_out,
               'external_artifact_limit_reached': artifact_limit, 'analyzer_exit_code': analyzer_exit_code,
               'child_peak_rss_mib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss/1024,
               'environment': environment, 'artifacts': artifacts}
    write(case_dir/'receipt.json', receipt)


def run(registration, prepared_index, root, replay=False):
    if os.environ.get('AHAS_NETWORK_ISOLATION') != 'linux_seccomp_socket_denial':
        raise RuntimeError('Socket-denial offline wrapper required')
    plan = json.loads(Path(registration).read_bytes())
    if plan['phase'] != 'frozen_before_chronological_execution':
        raise ValueError('Final pre-score registration required')
    if sha(prepared_index) != plan['prepared_index_sha256'] or sha(__file__) != plan['runner_sha256']:
        raise ValueError('Registered index or execution adapter changed')
    for artifact in plan['bound_artifacts']:
        if sha(artifact['path']) != artifact['sha256']:
            raise ValueError('Registered input/code/environment changed')
    index = json.loads(Path(prepared_index).read_bytes())
    for artifact in index['bound_files']:
        if sha(artifact['path']) != artifact['sha256']:
            raise ValueError('Prepared input differs from registration')
    bound = [str(Path(a['path']).resolve()) for a in index['bound_files']]
    required = {str(Path(c[field]).resolve()) for c in index['cases'] for field in ('input','manifest','metadata')}
    if len(bound) != len(set(bound)) or not required.issubset(set(bound)):
        raise ValueError('All distinct prepared input, manifest and metadata files must be bound')
    cases = checked_cases(index, plan['replay_block_id'], replay)
    limits = plan['limits']
    if limits != EXPECTED_LIMITS:
        raise ValueError('Unexpected registered execution ceiling')
    if (len(index['cases'])+16)*CASE_ARTIFACT_BYTES > limits['run_artifact_bytes']:
        raise ValueError('Original plus replay worst-case artifact ceiling exceeded')
    env = plan['replay_environment' if replay else 'execution_environment']
    identity = baseline_identity(env)
    root = Path(root)
    root.mkdir(mode=0o700, exist_ok=False)
    if replay:
        import shutil
        relocated = root/'relocated'
        relocated.mkdir(mode=0o700)
        replacements = []
        for case in cases:
            case = dict(case)
            for field in ('input', 'manifest'):
                target = relocated/(case['case_id']+'.'+field+Path(case[field]).suffix)
                shutil.copyfile(case[field], target)
                if sha(case[field]) != sha(target):
                    raise ValueError('Relocation changed input bytes')
                case[field] = str(target)
            replacements.append(case)
        cases = replacements
    start = time.monotonic()
    write(root/'start-binding.json', {'registration_sha256': sha(registration), 'index_sha256': sha(prepared_index),
          'runner_sha256': sha(__file__), 'started_utc': datetime.now(timezone.utc).isoformat(),
          'case_ids': [c['case_id'] for c in cases], 'replay': replay,
          'actual_baseline_identity': identity, 'outer_worker_wall_seconds':WORKER_WALL_SECONDS,
          'frozen_case_artifact_bytes': CASE_ARTIFACT_BYTES,
          'original_plus_replay_worst_case_artifact_bytes':(len(index['cases'])+16)*CASE_ARTIFACT_BYTES})
    lock = Lock()
    budget = {'completed_bytes':0, 'active_reservations':0, 'limit_reached':False}
    def dispatch(case):
        with lock:
            remaining = limits['dispatch_wall_seconds']-(time.monotonic()-start)
            if remaining <= 0:
                return {'case_id': case['case_id'], 'status': 'not_dispatched_wall_limit'}
            if budget['limit_reached'] or (budget['completed_bytes']+
                    (budget['active_reservations']+1)*CASE_ARTIFACT_BYTES > limits['run_artifact_bytes']):
                return {'case_id': case['case_id'], 'status': 'not_dispatched_artifact_limit'}
            budget['active_reservations'] += 1
        receipt = None
        row = {'case_id': case['case_id'], 'status':'worker_failed'}
        process = None
        try:
            # Every case gets a fresh worker, so peak child RSS belongs to it.
            spec = root/(case['case_id']+'.worker.json')
            write(spec, {'case': case, 'root': str(root), 'limits': limits, 'environment': env})
            with (root/(case['case_id']+'.worker-stdout.log')).open('xb') as stdout, \
                 (root/(case['case_id']+'.worker-stderr.log')).open('xb') as stderr:
                process = subprocess.Popen([sys.executable, '-B', __file__, '--worker', str(spec)],
                    stdout=stdout, stderr=stderr, start_new_session=True)
                try:
                    process.wait(timeout=min(WORKER_WALL_SECONDS, remaining))
                except subprocess.TimeoutExpired:
                    stop_worker(process, root/case['case_id'])
                    row.update(status='worker_wall_limit', exit_code=4)
                else:
                    if process.returncode:
                        stop_worker(process, root/case['case_id'])
                        row['exit_code'] = process.returncode
                    else:
                        receipt = json.loads((root/case['case_id']/'receipt.json').read_bytes())
                        if receipt['case_id'] != case['case_id']:
                            raise ValueError('Worker receipt case mismatch')
                        row = {'case_id': case['case_id'], 'status': 'attempted', 'receipt': receipt}
                        print(json.dumps({k: receipt[k] for k in
                            ('case_id','exit_code','wall_seconds','child_peak_rss_mib')}), flush=True)
        except Exception as error:
            if process is not None and process.poll() is None:
                stop_worker(process, root/case['case_id'])
            row = {'case_id':case['case_id'], 'status':'worker_failed', 'error_type':type(error).__name__}
        finally:
            # Even a failed worker's surviving artifacts count against the cap.
            artifacts = artifact_inventory(root/case['case_id']/'analysis')
            size = sum(a['bytes'] for a in artifacts)
            if receipt is None:
                row['surviving_artifacts'] = artifacts
            with lock:
                budget['active_reservations'] -= 1
                budget['completed_bytes'] += size
                if size > CASE_ARTIFACT_BYTES or budget['completed_bytes'] > limits['run_artifact_bytes']:
                    budget['limit_reached'] = True
                    row['artifact_limit_reached'] = True
        return row
    with ThreadPoolExecutor(max_workers=limits['parallel_cases']) as pool:
        rows = list(pool.map(dispatch, cases))
    # Preserve every attempted, failed and undispatched planned case on failure.
    write(root/'execution.json', {'cases': rows, 'wall_seconds': time.monotonic()-start,
          'artifact_bytes':budget['completed_bytes'], 'artifact_limit_reached':budget['limit_reached'],
          'replay': replay})


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--registration', type=Path)
    p.add_argument('--index', type=Path)
    p.add_argument('--out', type=Path)
    p.add_argument('--replay', action='store_true')
    p.add_argument('--worker', type=Path)
    args = p.parse_args()
    if args.worker:
        worker(**json.loads(args.worker.read_bytes()))
    else:
        run(args.registration, args.index, args.out, args.replay)
