"""Post-outcome metadata-only diagnosis of fixed-pool edge losses.

This reporting helper independently reconstructs the prescribed prefixes and
exact gates. It never reads source writing, imports a scorer or changes cells.
"""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from fractions import Fraction
from itertools import combinations
import argparse
import hashlib
import json
from pathlib import Path
import resource
import time

DAY=86400

def require(value,code):
    if not value:raise ValueError(code)

def read(path):return json.loads(Path(path).read_bytes())

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def stamp(value):
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    require(d.utcoffset() is not None and d.utcoffset().total_seconds()==0 and d.microsecond==0,'invalid_utc')
    return int(d.timestamp())

def rational(value):return {'numerator':value.numerator,'denominator':value.denominator}

def encode(value):
    if isinstance(value,Fraction):return rational(value)
    if isinstance(value,dict):return {k:encode(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [encode(v) for v in value]
    return value

def prefix(rows,cut,period):
    lo,hi=(cut-180*DAY,cut) if period=='early' else (cut,cut+180*DAY)
    candidates=[r for r in rows if lo<=r['timestamp']<hi and 20<=r['retained_words']<=500]
    candidates.sort(key=lambda r:(abs(r['timestamp']-cut),r['timestamp'],r['record_id']))
    words=0;kept=[];reason='insufficient_remaining_volume'
    for row in candidates:
        kept.append(row);words+=row['retained_words']
        if words>5500:reason='whole_prefix_exceeds_5500_words_before_both_targets';break
        if len(kept)>200:reason='whole_prefix_exceeds_200_records_before_both_targets';break
        if words>=5000 and len(kept)>=40:
            ordered=sorted(r['timestamp'] for r in kept);n=len(ordered)
            return {'available':True,'records':n,'words':words,'median_timestamp':Fraction(ordered[(n-1)//2]+ordered[n//2],2),'reason':None}
    return {'available':False,'records':None,'words':None,'median_timestamp':None,'reason':reason,
      'remaining_records':len(candidates),'remaining_words':sum(r['retained_words'] for r in candidates),
      'stopped_prefix_records':len(kept),'stopped_prefix_words':words}

def gates(accounts):
    missing=[f'{i+1}/{k}' for i,cells in enumerate(accounts) for k,c in cells.items() if not c['available']]
    if missing:return {'compatible':False,'unavailable_cell_count':len(missing),'failed_gates':['cell_prefix_unavailable'],
                       'record_ratio':None,'word_ratio':None,'early_median_span_days':None,'late_median_span_days':None}
    cells=[c for account in accounts for c in account.values()]
    words=Fraction(max(c['words'] for c in cells),min(c['words'] for c in cells))
    records=Fraction(max(c['records'] for c in cells),min(c['records'] for c in cells))
    spans={p:(max(a[c+'/'+p]['median_timestamp'] for a in accounts for c in 'XY')-
              min(a[c+'/'+p]['median_timestamp'] for a in accounts for c in 'XY'))/DAY for p in ('early','late')}
    failures=[]
    if words>Fraction(11,10):failures.append('word_ratio_above_11_over_10')
    if records>Fraction(5,4):failures.append('record_ratio_above_5_over_4')
    for p in ('early','late'):
        if spans[p]>30:failures.append(p+'_median_span_above_30_days')
    return {'compatible':not failures,'unavailable_cell_count':0,'failed_gates':failures,'record_ratio':records,'word_ratio':words,
            'early_median_span_days':spans['early'],'late_median_span_days':spans['late']}

def maximum_matching(nodes,edges):
    if not nodes:return 0
    first,*rest=nodes;answer=maximum_matching(rest,edges)
    for other in rest:
        if frozenset((first,other)) in edges:answer=max(answer,1+maximum_matching([x for x in rest if x!=other],edges))
    return answer

def diagnose(plan_path,selection_path,preparation_path,audit_path,final_summary_path):
    plan=read(plan_path);selection=read(selection_path);preparation=read(preparation_path);audit=read(audit_path);final=read(final_summary_path)
    require(preparation['selection_sha256']==sha(selection_path) and preparation['plan_sha256']==sha(plan_path),'selection_plan_binding')
    require(final['candidate_pool_sha256']==preparation['candidate_pool_sha256'] and final['audit_sha256']==sha(audit_path),'audit_pool_binding')
    metadata=selection['selected_metadata'];require(len(metadata)==preparation['records'],'metadata_pool_count')
    purged=set(audit['purge_record_ids']);survivors=set(audit['surviving_candidate_ids'])
    require(len(purged)==len(audit['purge_record_ids']) and len(survivors)==len(audit['surviving_candidate_ids']) and not purged&survivors and purged|survivors==set(metadata),'audit_partition')
    cells=defaultdict(list)
    for rid,row in metadata.items():
        require(row['record_id']==rid and row['reason'] is None,'metadata_identity')
        projection={k:row[k] for k in ('record_id','retained_words')};projection['timestamp']=stamp(row['created_utc'])
        cells[row['stratum_id'],row['account_key'],row['community'],row['period']].append(projection)
    public_cells=[];strata=[];all_edges=[];pre_available=post_available=0
    for spec in plan['strata']:
        sid=spec['stratum_id'];cut=stamp(spec['cut']);accounts=spec['accounts']
        labels={a:sid+'/candidate-'+str(i+1).zfill(2) for i,a in enumerate(accounts)}
        before={};after={};account_changes=[]
        for account in accounts:
            before[account]={};after[account]={}
            for letter,community in zip('XY',spec['communities']):
                for period in ('early','late'):
                    key=letter+'/'+period;pool=cells[sid,account,community,period];remaining=[r for r in pool if r['record_id'] in survivors]
                    old=prefix(pool,cut,period);new=prefix(remaining,cut,period)
                    before[account][key]=old;after[account][key]=new
                    pre_available+=old['available'];post_available+=new['available']
                    counts=Counter(reason for r in pool if r['record_id'] in purged for reason in audit['purge_reasons'][r['record_id']])
                    public_cells.append({'cell_id':labels[account]+'/'+key,'stratum_id':sid,'pool_records':len(pool),
                      'pool_words':sum(r['retained_words'] for r in pool),'purged_records':len(pool)-len(remaining),
                      'purged_words':sum(r['retained_words'] for r in pool if r['record_id'] in purged),
                      'surviving_records':len(remaining),'surviving_words':sum(r['retained_words'] for r in remaining),
                      'purge_reason_counts':dict(counts),'before':old,'after':new,
                      'selected_record_count_delta':new['records']-old['records'] if old['available'] and new['available'] else None,
                      'selected_median_shift_days':(new['median_timestamp']-old['median_timestamp'])/DAY if old['available'] and new['available'] else None})
            account_changes.append({'candidate_id':labels[account],'before':gates([before[account]]),'after':gates([after[account]])})
        oldedges=set();newedges=set();lost=[]
        for a,b in combinations(accounts,2):
            old=gates([before[a],before[b]]);new=gates([after[a],after[b]])
            if old['compatible']:oldedges.add(frozenset((a,b)))
            if new['compatible']:newedges.add(frozenset((a,b)))
            edge={'endpoints':[labels[a],labels[b]],'before':old,'after':new,'lost_after_audit':old['compatible'] and not new['compatible']}
            all_edges.append(edge)
            if edge['lost_after_audit']:lost.append(edge)
        result={'stratum_id':sid,'cut':spec['cut'],'pool_accounts':len(accounts),
          'before_qualified_accounts':sum(gates([v])['compatible'] for v in before.values()),
          'after_qualified_accounts':sum(gates([v])['compatible'] for v in after.values()),
          'before_compatible_edges':len(oldedges),'after_compatible_edges':len(newedges),
          'before_maximum_disjoint_blocks':maximum_matching(accounts,oldedges),
          'after_maximum_disjoint_blocks':maximum_matching(accounts,newedges),
          'lost_compatible_edges':len(lost),'lost_edge_failure_gate_counts':dict(Counter(reason for edge in lost for reason in edge['after']['failed_gates'])),
          'account_changes':account_changes}
        actual=next(r for r in final['strata'] if r['stratum_id']==sid)
        require(result['after_qualified_accounts']==actual['post_audit_qualified_accounts'] and len(newedges)==actual['compatible_edges'] and min(result['after_maximum_disjoint_blocks'],spec['block_cap'])==actual['selected_blocks'],'post_result_disagrees_with_finalizer')
        strata.append(result)
    return {'phase':'post_outcome_metadata_only_pre_post_edge_diagnosis','status':'passed',
      'source_metadata_records':len(metadata),'purged_records':len(purged),'surviving_records':len(survivors),
      'candidate_accounts':sum(r['pool_accounts'] for r in strata),'candidate_cells':len(public_cells),
      'before_available_cell_prefixes':pre_available,'after_available_cell_prefixes':post_available,
      'before_compatible_edges':sum(r['before_compatible_edges'] for r in strata),'after_compatible_edges':sum(r['after_compatible_edges'] for r in strata),
      'strata':strata,'cells':public_cells,'edges':all_edges,
      'input_hashes':{k:sha(v) for k,v in [('plan',plan_path),('selection_metadata',selection_path),('preparation_receipt',preparation_path),('audit',audit_path),('final_summary',final_summary_path)]},
      'opaque_labels':'Candidate ordinals follow frozen plan account-list order within each stratum. These are local opaque labels; no source-account map is published.',
      'interpretation':'Within the same frozen audit pool and cut, remove exactly audited purges and reapply the original prefixes and gates. Edge loss may follow unavailable cell volume, changed prefix record counts or changed median dates. This is a mechanical explanation, not a causal estimate or detector outcome.',
      'source_prose_read':False,'source_identifiers_published':False,'new_preprocessing_calls':0,'new_style_calls':0,
      'alternate_cuts_examined':0,'refill_records_added':0,'targets_changed':False}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('plan','selection','preparation','audit','final-summary','out'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args();started=time.monotonic();resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    result=diagnose(args.plan,args.selection,args.preparation,args.audit,args.final_summary)
    result.update(wall_seconds=time.monotonic()-started,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                  implementation_sha256=sha(Path(__file__)),recorded_utc=datetime.now(timezone.utc).isoformat())
    with args.out.open('x') as f:json.dump(encode(result),f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({k:result[k] for k in ('status','candidate_accounts','candidate_cells','before_available_cell_prefixes','after_available_cell_prefixes','before_compatible_edges','after_compatible_edges')}),flush=True)
