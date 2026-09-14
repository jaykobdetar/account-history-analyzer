#!/usr/bin/env python3
"""Preserve each fresh command attempt, including nonzero exits."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--log-prefix', type=Path, required=True)
    p.add_argument('command', nargs=argparse.REMAINDER)
    args=p.parse_args()
    command=args.command[1:] if args.command[:1]==['--'] else args.command
    paths={k:Path(str(args.log_prefix)+'.'+k) for k in ('stdout.log','stderr.log','receipt.json')}
    if any(v.exists() for v in paths.values()):
        raise RuntimeError('Refuse to overwrite an earlier command attempt')
    start=datetime.now(timezone.utc).isoformat()
    t=time.monotonic()
    with paths['stdout.log'].open('xb') as out,paths['stderr.log'].open('xb') as err:
        result=subprocess.run(command,stdout=out,stderr=err)
    receipt={'argv':command,'cwd':str(Path.cwd()),'started_utc':start,
             'finished_utc':datetime.now(timezone.utc).isoformat(),
             'exit_code':result.returncode,'wall_seconds':time.monotonic()-t,
             'child_peak_rss_mib':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss/1024,
             'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'outputs':{k:{'bytes':v.stat().st_size,'sha256':hashlib.sha256(v.read_bytes()).hexdigest()}
                        for k,v in paths.items() if k!='receipt.json'}}
    paths['receipt.json'].write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt),flush=True)
    sys.exit(result.returncode)

if __name__=='__main__':
    main()
