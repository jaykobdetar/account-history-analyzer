"""Independent saved-result arithmetic and integrity check; Python stdlib only.

Reads bound metadata and saved primary boundaries/windows. It never imports
analyzer, preparation, scorer, or study arithmetic modules. Public output is
limited to status, counts, resource observations, and file hashes.
"""
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import resource
import signal
import time

SCHEMA='pilot4-chronology-math-v1'
FINGERPRINT='bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179'
CONFIG='8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925'
CONDITIONS=('continuity_same_community','switch_same_community','continuity_changed_community','switch_changed_community')
ANCHORS=('AX','AY','BX','BY')
OPERATIONAL={'ingest_receipt.json','run_receipt.json'}


def require(condition,code):
    if not condition:raise ValueError(code)

def same(actual,expected,code='arithmetic_mismatch'):
    require(type(actual) is type(expected),code)
    if isinstance(expected,dict):
        require(set(actual)==set(expected),code)
        for key in expected:same(actual[key],expected[key],code)
    elif isinstance(expected,list):
        require(len(actual)==len(expected),code)
        for a,b in zip(actual,expected):same(a,b,code)
    else:require(actual==expected and (not isinstance(actual,float) or math.isfinite(actual)),code)

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def read(path):return json.loads(Path(path).read_bytes())

def save(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')

def integer(value,minimum=0):
    require(type(value) is int and value>=minimum,'invalid_integer');return value

def timestamp(value):
    if value is None:return None
    require(isinstance(value,str),'invalid_timestamp')
    stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    require(stamp.tzinfo is not None and stamp.utcoffset() is not None,'naive_timestamp')
    return stamp.astimezone(timezone.utc)

def iso(value):return value.isoformat().replace('+00:00','Z') if value is not None else None

def mean(values):
    if not values:return None
    return float(sum(map(Fraction,values),Fraction(0))/len(values))

def distance(interval,k):
    lower,upper=interval
    integer(lower,1);integer(upper,lower);integer(k,1)
    if k<lower:return lower-k
    if k>upper:return k-upper
    return 0

def bracket(interval,times):
    lower,upper=interval
    integer(lower,1);integer(upper,lower)
    require(upper<len(times),'interval_outside_snapshot')
    a,b=times[lower-1],times[upper]
    return {'split_interval':list(interval),'possible_split_position_count':upper-lower+1,
            'record_gap_positions':upper-lower,'left_record_position':lower-1,'right_record_position':upper,
            'left_utc':iso(a),'right_utc':iso(b),'elapsed_seconds':(b-a).total_seconds() if a is not None and b is not None else None}

def windows_from_metadata(metadata):
    identifiers=[r['record_id'] for r in metadata]
    require(all(isinstance(x,str) and x for x in identifiers) and len(set(identifiers))==len(identifiers),'duplicate_or_missing_source_id')
    eligible=[]
    for position,row in enumerate(metadata):
        words=integer(row.get('retained_words',row.get('counts',{}).get('retained_words')))
        if 'style_eligible' in row:
            require(type(row['style_eligible']) is bool,'nonboolean_eligibility')
            good=row['style_eligible'] and row.get('kind','comment')=='comment'
            require(not good or words>=20,'eligible_short_record')
        else:
            require(type(row['usable']) is bool,'nonboolean_usable')
            good=(row['kind']=='comment' and row['usable'] and row['language']=='en' and row['created_utc'] is not None and words>=20)
        if good:eligible.append((position,words))
    result=[];offset=0
    while offset<len(eligible):
        stop=offset;total=0
        while stop<len(eligible) and (stop-offset<8 or total<1000):
            total+=eligible[stop][1];stop+=1
        positions=[r[0] for r in eligible[offset:stop]]
        result.append({'qualified':len(positions)>=8 and total>=1000,'first_record_position':positions[0],
          'last_record_position':positions[-1],'record_positions':positions,'record_count':len(positions),'word_count':total})
        offset=stop
    return result

def primary_from_saved(result,exit_code):
    if result is None:
        return {'status':'resource_limit' if exit_code==4 else 'unavailable',
          'reason_codes':sorted(['no_results_artifact']+(['whole_pipeline_incomplete'] if exit_code!=0 else [])),
          'native_change_status':None,'stream_id':None,'primary_window_ids':None,'intervals':[]}
    require(result['analysis']['implementation_fingerprint']==FINGERPRINT and result['analysis']['config_sha256']==CONFIG,'analysis_identity')
    style=result.get('modules',{}).get('style',{}).get('payload') or {}
    streams=[r for r in style.get('streams',[]) if (r['scope_type'],r['kind'],r['subreddit'])==('pooled','comment',None)]
    require(len(streams)<=1,'ambiguous_primary_stream')
    changes=[r for r in style.get('changes',[]) if streams and r['stream_id']==streams[0]['stream_id']]
    require(len(changes)<=1,'ambiguous_primary_change')
    change=changes[0] if changes else None
    native=change['status'] if change else None
    intervals=[]
    for boundary in change.get('boundaries',[]) if change else []:
        pair=boundary['record_interval'];require(isinstance(pair,list) and len(pair)==2,'native_interval_shape')
        a,b=pair;integer(a);integer(b,a+1);intervals.append([a+1,b])
    require(native!='no_measurable_variation' or not intervals,'constant_series_candidates')
    if exit_code!=0:status='resource_limit' if exit_code==4 else 'unavailable';reasons=['whole_pipeline_incomplete']
    elif change is None:status='abstained';reasons=['requested_scope_not_selected_or_eligible']
    elif native not in ('ok','no_measurable_variation'):status='abstained';reasons=sorted(set(change['reason_codes']+[native]))
    else:status='ok';reasons=[]
    return {'status':status,'reason_codes':reasons,'native_change_status':native,'intervals':intervals,
            'stream_id':streams[0]['stream_id'] if streams else None,'primary_window_ids':streams[0].get('window_ids') if streams else None}

def saved_window_check(metadata,directory,primary,expected):
    path=directory/'windows.jsonl'
    if not path.exists() or primary['stream_id'] is None:return 'no_saved_primary_windows'
    names=primary['primary_window_ids']
    require(isinstance(names,list) and len(names)==len(set(names)) and all(isinstance(x,str) and x for x in names),'primary_window_ids')
    chosen=[]
    with path.open() as f:
        for line in f:
            row=json.loads(line)
            if row['window_id'] in names:
                require(row['stream_id']==primary['stream_id'],'primary_window_stream')
                chosen.append(row)
    chosen.sort(key=lambda r:r['first_record_position'])
    require([r['window_id'] for r in chosen]==names,'primary_window_membership_or_order')
    require(len(chosen)==len(expected),'primary_window_count')
    for actual,want in zip(chosen,expected):
        for field in ('qualified','first_record_position','last_record_position','record_count','word_count'):
            same(actual[field],want[field],'primary_window_metadata')
        same(actual['record_ids'],[metadata[i]['record_id'] for i in want['record_positions']],'primary_window_source_membership')
    return 'all_primary_memberships_counts_positions_verified'

def expected_score(metadata,primary,truth_k,control_k):
    require((truth_k is None)!=(control_k is None),'truth_control_exclusivity')
    k=truth_k if truth_k is not None else control_k;integer(k,1);require(k<len(metadata),'truth_outside_snapshot')
    times=[timestamp(r['created_utc']) for r in metadata];observed=[t for t in times if t is not None]
    require(times==observed+[None]*(len(times)-len(observed)) and observed==sorted(observed),'noncanonical_time_order')
    windows=windows_from_metadata(metadata);qualified=[w for w in windows if w['qualified']]
    grid=[]
    if len(qualified)>=8:
        for j in range(3,len(qualified)-2):
            pair=[qualified[j-1]['last_record_position']+1,qualified[j]['first_record_position']]
            grid.append({'window_index':j,'split_interval':pair})
    closest=min(grid,key=lambda g:(distance(g['split_interval'],k),g['window_index'])) if grid else None
    best_error=distance(closest['split_interval'],k) if closest else None
    executed=primary['status'] in ('ok','no_measurable_variation')
    intervals=primary['intervals'] if executed else None
    if executed:
        require(len(qualified)>=8 and isinstance(intervals,list),'executed_without_primary_grid')
        indexes={tuple(g['split_interval']):g['window_index'] for g in grid};previous=0
        for interval in intervals:
            j=indexes.get(tuple(interval));require(j is not None and j-previous>=3,'candidate_grid_or_segmentation');previous=j
        require(primary['native_change_status']!='no_measurable_variation' or not intervals,'constant_candidates')
    nearest=min(intervals,key=lambda pair:(distance(pair,k),pair)) if intervals else None
    error=distance(nearest,k) if nearest else None
    hit=(error is not None and error<=10) if executed else None
    location={'reference_split_k':k,'matched_within_tolerance':hit,
      'exact_interval_containment':(error==0) if executed else None,'nearest_interval_error_records':error,
      'nearest_interval':bracket(nearest,times) if nearest else None,
      'excess_error_over_best_grid_records':error-best_error if error is not None and best_error is not None else None,
      'matched_candidate_count':int(hit) if executed else None,
      'unmatched_candidate_count':len(intervals)-int(hit) if executed else None}
    score={'schema_version':SCHEMA,'tolerance_records':10,'status':primary['status'],
      'reason_codes':sorted(set(primary['reason_codes'])),'executed':executed,
      'candidate_occurrence':bool(intervals) if executed else None,'candidate_count':len(intervals) if executed else None,
      'candidate_intervals':[bracket(pair,times) for pair in intervals] if executed else None,
      'truth_boundaries':[truth_k] if truth_k is not None else [],
      'switch_localization':location if truth_k is not None else None,
      'control_junction_diagnostic':location if truth_k is None else None,
      'grid_resolution':{'reference_type':'source_switch_truth' if truth_k is not None else 'control_construction_junction',
        'reference_split_k':k,'qualified_window_count':len(qualified),'minimum_qualified_windows':8,
        'minimum_segment_windows':3,'adequate_window_count':len(qualified)>=8,'legal_boundary_count':len(grid),
        'best_interval_error_records':best_error,'attainable_within_tolerance':best_error<=10 if best_error is not None else None,
        'exact_containment_attainable':best_error==0 if best_error is not None else None,
        'nearest_legal_boundary':{**closest,**bracket(closest['split_interval'],times)} if closest else None,
        'legal_boundaries':[{**g,**bracket(g['split_interval'],times)} for g in grid]},
      'temporal_resolution':{'supplied_record_count':len(metadata),'missing_timestamp_count':len(times)-len(observed),
        'first_utc':iso(observed[0]) if observed else None,'last_utc':iso(observed[-1]) if observed else None,
        'elapsed_seconds':(observed[-1]-observed[0]).total_seconds() if observed else None,
        'construction_junction':bracket([k,k],times),
        'qualified_windows':[{'window_index':j,'first_record_position':w['first_record_position'],
          'last_record_position':w['last_record_position'],'record_count':w['record_count'],'word_count':w['word_count'],
          'first_utc':iso(times[w['first_record_position']]),'last_utc':iso(times[w['last_record_position']]),
          'straddles_construction_junction':w['first_record_position']<k<=w['last_record_position']} for j,w in enumerate(qualified)]}}
    return score,windows

METRICS={'candidate_occurrence':('candidate_occurrence',),'candidate_count':('candidate_count',),
 'switch_matched_within_tolerance':('switch_localization','matched_within_tolerance'),
 'switch_exact_interval_containment':('switch_localization','exact_interval_containment'),
 'switch_nearest_interval_error_records':('switch_localization','nearest_interval_error_records'),
 'switch_excess_error_over_best_grid_records':('switch_localization','excess_error_over_best_grid_records'),
 'control_junction_matched_within_tolerance':('control_junction_diagnostic','matched_within_tolerance'),
 'control_junction_exact_interval_containment':('control_junction_diagnostic','exact_interval_containment'),
 'control_junction_nearest_interval_error_records':('control_junction_diagnostic','nearest_interval_error_records'),
 'grid_attainable_within_tolerance':('grid_resolution','attainable_within_tolerance'),
 'grid_best_interval_error_records':('grid_resolution','best_interval_error_records')}

def metric(score,path):
    value=score
    for key in path:
        if value is None:return None
        value=value[key]
    return value

def validate_factorial(cases):
    require(0<len(cases)<=48 and len(cases)%16==0,'original_case_ceiling_or_count')
    identifiers=[r['case_id'] for r in cases]
    require(len(set(identifiers))==len(identifiers),'duplicate_case')
    blocks=list(dict.fromkeys(r['block_id'] for r in cases))
    for block in blocks:
        require(isinstance(block,str) and block and '/' not in block and '\\' not in block and ':' not in block,'unsafe_block_id')
        selected=[r for r in cases if r['block_id']==block]
        require(len(selected)==16 and len({r['stratum_id'] for r in selected})==1,'incomplete_or_multistratum_block')
        seen=set()
        for row in selected:
            anchor,condition=row['anchor_id'],row['condition']
            require(anchor in ANCHORS and condition in CONDITIONS and (anchor,condition) not in seen,'factorial_descriptor')
            seen.add((anchor,condition));switch=condition.startswith('switch_');changed='_changed_' in condition
            a,c=anchor;b=({'A':'B','B':'A'}[a] if switch else a);d=({'X':'Y','Y':'X'}[c] if changed else c)
            expected={'case_id':f'{block}:{anchor}:{condition}','source_switch':switch,'community_change':changed,
                      'left_cell_id':f'{block}:{a}:{c}:early','right_cell_id':f'{block}:{b}:{d}:late'}
            for k,v in expected.items():same(row[k],v,'factorial_assignment')
    return blocks

def aggregate(rows):
    blocks=sorted(validate_factorial(rows));per_block=[]
    for block in blocks:
        for condition in CONDITIONS:
            scores=[r['score'] for r in rows if r['block_id']==block and r['condition']==condition]
            metrics={}
            for name,path in METRICS.items():
                values=[metric(s,path) for s in scores];values=[v for v in values if v is not None]
                metrics[name]={'available_cases':len(values),'planned_cases':4,'available_mean':mean(values),
                               'complete_mean':mean(values) if len(values)==4 else None}
            per_block.append({'block_id':block,'condition':condition,'planned_cases':4,
                'executed_cases':sum(s['executed'] for s in scores),'unavailable_cases':sum(not s['executed'] for s in scores),
                'status_counts':dict(sorted(Counter(s['status'] for s in scores).items())),
                'reason_code_case_counts':dict(sorted(Counter(x for s in scores for x in set(s['reason_codes'])).items())),
                'metrics':metrics})
    conditions=[]
    for condition in CONDITIONS:
        selected=[r for r in per_block if r['condition']==condition];metrics={}
        for name in METRICS:
            values=[r['metrics'][name] for r in selected]
            available=[r['available_mean'] for r in values if r['available_mean'] is not None]
            complete=[r['complete_mean'] for r in values if r['complete_mean'] is not None]
            metrics[name]={'planned_cases':4*len(blocks),'available_cases':sum(r['available_cases'] for r in values),
              'planned_blocks':len(blocks),'available_blocks':len(available),'complete_blocks':len(complete),
              'available_block_equal_mean':mean(available),'complete_block_equal_mean':mean(complete)}
        statuses=Counter();reasons=Counter()
        for row in selected:statuses.update(row['status_counts']);reasons.update(row['reason_code_case_counts'])
        conditions.append({'condition':condition,'planned_blocks':len(blocks),'planned_cases':4*len(blocks),
          'executed_cases':sum(r['executed_cases'] for r in selected),'unavailable_cases':sum(r['unavailable_cases'] for r in selected),
          'status_counts':dict(sorted(statuses.items())),'reason_code_case_counts':dict(sorted(reasons.items())),'metrics':metrics})
    return {'schema_version':SCHEMA,'analysis_type':'descriptive_only','confidence_intervals':None,
       'confidence_interval_reason':'no_registered_interval_procedure_small_related_block_design','tolerance_records':10,
       'planned_blocks':len(blocks),'planned_cases':len(rows),'per_block':per_block,'conditions':conditions}

CONTRASTS=(('switch_occurrence_same_community',1,0,None),('switch_occurrence_changed_community',3,2,None),
 ('community_change_occurrence_continuity',2,0,None),('community_change_occurrence_switch',3,1,None),
 ('community_change_switch_localization',3,1,'switch_localization'),
 ('community_change_control_junction_alignment',2,0,'control_junction_diagnostic'))

def contrasts(rows):
    blocks=sorted(validate_factorial(rows));lookup={(r['block_id'],r['anchor_id'],r['condition']):r['score'] for r in rows}
    output=[]
    for name,left,right,field in CONTRASTS:
        block_rows=[]
        for block in blocks:
            anchors=[]
            for anchor in ANCHORS:
                values=[metric(lookup[block,anchor,CONDITIONS[i]],(field,'matched_within_tolerance') if field else ('candidate_occurrence',)) for i in (left,right)]
                delta=None if None in values else int(values[0])-int(values[1])
                anchors.append({'anchor_id':anchor,'left_value':values[0],'right_value':values[1],'difference':delta})
            valid=[r['difference'] for r in anchors if r['difference'] is not None]
            block_rows.append({'block_id':block,'anchors':anchors,'common_available_anchors':len(valid),
                               'available_anchor_mean':mean(valid),'complete_block_mean':mean(valid) if len(valid)==4 else None})
        output.append({'contrast':name,'direction':CONDITIONS[left]+' minus '+CONDITIONS[right],
          'planned_blocks':len(blocks),'planned_anchors':4*len(blocks),
          'common_available_anchors':sum(r['common_available_anchors'] for r in block_rows),
          'complete_blocks':sum(r['complete_block_mean'] is not None for r in block_rows),
          'complete_block_equal_mean':mean([r['complete_block_mean'] for r in block_rows if r['complete_block_mean'] is not None]),
          'available_block_equal_mean':mean([r['available_anchor_mean'] for r in block_rows if r['available_anchor_mean'] is not None]),'blocks':block_rows})
    interaction=[]
    for block in blocks:
        anchors=[]
        for anchor in ANCHORS:
            values=[lookup[block,anchor,c]['candidate_occurrence'] for c in CONDITIONS]
            delta=None if None in values else int(values[3])-int(values[2])-int(values[1])+int(values[0])
            anchors.append({'anchor_id':anchor,'difference_in_differences':delta})
        valid=[r['difference_in_differences'] for r in anchors if r['difference_in_differences'] is not None]
        interaction.append({'block_id':block,'anchors':anchors,'common_available_anchors':len(valid),
                            'complete_block_mean':mean(valid) if len(valid)==4 else None,'available_anchor_mean':mean(valid)})
    return {'interpretation':'Descriptive paired changes on common observed outcomes; source-account proxies and sampled histories, not causal effects.',
      'contrasts':output,'occurrence_interaction':{'direction':'(switch minus continuity) with community change minus without community change',
      'blocks':interaction,'planned_anchors':4*len(blocks),'common_available_anchors':sum(r['common_available_anchors'] for r in interaction),
      'complete_blocks':sum(r['complete_block_mean'] is not None for r in interaction),
      'complete_block_equal_mean':mean([r['complete_block_mean'] for r in interaction if r['complete_block_mean'] is not None])}}

def inventory(directory):
    if not directory.is_dir():return []
    output=[]
    for p in sorted(directory.iterdir()):
        require(not p.is_symlink(),'symlink_artifact')
        if p.is_file():output.append({'name':p.name,'bytes':p.stat().st_size,'sha256':sha(p),'canonical':p.name not in OPERATIONAL})
    return output

def checked_execution(root,index_path,registration_path,identifiers,replay):
    binding=read(root/'start-binding.json');execution=read(root/'execution.json')
    registration=read(registration_path)
    same(binding['case_ids'],identifiers,'execution_start_membership')
    same([r['case_id'] for r in execution['cases']],identifiers,'execution_complete_membership')
    require(binding['replay'] is replay and execution['replay'] is replay,'execution_replay_flag')
    require(binding['index_sha256']==sha(index_path) and binding['registration_sha256']==sha(registration_path), 'execution_input_binding')
    require(binding['runner_sha256']==registration['runner_sha256'],'execution_runner_binding')
    cases={};canonical={}
    for attempt in execution['cases']:
        case_id=attempt['case_id'];receipt=attempt.get('receipt');directory=root/case_id
        artifacts=inventory(directory/'analysis')
        if receipt is not None:
            require(attempt['status']=='attempted' and receipt['case_id']==case_id,'attempt_receipt_identity')
            same(read(directory/'receipt.json'),receipt,'saved_receipt_changed')
            same(artifacts,receipt['artifacts'],'saved_artifact_changed')
        else:require(attempt['status']!='attempted','attempt_without_receipt')
        canonical[case_id]={r['name']:{'bytes':r['bytes'],'sha256':r['sha256']} for r in artifacts if r['canonical']}
        cases[case_id]=attempt
    return cases,binding,canonical

def check_csv(path,rows):
    with path.open(newline='') as f:reader=csv.DictReader(f);actual=list(reader);fields=reader.fieldnames
    require(len(actual)==len(rows),'csv_case_count')
    for published,row in zip(actual,rows):
        expected={k:row[k] for k in fields if k in row}
        for k in ('executed','candidate_count','candidate_occurrence'):expected[k]=row['score'][k]
        for prefix,field in [('switch','switch_localization'),('control_junction','control_junction_diagnostic')]:
            value=row['score'][field]
            expected[prefix+'_matched_within_10']=value['matched_within_tolerance'] if value else None
            expected[prefix+'_nearest_error_records']=value['nearest_interval_error_records'] if value else None
        same(published,{k:'' if expected[k] is None else str(expected[k]) for k in fields},'csv_value')

def verify(index_path,run_root,scores_root,registration_path,protocol_path,replay_root=None,replay_report=None):
    index_path=Path(index_path);run_root=Path(run_root);scores_root=Path(scores_root)
    registration_path=Path(registration_path);protocol_path=Path(protocol_path)
    index=read(index_path);registration=read(registration_path);cases=index['cases'];blocks=validate_factorial(cases)
    require(registration['phase']=='frozen_before_chronological_execution' and registration['prepared_index_sha256']==sha(index_path),'scoring_registration')
    artifact_refs=registration['bound_artifacts'];paths=[str(Path(r['path']).resolve()) for r in artifact_refs]
    require(len(paths)==len(set(paths)),'duplicate_scoring_binding')
    require(str(Path(__file__).resolve()) in paths and str(protocol_path.resolve()) in paths,'checker_and_protocol_not_registered')
    for ref in artifact_refs:require(sha(ref['path'])==ref['sha256'],'registered_artifact_changed')
    refs=index['bound_files'];bound={str(Path(r['path']).resolve()):r['sha256'] for r in refs}
    require(len(bound)==len(refs),'duplicate_prepared_binding')
    for case in cases:
        for field in ('input','manifest','metadata'):require(str(Path(case[field]).resolve()) in bound,'unbound_prepared_file')
    for path,digest in bound.items():require(sha(path)==digest,'prepared_file_changed')
    identifiers=[r['case_id'] for r in cases]
    attempts,binding,canonical=checked_execution(run_root,index_path,registration_path,identifiers,False)
    require(registration['replay_block_id']==blocks[0],'registered_replay_not_first_block')
    published=read(scores_root/'cases.json');same([r['case_id'] for r in published],identifiers,'published_case_membership')
    rows=[];metadata_occurrences=0;qualified_windows=0;candidate_count=0;unavailable=0
    descriptor_fields=('case_id','block_id','stratum_id','anchor_id','condition','source_switch','community_change','left_cell_id','right_cell_id')
    for case,actual in zip(cases,published):
        for field in descriptor_fields:same(actual[field],case[field],'published_descriptor')
        require(case['source_switch'] is (case['truth_k'] is not None) and (case['truth_k'] is None)!=(case['control_junction_k'] is None),'case_truth_assignment')
        attempt=attempts[case['case_id']];receipt=attempt.get('receipt');exit_code=receipt['exit_code'] if receipt else None
        directory=run_root/case['case_id']/'analysis';result_path=directory/'results.json'
        try:result=read(result_path) if result_path.exists() else None
        except json.JSONDecodeError:
            require(exit_code!=0,'successful_invalid_results');result=None
        primary=primary_from_saved(result,exit_code)
        metadata=read(case['metadata'])['records'];require(len(metadata)<=400,'case_metadata_record_cap')
        expected,windows=expected_score(metadata,primary,case['truth_k'],case['control_junction_k'])
        try:validation=saved_window_check(metadata,directory,primary,windows)
        except (ValueError,KeyError,json.JSONDecodeError):
            require(not expected['executed'],'executed_primary_windows_invalid');validation='unavailable_partial_windows_unverified'
        require(not expected['executed'] or validation=='all_primary_memberships_counts_positions_verified','executed_without_saved_windows')
        same(actual['score'],expected,'case_score_arithmetic')
        same(actual['primary_window_check'],validation,'window_validation_status')
        same(actual['native_change_status'],primary['native_change_status'],'native_status')
        same(actual['record_count'],len(metadata),'supplied_record_count')
        same(actual['retained_words'],sum(r['retained_words'] for r in metadata),'retained_word_sum')
        same(actual['results_sha256'],sha(result_path) if result_path.exists() else None,'saved_results_hash')
        same(actual['artifact_bytes'],sum(r['bytes'] for r in receipt['artifacts']) if receipt else 0,'artifact_byte_sum')
        resources={k:receipt[k] for k in ('exit_code','wall_seconds','child_peak_rss_mib','external_wall_limit_reached')} if receipt else None
        same(actual['resources'],resources,'resource_projection')
        statuses={k:{'status':v['status'],'reason_codes':v['reason_codes']} for k,v in result['modules'].items()} if result else None
        same(actual['full_pipeline_statuses'],statuses,'full_pipeline_statuses')
        rows.append({**{k:case[k] for k in descriptor_fields},'score':expected})
        metadata_occurrences+=len(metadata);qualified_windows+=expected['grid_resolution']['qualified_window_count']
        candidate_count+=expected['candidate_count'] or 0;unavailable+=not expected['executed']
    summary=read(scores_root/'summary.json')
    expected_summary={'all_strata':aggregate(rows),
       'by_stratum':{s:aggregate([r for r in rows if r['stratum_id']==s]) for s in sorted({r['stratum_id'] for r in rows})},
       'matched_changes_all_strata':contrasts(rows),
       'matched_changes_by_stratum':{s:contrasts([r for r in rows if r['stratum_id']==s]) for s in sorted({r['stratum_id'] for r in rows})},
       'input_index_sha256':sha(index_path),'execution_manifest_sha256':sha(run_root/'execution.json')}
    same(summary,expected_summary,'aggregate_or_matched_arithmetic')
    check_csv(scores_root/'cases.csv',published)
    replay_cases=0;replay_files=0
    require((replay_root is None)==(replay_report is None),'replay_arguments_together')
    if replay_root is not None:
        replay_root=Path(replay_root);replay_report=Path(replay_report)
        selected=[r for r in cases if r['block_id']==blocks[0]];replay_ids=[r['case_id'] for r in selected]
        require(len(replay_ids)==16,'replay_case_count')
        _,replay_binding,replay_inventory=checked_execution(replay_root,index_path,registration_path,replay_ids,True)
        for field in ('index_sha256','registration_sha256','runner_sha256'):same(replay_binding[field],binding[field],'replay_binding')
        comparison=[]
        for case in selected:
            identifier=case['case_id'];a,b=canonical[identifier],replay_inventory[identifier]
            equal=bool(a) and a==b
            comparison.append({'case_id':identifier,'canonical_file_count':len(a),'all_files_byte_identical':equal,
               'differing_files':sorted(k for k in set(a)|set(b) if a.get(k)!=b.get(k))})
            for field in ('input','manifest'):
                relocated=replay_root/'relocated'/(identifier+'.'+field+Path(case[field]).suffix)
                require(relocated.resolve()!=Path(case[field]).resolve() and sha(relocated)==sha(case[field]),'replay_relocated_input_changed')
            replay_files+=len(a)
        expected_replay={'cases':comparison,'all_passed':all(r['all_files_byte_identical'] for r in comparison),
                         'excluded_operational_files':['ingest_receipt.json','run_receipt.json']}
        same(read(replay_report),expected_replay,'replay_report')
        require(expected_replay['all_passed'],'replay_canonical_difference');replay_cases=16
    output={'status':'passed','original_cases_verified':len(cases),'independent_blocks':len(blocks),
      'represented_strata':len({r['stratum_id'] for r in cases}),'condition_case_totals':{c:sum(r['condition']==c for r in cases) for c in CONDITIONS},
      'executed_cases':len(cases)-unavailable,'unavailable_cases':unavailable,'primary_candidate_count':candidate_count,
      'metadata_record_occurrences_verified':metadata_occurrences,'qualified_window_occurrences_verified':qualified_windows,
      'record_occurrences_are_repeated_inputs_not_independent_records':True,
      'all_case_grid_localization_and_availability_fields_verified':True,
      'all_condition_block_equal_means_and_matched_changes_verified':True,
      'replay_cases_verified':replay_cases,'replay_canonical_file_occurrences_verified':replay_files,
      'replay_scope':'Not requested in this check' if replay_root is None else 'Complete first registered block; exact two operational exclusions; relocated inputs verified',
      'input_hashes':{'prepared_index':sha(index_path),'registration':sha(registration_path),'protocol':sha(protocol_path),
        'main_execution':sha(run_root/'execution.json'),'main_start_binding':sha(run_root/'start-binding.json')},
      'score_hashes':{name:sha(scores_root/name) for name in ('cases.json','summary.json','cases.csv')},
      'checker_sha256':sha(Path(__file__)),'source_prose_displayed':False,'private_source_identifiers_published':False,
      'new_preprocessing_calls':0,'new_style_calls':0,'arithmetic_basis':'Independent Python stdlib reconstruction from bound metadata and saved primary outputs; no analyzer or scorer imports.'}
    if replay_root is not None:output['replay_hashes']={'execution':sha(replay_root/'execution.json'),'start_binding':sha(replay_root/'start-binding.json'),'report':sha(replay_report)}
    return output

def main():
    p=argparse.ArgumentParser()
    for name in ('index','run','scores','registration','protocol','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--replay',type=Path);p.add_argument('--replay-report',type=Path)
    args=p.parse_args();require(not args.out.exists(),'output_already_exists')
    started=time.monotonic();utc=datetime.now(timezone.utc).isoformat()
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    def alarm(*_):raise TimeoutError('checker_wall_budget')
    signal.signal(signal.SIGALRM,alarm);signal.alarm(1800)
    try:
        result=verify(args.index,args.run,args.scores,args.registration,args.protocol,args.replay,args.replay_report);exit_code=0
    except Exception as error:
        code=str(error) if isinstance(error,ValueError) and str(error).replace('_','').isalpha() else None
        result={'status':'failed','error_type':type(error).__name__,'check_code':code,'checker_sha256':sha(Path(__file__))};exit_code=1
    finally:signal.alarm(0)
    result.update(started_utc=utc,finished_utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.monotonic()-started,
                  peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    save(args.out,result);print(json.dumps({'status':result['status'],'original_cases_verified':result.get('original_cases_verified',0)}),flush=True)
    return exit_code

if __name__=='__main__':raise SystemExit(main())
