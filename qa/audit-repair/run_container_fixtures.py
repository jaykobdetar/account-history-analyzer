import hashlib,json,os,subprocess,time
from pathlib import Path
root=Path.cwd();qa=root/'qa/audit-repair';out=qa/'container-output';out.mkdir(exist_ok=True)
receipt={'commands':[],'comparisons':[],'status':'running','network_isolation':'docker_network_none'}
for fixture in ['arithmetic','constructed_style_shift']:
 for operation in ['analyze','verify']:
  argv=['docker','run','--rm','--network','none','--user',f'{os.getuid()}:{os.getgid()}','--env','AHAS_NETWORK_ISOLATION=docker_network_none','--mount',f'type=bind,src={out},dst=/output','ahas-reference:1.0.2',operation,'--input',f'fixtures/{fixture}.jsonl','--manifest',f'fixtures/{fixture}.snapshot.json']
  argv+=['--out',f'/output/{fixture}'] if operation=='analyze' else ['--analysis-dir',f'/output/{fixture}','--recompute']
  start=time.perf_counter();p=subprocess.run(argv,capture_output=True,text=True,timeout=600)
  receipt['commands'].append({'argv':argv,'stdout':p.stdout,'stderr':p.stderr,'exit_code':p.returncode,'seconds':time.perf_counter()-start})
  (qa/'container-fixture-receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
  if p.returncode:raise SystemExit(p.stderr)
 print(fixture+' container analysis/recompute passed',flush=True)
receipt['status']='generated'
(qa/'container-fixture-receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
