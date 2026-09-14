#!/usr/bin/env python3
"""Execute only prepared paired batches bound by the final pre-score freeze."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import digest
from account_history_analyzer.pipeline import implementation_identity

ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    with path.open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()

def validate_freeze(root):
    freeze_path=root/'protocol/scoring-freeze.json'
    freeze=json.loads(freeze_path.read_bytes())
    if freeze.get('status')!='frozen' or freeze.get('scoring_authorized') is not True:
        raise ValueError('Scoring is not authorized by a completed input and audit freeze')
    for relative,expected in freeze['files'].items():
        path=(root/relative).resolve()
        if not path.is_relative_to(root.resolve()) or sha(path)!=expected:
            raise ValueError('Frozen file mismatch: '+relative)
    if implementation_identity()[0]!=freeze['implementation_fingerprint']:
        raise ValueError('Frozen production source mismatch')
    if digest(AnalysisConfig.from_toml().analytical())!=freeze['analysis_config_sha256']:
        raise ValueError('Frozen configuration mismatch')
    prepared=(root/freeze['paired_prepared_directory']).resolve()
    if not prepared.is_relative_to(root.resolve()):raise ValueError('Prepared directory leaves study root')
    summary=json.loads((prepared/'preparation-summary.json').read_bytes())
    for item in summary['datasets']:
        dataset=(prepared/item['path']).resolve()
        if sha(dataset)!=item['sha256']:raise ValueError('Prepared dataset mismatch')
        doc=json.loads(dataset.read_bytes())
        if {p['split'] for p in doc['pairs']} - {'development','evaluation'}:
            raise ValueError('Invalid scoring partition')
        for unit in doc['texts']:
            for field in ('input','manifest'):
                target=(dataset.parent/unit[field]).resolve()
                if not target.is_relative_to(prepared/'scored/units'):
                    raise ValueError('Confirmation or unapproved source referenced')
    return summary,prepared

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs',type=int,choices=(1,2),default=2)
    parser.add_argument('--only',help='Exact registered dataset filename stem, for a separate replay')
    parser.add_argument('--destination',default='outputs/paired')
    args=parser.parse_args()
    if os.environ.get('AHAS_NETWORK_ISOLATION')!='linux_seccomp_socket_denial':
        raise RuntimeError('Use the reference offline wrapper')
    summary,prepared=validate_freeze(ROOT)
    selected=[item for item in summary['datasets'] if args.only is None or Path(item['path']).stem==args.only]
    if not selected:raise ValueError('No registered dataset selected')
    dest=(ROOT/args.destination).resolve()
    if not dest.is_relative_to(ROOT) or dest.exists():raise ValueError('Use a new output destination inside this study')
    dest.mkdir(parents=True)
    def execute(item):
        name=Path(item['path']).stem
        command=[sys.executable,str(ROOT/'scripts/run_recorded.py'),str(dest/'logs'/name),
                 sys.executable,'-B','-m','account_history_analyzer','evaluate','--suite','paired_text',
                 '--dataset',str(prepared/item['path']),'--out',str(dest/name)]
        result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        # Child recorder captures the exact analysis command, RSS and raw logs.
        row={**item,'output':str((dest/name).relative_to(ROOT)),'driver_exit_code':result.returncode,
             'driver_stdout':result.stdout,'driver_stderr':result.stderr}
        print(json.dumps({'dataset':name,'exit_code':result.returncode}),flush=True)
        return row
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:rows=list(executor.map(execute,selected))
    result={'freeze_sha256':sha(ROOT/'protocol/scoring-freeze.json'),'jobs':args.jobs,
            'network_isolation':os.environ['AHAS_NETWORK_ISOLATION'],'runs':rows}
    (dest/'execution-index.json').write_text(json.dumps(result,indent=2)+'\n')
    return int(any(row['driver_exit_code'] for row in rows))

if __name__=='__main__':sys.exit(main())
