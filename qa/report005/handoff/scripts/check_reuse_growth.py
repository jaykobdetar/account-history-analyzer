from pathlib import Path
from datetime import datetime,timezone,timedelta
from dataclasses import asdict
import json,sys,time,tarfile,importlib.util,hashlib,tempfile,random
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.features import extract_records
from account_history_analyzer.io import canonical_bytes,load_snapshot
from account_history_analyzer.reuse import analyze_reuse
root=Path(sys.argv[1]); output=Path(sys.argv[2]); cfg=AnalysisConfig.from_mapping()
basepath=Path(sys.argv[3]) if len(sys.argv)>3 else Path(__file__).resolve().parents[1]/'evidence/baseline_reuse_101.py'
spec=importlib.util.spec_from_file_location('account_history_analyzer._review_baseline_reuse',basepath)
base=importlib.util.module_from_spec(spec);sys.modules[spec.name]=base;spec.loader.exec_module(base)
patterns={'identical': ['echo'], 'one_edit':['echo'], 'period3_edit':['alpha','beta','gamma'], 'period3_shift':['alpha','beta','gamma'], 'period31_edit':['word'+chr(97+i//26)+chr(97+i%26) for i in range(31)]}
rows=[]
with tempfile.TemporaryDirectory(prefix='ahas-review-reuse-') as temp:
 temp=Path(temp)
 manifest=json.loads((root/'fixtures/arithmetic.snapshot.json').read_text())
 for name,pattern in patterns.items():
  for n in (1000,2000,4000,8000):
   a=[pattern[i%len(pattern)] for i in range(n)]; b=list(a)
   if name.endswith('edit'): b[n//2]='replacement'
   if name.endswith('shift'): b=b[1:]+b[:1]
   records=[{'schema_version':'1.0.0','id':f'review_{i}','account_id':manifest['account_id'],'kind':'comment','status':'present','language':'en','text':' '.join(v),'created_utc':f'2025-01-01T00:00:0{i}Z'} for i,v in enumerate((a,b))]
   (temp/'records.jsonl').write_bytes(b''.join(canonical_bytes(x) for x in records)); (temp/'manifest.json').write_bytes(canonical_bytes(manifest))
   snapshot=load_snapshot(temp/'records.jsonl',temp/'manifest.json',cfg); features=extract_records(snapshot,cfg)
   started=time.perf_counter(); new=analyze_reuse(snapshot,features,cfg); elapsed=time.perf_counter()-started
   row={'pattern':name,'words_per_record':n,'repaired_seconds':elapsed,'candidate_pairs':new['candidate_pair_count'],'complete':new['budget_complete'],'work_units':new['resource_usage']['work_units'],'matches':[p['matching_passages'][0]['token_count'] for p in new['pairs']]}
   if n==8000:
    started=time.perf_counter(); original=base.analyze_reuse(snapshot,features,cfg); row['baseline_seconds']=time.perf_counter()-started
    row['full_pair_payload_equal']=canonical_bytes(new['pairs'])==canonical_bytes(original['pairs'])
    row['baseline_pair_count']=len(original['pairs']);row['pair_payload_sha256']=hashlib.sha256(canonical_bytes(new['pairs'])).hexdigest()
   rows.append(row);print(row,flush=True)
   output.write_text(json.dumps({'scope':'Actual unchanged 1.0.1 versus 1.0.2 reuse modules on identical locally prepared features. Single-run timings exclude preprocessing. Nonreference environment.','cases':rows},indent=2)+'\n')
