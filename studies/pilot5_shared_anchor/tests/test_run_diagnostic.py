"""Synthetic wrapper checks; no corpus records or style computation."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import pytest

SPEC = importlib.util.spec_from_file_location('run_diagnostic', Path(__file__).parents[1]/'scripts/run_diagnostic.py')
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)


def put(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True)+'\n')


class Synthetic:
    def __init__(self, root):
        self.root = root
        self.prepared = root/'prepared'
        self.prepared.mkdir()
        self.index = self.prepared/'index.json'
        self.registration = root/'registration.json'
        self.cases = []
        cut = datetime(2020, 1, 1, tzinfo=timezone.utc)
        block = 'synthetic-pilot5'
        for condition in d.CONDITIONS:
            switch, changed = condition.startswith('switch_'), condition.endswith('changed_community')
            case = dict(case_id=f'{block}:AX:{condition}', block_id=block, stratum_id='synthetic-stratum',
                        anchor_id='AX', condition=condition, source_switch=switch, community_change=changed,
                        left_cell_id=f'{block}:A:X:early', right_cell_id=f'{block}:{"B" if switch else "A"}:{"Y" if changed else "X"}:late',
                        truth_k=40 if switch else None, control_junction_k=None if switch else 40)
            records = []
            for ordinal in range(80):
                early = ordinal < 40
                rid = f'anchor-{ordinal:03}' if early else f'{condition}-{ordinal:03}'
                records.append({'schema_version': '1.0.0', 'id': rid, 'account_id': case['case_id'],
                    'kind': 'comment', 'text': 'Synthetic retained comment ' + 'alpha ' * 122,
                    'created_utc': (cut+timedelta(hours=ordinal-40 if early else ordinal-39)).isoformat().replace('+00:00','Z'),
                    'subreddit': 'synthetic-Y' if changed and not early else 'synthetic-X', 'status': 'present'})
            metadata = [{'record_id': r['id'], 'created_utc': r['created_utc'], 'retained_words':125,
                         'style_eligible':True, 'kind':'comment'} for r in records]
            for field in ('input','manifest','metadata'):
                case[field] = str(self.prepared/(case['case_id']+'.'+field+('.jsonl' if field=='input' else '.json')))
            Path(case['input']).write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in records))
            put(case['manifest'], {'account_id':case['case_id']})
            put(case['metadata'], {'records':metadata})
            windows = d.reconstruct_windows(metadata)
            case.update(prescore_qualified_windows=10, prescore_legal_grid=d.legal_grid(windows))
            self.cases.append(case)
        self.refresh()

    def refresh(self):
        put(self.index, {'cases':self.cases, 'bound_files':[{'path':c[f], 'sha256':d.sha(c[f])} for c in self.cases for f in ('input','manifest','metadata')]})
        put(self.registration, {'phase':'frozen_before_shared_anchor_diagnostic',
            'prepared_index_sha256':d.sha(self.index), 'runner_sha256':d.sha(d.__file__),
            'bound_artifacts':[{'path':str(p),'sha256':d.sha(p)} for p in d.HELPERS],
            'limits':d.LIMITS, 'execution_environment':d.ORIGINAL_ENV, 'replay_environment':d.REPLAY_ENV})

    def mutate_input(self, ordinal, mutate):
        path = Path(self.cases[ordinal]['input'])
        records = [json.loads(line) for line in path.read_text().splitlines()]
        mutate(records)
        path.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in records))
        self.refresh()


def analysis_stub(case, directory, native=None, exit_code=0):
    directory.mkdir(parents=True)
    metadata = d.read(case['metadata'])['records']
    windows = d.reconstruct_windows(metadata)
    result = {'analysis':{'implementation_fingerprint':d.frozen.FINGERPRINT,'config_sha256':d.frozen.CONFIG},
        'modules':{'style':{'status':'ok','reason_codes':[], 'payload':{
            'streams':[{'scope_type':'pooled','kind':'comment','subreddit':None,'stream_id':'primary',
                        'window_ids':[f'window-{i}' for i in range(len(windows))]}],
            'changes':[{'stream_id':'primary','status':native or ('ok' if case['source_switch'] else 'no_measurable_variation'),
                        'reason_codes':[], 'boundaries':[{'record_interval':[39,40]}] if case['source_switch'] else []}]}},
            'text':{'status':'ok','reason_codes':[],'payload':{}},
            'temporal':{'status':'ok','reason_codes':[],'payload':{}}}}
    put(directory/'results.json',result)
    with (directory/'windows.jsonl').open('w') as handle:
        for i, window in enumerate(windows):
            row = {k:v for k,v in window.items() if k!='record_positions'}
            row.update(window_id=f'window-{i}',stream_id='primary',record_ids=[metadata[p]['record_id'] for p in window['record_positions']])
            handle.write(json.dumps(row)+'\n')
        handle.write(json.dumps({'window_id':'sensitivity','stream_id':'primary','word_count':500})+'\n')
    put(directory/'ingest_receipt.json',{'path':str(directory)})
    put(directory/'run_receipt.json',{'path':str(directory)})
    put(directory/'other_receipt.json',{'must_remain_canonical':True})
    receipt = {'case_id':case['case_id'],'exit_code':exit_code,'wall_seconds':0.1,'child_peak_rss_mib':1,
               'external_wall_limit_reached':False,'external_artifact_limit_reached':False,
               'artifacts':d.frozen.artifact_inventory(directory)}
    put(directory.parent/'receipt.json',receipt)
    return receipt


def fake_workers(monkeypatch, mode='ok'):
    calls = []
    class Worker:
        def __init__(self, argv, **kwargs):
            self.pid=999999999; self.returncode=None
            self.spec=d.read(argv[-1]);self.argv=argv;self.kwargs=kwargs;calls.append(self)
        def wait(self,timeout=None):
            self.timeout=timeout
            if self.returncode is not None:return self.returncode
            if mode=='timeout':raise subprocess.TimeoutExpired('synthetic',timeout)
            self.returncode=7 if mode=='failure' else 0
            if self.returncode==0:
                case_root=Path(self.spec['root'])/self.spec['case']['case_id']
                receipt=analysis_stub(self.spec['case'],case_root/'analysis')
                receipt['environment']=self.spec['environment']
                put(case_root/'receipt.json',receipt)
            return self.returncode
        def poll(self):return self.returncode
    monkeypatch.setattr(d.subprocess,'Popen',Worker)
    monkeypatch.setattr(d.frozen,'baseline_identity',lambda environment:{'synthetic_identity':True})
    monkeypatch.setattr(d.frozen,'stop_worker',lambda process,path:setattr(process,'returncode',-9))
    monkeypatch.setenv('AHAS_NETWORK_ISOLATION','linux_seccomp_socket_denial')
    return calls


def refresh_receipt(root, case_id, exit_code=None):
    execution=d.read(root/'execution.json')
    row=next(r for r in execution['cases'] if r['case_id']==case_id)
    if exit_code is not None:row['receipt']['exit_code']=exit_code
    row['receipt']['artifacts']=d.frozen.artifact_inventory(root/case_id/'analysis')
    put(root/case_id/'receipt.json',row['receipt']);put(root/'execution.json',execution)


def test_five_samples_four_fixed_histories_and_exact_alias_mask(tmp_path):
    fixture=Synthetic(tmp_path)
    assert len(d.checked_index(fixture.index)['cases'])==4
    raw=b'{"text":"the account_id word stays", "account_id" : "alias", "n":1}\n'
    record,masked=d.mask_alias(raw)
    assert record['account_id']=='alias' and masked==raw.replace(b'"alias"',b'"<uniform-case-alias>"')
    with pytest.raises(ValueError,match='Duplicate'):
        d.mask_alias(b'{"account_id":"a","account_id":"b"}')


@pytest.mark.parametrize('mutation',[
    lambda c:c.pop(),lambda c:c.reverse(),lambda c:c[0].update(source_switch=True),
    lambda c:c[0].update(truth_k=40),lambda c:c[0].update(control_junction_k=41),
    lambda c:c[0].update(case_id='../bad'),lambda c:c[0].update(anchor_id='BX'),
    lambda c:c[0].update(stratum_id='other'),lambda c:c[0].update(right_cell_id='wrong'),
    lambda c:c[0].update(prescore_qualified_windows=11),
])
def test_changed_four_case_contract_rejected(tmp_path,mutation):
    fixture=Synthetic(tmp_path);mutation(fixture.cases);fixture.refresh()
    with pytest.raises(ValueError):d.checked_index(fixture.index)


def test_shared_anchor_text_and_raw_format_cannot_change(tmp_path):
    fixture=Synthetic(tmp_path)
    fixture.mutate_input(1,lambda rows:rows[0].update(text=rows[0]['text']+' altered'))
    with pytest.raises(ValueError,match='shared anchor'):d.checked_index(fixture.index)


def test_shared_anchor_raw_byte_format_cannot_change(tmp_path):
    fixture=Synthetic(tmp_path);path=Path(fixture.cases[1]['input'])
    path.write_bytes(path.read_bytes().replace(b'"account_id": ',b'"account_id" : ',1));fixture.refresh()
    with pytest.raises(ValueError,match='shared anchor'):d.checked_index(fixture.index)


def test_duplicate_right_sample_record_ids_rejected(tmp_path):
    fixture=Synthetic(tmp_path)
    first=d.read(fixture.cases[0]['metadata'])['records'][40]['record_id']
    fixture.mutate_input(1,lambda rows:rows[40].update(id=first))
    path=fixture.cases[1]['metadata'];metadata=d.read(path);metadata['records'][40]['record_id']=first;put(path,metadata);fixture.refresh()
    with pytest.raises(ValueError,match='five distinct'):d.checked_index(fixture.index)


def test_hash_binding_refuses_changes_and_omitted_helpers(tmp_path):
    fixture=Synthetic(tmp_path);Path(fixture.cases[0]['input']).write_text('changed')
    with pytest.raises(ValueError,match='hash'):d.checked_registration(fixture.registration,fixture.index)


def test_every_frozen_helper_and_environment_must_be_bound(tmp_path):
    fixture=Synthetic(tmp_path);plan=d.read(fixture.registration);plan['bound_artifacts'].pop();put(fixture.registration,plan)
    with pytest.raises(ValueError,match='helper'):d.checked_registration(fixture.registration,fixture.index)
    fixture.refresh();plan=d.read(fixture.registration);plan['replay_environment']['TZ']='UTC';put(fixture.registration,plan)
    with pytest.raises(ValueError,match='environments'):d.checked_registration(fixture.registration,fixture.index)


def test_primary_run_and_relocated_four_case_replay(tmp_path,monkeypatch):
    fixture=Synthetic(tmp_path);calls=fake_workers(monkeypatch)
    first,replay=tmp_path/'first',tmp_path/'replay'
    d.run(fixture.registration,fixture.index,first)
    d.run(fixture.registration,fixture.index,replay,True,first)
    assert len(calls)==8 and all(c.timeout==630 for c in calls)
    assert all(c.argv[2]==str(d.P4/'run_full_chronology.py') and c.kwargs['start_new_session'] for c in calls)
    for call in calls[4:]:
        assert call.spec['environment']==d.REPLAY_ENV
        original=next(c for c in fixture.cases if c['case_id']==call.spec['case']['case_id'])
        for field in ('input','manifest'):
            assert Path(call.spec['case'][field]).parent==replay/'relocated'
            assert d.sha(call.spec['case'][field])==d.sha(original[field])
    result=d.replay_check(fixture.index,first,replay,tmp_path/'replay-check.json')
    assert result['all_passed'] and result['replayed_histories']==4
    assert all(r['canonical_file_count']==3 for r in result['cases'])


@pytest.mark.parametrize('mode,status',[('failure','worker_failed'),('timeout','worker_wall_limit')])
def test_failed_workers_preserve_all_four_and_null_outcomes(tmp_path,monkeypatch,mode,status):
    fixture=Synthetic(tmp_path);fake_workers(monkeypatch,mode)
    out=tmp_path/'run';d.run(fixture.registration,fixture.index,out)
    execution=d.read(out/'execution.json');assert len(execution['cases'])==4
    assert all(r['status']==status for r in execution['cases'])
    summary=d.score(fixture.index,out,tmp_path/'scored')
    assert summary['executed_histories']==0
    rows=d.read(tmp_path/'scored/cases.json')
    assert all(r['score']['candidate_count'] is None and r['score']['candidate_occurrence'] is None for r in rows)
    assert all(r['switch_minus_control_candidate_count'] is None for r in summary['descriptive_switch_minus_control'])


def test_constant_primary_and_ten_record_localization_saved_exact_windows(tmp_path,monkeypatch):
    fixture=Synthetic(tmp_path);fake_workers(monkeypatch)
    out=tmp_path/'run';d.run(fixture.registration,fixture.index,out)
    summary=d.score(fixture.index,out,tmp_path/'scored')
    assert summary['executed_histories']==4 and not summary['independent_replicates_estimated']
    assert all(c['switch_minus_control_candidate_occurrence']==1 for c in summary['descriptive_switch_minus_control'])
    rows=d.read(tmp_path/'scored/cases.json')
    for row in rows:
        assert row['score']['executed'] and row['primary_window_check']=='all_primary_memberships_counts_positions_verified'
        if row['source_switch']:
            assert row['score']['switch_localization']['nearest_interval_error_records']==0
            assert row['score']['switch_localization']['matched_within_tolerance']
        else:
            assert row['native_change_status']=='no_measurable_variation' and row['score']['candidate_count']==0
        assert set(row['full_pipeline_statuses'])=={'style','text','temporal'}


def test_failed_whole_pipeline_cannot_become_zero_candidates(tmp_path,monkeypatch):
    fixture=Synthetic(tmp_path);fake_workers(monkeypatch)
    out=tmp_path/'run';d.run(fixture.registration,fixture.index,out)
    refresh_receipt(out,fixture.cases[0]['case_id'],4)
    summary=d.score(fixture.index,out,tmp_path/'scored')
    rows=d.read(tmp_path/'scored/cases.json')
    assert rows[0]['score']['candidate_count'] is None
    assert summary['descriptive_switch_minus_control'][0]['switch_minus_control_candidate_count'] is None


def test_baseline_mismatch_precedes_dispatch(tmp_path,monkeypatch):
    fixture=Synthetic(tmp_path);calls=fake_workers(monkeypatch)
    def fail(env):raise ValueError('identity mismatch')
    monkeypatch.setattr(d.frozen,'baseline_identity',fail)
    with pytest.raises(ValueError,match='identity'):d.run(fixture.registration,fixture.index,tmp_path/'run')
    assert not calls and not (tmp_path/'run').exists()


def test_wall_limit_retains_four_undispatched_cases(tmp_path,monkeypatch):
    fixture=Synthetic(tmp_path);calls=fake_workers(monkeypatch)
    counter=iter([0]+[3601]*30);monkeypatch.setattr(d.time,'monotonic',lambda:next(counter))
    out=tmp_path/'run';d.run(fixture.registration,fixture.index,out)
    assert not calls and all(r['status']=='not_dispatched_wall_limit' for r in d.read(out/'execution.json')['cases'])


def test_artifact_cap_marks_effective_unavailable_and_stops_dispatch(tmp_path,monkeypatch):
    fixture=Synthetic(tmp_path);fake_workers(monkeypatch)
    monkeypatch.setattr(d.frozen,'CASE_ARTIFACT_BYTES',100)
    out=tmp_path/'run';d.run(fixture.registration,fixture.index,out)
    execution=d.read(out/'execution.json')
    assert execution['artifact_limit_reached'] and len(execution['cases'])==4
    assert any(row['status']=='not_dispatched_artifact_limit' for row in execution['cases'])
    summary=d.score(fixture.index,out,tmp_path/'scored')
    assert summary['executed_histories']==0


def test_saved_artifacts_receipts_and_exact_primary_ids_cannot_change(tmp_path,monkeypatch):
    fixture=Synthetic(tmp_path);fake_workers(monkeypatch)
    out=tmp_path/'run';d.run(fixture.registration,fixture.index,out)
    case=fixture.cases[0];result_path=out/case['case_id']/'analysis/results.json'
    result=d.read(result_path);result['modules']['style']['payload']['streams'][0]['window_ids'].pop();put(result_path,result)
    with pytest.raises(ValueError,match='artifact inventory'):d.score(fixture.index,out,tmp_path/'bad')
    refresh_receipt(out,case['case_id'])
    with pytest.raises(ValueError,match='windows differ'):d.score(fixture.index,out,tmp_path/'bad')


def test_replay_never_accepts_empty_or_missing_case_lists(tmp_path,monkeypatch):
    fixture=Synthetic(tmp_path);fake_workers(monkeypatch)
    first,replay=tmp_path/'first',tmp_path/'replay'
    d.run(fixture.registration,fixture.index,first);d.run(fixture.registration,fixture.index,replay,True,first)
    execution=d.read(replay/'execution.json');execution['cases']=[];put(replay/'execution.json',execution)
    with pytest.raises(ValueError):d.replay_check(fixture.index,first,replay,tmp_path/'check.json')


def test_saved_relocated_inputs_cannot_change(tmp_path,monkeypatch):
    fixture=Synthetic(tmp_path);fake_workers(monkeypatch)
    first,replay=tmp_path/'first',tmp_path/'replay'
    d.run(fixture.registration,fixture.index,first);d.run(fixture.registration,fixture.index,replay,True,first)
    next((replay/'relocated').glob('*.jsonl')).write_bytes(b'changed')
    with pytest.raises(ValueError,match='relocated input bytes'):
        d.replay_check(fixture.index,first,replay,tmp_path/'check.json')


def test_saved_worker_environment_must_match_start_binding(tmp_path,monkeypatch):
    fixture=Synthetic(tmp_path);fake_workers(monkeypatch)
    out=tmp_path/'run';d.run(fixture.registration,fixture.index,out)
    execution=d.read(out/'execution.json');receipt=execution['cases'][0]['receipt']
    receipt['environment']['TZ']='wrong';put(out/'execution.json',execution)
    put(out/receipt['case_id']/'receipt.json',receipt)
    with pytest.raises(ValueError,match='environment mismatch'):
        d.score(fixture.index,out,tmp_path/'scored')
