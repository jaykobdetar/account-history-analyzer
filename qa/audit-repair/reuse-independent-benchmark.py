from pathlib import Path
import json,time
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.features import extract_records
from account_history_analyzer.io import load_snapshot
from account_history_analyzer.reuse import analyze_reuse
root=Path.cwd()
c=AnalysisConfig.from_mapping()
s=load_snapshot(root/'benchmarks/input/records.jsonl',root/'benchmarks/input/snapshot.json',c)
f=extract_records(s,c)
rows=[]
for label,conf in [('current_default',c),('measurement_capacity',c.with_overrides({'reuse':{'max_work_units':1000000000}}))]:
 start=time.perf_counter();r=analyze_reuse(s,f,conf);elapsed=time.perf_counter()-start
 row={'configuration':label,'snapshot_sha256':s.canonical_sha256,'unique_records':len(f),'runtime_seconds':elapsed,
      'near_status':r['near_status'],'resource_limit_reason':r['resource_limit_reason'],
      'candidate_pair_count':r['candidate_pair_count'],'candidate_count_is_lower_bound':r['candidate_count_is_lower_bound'],
      'qualifying_pairs':len(r['pairs']),'exact_groups':len(r['exact_groups']), 'resource_usage':r['resource_usage'],'resource_limits':r['resource_limits']}
 rows.append(row);print(json.dumps(row,sort_keys=True),flush=True)
(root/'qa/audit-repair/reuse-independent-benchmark.json').write_text(json.dumps({'network_isolation':'linux_seccomp_socket_denial','command':'python3.12 scripts/offline_exec.py .venv/bin/python - < independently measured analyze_reuse probe >','rows':rows},indent=2)+'\n')
