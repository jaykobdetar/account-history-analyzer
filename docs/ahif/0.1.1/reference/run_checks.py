#!/usr/bin/env python3
"""Reproducible local format checks. No collection, projection or analysis."""
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import validate_bundle as v

ROOT=v.ROOT
REPO=ROOT.parents[2]
CHECKS=ROOT/'checks'
HISTORY=ROOT.parent/'history/0.1.0'


def hash_files(root,folders):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in folders for p in sorted((root/folder).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


def command(args,cwd=REPO):
    result=subprocess.run(args,cwd=cwd,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},
                          capture_output=True,text=True,timeout=60)
    return {'command':args,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}


def main():
    CHECKS.mkdir(exist_ok=True)
    result={'package':'AHIF 0.1.1 reviewed contract','started_at':datetime.now(timezone.utc).isoformat(),
            'python':sys.version,'dependencies':{p:version(p) for p in ('jsonschema','referencing','account-history-analyzer')},
            'status':'failed','projection_status':'not_implemented','analysis_executed':False}
    ok=True
    try:
        stream=io.StringIO()
        tests=unittest.defaultTestLoader.discover(str(ROOT/'reference'),pattern='test_*.py')
        run=unittest.TextTestRunner(stream=stream,verbosity=2).run(tests)
        (CHECKS/'tests.log').write_text(stream.getvalue())
        result['unit_tests']={'run':run.testsRun,'failures':len(run.failures),'errors':len(run.errors),'skipped':len(run.skipped)}
        ok &= run.wasSuccessful()
        result['negative_fixture_recipes']=len(json.loads((ROOT/'fixtures/negative-cases.json').read_text()))
        result['bundles']={p.name:v.validate_bundle(p,require_canonical=True)
                          for p in sorted((ROOT/'examples').iterdir()) if p.is_dir()}
        cli_good=command([sys.executable,str(ROOT/'reference/validate_bundle.py'),str(ROOT/'examples/review-cases'),'--canonical'])
        cli_old=command([sys.executable,str(ROOT/'reference/validate_bundle.py'),str(HISTORY/'examples/minimal')])
        result['cli_checks']={'canonical_bundle_returncode':cli_good['returncode'],
                              'unsupported_010_returncode':cli_old['returncode']}
        (CHECKS/'cli.log').write_text(json.dumps([cli_good,cli_old],indent=2)+'\n')
        ok &= cli_good['returncode']==0 and cli_old['returncode']==2
        # Regenerate only in an isolated temporary directory; never edit history.
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'0.1.1';shutil.copytree(ROOT/'reference',target/'reference')
            (target/'schemas').mkdir()
            commands=[command([sys.executable,str(target/'reference'/script)])
                      for script in ('build_schemas.py','build_examples.py')]
            original=hash_files(ROOT,['schemas','examples']);generated=hash_files(target,['schemas','examples'])
            match=original==generated
            result['regeneration']={'files_compared':len(original),'byte_identical':match,
                                    'commands_succeeded':all(c['returncode']==0 for c in commands)}
            (CHECKS/'regeneration.log').write_text(json.dumps(commands,indent=2)+'\n')
            ok &= match and all(c['returncode']==0 for c in commands)
        expected=json.loads((CHECKS/'frozen-boundary.json').read_text())['files']
        mismatches=[name for name,h in expected.items() if not (REPO/name).is_file() or hashlib.sha256((REPO/name).read_bytes()).hexdigest()!=h]
        current=hash_files(REPO,['src','schemas','config','resources'])
        expected_core={name:h for name,h in expected.items() if name.split('/')[0] in ('src','schemas','config','resources')}
        added=sorted(set(current)-set(expected_core))
        result['frozen_boundary']={'files_compared':len(expected),'mismatches':mismatches,'unexpected_core_files':added,'unchanged':not mismatches and not added}
        ok &= not mismatches and not added
        historical=json.loads((CHECKS/'historical-members.json').read_text())
        historical_now=hash_files(HISTORY,['.'])
        checksum_count=0
        for line in (HISTORY/'SHA256SUMS.txt').read_text().splitlines():
            h,name=line.split('  ',1)
            if historical_now.get(name)!=h: raise AssertionError('Historical checksum mismatch: '+name)
            checksum_count+=1
        result['historical_preservation']={'members':len(historical),'manifest_checksums_verified':checksum_count,'byte_identical':historical_now==historical}
        ok &= historical_now==historical
        old=command([sys.executable,'-m','unittest','discover','-s',str(HISTORY/'reference'),'-v'])
        (CHECKS/'historical-rerun.log').write_text(old['stdout']+old['stderr'])
        result['historical_rerun']={'returncode':old['returncode'],'log':'historical-rerun.log','scope':'Original 0.1.0 tests; not evidence of production support.'}
        ok &= old['returncode']==0
        node=shutil.which('node')
        if node:
            values=[{'z':n,'a':text,'2':'numeric-looking property','11':[None,True,False]} for n in (-9007199254740991,-1,0,1,9007199254740991)
                    for text in ('',''.join(chr(i) for i in range(32)),'é e\u0301 😀 \u2028 \u0085 \u2029','"\\/','literal \n whitespace  ')]
            # Direct recursive serializer is required: JS object enumeration
            # reorders numeric-looking keys even after property insertion sort.
            js="""const fs=require('fs');
const c=x=>x===null||typeof x!=='object'?JSON.stringify(x):Array.isArray(x)?'['+x.map(c).join(',')+']':'{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+c(x[k])).join(',')+'}';
process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(x=>Buffer.from(c(x),'utf8').toString('hex'))));"""
            proc=subprocess.run([node,'-e',js],input=json.dumps(values),capture_output=True,text=True,timeout=30)
            same=proc.returncode==0 and json.loads(proc.stdout)==[v.canonical(x).hex() for x in values]
            result['restricted_canonical_cross_runtime']={'status':'passed' if same else 'failed','node':command([node,'--version'])['stdout'].strip(),'vectors':len(values),'full_rfc8785_suite':False}
            ok &= same
        else:
            result['restricted_canonical_cross_runtime']={'status':'not_run','reason':'Node unavailable','full_rfc8785_suite':False}
        result['input_hashes']=hash_files(ROOT,['reference','schemas','examples','fixtures'])
        result['input_hashes'].update({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.glob('*.md'))})
        result['not_executed']=['Production AHAS numerical analysis or scientific pilot','Real-account collection or evidence access',
            'Source normalizer or projection implementation','Evidence authenticity or locator verification',
            'Full BCP-47 registry or general JCS compliance suite','Production untrusted ingestion/security audit',
            'Commit, push, release build or publication']
        result['status']='passed_for_exercised_checks' if ok else 'failed'
    except Exception as exc:
        result['error']=type(exc).__name__+': '+str(exc)
        ok=False
    result['finished_at']=datetime.now(timezone.utc).isoformat()
    (CHECKS/'verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:result[k] for k in ('status','unit_tests','regeneration','frozen_boundary','historical_preservation','restricted_canonical_cross_runtime') if k in result},indent=2))
    if 'error' in result: print(result['error'])
    return 0 if ok else 1

if __name__=='__main__': raise SystemExit(main())
