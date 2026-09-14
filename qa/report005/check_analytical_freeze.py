"""REPORT005 operational fixture run and strict 1.0.2 analytical freeze check.

Run only after the new implementation fingerprint is frozen. Historical reports,
source and old QA scripts are read-only inputs to this driver.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
QA=ROOT/'qa/report005'
NEW=ROOT/'output/report005'
OLD=ROOT/'output/audit-repair'
FIXTURES=('arithmetic','constructed_style_shift','constructed_topic_shift','edge_cases','empty','stable_constructed_style')
UNCHANGED=('resolved_config.json','method_registry.json','records_features.jsonl','windows.jsonl','evidence.jsonl',
           'activity_daily.svg','activity_hourly.svg','eligible_word_volume.svg','surface_features.svg','adjacent_distances.svg')
ALLOWED={('analysis','suite_version'),('analysis','implementation_fingerprint'),('analysis','resource_sha256','report_templates')}
OLD_FP='583043074c28db2c91b62c33dc0197a569e863f4c83a80197c509324d9cb4fac'


def canonical(obj):
    return (json.dumps(obj,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode()


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(65536),b''):
            h.update(block)
    return h.hexdigest()


def differences(left,right,path=()):
    if type(left) is not type(right):
        return [path]
    if isinstance(left,dict):
        if left.keys()!=right.keys():
            return [path+('<keys>',)]
        return [p for key in sorted(left) for p in differences(left[key],right[key],path+(key,))]
    if isinstance(left,list):
        if len(left)!=len(right):
            return [path+('<length>',)]
        return [p for i,(a,b) in enumerate(zip(left,right,strict=True)) for p in differences(a,b,path+(str(i),))]
    return [] if left==right else [path]


def without_release_metadata(result):
    copy=deepcopy(result)
    for path in ALLOWED:
        target=copy
        for key in path[:-1]:
            target=target[key]
        del target[path[-1]]
    return copy


def compare(expected):
    summary={'scope':'REPORT005 strict analytical freeze relative to preserved 1.0.2 fixture reports',
        'status':'pending','old_suite_version':'1.0.2','new_suite_version':'1.0.3',
        'old_implementation_fingerprint':OLD_FP,'new_implementation_fingerprint':expected,
        'allowed_changed_paths':['.'.join(path) for path in sorted(ALLOWED)],
        'unchanged_artifact_names':list(UNCHANGED),'measurement_or_finding_exceptions':[],
        'truth_sidecars_read':False,'fixtures':[]}
    destination=QA/'analytical-freeze.json'
    assert not destination.exists(), 'Refusing to overwrite analytical freeze receipt'
    try:
        for fixture in FIXTURES:
            before=OLD/fixture;after=NEW/fixture
            old=json.loads((before/'results.json').read_bytes())
            new=json.loads((after/'results.json').read_bytes())
            assert old['analysis']['suite_version']=='1.0.2'
            assert new['analysis']['suite_version']=='1.0.3'
            assert old['analysis']['implementation_fingerprint']==OLD_FP
            assert new['analysis']['implementation_fingerprint']==expected
            changed=set(differences(old,new))
            assert changed==ALLOWED, fixture+': unexpected changed paths '+repr(sorted(changed))
            analytical_old=canonical(without_release_metadata(old))
            analytical_new=canonical(without_release_metadata(new))
            assert analytical_old==analytical_new, fixture+': analytical payload changed'
            artifacts=[]
            for name in UNCHANGED:
                before_sha,after_sha=sha(before/name),sha(after/name)
                assert (before/name).read_bytes()==(after/name).read_bytes(), fixture+': changed '+name
                artifacts.append({'name':name,'bytes':(after/name).stat().st_size,'sha256':after_sha,'byte_identical':True})
            summary['fixtures'].append({'fixture':fixture,'status':'passed',
                'old_results_sha256':sha(before/'results.json'),'new_results_sha256':sha(after/'results.json'),
                'exact_changed_paths':['.'.join(path) for path in sorted(changed)],
                'all_remaining_results_equal':True,'frozen_analytical_payload_sha256':hashlib.sha256(analytical_new).hexdigest(),
                'modules_and_findings_equal':old['modules']==new['modules'] and old['findings']==new['findings'],
                'unchanged_artifacts':artifacts,
                'old_report_templates_sha256':old['analysis']['resource_sha256']['report_templates'],
                'new_report_templates_sha256':new['analysis']['resource_sha256']['report_templates']})
        summary['status']='passed'
        summary['unchanged_artifact_comparison_count']=len(FIXTURES)*len(UNCHANGED)
    except Exception as exc:
        summary['status']='failed';summary['error']={'type':type(exc).__name__,'message':str(exc)}
        destination.write_bytes(canonical(summary))
        raise
    destination.write_bytes(canonical(summary))
    print(json.dumps({'status':'passed','fixture_results_analytically_frozen':6,'byte_identical_artifacts':60}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-fingerprint',required=True)
    parser.add_argument('--compare-only',action='store_true')
    args=parser.parse_args()
    if not args.compare_only:
        log=QA/'fixture-driver.log';receipt_path=QA/'fixture-command.json'
        assert not log.exists() and not receipt_path.exists(), 'Refusing to overwrite command receipt'
        assert not NEW.exists(), 'Refusing to overwrite fixture outputs'
        argv=[str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/offline_exec.py'),str(ROOT/'.venv/bin/python'),
            str(ROOT/'scripts/check_audit_fixture_reports.py'),'--outroot',str(NEW),'--qa',str(QA),
            '--expected-fingerprint',args.expected_fingerprint]
        env={key:value for key,value in os.environ.items() if key!='PYTHONPATH'}
        start=time.perf_counter()
        with log.open('xb') as output:
            result=subprocess.run(argv,cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT)
        receipt={'argv':argv,'cwd':str(ROOT),'exit_code':result.returncode,'elapsed_seconds':time.perf_counter()-start,
            'timing_scope':'Operational duration; other release QA may run concurrently.',
            'network_isolation':'linux_seccomp_socket_denial','log_path':str(log),'log_sha256':sha(log),
            'expected_implementation_fingerprint':args.expected_fingerprint}
        receipt_path.write_bytes(canonical(receipt))
        if result.returncode:
            raise RuntimeError('Fixture driver failed; see '+str(log))
    compare(args.expected_fingerprint)


if __name__=='__main__':
    main()
