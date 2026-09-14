"""Record one actual command; refuse to overwrite an earlier execution."""
import datetime
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

prefix=Path(sys.argv[1])
command=sys.argv[2:]
assert command
prefix.parent.mkdir(parents=True,exist_ok=True)
receipt_path=Path(str(prefix)+'.receipt.json')
if receipt_path.exists():
    raise SystemExit('refusing to overwrite a historical command receipt')
start=datetime.datetime.now(datetime.UTC).isoformat()
tick=time.perf_counter()
with Path(str(prefix)+'.stdout.log').open('xb') as out, Path(str(prefix)+'.stderr.log').open('xb') as err:
    result=subprocess.run(command,stdout=out,stderr=err)
usage=resource.getrusage(resource.RUSAGE_CHILDREN)
receipt={'command':command,'cwd':str(Path.cwd()),'started_utc':start,
         'finished_utc':datetime.datetime.now(datetime.UTC).isoformat(),
         'exit_code':result.returncode,'wall_seconds':time.perf_counter()-tick,
         'peak_rss_kib':usage.ru_maxrss,'measurement_scope':'this command and descendants; separate from canonical results'}
for name in ('stdout','stderr'):
    receipt[name+'_sha256']=hashlib.sha256(Path(str(prefix)+'.'+name+'.log').read_bytes()).hexdigest()
receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt),flush=True)
sys.exit(result.returncode)
