"""Recompute available genuine modules and re-render supplied results.
Does not execute full pipeline or pinned ruptures. Uses the shipped snapshots,
results, windows and evidence; exact byte comparisons are reported individually.
"""
import json,sys,time,runpy,platform,importlib.metadata
from pathlib import Path
repo=Path(sys.argv[1]).resolve();sys.path.insert(0,str(repo/'src'))
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import load_snapshot,canonical_bytes,sha256_bytes
from account_history_analyzer.features import extract_records,pooled
from account_history_analyzer.activity import analyze_activity
from account_history_analyzer.reuse import analyze_reuse
from account_history_analyzer.links import analyze_links
from account_history_analyzer.interactions import analyze_interactions
from account_history_analyzer.artifacts import jsonl_bytes,verify_artifacts
from account_history_analyzer.reporting import render_html,render_markdown
from account_history_analyzer.charts import render_charts
ResourceAudit=runpy.run_path(str(repo/'tests/test_security.py'))['ResourceAudit']
c=AnalysisConfig.from_toml(repo/'config/default.toml')
output={'environment':{'python':platform.python_version(),'packages':{}},'cases':[]}
for package in ['numpy','scipy','markdown-it-py','jsonschema','pytest','ruptures','hypothesis']:
    try:output['environment']['packages'][package]=importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:output['environment']['packages'][package]=None
for name in ['arithmetic','empty','edge_cases','stable_constructed_style','constructed_topic_shift','constructed_style_shift']:
    start=time.perf_counter();directory=repo/'output'/name
    stored=json.loads((directory/'results.json').read_bytes())
    evidence=[json.loads(line) for line in (directory/'evidence.jsonl').read_text().splitlines()]
    windows=[json.loads(line) for line in (directory/'windows.jsonl').read_text().splitlines()]
    snapshot=load_snapshot(repo/'fixtures'/f'{name}.jsonl',repo/'fixtures'/f'{name}.snapshot.json',c)
    features=extract_records(snapshot,c)
    checks={'snapshot':snapshot.canonical_sha256==stored['snapshot']['canonical_sha256'],
            'records_features_bytes':jsonl_bytes(features)==(directory/'records_features.jsonl').read_bytes()}
    for module,actual in [('text',{'body':pooled(features,c),'titles':pooled([f['title'] for f in features if f.get('title') is not None],c)}),('activity',analyze_activity(snapshot,c)),('reuse',analyze_reuse(snapshot,features,c)),('links',analyze_links(snapshot,features,windows,c)),('interactions',analyze_interactions(snapshot,c))]:
        checks[module+'_payload_bytes']=canonical_bytes(actual)==canonical_bytes(stored['modules'][module]['payload'])
    renders={'report.md':render_markdown(stored,evidence,windows=windows).encode(),
             'report.html':render_html(stored,evidence,windows=windows).encode(),
             **render_charts(stored,windows)}
    rendered={name:data==(directory/name).read_bytes() for name,data in renders.items()}
    htmlaudit=ResourceAudit();htmlaudit.feed(renders['report.html'].decode())
    item={'fixture':name,'records':len(snapshot.records),'checks':checks,'rendered_byte_matches':rendered,
          'static_html_security_violations':htmlaudit.violations,'seconds':time.perf_counter()-start}
    output['cases'].append(item);print(json.dumps(item),flush=True)
Path(sys.argv[2]).write_text(json.dumps(output,indent=2)+'\n')
assert all(all(item['checks'].values()) and all(item['rendered_byte_matches'].values()) and not item['static_html_security_violations'] for item in output['cases'])
