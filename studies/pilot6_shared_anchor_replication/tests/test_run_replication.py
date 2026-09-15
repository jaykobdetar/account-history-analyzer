"""Synthetic orchestration and real tiny-process cleanup; no analyzer calls."""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time

import pytest

S6 = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('pilot6_runner', S6/'scripts/run_replication.py')
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)
OLD = importlib.util.spec_from_file_location('pilot5_synthetic_fixture',
     S6.parent/'pilot5_shared_anchor/tests/test_run_diagnostic.py')
fixture_module = importlib.util.module_from_spec(OLD)
OLD.loader.exec_module(fixture_module)


def put(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True)+'\n')


class Cohort:
    def __init__(self, root, n=2):
        self.root, self.fixtures = root, []
        self.index, self.plan = root/'cohort.json', root/'global.json'
        self.doc = {'target_pairs': 10, 'excluded_account_keys': [f'excluded-{i}' for i in range(119)], 'pairs': []}
        for number in range(1, n+1):
            pid = f'pilot6-pair-{number:02}'
            pair_root = root/pid
            pair_root.mkdir()
            f = fixture_module.Synthetic(pair_root)
            for case in f.cases:
                for field in ('case_id', 'block_id', 'left_cell_id', 'right_cell_id'):
                    case[field] = case[field].replace('synthetic-pilot5', pid)
                records = [json.loads(line) for line in Path(case['input']).read_text().splitlines()]
                for record in records:
                    record['account_id'] = case['case_id']
                    record['id'] = pid+'-'+record['id']
                Path(case['input']).write_text(''.join(json.dumps(x, sort_keys=True)+'\n' for x in records))
                put(case['manifest'], {'account_id': case['case_id']})
                metadata = r.read(case['metadata'])
                for m in metadata['records']:
                    m['record_id'] = pid+'-'+m['record_id']
                put(case['metadata'], metadata)
            f.refresh()
            self.fixtures.append(f)
            self.doc['pairs'].append({'pair_id': pid, 'source_account_keys': [f'account-{number}-a', f'account-{number}-b'],
                                     'index': str(f.index), 'registration': str(f.registration)})
        self.refresh()

    def refresh(self):
        put(self.index, self.doc)
        paths = [Path(r.__file__), r.P5, r.OFFLINE, self.index, *r.adapter.HELPERS]
        paths += [Path(p[k]) for p in self.doc['pairs'] for k in ('index', 'registration')]
        put(self.plan, {'phase': 'frozen_before_pilot6_replication', 'cohort_index': str(self.index),
            'cohort_sha256': r.sha(self.index), 'runner_sha256': r.sha(r.__file__), 'limits': r.LIMITS,
            'bound_artifacts': [{'path': str(p), 'sha256': r.sha(p)} for p in paths]})


def synthetic_phases(monkeypatch):
    fixture_module.fake_workers(monkeypatch)
    calls = []
    def phase(argv, log_root, output_root, deadline, artifact_limit):
        args = argv[6:]
        assert argv[:6] == [sys.executable, '-B', str(r.OFFLINE), sys.executable, '-B', str(r.P5)]
        command = args[0]
        get = lambda flag: args[args.index(flag)+1]
        calls.append((Path(log_root).parent.name, Path(log_root).name))
        if command == 'run':
            r.adapter.run(get('--registration'), get('--index'), get('--out'), '--replay' in args,
                          get('--original') if '--original' in args else None)
        elif command == 'score':
            r.adapter.score(get('--index'), get('--run'), get('--out'))
        else:
            r.adapter.replay_check(get('--index'), get('--run'), get('--replay-root'), get('--out'))
        return {'status': 'completed', 'exit_code': 0, 'wall_seconds': 0.01}
    monkeypatch.setattr(r, 'launch_phase', phase)
    return calls


def test_two_pairs_unchanged_adapter_complete_four_conditions_and_replays(tmp_path, monkeypatch):
    cohort = Cohort(tmp_path)
    calls = synthetic_phases(monkeypatch)
    summary = r.run(cohort.plan, tmp_path/'out')
    assert calls == [(p['pair_id'], phase) for p in cohort.doc['pairs'] for phase in r.PHASES]
    assert summary['registered_new_pairs'] == 2
    assert summary['planned_main_histories'] == summary['planned_replay_histories'] == 8
    assert summary['main_executed_primary_histories'] == 8
    assert summary['pairs_with_four_verified_replays'] == 2
    cases = r.read(tmp_path/'out/cases.json')
    assert [c['score']['candidate_count'] for c in cases] == [0, 1, 0, 1]*2
    assert [c['all_candidate_interval_errors_records'] for c in cases] == [[], [0], [], [0]]*2
    assert all(c['main_operation']['dispatched'] and c['replay_operation']['dispatched'] for c in cases)
    assert all(c['replay_verification']['canonical_file_count'] == 3 for c in cases)
    raw = (tmp_path/'out/cases.json').read_text()
    assert 'excluded-' not in raw and 'account-1-' not in raw and 'record_ids' not in raw


def test_zero_eligible_pairs_is_complete_recorded_shortfall_without_dispatch(tmp_path, monkeypatch):
    cohort = Cohort(tmp_path, 0)
    monkeypatch.setattr(r, 'launch_phase', lambda *a: pytest.fail('No pair may dispatch'))
    result = r.run(cohort.plan, tmp_path/'out')
    assert result['prescore_pair_shortfall'] == 10
    assert result['planned_main_histories'] == 0
    assert result['global_wall_seconds_since_first_dispatch'] is None
    assert r.read(tmp_path/'out/cases.json') == []
    assert not (tmp_path/'out/first-dispatch.json').exists()


@pytest.mark.parametrize('mutation,message', [
    (lambda c: c['pairs'][1]['source_account_keys'].__setitem__(0, 'account-1-a'), 'Repeated or excluded'),
    (lambda c: c['pairs'][0]['source_account_keys'].__setitem__(0, 'excluded-0'), 'Repeated or excluded'),
    (lambda c: c['pairs'][0].update(pair_id='../bad'), 'pair identifier'),
    (lambda c: c.update(target_pairs=11), 'pair count'),
    (lambda c: c['excluded_account_keys'].pop(), '119-account'),
])
def test_private_cohort_identity_and_exclusions_fail_closed(tmp_path, mutation, message):
    cohort = Cohort(tmp_path)
    mutation(cohort.doc); cohort.refresh()
    with pytest.raises(ValueError, match=message):
        r.checked_registration(cohort.plan)


def test_bindings_detect_input_change_and_missing_pair_registration(tmp_path):
    cohort = Cohort(tmp_path, 1)
    plan = r.read(cohort.plan)
    plan['bound_artifacts'] = [a for a in plan['bound_artifacts'] if a['path'] != str(cohort.fixtures[0].registration)]
    put(cohort.plan, plan)
    with pytest.raises(ValueError, match='Missing global'):
        r.checked_registration(cohort.plan)
    cohort.refresh()
    Path(cohort.fixtures[0].cases[0]['input']).write_text('changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        r.checked_registration(cohort.plan)


def test_global_wall_stop_retains_all_pairs_all_conditions_as_null(tmp_path, monkeypatch):
    cohort = Cohort(tmp_path)
    calls = []
    def expire(*args):
        calls.append(args)
        return {'status': 'global_wall_limit', 'exit_code': -9, 'wall_seconds': .1}
    monkeypatch.setattr(r, 'launch_phase', expire)
    result = r.run(cohort.plan, tmp_path/'out')
    assert len(calls) == 1 and result['stop_reason'] == 'global_wall_limit'
    assert result['main_unavailable_primary_histories'] == 8
    cases = r.read(tmp_path/'out/cases.json')
    assert len(cases) == 8
    assert all(c['score']['candidate_count'] is None and c['score']['candidate_intervals'] is None for c in cases)
    assert all(c['all_candidate_interval_errors_records'] is None for c in cases)
    assert all(c['score']['grid_resolution']['adequate_window_count'] for c in cases)
    assert all('metadata_reconstruction' in c['primary_window_check'] for c in cases)


def test_pair_reservation_before_start_and_no_shortfall_disappearance(tmp_path, monkeypatch):
    cohort = Cohort(tmp_path, 1)
    monkeypatch.setattr(r, 'tree_bytes', lambda _: r.LIMITS['global_artifact_bytes']-r.LIMITS['pair_reserved_artifact_bytes']+1)
    monkeypatch.setattr(r, 'launch_phase', lambda *a: pytest.fail('Reservation must stop dispatch'))
    result = r.run(cohort.plan, tmp_path/'out')
    assert result['stop_reason'] == 'not_dispatched_global_artifact_reservation'
    assert result['main_unavailable_primary_histories'] == 4


def test_unexpected_watchdog_exception_stops_new_dispatch_and_keeps_all_slots(tmp_path, monkeypatch):
    cohort = Cohort(tmp_path)
    calls = []
    def failure(*args):
        calls.append(args)
        raise RuntimeError('Synthetic cleanup uncertainty')
    monkeypatch.setattr(r, 'launch_phase', failure)
    result = r.run(cohort.plan, tmp_path/'out')
    assert len(calls) == 1
    assert result['stop_reason'] == 'orchestrator_exception'
    assert result['main_unavailable_primary_histories'] == 8


def test_failed_original_wrapper_preserves_slots_then_next_pair_is_attempted(tmp_path, monkeypatch):
    cohort = Cohort(tmp_path)
    calls = []
    def failure(*args):
        calls.append(Path(args[1]).name)
        return {'status': 'failed', 'exit_code': 2, 'wall_seconds': 0.01}
    monkeypatch.setattr(r, 'launch_phase', failure)
    result = r.run(cohort.plan, tmp_path/'out')
    assert calls == ['main', 'score']*2
    assert result['stop_reason'] is None and result['main_unavailable_primary_histories'] == 8
    for pair in cohort.doc['pairs']:
        saved = r.read(tmp_path/'out'/pair['pair_id']/'pair-summary.json')
        assert saved['phases']['replay']['status'] == 'not_dispatched_main_incomplete'


def test_score_failure_still_replays_all_four_frozen_inputs(tmp_path, monkeypatch):
    cohort = Cohort(tmp_path, 1)
    calls = synthetic_phases(monkeypatch)
    original = r.launch_phase
    def fail_score(argv, log, *args):
        if Path(log).name == 'score':
            return {'status': 'failed', 'exit_code': 2, 'wall_seconds': .01}
        return original(argv, log, *args)
    monkeypatch.setattr(r, 'launch_phase', fail_score)
    result = r.run(cohort.plan, tmp_path/'out')
    assert [p[1] for p in calls] == ['main', 'replay', 'replay-check']
    assert result['main_unavailable_primary_histories'] == 4
    assert result['pairs_with_four_verified_replays'] == 1


def test_replay_failure_does_not_erase_verified_original_scores(tmp_path, monkeypatch):
    cohort = Cohort(tmp_path, 1)
    synthetic_phases(monkeypatch)
    original = r.launch_phase
    def fail_replay(argv, log, *args):
        if Path(log).name == 'replay':
            return {'status': 'global_wall_limit', 'exit_code': -9, 'wall_seconds': .01}
        return original(argv, log, *args)
    monkeypatch.setattr(r, 'launch_phase', fail_replay)
    result = r.run(cohort.plan, tmp_path/'out')
    assert result['main_executed_primary_histories'] == 4
    assert result['pairs_with_four_verified_replays'] == 0
    assert all(c['replay_verification']['all_files_byte_identical'] is None for c in r.read(tmp_path/'out/cases.json'))


def test_malformed_partial_receipts_and_execution_do_not_erase_denominators(tmp_path, monkeypatch):
    cohort = Cohort(tmp_path, 1)
    case_id = cohort.fixtures[0].cases[0]['case_id']
    def partial(argv, log, *args):
        if Path(log).name == 'main':
            directory = Path(log)
            (directory/case_id).mkdir(parents=True)
            (directory/'execution.json').write_text('{')
            (directory/case_id/'receipt.json').write_text('{')
            (directory/(case_id+'.worker.json')).write_text('{}')
        return {'status': 'failed', 'exit_code': 2, 'wall_seconds': .01}
    monkeypatch.setattr(r, 'launch_phase', partial)
    summary = r.run(cohort.plan, tmp_path/'out')
    assert summary['main_unavailable_primary_histories'] == 4
    assert summary['main_dispatched_histories'] == 1
    rows = r.read(tmp_path/'out/cases.json')
    assert rows[0]['resources'] is None
    assert all(row['score']['candidate_occurrence'] is None for row in rows)


def test_saved_score_collection_failure_retains_raw_artifacts_and_null_rows(tmp_path, monkeypatch):
    cohort = Cohort(tmp_path, 1)
    synthetic_phases(monkeypatch)
    original = r.launch_phase
    def malformed(argv, log, *args):
        result = original(argv, log, *args)
        if Path(log).name == 'score':
            (Path(log).parent/'scores/cases.json').write_text('[]')
        return result
    monkeypatch.setattr(r, 'launch_phase', malformed)
    summary = r.run(cohort.plan, tmp_path/'out')
    assert summary['main_unavailable_primary_histories'] == 4
    saved = r.read(tmp_path/'out/pilot6-pair-01/pair-summary.json')
    assert saved['status'] == 'saved_output_verification_failed'
    assert saved['phases']['collection']['status'] == 'saved_output_verification_failed'
    assert (tmp_path/'out/pilot6-pair-01/scores/cases.json').read_text() == '[]'


def test_global_watchdog_kills_detached_child_and_grandchild(tmp_path):
    child = tmp_path/'child.py'
    grandchild = tmp_path/'grandchild.py'
    grandchild.write_text('import time\ntime.sleep(30)\n')
    child.write_text('import subprocess,sys,time,os\nfrom pathlib import Path\n'
        f'p=subprocess.Popen([sys.executable,{str(grandchild)!r}],start_new_session=True)\n'
        f'Path({str(tmp_path/"pids.json")!r}).write_text(str(os.getpid())+","+str(p.pid))\n'
        'time.sleep(30)\n')
    parent = tmp_path/'parent.py'
    parent.write_text('import subprocess,sys,time\n'
        f'subprocess.Popen([sys.executable,{str(child)!r}],start_new_session=True)\n'
        'time.sleep(30)\n')
    result = r.launch_phase([sys.executable, '-B', str(parent)], tmp_path/'phase', tmp_path,
                            time.monotonic()+.8, 1024**2)
    assert result['status'] == 'global_wall_limit'
    assert result['terminated_process_count'] >= 3
    pids = [int(p) for p in (tmp_path/'pids.json').read_text().split(',')]
    assert all((info := r.process_info(pid)) is None or info['state'] == 'Z' for pid in pids)


def test_orphan_after_fast_parent_failure_is_cleaned_up(tmp_path):
    parent = tmp_path/'parent.py'
    parent.write_text('import subprocess,sys\nfrom pathlib import Path\n'
        'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"],start_new_session=True)\n'
        f'Path({str(tmp_path/"pid")!r}).write_text(str(p.pid))\n'
        'raise SystemExit(7)\n')
    result = r.launch_phase([sys.executable, '-B', str(parent)], tmp_path/'phase', tmp_path,
                            time.monotonic()+3, 1024**2)
    assert result['status'] == 'failed' and result['exit_code'] == 7
    pid = int((tmp_path/'pid').read_text())
    assert (info := r.process_info(pid)) is None or info['state'] == 'Z'


def test_global_watchdog_preserves_oversized_output_and_stops_writer(tmp_path):
    script = tmp_path/'writer.py'
    script.write_text('from pathlib import Path\nimport time\n'
        f'Path({str(tmp_path/"artifact")!r}).write_bytes(b"x"*20000)\n'
        'time.sleep(30)\n')
    result = r.launch_phase([sys.executable, '-B', str(script)], tmp_path/'phase', tmp_path,
                            time.monotonic()+3, 10000)
    assert result['status'] == 'global_artifact_limit'
    assert (tmp_path/'artifact').stat().st_size == 20000


def test_successful_tiny_phase_and_expired_not_dispatched(tmp_path):
    result = r.launch_phase([sys.executable, '-c', 'print("synthetic")'], tmp_path/'phase', tmp_path,
                           time.monotonic()+3, 1024**2)
    assert result['status'] == 'completed' and result['exit_code'] == 0
    other = r.launch_phase([sys.executable, '-c', 'raise SystemExit(0)'], tmp_path/'expired', tmp_path,
                          time.monotonic()-1, 1024**2)
    assert other['status'] == 'not_dispatched_global_wall_limit'
    assert not (tmp_path/'expired.stdout.log').exists()
