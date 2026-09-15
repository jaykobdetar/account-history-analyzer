"""Bounded score-free five-sample replication enumeration; original helpers reused."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
P4=ROOT/'studies/pilot4_chronological_controls/scripts'
P5=ROOT/'studies/pilot5_shared_anchor/scripts'
sys.path[:0]=[str(P5),str(P4)]
from metadata_feasibility import select_prefix,seconds,jsonable
from metadata_feasibility_v2 import verify_matching_backend
from prepare_shared_anchor import evaluate,KEYS
from run_full_chronology import sha,write

PAIRS=[['AskAcademia','GradSchool'],['AskPhysics','Physics'],['math','learnmath'],
       ['linux','linuxquestions'],['programming','learnprogramming']]
DESIGN={'half_band_days':180,'half_target_words':5000,'half_min_records':40,
        'half_max_words':5500,'half_max_records':200,'record_word_min':20,'record_word_max':500}
LIMITS={'wall_seconds':1800,'address_space_bytes':4294967296,'metadata_rows':3000000,
        'metadata_bytes':1073741824,'directional_evaluations':2000000,'private_output_bytes':268435456}


def identity(account):
    return hashlib.sha256(('pilot6-anchor-order-v1\0'+account.casefold()).encode()).hexdigest()


def tie(row):
    return (row['stratum_id'],row['cut'],identity(row['account_a']),identity(row['account_b']),
            row['community_x'],row['community_y'])


def edge_key(row):
    return tuple(sorted((row['account_a'],row['account_b']),key=identity))


def choose_edges(rows):
    best={}
    for row in rows:
        if not row['valid']:continue
        edge=edge_key(row)
        if edge not in best or (row['cost'],tie(row))<(best[edge]['cost'],tie(best[edge])):
            best[edge]=row
    return best


def flags_excluded(flags,selection):
    rows=flags['accounts'];keys=[r['account_key'] for r in rows]
    fields=('pilot1_or_pilot2_or_private_mandatory_exclusion','pilot3_selected_scored_exposure','prior_capacity_only_exposure')
    if any(not isinstance(a,str) or not a or a!=a.casefold() for a in keys) or len(set(keys))!=len(keys) or \
       any(type(r[k]) is not bool for r in rows for k in fields):raise ValueError('Invalid canonical identities or Boolean flags')
    old={r['account_key'] for r in rows if r['pilot1_or_pilot2_or_private_mandatory_exclusion']}
    scored={r['account_key'] for r in rows if r['pilot3_selected_scored_exposure']}
    five_keys=[selection['selected'][k] for k in ('account_a','account_b')]
    if any(not isinstance(a,str) or not a or a!=a.casefold() for a in five_keys):raise ValueError('Invalid canonical Pilot5 exclusion identities')
    five=set(five_keys)
    if len(old)!=57 or len(scored)!=60 or len(five)!=2 or len(old|scored|five)!=119:
        raise ValueError('Expected distinct57+60+2 exclusion identities')
    return old|scored|five,{r['account_key'] for r in rows if r['prior_capacity_only_exposure']}


def run(plan_path,out,private):
    started=time.monotonic();plan=json.loads(Path(plan_path).read_bytes())
    if os.environ.get('AHAS_NETWORK_ISOLATION')!='linux_seccomp_socket_denial':raise ValueError('Offline wrapper required')
    if plan['phase']!='frozen_before_replication_metadata' or plan['script_sha256']!=sha(__file__):raise ValueError('Missing metadata registration')
    if plan['community_pairs']!=PAIRS or plan['design']!=DESIGN or plan['limits']!=LIMITS:raise ValueError('Registered design changed')
    expected=[f'{year}-{month:02d}-01T00:00:00Z' for year in range(2010,2019) for month in range(1,13) if (year,month)<=(2018,5)]
    if plan['cuts']!=expected:raise ValueError('Calendar grid changed')
    bound={str(Path(r['path']).resolve()):r['sha256'] for r in plan['bindings']}
    if len(bound)!=len(plan['bindings']):raise ValueError('Duplicate input binding')
    needed=[__file__,plan['exposure_flags'],plan['pilot5_selection'],plan['protocol']]+[r['path'] for r in plan['source_metadata']]
    needed += [str(P4/n) for n in ('metadata_feasibility.py','metadata_feasibility_v2.py','chronology_math.py','run_full_chronology.py')]+[str(P5/'prepare_shared_anchor.py')]
    if not set(map(lambda p:str(Path(p).resolve()),needed))<=set(bound):raise ValueError('Missing binding')
    sources=plan['source_metadata']
    if len({str(Path(r['path']).resolve()) for r in sources})!=len(sources):raise ValueError('Duplicate metadata source path')
    if any(type(r['bytes']) is not int or r['bytes']<0 for r in sources) or sum(r['bytes'] for r in sources)>LIMITS['metadata_bytes']:
        raise ValueError('Metadata input ceiling')
    if any(r['sha256']!=bound[str(Path(r['path']).resolve())] for r in sources):raise ValueError('Metadata declared hash differs from binding')
    for path,digest in bound.items():
        if sha(path)!=digest:raise ValueError('Bound metadata input changed')
    resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Metadata wall limit')))
    signal.alarm(LIMITS['wall_seconds'])
    out=Path(out);private=Path(private);out.mkdir(parents=True,exist_ok=False);private.mkdir(mode=0o700,parents=True,exist_ok=False)
    write(out/'start-binding.json',{'phase':plan['phase'],'plan_sha256':sha(plan_path),'script_sha256':sha(__file__),
          'started_utc':datetime.now(timezone.utc).isoformat(),'style_calls':0,'grid_localization_evaluated':False})
    counts=Counter();cuts=[];best={};timeline=defaultdict(list);entries={};seen=set();verified_sources=[]
    def check():
        if time.monotonic()-started>LIMITS['wall_seconds']:raise TimeoutError('Metadata wall limit')
    try:
        matching=verify_matching_backend(plan['matching_backend'],check)
        excluded,capacity=flags_excluded(json.loads(Path(plan['exposure_flags']).read_bytes()),json.loads(Path(plan['pilot5_selection']).read_bytes()))
        requested={c for pair in PAIRS for c in pair}
        for source in plan['source_metadata']:
            path=Path(source['path'])
            if path.stat().st_size!=source['bytes']:raise ValueError('Metadata bytes changed')
            digest=hashlib.sha256();source_bytes=source_rows=0
            with path.open('rb') as f:
                for line in f:
                    digest.update(line);source_bytes+=len(line);source_rows+=1
                    counts['metadata_rows']+=1;counts['metadata_bytes']+=len(line)
                    if counts['metadata_rows']>LIMITS['metadata_rows']:raise RuntimeError('Metadata row ceiling')
                    if counts['metadata_bytes']>LIMITS['metadata_bytes']:raise RuntimeError('Metadata byte ceiling')
                    if counts['metadata_rows']%10000==0:check()
                    row=json.loads(line);rid=row['record_id']
                    if not isinstance(rid,str) or not rid:raise ValueError('Invalid original record ID')
                    if rid in seen:raise ValueError('Metadata original ID repeated')
                    seen.add(rid)
                    account=row['account_key']
                    if not isinstance(account,str) or not account or account!=account.casefold():raise ValueError('Noncanonical metadata account key')
                    words=row['retained_words']
                    if words is None:
                        if row['reason'] is None:raise ValueError('Eligible metadata cannot have null retained words')
                    elif type(words) is not int or words<0:raise ValueError('Invalid integer retained-word metadata')
                    if row['account_key'] in excluded:counts['excluded_rows']+=1;continue
                    if row['community'] not in requested:counts['outside_registered_communities']+=1;continue
                    if row['reason'] is not None or not 20<=row['retained_words']<=500:counts['ineligible_rows']+=1;continue
                    small={'record_id':rid,'timestamp':seconds(row['created_utc']),'retained_words':row['retained_words']}
                    timeline[row['account_key'],row['community']].append(small)
                    entries[rid]={'record':{'created_utc':row['created_utc']}}
                    counts['eligible_rows']+=1
            if source_bytes!=source['bytes'] or digest.hexdigest()!=source['sha256']:
                raise ValueError('Metadata source changed during streaming')
            verified_sources.append({'source_index':len(verified_sources)+1,'bytes':source_bytes,
                                     'rows':source_rows,'sha256':digest.hexdigest()})
        del seen
        accounts=sorted({a for a,c in timeline},key=identity)
        for rows in timeline.values():rows.sort(key=lambda r:(r['timestamp'],r['record_id']))
        written=0
        with (private/'directional-evaluations.jsonl').open('xb') as f:
            for pair_index,(x,y) in enumerate(PAIRS,1):
                sid=f'stratum-{pair_index:02d}'
                possible=[a for a in accounts if all(len(timeline[a,c])>=40 and sum(r['retained_words'] for r in timeline[a,c])>=5000 for c in (x,y))]
                for cut_text in expected:
                    check();cut=seconds(cut_text);cells={};cell_fail=Counter();stats=Counter()
                    for a in possible:
                        for c in (x,y):
                            for period in ('early','late'):
                                value=select_prefix(timeline[a,c],cut,period,DESIGN)
                                cells[a,c,period]=value
                                if value is None:cell_fail[c+'/'+period]+=1
                    late_ok=[a for a in possible if all(cells[a,c,'late'] is not None for c in (x,y))]
                    stats['all_possible_ordered_directions']=2*len(possible)*(len(possible)-1)
                    stats['directions_without_two_late_accounts']=2*(len(possible)*(len(possible)-1)-len(late_ok)*(len(late_ok)-1))
                    for key in ('directions_without_anchor','evaluated_directions','valid_directions','invalid_evaluated_directions'):
                        stats[key]=0
                    for a in late_ok:
                        for b in late_ok:
                            if a==b:continue
                            for cx,cy in ((x,y),(y,x)):
                                anchor=cells[a,cx,'early']
                                if anchor is None:stats['directions_without_anchor']+=1;continue
                                counts['directional_evaluations']+=1
                                if counts['directional_evaluations']>LIMITS['directional_evaluations']:raise RuntimeError('Direction ceiling')
                                samples=dict(zip(KEYS,[anchor,cells[a,cx,'late'],cells[b,cx,'late'],cells[a,cy,'late'],cells[b,cy,'late']],strict=True))
                                result=evaluate(samples,entries)
                                row={'stratum_id':sid,'cut':cut_text,'account_a':a,'account_b':b,'community_x':cx,'community_y':cy,**result}
                                raw=(json.dumps(jsonable(row),sort_keys=True,separators=(',',':'))+'\n').encode();written+=len(raw)
                                if written>LIMITS['private_output_bytes']:raise RuntimeError('Enumeration output ceiling')
                                f.write(raw);stats['evaluated_directions']+=1
                                for reason in result['reason_codes']:stats[reason]+=1
                                if result['valid']:
                                    stats['valid_directions']+=1;edge=edge_key(row)
                                    if edge not in best or (row['cost'],tie(row))<(best[edge]['cost'],tie(best[edge])):best[edge]=row
                                else:stats['invalid_evaluated_directions']+=1
                    if stats['all_possible_ordered_directions']!=stats['directions_without_two_late_accounts']+stats['directions_without_anchor']+stats['evaluated_directions']:
                        raise AssertionError('Directional coverage does not reconcile')
                    if stats['evaluated_directions']!=stats['valid_directions']+stats['invalid_evaluated_directions']:
                        raise AssertionError('Evaluated direction outcomes do not reconcile')
                    for key in ('all_possible_ordered_directions','directions_without_two_late_accounts','directions_without_anchor'):
                        counts[key]+=stats[key]
                    cuts.append({'stratum_id':sid,'communities':[x,y],'cut':cut_text,'whole_history_necessary_accounts':len(possible),
                        'accounts_with_two_late_prefixes':len(late_ok),'unavailable_prefix_counts':dict(cell_fail),**dict(stats)})
                print(json.dumps({'completed_stratum':sid,'cuts':101,'valid_unordered_edges_so_far':len(best),'style_calls':0}),flush=True)
        nodes=sorted({a for edge in best for a in edge},key=identity)
        match=matching(nodes,{edge:row['cost'] for edge,row in best.items()},check)
        matched=sorted((best[tuple(pair)] for pair in match['pairs']),key=lambda r:(r['cost'],tie(r)))
        pool=[dict(row,pair_id=f'pilot6-pair-{i:02d}',prior_capacity_only_accounts=sum(a in capacity for a in (row['account_a'],row['account_b']))) for i,row in enumerate(matched[:20],1)]
        write(private/'provisional-pairs.json',{'plan_sha256':sha(plan_path),'pairs':jsonable(pool),'matching':jsonable(match),'unique_valid_edges':len(best)})
        write(private/'best-edge-directions.json',jsonable(list(best.values())))
        if sum(p.stat().st_size for p in private.iterdir())>LIMITS['private_output_bytes']:raise RuntimeError('Final metadata output ceiling')
        write(out/'all-calendar-cuts.json',cuts)
        summary={'status':'completed_score_free_metadata','plan_sha256':sha(plan_path),'counts':dict(counts),'pair_cut_count':len(cuts),
            'verified_source_metadata':verified_sources,
            'global_maximum_matching_pairs':match['cardinality'],'matching_exact_cost':jsonable(match['cost']),'provisional_pairs':len(pool),
            'target_new_pairs':10,'pool_ceiling':20,'source_accounts_in_provisional_pool':2*len(pool),'unique_valid_unordered_edges':len(best),
            'provisional_pairs_sha256':sha(private/'provisional-pairs.json'),'directional_enumeration_sha256':sha(private/'directional-evaluations.jsonl'),
            'style_calls':0,'grid_localization_evaluated':False,'cohort_finalized':False,'wall_seconds':time.monotonic()-started,
            'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
            'provisional_pair_metadata':[{k:jsonable(v) for k,v in row.items() if k not in ('account_a','account_b')} for row in pool]}
        write(out/'feasibility-summary.json',summary)
        print(json.dumps({k:summary[k] for k in ('status','provisional_pairs','global_maximum_matching_pairs','wall_seconds')}),flush=True)
        for p in private.iterdir():p.chmod(0o600)
        return 0
    except Exception as e:
        write(out/'incomplete-metadata.json',{'status':'incomplete_not_zero_capacity','error_type':type(e).__name__,'counts':dict(counts),
              'completed_pair_cuts':len(cuts),'wall_seconds':time.monotonic()-started,'style_calls':0})
        raise
    finally:signal.alarm(0)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ('plan','out','private-out'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();raise SystemExit(run(a.plan,a.out,a.private_out))
