#!/usr/bin/env python3
"""Bounded orchestration of every registered whole-history case and omission."""
import argparse,hashlib,json,os,subprocess,sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs',type=int,choices=(1,2),default=2)
    parser.add_argument('--only',help='Exact registered case ID for separate replay')
    parser.add_argument('--destination',default='outputs/streams')
    args=parser.parse_args()
    if os.environ.get('AHAS_NETWORK_ISOLATION')!='linux_seccomp_socket_denial':
        raise RuntimeError('Run through reference offline wrapper')
    from prepare_streams import verify_scoring_freeze
    freeze=ROOT/'protocol/scoring-freeze.json'
    plan,_,_=verify_scoring_freeze(ROOT,freeze)
    cases=plan['cases']+plan.get('operational_availability_views',[])
    if args.only:cases=[case for case in cases if case['case_id']==args.only]
    if not cases:raise ValueError('No registered case selected')
    dest=(ROOT/args.destination).resolve()
    if not dest.is_relative_to(ROOT) or dest.exists():raise ValueError('Use a new output destination inside this study')
    dest.mkdir(parents=True)
    def execute(case):
        name=case['case_id']
        command=[sys.executable,str(ROOT/'scripts/run_recorded.py'),str(dest/'logs'/name),
                 sys.executable,'-B',str(ROOT/'scripts/prepare_streams.py'),'run-case',
                 '--root',str(ROOT),'--freeze',str(freeze),'--case',name,'--out',str(dest/name)]
        result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        row={'case_id':name,'preparation_status':case['preparation_status'],
             'execution_mode':case['execution_mode'],'output':str((dest/name).relative_to(ROOT)),
             'driver_exit_code':result.returncode,'driver_stdout':result.stdout,'driver_stderr':result.stderr}
        print(json.dumps({'case_id':name,'driver_exit_code':result.returncode}),flush=True)
        return row
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:rows=list(executor.map(execute,cases))
    result={'freeze_sha256':hashlib.sha256(freeze.read_bytes()).hexdigest(),'jobs':args.jobs,
            'network_isolation':os.environ['AHAS_NETWORK_ISOLATION'],'runs':rows}
    (dest/'execution-index.json').write_text(json.dumps(result,indent=2)+'\n')
    return int(any(row['driver_exit_code'] for row in rows))

if __name__=='__main__':sys.exit(main())
