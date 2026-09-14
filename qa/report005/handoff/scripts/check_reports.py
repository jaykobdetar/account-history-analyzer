from pathlib import Path
import json,hashlib,sys,time,gc
from collections.abc import Mapping
from account_history_analyzer.artifact_io import load_artifact_json,iter_artifact_jsonl
from account_history_analyzer.reporting import render_markdown,render_html
from account_history_analyzer.charts import render_charts
def canonical_digest(value):
 # Independent fast reference serialization for immutability comparisons.
 return hashlib.sha256((json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest()
root=Path(sys.argv[1]); out=Path(sys.argv[2]); summaries={}
def reverse(value):
 if isinstance(value,dict):return {k:reverse(v) for k,v in reversed(list(value.items()))}
 if isinstance(value,list):return [reverse(v) for v in value]
 return value
for p in sorted((root/'output/audit-repair').iterdir()):
 if not p.is_dir():continue
 r=load_artifact_json(p/'results.json'); e=list(iter_artifact_jsonl(p/'evidence.jsonl')); w=list(iter_artifact_jsonl(p/'windows.jsonl'))
 before=canonical_digest(r)
 md=render_markdown(r,e,windows=w).encode(); html=render_html(r,e,windows=w).encode()
 charts=render_charts(r,w)
 actual={'report.md':md,'report.html':html,**charts}
 checks={n:b==(p/n).read_bytes() for n,b in actual.items()}
 reversed_r,reversed_e,reversed_w=reverse(r),reverse(e),reverse(w)
 order={}
 for mode in ('included','none'):
  first_md=render_markdown(r,e,windows=w,excerpts=mode)
  first_html=render_html(r,e,windows=w,excerpts=mode)
  order[mode]={'markdown':first_md==render_markdown(reversed_r,reversed_e,windows=reversed_w,excerpts=mode),'html':first_html==render_html(reversed_r,reversed_e,windows=reversed_w,excerpts=mode)}
 summaries[p.name]={'published_rerender_equal':checks,'recursive_mapping_reversal':order,'input_result_unchanged':canonical_digest(r)==before,'canonical_map_reversal_equal':canonical_digest(reversed_r)==before}
 out.write_text(json.dumps({'scope':'Rendering saved analytical values, not recomputing numerical analysis. Actual unmodified modules under local nonreference environment.','fixtures':summaries},indent=2)+'\n')
 print(p.name, summaries[p.name],flush=True)
 del r,e,w,reversed_r,reversed_e,reversed_w,actual,charts,md,html
 gc.collect()
out.write_text(json.dumps({'scope':'Rendering saved analytical values, not recomputing numerical analysis. Actual unmodified modules under local nonreference environment.','fixtures':summaries},indent=2)+'\n')
