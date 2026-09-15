"""Four-case native/window arithmetic check; stdlib only, no analyzer calls."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import signal

CONDITIONS=('continuity_same_community','switch_same_community',
            'continuity_changed_community','switch_changed_community')
FP='bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179'
CONFIG='8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925'


def require(ok,code):
    if not ok:raise ValueError(code)


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def read(path):return json.loads(Path(path).read_bytes())


def timestamp(value):return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc)


def stamp(value):return value.isoformat().replace('+00:00','Z')


def error(interval,k):
    lo,hi=interval
    require(type(lo) is int and type(hi) is int and 1<=lo<=hi,'bad_split_interval')
    return min(abs(k-point) for point in range(lo,hi+1))


def bracket(interval,times):
    lo,hi=interval;left,right=times[lo-1],times[hi]
    return {'split_interval':list(interval),'possible_split_position_count':hi-lo+1,
        'record_gap_positions':hi-lo,'left_record_position':lo-1,'right_record_position':hi,
        'left_utc':stamp(left),'right_utc':stamp(right),'elapsed_seconds':(right-left).total_seconds()}


def reconstruct(rows):
    windows=[];positions=[];words=0
    for i,row in enumerate(rows):
        require(type(row['style_eligible']) is bool,'bad_eligibility_flag')
        if not row['style_eligible'] or row['kind']!='comment':continue
        require(type(row['retained_words']) is int and row['retained_words']>=20,'bad_retained_word_count')
        words+=row['retained_words'];positions.append(i)
        if words>=1000 and len(positions)>=8:
            windows.append({'qualified':True,'positions':positions,'word_count':words});positions=[];words=0
    if positions:windows.append({'qualified':False,'positions':positions,'word_count':words})
    return windows


def grid(windows):
    usable=[w for w in windows if w['qualified']]
    return [{'window_index':j,'split_interval':[usable[j-1]['positions'][-1]+1,usable[j]['positions'][0]]}
            for j in range(3,len(usable)-2)] if len(usable)>=8 else []


def localization(intervals,k,best,times):
    nearest=min(intervals,key=lambda x:(error(x,k),x)) if intervals else None
    distance=error(nearest,k) if nearest else None
    match=None if intervals is None else distance is not None and distance<=10
    return {'reference_split_k':k,'matched_within_tolerance':match,
        'exact_interval_containment':None if intervals is None else distance==0,
        'nearest_interval_error_records':distance,'nearest_interval':bracket(nearest,times) if nearest else None,
        'excess_error_over_best_grid_records':distance-best if distance is not None and best is not None else None,
        'matched_candidate_count':int(match) if match is not None else None,
        'unmatched_candidate_count':len(intervals)-int(match) if match is not None else None}


def native(result,exit_code):
    if result is None:
        return {'status':'resource_limit' if exit_code==4 else 'unavailable',
            'reasons':sorted(['no_results_artifact']+(['whole_pipeline_incomplete'] if exit_code!=0 else [])),
            'native_status':None,'intervals':None,'stream':None}
    require(result['analysis']['implementation_fingerprint']==FP and
            result['analysis']['config_sha256']==CONFIG,'native_identity_changed')
    style=result.get('modules',{}).get('style',{}).get('payload') or {}
    streams=[s for s in style.get('streams',[]) if (s['scope_type'],s['kind'],s['subreddit'])==('pooled','comment',None)]
    require(len(streams)<=1,'ambiguous_primary_stream');stream=streams[0] if streams else None
    changes=[c for c in style.get('changes',[]) if stream and c['stream_id']==stream['stream_id']]
    require(len(changes)<=1,'ambiguous_primary_change');change=changes[0] if changes else None
    state=change['status'] if change else None
    if exit_code!=0:status='resource_limit' if exit_code==4 else 'unavailable';reasons=['whole_pipeline_incomplete']
    elif change is None:status='abstained';reasons=['requested_scope_not_selected_or_eligible']
    elif state not in ('ok','no_measurable_variation'):status='abstained';reasons=sorted(set(change['reason_codes']+[state]))
    else:status='ok';reasons=[]
    intervals=None
    if status=='ok':
        intervals=[]
        for boundary in change['boundaries']:
            left,right=boundary['record_interval']
            require(type(left) is int and type(right) is int and 0<=left<right,'bad_native_record_interval')
            intervals.append([left+1,right])
        require(state!='no_measurable_variation' or not intervals,'constant_series_has_candidates')
    return {'status':status,'reasons':reasons,'native_status':state,'intervals':intervals,'stream':stream}


def checked_case(case,attempt,run_root,scored):
    rows=read(case['metadata'])['records'];times=[timestamp(r['created_utc']) for r in rows]
    require(times==sorted(times),'metadata_not_chronological')
    k=case['truth_k'] if case['source_switch'] else case['control_junction_k']
    windows=reconstruct(rows);boundaries=grid(windows)
    distances=[error(g['split_interval'],k) for g in boundaries];best=min(distances) if distances else None
    best_boundary=min(boundaries,key=lambda g:(error(g['split_interval'],k),g['window_index'])) if boundaries else None
    directory=Path(run_root)/case['case_id']/'analysis';result_path=directory/'results.json'
    receipt=attempt.get('receipt');exit_code=attempt.get('effective_exit_code',receipt['exit_code'] if receipt else None)
    try:result=read(result_path) if result_path.exists() else None
    except json.JSONDecodeError:
        require(exit_code!=0,'successful_invalid_results');result=None
    extracted=native(result,exit_code);executed=extracted['status']=='ok';intervals=extracted['intervals']
    if executed:
        requested=extracted['stream']['window_ids'];require(len(requested)==len(set(requested)),'duplicate_declared_windows')
        saved=[r for r in map(json.loads,(directory/'windows.jsonl').read_text().splitlines()) if r['window_id'] in set(requested)]
        saved.sort(key=lambda w:w['first_record_position'])
        require([w['window_id'] for w in saved]==requested and len(saved)==len(windows),'primary_window_set_changed')
        for actual,expected in zip(saved,windows):
            positions=expected['positions']
            require(actual['stream_id']==extracted['stream']['stream_id'] and actual['qualified']==expected['qualified']
                and actual['word_count']==expected['word_count'] and actual['record_count']==len(positions)
                and actual['first_record_position']==positions[0] and actual['last_record_position']==positions[-1]
                and actual['record_ids']==[rows[p]['record_id'] for p in positions],'native_window_membership_mismatch')
        require(scored['primary_window_check']=='all_primary_memberships_counts_positions_verified','reported_window_check_mismatch')
        require(all(interval in [g['split_interval'] for g in boundaries] for interval in intervals),'native_candidate_off_grid')
    expect={'tolerance_records':10,'status':extracted['status'],'reason_codes':extracted['reasons'],
        'executed':executed,'candidate_occurrence':bool(intervals) if executed else None,
        'candidate_count':len(intervals) if executed else None,
        'candidate_intervals':[bracket(v,times) for v in intervals] if executed else None,
        'truth_boundaries':[k] if case['source_switch'] else [],
        'switch_localization':localization(intervals,k,best,times) if case['source_switch'] else None,
        'control_junction_diagnostic':None if case['source_switch'] else localization(intervals,k,best,times),
        'grid_resolution':{'reference_type':'source_switch_truth' if case['source_switch'] else 'control_construction_junction',
            'reference_split_k':k,'qualified_window_count':sum(w['qualified'] for w in windows),
            'minimum_qualified_windows':8,'minimum_segment_windows':3,'adequate_window_count':len(boundaries)>0,
            'legal_boundary_count':len(boundaries),'best_interval_error_records':best,
            'attainable_within_tolerance':best<=10 if best is not None else None,
            'exact_containment_attainable':best==0 if best is not None else None,
            'nearest_legal_boundary':dict(best_boundary,**bracket(best_boundary['split_interval'],times)) if best_boundary else None,
            'legal_boundaries':[dict(g,**bracket(g['split_interval'],times)) for g in boundaries]}}
    for key,value in expect.items():require(scored['score'][key]==value,'reported_'+key+'_mismatch')
    require(scored['native_change_status']==extracted['native_status'],'reported_native_status_mismatch')
    require(scored['record_count']==len(rows) and scored['retained_words']==sum(r['retained_words'] for r in rows),'reported_volume_mismatch')
    require(scored['results_sha256']==(sha(result_path) if result_path.exists() else None),'results_hash_mismatch')
    temporal=scored['score']['temporal_resolution']
    require(temporal['construction_junction']==bracket([k,k],times),'junction_calendar_bracket_mismatch')
    expected_windows=[{'window_index':i,'first_record_position':w['positions'][0],'last_record_position':w['positions'][-1],
        'record_count':len(w['positions']),'word_count':w['word_count'],'first_utc':stamp(times[w['positions'][0]]),
        'last_utc':stamp(times[w['positions'][-1]]),'straddles_construction_junction':w['positions'][0]<k<=w['positions'][-1]}
        for i,w in enumerate(w for w in windows if w['qualified'])]
    require(temporal['qualified_windows']==expected_windows,'qualified_window_calendar_resolution_mismatch')
    return {'condition':case['condition'],'native_status':extracted['native_status'],'executed':executed,
        'candidate_count':expect['candidate_count'],'candidate_occurrence':expect['candidate_occurrence'],
        'candidate_split_intervals':intervals,'junction_k':k,'best_grid_error_records':best,
        'qualified_windows':sum(w['qualified'] for w in windows),'localization':localization(intervals,k,best,times),
        'reference_is_source_switch':case['source_switch'],'results_sha256':scored['results_sha256']}


def check(index_path,registration,run_root,scores):
    plan=read(registration);index=read(index_path);cases=read(Path(scores)/'cases.json');summary=read(Path(scores)/'summary.json')
    require(plan['prepared_index_sha256']==sha(index_path),'registered_index_mismatch')
    for row in plan['bound_artifacts']:require(sha(row['path'])==row['sha256'],'execution_bound_artifact_changed')
    require([c['condition'] for c in index['cases']]==list(CONDITIONS),'four_condition_index_required')
    require([c['case_id'] for c in cases]==[c['case_id'] for c in index['cases']],'four_score_rows_required')
    execution=read(Path(run_root)/'execution.json');binding=read(Path(run_root)/'start-binding.json')
    require(binding['registration_sha256']==sha(registration) and binding['index_sha256']==sha(index_path)
        and not binding['replay'],'main_execution_binding_mismatch')
    require([r['case_id'] for r in execution['cases']]==[c['case_id'] for c in cases],'execution_case_membership_mismatch')
    checked=[checked_case(case,attempt,run_root,scored) for case,attempt,scored in zip(index['cases'],execution['cases'],cases,strict=True)]
    require(summary['planned_histories']==4 and summary['distinct_samples']==5 and summary['shared_anchor_count']==1
        and summary['executed_histories']==sum(c['executed'] for c in checked),'summary_denominator_mismatch')
    contrasts=[]
    for first in (0,2):
        control,switch=checked[first:first+2];both=control['executed'] and switch['executed']
        contrasts.append({'community_change':first==2,'both_executed':both,
            'switch_minus_control_candidate_occurrence':int(switch['candidate_occurrence'])-int(control['candidate_occurrence']) if both else None,
            'switch_minus_control_candidate_count':switch['candidate_count']-control['candidate_count'] if both else None})
    require(summary['descriptive_switch_minus_control']==contrasts,'paired_contrast_mismatch')
    return {'status':'passed','cases_checked':4,'one_shared_anchor_unit':True,'cases':checked,
        'paired_contrasts':contrasts,'analyzer_calls':0,'source_prose_inspected':False,
        'scope':'Independent native primary extraction, exact saved window memberships, interval/grid/calendar arithmetic and paired summary denominators; no production or prior-study arithmetic imports.'}


def main():
    p=argparse.ArgumentParser()
    for key in ('index','registration','run','scores','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('independent_review_time_limit')));signal.alarm(300)
    start={'started_utc':datetime.now(timezone.utc).isoformat(),'checker_sha256':sha(__file__),
        'index_sha256':sha(a.index),'registration_sha256':sha(a.registration),
        'cases_sha256':sha(a.scores/'cases.json'),'summary_sha256':sha(a.scores/'summary.json')}
    with Path(str(a.out)+'.start-binding.json').open('x') as f:json.dump(start,f,sort_keys=True,indent=2)
    report=check(a.index,a.registration,a.run,a.scores);report['checker_sha256']=start['checker_sha256']
    with a.out.open('x') as f:json.dump(report,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps(report,sort_keys=True))


if __name__=='__main__':main()
