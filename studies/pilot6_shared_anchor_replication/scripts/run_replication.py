"""Bounded Pilot6 orchestration of the unchanged Pilot5 four-history adapter.

All source-containing inputs and native artifacts stay in the private output tree.
No analyzer configuration, previous study code or saved output is modified.
"""
from __future__ import annotations

import argparse
from collections import Counter
import ctypes
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
P5 = ROOT / 'studies/pilot5_shared_anchor/scripts/run_diagnostic.py'
OFFLINE = ROOT / 'scripts/offline_exec.py'
SPEC = importlib.util.spec_from_file_location('pilot6_frozen_pilot5', P5)
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)
sha, write, read, require = adapter.sha, adapter.write, adapter.read, adapter.require
LIMITS = {'global_wall_seconds': 14400, 'global_artifact_bytes': 12 * 1024**3,
          'max_pairs': 10, 'pair_reserved_artifact_bytes': 8 * 512 * 1024**2}
PHASES = ('main', 'score', 'replay', 'replay-check')


def tree_bytes(root):
    """Count all private artifacts, including logs/relocated inputs, conservatively."""
    total = 0
    for path in Path(root).rglob('*'):
        try:
            if path.is_file():
                total += path.stat().st_size
        except FileNotFoundError:  # a still-running writer may rename an artifact
            pass
    return total


def checked_registration(path):
    plan = read(path)
    require(plan['phase'] == 'frozen_before_pilot6_replication', 'Pilot6 execution registration required')
    require(plan['limits'] == LIMITS, 'Global execution limits differ from the registered protocol')
    require(plan['runner_sha256'] == sha(__file__), 'Pilot6 runner changed')
    cohort_path = Path(plan['cohort_index']).resolve()
    require(plan['cohort_sha256'] == sha(cohort_path), 'Frozen cohort changed')
    bindings = {}
    for row in plan['bound_artifacts']:
        target = str(Path(row['path']).resolve())
        require(target not in bindings and sha(target) == row['sha256'], 'Duplicate or changed global binding')
        bindings[target] = row['sha256']
    needed = {str(p.resolve()) for p in (Path(__file__), P5, OFFLINE, cohort_path, *adapter.HELPERS)}
    cohort = read(cohort_path)
    require(cohort['target_pairs'] == 10 and isinstance(cohort['pairs'], list)
            and 0 <= len(cohort['pairs']) <= LIMITS['max_pairs'], 'Invalid actual or target pair count')
    excluded = cohort['excluded_account_keys']
    require(isinstance(excluded, list) and len(excluded) == len(set(excluded)) == 119
            and all(isinstance(k, str) and k and k == k.casefold() for k in excluded),
            'The frozen 119-account exclusion union is required')
    seen_pairs, seen_accounts, seen_cases, seen_files, seen_records = set(), set(), set(), set(), set()
    indices = {}
    for pair in cohort['pairs']:
        pid = pair['pair_id']
        require(isinstance(pid, str) and pid.startswith('pilot6-pair-') and Path(pid).name == pid
                and '\\' not in pid and pid not in seen_pairs, 'Unsafe or duplicate pair identifier')
        seen_pairs.add(pid)
        accounts = pair['source_account_keys']
        require(isinstance(accounts, list) and len(accounts) == len(set(accounts)) == 2
                and all(isinstance(a, str) and a and a == a.casefold() for a in accounts),
                'Each pair must bind two distinct canonical source accounts')
        require(not set(accounts) & (seen_accounts | set(excluded)), 'Repeated or excluded source account')
        seen_accounts.update(accounts)
        needed.update(str(Path(pair[f]).resolve()) for f in ('index', 'registration'))
        _, index = adapter.checked_registration(pair['registration'], pair['index'])
        require(all(c['block_id'] == pid for c in index['cases']), 'Pair ID must equal the four-case block ID')
        files = {str(Path(c[f]).resolve()) for c in index['cases'] for f in ('input', 'manifest', 'metadata')}
        case_ids = {c['case_id'] for c in index['cases']}
        records = {r['record_id'] for c in index['cases'] for r in read(c['metadata'])['records']}
        require(not (files & seen_files or case_ids & seen_cases or records & seen_records),
                'Different pairs must not share case IDs, files or original record IDs')
        seen_files.update(files); seen_cases.update(case_ids); seen_records.update(records)
        indices[pid] = index
    require(needed.issubset(bindings), 'Missing global cohort, index, registration or unchanged helper binding')
    return plan, cohort, indices


def process_info(pid):
    """Linux PID identity: parent, start ticks, process group and state."""
    try:
        raw = Path(f'/proc/{pid}/stat').read_text()
        fields = raw[raw.rfind(')') + 2:].split()
        return {'pid': int(pid), 'parent': int(fields[1]), 'start': int(fields[19]),
                'group': int(fields[2]), 'state': fields[0]}
    except (OSError, ValueError, IndexError):
        return None


def descendants(pid):
    nodes = {}
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            info = process_info(int(path.name))
            if info is not None:
                nodes[info['pid']] = info
    found, frontier = {}, {pid}
    while frontier:
        following = {p for p, row in nodes.items() if row['parent'] in frontier and p not in found and p != pid}
        found.update((p, nodes[p]) for p in following)
        frontier = following
    return found


def stop_descendants(process, tracked):
    """Stop detached P5 workers and analyzer sessions as well as their parent.

    A remembered PID is signalled only while its start ticks still match. Tracking
    during execution also retains children reparented after an outer failure.
    """
    tracked.update(descendants(process.pid))
    parent = process_info(process.pid)
    if parent:
        tracked[parent['pid']] = parent
    # Freeze parents first so they cannot dispatch another detached worker while
    # the descendant snapshot is collected. SIGKILL then prevents orphan writers.
    for row in sorted(tracked.values(), key=lambda r: r['pid'] != process.pid):
        now = process_info(row['pid'])
        if now and now['start'] == row['start']:
            try:
                os.kill(row['pid'], signal.SIGSTOP)
            except ProcessLookupError:
                pass
    tracked.update(descendants(process.pid))
    killed = 0
    for row in reversed(list(tracked.values())):
        now = process_info(row['pid'])
        if not now or now['start'] != row['start']:
            continue
        try:
            if now['group'] == row['pid'] and now['group'] != os.getpgrp():
                os.killpg(now['group'], signal.SIGKILL)
            else:
                os.kill(row['pid'], signal.SIGKILL)
            killed += 1
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        raise RuntimeError('Child cleanup did not terminate the dispatched wrapper')
    deadline = time.monotonic()+5
    while True:
        live = []
        for pid, row in tracked.items():
            now = process_info(pid)
            if not now or now['start'] != row['start']:
                continue
            if now['state'] != 'Z':
                live.append(pid)
            elif now['parent'] == os.getpid():
                try:
                    os.waitpid(pid, os.WNOHANG)
                except ChildProcessError:
                    pass
        if not live:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('A detached child did not finish after termination')
        time.sleep(.01)
    return killed


def subreaper(enable=None):
    """Adopt orphaned detached workers so a fast parent failure cannot hide them."""
    libc = ctypes.CDLL(None, use_errno=True)
    current = ctypes.c_int()
    if libc.prctl(37, ctypes.byref(current), 0, 0, 0) != 0:  # PR_GET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), 'Unable to inspect child subreaper state')
    if enable is not None and libc.prctl(36, int(enable), 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'Unable to protect detached child cleanup')
    return current.value


def launch_phase(argv, log_root, output_root, deadline, artifact_limit):
    """A global watchdog surrounds unchanged per-case and per-pair guards."""
    started = time.monotonic()
    remaining = deadline - started
    if remaining <= 0:
        return {'status': 'not_dispatched_global_wall_limit', 'exit_code': None, 'wall_seconds': 0.0}
    if tree_bytes(output_root) >= artifact_limit:
        return {'status': 'not_dispatched_global_artifact_limit', 'exit_code': None, 'wall_seconds': 0.0}
    tracked = {}
    existing = {(p, r['start']) for p, r in descendants(os.getpid()).items()}
    with Path(str(log_root) + '.stdout.log').open('xb') as stdout, Path(str(log_root) + '.stderr.log').open('xb') as stderr:
        prior_subreaper = subreaper(True)
        try:
            process = subprocess.Popen(argv, stdout=stdout, stderr=stderr, start_new_session=True)
        except BaseException:
            subreaper(prior_subreaper)
            raise
        reason = None
        killed = 0
        try:
            while True:
                tracked.update(descendants(process.pid))
                tracked.update((p, r) for p, r in descendants(os.getpid()).items()
                               if (p, r['start']) not in existing and p != process.pid)
                code = process.poll()
                if time.monotonic() >= deadline:
                    reason = 'global_wall_limit'
                elif tree_bytes(output_root) >= artifact_limit:
                    reason = 'global_artifact_limit'
                if reason is not None or code is not None:
                    break
                time.sleep(min(0.1, max(0, deadline-time.monotonic())))
            # Even an unexpectedly failed outer wrapper can leave detached workers.
            if reason is not None or code != 0:
                killed = stop_descendants(process, tracked)
            else:
                live = [row for row in tracked.values() if (now := process_info(row['pid']))
                        and now['start'] == row['start'] and now['state'] != 'Z']
                if live:
                    reason = 'unexpected_surviving_descendants'
                    killed = stop_descendants(process, tracked)
        except BaseException:
            stop_descendants(process, tracked)
            raise
        finally:
            for pid, row in tracked.items():
                now = process_info(pid)
                if now and now['start'] == row['start'] and now['parent'] == os.getpid():
                    try:
                        os.waitpid(pid, os.WNOHANG)
                    except ChildProcessError:
                        pass
            subreaper(prior_subreaper)
    return {'status': reason or ('completed' if process.returncode == 0 else 'failed'),
            'exit_code': process.returncode, 'wall_seconds': time.monotonic()-started,
            'terminated_process_count': killed, 'artifact_bytes_after_phase': tree_bytes(output_root)}


def command(pair, directory, phase):
    args = [sys.executable, '-B', str(OFFLINE), sys.executable, '-B', str(P5)]
    common = ['--index', pair['index']]
    if phase in ('main', 'replay'):
        args += ['run', *common, '--registration', pair['registration'], '--out', str(directory/phase)]
        if phase == 'replay':
            args += ['--replay', '--original', str(directory/'main')]
    elif phase == 'score':
        args += ['score', *common, '--run', str(directory/'main'), '--out', str(directory/'scores')]
    elif phase == 'replay-check':
        args += ['replay-check', *common, '--run', str(directory/'main'), '--replay-root', str(directory/'replay'),
                 '--out', str(directory/'replay-check.json')]
    else:
        raise ValueError('Unknown frozen adapter phase')
    return args


def operation_receipt(path, case_id):
    """Only well-formed operational fields enter an unverified fallback row."""
    try:
        value = read(path)
        keys = ('exit_code', 'wall_seconds', 'child_peak_rss_mib',
                'external_wall_limit_reached', 'external_artifact_limit_reached')
        if not isinstance(value, dict) or value.get('case_id') != case_id or not all(k in value for k in keys):
            return None
        return value
    except (OSError, ValueError, TypeError):
        return None


def unavailable_case(case, reason, directory):
    metadata = read(case['metadata'])['records']
    scoring = adapter.score_case(candidate_intervals=None, status='unavailable', reason_codes=[reason],
        truth_k=case['truth_k'], control_junction_k=case['control_junction_k'],
        windows=adapter.reconstruct_windows(metadata), record_timestamps=[r['created_utc'] for r in metadata])
    receipt_path = directory/'main'/case['case_id']/'receipt.json'
    receipt = operation_receipt(receipt_path, case['case_id'])
    return {**{k: case[k] for k in adapter.DESCRIPTORS}, 'score': scoring,
        'primary_window_check': 'metadata_reconstruction_only_unverified_execution', 'native_change_status': None,
        'record_count': len(metadata), 'retained_words': sum(r['retained_words'] for r in metadata),
        'full_pipeline_statuses': None, 'resources': {k: receipt[k] for k in ('exit_code', 'wall_seconds',
             'child_peak_rss_mib', 'external_wall_limit_reached', 'external_artifact_limit_reached')} if receipt else None,
        'effective_exit_code': None, 'dispatch_status': reason,
        'external_wrapper_artifact_limit_reached': 'artifact_limit' in reason,
        'artifact_bytes': tree_bytes(directory/'main'/case['case_id']/'analysis'), 'results_sha256': None}


def attempts_by_case(directory, case_ids):
    path = directory/'execution.json'
    if path.exists():
        try:
            doc = read(path)
            rows = doc['cases']
            valid = [r.get('case_id') for r in rows] == case_ids
            valid = valid and all(isinstance(r.get('status'), str) and (r.get('receipt') is None or
                   r['receipt'] == operation_receipt(directory/r['case_id']/'receipt.json', r['case_id'])) for r in rows)
            if valid:
                return {r['case_id']: r for r in rows}
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            pass
    # Abrupt termination may preclude a complete execution manifest. Receipts
    # preserve operations, but never establish verified scientific results here.
    result = {}
    for cid in case_ids:
        receipt_path = directory/cid/'receipt.json'
        receipt = operation_receipt(receipt_path, cid)
        if receipt_path.exists() or (directory/(cid+'.worker.json')).exists():
            result[cid] = {'case_id': cid, 'status': 'incomplete_execution_manifest', 'receipt': receipt}
    return result


def collect_pair(pair, index, directory, phases, reason):
    scored = directory/'scores/cases.json'
    verified_score = phases.get('score', {}).get('status') == 'completed'
    rows = read(scored) if verified_score else [unavailable_case(c, reason, directory) for c in index['cases']]
    require([r['case_id'] for r in rows] == [c['case_id'] for c in index['cases']], 'Scored cases lost or reordered')
    case_ids = [c['case_id'] for c in index['cases']]
    main_attempts = attempts_by_case(directory/'main', case_ids)
    replay_attempts = attempts_by_case(directory/'replay', case_ids)
    checked = read(directory/'replay-check.json') if phases.get('replay-check', {}).get('status') == 'completed' else None
    replay_rows = {r['case_id']: r for r in checked['cases']} if checked else {}
    for row in rows:
        k = row['score']['grid_resolution']['reference_split_k']
        intervals = row['score']['candidate_intervals']
        row['all_candidate_interval_errors_records'] = [max(i['split_interval'][0]-k, k-i['split_interval'][1], 0)
                                                       for i in intervals] if intervals is not None else None
        row['pair_id'] = pair['pair_id']
        for label, attempts in (('main_operation', main_attempts), ('replay_operation', replay_attempts)):
            attempt = attempts.get(row['case_id'])
            receipt = attempt.get('receipt') if attempt else None
            row[label] = {'dispatched': bool(attempt and attempt['status'] not in
                 ('not_dispatched_wall_limit', 'not_dispatched_artifact_limit')),
                'status': attempt['status'] if attempt else 'not_dispatched_or_unrecorded',
                'exit_code': attempt.get('effective_exit_code', receipt.get('exit_code') if receipt else None) if attempt else None,
                'wall_seconds': receipt.get('wall_seconds') if receipt else None,
                'child_peak_rss_mib': receipt.get('child_peak_rss_mib') if receipt else None,
                'artifact_bytes': tree_bytes(directory/('main' if label == 'main_operation' else 'replay')/row['case_id']/'analysis')}
        row['replay_verification'] = replay_rows.get(row['case_id'], {'all_files_byte_identical': None,
            'canonical_file_count': None, 'reason': reason if checked is None else 'missing_case'})
    return {'pair_id': pair['pair_id'], 'phases': phases, 'status': reason,
        'cases': rows, 'artifact_bytes': tree_bytes(directory),
        'replay_all_passed': checked['all_passed'] if checked else None,
        'inherited_adapter_summary': {'study_label': 'pilot5_shared_anchor_exploratory',
            'interpretation': 'The unchanged per-pair adapter retains its original study label. These are new Pilot6 pairs; the label is not a Pilot5 replication count.',
            'sha256': sha(directory/'scores/summary.json') if verified_score else None}}


def run(registration, output):
    plan, cohort, indices = checked_registration(registration)
    out = Path(output)
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    write(out/'start-binding.json', {'registration_sha256': sha(registration), 'cohort_sha256': plan['cohort_sha256'],
        'runner_sha256': sha(__file__), 'unchanged_pilot5_runner_sha256': sha(P5), 'limits': LIMITS,
        'started_utc': datetime.now(timezone.utc).isoformat(), 'pair_ids': [p['pair_id'] for p in cohort['pairs']],
        'case_ids': [c['case_id'] for p in cohort['pairs'] for c in indices[p['pair_id']]['cases']]})
    first_dispatch, stop_reason = None, None
    pairs = []
    for pair in cohort['pairs']:
        directory = out/pair['pair_id']
        directory.mkdir(mode=0o700)
        phases = {}
        reason = stop_reason
        if reason is None and tree_bytes(out) + LIMITS['pair_reserved_artifact_bytes'] > LIMITS['global_artifact_bytes']:
            reason = stop_reason = 'not_dispatched_global_artifact_reservation'
        if reason is None and first_dispatch is not None and time.monotonic()-first_dispatch >= LIMITS['global_wall_seconds']:
            reason = stop_reason = 'not_dispatched_global_wall_limit'
        if reason is None:
            if first_dispatch is None:
                first_dispatch = time.monotonic()
                write(out/'first-dispatch.json', {'started_utc': datetime.now(timezone.utc).isoformat(),
                    'global_wall_seconds': LIMITS['global_wall_seconds']})
            for phase in PHASES:
                # A score failure still leaves the registered replay scientifically
                # necessary if the main execution manifest is complete and time remains.
                if phase == 'replay' and phases['main']['status'] != 'completed':
                    phases[phase] = {'status': 'not_dispatched_main_incomplete', 'exit_code': None, 'wall_seconds': 0.0}
                    continue
                if phase == 'replay-check' and phases['replay']['status'] != 'completed':
                    phases[phase] = {'status': 'not_dispatched_replay_incomplete', 'exit_code': None, 'wall_seconds': 0.0}
                    continue
                if stop_reason is not None:
                    phases[phase] = {'status': 'not_dispatched_' + stop_reason, 'exit_code': None, 'wall_seconds': 0.0}
                    continue
                try:
                    result = launch_phase(command(pair, directory, phase), directory/phase, out,
                         first_dispatch + LIMITS['global_wall_seconds'], LIMITS['global_artifact_bytes'])
                except Exception as error:
                    result = {'status': 'adapter_exception', 'error_type': type(error).__name__, 'exit_code': None, 'wall_seconds': None}
                    # An unexpected watchdog/cleanup failure cannot license a
                    # second group of workers while earlier state is uncertain.
                    stop_reason = 'orchestrator_exception'
                phases[phase] = result
                if 'global_wall_limit' in result['status'] or 'global_artifact_limit' in result['status']:
                    stop_reason = result['status']
            reason = stop_reason or ('completed' if all(p['status'] == 'completed' for p in phases.values()) else 'adapter_phase_failed')
        else:
            phases = {p: {'status': reason, 'exit_code': None, 'wall_seconds': 0.0} for p in PHASES}
        try:
            result = collect_pair(pair, indices[pair['pair_id']], directory, phases, reason)
        except Exception as error:
            # Preserve every denominator even if malformed saved adapter output
            # prevents verification; no result from that pair is silently trusted.
            phases['collection'] = {'status': 'saved_output_verification_failed', 'error_type': type(error).__name__}
            safe_phases = {k: v for k, v in phases.items() if k not in ('score', 'replay-check')}
            result = collect_pair(pair, indices[pair['pair_id']], directory, safe_phases, 'saved_output_verification_failed')
            result['phases'] = phases
        write(directory/'pair-summary.json', result)
        pairs.append(result)
    cases = [r for pair in pairs for r in pair['cases']]
    summary = {'study': 'pilot6_shared_anchor_replication', 'target_new_pairs': 10,
        'registered_new_pairs': len(pairs), 'prescore_pair_shortfall': 10-len(pairs),
        'planned_main_histories': len(cases), 'planned_replay_histories': len(cases),
        'main_dispatched_histories': sum(r['main_operation']['dispatched'] for r in cases),
        'replay_dispatched_histories': sum(r['replay_operation']['dispatched'] for r in cases),
        'main_executed_primary_histories': sum(r['score']['executed'] for r in cases),
        'main_unavailable_primary_histories': sum(not r['score']['executed'] for r in cases),
        'pairs_with_four_executed_primary_histories': sum(all(r['score']['executed'] for r in p['cases']) for p in pairs),
        'pairs_with_four_verified_replays': sum(p['replay_all_passed'] is True for p in pairs),
        'stop_reason': stop_reason, 'global_wall_seconds_since_first_dispatch': time.monotonic()-first_dispatch if first_dispatch is not None else None,
        'artifact_bytes_before_final_reports': tree_bytes(out), 'condition_counts': dict(Counter(r['condition'] for r in cases)),
        'registration_sha256': sha(registration), 'cohort_sha256': plan['cohort_sha256'],
        'pair_statuses': [{'pair_id': p['pair_id'], 'status': p['status'], 'replay_all_passed': p['replay_all_passed']} for p in pairs],
        'counting_note': 'Each new disjoint source-account pair is one replication unit. Four main histories share its anchor; replays add no new units. Prior Pilot5 inputs/results are excluded.',
        'intervals_and_missingness': 'Original per-case scores are retained; all interval distances use the unsnapped junction. Unavailable candidate/localization outcomes stay null, with metadata grid resolution labeled separately.'}
    write(out/'cases.json', cases)
    write(out/'summary.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration', required=True)
    parser.add_argument('--out', required=True, help='New private output directory')
    args = parser.parse_args()
    run(args.registration, args.out)
