#!/usr/bin/env python3
"""Download only the exact approved archive list under explicit byte limits."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen
import zipfile

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--data',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True)
    args=p.parse_args()
    plan=json.loads(args.plan.read_text())
    if args.receipt.exists():
        raise RuntimeError('Preserve prior acquisition receipt')
    args.data.mkdir(mode=0o700,parents=True,exist_ok=True)
    if sum(s['bytes'] for s in plan['sources'])>plan['max_download_bytes']:
        raise ValueError('Declared sources exceed download bound')
    start=time.monotonic()
    records=[]
    for source in plan['sources']:
        path=args.data/(source['community']+'.corpus.zip')
        part=path.with_suffix('.zip.partial')
        if path.exists() or part.exists():
            raise RuntimeError('Preserve any previous complete/partial acquisition')
        got=0
        h=hashlib.sha256()
        began=datetime.now(timezone.utc).isoformat()
        with urlopen(Request(source['url'],headers={'User-Agent':'AHAS-authorized-archive-study/1.0'}),timeout=60) as response, part.open('xb') as f:
            headers={k:response.headers.get(k) for k in ('Content-Length','Content-Type','Last-Modified','ETag')}
            if response.status!=200:
                raise RuntimeError('Unexpected source HTTP status')
            while True:
                chunk=response.read(1024*1024)
                if not chunk:
                    break
                got+=len(chunk)
                if got>source['bytes'] or time.monotonic()-start>plan['max_wall_seconds']:
                    raise RuntimeError('Acquisition byte/time limit exhausted; preserve partial file')
                f.write(chunk)
                h.update(chunk)
        part.chmod(0o600)
        if got!=source['bytes']:
            raise RuntimeError('Archive byte count differs from frozen official index')
        with zipfile.ZipFile(part) as z:
            members=[{'name':i.filename,'bytes':i.file_size,'compressed_bytes':i.compress_size} for i in z.infolist()]
            utterances=[i for i in members if i['name']=='utterances.jsonl']
            if len(utterances)!=1:
                raise RuntimeError('No unique utterances.jsonl member')
        part.rename(path)
        records.append({**source,'sha256':h.hexdigest(),'bytes_received':got,'started_utc':began,
                        'finished_utc':datetime.now(timezone.utc).isoformat(),'headers':headers,'members':members})
        print(json.dumps({'community':source['community'],'bytes':got,'sha256':h.hexdigest()}),flush=True)
    args.receipt.write_text(json.dumps({'status':'acquired','plan_sha256':hashlib.sha256(args.plan.read_bytes()).hexdigest(),
          'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'source_count':len(records),'total_bytes':sum(r['bytes_received'] for r in records),
          'wall_seconds':time.monotonic()-start,'sources':records},indent=2)+'\n')

if __name__=='__main__':
    main()
