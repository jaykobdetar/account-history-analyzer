"""Independent metadata-only shared-anchor construction oracle.

Uses only saved audited-survivor metadata. No analyzer, source text, previous
study arithmetic, or candidate-output module is imported. Actual-file checking
is added only against the separately frozen Pilot5 schema.
"""
from datetime import datetime,timezone
from fractions import Fraction
from itertools import combinations,permutations
import hashlib

DAY=86400
SAMPLES=('anchor','late_AX','late_BX','late_AY','late_BY')
LATE=SAMPLES[1:]


def require(condition,code):
    if not condition:raise ValueError(code)

def seconds(value):
    t=datetime.fromisoformat(value.replace('Z','+00:00'))
    require(t.utcoffset() is not None and t.utcoffset().total_seconds()==0 and t.microsecond==0,'integer_utc_required')
    return int(t.timestamp())

def account_hash(account):
    require(isinstance(account,str) and account and account==account.casefold(),'canonical_source_account_required')
    return hashlib.sha256(('pilot5-anchor-order-v1\0'+account).encode('utf-8')).hexdigest()

def select_prefix(records,cut,period):
    require(period in ('early','late'),'unknown_period')
    low,high=(cut-180*DAY,cut) if period=='early' else (cut,cut+180*DAY)
    data=[]
    for row in records:
        stamp=row['timestamp'] if 'timestamp' in row else seconds(row['created_utc'])
        require(type(stamp) is int and type(row['retained_words']) is int,'noninteger_record_metadata')
        if low<=stamp<high and 20<=row['retained_words']<=500:
            data.append((stamp,row['record_id'],row['retained_words']))
    require(len({r[1] for r in data})==len(data),'duplicate_record_id')
    data.sort(key=lambda row:(abs(cut-row[0]),row[0],row[1]))
    words=0
    for stop,row in enumerate(data,1):
        words+=row[2]
        if words>5500 or stop>200:return None
        if words>=5000 and stop>=40:
            selected=sorted(data[:stop]);median=Fraction(selected[(stop-1)//2][0]+selected[stop//2][0],2)
            return {'records':stop,'retained_words':words,'median_timestamp':median,
                    'rows':[{'timestamp':t,'record_id':rid,'retained_words':w} for t,rid,w in selected]}
    return None

def window_counts(rows):
    """All supplied rows here are previously audited eligible whole comments."""
    order=[(r['timestamp'],r['record_id']) for r in rows]
    require(order==sorted(order) and len({r['record_id'] for r in rows})==len(rows),'noncanonical_or_repeated_history')
    qualified=0;words=0;records=0
    for row in rows:
        require(type(row['retained_words']) is int and 20<=row['retained_words']<=500,'invalid_whole_record_words')
        words+=row['retained_words'];records+=1
        if words>=1000 and records>=8:qualified+=1;words=0;records=0
    return {'qualified_windows':qualified,'remainder_records':records,'remainder_words':words}

def evaluate_samples(samples):
    require(set(samples)==set(SAMPLES),'five_sample_keys_required')
    missing=[name for name in SAMPLES if samples[name] is None]
    if missing:return {'valid':False,'failed_gates':['sample_prefix_unavailable'],
                       'unavailable_samples':missing,'exact_cost':None,'word_ratio':None,
                       'record_ratio':None,'late_median_span_days':None,'histories':None}
    words=[samples[k]['retained_words'] for k in SAMPLES];counts=[samples[k]['records'] for k in SAMPLES]
    require(min(words)>0 and min(counts)>0,'empty_sample')
    wr=Fraction(max(words),min(words));rr=Fraction(max(counts),min(counts))
    medians=[samples[k]['median_timestamp'] for k in LATE];span=(max(medians)-min(medians))/DAY
    histories={name:window_counts(sorted(samples['anchor']['rows']+samples[name]['rows'],key=lambda r:(r['timestamp'],r['record_id']))) for name in LATE}
    failures=[]
    if wr>Fraction(11,10):failures.append('five_sample_word_ratio_above_11_over_10')
    if rr>Fraction(5,4):failures.append('five_sample_record_ratio_above_5_over_4')
    if span>30:failures.append('four_late_median_span_above_30_days')
    if any(h['qualified_windows']<8 for h in histories.values()):failures.append('one_or_more_histories_below_eight_primary_windows')
    cost=sum((abs(a-b)/Fraction(180*DAY) for a,b in combinations(medians,2)),Fraction(0))
    cost+=sum((Fraction(abs(a-b),5000) for a,b in combinations(words,2)),Fraction(0))
    cost+=sum((Fraction(abs(a-b),40) for a,b in combinations(counts,2)),Fraction(0))
    return {'valid':not failures,'failed_gates':failures,'unavailable_samples':[],
            'exact_cost':cost,'word_ratio':wr,'record_ratio':rr,'late_median_span_days':span,'histories':histories}

def trial_key(trial):
    require(trial['evaluation']['valid'],'invalid_trial_cannot_rank')
    return (trial['evaluation']['exact_cost'],trial['stratum_id'],account_hash(trial['A']),account_hash(trial['B']),trial['X'],trial['Y'])

def enumerate_trials(strata,records_by_cell):
    """Use each frozen stratum/cut and every ordered distinct account/community choice."""
    trials=[]
    for spec in sorted(strata,key=lambda r:r['stratum_id']):
        sid=spec['stratum_id'];cut=seconds(spec['cut']);accounts=sorted(spec['accounts'],key=account_hash)
        require(len(set(accounts))==len(accounts) and len(spec['communities'])==2 and len(set(spec['communities']))==2,'invalid_registered_stratum')
        cache={}
        for account in accounts:
            for community in spec['communities']:
                for period in ('early','late'):
                    cache[account,community,period]=select_prefix(records_by_cell.get((sid,account,community,period),[]),cut,period)
        for a,b in permutations(accounts,2):
            for x,y in permutations(sorted(spec['communities']),2):
                samples={'anchor':cache[a,x,'early'],'late_AX':cache[a,x,'late'],'late_BX':cache[b,x,'late'],
                         'late_AY':cache[a,y,'late'],'late_BY':cache[b,y,'late']}
                trials.append({'stratum_id':sid,'cut':spec['cut'],'A':a,'B':b,'X':x,'Y':y,
                               'samples':samples,'evaluation':evaluate_samples(samples)})
    valid=[r for r in trials if r['evaluation']['valid']]
    selected=min(valid,key=trial_key) if valid else None
    return trials,selected

# Saved-file adapter. None of the paths below open source writing; the pool is
# verified by byte hash and the separately bound preparation metadata receipt.
import argparse
from collections import defaultdict
import json
from pathlib import Path
import resource
import signal
import time


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def read(path):return json.loads(Path(path).read_bytes())

def encoded(value):
    if isinstance(value,Fraction):return {'numerator':value.numerator,'denominator':value.denominator}
    if isinstance(value,dict):return {k:encoded(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [encoded(v) for v in value]
    return value

def same(actual,expected,code):
    require(type(actual) is type(expected),code)
    if isinstance(expected,dict):
        require(set(actual)==set(expected),code)
        for k in expected:same(actual[k],expected[k],code)
    elif isinstance(expected,list):
        require(len(actual)==len(expected),code)
        for a,b in zip(actual,expected):same(a,b,code)
    else:require(actual==expected,code)

def producer_projection(trial,number):
    e=trial['evaluation']
    row={'candidate_id':f'candidate-{number:02d}','stratum_id':trial['stratum_id'],'cut':trial['cut'],
         'account_a':trial['A'],'account_b':trial['B'],'community_x':trial['X'],'community_y':trial['Y'],
         'valid':e['valid'],'cost':e['exact_cost']}
    if e['unavailable_samples']:
        row.update(reason_codes=['unavailable_sample:'+k for k in e['unavailable_samples']],qualified_window_counts=None)
    else:
        row.update(reason_codes=['fewer_than_eight_qualified_windows' if k=='one_or_more_histories_below_eight_primary_windows' else k for k in e['failed_gates']],
          qualified_window_counts=[e['histories'][k]['qualified_windows'] for k in LATE],
          late_median_span_days=e['late_median_span_days'],five_sample_word_ratio=e['word_ratio'],five_sample_record_ratio=e['record_ratio'])
    return encoded(row)

def sample_statistics(key,value):
    lengths=sorted(r['retained_words'] for r in value['rows']);quantiles={}
    for p in (0,.25,.5,.75,1):
        at=(len(lengths)-1)*p;i=int(at)
        quantiles[str(p)]=lengths[i]+(lengths[min(i+1,len(lengths)-1)]-lengths[i])*(at-i)
    return {'sample_key':key,'records':value['records'],'retained_words':value['retained_words'],
       'word_target_overshoot':value['retained_words']-5000,'longest_record_word_share':max(lengths)/sum(lengths),
       'word_length_quantiles':quantiles,'median_timestamp':encoded(value['median_timestamp']),
       'first_timestamp':value['rows'][0]['timestamp'],'last_timestamp':value['rows'][-1]['timestamp']}

def verify(plan_path,prepared,public):
    plan_path=Path(plan_path);prepared=Path(prepared);public=Path(public)
    plan=read(plan_path)
    require(plan['phase']=='frozen_before_five_sample_enumeration','wrong_registered_phase')
    refs=plan['bindings'];bound={str(Path(r['path']).resolve()):r['sha256'] for r in refs}
    require(len(bound)==len(refs),'duplicate_registered_binding')
    for key in ('pool','audit','preparation_plan','original_prefix_rules','source_selection_metadata','source_preparation_receipt'):
        require(str(Path(plan[key]).resolve()) in bound,'unbound_source_dependency')
    for path,digest in bound.items():require(sha(path)==digest,'registered_source_or_code_changed')
    old=read(plan['preparation_plan']);selection=read(plan['source_selection_metadata']);preparation=read(plan['source_preparation_receipt']);audit=read(plan['audit'])
    require(preparation['selection_sha256']==sha(plan['source_selection_metadata']) and preparation['candidate_pool_sha256']==sha(plan['pool']), 'source_metadata_pool_binding')
    require(preparation['plan_sha256']==sha(plan['preparation_plan']),'source_preparation_plan_binding')
    require(audit['summary']['gate_b_ready'] is True and audit['summary']['available_content_and_grouping_audit_complete'] is True and audit['engine_audit']['status']=='audited','audit_gate_unavailable')
    metadata=selection['selected_metadata'];survivors=audit['surviving_candidate_ids'];purges=audit['purge_record_ids']
    require(len(metadata)==2447 and len(survivors)==2252 and len(set(survivors))==2252 and len(set(purges))==195 and len(purges)==195,'frozen_pool_counts')
    require(not set(survivors)&set(purges) and set(survivors)|set(purges)==set(metadata),'survivor_partition')
    design=read(plan['original_prefix_rules'])
    fixed={'half_band_days':180,'record_word_min':20,'record_word_max':500,'half_target_words':5000,
           'half_min_records':40,'half_max_words':5500,'half_max_records':200}
    require(all(design[k]==v for k,v in fixed.items()),'original_prefix_rule_changed')
    require([s['stratum_id'] for s in old['strata']]==['stratum-02','stratum-04','stratum-05'] and [len(s['accounts']) for s in old['strata']]==[2,3,2],'frozen_account_allocation')
    assignments={a:s for s in old['strata'] for a in s['accounts']};require(len(assignments)==7,'cross_stratum_account_reuse')
    records=defaultdict(list)
    for rid in survivors:
        r=metadata[rid];require(r['record_id']==rid and r['reason'] is None and type(r['retained_words']) is int and 20<=r['retained_words']<=500,'survivor_metadata')
        spec=assignments.get(r['account_key']);require(spec is not None and r['stratum_id']==spec['stratum_id'] and r['community'] in spec['communities'] and r['period'] in ('early','late'),'survivor_assignment')
        cut=seconds(spec['cut']);t=seconds(r['created_utc']);lo,hi=(cut-180*DAY,cut) if r['period']=='early' else (cut,cut+180*DAY)
        require(lo<=t<hi,'survivor_outside_frozen_band')
        records[r['stratum_id'],r['account_key'],r['community'],r['period']].append({'record_id':rid,'timestamp':t,'retained_words':r['retained_words']})
    trials,winner=enumerate_trials(old['strata'],records);require(len(trials)==20,'directional_trial_count')
    projected=[producer_projection(t,i+1) for i,t in enumerate(trials)]
    winner_index=next((i for i,t in enumerate(trials) if t is winner),None)
    expected_winner=projected[winner_index] if winner is not None else None
    private=read(prepared/'selection.json');same(private['candidates'],projected,'all_twenty_candidate_arithmetic')
    same(private['selected'],expected_winner,'minimum_exact_cost_and_tie_winner')
    public_expected={'candidates':[{k:v for k,v in r.items() if k not in ('account_a','account_b')} for r in projected],
      'valid_candidates':sum(t['evaluation']['valid'] for t in trials),'selected_candidate_id':expected_winner['candidate_id'] if winner else None,
      'selection_uses_style_results':False,'registration_sha256':sha(plan_path)}
    same(read(public/'candidate-enumeration.json'),public_expected,'public_candidate_projection')
    result={'status':'passed','candidate_directions_verified':20,'valid_directions':public_expected['valid_candidates'],
      'selected_candidate_id':public_expected['selected_candidate_id'],'source_survivors_verified':2252,
      'exact_prefix_cost_gate_and_tie_checks_passed':True,'independent_primary_window_guard_verified':True,
      'source_prose_read':False,'original_source_identifiers_published':False,'new_preprocessing_calls':0,'new_style_calls':0,
      'checker_sha256':sha(Path(__file__)),'input_hashes':{'plan':sha(plan_path),'audit':sha(plan['audit']),
       'source_selection_metadata':sha(plan['source_selection_metadata']),'source_preparation_receipt':sha(plan['source_preparation_receipt'])},
      'output_hashes':{'selection':sha(prepared/'selection.json'),'candidate_enumeration':sha(public/'candidate-enumeration.json')}}
    if winner is None:
        require(not (prepared/'index.json').exists(),'unavailable_selection_has_prepared_index')
        result.update(selected_samples=0,prepared_histories=0);return result
    require(private['plan_sha256']==sha(plan_path) and private['audit_sha256']==sha(plan['audit']),'selected_source_hashes')
    ids={k:[r['record_id'] for r in winner['samples'][k]['rows']] for k in SAMPLES}
    same(private['source_samples'],ids,'five_exact_whole_record_samples')
    flat=[rid for rows in ids.values() for rid in rows];require(len(flat)==len(set(flat)) and set(flat)<=set(survivors),'five_samples_not_disjoint_survivors')
    same(read(public/'samples.json'),[sample_statistics(k,winner['samples'][k]) for k in SAMPLES],'public_sample_statistics')
    index=read(prepared/'index.json');require(len(index['cases'])==4 and index['prepared_block_count']==1,'four_histories_one_unit')
    file_refs=index['bound_files'];require(len({r['path'] for r in file_refs})==len(file_refs),'duplicate_prepared_binding')
    for row in file_refs:require(sha(row['path'])==row['sha256'],'prepared_file_hash')
    conditions=('continuity_same_community','switch_same_community','continuity_changed_community','switch_changed_community')
    for case,condition,key in zip(index['cases'],conditions,LATE):
        require(case['condition']==condition and case['anchor_id']=='AX' and case['stratum_id']==winner['stratum_id'],'case_direction')
        k=len(ids['anchor']);require(case['truth_k']==(k if condition.startswith('switch_') else None) and case['control_junction_k']==(None if condition.startswith('switch_') else k),'case_truth_or_junction')
        expected_ids=ids['anchor']+ids[key];actual_meta=read(case['metadata'])['records']
        expected_meta=[{'record_id':rid,'created_utc':metadata[rid]['created_utc'],'retained_words':metadata[rid]['retained_words'],'kind':'comment','style_eligible':True} for rid in expected_ids]
        same(actual_meta,expected_meta,'constructed_history_metadata')
        require(case['prescore_qualified_windows']==winner['evaluation']['histories'][key]['qualified_windows'],'saved_window_adequacy')
    summary=read(public/'selection-summary.json')
    expected_summary={'selected_candidate_id':expected_winner['candidate_id'],'stratum_id':winner['stratum_id'],
      'community_x':winner['X'],'community_y':winner['Y'],'cut':winner['cut'],'source_samples':5,'source_accounts':2,
      'independent_diagnostic_units':1,'histories':4,'unique_records':len(flat),
      'unique_retained_words':sum(metadata[r]['retained_words'] for r in flat),'shared_anchor_records':len(ids['anchor']),
      'qualified_windows_per_history':[winner['evaluation']['histories'][k]['qualified_windows'] for k in LATE],
      'metadata_cost':encoded(winner['evaluation']['exact_cost']),'index_sha256':sha(prepared/'index.json'),
      'selection_sha256':sha(prepared/'selection.json'),'style_calls':0,'new_preprocessor_calls':0,
      'audit_reuse':'Subset of2252survivors; prior conservative cross-cell and historical purges retained.'}
    same(summary,expected_summary,'public_selection_summary')
    result.update(selected_samples=5,prepared_histories=4,independent_diagnostic_units=1,unique_selected_records=len(flat),
      unique_selected_retained_words=expected_summary['unique_retained_words'],shared_anchor_records=len(ids['anchor']),
      qualified_windows_per_history=expected_summary['qualified_windows_per_history'])
    result['output_hashes'].update(index=sha(prepared/'index.json'),samples=sha(public/'samples.json'),summary=sha(public/'selection-summary.json'))
    return result

def main():
    p=argparse.ArgumentParser()
    for k in ('plan','prepared','public','out'):p.add_argument('--'+k,type=Path,required=True)
    args=p.parse_args();started=time.monotonic();require(not args.out.exists(),'existing_check_output')
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2)
    def stop(*_):raise TimeoutError('independent_check_wall_budget')
    signal.signal(signal.SIGALRM,stop);signal.alarm(1800)
    try:result=verify(args.plan,args.prepared,args.public);exit_code=0
    except Exception as e:
        code=str(e) if isinstance(e,ValueError) and str(e).replace('_','').isalnum() else None
        result={'status':'failed','error_type':type(e).__name__,'check_code':code,'checker_sha256':sha(Path(__file__))};exit_code=1
    finally:signal.alarm(0)
    result.update(wall_seconds=time.monotonic()-started,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                  recorded_utc=datetime.now(timezone.utc).isoformat())
    with args.out.open('x') as f:json.dump(result,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps({k:result[k] for k in ('status','candidate_directions_verified') if k in result}),flush=True)
    return exit_code

if __name__=='__main__':raise SystemExit(main())
