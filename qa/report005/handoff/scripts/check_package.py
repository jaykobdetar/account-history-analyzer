from pathlib import Path
import json, hashlib, zipfile, tarfile, sys, re
root=Path(sys.argv[1]); benchmark=Path(sys.argv[2]); out=Path(sys.argv[3])
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  while chunk:=f.read(1<<20): h.update(chunk)
 return h.hexdigest()
def digest(value):return hashlib.sha256((json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest()
source=root/'src/account_history_analyzer'
covered={str(p.relative_to(source)):sha(p) for p in sorted(source.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py','.json','.toml','.txt'}}
wheel=root/'dist/account_history_analyzer-1.0.2-py3-none-any.whl'
with zipfile.ZipFile(wheel) as z:
 names=[n for n in z.namelist() if n.startswith('account_history_analyzer/') and not n.endswith('/')]
 matches={n:(root/'src'/n).exists() and hashlib.sha256(z.read(n)).hexdigest()==sha(root/'src'/n) for n in names}
reference=json.loads((root/'qa/audit-repair/benchmark-lifecycle-receipt.json').read_text())
package={'fingerprint':digest(covered),'fingerprint_files':len(covered),'reference_fingerprint':reference['implementation_fingerprint'],'wheel_sha256':sha(wheel),'wheel_package_files':len(names),'wheel_matches':matches,'changes_against_101':{}}
with tarfile.open(sys.argv[4]) as tf:
 old={m.name.split('/src/account_history_analyzer/',1)[1]:hashlib.sha256(tf.extractfile(m).read()).hexdigest() for m in tf if m.isfile() and '/src/account_history_analyzer/' in m.name}
 package['changes_against_101']={n:'added' if n not in old else 'changed' for n,s in covered.items() if old.get(n)!=s}
checks={}
for name,folder in [(p.name,p) for p in sorted((root/'output/audit-repair').iterdir()) if p.is_dir()]+[('benchmark',benchmark)]:
 c=json.loads((folder/'checksums.json').read_text())
 observed={n:sha(folder/n) for n in c}
 checks[name]={'file_count':len(c),'matches':{n:observed[n]==s for n,s in c.items()},'manifest_sha256':sha(folder/'checksums.json'),'results_bytes':(folder/'results.json').stat().st_size}
 if name=='benchmark':
  checks[name]['all_16_file_sizes_match_receipt']={n:(folder/n).stat().st_size==s for n,s in reference['artifact_bytes'].items()}
  checks[name]['checksums_match_receipt']=c==reference['canonical_checksums']
  checks[name]['input_hash_matches_receipt']=sha(root/'benchmarks/input/records.jsonl')==reference['input_sha256']
  checks[name]['manifest_hash_matches_receipt']=sha(root/'benchmarks/input/snapshot.json')==reference['manifest_sha256']
  checks[name]['total_bytes']=sum(p.stat().st_size for p in folder.iterdir() if p.is_file())
logs={}
for n in ['full-tests.log','container-tests.log','browser-test.log','supplied-regressions-after.log']:
 text=(root/'qa/audit-repair'/n).read_text()
 logs[n]={'sha256':sha(root/'qa/audit-repair'/n),'summary':[line for line in text.splitlines() if re.search(r'\d+ passed',line)][-1:]}
result={'scope':'Independent package and checksum inspection, not independent execution of supplied release tests.','package':package,'bundles':checks,'supplied_logs':logs}
out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'fingerprint':package['fingerprint'],'wheel_files':len(names),'wheel_all_match':all(matches.values()),'bundle_counts':{n:v['file_count'] for n,v in checks.items()},'all_manifest_matches':all(all(v['matches'].values()) for v in checks.values()),'supplied_logs':logs},indent=2))
