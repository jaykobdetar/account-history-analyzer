"""Run original comparison code on supplied benchmark; no segmentation dependency."""
import sys,json,time
from pathlib import Path
repo=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(repo/'src'))
from account_history_analyzer import AnalysisConfig,load_snapshot
from account_history_analyzer.features import extract_records
from account_history_analyzer.comparisons import analyze_comparisons
from account_history_analyzer.io import canonical_bytes,load_json
c=AnalysisConfig.from_toml(repo/'config/default.toml')
s=load_snapshot(repo/'benchmarks/input/records.jsonl',repo/'benchmarks/input/snapshot.json',c)
t=time.perf_counter()
f=extract_records(s,c)
style,windows=analyze_comparisons(f,c)
data=canonical_bytes(style)
out=Path(sys.argv[2]);out.write_bytes(data)
r={'records':len(s.records),'comparisons':len(style['comparisons']),'style_payload_bytes':len(data),'style_payload_MiB':len(data)/1024**2,'load_json_default_limit':52428800,'seconds':time.perf_counter()-t}
try:load_json(out);r['reload']='ok'
except Exception as e:r['reload']={'type':type(e).__name__,'message':str(e)}
print(json.dumps(r,indent=2))
