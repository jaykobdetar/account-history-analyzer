"""Pilot5 four-history shared-anchor wrapper around unchanged Pilot4 adapters.

No analyzer configuration is supplied or modified. Selection and registration
must precede execution. Four histories share one anchor and are never treated
as four independent sampling units. Source writing remains in private outputs.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from threading import Lock
import time

P4 = Path(__file__).resolve().parents[2] / 'pilot4_chronological_controls' / 'scripts'
sys.path.insert(0, str(P4))
import run_full_chronology as frozen
from chronology_math import CONDITIONS, legal_grid, reconstruct_windows, score_case
from score_saved_chronology import checked_execution, checked_windows, metadata_ids

sha, write = frozen.sha, frozen.write
LIMITS = {'parallel_cases': 2, 'case_wall_seconds': 600,
          'process_address_space_bytes': 4294967296, 'dispatch_wall_seconds': 3600,
          'run_artifact_bytes': 8589934592}
ORIGINAL_ENV = {'PYTHONPATH': '/tmp/ahas-pilot3-installed', 'PYTHONHASHSEED': '0', 'TZ': 'UTC'}
REPLAY_ENV = {**ORIGINAL_ENV, 'PYTHONHASHSEED': '73129', 'TZ': 'Pacific/Honolulu'}
HELPERS = tuple(P4 / name for name in ('run_full_chronology.py', 'chronology_math.py',
                                     'score_saved_chronology.py', 'matched_condition_changes.py'))
DESCRIPTORS = ('case_id', 'block_id', 'stratum_id', 'anchor_id', 'condition',
               'source_switch', 'community_change', 'left_cell_id', 'right_cell_id')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_bytes())


def tree_bytes(root):
    return sum(path.stat().st_size for path in Path(root).rglob('*') if path.is_file()) if Path(root).exists() else 0


def distinct_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON object key')
        result[key] = value
    return result


def mask_alias(raw):
    """Retain exact input bytes, replacing only the top-level account_id value."""
    text = raw.decode('utf-8')
    decoder = json.JSONDecoder(object_pairs_hook=distinct_object)
    record = decoder.decode(text)
    require(isinstance(record, dict), 'A record must be a JSON object')
    pos = len(text) - len(text.lstrip())
    require(text[pos] == '{', 'A record must be an object')
    pos += 1
    span = None
    while True:
        while text[pos].isspace():
            pos += 1
        if text[pos] == '}':
            break
        key, end = decoder.raw_decode(text, pos)
        pos = end
        while text[pos].isspace():
            pos += 1
        require(text[pos] == ':', 'Invalid record field')
        pos += 1
        while text[pos].isspace():
            pos += 1
        value_start = pos
        _, pos = decoder.raw_decode(text, pos)
        if key == 'account_id':
            span = (value_start, pos)
        while text[pos].isspace():
            pos += 1
        if text[pos] == '}':
            break
        require(text[pos] == ',', 'Invalid object separator')
        pos += 1
    require(span is not None, 'Every record must have a uniform account alias')
    return record, (text[:span[0]] + '"<uniform-case-alias>"' + text[span[1]:]).encode('utf-8')


def checked_index(path):
    index = read(path)
    cases = index['cases']
    require(len(cases) == 4, 'Exactly four shared-anchor histories are required')
    require([c['condition'] for c in cases] == list(CONDITIONS), 'All four conditions must retain their fixed order')
    for field in ('case_id',):
        identifiers = [c[field] for c in cases]
        require(len(set(identifiers)) == 4 and all(isinstance(i, str) and i and Path(i).name == i
                and i not in {'.', '..'} and '\\' not in i for i in identifiers), 'Unsafe or duplicate case identifier')
    require(all(len({c[field] for c in cases}) == 1 for field in ('block_id', 'stratum_id', 'anchor_id', 'left_cell_id')),
            'All histories must share one block, stratum and anchor')
    require(cases[0]['anchor_id'] == 'AX', 'The registered single anchor is AX')
    bound = {}
    for artifact in index['bound_files']:
        target = str(Path(artifact['path']).resolve())
        require(target not in bound, 'Duplicate prepared file binding')
        require(sha(target) == artifact['sha256'], 'Prepared file hash mismatch')
        bound[target] = artifact['sha256']
    inputs = [str(Path(c[field]).resolve()) for c in cases for field in ('input', 'manifest', 'metadata')]
    require(len(set(inputs)) == 12 and set(inputs).issubset(bound), 'All twelve distinct case files must be hash-bound')
    common_anchor = common_metadata = None
    sample_sets = []
    for case in cases:
        block, condition = case['block_id'], case['condition']
        switch, changed = condition.startswith('switch_'), condition.endswith('changed_community')
        require(type(case['source_switch']) is bool and case['source_switch'] == switch and
                type(case['community_change']) is bool and case['community_change'] == changed,
                'Condition flags differ from the fixed design')
        require(case['case_id'] == f'{block}:AX:{condition}' and case['left_cell_id'] == f'{block}:A:X:early'
                and case['right_cell_id'] == f'{block}:{"B" if switch else "A"}:{"Y" if changed else "X"}:late',
                'Shared-anchor descriptor identity mismatch')
        junction = case['truth_k'] if switch else case['control_junction_k']
        require(type(junction) is int and junction > 0 and
                (case['control_junction_k'] if switch else case['truth_k']) is None,
                'Only switches have truth splits; controls have diagnostic junctions')
        require(all(Path(case[field]).stat().st_size <= 64 * 1024**2 for field in ('input', 'manifest', 'metadata')),
                'Prepared case file exceeds the fixed input bound')
        raw_lines = Path(case['input']).read_bytes().splitlines(keepends=True)
        require(bool(raw_lines) and all(line.strip() for line in raw_lines), 'Input records must be nonempty JSONL')
        parsed = [mask_alias(line) for line in raw_lines]
        records, masked = [r for r, _ in parsed], [b for _, b in parsed]
        metadata = read(case['metadata'])['records']
        ids = metadata_ids(metadata)
        require(junction < len(records) and len(records) == len(metadata), 'Junction must divide two nonempty samples')
        require(all(r['account_id'] == case['case_id'] for r in records), 'Input alias must uniformly equal case_id')
        require(read(case['manifest'])['account_id'] == case['case_id'], 'Manifest account alias mismatch')
        require([r['id'] for r in records] == ids, 'Metadata original IDs differ from input')
        require(all(r['created_utc'] == m['created_utc'] and r['kind'] == m.get('kind', 'comment') == 'comment'
                    and type(m['style_eligible']) is bool and m['style_eligible']
                    and type(m['retained_words']) is int and 20 <= m['retained_words'] <= 500
                    for r, m in zip(records, metadata)), 'Input and retained-word metadata differ')
        times = [datetime.fromisoformat(r['created_utc'].replace('Z', '+00:00')) for r in records]
        require(all(t.utcoffset().total_seconds() == 0 for t in times), 'Record timestamps must be UTC')
        require(list(zip(times, ids)) == sorted(zip(times, ids)), 'Input order must preserve canonical timestamps and IDs')
        require(times[junction-1] < times[junction], 'The first late record must follow every anchor record')
        early_communities = {r['subreddit'] for r in records[:junction]}
        late_communities = {r['subreddit'] for r in records[junction:]}
        require(len(early_communities) == len(late_communities) == 1 and
                (early_communities != late_communities) == changed, 'Community-change flag differs from original records')
        if common_anchor is None:
            common_anchor, common_metadata = masked[:junction], metadata[:junction]
            sample_sets.append(set(ids[:junction]))
        require(masked[:junction] == common_anchor and metadata[:junction] == common_metadata,
                'The shared anchor differs beyond the uniform account alias')
        sample_sets.append(set(ids[junction:]))
        windows = reconstruct_windows(metadata)
        require(sum(w['qualified'] for w in windows) >= 8, 'Each history must have at least eight qualified primary windows')
        if 'prescore_qualified_windows' in case:
            require(case['prescore_qualified_windows'] == sum(w['qualified'] for w in windows), 'Prescore window count mismatch')
        if 'prescore_legal_grid' in case:
            require(case['prescore_legal_grid'] == legal_grid(windows), 'Prescore legal grid mismatch')
    require(sum(map(len, sample_sets)) == len(set().union(*sample_sets)), 'The five distinct samples must not share original record IDs')
    return index


def checked_registration(registration, index_path):
    plan = read(registration)
    require(plan['phase'] == 'frozen_before_shared_anchor_diagnostic', 'Final shared-anchor registration required')
    require(plan['prepared_index_sha256'] == sha(index_path) and plan['runner_sha256'] == sha(__file__),
            'Registered index or wrapper changed')
    bindings = {}
    for row in plan['bound_artifacts']:
        target = str(Path(row['path']).resolve())
        require(target not in bindings and sha(target) == row['sha256'], 'Registered helper/input/environment binding mismatch')
        bindings[target] = row['sha256']
    require({str(p.resolve()) for p in HELPERS}.issubset(bindings), 'Every unchanged imported Pilot4 helper must be registered')
    require(plan['limits'] == LIMITS and plan['execution_environment'] == ORIGINAL_ENV and plan['replay_environment'] == REPLAY_ENV,
            'Registered execution ceilings or environments differ')
    return plan, checked_index(index_path)


def run(registration, index_path, output, replay=False, original=None):
    require(os.environ.get('AHAS_NETWORK_ISOLATION') == 'linux_seccomp_socket_denial', 'Socket-denial offline wrapper required')
    plan, index = checked_registration(registration, index_path)
    cases = index['cases']
    original_bytes = 0
    if replay:
        require(original is not None, 'Replay must bind the original four-history execution')
        _, prior_binding, attempts = checked_execution(original)
        require(not prior_binding['replay'] and list(attempts) == [c['case_id'] for c in cases]
                and prior_binding['index_sha256'] == sha(index_path)
                and prior_binding['registration_sha256'] == sha(registration)
                and prior_binding['runner_sha256'] == sha(__file__), 'Replay original execution binding mismatch')
        original_bytes = tree_bytes(original)
        require(original_bytes + 4 * frozen.CASE_ARTIFACT_BYTES <= LIMITS['run_artifact_bytes'],
                'Original plus replay worst-case artifact budget exceeded')
    environment = plan['replay_environment' if replay else 'execution_environment']
    identity = frozen.baseline_identity(environment)
    root = Path(output)
    root.mkdir(mode=0o700, exist_ok=False)
    if replay:
        relocated = root / 'relocated'
        relocated.mkdir(mode=0o700)
        replacements = []
        for source_case in cases:
            case = dict(source_case)
            for field in ('input', 'manifest'):
                target = relocated / (case['case_id'] + '.' + field + Path(case[field]).suffix)
                shutil.copyfile(case[field], target)
                require(sha(target) == sha(case[field]), 'Relocation changed input bytes')
                case[field] = str(target.resolve())
            replacements.append(case)
        cases = replacements
    write(root/'start-binding.json', {'registration_sha256': sha(registration), 'index_sha256': sha(index_path),
        'runner_sha256': sha(__file__), 'helper_sha256': {p.name: sha(p) for p in HELPERS},
        'started_utc': datetime.now(timezone.utc).isoformat(), 'case_ids': [c['case_id'] for c in cases],
        'replay': replay, 'environment': environment, 'actual_baseline_identity': identity,
        'outer_worker_wall_seconds': frozen.WORKER_WALL_SECONDS,
        'original_plus_replay_worst_case_analysis_bytes': 8 * frozen.CASE_ARTIFACT_BYTES})
    start = time.monotonic()
    lock = Lock()
    budget = {'artifact_limit_reached': False, 'completed_bytes': 0, 'active': 0}

    def dispatch(case):
        with lock:
            remaining = LIMITS['dispatch_wall_seconds'] - (time.monotonic() - start)
            if remaining <= 0:
                return {'case_id': case['case_id'], 'status': 'not_dispatched_wall_limit'}
            if budget['artifact_limit_reached'] or original_bytes + budget['completed_bytes'] + (budget['active'] + 1) * frozen.CASE_ARTIFACT_BYTES > LIMITS['run_artifact_bytes']:
                return {'case_id': case['case_id'], 'status': 'not_dispatched_artifact_limit'}
            budget['active'] += 1
        process, receipt = None, None
        row = {'case_id': case['case_id'], 'status': 'worker_failed'}
        try:
            spec = root / (case['case_id'] + '.worker.json')
            write(spec, {'case': case, 'root': str(root.resolve()), 'limits': LIMITS, 'environment': environment})
            with (root/(case['case_id']+'.worker-stdout.log')).open('xb') as stdout, (root/(case['case_id']+'.worker-stderr.log')).open('xb') as stderr:
                process = subprocess.Popen([sys.executable, '-B', str(P4/'run_full_chronology.py'), '--worker', str(spec)],
                                           stdout=stdout, stderr=stderr, start_new_session=True)
                try:
                    process.wait(timeout=min(frozen.WORKER_WALL_SECONDS, remaining))
                except subprocess.TimeoutExpired:
                    frozen.stop_worker(process, root/case['case_id'])
                    row.update(status='worker_wall_limit', effective_exit_code=4)
                else:
                    if process.returncode:
                        frozen.stop_worker(process, root/case['case_id'])
                        row['effective_exit_code'] = process.returncode
                    else:
                        receipt = read(root/case['case_id']/'receipt.json')
                        require(receipt['case_id'] == case['case_id'], 'Worker receipt case mismatch')
                        row = {'case_id': case['case_id'], 'status': 'attempted', 'receipt': receipt}
                        print(json.dumps({k: receipt[k] for k in ('case_id', 'exit_code', 'wall_seconds', 'child_peak_rss_mib')}), flush=True)
        except Exception as error:
            if process is not None and process.poll() is None:
                frozen.stop_worker(process, root/case['case_id'])
            row = {'case_id': case['case_id'], 'status': 'worker_failed', 'error_type': type(error).__name__}
        finally:
            inventory = frozen.artifact_inventory(root/case['case_id']/'analysis')
            size = tree_bytes(root/case['case_id'])
            if receipt is None:
                row['surviving_artifacts'] = inventory
            with lock:
                budget['active'] -= 1
                budget['completed_bytes'] += size
                if size > frozen.CASE_ARTIFACT_BYTES or original_bytes + tree_bytes(root) > LIMITS['run_artifact_bytes']:
                    budget['artifact_limit_reached'] = True
                    row.update(artifact_limit_reached=True, effective_exit_code=4)
        return row

    with ThreadPoolExecutor(max_workers=LIMITS['parallel_cases']) as pool:
        rows = list(pool.map(dispatch, cases))
    write(root/'execution.json', {'cases': rows, 'replay': replay, 'wall_seconds': time.monotonic()-start,
        'artifact_bytes': budget['completed_bytes'], 'artifact_limit_reached': budget['artifact_limit_reached'],
        'shared_anchor_dependence': True, 'original_plus_current_output_bytes_before_execution_manifest': original_bytes + tree_bytes(root)})


def check_saved(index_path, run_root, replay=False):
    index = checked_index(index_path)
    execution, binding, attempts = checked_execution(run_root)
    require(binding['index_sha256'] == sha(index_path) and binding['runner_sha256'] == sha(__file__) and
            binding['replay'] is replay and list(attempts) == [c['case_id'] for c in index['cases']],
            'Saved execution differs from the registered four-case index')
    require(binding['helper_sha256'] == {p.name: sha(p) for p in HELPERS}, 'Saved execution helper identity mismatch')
    require(binding['environment'] == (REPLAY_ENV if replay else ORIGINAL_ENV), 'Saved execution environment mismatch')
    for row in attempts.values():
        if row.get('receipt') is not None:
            require(row['receipt']['environment'] == binding['environment'], 'Worker receipt environment mismatch')
        if row.get('receipt') is None:
            require(row.get('surviving_artifacts', []) == frozen.artifact_inventory(Path(run_root)/row['case_id']/'analysis'),
                    'Failed worker surviving artifact inventory changed')
    return index, execution, binding, attempts


def score(index_path, run_root, output):
    index, execution, binding, attempts = check_saved(index_path, run_root)
    rows = []
    for case in index['cases']:
        attempt = attempts[case['case_id']]
        receipt = attempt.get('receipt')
        directory = Path(run_root)/case['case_id']/'analysis'
        result_path = directory/'results.json'
        exit_code = attempt.get('effective_exit_code', receipt['exit_code'] if receipt else None)
        try:
            result = read(result_path) if result_path.exists() else None
        except json.JSONDecodeError:
            require(exit_code != 0, 'Successful execution has invalid saved results')
            result = None
        primary = frozen.extract_primary(result, exit_code)
        metadata = read(case['metadata'])['records']
        executed = primary['status'] == 'ok'
        try:
            windows, validation = checked_windows(metadata, directory, primary['stream_id'], primary['primary_window_ids'])
        except (ValueError, KeyError, json.JSONDecodeError):
            if executed:
                raise
            windows, validation = reconstruct_windows(metadata), 'unavailable_partial_windows_unverified'
        require(not executed or validation == 'all_primary_memberships_counts_positions_verified',
                'Executed primary result requires exact saved primary-window verification')
        scoring = score_case(candidate_intervals=primary['candidate_intervals'], status=primary['status'],
            reason_codes=primary['reason_codes'], truth_k=case['truth_k'], control_junction_k=case['control_junction_k'],
            windows=windows, record_timestamps=[r['created_utc'] for r in metadata])
        rows.append({**{k: case[k] for k in DESCRIPTORS}, 'score': scoring,
            'primary_window_check': validation, 'native_change_status': primary['native_change_status'],
            'record_count': len(metadata), 'retained_words': sum(r['retained_words'] for r in metadata),
            'full_pipeline_statuses': {k: {'status': v['status'], 'reason_codes': v['reason_codes']} for k, v in result['modules'].items()} if result else None,
            'resources': {k: receipt[k] for k in ('exit_code', 'wall_seconds', 'child_peak_rss_mib', 'external_wall_limit_reached', 'external_artifact_limit_reached')} if receipt else None,
            'effective_exit_code': exit_code, 'dispatch_status': attempt['status'],
            'external_wrapper_artifact_limit_reached': attempt.get('artifact_limit_reached', False),
            'artifact_bytes': sum(a['bytes'] for a in frozen.artifact_inventory(directory)),
            'results_sha256': sha(result_path) if result_path.exists() else None})
    by_condition = {row['condition']: row for row in rows}
    contrasts = []
    for changed in (False, True):
        suffix = 'changed_community' if changed else 'same_community'
        control, switch = by_condition['continuity_' + suffix], by_condition['switch_' + suffix]
        available = control['score']['executed'] and switch['score']['executed']
        contrasts.append({'community_change': changed, 'both_executed': available,
            'switch_minus_control_candidate_occurrence': int(switch['score']['candidate_occurrence'])-int(control['score']['candidate_occurrence']) if available else None,
            'switch_minus_control_candidate_count': switch['score']['candidate_count']-control['score']['candidate_count'] if available else None})
    summary = {'study': 'pilot5_shared_anchor_exploratory', 'planned_histories': 4, 'distinct_samples': 5,
        'shared_anchor_count': 1, 'independent_replicates_estimated': False,
        'interpretation': 'Four descriptive histories share one anchor. Contrasts concern this constructed diagnostic only; no IID means, confidence intervals, population accuracy or causal effects are estimated.',
        'executed_histories': sum(row['score']['executed'] for row in rows),
        'descriptive_switch_minus_control': contrasts,
        'input_index_sha256': sha(index_path), 'execution_manifest_sha256': sha(Path(run_root)/'execution.json'),
        'registration_sha256': binding['registration_sha256']}
    out = Path(output)
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    write(out/'cases.json', rows)
    write(out/'summary.json', summary)
    fields = ['case_id', 'condition', 'source_switch', 'community_change', 'executed', 'candidate_count',
              'candidate_occurrence', 'record_count', 'retained_words', 'native_change_status',
              'switch_matched_within_10', 'switch_nearest_error_records',
              'control_junction_matched_within_10', 'control_junction_nearest_error_records', 'artifact_bytes']
    with (out/'cases.csv').open('x') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for row in rows:
            flat = {k: row[k] for k in fields if k in row}
            flat.update({k: row['score'][k] for k in ('executed', 'candidate_count', 'candidate_occurrence')})
            for prefix, field in [('switch', 'switch_localization'), ('control_junction', 'control_junction_diagnostic')]:
                loc = row['score'][field]
                flat[prefix+'_matched_within_10'] = loc['matched_within_tolerance'] if loc else None
                flat[prefix+'_nearest_error_records'] = loc['nearest_interval_error_records'] if loc else None
            writer.writerow(flat)
    return summary


def replay_check(index_path, first, replay, output):
    index, _, first_binding, original = check_saved(index_path, first)
    _, _, replay_binding, repeated = check_saved(index_path, replay, replay=True)
    require(all(first_binding[k] == replay_binding[k] for k in ('index_sha256', 'registration_sha256', 'runner_sha256', 'helper_sha256')),
            'Replay must bind the same original registration and code')
    require(list(original) == list(repeated) and len(repeated) == 4, 'All four histories must be replayed')
    require(tree_bytes(first) + tree_bytes(replay) <= LIMITS['run_artifact_bytes'], 'Original plus replay output ceiling exceeded')
    for case in index['cases']:
        for field in ('input', 'manifest'):
            relocated = Path(replay)/'relocated'/(case['case_id'] + '.' + field + Path(case[field]).suffix)
            require(relocated.is_file() and sha(relocated) == sha(case[field]), 'Saved relocated input bytes changed')
    rows = []
    for case_id in original:
        inventories = [{r['name']: {k: r[k] for k in ('bytes', 'sha256')}
                        for r in frozen.artifact_inventory(Path(root)/case_id/'analysis') if r['canonical']}
                       for root in (first, replay)]
        rows.append({'case_id': case_id, 'canonical_file_count': len(inventories[0]),
            'all_files_byte_identical': bool(inventories[0]) and inventories[0] == inventories[1],
            'differing_files': sorted(k for k in set(inventories[0]) | set(inventories[1]) if inventories[0].get(k) != inventories[1].get(k)),
            'original_dispatch_status': original[case_id]['status'], 'replay_dispatch_status': repeated[case_id]['status']})
    result = {'cases': rows, 'all_passed': all(row['all_files_byte_identical'] for row in rows),
              'excluded_operational_files': sorted(frozen.OPERATIONAL), 'replayed_histories': 4,
              'original_environment': ORIGINAL_ENV, 'replay_environment': REPLAY_ENV,
              'independent_replicates_estimated': False}
    write(output, result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'score', 'replay-check'))
    parser.add_argument('--index', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--registration')
    parser.add_argument('--run')
    parser.add_argument('--original')
    parser.add_argument('--replay', action='store_true')
    parser.add_argument('--replay-root')
    args = parser.parse_args()
    if args.command == 'run':
        require(args.registration is not None, 'Execution registration required')
        run(args.registration, args.index, args.out, args.replay, args.original)
    elif args.command == 'score':
        require(args.run is not None, 'Saved execution root required')
        score(args.index, args.run, args.out)
    else:
        require(args.run is not None and args.replay_root is not None, 'Both saved execution roots required')
        replay_check(args.index, args.run, args.replay_root, args.out)
