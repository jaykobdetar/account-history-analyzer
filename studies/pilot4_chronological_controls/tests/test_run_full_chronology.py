"""Synthetic boundary, process and registration checks; no original corpus."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_full_chronology as runner
from chronology_math import factorial_cases


def result(native='ok',boundary=(7,10)):
    return {'analysis':{'implementation_fingerprint':runner.FINGERPRINT,'config_sha256':runner.CONFIG},
            'modules':{'style':{'payload':{'streams':[{'scope_type':'pooled','kind':'comment','subreddit':None,'stream_id':'primary'}],
             'changes':[{'stream_id':'primary','status':native,'reason_codes':[],
                         'boundaries':[] if boundary is None else [{'record_interval':list(boundary)}]}]}}}}


def test_primary_gap_interval_conversion_and_constant_normalization():
    assert runner.extract_primary(result(),0)['candidate_intervals']==[[8,10]]
    native=result('no_measurable_variation',None)
    native['modules']['style']['payload']['changes'][0]['reason_codes']=['constant_series']
    x=runner.extract_primary(native,0)
    assert x['reason_codes']==[]
    assert x['status']=='ok' and x['native_change_status']=='no_measurable_variation' and x['candidate_intervals']==[]
    with pytest.raises(ValueError,match='Constant'):runner.extract_primary(result('no_measurable_variation'),0)


@pytest.mark.parametrize('exit_code,status',[(0,'unavailable'),(4,'resource_limit'),(2,'unavailable'),(None,'unavailable')])
def test_missing_whole_pipeline_never_executes_empty_zero(exit_code,status):
    x=runner.extract_primary(None,exit_code)
    assert x['status']==status and x['candidate_intervals']==[]


def test_missing_style_and_failed_whole_pipeline_override_native_success():
    x=result();del x['modules']['style']
    assert runner.extract_primary(x,0)['status']=='abstained'
    assert runner.extract_primary(x,4)['status']=='resource_limit'
    assert runner.extract_primary(result(),4)['status']=='resource_limit'
    assert runner.extract_primary(result('insufficient_windows',None),0)['status']=='abstained'


@pytest.mark.parametrize('which',['implementation_fingerprint','config_sha256'])
def test_identity_mismatch_rejected_even_after_resource_failure(which):
    x=result();x['analysis'][which]='wrong'
    with pytest.raises(ValueError,match='identity'):runner.extract_primary(x,4)


@pytest.mark.parametrize('boundary',[(1,1),(2,1),(-1,2),(True,2),(1.0,2)])
def test_invalid_original_boundary_rejected(boundary):
    with pytest.raises(ValueError,match='boundary'):runner.extract_primary(result(boundary=boundary),0)


def test_ambiguous_primary_stream_or_change_rejected():
    x=result();x['modules']['style']['payload']['streams']*=2
    with pytest.raises(ValueError,match='Ambiguous'):runner.extract_primary(x,0)
    x=result();x['modules']['style']['payload']['changes']*=2
    with pytest.raises(ValueError,match='Ambiguous'):runner.extract_primary(x,0)


def identity():
    return dict(implementation_fingerprint=runner.FINGERPRINT,config_sha256=runner.CONFIG,
                reference_environment=runner.REFERENCE_ENVIRONMENT,
                module_version='1.0.4',distribution_version='1.0.4',
                package_file=str(runner.INSTALLED_ROOT/'account_history_analyzer/__init__.py'),
                distribution_path=str(runner.INSTALLED_ROOT/'account_history_analyzer-1.0.4.dist-info'),
                direct_url=None)


def test_actual_probe_uses_registered_environment_and_30second_timeout(monkeypatch):
    calls=[]
    def probe(*args,**kwargs):
        calls.append((args,kwargs));return SimpleNamespace(returncode=0,stdout=json.dumps(identity()))
    monkeypatch.setattr(runner.subprocess,'run',probe)
    assert runner.baseline_identity({'PYTHONHASHSEED':'17'})==identity()
    assert calls[0][1]['timeout']==30 and calls[0][1]['env']['PYTHONHASHSEED']=='17'


@pytest.mark.parametrize('field,value',[
    ('reference_environment','dependency changed'),('distribution_version','1.0.0'),('module_version','1.0.0'),('package_file','/tmp/editable/__init__.py'),
    ('distribution_path','/tmp/other/dist-info'),('implementation_fingerprint','bad'),('config_sha256','bad'),
    ('direct_url',{'dir_info':{'editable':True}}),
])
def test_actual_baseline_probe_rejects_wrong_install(monkeypatch,field,value):
    x=identity();x[field]=value
    monkeypatch.setattr(runner.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=json.dumps(x)))
    with pytest.raises(ValueError,match='baseline identity'):runner.baseline_identity({})


def cases(blocks=1):
    return [{**r,'stratum_id':f'stratum-{i}'} for i in range(blocks) for r in factorial_cases(f'block-{i}')]


def test_exact_six_blocks_original_and_one_replay():
    index={'cases':cases(6)}
    assert len(runner.checked_cases(index,'block-0',False))==96
    assert runner.checked_cases(index,'block-0',True)==index['cases'][:16]
    assert (96+16)*runner.CASE_ARTIFACT_BYTES==56*1024**3<runner.EXPECTED_LIMITS['run_artifact_bytes']


@pytest.mark.parametrize('mutation',[
    lambda c:c.clear(),lambda c:c.pop(),lambda c:c.extend(c),
    lambda c:c[0].update(case_id='../bad'),lambda c:c[0].update(source_switch=True),
    lambda c:c[0].update(stratum_id='other'),lambda c:c[0].update(case_id=c[1]['case_id']),
])
def test_incomplete_unsafe_or_changed_design_rejected(mutation):
    rows=cases();mutation(rows)
    with pytest.raises(ValueError):runner.checked_cases({'cases':rows},'block-0',False)


def test_replay_cannot_pick_later_or_absent_block():
    for block in ('absent','block-1'):
        with pytest.raises(ValueError,match='first'):runner.checked_cases({'cases':cases(2)},block,True)


def prepared(tmp_path):
    rows=cases();bound=[]
    for row in rows:
        for field in ('input','manifest','metadata'):
            p=tmp_path/(row['case_id']+'.'+field);p.write_text('{}\n')
            row[field]=str(p);bound.append({'path':str(p),'sha256':runner.sha(p)})
    index=tmp_path/'index.json';index.write_text(json.dumps({'cases':rows,'bound_files':bound}))
    plan=dict(phase='frozen_before_chronological_execution',prepared_index_sha256=runner.sha(index),
              runner_sha256=runner.sha(runner.__file__),bound_artifacts=[],replay_block_id='block-0',
              limits=runner.EXPECTED_LIMITS,execution_environment={},replay_environment={'TZ':'Pacific/Honolulu'})
    registration=tmp_path/'registration.json';registration.write_text(json.dumps(plan))
    return registration,index


def install_fake_worker(monkeypatch,mode='success',artifact_size=3):
    calls=[]
    class Worker:
        def __init__(self,argv,**kwargs):
            self.pid=99999999;self.returncode=None;calls.append(self)
            self.spec=json.loads(Path(argv[-1]).read_bytes());self.kwargs=kwargs
        def wait(self,timeout=None):
            self.timeout=timeout
            if mode=='timeout' and self.returncode is None:raise subprocess.TimeoutExpired('synthetic',timeout)
            if self.returncode is not None:return self.returncode
            self.returncode=7 if mode=='failure' else 0
            if not self.returncode:
                spec=self.spec;root=Path(spec['root'])/spec['case']['case_id'];(root/'analysis').mkdir(parents=True)
                p=root/'analysis'/'synthetic.json';p.write_bytes(b'x'*artifact_size)
                receipt=dict(case_id=spec['case']['case_id'],exit_code=0,wall_seconds=.1,child_peak_rss_mib=1,
                             artifacts=runner.artifact_inventory(root/'analysis'))
                runner.write(root/'receipt.json',receipt)
            return self.returncode
        def poll(self):return self.returncode
    monkeypatch.setattr(runner.subprocess,'Popen',Worker)
    monkeypatch.setattr(runner,'baseline_identity',lambda env:identity())
    monkeypatch.setenv('AHAS_NETWORK_ISOLATION','linux_seccomp_socket_denial')
    return calls


def test_dispatch_complete_replay_relocates_bytes_and_binds_identity(tmp_path,monkeypatch):
    paths=prepared(tmp_path);calls=install_fake_worker(monkeypatch)
    out=tmp_path/'out';runner.run(*paths,out,replay=True)
    rows=json.loads((out/'execution.json').read_bytes())
    binding=json.loads((out/'start-binding.json').read_bytes())
    assert len(calls)==len(rows['cases'])==16 and rows['artifact_bytes']==48
    assert all(p.timeout==630 and p.kwargs['start_new_session'] for p in calls)
    assert binding['actual_baseline_identity']==identity() and binding['replay']
    original=json.loads(paths[1].read_bytes())['cases']
    for process,case in zip(calls,original):
        for field in ('input','manifest'):
            relocated=Path(process.spec['case'][field]);assert relocated.parent==out/'relocated'
            assert runner.sha(relocated)==runner.sha(case[field])


def test_dispatch_worker_failures_preserve_all_planned_rows(tmp_path,monkeypatch):
    paths=prepared(tmp_path);install_fake_worker(monkeypatch,'failure')
    monkeypatch.setattr(runner,'stop_worker',lambda *a:None)
    out=tmp_path/'out';runner.run(*paths,out)
    rows=json.loads((out/'execution.json').read_bytes())['cases']
    assert len(rows)==16 and all(r['status']=='worker_failed' and r['exit_code']==7 for r in rows)


def test_dispatch_outer_timeout_reaps_and_preserves_failures(tmp_path,monkeypatch):
    paths=prepared(tmp_path);calls=install_fake_worker(monkeypatch,'timeout');stopped=[]
    def stop(process,path):stopped.append(process);process.returncode=-9
    monkeypatch.setattr(runner,'stop_worker',stop)
    out=tmp_path/'out';runner.run(*paths,out)
    rows=json.loads((out/'execution.json').read_bytes())['cases']
    assert len(stopped)==16 and all(r['status']=='worker_wall_limit' and r['exit_code']==4 for r in rows)


def test_artifact_limit_stops_future_dispatch_and_keeps_manifest(tmp_path,monkeypatch):
    paths=prepared(tmp_path);install_fake_worker(monkeypatch,artifact_size=11)
    monkeypatch.setattr(runner,'CASE_ARTIFACT_BYTES',10)
    out=tmp_path/'out';runner.run(*paths,out)
    result=json.loads((out/'execution.json').read_bytes())
    assert len(result['cases'])==16 and result['artifact_limit_reached']
    assert any(r['status']=='not_dispatched_artifact_limit' for r in result['cases'])


def test_dispatch_wall_limit_keeps_undispatched_rows(tmp_path,monkeypatch):
    paths=prepared(tmp_path);calls=install_fake_worker(monkeypatch)
    counter=iter([0]+[7201]*100)
    monkeypatch.setattr(runner.time,'monotonic',lambda:next(counter))
    out=tmp_path/'out';runner.run(*paths,out)
    result=json.loads((out/'execution.json').read_bytes())
    assert not calls and len(result['cases'])==16
    assert all(r['status']=='not_dispatched_wall_limit' for r in result['cases'])


def test_baseline_failure_precedes_output_root_or_worker(tmp_path,monkeypatch):
    paths=prepared(tmp_path);calls=install_fake_worker(monkeypatch)
    monkeypatch.setattr(runner,'baseline_identity',lambda env:(_ for _ in ()).throw(ValueError('identity')))
    out=tmp_path/'out'
    with pytest.raises(ValueError,match='identity'):runner.run(*paths,out)
    assert not out.exists() and not calls


def test_unbound_input_rejected_before_probe(tmp_path,monkeypatch):
    registration,index=prepared(tmp_path)
    x=json.loads(index.read_bytes());x['bound_files'].pop();index.write_text(json.dumps(x))
    p=json.loads(registration.read_bytes());p['prepared_index_sha256']=runner.sha(index);registration.write_text(json.dumps(p))
    monkeypatch.setenv('AHAS_NETWORK_ISOLATION','linux_seccomp_socket_denial')
    with pytest.raises(ValueError,match='must be bound'):runner.run(registration,index,tmp_path/'out')


def test_stop_worker_kills_both_groups_and_checks_pid_start(tmp_path,monkeypatch):
    runner.write(tmp_path/'child-process.json',{'pid':123,'start_ticks':'456'})
    killed=[];waits=[]
    monkeypatch.setattr(runner,'process_start_ticks',lambda pid:'456')
    monkeypatch.setattr(runner,'kill_group',killed.append)
    process=SimpleNamespace(pid=789,wait=lambda timeout:waits.append(timeout))
    runner.stop_worker(process,tmp_path)
    assert killed==[123,789] and waits==[5]
    killed.clear();monkeypatch.setattr(runner,'process_start_ticks',lambda pid:'changed')
    runner.stop_worker(process,tmp_path)
    assert killed==[789]


def test_primary_window_ids_keep_declared_remainder_membership():
    x=result();x['modules']['style']['payload']['streams'][0]['window_ids']=['primary-1','remainder-2']
    assert runner.extract_primary(x,0)['primary_window_ids']==['primary-1','remainder-2']
    assert runner.extract_primary(None,4)['primary_window_ids'] is None


def test_fresh_worker_inner_timeout_maps_to_resource_and_preserves_native_exit(tmp_path,monkeypatch):
    calls=[];killed=[];limits=[]
    class Child:
        pid=99999998
        def __init__(self,argv,**kwargs):calls.append(kwargs);self.n=0
        def wait(self,timeout=None):
            self.n+=1
            if self.n==1:
                assert timeout==600
                raise subprocess.TimeoutExpired('synthetic',timeout)
            return -9
    monkeypatch.setattr(runner.subprocess,'Popen',Child)
    monkeypatch.setattr(runner.resource,'setrlimit',lambda *args:limits.append(args))
    monkeypatch.setattr(runner.signal,'signal',lambda *args:None)
    monkeypatch.setattr(runner,'kill_group',killed.append)
    monkeypatch.setattr(runner,'process_start_ticks',lambda pid:'synthetic-start')
    runner.worker({'case_id':'synthetic','input':'synthetic-input','manifest':'synthetic-manifest'},tmp_path,runner.EXPECTED_LIMITS,{})
    receipt=json.loads((tmp_path/'synthetic/receipt.json').read_bytes())
    assert receipt['exit_code']==4 and receipt['analyzer_exit_code']==-9
    assert receipt['external_wall_limit_reached'] and not receipt['external_artifact_limit_reached']
    assert killed==[Child.pid,Child.pid] and calls[0]['start_new_session']
    assert limits[0][1]==(4*1024**3,)*2


def test_remaining_global_time_bounds_worker_timeout(tmp_path,monkeypatch):
    paths=prepared(tmp_path);calls=install_fake_worker(monkeypatch)
    values=iter([0]+[7190]*100)
    monkeypatch.setattr(runner.time,'monotonic',lambda:next(values))
    runner.run(*paths,tmp_path/'out')
    assert len(calls)==16 and all(c.timeout==10 for c in calls)
