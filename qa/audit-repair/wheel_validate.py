"""Independent frozen 1.0.2 wheel rebuild/install/analysis verification receipt."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import time
import zipfile

ROOT=Path(__file__).resolve().parents[2]
QA=ROOT/'qa/audit-repair'
UV='/home/jaykob/.local/bin/uv'
CACHE='/tmp/ahas-uv-cache'
INSTALL=Path('/tmp/ahas-audit-install')
WHEEL=ROOT/'dist/account_history_analyzer-1.0.2-py3-none-any.whl'
SDIST=ROOT/'dist/account_history_analyzer-1.0.2.tar.gz'
EXPECTED='583043074c28db2c91b62c33dc0197a569e863f4c83a80197c509324d9cb4fac'
RECEIPT=QA/'wheel-verification.json'
REPORT=QA/'wheel-output/arithmetic'
SOURCE=ROOT/'output/audit-repair/arithmetic'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save():
    RECEIPT.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')


def run(name,argv,*,cwd=ROOT,seccomp=False,extra_env=None):
    if seccomp:
        argv=['/usr/bin/python3.12',str(ROOT/'scripts/offline_exec.py'),*argv]
    argv=[str(x) for x in argv]
    log=QA/(name+'.log')
    assert not log.exists(), 'Refusing to overwrite '+str(log)
    env={k:v for k,v in os.environ.items() if k!='PYTHONPATH'}
    env.update(extra_env or {})
    start=time.perf_counter()
    with log.open('xb') as output:
        completed=subprocess.run(argv,cwd=cwd,env=env,stdout=output,stderr=subprocess.STDOUT)
    entry={'name':name,'argv':argv,'cwd':str(cwd),'environment_overrides':extra_env or {},
           'exit_code':completed.returncode,'elapsed_seconds':time.perf_counter()-start,
           'log_path':str(log),'log_sha256':sha(log)}
    receipt['commands'].append(entry);save()
    print(json.dumps({'step':name,'exit_code':completed.returncode,'elapsed_seconds':entry['elapsed_seconds']}),flush=True)
    if completed.returncode:
        raise RuntimeError(f'{name} failed; inspect {log}')
    return log


def compare():
    if not (SOURCE/'checksums.json').exists():
        receipt['status']='passed_pending_source_comparison'
        save()
        print(json.dumps({'status':receipt['status'],'source':str(SOURCE)}),flush=True)
        return
    canonical=set(json.loads((SOURCE/'checksums.json').read_bytes()))|{'checksums.json'}
    installed=set(json.loads((REPORT/'checksums.json').read_bytes()))|{'checksums.json'}
    assert canonical==installed and len(canonical)==14
    rows=[]
    for name in sorted(canonical):
        assert (SOURCE/name).read_bytes()==(REPORT/name).read_bytes(), 'Canonical mismatch: '+name
        rows.append({'name':name,'bytes':(SOURCE/name).stat().st_size,'sha256':sha(SOURCE/name),'byte_identical':True})
    receipt['canonical_comparison']={'status':'passed','source_directory':str(SOURCE),'wheel_directory':str(REPORT),
        'compared_file_count':14,'files':rows,'excluded_receipts':['ingest_receipt.json','run_receipt.json'],
        'scope':'Every checksummed canonical artifact plus checksums.json; operational receipts excluded.'}
    receipt['status']='passed';save()
    print(json.dumps({'status':'passed','canonical_files':14,'wheel_sha256':sha(WHEEL)}),flush=True)


parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--compare-only',action='store_true')
args=parser.parse_args()
if args.compare_only:
    receipt=json.loads(RECEIPT.read_bytes())
    assert receipt['status']=='passed_pending_source_comparison'
else:
    assert not RECEIPT.exists(), 'Refusing to replace previous receipt'
    assert not INSTALL.exists(), 'Fresh environment already exists'
    receipt={'suite_version':'1.0.2','status':'in_progress','commands':[],
        'invocation':[sys.executable,*sys.argv],
        'expected_implementation_fingerprint':EXPECTED,
        'network_isolation':{'build_and_install':'uv --offline, cached hash-locked requirements; local IPC available',
            'installed_probe_analysis_recomputation':'linux_seccomp_socket_denial'},
        'timing_scope':'Operational durations while other QA may run; not performance measurements.',
        'historical_preservation':'No previous release, historical output or receipt overwritten.',
        'wheel':{'path':str(WHEEL),'sha256':sha(WHEEL),'bytes':WHEEL.stat().st_size},
        'sdist':{'path':str(SDIST),'sha256':sha(SDIST),'bytes':SDIST.stat().st_size},
        'lockfiles':{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'requirements.lock.txt',ROOT/'containers/build-requirements.lock')},
        'canonical_comparison':{'status':'pending_source_report'}}
try:
    if not args.compare_only:
        save()
        for label,seed,tz,cwd in [('a','1','UTC',ROOT),('b','773','Asia/Tokyo',Path('/tmp'))]:
            out=QA/('wheel-build-'+label)
            assert not out.exists(), 'Refusing to replace build destination'
            run('wheel-isolated-build-'+label,[UV,'build',SDIST,'--wheel','--out-dir',out,'--python',ROOT/'.venv/bin/python',
                '--offline','--no-python-downloads','--cache-dir',CACHE,'--build-constraints',ROOT/'containers/build-requirements.lock',
                '--require-hashes','--link-mode','copy','--no-progress'],cwd=cwd,extra_env={'PYTHONHASHSEED':seed,'TZ':tz})
        rebuilt=[QA/('wheel-build-'+label)/WHEEL.name for label in ('a','b')]
        assert all(p.read_bytes()==WHEEL.read_bytes() for p in rebuilt), 'Rebuilt wheels differ'
        receipt['rebuilt_wheels']=[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in rebuilt]
        receipt['wheel_bytes_identical']=True;save()
        run('wheel-fresh-venv',[UV,'venv',INSTALL,'--python',ROOT/'.venv/bin/python','--offline','--no-python-downloads','--cache-dir',CACHE])
        run('wheel-locked-dependencies',[UV,'pip','install','--python',INSTALL/'bin/python','--offline','--require-hashes',
            '--cache-dir',CACHE,'--link-mode','copy','-r',ROOT/'requirements.lock.txt','-r',ROOT/'containers/build-requirements.lock'])
        requirements=QA/'wheel-install.requirements.txt'
        requirements.write_text(f'account-history-analyzer @ {WHEEL.as_uri()} --hash=sha256:{sha(WHEEL)}\n')
        run('wheel-package-install',[UV,'pip','install','--python',INSTALL/'bin/python','--offline','--require-hashes','--no-deps',
            '--cache-dir',CACHE,'--link-mode','copy','-r',requirements],cwd=Path('/tmp'))
        probe='''import ast, hashlib, inspect, json, pathlib, sys
import importlib.metadata as metadata
import account_history_analyzer as a
from account_history_analyzer.pipeline import implementation_identity
from account_history_analyzer._vendor.ruptures_pr383 import PeltMinSize
from account_history_analyzer.changepoints import pelt_l2
from ruptures import Pelt
import numpy as np
path=pathlib.Path(a.__file__).resolve()
assert path.is_relative_to(pathlib.Path('/tmp/ahas-audit-install/lib/python3.12/site-packages'))
assert a.__version__==metadata.version('account-history-analyzer')=='1.0.2'
fp,environment,resources=implementation_identity()
assert fp=='583043074c28db2c91b62c33dc0197a569e863f4c83a80197c509324d9cb4fac'
vendor=path.parent/'_vendor'
provenance=json.loads((vendor/'ruptures_pr383.json').read_bytes())
source=(vendor/'ruptures_pr383_source.txt').read_bytes()
method=inspect.getsource(PeltMinSize._seg).encode()
assert provenance['commit']=='a28574d9e63b0c2a966e176a1d049d3c9deaaaaf'
assert provenance['source_sha256']==hashlib.sha256(source).hexdigest()
assert provenance['method_sha256']==hashlib.sha256(method).hexdigest()
assert provenance['license_sha256']==hashlib.sha256((vendor/'ruptures_LICENSE.txt').read_bytes()).hexdigest()
source_class=next(x for x in ast.parse(source).body if isinstance(x,ast.ClassDef) and x.name=='Pelt')
source_method=next(x for x in source_class.body if isinstance(x,ast.FunctionDef) and x.name=='_seg')
original=b''.join(source.splitlines(keepends=True)[source_method.lineno-1:source_method.end_lineno])
assert original==method
assert PeltMinSize.__bases__==(Pelt,)
signal=np.array([0,9,2,8,3,0,10],dtype=float)
assert Pelt(model='l2',min_size=3,jump=1).fit_predict(signal,.1)==[4,7]
result=pelt_l2(signal,.1)
assert result['internal_boundaries']==[3] and result['objective']==107.51666666666667
print(json.dumps({'module_file':str(path),'python':sys.version,'version':a.__version__,
'implementation_fingerprint':fp,'reference_environment':environment,'resource_sha256':resources,
'installed_distributions':{d.metadata['Name']:d.version for d in metadata.distributions()},
'vendor_method_exact':True,'vendor_provenance':provenance,'stock_ruptures_unmodified':True,
'optimizer_counterexample':result},sort_keys=True))'''
        log=run('wheel-installed-probe',[INSTALL/'bin/python','-c',probe],cwd=Path('/tmp'),seccomp=True)
        receipt['installed_probe']=json.loads(log.read_bytes())
        with zipfile.ZipFile(WHEEL) as wheel,tarfile.open(SDIST,'r:gz') as sdist:
            receipt['vendor_files']=[]
            for name in ('__init__.py','ruptures_pr383.py','ruptures_pr383.json','ruptures_LICENSE.txt','ruptures_pr383_source.txt'):
                member='account_history_analyzer/_vendor/'+name
                raw=wheel.read(member)
                assert (ROOT/'src'/member).read_bytes()==raw
                assert (Path(receipt['installed_probe']['module_file']).parent/'_vendor'/name).read_bytes()==raw
                assert sdist.extractfile('account_history_analyzer-1.0.2/src/'+member).read()==raw
                receipt['vendor_files'].append({'wheel_member':member,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),
                    'matches_source_sdist_and_installed':True})
            upstream=sdist.extractfile('account_history_analyzer-1.0.2/tests/vendor_pr383/test_pelt_min_size.py').read().decode()
            upstream=upstream.split('\n',4)[4].replace('from account_history_analyzer._vendor.ruptures_pr383 import PeltMinSize as Pelt','from ruptures import Pelt')
            assert hashlib.sha256(upstream.encode()).hexdigest()==receipt['installed_probe']['vendor_provenance']['upstream_tests_sha256']
            receipt['upstream_tests_provenance_matches_sdist']=True
        save()
        run('wheel-installed-analyze',[INSTALL/'bin/ahas','analyze','--input',ROOT/'fixtures/arithmetic.jsonl',
            '--manifest',ROOT/'fixtures/arithmetic.snapshot.json','--out',REPORT],cwd=Path('/tmp'),seccomp=True)
        log=run('wheel-installed-verify-recompute',[INSTALL/'bin/ahas','verify','--input',ROOT/'fixtures/arithmetic.jsonl',
            '--manifest',ROOT/'fixtures/arithmetic.snapshot.json','--analysis-dir',REPORT,'--recompute'],cwd=Path('/tmp'),seccomp=True)
        receipt['verification']=json.loads(log.read_bytes())
        assert receipt['verification']['status']=='reproduced'
        save()
    compare()
except Exception as exc:
    receipt['status']='failed';receipt['error']=str(exc);save();raise
