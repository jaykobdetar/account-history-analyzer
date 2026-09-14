#!/usr/bin/env python3
"""Measure genuine reuse work after preprocessing; use the offline runner."""
import argparse
import hashlib
import platform
from importlib import metadata
import json
import os
from pathlib import Path
import sys
import tempfile
import time

from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.features import extract_records
from account_history_analyzer.io import canonical_bytes, load_snapshot
from account_history_analyzer import reuse, __version__


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lengths',default='2000')
    parser.add_argument('--patterns',default='exact,edited')
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    if os.environ.get('AHAS_NETWORK_ISOLATION')!='linux_seccomp_socket_denial':
        parser.error('Run through scripts/offline_exec.py')
    results={'argv':[sys.executable,*sys.argv],'package_version':__version__,'installed_metadata_version':metadata.version('account-history-analyzer'),
             'python':platform.python_version(),'platform':platform.platform(),
             'reuse_source_sha256':hashlib.sha256(Path(reuse.__file__).read_bytes()).hexdigest(),
             'package_reuse_path':reuse.__file__,'network_isolation':os.environ['AHAS_NETWORK_ISOLATION'],
             'scope':'Reuse stage only; preprocessing excluded from timed interval','runs':[]}
    config=AnalysisConfig.from_toml()
    results['resolved_reuse_config']=dict(config['reuse'])
    with tempfile.TemporaryDirectory(prefix='ahas-reuse-probe-') as temporary:
        path=Path(temporary)
        manifest={'schema_version':'1.0.0','snapshot_id':'resource-probe','account_id':'supplied',
                  'source_category':'synthetic','text_format':'plain','default_language':'en','coverage':{'status':'unknown'}}
        (path/'manifest.json').write_bytes(canonical_bytes(manifest))
        for pattern in args.patterns.split(','):
            for n in map(int,args.lengths.split(',')):
                if n<20: raise ValueError('Use at least20 words for default pair qualification')
                tokens=['alpha']*n if pattern in {'exact','edited'} else [['alpha','beta','gamma'][i%3] for i in range(n)]
                if pattern=='near_edited':
                    vocabulary=['term'+chr(97+i//26)+chr(97+i%26) for i in range(31)]
                    tokens=[vocabulary[i%31] for i in range(n)]
                right=list(tokens)
                if pattern in {'edited','periodic_edited','near_edited'}: right[n//2]='different'
                elif pattern=='shifted': right=right[1:]+right[:1]
                elif pattern!='exact': raise ValueError('Unknown pattern '+pattern)
                records=[{'schema_version':'1.0.0','id':f'source{i}','account_id':'supplied','kind':'comment',
                          'text':' '.join(words),'status':'present','created_utc':f'2025-01-01T00:00:0{i}Z'}
                         for i,words in enumerate([tokens,right])]
                (path/'records.jsonl').write_bytes(b''.join(canonical_bytes(record) for record in records))
                snapshot=load_snapshot(path/'records.jsonl',path/'manifest.json',config)
                features=extract_records(snapshot,config)
                started=time.perf_counter()
                output=reuse.analyze_reuse(snapshot,features,config)
                elapsed=time.perf_counter()-started
                row={'pattern':pattern,'words_per_record':n,'codepoints_per_record':[len(record['text']) for record in records],
                     'elapsed_seconds':elapsed,'candidate_pair_count':output['candidate_pair_count'],
                     'near_status':output['near_status'],'budget_complete':output['budget_complete'],
                     'pair_count':len(output['pairs']),'near_duplicate_count':sum(pair['near_duplicate'] for pair in output['pairs']),
                     'pairs_sha256':hashlib.sha256(canonical_bytes(output['pairs'])).hexdigest(),'match_token_counts':[passage['token_count'] for pair in output['pairs'] for passage in pair['matching_passages']],
                     'resource_usage':output.get('resource_usage'),'resource_limit_reason':output.get('resource_limit_reason')}
                results['runs'].append(row)
                print(json.dumps(row,sort_keys=True),flush=True)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes(canonical_bytes(results))


if __name__=='__main__': main()
