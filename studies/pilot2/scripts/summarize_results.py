#!/usr/bin/env python3
"""Publish complete saved outcomes without source prose or account-key maps."""
import csv,hashlib,json
from collections import Counter
from pathlib import Path
from markdown_it import MarkdownIt

ROOT=Path(__file__).resolve().parents[1]

def read(path):return json.loads(path.read_bytes())
def write(path,value):
    with path.open('x') as target:json.dump(value,target,ensure_ascii=False,allow_nan=False,indent=2);target.write('\n')
def cell(value):
    if value is None:return 'unavailable'
    return str(value).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('|','&#124;').replace('\n',' ')
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(map(cell,headers))+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(cell,row))+' |' for row in rows])+'\n'

def render(path,markdown):
    path.write_text(markdown)
    body=MarkdownIt('commonmark',{'html':False,'typographer':False,'linkify':False}).enable('table').render(markdown)
    page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>AHAS pilot 2 saved outcomes</title><style>body{font:16px/1.55 system-ui,sans-serif;margin:2rem auto;padding:0 1.5rem;max-width:110rem;color:#17242e}table{border-collapse:collapse;display:block;overflow-x:auto;margin:1.5rem 0}th,td{border:1px solid #bbc9d3;padding:.45rem .65rem;text-align:left}th{background:#edf3f6}code{overflow-wrap:anywhere}a{color:#075d89}</style><body>'+body+'</body></html>\n'
    path.with_suffix('.html').write_text(page)

def main():
    freeze=read(ROOT/'protocol/scoring-freeze.json')
    prepared=ROOT/freeze['paired_prepared_directory']
    observations=read(prepared/'private/pair-observations.json')
    by_key={(row['home_community'],row['condition'],row['arm'],row['pair_id']):row for row in observations}
    batches=[];all_rows=[]
    for run in read(ROOT/'outputs/paired/execution-index.json')['runs']:
        result_path=ROOT/run['output']/'evaluation.json'
        meta={key:run[key] for key in ('home_community','condition','arm','method','primary_method')}
        if not result_path.exists():
            batches.append({**meta,'status':'execution_failed','exit_code':run['driver_exit_code'],'partitions':None});continue
        result=read(result_path);partitions={}
        for split,partition in result['partitions'].items():
            rows=partition['rows']
            distributions={label:sorted(row['score'] for row in rows if row['label']==label and row['score'] is not None) for label in ('same_author','different_author')}
            partitions[split]={'metrics':partition['metrics'],'complete_score_distributions':distributions,
                'reason_counts':dict(Counter(reason for row in rows for reason in row['reason_codes']))}
            for row in rows:
                paired=by_key[run['home_community'],run['condition'],run['arm'],row['pair_id']]
                all_rows.append({**meta,'partition':split,'pair_id':row['pair_id'],'block_id':paired['block_id'],
                    'label':row['label'],'status':row['status'],'score':row['score'],'raw_distance_below_guard_is_not_qualified':row['raw_distance'],
                    'reason_codes':row['reason_codes'],'left_volume':paired['left'],'right_volume':paired['right'],
                    'median_time_gap_seconds':paired['pair_median_time_gap_seconds']})
        batches.append({**meta,'status':result['status'],'exit_code':run['driver_exit_code'],'partitions':partitions,
                        'source_output_sha256':hashlib.sha256(result_path.read_bytes()).hexdigest()})
    write(ROOT/'review/paired-outcomes.json',batches);write(ROOT/'review/pair-observations.json',all_rows)
    metric_rows=[]
    for batch in batches:
        for split,part in (batch['partitions'] or {}).items():
            metrics=part['metrics']
            metric_rows.append([batch['home_community'],batch['condition'],batch['arm'],batch['method'],split,
                metrics['scored_pair_count'],metrics['total_pair_count'],metrics['abstained_pair_count'],
                metrics['ranking']['roc_auc']['value'],metrics['ranking']['average_precision']['value']])
    headings=['Home community','Condition','Arm','Method','Partition','Scored','Planned','Abstained','AUC','AP']
    with (ROOT/'review/paired-metrics.csv').open('x',newline='') as target:
        writer=csv.writer(target);writer.writerow(headings);writer.writerows(metric_rows)
    render(ROOT/'review/PAIRED_OUTCOMES.md','# Complete paired-text outcomes\n\nCoverage precedes ranking. Labels describe equality or difference of supplier account IDs, not verified human authorship. Retained-prose n=4 is the predeclared primary method; no threshold was fitted. Every score and abstention is in [pair-observations.json](pair-observations.json), and complete sorted score distributions are in [paired-outcomes.json](paired-outcomes.json). Related pairs, methods and omission arms are not independent people. No IID confidence interval is asserted. Confirmation units were not scored.\n\n'+table(headings,metric_rows))
    plan=read(ROOT/'prepared/streams/stream-plan.json')
    cases={case['case_id']:case for case in plan['cases']+plan.get('operational_availability_views',[])}
    streams=[];availability=[]
    for run in read(ROOT/'outputs/streams/execution-index.json')['runs']:
        case=cases[run['case_id']];output=ROOT/run['output'];op=output.parent/(output.name+'.operation')
        operation=read(op/'run.json') if (op/'run.json').exists() else None
        grid=read(op/'grid-diagnostic.json') if (op/'grid-diagnostic.json').exists() else None
        row={'case_id':run['case_id'],'preparation_status':case['preparation_status'],'preparation_reasons':case.get('reason_codes',[]),
             'driver_exit_code':run['driver_exit_code'],'execution_status':operation['status'] if operation else 'driver_failed',
             'grid_diagnostic':grid,'native_observation':None}
        if (output/'evaluation.json').exists():
            value=read(output/'evaluation.json')
            row['native_observation']=[observation for partition in value['partitions'].values() for observation in partition['rows']]
        streams.append(row)
        if (output/'results.json').exists():
            value=read(output/'results.json')
            for name,module in value['modules'].items():
                availability.append({'case_id':run['case_id'],'module':name,'status':module['status'],
                                     'reason_codes':module.get('reason_codes',[]),'truth_status':'unknown; operational availability only'})
    write(ROOT/'review/stream-outcomes.json',streams);write(ROOT/'review/module-availability.json',availability)
    stream_rows=[]
    for row in streams:
        grid=row['grid_diagnostic'] or {}
        stream_rows.append([row['case_id'],row['preparation_status'],row['execution_status'],grid.get('analysis_scope_status'),
            grid.get('qualified_windows'),len(grid['candidate_intervals']) if grid.get('candidate_intervals') is not None else None,
            grid.get('nearest_candidate_error_original_ordinals'),grid.get('best_legal_grid_error'),
            grid.get('tolerance_attainable'),grid.get('matched_at_original_tolerance')])
    render(ROOT/'review/STREAM_OUTCOMES.md','# Complete chronological and operating outcomes\n\nFour source pairs were formed; the two planned Cornell pair slots remained unfilled. All planned slots and fixed omissions remain visible below. Continuity controls describe no source-account ID reassignment, not stable human authorship. Unknown-truth views and their operational omission descendants have no accuracy labels. The ten-record tolerance is unchanged; an unattainable legal grid remains a failure of that precision requirement. The chronological study is exploratory, not an independent held-out replication.\n\n'+table(['Case','Preparation','Execution','Change scope status','Qualified windows','Candidates','Nearest error','Best legal error','Tolerance attainable','Matched within 10'],stream_rows)+'\n## Module availability\n\nThese are reused ordinary-analysis views of two natural histories, not new independent subjects. Missing Cornell views remain unfilled above. Full module results were not exported by the account-stream evaluator and are not inferred here.\n\n'+table(['Case','Module','Status','Reasons'],[[row['case_id'],row['module'],row['status'],', '.join(row['reason_codes'])] for row in availability]))
    print(json.dumps({'paired_batches':len(batches),'pair_method_arm_observations':len(all_rows),'stream_and_operational_slots':len(streams),'availability_rows':len(availability)}))

if __name__=='__main__':main()
