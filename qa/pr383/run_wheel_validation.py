"""Operational PR383 wheel validation; does not edit package or old receipts."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
QA = ROOT/'qa/pr383'
UV = '/home/jaykob/.local/bin/uv'
CACHE = '/tmp/ahas-uv-cache'
INSTALL = Path('/tmp/ahas-pr383-install')
WHEEL = ROOT/'dist/account_history_analyzer-1.0.1-py3-none-any.whl'
SDIST = ROOT/'dist/account_history_analyzer-1.0.1.tar.gz'
EXPECTED = '4ec887e4ecc344fbd9561c9cb3fc2fc9e95fe1f3a582409826d70ac5315f8a61'
RECEIPT = QA/'wheel-verification.json'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

receipt = {'suite_version':'1.0.1', 'status':'in_progress',
           'network_isolation':{'build_and_install':'uv --offline with hash-locked cached requirements','installed_analysis_and_verification':'linux_seccomp_socket_denial'},
           'prior_failed_attempt_receipt':str(QA/'wheel-verification-seccomp-attempt.json'),
           'invocation':['python3.12',str(Path(__file__).resolve())],
           'commands':[], 'wheel':{'path':str(WHEEL),'sha256':sha(WHEEL),'bytes':WHEEL.stat().st_size},
           'sdist':{'path':str(SDIST),'sha256':sha(SDIST),'bytes':SDIST.stat().st_size},
           'expected_implementation_fingerprint':EXPECTED,
           'canonical_comparison':{'status':'pending_source_report'},
           'historical_artifacts':'No 1.0.0 distribution or historical receipt was modified.'}

def save():
    RECEIPT.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')

def run(name, argv, cwd=ROOT):
    if name.startswith('wheel-installed-'):
        argv=['python3.12',str(ROOT/'scripts/offline_exec.py'),*argv]
    log=QA/(name+'.log')
    start=time.perf_counter()
    env={key:value for key,value in os.environ.items() if key != 'PYTHONPATH'}
    with log.open('wb') as output:
        completed=subprocess.run(argv,cwd=cwd,env=env,stdout=output,stderr=subprocess.STDOUT)
    record={'name':name,'argv':[str(v) for v in argv],'cwd':str(cwd),'exit_code':completed.returncode,
            'elapsed_seconds':time.perf_counter()-start,'log_path':str(log),'log_sha256':sha(log)}
    receipt['commands'].append(record)
    save()
    print(json.dumps({'step':name,'exit_code':completed.returncode,'elapsed_seconds':record['elapsed_seconds']}),flush=True)
    if completed.returncode:
        receipt['status']='failed'
        save()
        raise RuntimeError(f'{name} failed; inspect {log}')
    return log

try:
    assert not INSTALL.exists(), 'Fresh install target already exists; refusing to alter it'
    save()
    for label in ('a','b'):
        run('wheel-isolated-build-'+label+'-offline',[UV,'build',str(SDIST),'--wheel','--out-dir',str(QA/('wheel-build-'+label)),
            '--python',str(ROOT/'.venv/bin/python'),'--offline','--no-python-downloads','--cache-dir',CACHE,
            '--build-constraints',str(ROOT/'containers/build-requirements.lock'),'--require-hashes','--link-mode','copy','--no-progress'])
    builds=[QA/('wheel-build-'+label)/WHEEL.name for label in ('a','b')]
    receipt['rebuilt_wheels']=[{'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size} for path in builds]
    receipt['wheel_bytes_identical']=all(path.read_bytes()==WHEEL.read_bytes() for path in builds)
    assert receipt['wheel_bytes_identical'], 'Isolated rebuild differs from distribution wheel'
    save()
    run('wheel-fresh-venv',[UV,'venv',str(INSTALL),'--python',str(ROOT/'.venv/bin/python'),
         '--offline','--no-python-downloads','--cache-dir',CACHE])
    run('wheel-locked-dependencies',[UV,'pip','install','--python',str(INSTALL/'bin/python'),
         '--offline','--require-hashes','--cache-dir',CACHE,'--link-mode','copy',
         '-r',str(ROOT/'requirements.lock.txt'),'-r',str(ROOT/'containers/build-requirements.lock')])
    locked=QA/'wheel-install.requirements.txt'
    locked.write_text(f'account-history-analyzer @ {WHEEL.as_uri()} --hash=sha256:{sha(WHEEL)}\n')
    run('wheel-package-install',[UV,'pip','install','--python',str(INSTALL/'bin/python'),'--offline',
         '--require-hashes','--no-deps','--cache-dir',CACHE,'--link-mode','copy','-r',str(locked)],cwd=Path('/tmp'))
    probe = '''import account_history_analyzer as a, importlib.metadata as m, json, pathlib, sys
from account_history_analyzer.pipeline import implementation_identity
from account_history_analyzer.changepoints import pelt_l2
path=pathlib.Path(a.__file__).resolve()
assert path.is_relative_to(pathlib.Path('/tmp/ahas-pr383-install/lib/python3.12/site-packages'))
assert a.__version__=='1.0.1'
fp,env,resources=implementation_identity()
assert fp=='4ec887e4ecc344fbd9561c9cb3fc2fc9e95fe1f3a582409826d70ac5315f8a61'
result=pelt_l2([0,9,2,8,3,0,10],.1)
assert result['internal_boundaries']==[3]
print(json.dumps({'module_file':str(path),'python':sys.version,'version':a.__version__,
'implementation_fingerprint':fp,'reference_environment':env,'resource_sha256':resources,
'installed_distributions':{d.metadata['Name']:d.version for d in m.distributions()},
'optimizer_counterexample':result},sort_keys=True))'''
    log=run('wheel-installed-probe',[str(INSTALL/'bin/python'),'-c',probe],cwd=Path('/tmp'))
    receipt['installed_probe']=json.loads(log.read_text())
    with zipfile.ZipFile(WHEEL) as archive:
        required=['__init__.py','ruptures_pr383.py','ruptures_pr383.json','ruptures_LICENSE.txt','ruptures_pr383_source.txt']
        vendor=[]
        for filename in required:
            name='account_history_analyzer/_vendor/'+filename
            raw=archive.read(name)
            installed=Path(receipt['installed_probe']['module_file']).parent/'_vendor'/filename
            source=ROOT/'src'/name
            assert raw==installed.read_bytes()==source.read_bytes()
            vendor.append({'wheel_member':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),
                           'matches_source_and_installed':True})
        receipt['vendor_files']=vendor
    save()
    report=QA/'wheel-output/arithmetic'
    run('wheel-installed-analyze',[str(INSTALL/'bin/ahas'),'analyze',
         '--input',str(ROOT/'fixtures/arithmetic.jsonl'),'--manifest',str(ROOT/'fixtures/arithmetic.snapshot.json'),
         '--config',str(ROOT/'config/default.toml'),'--out',str(report)],cwd=Path('/tmp'))
    log=run('wheel-installed-verify-recompute',[str(INSTALL/'bin/ahas'),'verify',
         '--input',str(ROOT/'fixtures/arithmetic.jsonl'),'--manifest',str(ROOT/'fixtures/arithmetic.snapshot.json'),
         '--analysis-dir',str(report),'--recompute'],cwd=Path('/tmp'))
    receipt['verification']=json.loads(log.read_text())
    assert receipt['verification']['status']=='reproduced'
    receipt['status']='passed_pending_canonical_comparison'
    save()
except Exception as exc:
    receipt['status']='failed'
    receipt['error']=str(exc)
    save()
    raise
