import hashlib,json,tarfile
from pathlib import Path
root=Path.cwd();qa=root/'qa/audit-repair'
baseline=json.loads((qa/'baseline-inventory.json').read_text());changed=[]
for name,wanted in baseline.items():
 p=root/name
 if not p.is_file(): changed.append({'path':name,'reason':'missing'});continue
 with p.open('rb') as f: actual=hashlib.file_digest(f,'sha256').hexdigest()
 if actual!=wanted:changed.append({'path':name,'expected':wanted,'actual':actual})
archive=root/'release/1.0.1/account-history-analyzer-1.0.1-source-and-reports.tar.gz'
with tarfile.open(archive,'r:gz') as tf:
 names=['requirements.lock.txt','containers/build-requirements.lock','pyproject.toml','uv.lock']
 names+=[str(p.relative_to(root)) for p in (root/'src/account_history_analyzer/_vendor').iterdir() if p.is_file() and p.suffix!='.pyc']
 comparisons={}
 for name in names:
  old=tf.extractfile('account_history_analyzer_v1/'+name).read();current=(root/name).read_bytes()
  if name in {'pyproject.toml','uv.lock'}:current=current.replace(b'version = "1.0.2"',b'version = "1.0.1"')
  comparisons[name]=old==current
receipt={'historical_files_checked':len(baseline),'changed_historical_files':changed,'dependency_and_vendor_equivalence':comparisons,'project_metadata_version_normalized_for_comparison':True,'status':'passed' if not changed and all(comparisons.values()) else 'failed'}
(qa/'preservation.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');print(receipt)
raise SystemExit(receipt['status']!='passed')
