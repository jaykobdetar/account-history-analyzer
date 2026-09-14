"""Verify the final report-only source/package scope; never alter historical files."""
import difflib
import hashlib
import json
from pathlib import Path
import tarfile
from account_history_analyzer.pipeline import implementation_identity

root=Path.cwd();qa=root/'qa/report005';baseline=json.loads((qa/'baseline-inventory.json').read_text())
expected={'src/account_history_analyzer/reporting.py','src/account_history_analyzer/__init__.py','src/account_history_analyzer/payload_schemas.py','src/account_history_analyzer/contracts/results.schema.json','schemas/results.schema.json'}
changed=[]
for name,wanted in baseline.items():
 with (root/name).open('rb') as f:observed=hashlib.file_digest(f,'sha256').hexdigest()
 if observed!=wanted:changed.append(name)
assert set(changed)==expected,changed
archive=root/'release/1.0.2/account-history-analyzer-1.0.2-source-and-reports.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='8a5be86a5cb4a264368e50c1ecfd3109ebaad4e89405ec870bc8c05b82cd92ae'
paths=sorted([*expected,'pyproject.toml','uv.lock','README.md','containers/README.md','docs/DECISIONS.md','docs/MILESTONES.md','docs/TEST_MAP.md','docs/REPORT005.md','tests/test_ngram_labels.py','tests/test_report005_metadata.py'])
patch=[];files=[]
with tarfile.open(archive,'r:gz') as tf:
 members=set(tf.getnames())
 for name in paths:
  member='account_history_analyzer_v1/'+name
  old=tf.extractfile(member).read().decode() if member in members else ''
  new=(root/name).read_text()
  if name in {'pyproject.toml','uv.lock'}:assert new.replace('version = "1.0.3"','version = "1.0.2"')==old,name
  if new!=old:
   patch.extend(difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True),fromfile='a/'+name if old else '/dev/null',tofile='b/'+name))
   files.append({'path':name,'status':'modified' if old else 'added'})
(qa/'source.patch').write_text(''.join(patch));(qa/'changed-files.json').write_text(json.dumps(files,sort_keys=True,indent=2)+'\n')
fp,env,_=implementation_identity();assert fp=='c63f7130067baef0d8eeddcff30cf1c99ba31b8b69816ca843db03a917d9789a'
wanted='4b472fa9d44d0803ab8f510eedc5a8bac5db454c5363dae81bd322511a59934d'
wheel=root/'dist/account_history_analyzer-1.0.3-py3-none-any.whl'
rebuilt=qa/'wheel-build-final/account_history_analyzer-1.0.3-py3-none-any.whl'
assert hashlib.sha256(wheel.read_bytes()).hexdigest()==wanted and rebuilt.read_bytes()==wheel.read_bytes()
sdist=root/'dist/account_history_analyzer-1.0.3.tar.gz';count=0
with tarfile.open(sdist,'r:gz') as tf:
 for member in tf.getmembers():
  if not member.isfile():continue
  name=member.name.split('/',1)[1];p=root/name
  if p.is_file():assert tf.extractfile(member).read()==p.read_bytes(),name;count+=1
result={'status':'passed','implementation_fingerprint':fp,'reference_environment':env,'wheel_sha256':wanted,'matches_fresh_installed_tested_wheel':True,'final_sdist_sha256':hashlib.sha256(sdist.read_bytes()).hexdigest(),'sdist_source_files_compared':count,'changed_files_count':len(files),'baseline_files_checked':len(baseline),'changed_existing_inventory_files':changed,'dependency_locks_unchanged_except_project_version':True,'final_patch_sha256':hashlib.sha256((qa/'source.patch').read_bytes()).hexdigest(),'note':'Documentation-only final source-distribution rebuild produced the same installed/tested wheel; no additional numerical run implied.'}
(qa/'final-build-verification.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,sort_keys=True))
