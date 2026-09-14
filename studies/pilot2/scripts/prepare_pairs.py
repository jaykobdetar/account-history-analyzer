#!/usr/bin/env python3
"""Prepare bounded paired corpora from a supplied plan; this script cannot score.

Two explicit phases preserve pre-purge account selection. Confirmation sources
and units remain in a separate restricted directory and never enter a scored
dataset document. All records are original source records; no text is invented.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
import hashlib,json,os,resource,sys,time,zipfile
from pathlib import Path

from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import canonical_bytes,digest,load_snapshot
from account_history_analyzer.pipeline import implementation_identity
from account_history_analyzer.schemas import validate
from account_history_analyzer.text import preprocess

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'ahas-realworld-review'
EPOCH=datetime(1970,1,1,tzinfo=timezone.utc)
PLACEHOLDERS={'','anonymous','[anonymous]','unknown','[unknown]','[deleted]','[removed]','[missing]','automoderator'}


def file_sha(path):
    with Path(path).open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()


def hashed(salt,value):return hashlib.sha256((salt+':'+value).encode()).hexdigest()


def write(path,value,*,jsonl=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    data=b''.join(canonical_bytes(row) for row in value) if jsonl else canonical_bytes(value)
    with path.open('xb') as handle:handle.write(data)
    path.chmod(0o600)
    return hashlib.sha256(data).hexdigest()


def read_rows(path):
    with Path(path).open() as handle:return [json.loads(line) for line in handle if line.strip()]


def utc(seconds):
    if type(seconds) is not int:return None
    try:return (EPOCH+timedelta(seconds=seconds)).isoformat(timespec='seconds').replace('+00:00','Z')
    except (OverflowError,ValueError):return None


def microseconds(value):
    delta=datetime.fromisoformat(value)-EPOCH
    return (delta.days*86400+delta.seconds)*1000000+delta.microseconds


def median_twice(rows):
    times=sorted(microseconds(row['record']['created_utc']) for row in rows)
    if not times:return None
    n=len(times);return times[n//2]*2 if n%2 else times[n//2-1]+times[n//2]


def median_utc(rows):
    value=median_twice(rows)
    return (EPOCH+timedelta(microseconds=value//2)).isoformat().replace('+00:00','Z') if value is not None else None


def cell_of(instant,plan):
    if instant is None:return None
    return next((cell for cell in ('early','late') if plan['paired'][cell]['start_utc']<=instant<plan['paired'][cell]['end_utc']),None)


def canonical_order(rows):return sorted(rows,key=lambda row:(row['record']['created_utc'],row['record']['id']))


def choose_shortlist(frame,plan,excluded):
    """Metadata-only global home assignment and balanced split shortlists."""
    accounts=defaultdict(lambda:defaultdict(lambda:Counter()))
    exclusions=Counter()
    for row in frame:
        account=row['source_account'].casefold();community=row['community']
        if account.strip() in PLACEHOLDERS or account in excluded:
            exclusions['old_or_placeholder_frame_rows']+=1;continue
        if community not in plan['communities']:
            exclusions['unplanned_community_frame_rows']+=1;continue
        for year in ('2017','2018'):
            accounts[account][community][year]+=row['years'].get(year,{}).get('present_raw_codepoints',0)
    groups=defaultdict(list)
    for account,communities in accounts.items():
        home=min(communities,key=lambda community:(-sum(communities[community].values()),community))
        ranking=hashed(plan['salts']['author_rank'],account)
        split=plan['splits'][int(hashed(plan['salts']['author_split'],account),16)%len(plan['splits'])]
        groups[home,split].append({'account_key':account,'account_alias':'account-'+ranking[:20],
            'author_rank_hash':ranking,'split':split,'home_community':home,
            'pre_shortlist_capacity':min(communities[home].get(year,0) for year in ('2017','2018')),
            'home_raw_codepoints_by_year':dict(communities[home])})
    chosen=[];summary=[]
    limit=plan['paired']['pre_shortlist_per_home_community_per_split']
    for home in plan['communities']:
        for split in plan['splits']:
            ranked=sorted(groups[home,split],key=lambda row:(-row['pre_shortlist_capacity'],row['author_rank_hash']))
            chosen.extend({**row,'pre_shortlist_rank':rank+1} for rank,row in enumerate(ranked[:limit]))
            summary.append({'home_community':home,'split':split,'available_account_keys':len(ranked),
                            'shortlisted':min(limit,len(ranked)),'not_shortlisted':max(0,len(ranked)-limit)})
    return chosen,summary,dict(exclusions)


def convert(row,account_alias):
    text=row.get('text')
    state='unavailable' if text is None else {'[removed]':'removed','[deleted]':'deleted'}.get(text.strip(),'present')
    return {'schema_version':'1.0.0','id':row['id'],'account_id':account_alias,'kind':'comment',
        'text':text if state=='present' else None,'status':state,'created_utc':utc(row['timestamp']),
        'subreddit':row['meta'].get('subreddit'),'language':None,'edit_state':'unknown','edited_utc':None,
        'title':None,'parent_id':row.get('reply_to'),'thread_id':row.get('root'),
        'parent_created_utc':None,'permalink':row['meta'].get('permalink')}


def select_centered(rows,budget,minimum,center):
    """Choose whole records once; never fill a deleted or insufficient unit."""
    ranked=sorted(rows,key=lambda row:(abs(microseconds(row['record']['created_utc'])-microseconds(center)),
                                      row['record']['created_utc'],row['record']['id']))
    selected=[];words=0
    for row in ranked:
        selected.append(row);words+=row['retained_words']
        if words>=budget and len(selected)>=minimum:break
    return canonical_order(selected)


def shared_budget(cells):return max(1000,min(3000,min(sum(row['retained_words'] for row in rows) for rows in cells)))


def pair_blocks(accounts,cells):
    """Enumerate the three legal perfect matchings, with exact median costs."""
    accounts=sorted(accounts,key=lambda row:row['author_rank_hash'])
    if len(accounts)!=4:raise ValueError('A complete stratum requires exactly four selected accounts; unfilled slots must be explicit.')
    choices=[((0,1),(2,3)),((0,2),(1,3)),((0,3),(1,2))]
    missing=any(median_twice(cells.get((row['account_key'],cell),[])) is None for row in accounts for cell in ('early','late'))
    outcomes=[]
    for choice in choices:
        key=tuple((accounts[a]['author_rank_hash'],accounts[b]['author_rank_hash']) for a,b in choice)
        twice_cost=None if missing else sum(abs(median_twice(cells[accounts[a]['account_key'],cell])-median_twice(cells[accounts[b]['account_key'],cell]))
                                           for a,b in choice for cell in ('early','late'))
        outcomes.append((0 if twice_cost is None else twice_cost,key,choice))
    _,_,chosen=min(outcomes)
    return [(accounts[a],accounts[b]) for a,b in chosen],{
        'summed_cell_median_gap_seconds':None if missing else min(outcomes)[0]/2000000,
        'reason':'missing_cell_median_lexicographic_fallback' if missing else None,
        'enumerated_matchings':3,'pairing_author_hashes':[[accounts[a]['author_rank_hash'],accounts[b]['author_rank_hash']] for a,b in chosen]}


def omit(rows,arm,salt):
    rows=canonical_order(rows)
    if arm=='full':return rows
    if arm=='hash50':return [row for row in rows if int(hashed(salt,row['record']['id']),16)%2==0]
    if arm=='middle50':return [row for i,row in enumerate(rows) if not len(rows)//4<=i<(3*len(rows))//4]
    if arm=='drop_Cornell':return [row for row in rows if row['record']['subreddit']!='Cornell']
    raise ValueError('Unknown predefined omission arm')


def unit_stats(rows,budget,minimum):
    words=sum(row['retained_words'] for row in rows)
    return {'target_B':budget,'actual_eligible_words':words,'overshoot_words':max(0,words-budget),
        'eligible_records':len(rows),'largest_record_share':max((row['retained_words'] for row in rows),default=0)/words if words else None,
        'first_utc':rows[0]['record']['created_utc'] if rows else None,'last_utc':rows[-1]['record']['created_utc'] if rows else None,
        'median_utc':median_utc(rows),'qualified_for_production_comparison':words>=1000 and len(rows)>=minimum,
        'target_reached':words>=budget and len(rows)>=minimum}


def thread_exclusions(pool):
    splits=defaultdict(set)
    for row in pool:
        if row['record']['thread_id']:splits[row['record']['thread_id']].add(row['split'])
    crossed={thread for thread,values in splits.items() if len(values)>1}
    return crossed,{row['record']['id'] for row in pool if row['record']['thread_id'] in crossed}


def manifest(unit_id,alias,plan,cell):
    return {'schema_version':'1.0.0','snapshot_id':unit_id,'account_id':alias,'source_category':'research_corpus',
        'capture_utc':None,'text_format':'markdown','default_language':'en','license_notes':'Local authorized corpus use; no redistribution license inferred.',
        'source_notes':'Original ConvoKit Reddit comment records selected by a preregistered paired sampling adapter. English is a corpus assumption, not verified. Parent creation times and edit history are not inferred.',
        'coverage':{'status':'sampled','start_utc':plan['paired'][cell]['start_utc'],'end_utc':plan['paired'][cell]['end_utc'],
                    'known_gaps':[],'notes':'Whole-record paired sample, with deliberate exclusions and omissions; not a complete account history.'}}


def binding(plan):
    fp,_,_=implementation_identity()
    if fp!=plan['implementation_fingerprint'] or digest(AnalysisConfig.from_toml().analytical())!=plan['analysis_config_sha256']:
        raise ValueError('Frozen AHAS implementation/configuration binding mismatch')


def candidates(plan,plan_path,out):
    if out.exists():raise ValueError('Candidate output exists; preserve the prior run and choose a new destination')
    binding(plan);started=time.monotonic();script_bytes=Path(__file__).read_bytes()
    frame_path=ROOT/'inventory/private/source-frame.jsonl'
    frame_summary=json.loads((ROOT/'inventory/source-frame-summary.json').read_bytes())
    if file_sha(frame_path)!=frame_summary['restricted_frame_sha256']:raise ValueError('Source frame hash mismatch')
    old_map=json.loads((OLD/'inputs/public/source-map.json').read_bytes())
    excluded={row['source_account'].casefold() for row in old_map['accounts']}
    shortlist,metadata_summary,exclusion_summary=choose_shortlist(read_rows(frame_path),plan,excluded)
    by_author={row['account_key']:row for row in shortlist};pool=[];counts=Counter();ids=set();config=AnalysisConfig.from_toml()
    for community in plan['communities']:
        item=plan['source_archives'][community];path=(ROOT/item['path']).resolve()
        if file_sha(path)!=item['sha256']:raise ValueError('Source archive SHA mismatch: '+community)
        with zipfile.ZipFile(path) as archive,archive.open('utterances.jsonl') as source:
            for line in source:
                row=json.loads(line);counts['source_rows_scanned']+=1
                account=row.get('user')
                if not isinstance(account,str) or account.casefold() not in by_author:continue
                account=account.casefold();selection=by_author[account]
                if row.get('root')==row['id']:counts['shortlist_submissions_excluded']+=1;continue
                cell=cell_of(utc(row.get('timestamp')),plan)
                if cell is None:counts['shortlist_outside_time_cells']+=1;continue
                text=row.get('text')
                if not isinstance(text,str) or text.strip() in {'[removed]','[deleted]'}:
                    counts['shortlist_nonpresent_excluded']+=1;continue
                record=convert(row,selection['account_alias'])
                if record['subreddit'] not in plan['communities']:raise ValueError('Unexpected source community')
                view=preprocess(record,{'default_language':'en','text_format':'markdown'},config)
                words=sum(len(tokens) for tokens in view['word_tokens']);counts['shortlist_records_preprocessed']+=1
                if not view['usable'] or words<config['style']['minimum_record_words']:
                    counts['shortlist_below_record_word_guard']+=1;continue
                if record['id'] in ids:raise ValueError('Duplicate selected original record ID')
                ids.add(record['id'])
                pool.append({'record':record,'split':selection['split'],'account_key':account,
                    'home_community':selection['home_community'],'source_community':record['subreddit'],
                    'cell':cell,'retained_words':words,'source_line_sha256':hashlib.sha256(line).hexdigest()})
    capacities=defaultdict(Counter)
    for row in pool:
        if row['source_community']==row['home_community']:capacities[row['account_key']][row['cell']]+=row['retained_words']
    selected=[];selection_groups=[]
    for home in plan['communities']:
        for split in plan['splits']:
            group=[{**row,'eligible_words_by_cell':{cell:capacities[row['account_key']][cell] for cell in ('early','late')}}
                   for row in shortlist if row['home_community']==home and row['split']==split]
            ranked=sorted(group,key=lambda row:(-min(row['eligible_words_by_cell'].values()),row['author_rank_hash']))
            limit=plan['paired']['target_accounts_per_home_community_per_split']
            selected.extend({**row,'selected_rank':i+1} for i,row in enumerate(ranked[:limit]))
            selection_groups.append({'home_community':home,'split':split,'selected':min(limit,len(ranked)),
                                     'unfilled_slots':max(0,limit-len(ranked)),'not_selected_after_capacity_ranking':max(0,len(ranked)-limit)})
    selected_keys={row['account_key'] for row in selected};pool=canonical_order([row for row in pool if row['account_key'] in selected_keys])
    out.mkdir(parents=True,mode=0o700);private=out/'private';private.mkdir(mode=0o700)
    (private/'candidate-adapter.py').write_bytes(script_bytes)
    write(private/'preparation-plan.json',plan)
    pool_hash=write(private/'candidate-pool.jsonl',pool,jsonl=True)
    selection={'protocol_id':plan['protocol_id'],'plan_sha256':file_sha(plan_path),'candidate_pool_sha256':pool_hash,
        'source_frame_sha256':file_sha(frame_path),'selected_before_purges':True,'accounts':selected,
        'shortlist':shortlist,'metadata_strata':metadata_summary,'selected_strata':selection_groups,
        'scan_counts':dict(counts),'metadata_exclusions':exclusion_summary,'candidate_record_count':len(pool),
        'candidate_word_count':sum(row['retained_words'] for row in pool),'scores_computed':False}
    write(private/'selection.json',selection)
    summary={key:selection[key] for key in ['protocol_id','plan_sha256','candidate_pool_sha256','selected_before_purges','metadata_strata','selected_strata','scan_counts','metadata_exclusions','candidate_record_count','candidate_word_count','scores_computed']}
    summary['candidate_records_by_split']=dict(Counter(row['split'] for row in pool))
    write(out/'candidate-summary.json',summary)
    write(out/'candidate-receipt.json',{'elapsed_seconds':time.monotonic()-started,'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        'adapter_sha256':hashlib.sha256(script_bytes).hexdigest(),'argv':sys.argv,'network_isolation':os.environ.get('AHAS_NETWORK_ISOLATION')})
    print(json.dumps(summary))


def finalize(plan,plan_path,out,audit_path):
    binding(plan);started=time.monotonic();private=out/'private';selection=json.loads((private/'selection.json').read_bytes())
    saved_plan=json.loads((private/'preparation-plan.json').read_bytes())
    # Only operational draft/frozen labels may change after candidate creation.
    if {k:v for k,v in plan.items() if k!='state'}!={k:v for k,v in saved_plan.items() if k!='state'}:
        raise ValueError('Plan changed after candidate preparation; preserve and explicitly rebuild candidates')
    if (out/'preparation-summary.json').exists():raise ValueError('Final preparation already exists')
    pool=read_rows(private/'candidate-pool.jsonl');pool_hash=file_sha(private/'candidate-pool.jsonl')
    audit=json.loads(Path(audit_path).read_bytes())
    if audit.get('status')!='audited' or audit.get('candidate_pool_sha256')!=pool_hash:
        raise ValueError('A complete, exactly bound leakage audit is required before finalization')
    ids={row['record']['id'] for row in pool};extra=set(audit['purge_record_ids'])
    if not extra<=ids:raise ValueError('Leakage purge references unknown original IDs')
    cluster_by_id={};split_by_id={row['record']['id']:row['split'] for row in pool}
    for cluster in audit['near_duplicate_clusters']:
        if len({split_by_id.get(identifier) for identifier in cluster['record_ids']})>1 and not set(cluster['record_ids'])<=extra:
            raise ValueError('Cross-split audited component was not symmetrically purged')
        for identifier in cluster['record_ids']:
            if identifier not in ids or identifier in cluster_by_id:raise ValueError('Invalid or duplicate cluster membership')
            cluster_by_id[identifier]=cluster['cluster_id']
    if set(cluster_by_id)!=ids:raise ValueError('Completed audit must cover every candidate including actual singleton components')
    crossed,thread_purge=thread_exclusions(pool)
    removed=extra|thread_purge;retained=[row for row in pool if row['record']['id'] not in removed]
    by_cell=defaultdict(list)
    for row in retained:by_cell[row['account_key'],row['source_community'],row['cell']].append(row)
    for rows in by_cell.values():rows.sort(key=lambda row:(row['record']['created_utc'],row['record']['id']))
    blocks=[];units=[];pair_observations=[];datasets=defaultdict(lambda:{'texts':[],'pairs':[]});minimum=plan['paired']['minimum_eligible_records']
    for home_index,home in enumerate(plan['communities']):
        other=plan['communities'][(home_index+1)%len(plan['communities'])]
        for split in plan['splits']:
            accounts=[row for row in selection['accounts'] if row['home_community']==home and row['split']==split]
            if len(accounts)!=4:
                blocks.append({'home_community':home,'split':split,'status':'unfilled_account_slots','selected_accounts':len(accounts)});continue
            matches,matching=pair_blocks(accounts,{(row['account_key'],cell):by_cell[row['account_key'],home,cell] for row in accounts for cell in ('early','late')})
            for index,(a,b) in enumerate(matches):
                block_id='block-'+digest({'home':home,'split':split,'accounts':[a['account_key'],b['account_key']]})[:24]
                block={'block_id':block_id,'home_community':home,'split':split,'accounts':[a['account_alias'],b['account_alias']],
                       'account_keys':[a['account_key'],b['account_key']],'matching':matching,'conditions':{}}
                for condition in plan['paired']['conditions']:
                    late_community=home if condition=='within_community' else other
                    cells=[by_cell[account['account_key'],home if cell=='early' else late_community,cell] for account in (a,b) for cell in ('early','late')]
                    budget=shared_budget(cells);base=[select_centered(rows,budget,minimum,plan['paired'][cell]['center_utc']) for rows,cell in zip(cells,['early','late','early','late'])]
                    block['conditions'][condition]={'target_B':budget,'cell_capacities':[sum(row['retained_words'] for row in rows) for rows in cells],
                                                   'late_community':late_community}
                    for arm in plan['paired']['arms']:
                        emitted=[];emitted_rows=[]
                        for position,(account,cell) in enumerate([(a,'early'),(a,'late'),(b,'early'),(b,'late')]):
                            rows=omit(base[position],arm,plan['salts']['omission'])
                            unit_id='unit-'+digest({'block':block_id,'condition':condition,'arm':arm,'account':account['account_key'],'cell':cell})[:24]
                            subtree='confirmation' if split=='confirmation' else 'scored'
                            directory=out/subtree/'units';directory.mkdir(parents=True,exist_ok=True,mode=0o700)
                            source_path=directory/(unit_id+'.jsonl');manifest_path=directory/(unit_id+'.snapshot.json')
                            write(source_path,[row['record'] for row in rows],jsonl=True)
                            write(manifest_path,manifest(unit_id,account['account_alias'],plan,cell))
                            snapshot=load_snapshot(source_path,manifest_path)
                            groups={'author':[account['account_key']],'related_sample':[block_id,'author:'+account['account_key']]}
                            for key,values in [('thread',{row['record']['thread_id'] for row in rows if row['record']['thread_id']}),
                                               ('source_document',{row['record']['id'] for row in rows}),
                                               ('near_duplicate_cluster',{cluster_by_id[row['record']['id']] for row in rows})]:
                                if values:groups[key]=sorted(values)
                            unit={'text_id':unit_id,'input':str(source_path.relative_to(out)),'manifest':str(manifest_path.relative_to(out)),
                                  'groups':groups}
                            emitted.append(unit)
                            emitted_rows.append(rows)
                            units.append({'text_id':unit_id,'block_id':block_id,'split':split,'account_key':account['account_key'],
                                'home_community':home,'source_community':home if cell=='early' else late_community,'cell':cell,'condition':condition,'arm':arm,
                                'base_record_ids':[row['record']['id'] for row in base[position]],'record_ids':[row['record']['id'] for row in rows],
                                'stats':unit_stats(rows,budget,minimum),'input':unit['input'],'manifest':unit['manifest'],
                                'canonical_snapshot_sha256':snapshot.canonical_sha256,'groups':groups})
                        if split!='confirmation':
                            key=(home,condition,arm)
                            datasets[key]['texts'].extend(emitted)
                            for left,right,label in [(0,1,'same_author'),(2,3,'same_author'),(0,3,'different_author'),(2,1,'different_author')]:
                                pair={'pair_id':'pair-'+digest({'block':block_id,'condition':condition,'left':left,'right':right})[:24],
                                    'left_text_id':emitted[left]['text_id'],'right_text_id':emitted[right]['text_id'],'split':split,'label':label}
                                datasets[key]['pairs'].append(pair)
                                left_time=median_twice(emitted_rows[left]);right_time=median_twice(emitted_rows[right])
                                pair_observations.append({**pair,'block_id':block_id,'home_community':home,'condition':condition,'arm':arm,
                                    'pair_median_time_gap_seconds':abs(left_time-right_time)/2000000 if left_time is not None and right_time is not None else None,
                                    'target_B':budget,'left':unit_stats(emitted_rows[left],budget,minimum),'right':unit_stats(emitted_rows[right],budget,minimum)})
                blocks.append(block)
    output_datasets=[]
    directory=out/'scored/datasets';directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    for (home,condition,arm),content in sorted(datasets.items()):
        for method in plan['methods']:
            name=home+'.'+condition+'.'+arm+'.'+method['name']
            document={'schema_version':'1.0.0','format':'paired_text','dataset_id':plan['protocol_id']+':'+name,
                'provenance':'Authorized local ConvoKit Reddit corpora. Source and preparation hashes in paired preparation manifests. Original body text, IDs and UTC creation times are preserved. English is assumed. Confirmation sources are absent.',
                'label_definition':'same_author/different_author denote equal/different casefolded source account keys only. Shared or automated accounts, multiple accounts per person, and actual human continuity are unverified. These labels are not human-authorship ground truth.',
                'protocol':{'analysis_config_sha256':plan['analysis_config_sha256'],'registered_before_evaluation':True,
                    'preregistration_provenance':'Protocol and full preparation hashes must be frozen by the study runner before any evaluator invocation; this adapter performs no scoring.',
                    'distance':{key:method[key] for key in ['method_id','view','n']},'frozen_threshold':None},
                'texts':[{**unit,'input':'../../'+unit['input'],'manifest':'../../'+unit['manifest']} for unit in content['texts']],
                'pairs':content['pairs']}
            validate(document,'evaluation_paired_text')
            path=directory/(name+'.json');checksum=write(path,document)
            output_datasets.append({'home_community':home,'condition':condition,'arm':arm,'method':method['name'],
                'primary_method':method['primary'],'path':str(path.relative_to(out)),'sha256':checksum,
                'pairs':len(document['pairs']),'texts':len(document['texts'])})
    write(private/'units.json',units);write(private/'blocks.json',blocks);write(private/'pair-observations.json',pair_observations)
    write(private/'purge.json',{'candidate_pool_sha256':pool_hash,'audit_sha256':file_sha(audit_path),
        'cross_split_thread_ids':sorted(crossed),'thread_purge_record_ids':sorted(thread_purge),'audit_purge_record_ids':sorted(extra),
        'all_purge_record_ids':sorted(removed),'no_replacements_or_refills':True})
    summary={'protocol_id':plan['protocol_id'],'plan_sha256':file_sha(plan_path),'candidate_pool_sha256':pool_hash,
        'audit_sha256':file_sha(audit_path),'candidate_records':len(pool),'records_purged':len(removed),
        'thread_purged_records':len(thread_purge),'audit_purged_records':len(extra),'surviving_candidate_records':len(retained),
        'selected_accounts':len(selection['accounts']),'selected_strata':selection['selected_strata'],
        'unit_count':len(units),'confirmation_unit_count':sum(unit['split']=='confirmation' for unit in units),
        'dataset_count':len(output_datasets),'datasets':output_datasets,'scores_computed':False,
        'pair_label_balance_without_method_repetition':dict(Counter(row['label'] for row in pair_observations)),
        'confirmation_in_scored_documents':False,'leakage_limitations':audit.get('limitations',[])}
    write(out/'preparation-summary.json',summary)
    write(out/'prepared-sha256.json',{str(path.relative_to(out)):file_sha(path) for path in sorted(out.rglob('*')) if path.is_file()})
    write(out/'finalize-receipt.json',{'elapsed_seconds':time.monotonic()-started,'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        'argv':sys.argv,'adapter_sha256':file_sha(__file__),'network_isolation':os.environ.get('AHAS_NETWORK_ISOLATION')})
    print(json.dumps({key:summary[key] for key in ['selected_accounts','candidate_records','records_purged','surviving_candidate_records','unit_count','confirmation_unit_count','dataset_count','scores_computed']}))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=['candidates','finalize'])
    parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--audit',type=Path)
    args=parser.parse_args()
    if os.environ.get('AHAS_NETWORK_ISOLATION')!='linux_seccomp_socket_denial':raise RuntimeError('Run preparation under scripts/offline_exec.py')
    plan=json.loads(args.plan.read_bytes())
    if args.phase=='candidates':candidates(plan,args.plan,args.out)
    else:
        if args.audit is None:parser.error('finalize requires --audit')
        finalize(plan,args.plan,args.out,args.audit)


if __name__=='__main__':main()
