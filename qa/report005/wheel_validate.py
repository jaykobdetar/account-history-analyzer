"""Fresh, offline 1.0.3 wheel installation and actual installed CLI verification."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
QA = ROOT / 'qa/report005'
INSTALL = Path('/tmp/ahas-report005-install')
UV = '/home/jaykob/.local/bin/uv'
CACHE = '/tmp/ahas-uv-cache'
SYSTEM_PYTHON = '/usr/bin/python3.12'
WHEEL = ROOT / 'dist/account_history_analyzer-1.0.3-py3-none-any.whl'
EXPECTED_FP = 'c63f7130067baef0d8eeddcff30cf1c99ba31b8b69816ca843db03a917d9789a'
RECEIPT = QA / 'wheel-verification.json'
state = {
    'suite_version':'1.0.3', 'status':'running', 'commands':[],
    'expected_implementation_fingerprint':EXPECTED_FP,
    'scope':'Fresh hash-locked offline wheel installation; installed CLI analysis and complete numerical/artifact replay; no sdist rebuild in this receipt',
    'historical_preservation':'No previous release environments, artifacts or receipts modified; root .venv unused for installation',
    'network_isolation':{'installation':'uv --offline with existing cache; not seccomp',
                         'installed_commands':'Linux seccomp socket denial via scripts/offline_exec.py'},
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save():
    RECEIPT.write_text(json.dumps(state, indent=2, sort_keys=True)+'\n')


def run(name, argv, *, seccomp=False):
    env = os.environ.copy()
    for variable in ('PYTHONPATH', 'PYTHONHOME'):
        env.pop(variable, None)
    env.update(PYTHONHASHSEED='317', TZ='UTC')
    started = time.perf_counter()
    result = subprocess.run(argv, cwd='/tmp', env=env, capture_output=True, text=True)
    log = QA / (name+'.log')
    log.write_text(result.stdout+result.stderr)
    state['commands'].append({'name':name, 'argv':argv, 'cwd':'/tmp',
        'environment_overrides':{'PYTHONHASHSEED':'317','TZ':'UTC'},
        'removed_environment_variables':['PYTHONPATH','PYTHONHOME'],
        'seccomp_network_denial':seccomp,
        'exit_code':result.returncode, 'elapsed_seconds':time.perf_counter()-started,
        'log_path':str(log.relative_to(ROOT)), 'log_sha256':sha(log.read_bytes())})
    save()
    print(name, result.returncode, flush=True)
    if result.returncode:
        raise RuntimeError(f'{name} failed; see {log}')
    return result.stdout


def main():
    global state
    resume = sys.argv[1:] == ['--resume-existing-fresh']
    if INSTALL.exists() and not resume:
        raise RuntimeError('Fresh installation path already exists')
    if RECEIPT.exists() and not resume:
        raise RuntimeError('Refuse to overwrite existing validation receipt')
    if resume:
        state = json.loads(RECEIPT.read_text())
        assert state['status']=='failed' and state['failure']=='AssertionError: '
        assert all(row['exit_code']==0 for row in state['commands'])
        state['commands'] = state['commands'][:3]
        state.pop('failure')
        state.pop('installed_probe')
        state['status']='running'
        state['harness_correction']='Initial source inventory omitted the correctly shipped py.typed marker. Failed receipt/script/logs preserved in wheel-initial-inventory-attempt. Reused the same newly created, hash-locked installation after correcting only the inventory.'
    state['wheel']={'path':str(WHEEL.relative_to(ROOT)), 'sha256':sha(WHEEL.read_bytes()), 'bytes':WHEEL.stat().st_size}
    locks = [ROOT/'requirements.lock.txt', ROOT/'containers/build-requirements.lock']
    state['lockfiles']={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in locks}
    wheel_requirements = QA/'wheel-install.requirements.txt'
    wheel_requirements.write_text(str(WHEEL)+' --hash=sha256:'+state['wheel']['sha256']+'\n')
    python = str(INSTALL/'bin/python')
    if not resume:
        run('wheel-fresh-venv', [UV,'venv',str(INSTALL),'--python',SYSTEM_PYTHON,'--offline','--no-python-downloads','--cache-dir',CACHE])
        run('wheel-locked-dependencies', [UV,'pip','install','--python',python,'--offline','--require-hashes','--cache-dir',CACHE,'--link-mode','copy','-r',str(locks[0]),'-r',str(locks[1])])
        run('wheel-package-install', [UV,'pip','install','--python',python,'--offline','--require-hashes','--no-deps','--cache-dir',CACHE,'--link-mode','copy','-r',str(wheel_requirements)])
    offline = [SYSTEM_PYTHON,str(ROOT/'scripts/offline_exec.py')]
    probe = '''import hashlib, importlib.metadata as m, json, pathlib, sys
import account_history_analyzer as a
from account_history_analyzer.pipeline import implementation_identity
from account_history_analyzer.reporting import ngram_label, TEMPLATE_VERSION
path=pathlib.Path(a.__file__).resolve()
assert path.is_relative_to(pathlib.Path('/tmp/ahas-report005-install/lib/python3.12/site-packages'))
assert a.__version__==m.version('account-history-analyzer')==TEMPLATE_VERSION=='1.0.3'
fp,environment,resources=implementation_identity()
assert fp=='c63f7130067baef0d8eeddcff30cf1c99ba31b8b69816ca843db03a917d9789a'
cases=[' th','he ',' the ',r'\\u0020','é','😀','\\t\\n','&nbsp;','"\\\\|']
for value in cases:
 assert json.loads(ngram_label(value))==value
assert ngram_label(' ')==r'"\\u0020"'
source=pathlib.Path('SOURCE_ROOT')/'src/account_history_analyzer'
files={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
for name,expected in files.items():
 assert hashlib.sha256((path.parent/name).read_bytes()).hexdigest()==expected, name
print(json.dumps({'module_file':str(path),'python':sys.version,'version':a.__version__,
 'implementation_fingerprint':fp,'reference_environment':environment,'resource_sha256':resources,
 'installed_distributions':{d.metadata['Name']:d.version for d in m.distributions()},
 'installed_package_file_count':len(files),'installed_package_sha256':files,
 'ngram_label_roundtrip_cases':cases,'space_label':ngram_label(' ')},sort_keys=True))
'''.replace('SOURCE_ROOT',str(ROOT))
    state['installed_probe']=json.loads(run('wheel-installed-probe',offline+[python,'-c',probe],seccomp=True))
    with zipfile.ZipFile(WHEEL) as archive:
        packaged={name.removeprefix('account_history_analyzer/'):sha(archive.read(name)) for name in archive.namelist() if name.startswith('account_history_analyzer/') and not name.endswith('/')}
    assert packaged==state['installed_probe']['installed_package_sha256']
    state['wheel_package_files_match_source_and_installation']=True
    output=QA/'wheel-output/arithmetic'
    inputs=['--input',str(ROOT/'fixtures/arithmetic.jsonl'),'--manifest',str(ROOT/'fixtures/arithmetic.snapshot.json')]
    installed_cli=str(INSTALL/'bin/ahas')
    state['analysis']=json.loads(run('wheel-installed-analyze',offline+[installed_cli,'analyze',*inputs,'--out',str(output)],seccomp=True))
    state['verification']=json.loads(run('wheel-installed-verify-recompute',offline+[installed_cli,'verify',*inputs,'--analysis-dir',str(output),'--recompute'],seccomp=True))
    reference=ROOT/'output/report005/arithmetic'
    names=sorted(set(json.loads((reference/'checksums.json').read_bytes()))|{'checksums.json'})
    assert len(names)==14
    comparisons=[]
    for name in names:
        source=(reference/name).read_bytes()
        installed=(output/name).read_bytes()
        comparisons.append({'name':name,'bytes':len(source),'source_sha256':sha(source),'wheel_sha256':sha(installed),'byte_identical':source==installed})
    state['canonical_comparison']={'source_directory':str(reference.relative_to(ROOT)),
        'installed_directory':str(output.relative_to(ROOT)),'compared_file_count':len(comparisons),
        'excluded_receipts':['ingest_receipt.json','run_receipt.json'],
        'exclusion_reason':'Operational paths and timing are outside canonical analytical identity.', 'files':comparisons}
    assert all(row['byte_identical'] for row in comparisons)
    state['status']='passed'
    save()
    print(json.dumps({'status':'passed','wheel_sha256':state['wheel']['sha256'],
        'installed_package_file_count':len(packaged),'canonical_file_count':len(comparisons),
        'implementation_fingerprint':state['installed_probe']['implementation_fingerprint']},sort_keys=True))


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        state['status']='failed'
        state['failure']=f'{type(exc).__name__}: {exc}'
        save()
        raise
