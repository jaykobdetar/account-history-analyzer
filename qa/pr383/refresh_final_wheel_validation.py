"""Operational final-sdist refresh; package and documentation remain unchanged."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import time
import zipfile

ROOT=Path(__file__).resolve().parents[2]
QA=ROOT/'qa/pr383'
UV='/home/jaykob/.local/bin/uv'
CACHE='/tmp/ahas-uv-cache'
INSTALL=Path('/tmp/ahas-pr383-install')
WHEEL=ROOT/'dist/account_history_analyzer-1.0.1-py3-none-any.whl'
SDIST=ROOT/'dist/account_history_analyzer-1.0.1.tar.gz'
EXPECTED_WHEEL='e439e8cc54943d1bbf7a3b54734c5cec3d4a78b732fe95b06a7ec9084374e7ba'
EXPECTED_FP='4ec887e4ecc344fbd9561c9cb3fc2fc9e95fe1f3a582409826d70ac5315f8a61'
RECEIPT=QA/'wheel-verification.json'
PRESERVED=QA/'initial-wheel-validation'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

assert not PRESERVED.exists(), 'Preserved validation already exists; refusing to alter it'
PRESERVED.mkdir()
old=json.loads(RECEIPT.read_text())
assert old['status']=='passed' and sha(WHEEL)==EXPECTED_WHEEL
shutil.copy2(RECEIPT,PRESERVED/'wheel-verification.json')
shutil.copy2(SDIST,PRESERVED/SDIST.name)
receipt={'suite_version':'1.0.1','status':'in_progress','commands':[],
 'invocation':['python3.12',str(Path(__file__).resolve())],
 'network_isolation':{'build':'uv --offline with hash-locked cached build constraints',
                       'installed_analysis_and_verification':'linux_seccomp_socket_denial'},
 'preserved_initial_validation':{'receipt':str(PRESERVED/'wheel-verification.json'),
                                'receipt_sha256':sha(PRESERVED/'wheel-verification.json'),
                                'sdist':str(PRESERVED/SDIST.name),'sdist_sha256':sha(PRESERVED/SDIST.name)},
 'prior_failed_attempt_receipt':old['prior_failed_attempt_receipt'],
 'installation':{'path':str(INSTALL),'reused':True,'reason':'Previously hash-installed wheel remains byte-identical.',
                 'original_installation_receipt':str(PRESERVED/'wheel-verification.json')},
 'expected_implementation_fingerprint':EXPECTED_FP,
 'historical_artifacts':'No 1.0.0 distributions or historical receipts were modified.'}

def save():
    RECEIPT.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')

def run(name,argv,cwd=ROOT,isolated=False):
    if isolated:
        argv=['python3.12',str(ROOT/'scripts/offline_exec.py'),*argv]
    log=QA/(name+'.log')
    assert not log.exists(), 'Refusing to overwrite prior log '+str(log)
    env={key:value for key,value in os.environ.items() if key!='PYTHONPATH'}
    started=time.perf_counter()
    with log.open('wb') as output:
        result=subprocess.run(argv,cwd=cwd,env=env,stdout=output,stderr=subprocess.STDOUT)
    receipt['commands'].append({'name':name,'argv':argv,'cwd':str(cwd),'exit_code':result.returncode,
        'elapsed_seconds':time.perf_counter()-started,'log_path':str(log),'log_sha256':sha(log)})
    save()
    print(json.dumps({'step':name,'exit_code':result.returncode}),flush=True)
    if result.returncode:
        raise RuntimeError(f'{name} failed; inspect {log}')
    return log

try:
    save()
    run('wheel-final-dist-refresh',[UV,'build','--python',str(ROOT/'.venv/bin/python'),'--offline',
        '--no-build-isolation','--out-dir',str(ROOT/'dist'),'--cache-dir',CACHE])
    assert sha(WHEEL)==EXPECTED_WHEEL, 'Refreshed wheel changed unexpectedly'
    receipt['wheel']={'path':str(WHEEL),'sha256':sha(WHEEL),'bytes':WHEEL.stat().st_size}
    receipt['sdist']={'path':str(SDIST),'sha256':sha(SDIST),'bytes':SDIST.stat().st_size}
    for label in ('a','b'):
        run('wheel-final-isolated-build-'+label,[UV,'build',str(SDIST),'--wheel',
            '--out-dir',str(QA/('wheel-final-build-'+label)),'--python',str(ROOT/'.venv/bin/python'),
            '--offline','--no-python-downloads','--cache-dir',CACHE,'--build-constraints',
            str(ROOT/'containers/build-requirements.lock'),'--require-hashes','--link-mode','copy','--no-progress'])
    rebuilt=[QA/('wheel-final-build-'+label)/WHEEL.name for label in ('a','b')]
    assert all(path.read_bytes()==WHEEL.read_bytes() for path in rebuilt)
    receipt['rebuilt_wheels']=[{'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size} for path in rebuilt]
    receipt['wheel_bytes_identical']=True
    previous_probe=next(step for step in old['commands'] if step['name']=='wheel-installed-probe')
    probe_argv=previous_probe['argv'][2:]
    log=run('wheel-final-installed-probe',probe_argv,cwd=Path('/tmp'),isolated=True)
    receipt['installed_probe']=json.loads(log.read_text())
    assert receipt['installed_probe']['implementation_fingerprint']==EXPECTED_FP
    with zipfile.ZipFile(WHEEL) as wheel,tarfile.open(SDIST,'r:gz') as sdist:
        receipt['vendor_files']=[]
        for entry in old['vendor_files']:
            raw=wheel.read(entry['wheel_member'])
            assert hashlib.sha256(raw).hexdigest()==entry['sha256']
            assert sdist.extractfile(entry['sdist_member']).read()==raw
            filename=Path(entry['wheel_member']).name
            assert (Path(receipt['installed_probe']['module_file']).parent/'_vendor'/filename).read_bytes()==raw
            assert (ROOT/'src'/entry['wheel_member']).read_bytes()==raw
            receipt['vendor_files'].append(entry)
        checked=[]
        paths=[ROOT/'README.md']
        for directory in ('docs','scripts'):
            paths.extend(path for path in sorted((ROOT/directory).rglob('*'))
                         if path.is_file() and '__pycache__' not in path.parts)
        for path in paths:
            relative=path.relative_to(ROOT)
            raw=sdist.extractfile('account_history_analyzer-1.0.1/'+str(relative)).read()
            assert raw==path.read_bytes(), 'Sdist contains stale documentation/helper '+str(relative)
            checked.append({'path':str(relative),'sha256':sha(path)})
        receipt['final_documentation_and_helpers']={'status':'passed','checked_files':checked}
    save()
    report=QA/'wheel-output/arithmetic'
    run('wheel-final-installed-analyze',[str(INSTALL/'bin/ahas'),'analyze','--input',str(ROOT/'fixtures/arithmetic.jsonl'),
        '--manifest',str(ROOT/'fixtures/arithmetic.snapshot.json'),'--config',str(ROOT/'config/default.toml'),
        '--out',str(report),'--overwrite'],cwd=Path('/tmp'),isolated=True)
    log=run('wheel-final-installed-verify-recompute',[str(INSTALL/'bin/ahas'),'verify',
        '--input',str(ROOT/'fixtures/arithmetic.jsonl'),'--manifest',str(ROOT/'fixtures/arithmetic.snapshot.json'),
        '--analysis-dir',str(report),'--recompute'],cwd=Path('/tmp'),isolated=True)
    receipt['verification']=json.loads(log.read_text())
    assert receipt['verification']['status']=='reproduced'
    source=ROOT/'output/pr383/arithmetic'
    ignored={'ingest_receipt.json','run_receipt.json'}
    names={p.name for p in source.iterdir() if p.is_file()}-ignored
    assert names=={p.name for p in report.iterdir() if p.is_file()}-ignored
    assert len(names)==14
    comparison=[]
    for name in sorted(names):
        a=(source/name).read_bytes();b=(report/name).read_bytes()
        assert a==b, name
        comparison.append({'name':name,'bytes':len(a),'source_sha256':hashlib.sha256(a).hexdigest(),
                           'wheel_sha256':hashlib.sha256(b).hexdigest(),'byte_identical':True})
    receipt['canonical_comparison']={'status':'passed','source_directory':str(source),'wheel_directory':str(report),
        'compared_file_count':len(names),'files':comparison,'excluded_receipts':sorted(ignored),
        'exclusion_reason':'Operational paths and run timing are outside canonical analytical identity.'}
    log=QA/'wheel-final-canonical-comparison.log'
    log.write_text(json.dumps({'status':'passed','compared_canonical_files':len(names),'all_byte_identical':True})+'\n')
    receipt['canonical_comparison']['log_path']=str(log)
    receipt['canonical_comparison']['log_sha256']=sha(log)
    receipt['status']='passed'
    save()
    print(json.dumps({'status':'passed','wheel_sha256':sha(WHEEL),'sdist_sha256':sha(SDIST),'canonical_files':14}),flush=True)
except Exception as exc:
    receipt['status']='failed';receipt['error']=str(exc);save();raise
