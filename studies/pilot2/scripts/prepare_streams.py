#!/usr/bin/env python3
"""Chronological preparation and single-case execution for the second pilot.

Preparation may count retained words and audit grouping, but never calculates
style distances, output grids or optimizer candidates. Execution requires a
separate, matching root-authorized protocol freeze receipt.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from account_history_analyzer import AnalysisConfig, __version__, load_snapshot
from account_history_analyzer.io import canonical_bytes, canonical_digest, epoch_us, record_sort_key
from account_history_analyzer.pipeline import implementation_identity
from account_history_analyzer.schemas import validate

COMMUNITIES=('ApplyingToCollege','Cornell','college')
ARMS=('full','hash50','middle50','drop_Cornell')
CHRONOLOGY_SALT='ahas-pilot2-chronology-v1'
OMISSION_SALT='ahas-pilot2-omission-v1'
PREFIX='ahas-pilot2-20260914:chronological:'
SCOPE={'scope_type':'pooled','kind':'comment','subreddit':None}
EPOCH=datetime(1970,1,1,tzinfo=timezone.utc)


def sha_file(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block:=stream.read(65536):result.update(block)
    return result.hexdigest()


def keyed(kind,value):
    return hashlib.sha256((PREFIX+kind+':'+value).encode()).hexdigest()


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def author_alias(account_key):return 'chrono-'+keyed('author',account_key)[:20]


def source_status(text):
    if text is None:return 'unavailable'
    if not isinstance(text,str):raise ValueError('Non-string source text; never silently drop a record')
    return {'[removed]':'removed','[deleted]':'deleted'}.get(text.strip(),'present')


def timestamp(seconds):
    if seconds is None:return None
    if type(seconds) is not int:raise ValueError('Noninteger timestamp cannot be silently rounded')
    try:return (EPOCH+timedelta(seconds=seconds)).isoformat(timespec='seconds').replace('+00:00','Z')
    except (ValueError,OverflowError) as exc:raise ValueError('Unrepresentable source timestamp') from exc


def convert(row,account_key):
    """Preserve record content and metadata; declaration of English is manifest-only."""
    status=source_status(row.get('text'))
    record={'schema_version':'1.0.0','id':row['id'],'account_id':author_alias(account_key),'kind':'comment',
        'text':row.get('text') if status=='present' else None,'status':status,'created_utc':timestamp(row.get('timestamp')),
        'subreddit':(row.get('meta') or {}).get('subreddit'),'language':None,'title':None,
        'edit_state':'unknown','edited_utc':None,'parent_id':row.get('reply_to'),'thread_id':row.get('root'),
        'parent_created_utc':None,'permalink':(row.get('meta') or {}).get('permalink')}
    validate(record,'record');return record


def manifest(alias,records,*,constructed=False):
    times=[r['created_utc'] for r in records if r['created_utc'] is not None]
    notes=('Constructed source-account timeline; original text, IDs and timestamps survive. Only account metadata is reassigned. ' if constructed else
           'All available comments of this account across the three frozen source archives, with no trimming or thread deletion. ')
    notes+='Complete means complete within these available archives, not complete Reddit or account coverage. English is an unverified corpus-level operational declaration, not per-record detection. Edit histories are unknown.'
    result={'schema_version':'1.0.0','snapshot_id':alias,'account_id':alias,'source_category':'research_corpus','capture_utc':None,
        'text_format':'markdown','default_language':'en','source_notes':notes,
        'license_notes':'Corpus-specific redistribution rights remain unestablished; local study use only, no raw-prose redistribution.',
        'coverage':{'status':'sampled','start_utc':min(times) if times else None,'end_utc':max(times) if times else None,
                    'known_gaps':[],'notes':'Available historical corpus comments only; omissions are not verified absence of activity.'}}
    validate(result,'snapshot');return result


def metadata_candidates(frame_rows,excluded_authors):
    """Combine case-insensitive identities across archives before capacity checks."""
    combined={}
    for row in frame_rows:
        key=row['source_account'].casefold()
        item=combined.setdefault(key,{'account_key':key,'comment_count':0,'present_raw_codepoints':0,
            'raw_codepoints_by_home_source':Counter(),'source_spellings':set(),'excluded_reasons':set()})
        item['comment_count']+=row['comment_count'];item['present_raw_codepoints']+=row['present_raw_codepoints']
        item['raw_codepoints_by_home_source'][row['source_community']]+=row['present_raw_codepoints']
        item['source_spellings'].add(row['source_account'])
        if row['excluded_from_new_sampling']:item['excluded_reasons'].add(row['excluded_from_new_sampling'])
    result=[];counts=Counter()
    for key,item in combined.items():
        if key in excluded_authors:item['excluded_reasons'].add('paired_or_confirmation_author')
        if not 200<=item['comment_count']<=400:item['excluded_reasons'].add('outside_200_to_400_available_comment_guard')
        if item['present_raw_codepoints']<40000:item['excluded_reasons'].add('below_40000_present_raw_codepoints')
        if item['excluded_reasons']:
            counts.update(item['excluded_reasons']);continue
        item['home_community']=min(COMMUNITIES,key=lambda c:(-item['raw_codepoints_by_home_source'][c],c))
        item['rank_hash']=hashlib.sha256((CHRONOLOGY_SALT+':'+key).encode()).hexdigest()
        item['source_spellings']=sorted(item['source_spellings'])
        item['raw_codepoints_by_home_source']=dict(item['raw_codepoints_by_home_source'])
        item['excluded_reasons']=[]
        result.append(item)
    return sorted(result,key=lambda item:(COMMUNITIES.index(item['home_community']),item['rank_hash'])),dict(counts)


def median_instant(records):
    """Upper middle actual timestamp; it is always a supplied instant."""
    if not records or any(r['created_utc'] is None for r in records):return None
    times=sorted(epoch_us(r['created_utc']) for r in records)
    return times[len(times)//2]


def pair_closest(accounts):
    """Greedy closest median timestamps; hash ties, then hash orientation.

    Selection precedes pairing. Missing times do not prompt replacement; those
    authors still occupy selected slots and yield explicit unconstructible pairs.
    """
    remaining=list(accounts);pairs=[]
    while len(remaining)>=2:
        candidates=[]
        for i in range(len(remaining)):
            for j in range(i+1,len(remaining)):
                a,b=remaining[i],remaining[j]
                error=abs(a['median_utc_us']-b['median_utc_us']) if a['median_utc_us'] is not None and b['median_utc_us'] is not None else float('inf')
                tie=keyed('pair',':'.join(sorted((a['account_key'],b['account_key']))))
                candidates.append((error,tie,i,j))
        _,_,i,j=min(candidates)
        pair=sorted((remaining[i],remaining[j]),key=lambda a:keyed('orientation',a['account_key']))
        pairs.append(pair)
        remaining=[a for k,a in enumerate(remaining) if k not in {i,j}]
    return pairs,remaining


def construct(left,right,alias):
    """Metadata-fixed union-median cut, retaining complete before/after portions."""
    joined=left+right
    if not joined or any(r['created_utc'] is None for r in joined):
        return {'status':'not_constructible','reason_codes':['missing_timestamps_prevent_complete_chronological_cut'],'records':[],'source_sides':{},'cut_utc':None}
    ordered=sorted(joined,key=record_sort_key)
    cut=ordered[len(ordered)//2]['created_utc']
    before=[r for r in left if epoch_us(r['created_utc'])<epoch_us(cut)]
    after=[r for r in right if epoch_us(r['created_utc'])>=epoch_us(cut)]
    if not before or not after:
        return {'status':'not_constructible','reason_codes':['empty_source_side_at_registered_cut'],'records':[],'source_sides':{},'cut_utc':cut}
    sides={r['id']:'left' for r in before};sides.update({r['id']:'right' for r in after})
    if len(sides)!=len(before)+len(after):raise ValueError('Source histories share record IDs')
    rows=sorted(({**r,'account_id':alias} for r in before+after),key=record_sort_key)
    return {'status':'constructed','reason_codes':[],'records':rows,'source_sides':sides,'cut_utc':cut}


def arm_records(records,arm):
    if arm=='full':return list(records)
    if arm=='hash50':
        keep={r['id'] for r in records if int(hashlib.sha256((OMISSION_SALT+':'+r['id']).encode()).hexdigest(),16)%2==0}
        return [r for r in records if r['id'] in keep]
    if arm=='middle50':
        start=len(records)//4;end=3*len(records)//4
        return list(records[:start])+list(records[end:])
    if arm=='drop_Cornell':return [r for r in records if r['subreddit']!='Cornell']
    raise ValueError('Unknown fixed omission arm')


def surviving_truth(records,source_sides):
    labels=[source_sides[r['id']] for r in records]
    if not labels or 'left' not in labels or 'right' not in labels:
        return {'status':'not_labeled_construction','reason_codes':['an_entire_source_side_is_absent_after_omission'],'truth_boundaries':None}
    cut=labels.index('right')
    if labels!=['left']*cut+['right']*(len(labels)-cut):raise ValueError('Source labels are not a single chronological transition')
    return {'status':'labeled_construction','reason_codes':[],'truth_boundaries':[cut]}


def word_eligibility(features,source_records):
    eligible=[r for r in features if r['kind']=='comment' and r['usable'] and r['language']=='en'
              and r['created_utc'] is not None and r['counts']['retained_words']>=20]
    return {'eligible_record_count':len(eligible),'eligible_words':sum(r['counts']['retained_words'] for r in eligible),
            'record_count':len(features),'status_counts':dict(sorted(Counter(r['status'] for r in source_records).items())),
            'missing_timestamps':sum(r['created_utc'] is None for r in features)}


def load_jsonl(path):
    with Path(path).open() as stream:
        for line in stream:
            if line.strip():yield json.loads(line)


def require_offline():
    if os.environ.get('AHAS_NETWORK_ISOLATION')!='linux_seccomp_socket_denial':raise ValueError('Run under the offline runner')

# Preparation orchestration and freeze-gated one-case driver are completed after
# the paired cohort and group-audit owner publish their stable input contracts.


def check_current_release(protocol):
    config=AnalysisConfig.from_toml();fp,environment,resources=implementation_identity()
    if __version__!=protocol['source_release'] or fp!=protocol['implementation_fingerprint']:
        raise ValueError('Source release differs from the protocol')
    if canonical_digest(config.analytical())!=protocol['analysis_config_sha256']:
        raise ValueError('Expanded default configuration differs from the protocol')
    if protocol['salts']['chronology']!=CHRONOLOGY_SALT or protocol['salts']['omission']!=OMISSION_SALT:
        raise ValueError('Registered selection/omission salts differ')
    if tuple(protocol['chronological']['arms'])!=ARMS:
        raise ValueError('Registered chronological omission arms differ')
    expected={'source_comments_min':200,'source_comments_max':400,'present_raw_codepoints_min':40000,
              'eligible_retained_words_min':8000,'boundary_tolerance_records':10,'target_splice_pairs':6}
    if any(protocol['chronological'][k]!=v for k,v in expected.items()):raise ValueError('Unexpected chronological protocol bounds')
    return config,{'suite_version':__version__,'implementation_fingerprint':fp,'reference_environment':environment,'resource_sha256':resources}


def spool_candidates(root,protocol,candidates,directory):
    wanted={c['account_key']:c for c in candidates};counts=Counter();source_receipts=[]
    for community in COMMUNITIES:
        spec=protocol['source_archives'][community];archive_path=root/spec['path']
        if sha_file(archive_path)!=spec['sha256']:raise ValueError('Frozen source archive hash mismatch')
        member_hash=hashlib.sha256();read_rows=0;kept=0
        with zipfile.ZipFile(archive_path) as archive:
            names=[x for x in archive.infolist() if x.filename=='utterances.jsonl']
            if len(names)!=1:raise ValueError('Expected exactly one source utterances member')
            with archive.open(names[0]) as stream:
                for line_number,line in enumerate(stream,1):
                    member_hash.update(line);row=json.loads(line);read_rows+=1
                    author=row.get('user')
                    if not isinstance(author,str) or author.casefold() not in wanted:continue
                    if row.get('root')==row.get('id'):continue
                    key=author.casefold();path=directory/(author_alias(key)+'.jsonl')
                    wrapper={'source_community':community,'source_line':line_number,'source_archive_sha256':spec['sha256'],'source_row':row}
                    with path.open('ab') as output:output.write(canonical_bytes(wrapper))
                    counts[key]+=1;kept+=1
        source_receipts.append({'community':community,'archive_sha256':spec['sha256'],'utterances_sha256':member_hash.hexdigest(),
                                'source_rows_read':read_rows,'candidate_comment_occurrences_spooled':kept})
    return counts,source_receipts


def record_groups(accounts,records,clusters=None):
    groups={'author':sorted(accounts),'related_sample':sorted(accounts)}
    for key,values in [('thread',{r['thread_id'] for r in records if r['thread_id']}),('source_document',{r['id'] for r in records})]:
        if values:groups[key]=sorted(values)
    if clusters:
        values={clusters[r['id']] for r in records if r['id'] in clusters}
        if values:groups['near_duplicate_cluster']=sorted(values)
    return groups


def write_snapshot(directory,case_id,records,*,constructed=False,account_alias=None):
    input_path=directory/(case_id+'.jsonl');manifest_path=directory/(case_id+'.snapshot.json')
    with input_path.open('xb') as f:
        for r in records:f.write(canonical_bytes(r))
    value=manifest(account_alias or (records[0]['account_id'] if records else case_id),records,constructed=constructed)
    write_json(manifest_path,value)
    return input_path,manifest_path


def one_stream_dataset(case_id,records_path,manifest_path,truth,groups,config_hash,annotation):
    result={'schema_version':'1.0.0','format':'account_stream','dataset_id':case_id,
        'provenance':'Frozen three-corpus local source comments; shared ConvoKit/Pushshift collection, not an independent-corpus replication.',
        'label_definition':annotation,'protocol':{'analysis_config_sha256':config_hash,'registered_before_evaluation':True,
            'preregistration_provenance':'Root protocol/plan.json, PROTOCOL.md and scoring-freeze.json bind this prepared one-case document before execution.',
            'boundary_tolerance_records':10},
        'streams':[{'stream_id':case_id,'input':records_path,'manifest':manifest_path,'split':'development','groups':groups,
                    'scope':SCOPE,'truth_boundaries':truth,'annotation_provenance':annotation}]}
    validate(result,'evaluation_account_stream');return result


def reject_confirmation_components(chosen,record_ids_by_author,audit,paired_rows):
    """Reject complete authors; components are inspected jointly, never purged."""
    if audit.get('status') not in {'ok','complete','audited'}:
        return {a['account_key']:['related_component_audit_incomplete'] for a in chosen}
    components=audit['components']
    confirmation_ids={r['id'] for r in paired_rows if r['split']=='confirmation'}
    component_confirmation=set()
    for component in components:
        members=set(component['record_ids'])
        if 'confirmation' in component['split_memberships'] or members & confirmation_ids:
            component_confirmation.update(members)
    return {author:['related_component_touches_confirmation'] for author,ids in record_ids_by_author.items() if set(ids)&component_confirmation}


def metadata_group_audit(chosen_records,paired_pool):
    """Full-history grouping overlaps, including unavailable source text."""
    paired={split:{'author':set(),'thread':set(),'source_document':set()} for split in ('development','evaluation','confirmation')}
    for row in paired_pool:
        record=row['record'];scope=paired[row['split']]
        scope['author'].add(row['account_key']);scope['source_document'].add(record['id'])
        if record['thread_id']:scope['thread'].add(record['thread_id'])
    result=[]
    for author,records in chosen_records.items():
        own={'author':{author},'thread':{r['thread_id'] for r in records if r['thread_id']},'source_document':{r['id'] for r in records}}
        result.append({'account_alias':author_alias(author),'missing_thread_records':sum(r['thread_id'] is None for r in records),
            'overlap_counts_by_paired_split':{split:{dimension:len(own[dimension]&sets[dimension]) for dimension in own} for split,sets in paired.items()}})
    return result


def verify_paired_pool(selection,pool_path):
    expected=selection.get('candidate_pool_sha256')
    if not isinstance(expected,str) or sha_file(pool_path)!=expected:
        raise ValueError('Paired protection pool does not match the complete selected-cohort hash')


def prepare(args):
    require_offline();root=args.root.resolve();out=root/'prepared/streams'
    if out.exists():raise ValueError('Never replace chronological preparation')
    protocol_path=root/'protocol/plan.json';protocol=json.loads(protocol_path.read_bytes())
    config,identity=check_current_release(protocol)
    selection=json.loads(args.exclude_cohort.read_bytes())
    verify_paired_pool(selection,args.paired_pool)
    paired_accounts=selection['accounts'];excluded={a['account_key'].casefold() for a in paired_accounts}
    paired_pool=list(load_jsonl(args.paired_pool))
    if any(r['account_key'].casefold() not in excluded for r in paired_pool):raise ValueError('Paired protection population is not bound to the selected cohort')
    if not any(r['split']=='confirmation' for r in paired_pool):raise ValueError('Missing confirmation protection population')
    frame_path=root/'inventory/private/source-frame.jsonl'
    candidates,metadata_exclusions=metadata_candidates(load_jsonl(frame_path),excluded)
    confirm_threads={r['record']['thread_id'] for r in paired_pool if r['split']=='confirmation' and r['record']['thread_id']}
    confirm_ids={r['record']['id'] for r in paired_pool if r['split']=='confirmation'}
    (root/'prepared').mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.streams-preparation-',dir=root/'prepared'))
    (staging/'private').mkdir();(staging/'accounts').mkdir();(staging/'cases').mkdir();(staging/'datasets').mkdir()
    chosen=[];chosen_records={};selection_audit=[];by_home=defaultdict(list);source_receipts=[]
    from account_history_analyzer.features import extract_records
    try:
        with tempfile.TemporaryDirectory(prefix='spool-',dir=staging/'private') as work:
            spool=Path(work);_,source_receipts=spool_candidates(root,protocol,candidates,spool)
            for candidate in candidates:
                key=candidate['account_key'];home=candidate['home_community'];alias=author_alias(key)
                audit={'account_alias':alias,'home_community':home,'rank_hash':candidate['rank_hash'],'metadata_comment_count':candidate['comment_count'],
                       'metadata_present_raw_codepoints':candidate['present_raw_codepoints'],'status':'excluded','reason_codes':[]}
                if len(by_home[home])>=4:
                    audit.update(status='not_selected',reason_codes=['home_slots_filled_by_earlier_hash_rank']);selection_audit.append(audit);continue
                wrappers=list(load_jsonl(spool/(alias+'.jsonl')));source_by_id={};records=[];source_map=[]
                for wrapper in wrappers:
                    row=wrapper['source_row'];record=convert(row,key)
                    if record['id'] in source_by_id:
                        if source_by_id[record['id']]!=record:raise ValueError('Conflicting duplicate source record')
                        continue
                    source_by_id[record['id']]=record;records.append(record)
                    source_map.append({'record_id':record['id'],'source_archive_sha256':wrapper['source_archive_sha256'],
                        'source_community':wrapper['source_community'],'source_line':wrapper['source_line'],
                        'source_text_sha256':hashlib.sha256(row['text'].encode()).hexdigest() if isinstance(row.get('text'),str) else None,
                        'status':record['status'],'source_timestamp':row.get('timestamp')})
                records.sort(key=record_sort_key)
                if not 200<=len(records)<=400:audit['reason_codes'].append('actual_unique_comment_count_outside_registered_guard')
                if any(r['id'] in confirm_ids for r in records):audit['reason_codes'].append('source_document_overlaps_confirmation')
                if any(r['thread_id'] in confirm_threads for r in records if r['thread_id']):audit['reason_codes'].append('thread_overlaps_confirmation')
                if audit['reason_codes']:selection_audit.append(audit);continue
                input_path,manifest_path=write_snapshot(spool,alias+'.converted',records)
                snap=load_snapshot(input_path,manifest_path,config);features=extract_records(snap,config)
                volume=word_eligibility(features,snap.records);audit.update(volume)
                if volume['eligible_words']<8000:
                    audit['reason_codes'].append('below_8000_eligible_retained_words');selection_audit.append(audit);continue
                accepted={**candidate,**volume,'account_alias':alias,'median_utc_us':median_instant(records)}
                chosen.append(accepted);by_home[home].append(accepted);chosen_records[key]=records
                audit['status']='provisionally_selected';selection_audit.append(audit)
                write_json(staging/'private'/(alias+'.source-map.json'),source_map)
        # Complete selected histories and the pre-purge paired population are
        # audited together. A three-author template may emerge only jointly.
        from leakage_audit import audit_records,audit_definition
        import leakage_audit
        flat_paired=[{'id':r['record']['id'],'text':r['record']['text'],'status':r['record']['status'],
                      'split':r['split'],'account_key':r['account_key']} for r in paired_pool]
        chrono=[{'id':r['id'],'text':r['text'],'status':r['status'],'split':'development','account_key':key,
                 'cohort_role':'chronological_exploratory'} for key,records in chosen_records.items() for r in records]
        try:
            joint=audit_records(flat_paired+chrono,max_candidate_pairs=2000000)
        except MemoryError:
            joint={'status':'not_auditable','excluded_ids':[],'cluster_by_id':{},'components':[],'relations':[],
                   'summary':{'status':'not_auditable','complete':False,'reason_codes':['address_space_limit_exhausted'],
                              'method':audit_definition(),'record_count':len(flat_paired)+len(chrono),
                              'candidate_pair_count':None,'max_candidate_pairs':2000000,'no_style_distances_calculated':True}}
        write_json(staging/'private/joint-related-audit.json',joint)
        rejected=reject_confirmation_components(chosen,{key:[r['id'] for r in records] for key,records in chosen_records.items()},joint,flat_paired)
        metadata_audit=metadata_group_audit(chosen_records,paired_pool)
        for entry in metadata_audit:
            if any(entry['overlap_counts_by_paired_split']['confirmation'].values()):
                key=next(k for k in chosen_records if author_alias(k)==entry['account_alias'])
                rejected.setdefault(key,[]).append('confirmation_metadata_overlap')
        final=[a for a in chosen if a['account_key'] not in rejected]
        final_keys={a['account_key'] for a in final}
        for row in selection_audit:
            if row['status']=='provisionally_selected':
                key=next(a['account_key'] for a in chosen if a['account_alias']==row['account_alias'])
                row['status']='selected' if key in final_keys else 'rejected_after_joint_audit_no_refill'
                row['reason_codes']=sorted(rejected.get(key,[]))
        clusters=joint.get('cluster_by_id',{})
        paired_id_split={r['record']['id']:r['split'] for r in paired_pool}
        chronological_id_author={r['id']:key for key,records in chosen_records.items() for r in records}
        component_overlap_counts={split:0 for split in ('development','evaluation','confirmation')}
        multiple_chronological_author_components=0
        for component in joint.get('components',[]):
            members=component['record_ids']
            author_keys={chronological_id_author[i] for i in members if i in chronological_id_author}
            if len(author_keys)>1:multiple_chronological_author_components+=1
            if author_keys:
                for split in {paired_id_split[i] for i in members if i in paired_id_split}:component_overlap_counts[split]+=1
        chrono_threads=defaultdict(set)
        for key,records in chosen_records.items():
            for record in records:
                if record['thread_id']:chrono_threads[record['thread_id']].add(key)
        groups={'status':'exploratory_not_independent_heldout','confirmation_protection_status':'observed_related_groups_audited' if joint.get('status') in {'ok','complete','audited'} else 'not_auditable',
            'joint_related_audit_sha256':sha_file(staging/'private/joint-related-audit.json'),
            'joint_audit_helper_sha256':sha_file(leakage_audit.__file__),'joint_candidate_pair_cap':2000000,
            'metadata_overlap_audit':metadata_audit,'related_components_touching_chronology_by_paired_split':component_overlap_counts,
            'related_components_with_multiple_chronological_authors':multiple_chronological_author_components,
            'threads_shared_by_multiple_chronological_authors':sum(len(keys)>1 for keys in chrono_threads.values()),
            'content_unobservable_record_count':sum(r['text'] is None for rows in chosen_records.values() for r in rows),
            'missing_thread_record_count':sum(r['thread_id'] is None for rows in chosen_records.values() for r in rows),
            'unverified_relations':['Unavailable source prose cannot be checked for content relations.','Missing thread metadata cannot establish thread disjointness.','Unmarked/indirect quotation and natural-person identity remain unverified.'],
            'rejected_author_count':len(rejected),
            'rejected_accounts':[{'account_alias':author_alias(k),'reason_codes':sorted(v)} for k,v in sorted(rejected.items())],
            'missing_metadata_policy':'Missing thread or unavailable source prose is reported as unauditable for that dimension; no natural-person or unmarked-quotation inference.',
            'population':'Complete provisional chronological histories jointly with pre-purge selected paired pool including confirmation.',
            'shared_collection':'All groups share the ConvoKit/Pushshift source collection; not independent corpus replications.',
            'paired_pool_sha256':sha_file(args.paired_pool),'selected_paired_cohort_sha256':sha_file(args.exclude_cohort),
            'chronological_input_split_in_joint_audit':'development with chronological_exploratory metadata; no scores computed'}
        write_json(staging/'group-audit.json',groups)
        # Planned slots survive any exclusion/purge. No author refill is allowed.
        all_cases=[];operational_views=[];pairings=[];unfilled=[];natural_used=set()
        config_hash=canonical_digest(config.analytical())
        for home in COMMUNITIES:
            eligible=[a for a in final if a['home_community']==home]
            pairs,leftovers=pair_closest(eligible)
            unfilled.append({'home_community':home,'planned_authors':4,'selected_authors':len(eligible),
                             'unfilled_author_slots':4-len(eligible),'planned_source_pairs':2,'formed_pairs':len(pairs),
                             'unpaired_selected_author_count':len(leftovers)})
            for pair_index in range(2):
                pair_id='chrono-'+home+'-pair'+str(pair_index+1)
                if pair_index>=len(pairs):
                    for kind in ('splice','continuity_proxy'):
                        for arm in ARMS:all_cases.append({'case_id':pair_id+'-'+kind+'-'+arm,'pair_id':pair_id,'home_community':home,
                            'case_type':kind,'arm':arm,'preparation_status':'unfilled_slot','reason_codes':['insufficient_selected_disjoint_source_accounts'],
                            'execution_mode':None,'input':None,'manifest':None,'dataset':None,'truth_boundaries':None})
                    continue
                a,b=pairs[pair_index];aa=chosen_records[a['account_key']];bb=chosen_records[b['account_key']]
                pairings.append({'pair_id':pair_id,'home_community':home,'source_account_aliases':[a['account_alias'],b['account_alias']],
                    'median_timestamp_gap_microseconds':abs(a['median_utc_us']-b['median_utc_us']) if a['median_utc_us'] is not None and b['median_utc_us'] is not None else None})
                for item,records in ((a,aa),(b,bb)):
                    write_snapshot(staging/'accounts',item['account_alias'],records)
                construction=construct(aa,bb,pair_id+'-constructed')
                for kind,base in (('splice',construction['records']),('continuity_proxy',aa)):
                    for arm in ARMS:
                        case_id=pair_id+'-'+kind+'-'+arm
                        case={'case_id':case_id,'pair_id':pair_id,'home_community':home,'case_type':kind,'arm':arm,
                              'exploratory_not_independent_heldout':True,'source_account_count':2 if kind=='splice' else 1}
                        if kind=='splice' and construction['status']!='constructed':
                            case.update(preparation_status='not_constructible',reason_codes=construction['reason_codes'],execution_mode=None,
                                        input=None,manifest=None,dataset=None,truth_boundaries=None);all_cases.append(case);continue
                        records=arm_records(base,arm)
                        truth=surviving_truth(records,construction['source_sides']) if kind=='splice' else {'status':'account_id_continuity_proxy','reason_codes':[],'truth_boundaries':[]}
                        ip,mp=write_snapshot(staging/'cases',case_id,records,constructed=kind=='splice',account_alias=base[0]['account_id'])
                        # An absent source side is still analyzable for module
                        # availability, but cannot be labeled unchanged.
                        mode='evaluate' if truth['truth_boundaries'] is not None else 'analyze_unknown_truth'
                        annotation=('Known evaluator source-account reassignment only, not verified human authorship or takeover.' if kind=='splice' else
                                    'Empty truth denotes source-account-ID continuity only; it does NOT establish stable human authorship or no natural stylistic changes.')
                        gp=record_groups([a['account_alias'],b['account_alias']] if kind=='splice' else [a['account_alias']],records,clusters)
                        dataset_path=staging/'datasets'/(case_id+'.json') if mode=='evaluate' else None
                        if dataset_path:write_json(dataset_path,one_stream_dataset(case_id,'../cases/'+ip.name,'../cases/'+mp.name,truth['truth_boundaries'],gp,config_hash,annotation))
                        original={r['id']:i for i,r in enumerate(base)}
                        mapping=[{'record_id':r['id'],'surviving_ordinal':i,'full_original_ordinal':original[r['id']],
                                  'source_side':construction['source_sides'][r['id']] if kind=='splice' else 'one_source_account'} for i,r in enumerate(records)]
                        write_json(staging/'private'/(case_id+'.ordinal-map.json'),mapping)
                        case.update(preparation_status=truth['status'],reason_codes=truth['reason_codes'],execution_mode=mode,
                            input=str(ip.relative_to(staging)),manifest=str(mp.relative_to(staging)),dataset=str(dataset_path.relative_to(staging)) if dataset_path else None,
                            truth_boundaries=truth['truth_boundaries'],record_count=len(records),full_record_count=len(base),
                            missing_records=len(base)-len(records),status_counts=dict(sorted(Counter(r['status'] for r in records).items())),
                            cut_utc=construction['cut_utc'] if kind=='splice' else None,
                            unchanged_surviving_record_check=all(r==base[original[r['id']]] for r in records),groups=gp)
                        all_cases.append(case)
                if home not in natural_used:
                    natural_used.add(home);case_id=pair_id+'-unknown-natural-full'
                    all_cases.append({'case_id':case_id,'pair_id':pair_id,'home_community':home,'case_type':'unknown_truth_natural','arm':'full',
                        'preparation_status':'unknown_truth','reason_codes':[],'execution_mode':'analyze_unknown_truth','dataset':None,
                        'input':'accounts/'+a['account_alias']+'.jsonl','manifest':'accounts/'+a['account_alias']+'.snapshot.json','truth_boundaries':None,
                        'record_count':len(aa),'shared_input_with_case':pair_id+'-continuity_proxy-full',
                        'dependence_note':'Same A-account input as the proxy control; reused measurement view, not an independent source account or case.'})
                    for omission in ARMS[1:]:
                        control=next(c for c in all_cases if c['case_id']==pair_id+'-continuity_proxy-'+omission)
                        operational_views.append({'case_id':pair_id+'-operational-availability-'+omission,'pair_id':pair_id,'home_community':home,
                            'case_type':'operational_module_availability_only','arm':omission,'preparation_status':'unknown_truth',
                            'reason_codes':[],'execution_mode':'analyze_unknown_truth','dataset':None,'input':control['input'],'manifest':control['manifest'],
                            'truth_boundaries':None,'record_count':control['record_count'],'shared_input_with_case':control['case_id'],
                            'scientific_sample_count_increment':0,'dependence_note':'Operational omission availability of the same preregistered natural-history source; not a new independent scientific view or subject.'})
            if home not in natural_used:
                all_cases.append({'case_id':'chrono-'+home+'-unknown-natural-full','home_community':home,'case_type':'unknown_truth_natural','arm':'full',
                    'preparation_status':'unfilled_slot','reason_codes':['no_A_control_available'],'execution_mode':None,'input':None,'manifest':None,'dataset':None,'truth_boundaries':None})
                for omission in ARMS[1:]:
                    operational_views.append({'case_id':'chrono-'+home+'-operational-availability-'+omission,'home_community':home,
                        'case_type':'operational_module_availability_only','arm':omission,'preparation_status':'unfilled_slot',
                        'reason_codes':['no_A_control_available'],'execution_mode':None,'input':None,'manifest':None,'dataset':None,
                        'truth_boundaries':None,'scientific_sample_count_increment':0})
        plan={'protocol_id':protocol['protocol_id'],'preparation_status':'prepared_not_scored','scoring_executed':False,
            'source_identity':identity,'protocol_plan_sha256_at_preparation':sha_file(protocol_path),'analysis_config_sha256':config_hash,
            'source_frame_sha256':sha_file(frame_path),'source_archives':source_receipts,
            'selected_paired_cohort_sha256':sha_file(args.exclude_cohort),'paired_pool_sha256':sha_file(args.paired_pool),
            'group_audit_sha256':sha_file(staging/'group-audit.json'),'metadata_exclusion_counts':metadata_exclusions,
            'metadata_candidates':len(candidates),'provisional_source_accounts':len(chosen),'final_source_accounts':len(final),
            'unfilled_slots':unfilled,'pairings':pairings,'cases':all_cases,'operational_availability_views':operational_views,'max_concurrent_execution':2,
            'scoring_gate':'Separate matching root scoring-freeze.json is mandatory; preparation never invokes an optimizer or output-grid calculation.',
            'pairing_tie_rule':'Greedy minimum absolute upper-median timestamp gap, pair hash tie; pair orientation by fixed author orientation hash.',
            'home_tie_rule':'Lexicographic source community among equal maximum all-archive present raw codepoint totals.',
            'construction_missing_timestamp_policy':'Any missing source timestamp makes that source-pair construction unavailable; whole account controls remain unchanged.',
            'conversion_policy':'Present source prose, IDs and timestamp instants are preserved. Deleted/removed/unavailable bodies are null in the strict input contract; their unchanged original archive row, line locator and source-text hash remain in private provenance. No records are silently removed.',
            'no_refill_after_joint_audit':True}
        write_json(staging/'private/selection-audit.json',selection_audit)
        write_json(staging/'private/selected-accounts.json',{'provisional':chosen,'accepted':final})
        plan['inputs_sha256']={str(p.relative_to(staging)):sha_file(p) for directory in ('accounts','cases','datasets') for p in sorted((staging/directory).glob('*')) if p.is_file()}
        write_json(staging/'stream-plan.json',plan)
        write_json(staging/'files-sha256.json',{str(p.relative_to(staging)):sha_file(p) for p in sorted(staging.rglob('*')) if p.is_file()})
        staging.rename(out)
        print(json.dumps({'status':'prepared_not_scored','metadata_candidates':len(candidates),'provisional_source_accounts':len(chosen),
                          'final_source_accounts':len(final),'formed_pairs':len(pairings),'planned_case_count':len(all_cases),'unfilled_slots':unfilled,
                          'stream_plan_sha256':sha_file(out/'stream-plan.json'),'group_audit_sha256':sha_file(out/'group-audit.json')},sort_keys=True))
    except Exception:
        # Keep failed preparation for inspection. Do not let it masquerade as a
        # frozen cohort or replace it silently on a subsequent attempt.
        write_json(staging/'PREPARATION_FAILED.json',{'status':'failed_not_scored','scoring_executed':False})
        raise


def guarded_path(base,relative):
    path=base/relative
    if path.is_symlink() or not path.resolve().is_relative_to(base.resolve()):raise ValueError('Prepared path escapes the fixed input subtree')
    if any(p.is_symlink() for p in path.parents if p!=base.parent):raise ValueError('Symlinked prepared path')
    return path


def verify_frozen_files(root,file_map):
    if not isinstance(file_map,dict) or not file_map:raise ValueError('Missing complete source/script/input freeze map')
    for relative,expected in file_map.items():
        if not isinstance(relative,str) or not isinstance(expected,str):raise ValueError('Invalid source freeze entry')
        if sha_file(guarded_path(root,relative))!=expected:raise ValueError('A frozen study source/script/input file changed')


def verify_scoring_freeze(root,freeze_path):
    """Fail closed before any analysis, including diagnostics, can be imported."""
    freeze=json.loads(freeze_path.read_bytes())
    if freeze.get('status')!='frozen' or freeze.get('scoring_authorized') is not True:
        raise ValueError('Root scoring authorization is absent; preparation is not authorization')
    required={'scripts/prepare_streams.py','scripts/check_old_grid.py','scripts/leakage_audit.py',
              'prepared/streams/stream-plan.json','prepared/streams/group-audit.json'}
    if not required<=freeze.get('files',{}).keys():raise ValueError('Required study scripts or preparation artifacts are absent from the source freeze')
    verify_frozen_files(root,freeze['files'])
    streams=root/'prepared/streams';plan_path=streams/'stream-plan.json';group_path=streams/'group-audit.json'
    protocol_path=root/'protocol/plan.json';protocol=json.loads(protocol_path.read_bytes())
    config,identity=check_current_release(protocol)
    expected={'stream_plan_sha256':sha_file(plan_path),'stream_group_audit_sha256':sha_file(group_path),
        'analysis_config_sha256':canonical_digest(config.analytical()),'implementation_fingerprint':identity['implementation_fingerprint'],
        'protocol_plan_sha256':sha_file(protocol_path)}
    if any(freeze.get(k)!=v for k,v in expected.items()):raise ValueError('Frozen protocol/source/prepared identities do not match')
    plan=json.loads(plan_path.read_bytes())
    if plan.get('scoring_executed') is not False:raise ValueError('Prepared plan is not a pre-score document')
    for relative,digest in plan['inputs_sha256'].items():
        if sha_file(guarded_path(streams,relative))!=digest:raise ValueError('A frozen prepared input changed')
    return plan,config,freeze


def post_execution_grid(case,streams,output,config):
    """Post-score fixed diagnostics only; never used to choose source accounts."""
    from account_history_analyzer.features import extract_records
    from check_old_grid import independent_windows,legal_grid,interval_error
    from account_history_analyzer.windows import build_streams
    from check_old_grid import check_memberships
    snapshot=load_snapshot(guarded_path(streams,case['input']),guarded_path(streams,case['manifest']),config)
    features=extract_records(snapshot,config)
    windows=independent_windows(features)
    production=next(s for s in build_streams(features,config)['streams'] if s['scope_type']=='pooled' and s['kind']=='comment')
    check_memberships(windows,production['windows'])
    n=sum(w['qualified'] for w in windows);adequate=n>=8
    grid=legal_grid(windows,3) if adequate else []
    truth=case['truth_boundaries'];observed=None;change_status=None;scope_status=None
    if case['execution_mode']=='evaluate':
        result=json.loads((output/'evaluation.json').read_bytes())
        rows=[r for p in result['partitions'].values() for r in p['rows']]
        if len(rows)!=1:raise ValueError('Expected one whole-history evaluator case')
        row=rows[0];change_status=row['change_status'];scope_status=row['status']
        if row['status']=='ok':observed=row['candidate_intervals']
    else:
        result=json.loads((output/'results.json').read_bytes());style=result['modules']['style']['payload']
        stream=next(s for s in style['streams'] if s['scope_type']=='pooled' and s['kind']=='comment')
        change=next(r for r in style['changes'] if r['stream_id']==stream['stream_id'])
        change_status=change['status'];scope_status=change['status']
        if change['status'] in {'ok','no_measurable_variation'}:
            observed=[[b['record_interval'][0]+1,b['record_interval'][1]] for b in change['boundaries']]
    measurable=observed is not None
    result={'case_id':case['case_id'],'coordinate_definition':'Inclusive split interval [last eligible left original ordinal + 1, first eligible right original ordinal] in each surviving canonical snapshot.',
        'qualified_windows':n,'input_adequate':adequate,'analysis_scope_status':scope_status,'change_status':change_status,
        'candidate_measurement_available':measurable,'has_candidate':bool(observed) if measurable else None,
        'candidate_intervals':observed,'truth_boundaries':truth,'registered_tolerance_records':10,
        'independent_vs_production_window_memberships':'passed','legal_boundaries':grid,
        'best_legal_grid_error':None,'nearest_candidate_error_original_ordinals':None,'excess_error_over_grid':None,
        'tolerance_attainable':None,'matched_at_original_tolerance':None,
        'insufficient_input':not adequate,'adequate_no_candidate':adequate and measurable and not observed,
        'off_target_candidate':None,'grid_unattainable':None,
        'label_note':'Source-account construction or continuity proxy only. Unknown truth is not changed to an empty truth array.'}
    if truth and len(truth)==1:
        point=truth[0];errors=[interval_error(r['split_interval'],point) for r in grid]
        best=min(errors) if errors else None
        candidate_errors=[interval_error(r,point) for r in observed] if measurable else None
        closest=min(candidate_errors) if candidate_errors else None
        result.update(best_legal_grid_error=best,nearest_candidate_error_original_ordinals=closest,
            candidate_errors_original_ordinals=candidate_errors,
            excess_error_over_grid=closest-best if closest is not None and best is not None else None,
            tolerance_attainable=best<=10 if best is not None else None,
            matched_at_original_tolerance=any(x<=10 for x in candidate_errors) if measurable else None,
            off_target_candidate=bool(candidate_errors) and closest>10 if measurable else None,
            grid_unattainable=best>10 if best is not None else None)
    return result


def run_case(args):
    require_offline();root=args.root.resolve();streams=root/'prepared/streams'
    plan,config,freeze=verify_scoring_freeze(root,args.freeze)
    cases=[c for c in plan['cases']+plan.get('operational_availability_views',[]) if c['case_id']==args.case]
    if len(cases)!=1:raise ValueError('Exactly one registered case must be selected')
    case=cases[0];output=args.out.resolve()
    if output.exists():raise ValueError('Never overwrite a prior analysis or operational receipt')
    if output.is_relative_to(streams) or streams.is_relative_to(output):raise ValueError('Output must be separate from frozen inputs')
    operational=output.parent/(output.name+'.operation')
    if operational.exists():raise ValueError('Never replace a prior operational receipt')
    operational.mkdir(parents=True)
    receipt={'case_id':case['case_id'],'freeze_sha256':sha_file(args.freeze),'registered_preparation_status':case['preparation_status'],
             'network_isolation':os.environ['AHAS_NETWORK_ISOLATION'],'command':None,'exit_code':None,'status':'not_executed'}
    if case['execution_mode'] is None:
        receipt['reason_codes']=case['reason_codes'];write_json(operational/'run.json',receipt)
        print(json.dumps({'case_id':case['case_id'],'status':'not_executed','reason_codes':case['reason_codes']},sort_keys=True));return 0
    # One invocation, one unchanged whole-history input. The parent may schedule
    # at most two invocations concurrently; this driver never starts a batch.
    if case['execution_mode']=='evaluate':
        argv=[sys.executable,'-B','-m','account_history_analyzer','evaluate','--suite','account_stream','--dataset',str(guarded_path(streams,case['dataset'])),'--out',str(output)]
    else:
        argv=[sys.executable,'-B','-m','account_history_analyzer','analyze','--input',str(guarded_path(streams,case['input'])),
              '--manifest',str(guarded_path(streams,case['manifest'])),'--out',str(output)]
    receipt['command']=argv
    with (operational/'stdout.log').open('xb') as o,(operational/'stderr.log').open('xb') as e:
        process=subprocess.run(argv,cwd=root,stdout=o,stderr=e)
    receipt.update(exit_code=process.returncode,status='executed' if process.returncode==0 else 'resource_limit' if process.returncode==4 else 'failed')
    receipt.update(stdout_sha256=sha_file(operational/'stdout.log'),stderr_sha256=sha_file(operational/'stderr.log'))
    if process.returncode in {0,4} and output.exists():
        diagnostic=post_execution_grid(case,streams,output,config)
        write_json(operational/'grid-diagnostic.json',diagnostic)
    write_json(operational/'run.json',receipt)
    print(json.dumps({'case_id':case['case_id'],'status':receipt['status'],'exit_code':process.returncode},sort_keys=True))
    return process.returncode


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--root',type=Path,required=True);prep.add_argument('--exclude-cohort',type=Path,required=True);prep.add_argument('--paired-pool',type=Path,required=True)
    run=sub.add_parser('run-case');run.add_argument('--root',type=Path,required=True);run.add_argument('--freeze',type=Path,required=True);run.add_argument('--case',required=True);run.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    try:return prepare(args) if args.command=='prepare' else run_case(args)
    except Exception as exc:
        # Detailed failures remain private if invoked through run_recorded.py.
        print(json.dumps({'status':'failed','error_type':type(exc).__name__,'error':str(exc)}),file=sys.stderr)
        return 1

if __name__=='__main__':raise SystemExit(main())
