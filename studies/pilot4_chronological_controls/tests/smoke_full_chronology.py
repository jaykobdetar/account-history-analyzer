"""One explicitly synthetic ordinary-CLI smoke, never a corpus study execution."""
import argparse
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_full_chronology as runner
from score_saved_chronology import checked_windows
from chronology_math import legal_grid,score_case


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--private',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    a=parser.parse_args();a.private.mkdir(mode=0o700,exist_ok=False)
    environment={'PYTHONPATH':'/tmp/ahas-pilot3-installed','PYTHONHASHSEED':'7','TZ':'UTC'}
    identity=runner.baseline_identity(environment)
    # Identical synthetic windows intentionally exercise executed constant-series status.
    words=('the careful synthetic writer describes an ordinary example using simple words and clear sentences today').split()
    prose=' '.join((words*9)[:125])
    assert len(prose.split())==125
    start=datetime(2025,1,1,tzinfo=timezone.utc)
    records=[{'schema_version':'1.0.0','id':f'synthetic-{i:03d}','account_id':'synthetic-account','kind':'comment',
              'text':prose,'status':'present','created_utc':(start+timedelta(hours=i)).isoformat().replace('+00:00','Z'),
              'subreddit':'synthetic-community'} for i in range(64)]
    manifest={'schema_version':'1.0.0','snapshot_id':'synthetic-snapshot','account_id':'synthetic-account',
              'source_category':'synthetic','text_format':'plain','default_language':'en','coverage':{'status':'unknown'}}
    source=a.private/'records.jsonl';source.write_text(''.join(json.dumps(r)+'\n' for r in records))
    snapshot=a.private/'snapshot.json';runner.write(snapshot,manifest)
    metadata=[{'record_id':r['id'],'retained_words':125,'style_eligible':True,'created_utc':r['created_utc']} for r in records]
    spec=a.private/'worker.json';runner.write(spec,{'case':{'case_id':'synthetic-smoke','input':str(source),'manifest':str(snapshot)},
            'root':str(a.private),'limits':runner.EXPECTED_LIMITS,'environment':environment})
    runner.write(a.private/'start-binding.json',{'explicitly_synthetic':True,'real_corpus_rows':0,
        'script_sha256':runner.sha(__file__),'runner_sha256':runner.sha(runner.__file__),
        'score_adapter_sha256':runner.sha(Path(__file__).resolve().parents[1]/'scripts/score_saved_chronology.py'),
        'math_sha256':runner.sha(Path(__file__).resolve().parents[1]/'scripts/chronology_math.py'),
        'source_sha256':runner.sha(source),'manifest_sha256':runner.sha(snapshot),'baseline':identity})
    process=subprocess.run([sys.executable,'-B',runner.__file__,'--worker',str(spec)],timeout=630)
    assert process.returncode==0,'Synthetic worker failed'
    receipt=json.loads((a.private/'synthetic-smoke/receipt.json').read_bytes())
    assert receipt['exit_code']==0,'Synthetic ordinary analyzer failed'
    directory=a.private/'synthetic-smoke/analysis'
    result=json.loads((directory/'results.json').read_bytes())
    primary=runner.extract_primary(result,receipt['exit_code'])
    assert primary['status']=='ok' and primary['native_change_status']=='no_measurable_variation'
    assert primary['reason_codes']==[] and primary['candidate_intervals']==[]
    windows,validation=checked_windows(metadata,directory,primary['stream_id'])
    assert validation=='all_primary_memberships_counts_positions_verified'
    assert len(windows)==8 and all(w['qualified'] and w['record_count']==8 and w['word_count']==1000 for w in windows)
    grid=legal_grid(windows)
    assert [w['split_interval'] for w in grid]==[[24,24],[32,32],[40,40]]
    score=score_case(candidate_intervals=primary['candidate_intervals'],status=primary['status'],
                    reason_codes=primary['reason_codes'],truth_k=None,control_junction_k=32,
                    windows=windows,record_timestamps=[r['created_utc'] for r in metadata])
    assert score['executed'] and score['candidate_count']==0 and score['candidate_occurrence'] is False
    assert runner.artifact_inventory(directory)==receipt['artifacts']
    report={'status':'passed','explicitly_synthetic':True,'real_corpus_records':0,'ordinary_cli_executions':1,
            'record_count':64,'retained_words':8000,'qualified_windows':8,'words_per_window':1000,
            'records_per_window':8,'legal_split_intervals':[[24,24],[32,32],[40,40]],
            'native_change_status':primary['native_change_status'],'normalized_status':primary['status'],
            'candidate_count':score['candidate_count'],'candidate_occurrence':score['candidate_occurrence'],
            'primary_window_check':validation,'artifact_count':len(receipt['artifacts']),
            'artifact_bytes':sum(r['bytes'] for r in receipt['artifacts']),
            'artifact_inventory':receipt['artifacts'],'analysis_wall_seconds':receipt['wall_seconds'],
            'analysis_peak_rss_mib':receipt['child_peak_rss_mib'],
            'private_start_binding_sha256':runner.sha(a.private/'start-binding.json'),
            'private_receipt_sha256':runner.sha(a.private/'synthetic-smoke/receipt.json')}
    a.report.parent.mkdir(parents=True,exist_ok=True);runner.write(a.report,report)
    print(json.dumps({k:v for k,v in report.items() if k!='artifact_inventory'},sort_keys=True))


if __name__=='__main__':main()
