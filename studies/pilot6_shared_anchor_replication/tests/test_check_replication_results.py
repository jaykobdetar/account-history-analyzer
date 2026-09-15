"""Independent checker tests with synthetic prior-adapter outputs only."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

S6 = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('pilot6_independent_check',S6/'scripts/check_replication_results.py')
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)
FIXTURE = importlib.util.spec_from_file_location('pilot6_runner_fixtures',S6/'tests/test_run_replication.py')
f = importlib.util.module_from_spec(FIXTURE)
FIXTURE.loader.exec_module(f)


def prepared(tmp_path, monkeypatch, n=2, mode='success'):
    cohort = f.Cohort(tmp_path,n)
    plan = c.read(cohort.plan)
    plan['bound_artifacts'] += [{'path':str(p),'sha256':c.sha(p)} for p in (Path(c.__file__),c.PRIOR)]
    f.put(cohort.plan,plan)
    if mode == 'success':
        f.synthetic_phases(monkeypatch)
    elif mode == 'global_stop':
        monkeypatch.setattr(f.r,'launch_phase',lambda *a:{'status':'global_wall_limit','exit_code':-9,'wall_seconds':.1})
    elif mode == 'worker_failure':
        f.synthetic_phases(monkeypatch)
        f.fixture_module.fake_workers(monkeypatch,mode='failure')
    else:
        raise AssertionError('Unknown synthetic mode')
    f.r.run(cohort.plan,tmp_path/'run')
    return cohort,tmp_path/'run'


def mutate_public(run, mutate, pair='pilot6-pair-01', original=False):
    summary_path = run/pair/'pair-summary.json'
    pair_doc = c.read(summary_path)
    mutate(pair_doc['cases'])
    f.put(summary_path,pair_doc)
    cases = c.read(run/'cases.json')
    cases = pair_doc['cases'] + cases[4:]
    f.put(run/'cases.json',cases)
    if original:
        f.put(run/pair/'scores/cases.json',[{k:v for k,v in row.items() if k not in c.ADDED_FIELDS} for row in pair_doc['cases']])


def test_two_pairs_full_independent_native_grid_cost_replay_and_counts(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch)
    report = c.check(cohort.plan,run)
    assert report['status'] == 'passed'
    assert report['new_source_account_pairs'] == report['independent_sampling_units'] == 2
    assert report['planned_main_histories'] == report['planned_replay_histories'] == 8
    assert report['main_executed_primary_histories'] == 8
    assert report['pairs_with_four_verified_replays'] == 2
    assert report['operating_costs']['main_operation']['recorded_wall_time_histories'] == 8
    assert report['operating_costs']['main_operation']['sum_case_wall_seconds'] == pytest.approx(.8)
    assert [r['candidate_count'] for r in report['cases']] == [0,1,0,1]*2
    assert report['analyzer_calls'] == 0
    assert 'record_ids' not in json.dumps(report) and 'account-1-' not in json.dumps(report)


def test_empty_cohort_preserves_ten_pair_shortfall_and_zero_units(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch,n=0)
    report = c.check(cohort.plan,run)
    assert report['new_source_account_pairs'] == report['independent_sampling_units'] == 0
    assert report['cases'] == []


def test_global_stop_all_four_slots_null_with_metadata_grid(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch,mode='global_stop')
    report = c.check(cohort.plan,run)
    assert report['main_unavailable_primary_histories'] == 8
    assert all(r['candidate_count'] is None and r['best_grid_error_records'] == 0 for r in report['cases'])
    assert all(r['independent_main_arithmetic_check'] == 'unavailable_preserved_null' for r in report['pairs'])


def test_completed_worker_failures_remain_null_not_executed_zero(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch,n=1,mode='worker_failure')
    report = c.check(cohort.plan,run)
    assert report['main_unavailable_primary_histories'] == 4
    assert report['pairs_with_four_verified_replays'] == 0
    assert all(r['candidate_count'] is None for r in report['cases'])
    assert report['pairs'][0]['independent_main_arithmetic_check'] == 'passed'


def test_independent_checker_must_be_bound_before_execution(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch,n=0)
    plan = c.read(cohort.plan)
    plan['bound_artifacts'] = [r for r in plan['bound_artifacts'] if r['path'] != str(c.PRIOR)]
    f.put(cohort.plan,plan)
    with pytest.raises(ValueError,match='not_preregistered'):
        c.check(cohort.plan,run)


def test_artifact_reservation_stop_requires_supporting_saved_storage(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch,n=1,mode='global_stop')
    path = run/'pilot6-pair-01/pair-summary.json'
    pair = c.read(path)
    pair['phases']['main']['status'] = 'not_dispatched_global_artifact_reservation'
    f.put(path,pair)
    with pytest.raises(ValueError,match='reservation_stop_not_supported'):
        c.check(cohort.plan,run)


@pytest.mark.parametrize('key,value',[
    ('registered_new_pairs',8),('planned_main_histories',16),('planned_replay_histories',4),
    ('main_executed_primary_histories',7),('pairs_with_four_verified_replays',8),
    ('main_dispatched_histories',0),('prescore_pair_shortfall',0),
])
def test_histories_or_replays_cannot_be_counted_as_new_independent_pairs(tmp_path,monkeypatch,key,value):
    cohort,run = prepared(tmp_path,monkeypatch)
    summary = c.read(run/'summary.json');summary[key]=value;f.put(run/'summary.json',summary)
    with pytest.raises(ValueError,match='denominator_or_cost'):
        c.check(cohort.plan,run)


def test_missing_condition_fails_even_if_pair_and_global_reports_agree(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch,n=1)
    mutate_public(run,lambda rows:rows.pop())
    with pytest.raises(ValueError,match='case_slots'):
        c.check(cohort.plan,run)


def test_native_interval_arithmetic_detects_jointly_changed_adapter_and_aggregate(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch,n=1)
    mutate_public(run,lambda rows:rows[1]['score']['switch_localization'].update(nearest_interval_error_records=9),original=True)
    with pytest.raises(ValueError,match='localization_mismatch'):
        c.check(cohort.plan,run)


def test_every_candidate_error_is_independently_recomputed(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch,n=1)
    mutate_public(run,lambda rows:rows[1].update(all_candidate_interval_errors_records=[1]))
    with pytest.raises(ValueError,match='every_candidate_error'):
        c.check(cohort.plan,run)


def test_null_unavailable_cannot_be_replaced_with_zero(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch,n=1,mode='global_stop')
    mutate_public(run,lambda rows:rows[0]['score'].update(candidate_count=0))
    with pytest.raises(ValueError,match='not_null'):
        c.check(cohort.plan,run)


def test_unavailable_grid_is_reconstructed_without_saved_native_outputs(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch,n=1,mode='global_stop')
    mutate_public(run,lambda rows:rows[0]['score']['grid_resolution'].update(best_interval_error_records=2))
    with pytest.raises(ValueError,match='grid_or_temporal'):
        c.check(cohort.plan,run)


def test_operating_cost_is_compared_to_original_receipt(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch,n=1)
    mutate_public(run,lambda rows:rows[0]['main_operation'].update(wall_seconds=9999))
    with pytest.raises(ValueError,match='operating_cost'):
        c.check(cohort.plan,run)


def test_replay_canonical_file_change_detected_even_with_updated_worker_inventory(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch,n=1)
    pair = cohort.doc['pairs'][0];case = cohort.fixtures[0].cases[0]
    replay = run/pair['pair_id']/'replay'
    target = replay/case['case_id']/'analysis/other_receipt.json'
    f.put(target,{'must_remain_canonical':None})  # null and true have the same byte length
    f.fixture_module.refresh_receipt(replay,case['case_id'])
    with pytest.raises(ValueError,match='replay_hash'):
        c.check(cohort.plan,run)


def test_only_two_operational_receipts_are_excluded(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch,n=1)
    target = run/'pilot6-pair-01/replay-check.json'
    doc = c.read(target);doc['excluded_operational_files'].append('other_receipt.json');f.put(target,doc)
    with pytest.raises(ValueError,match='replay_design'):
        c.check(cohort.plan,run)


def test_relocated_input_hash_must_match_even_when_canonical_results_match(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch,n=1)
    relocated = next((run/'pilot6-pair-01/replay/relocated').glob('*.input.jsonl'))
    with relocated.open('a') as handle:handle.write(' ')
    with pytest.raises(ValueError,match='relocated_input'):
        c.check(cohort.plan,run)


def test_unverified_replay_cannot_claim_pass(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch,n=1,mode='global_stop')
    target = run/'pilot6-pair-01/pair-summary.json'
    pair = c.read(target);pair['replay_all_passed']=True;f.put(target,pair)
    with pytest.raises(ValueError,match='unverified_replay_claimed'):
        c.check(cohort.plan,run)


def test_incomplete_main_with_partial_native_output_keeps_all_scores_unavailable(tmp_path,monkeypatch):
    cohort = f.Cohort(tmp_path,1)
    plan = c.read(cohort.plan)
    plan['bound_artifacts'] += [{'path':str(p),'sha256':c.sha(p)} for p in (Path(c.__file__),c.PRIOR)]
    f.put(cohort.plan,plan)
    case = cohort.fixtures[0].cases[0]
    def partial(argv,log,*args):
        if Path(log).name == 'main':
            f.fixture_module.analysis_stub(case,Path(log)/case['case_id']/'analysis')
            (Path(log)/'execution.json').write_text('{')
        return {'status':'global_wall_limit','exit_code':-9,'wall_seconds':.1}
    monkeypatch.setattr(f.r,'launch_phase',partial)
    f.r.run(cohort.plan,tmp_path/'run')
    report = c.check(cohort.plan,tmp_path/'run')
    assert report['main_unavailable_primary_histories'] == 4
    assert all(r['candidate_count'] is None for r in report['cases'])
    assert (tmp_path/'run/pilot6-pair-01/main'/case['case_id']/'analysis/results.json').exists()


def test_successful_native_module_status_cannot_be_relabelled(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch,n=1)
    mutate_public(run,lambda rows:rows[0]['full_pipeline_statuses']['style'].update(status='abstained'),original=True)
    with pytest.raises(ValueError,match='full_module_status'):
        c.check(cohort.plan,run)


def test_every_interval_checked_for_multiple_candidates_including_unmatched_one(tmp_path,monkeypatch):
    cohort = f.Cohort(tmp_path,1)
    plan = c.read(cohort.plan)
    plan['bound_artifacts'] += [{'path':str(p),'sha256':c.sha(p)} for p in (Path(c.__file__),c.PRIOR)]
    f.put(cohort.plan,plan)
    f.synthetic_phases(monkeypatch)
    original = f.r.launch_phase
    def multiple(argv,log,*args):
        result = original(argv,log,*args)
        if Path(log).name in ('main','replay'):
            case = cohort.fixtures[0].cases[1]
            path = Path(log)/case['case_id']/'analysis/results.json'
            doc = c.read(path)
            doc['modules']['style']['payload']['changes'][0]['boundaries'] = [
                {'record_interval':[23,24]},{'record_interval':[47,48]}]
            f.put(path,doc)
            f.fixture_module.refresh_receipt(Path(log),case['case_id'])
        return result
    monkeypatch.setattr(f.r,'launch_phase',multiple)
    f.r.run(cohort.plan,tmp_path/'run')
    report = c.check(cohort.plan,tmp_path/'run')
    assert report['cases'][1]['candidate_count'] == 2
    assert report['cases'][1]['all_candidate_errors_records'] == [16,8]


def test_cli_writes_fresh_hashbound_public_check_without_analyzer(tmp_path,monkeypatch):
    cohort,run = prepared(tmp_path,monkeypatch,n=0)
    # No P5 fake-worker subprocess monkeypatch is needed in an empty-cohort CLI.
    monkeypatch.undo()
    out = tmp_path/'check.json'
    result = subprocess.run([sys.executable,'-B',str(c.__file__),'--registration',str(cohort.plan),
                            '--run',str(run),'--out',str(out)],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    assert c.read(out)['status'] == 'passed'
    assert c.read(Path(str(out)+'.start-binding.json'))['checker_sha256'] == c.sha(c.__file__)
