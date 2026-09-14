"""Run genuine AHAS functions on small adversarial-but-valid examples.
Usage: PYTHONPATH=/path/to/repo/src python probe_reuse_and_links.py output.json
No AHAS source or dependency substitutions are used.
"""
import json, tempfile, time, sys
from pathlib import Path
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import canonical_bytes, load_snapshot
from account_history_analyzer.features import extract_records
from account_history_analyzer.reuse import analyze_reuse

config=AnalysisConfig.from_toml()
manifest={"schema_version":"1.0.0","snapshot_id":"audit","account_id":"audit","source_category":"synthetic","text_format":"markdown","default_language":"en","coverage":{"status":"unknown"}}
def prepare(texts,directory):
    rows=[{"schema_version":"1.0.0","id":f"r{i}","account_id":"audit","kind":"comment","text":text,"status":"present","created_utc":f"2025-01-01T00:00:{i:02}Z"} for i,text in enumerate(texts)]
    ip=directory/'input.jsonl';mp=directory/'snapshot.json'
    ip.write_bytes(b''.join(canonical_bytes(r) for r in rows));mp.write_bytes(canonical_bytes(manifest))
    snapshot=load_snapshot(ip,mp)
    return snapshot,extract_records(snapshot,config)
result={"runtime_note":"Real AHAS source, current environment; dependency versions differ from the release lock.","reuse":[],"links":[]}
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    for n in [500,1000,2000,4000,8000]:
        snapshot,features=prepare(['word '*n,'word '*n],root)
        start=time.perf_counter();out=analyze_reuse(snapshot,features,config);elapsed=time.perf_counter()-start
        row={"words_per_record":n,"characters_per_record":len('word '*n),"record_count":2,"candidate_pair_count":out['candidate_pair_count'],"budget_complete":out['budget_complete'],"seconds":elapsed,"pair_count":len(out['pairs']),"matching_tokens":out['pairs'][0]['matching_passages'][0]['token_count']}
        result['reuse'].append(row);print(json.dumps(row),flush=True)
    cases=[
       ('bare','https://example.org'),
       ('URL-only label','[https://example.org](https://example.org)'),
       ('ordinary label','[Read more](https://example.org)'),
       ('mixed descriptive label','[Read https://example.org for details](https://example.org)'),
       ('same mixed label inside quote','> [Read https://example.org for details](https://example.org)'),
    ]
    for name,text in cases:
        snapshot,features=prepare([text],root)
        row={"case":name,"source":text,"links":[dict(x) for x in features[0]['links']],"link_count":len(features[0]['links'])}
        result['links'].append(row);print(json.dumps(row),flush=True)
Path(sys.argv[1]).write_text(json.dumps(result,indent=2,default=list)+'\n')
