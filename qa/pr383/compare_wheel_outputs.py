"""Compare fresh source/wheel artifacts without modifying either report."""
from pathlib import Path
import hashlib
import json
import tarfile

ROOT=Path(__file__).resolve().parents[2]
QA=ROOT/'qa/pr383'
receipt_path=QA/'wheel-verification.json'
receipt=json.loads(receipt_path.read_text())
source=ROOT/'output/pr383/arithmetic'
wheel=QA/'wheel-output/arithmetic'
ignored={'ingest_receipt.json','run_receipt.json'}
source_files={p.name for p in source.iterdir() if p.is_file()}-ignored
wheel_files={p.name for p in wheel.iterdir() if p.is_file()}-ignored
assert source_files==wheel_files, (source_files, wheel_files)
assert len(source_files)==14
comparisons=[]
for name in sorted(source_files):
 a=(source/name).read_bytes()
 b=(wheel/name).read_bytes()
 row={'name':name,'bytes':len(a),'source_sha256':hashlib.sha256(a).hexdigest(),
      'wheel_sha256':hashlib.sha256(b).hexdigest(),'byte_identical':a==b}
 comparisons.append(row)
assert all(row['byte_identical'] for row in comparisons)
for directory in (source,wheel):
 assert json.loads((directory/'results.json').read_text())['analysis']['implementation_fingerprint']==receipt['expected_implementation_fingerprint']
with tarfile.open(receipt['sdist']['path'],'r:gz') as archive:
 for entry in receipt['vendor_files']:
  name='account_history_analyzer-1.0.1/src/'+entry['wheel_member']
  raw=archive.extractfile(name).read()
  assert hashlib.sha256(raw).hexdigest()==entry['sha256']
  entry['sdist_member']=name
  entry['matches_sdist']=True
receipt['canonical_comparison']={'status':'passed','source_directory':str(source),'wheel_directory':str(wheel),
 'compared_file_count':len(comparisons),'files':comparisons,'excluded_receipts':sorted(ignored),
 'exclusion_reason':'Operational paths, input-file receipts and run timing are outside canonical analytical identity.'}
receipt['status']='passed'
receipt['commands'].append({'name':'wheel-canonical-comparison','argv':['python3.12',str(ROOT/'scripts/offline_exec.py'),
 'python3.12',str(Path(__file__).resolve())],'cwd':str(ROOT),'exit_code':0,
 'log_path':str(QA/'wheel-canonical-comparison.log')})
receipt_path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
print(json.dumps({'status':'passed','compared_canonical_files':len(comparisons),
 'all_byte_identical':True,'sdist_vendor_files_checked':len(receipt['vendor_files']),
 'wheel_sha256':receipt['wheel']['sha256'],
 'implementation_fingerprint':receipt['expected_implementation_fingerprint']},sort_keys=True))
