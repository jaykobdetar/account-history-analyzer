"""Recheck the preserved single synthetic CLI output after adapter correction.

No analyzer, preprocessing, or source-corpus run occurs. The first failed check
and successful underlying ordinary CLI artifacts remain unchanged.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_full_chronology as runner
from score_saved_chronology import checked_windows
from chronology_math import legal_grid,score_case


def main():
    p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    args=p.parse_args();root=args.private
    binding=json.loads((root/'start-binding.json').read_bytes())
    assert binding['explicitly_synthetic'] is True and binding['real_corpus_rows']==0
    assert binding['source_sha256']==runner.sha(root/'records.jsonl')
    assert binding['manifest_sha256']==runner.sha(root/'snapshot.json')
    receipt=json.loads((root/'synthetic-smoke/receipt.json').read_bytes())
    directory=root/'synthetic-smoke/analysis';assert receipt['exit_code']==0
    assert runner.artifact_inventory(directory)==receipt['artifacts']
    records=[json.loads(line) for line in (root/'records.jsonl').read_text().splitlines()]
    assert len(records)==64 and all(r['account_id']=='synthetic-account' and len(r['text'].split())==125 for r in records)
    metadata=[{'record_id':r['id'],'retained_words':125,'style_eligible':True,'created_utc':r['created_utc']} for r in records]
    result=json.loads((directory/'results.json').read_bytes());primary=runner.extract_primary(result,receipt['exit_code'])
    assert primary['status']=='ok' and primary['native_change_status']=='no_measurable_variation'
    assert primary['reason_codes']==[] and primary['candidate_intervals']==[]
    windows,validation=checked_windows(metadata,directory,primary['stream_id'],primary['primary_window_ids'])
    assert validation=='all_primary_memberships_counts_positions_verified'
    assert len(windows)==8 and all(w['qualified'] and w['record_count']==8 and w['word_count']==1000 for w in windows)
    assert [w['split_interval'] for w in legal_grid(windows)]==[[24,24],[32,32],[40,40]]
    score=score_case(candidate_intervals=primary['candidate_intervals'],status=primary['status'],
                    reason_codes=primary['reason_codes'],truth_k=None,control_junction_k=32,
                    windows=windows,record_timestamps=[r['created_utc'] for r in metadata])
    assert score['executed'] and score['candidate_count']==0 and score['candidate_occurrence'] is False
    all_windows=[json.loads(line) for line in (directory/'windows.jsonl').read_text().splitlines()]
    same_stream_count=sum(row['stream_id']==primary['stream_id'] for row in all_windows)
    assert same_stream_count==21 and len(primary['primary_window_ids'])==8
    output={'status':'passed','explicitly_synthetic':True,'real_corpus_records':0,'new_analyzer_executions':0,
            'preserved_ordinary_cli_executions':1,'record_count':64,'retained_words':8000,
            'qualified_primary_windows':8,'words_per_primary_window':1000,'records_per_primary_window':8,
            'all_saved_windows_with_same_stream_id':21,'sensitivity_windows_correctly_separated':13,
            'legal_split_intervals':[[24,24],[32,32],[40,40]],'primary_window_check':validation,
            'native_change_status':primary['native_change_status'],'normalized_status':primary['status'],
            'candidate_count':score['candidate_count'],'candidate_occurrence':score['candidate_occurrence'],
            'artifact_count':len(receipt['artifacts']),'artifact_bytes':sum(a['bytes'] for a in receipt['artifacts']),
            'artifact_inventory':receipt['artifacts'],'analysis_wall_seconds':receipt['wall_seconds'],
            'analysis_peak_rss_mib':receipt['child_peak_rss_mib'],
            'original_start_binding_sha256':runner.sha(root/'start-binding.json'),
            'original_receipt_sha256':runner.sha(root/'synthetic-smoke/receipt.json'),
            'checker_sha256':runner.sha(__file__),'updated_runner_sha256':runner.sha(runner.__file__),
            'updated_score_adapter_sha256':runner.sha(Path(__file__).resolve().parents[1]/'scripts/score_saved_chronology.py')}
    runner.write(args.report,output)
    print(json.dumps({k:v for k,v in output.items() if k!='artifact_inventory'},sort_keys=True))

if __name__=='__main__':main()
