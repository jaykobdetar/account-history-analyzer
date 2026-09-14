#!/usr/bin/env python3
"""Metadata-only streaming frame for explicitly authorized local corpora.

Raw text is used only for present/sentinel classification and codepoint length,
then released. No preprocessing, lexical features, similarities or scores run.
"""
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib,json,os,resource,sys,time,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'ahas-realworld-review'
PLACEHOLDERS={'','anonymous','[anonymous]','unknown','[unknown]','[deleted]','[removed]','[missing]'}


def canonical(value):return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def sha(path):
    with Path(path).open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()


def utc(value):
    if type(value) is not int:return None
    try:return datetime.fromtimestamp(value,timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    except (ValueError,OverflowError,OSError):return None


def zero_year():return {'comment_count':0,'present_comment_count':0,'present_raw_codepoints':0,'timestamped_present_comment_count':0}


def main():
    if os.environ.get('AHAS_NETWORK_ISOLATION')!='linux_seccomp_socket_denial':raise RuntimeError('Kernel network isolation required')
    started=time.monotonic();out=ROOT/'inventory';private=out/'private';private.mkdir(exist_ok=True,mode=0o700)
    frame_path=private/'source-frame.jsonl';summary_path=out/'source-frame-summary.json'
    if frame_path.exists() or summary_path.exists():raise RuntimeError('Refuse to overwrite inventory frame')
    old_map_path=OLD/'inputs/public/source-map.json';old_map=json.loads(old_map_path.read_bytes())
    old_accounts={row['source_account'].casefold() for row in old_map['accounts']}
    sources=[]
    for name in ('ApplyingToCollege','Cornell','college'):
        if name=='Cornell':
            path=OLD/'inputs/Cornell.corpus.zip';expected='f153a56a343e6d9568d90b635d44d1ccca71479ac19cd28e075587485bad715d'
        else:
            path=ROOT/f'data/{name}.corpus.zip';expected=json.loads((out/f'{name}-acquisition.json').read_bytes())['sha256']
        if sha(path)!=expected:raise RuntimeError('Acquisition SHA mismatch: '+name)
        sources.append((name,path,expected))
    global_ids=set();summaries=[];account_communities=defaultdict(set);frame_rows=0
    with frame_path.open('xb') as frame:
        for name,path,archive_hash in sources:
            source_started=time.monotonic();counts=Counter();fields=Counter();meta_fields=Counter();years=Counter();communities=Counter()
            ids=set();parent_refs=set();thread_refs=set();authors={};seen_duplicate_ids=Counter();utterances_hash=hashlib.sha256()
            first=None;last=None
            with zipfile.ZipFile(path) as archive:
                members=[entry for entry in archive.infolist() if entry.filename=='utterances.jsonl']
                if len(members)!=1:raise RuntimeError('Expected one utterances.jsonl member: '+name)
                with archive.open(members[0]) as source:
                    for line in source:
                        utterances_hash.update(line);row=json.loads(line);counts['rows']+=1
                        fields[tuple(sorted(row))]+=1;meta=row.get('meta') or {};meta_fields.update(meta.keys())
                        identifier=row.get('id');parent=row.get('reply_to');thread=row.get('root');account=row.get('user')
                        instant=utc(row.get('timestamp'));year=instant[:4] if instant else 'missing';years[year]+=1
                        counts['missing_timestamp']+=instant is None
                        counts['missing_thread']+=not thread
                        counts['missing_speaker']+=not isinstance(account,str) or not account.strip()
                        counts['missing_id']+=not isinstance(identifier,str) or not identifier
                        counts['explicit_language_missing']+='language' not in row and 'language' not in meta
                        counts['explicit_edit_history_missing']+='edit_state' not in row and 'edit_state' not in meta
                        counts['explicit_near_duplicate_cluster_missing']+='near_duplicate_cluster' not in row and 'near_duplicate_cluster' not in meta
                        if instant:first=instant if first is None else min(first,instant);last=instant if last is None else max(last,instant)
                        community=meta.get('subreddit');communities[str(community)]+=1
                        if parent is not None:parent_refs.add(parent)
                        if thread:thread_refs.add(thread)
                        if identifier in ids:
                            seen_duplicate_ids[identifier]+=1;counts['duplicate_id_occurrences']+=1
                            continue
                        ids.add(identifier)
                        counts['id_previously_seen_in_another_corpus']+=identifier in global_ids
                        kind='submission' if thread==identifier else 'comment';counts[kind+'s']+=1
                        counts['submission_parent_classification_disagreements']+=(thread==identifier)!=(parent is None)
                        if kind!='comment':continue
                        counts['comments_missing_parent']+=parent is None
                        text=row.get('text');state=('unavailable' if text is None else 'invalid_nonstring' if not isinstance(text,str) else {'[removed]':'removed','[deleted]':'deleted'}.get(text.strip(),'present'))
                        counts['comment_status_'+state]+=1
                        if not isinstance(account,str):continue
                        exclusion=('placeholder_account' if account.strip().casefold() in PLACEHOLDERS else
                                   'automoderator_account' if account.casefold()=='automoderator' else
                                   'old_pilot_account' if account.casefold() in old_accounts else None)
                        if exclusion:counts['excluded_comments_'+exclusion]+=1
                        key=(account,community)
                        if key not in authors:
                            authors[key]={'source_archive_sha256':archive_hash,'source_community':name,'community':community,
                                'source_account':account,'excluded_from_new_sampling':exclusion,'comment_count':0,
                                'present_comment_count':0,'present_raw_codepoints':0,'first_comment_utc':None,'last_comment_utc':None,
                                'missing_thread_comment_count':0,'years':defaultdict(zero_year)}
                        entry=authors[key];entry['comment_count']+=1;entry['years'][year]['comment_count']+=1
                        entry['missing_thread_comment_count']+=not thread
                        if instant:
                            entry['first_comment_utc']=instant if entry['first_comment_utc'] is None else min(entry['first_comment_utc'],instant)
                            entry['last_comment_utc']=instant if entry['last_comment_utc'] is None else max(entry['last_comment_utc'],instant)
                        if state=='present':
                            entry['present_comment_count']+=1;entry['present_raw_codepoints']+=len(text)
                            period=entry['years'][year];period['present_comment_count']+=1;period['present_raw_codepoints']+=len(text)
                            period['timestamped_present_comment_count']+=instant is not None
                            counts['comments_preprocessable_in_cornell_inventory']+=1
                        if not exclusion:account_communities[account.casefold()].add(name)
            for key in sorted(authors,key=lambda pair:(pair[0],str(pair[1]))):
                frame.write(canonical(authors[key]));frame_rows+=1
            available=[row for row in authors.values() if row['excluded_from_new_sampling'] is None]
            annual={}
            for year in ('2016','2017','2018'):
                periods=[row['years'].get(year,zero_year()) for row in available]
                annual[year]={'additional_accounts_with_comments':sum(period['comment_count']>0 for period in periods),
                    'additional_present_comments':sum(period['present_comment_count'] for period in periods),
                    'additional_present_raw_codepoints':sum(period['present_raw_codepoints'] for period in periods),
                    'accounts_with_at_least_50_present_comments':sum(period['present_comment_count']>=50 for period in periods),
                    'accounts_with_at_least_100_present_comments':sum(period['present_comment_count']>=100 for period in periods)}
            summaries.append({'community':name,'archive_sha256':archive_hash,'archive_bytes':path.stat().st_size,
                'utterances_sha256':utterances_hash.hexdigest(),'utterances_bytes':members[0].file_size,'counts':dict(sorted(counts.items())),
                'unique_record_ids':len(ids),'duplicated_id_count':len(seen_duplicate_ids),
                'unique_missing_parent_references':len(parent_refs-ids),'unique_missing_thread_references':len(thread_refs-ids),
                'source_field_patterns':[{'fields':list(field),'rows':count} for field,count in sorted(fields.items())],
                'source_meta_field_presence':dict(sorted(meta_fields.items())),'community_labels':dict(sorted(communities.items())),
                'calendar_year_counts':dict(sorted(years.items())),'first_utc':first,'last_utc':last,
                'additional_account_community_keys':len(available),'calendar_metadata_capacity':annual,
                'scan_seconds_operational':time.monotonic()-source_started})
            global_ids.update(ids)
            # Release source graph/metadata before reading the next large ZIP.
            del ids,parent_refs,thread_refs,authors,available
    frame_path.chmod(0o600)
    pair_overlaps={a+' / '+b:sum(a in groups and b in groups for groups in account_communities.values())
                   for a,b in [('ApplyingToCollege','Cornell'),('ApplyingToCollege','college'),('Cornell','college')]}
    timing=[{'community':row['community'],'scan_seconds':row.pop('scan_seconds_operational')} for row in summaries]
    summary={'scope':'Pre-score metadata-only inventory of authorized local Cornell/ApplyingToCollege/college source corpora.',
        'source_prose_exported':False,'text_preprocessing_executed':False,'style_scores_computed':False,'held_out_cohort_selected':False,
        'old_source_map_sha256':sha(old_map_path),'old_accounts_excluded_case_insensitively':len(old_accounts),
        'sources':summaries,'restricted_frame_rows':frame_rows,'restricted_frame_sha256':sha(frame_path),
        'additional_account_keys_casefolded':len(account_communities),'account_keys_observed_in_multiple_sources':sum(len(groups)>1 for groups in account_communities.values()),
        'source_pair_account_overlaps_casefolded':pair_overlaps,
        'limitations':['Raw source codepoints include markup, quotations, links, numbers and ineligible short comments; they do not establish retained-word eligibility.',
            'Account keys may denote shared/automated accounts or multiple accounts per person; no stronger authorship labels are created.',
            'Duplicate IDs are counted, not resolved here; conflicting duplicate content is not adjudicated by this metadata-only pass.',
            'Exact topic, natural-person identity, language, edit history, and near-duplicate/template grouping remain unverified.',
            'Observed calendar bounds are incomplete historical source coverage, not complete account histories.',
            'The old-pilot account exclusion is case-insensitive for conservative cross-corpus separation; frame retains original account spelling.']}
    summary_path.write_bytes(canonical(summary))
    receipt={'argv':sys.argv,'script_sha256':sha(__file__),'network_isolation':os.environ['AHAS_NETWORK_ISOLATION'],
        'wall_seconds':time.monotonic()-started,'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        'per_source_operational':timing,'frame_bytes':frame_path.stat().st_size,'summary_bytes':summary_path.stat().st_size}
    (out/'source-frame.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'status':'inventoried','source_count':len(sources),'frame_rows':frame_rows,'resources':receipt}))


if __name__=='__main__':main()
