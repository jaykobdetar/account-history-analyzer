"""Independently check packaged source, wheel and saved complete-report checksums.
Usage: python probe_integrity.py REPO OUTPUT_JSON
No missing full-pipeline dependency is substituted or imported.
"""
import hashlib,json,sys,zipfile
from pathlib import Path
repo=Path(sys.argv[1]).resolve();root=repo/'src/account_history_analyzer';sys.path.insert(0,str(repo/'src'))
from account_history_analyzer.io import digest
from account_history_analyzer.artifacts import verify_artifacts
source={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py','.json','.toml','.txt'}}
result={'source_fingerprint':digest(source),'source_file_count':len(source),'wheel':{},'reports':{}}
wheels=list((repo/'dist').glob('*.whl'))
if len(wheels)!=1:raise RuntimeError('Expected exactly one release wheel')
with zipfile.ZipFile(wheels[0]) as wheel:
    mismatches=[]
    for relative in source:
        member='account_history_analyzer/'+relative
        if member not in wheel.namelist() or wheel.read(member)!=(root/relative).read_bytes():mismatches.append(relative)
    result['wheel']={'filename':wheels[0].name,'source_files_compared':len(source),'mismatches':mismatches}
for directory in sorted((repo/'output').iterdir()):
    if not directory.is_dir():continue
    if not (directory/'checksums.json').exists():
        result['reports'][directory.name]={'scope':'derivative_render_not_complete_analysis','verification':'not_applicable'};continue
    checked=verify_artifacts(directory)
    stored=json.loads((directory/'results.json').read_bytes())
    result['reports'][directory.name]={**checked,'results_bytes':(directory/'results.json').stat().st_size,
                                      'source_fingerprint_matches':stored['analysis']['implementation_fingerprint']==result['source_fingerprint']}
Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
assert not result['wheel']['mismatches']
assert all(r.get('source_fingerprint_matches',True) for r in result['reports'].values())
