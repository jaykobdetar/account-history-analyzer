#!/usr/bin/env python3
"""Inventory authorized local Cornell volume; never select a cohort or score style.

Call through the frozen repository's scripts/offline_exec.py. Only the existing
Cornell archive, old cohort, and source map are read. No source prose is exported.
"""
from __future__ import annotations

import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time
import unicodedata
import zipfile

from account_history_analyzer import __version__
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import canonical_bytes,digest
from account_history_analyzer.pipeline import implementation_identity
from account_history_analyzer.text import preprocess

ROOT=Path(__file__).resolve().parents[1]
PREVIOUS=ROOT.parent/'ahas-realworld-review'
ARCHIVE=PREVIOUS/'inputs/Cornell.corpus.zip'
EXPECTED_ARCHIVE='f153a56a343e6d9568d90b635d44d1ccca71479ac19cd28e075587485bad715d'
EXPECTED_UTTERANCES='e22f4c69d2a39de40b38ddb13bfecf000b3f82a9a5823e0395e1d5d408a541f9'
YEARS=('2016','2017','2018')
PLACEHOLDERS={'','anonymous','[anonymous]','unknown','[unknown]','[deleted]','[removed]','[missing]'}


def hash_file(path):
    with Path(path).open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()


def alias(account):return 'inventory-'+hashlib.sha256(('ahas-pilot2-inventory:'+account).encode()).hexdigest()[:20]


def timestamp(value):
    if type(value) is not int:return None
    try:return datetime.fromtimestamp(value,timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    except (ValueError,OverflowError,OSError):return None


def status(text):
    if text is None:return 'unavailable'
    if not isinstance(text,str):return 'invalid_nonstring'
    return {'[removed]':'removed','[deleted]':'deleted'}.get(text.strip(),'present')


def windows(records,target,minimum):
    """Planning capacity on whole eligible records; no text features are pooled."""
    closed=[];buffer=[];words=0
    for row in records:
        buffer.append(row);words+=row['retained_words']
        if len(buffer)>=minimum and words>=target:
            closed.append({'record_count':len(buffer),'word_count':words,'overshoot_words':words-target,
                'largest_record_share':max(r['retained_words'] for r in buffer)/words,
                'first_utc':buffer[0]['created_utc'],'last_utc':buffer[-1]['created_utc'],
                'first_record_id':buffer[0]['record_id'],'last_record_id':buffer[-1]['record_id']})
            buffer=[];words=0
    return {'qualified_unit_count':len(closed),'qualified_units':closed,
            'remainder_records':len(buffer),'remainder_words':words}


def distribution(values):
    values=sorted(values)
    if not values:return {'count':0,'minimum':None,'median':None,'maximum':None,'total':0}
    middle=len(values)//2
    return {'count':len(values),'minimum':values[0],
            'median':values[middle] if len(values)%2 else (values[middle-1]+values[middle])/2,
            'maximum':values[-1],'total':sum(values)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'inventory/cornell',help='New directory; existing output is refused.')
    args=parser.parse_args()
    if args.out.exists():parser.error('Output exists; preserve it and choose a new directory.')
    started=time.monotonic();phases={}
    if os.environ.get('AHAS_NETWORK_ISOLATION')!='linux_seccomp_socket_denial':
        raise RuntimeError('Run inventory through scripts/offline_exec.py; network isolation is required.')
    archive_sha=hash_file(ARCHIVE)
    if archive_sha!=EXPECTED_ARCHIVE:raise RuntimeError('Authorized archive hash mismatch')
    old_cohort_path=PREVIOUS/'protocol/cohort.json';old_map_path=PREVIOUS/'inputs/public/source-map.json'
    old_cohort=json.loads(old_cohort_path.read_bytes());old_map=json.loads(old_map_path.read_bytes())
    excluded={account['source_account'] for account in old_map['accounts']}
    assert len(excluded)==len(old_cohort['accounts'])==12
    config=AnalysisConfig.from_toml();fp,environment,resources=implementation_identity()
    minimum_words=config['style']['minimum_record_words'];minimum_records=config['windows']['minimum_records']
    target=config['windows']['target_words'];minimum_windows=config['changes']['minimum_windows']
    assert (minimum_words,minimum_records,target,minimum_windows)==(20,8,1000,8)
    phases['input_identity_seconds']=time.monotonic()-started
    source_counts=Counter();missing=Counter();field_patterns=Counter();meta_fields=Counter();communities=Counter()
    source_statuses=Counter();source_years=Counter();exclusions=Counter();account_rows=defaultdict(list)
    ids={};duplicate_ids=Counter();conflicting_ids=set();parents=[];named_accounts=set();all_root_ids=set()
    raw_text_hashes=defaultdict(set);retained_hashes=defaultdict(set);duplicate_text_occurrences=Counter()
    minimum_time=None;maximum_time=None;utterance_hash=hashlib.sha256();preprocessing_seconds=0.0
    with zipfile.ZipFile(ARCHIVE) as archive:
        entries=archive.infolist()
        matches=[entry for entry in entries if entry.filename=='utterances.jsonl']
        if len(matches)!=1:raise RuntimeError('Expected one exact utterances.jsonl member')
        member_inventory=[{'name':entry.filename,'bytes':entry.file_size,'compressed_bytes':entry.compress_size} for entry in entries]
        with archive.open(matches[0]) as handle:
            for ordinal,line in enumerate(handle,start=1):
                utterance_hash.update(line);row=json.loads(line);source_counts['rows']+=1
                field_patterns[tuple(sorted(row))]+=1
                meta=row.get('meta') or {};meta_fields.update(meta.keys())
                identifier=row.get('id');speaker=row.get('user');thread=row.get('root');parent=row.get('reply_to')
                created=timestamp(row.get('timestamp'));kind='submission' if thread==identifier else 'comment'
                state=status(row.get('text'));source_statuses[state]+=1;source_counts[kind+'s']+=1
                if not isinstance(identifier,str) or not identifier:raise RuntimeError('Missing source record identifier')
                row_sha=digest(row)
                if identifier in ids:
                    duplicate_ids[identifier]+=1
                    if ids[identifier]!=row_sha:conflicting_ids.add(identifier)
                    continue
                ids[identifier]=row_sha
                if created:
                    source_years[created[:4]]+=1
                    minimum_time=created if minimum_time is None else min(minimum_time,created)
                    maximum_time=created if maximum_time is None else max(maximum_time,created)
                else:missing['invalid_or_missing_created_utc']+=1
                missing['speaker']+=not isinstance(speaker,str) or not speaker.strip()
                missing['thread']+=not isinstance(thread,str) or not thread
                missing['parent']+=parent is None
                if parent is not None:parents.append(parent)
                if thread:all_root_ids.add(thread)
                if (thread==identifier)!=(parent is None):source_counts['submission_parent_classification_disagreements']+=1
                community=meta.get('subreddit');communities[str(community) if community is not None else '(missing)']+=1
                for key in ('language','edit_state','edited_utc','near_duplicate_cluster','source_document','related_sample'):
                    missing['explicit_'+key]+=key not in row and key not in meta
                if isinstance(speaker,str) and speaker.strip():named_accounts.add(speaker)
                if kind!='comment':continue
                exclusion=('placeholder_account' if not isinstance(speaker,str) or speaker.strip().casefold() in PLACEHOLDERS else
                           'automoderator_account' if speaker.casefold()=='automoderator' else
                           'old_pilot_account' if speaker in excluded else None)
                if exclusion:exclusions[exclusion]+=1
                if not isinstance(speaker,str):continue
                view=None;words=None;retained_hash=None
                if state=='present':
                    record={'id':identifier,'kind':'comment','text':row['text'],'status':'present','title':None,
                            'subreddit':community,'created_utc':created,'edit_state':'unknown','language':None}
                    before=time.monotonic()
                    view=preprocess(record,{'default_language':'en','text_format':'markdown'},config)
                    words=sum(len(segment) for segment in view['word_tokens'])
                    preprocessing_seconds+=time.monotonic()-before
                    # This is an exact-normalization audit only. No matches are
                    # removed and no near-duplicate grouping claim is made.
                    normalized=unicodedata.normalize('NFC',row['text'].replace('\r\n','\n').replace('\r','\n'))
                    raw_hash=hashlib.sha256(normalized.encode()).hexdigest()
                    duplicate_text_occurrences[raw_hash]+=1;raw_text_hashes[raw_hash].add(speaker)
                    retained_hash=hashlib.sha256(canonical_bytes([s['text'] for s in view['segments']])).hexdigest()
                    retained_hashes[retained_hash].add(speaker)
                account_rows[speaker].append({'record_id':identifier,'source_line':ordinal,'thread_id':thread,
                    'parent_id':parent,'created_utc':created,'year':created[:4] if created else None,'subreddit':community,
                    'status':state,'retained_words':words,'eligible':state=='present' and created is not None and words is not None and words>=minimum_words,
                    'source_text_sha256':hashlib.sha256(row['text'].encode()).hexdigest() if isinstance(row.get('text'),str) else None,
                    'retained_segments_sha256':retained_hash,
                    'removed_quote_spans':view['structure']['removed_quote_spans'] if view else None,
                    'removed_code_spans':view['structure']['removed_code_spans'] if view else None})
    if utterance_hash.hexdigest()!=EXPECTED_UTTERANCES:raise RuntimeError('Authorized utterance member hash mismatch')
    if conflicting_ids:raise RuntimeError('Conflicting duplicate IDs require an explicit adapter decision before capacity inventory')
    phases['record_scan_seconds']=time.monotonic()-started-phases['input_identity_seconds']
    phases['preprocessing_seconds_within_scan']=preprocessing_seconds
    missing['referenced_parent_not_in_archive']=sum(parent not in ids for parent in parents)
    missing['referenced_thread_not_in_archive']=sum(thread not in ids for thread in all_root_ids)
    candidates=[];candidate_record_rows=[]
    for account,records in sorted(account_rows.items()):
        if account in excluded or account.strip().casefold() in PLACEHOLDERS or account.casefold()=='automoderator':continue
        records.sort(key=lambda row:(row['created_utc'] is None,row['created_utc'] or '',row['record_id']))
        eligible=[row for row in records if row['eligible']]
        annual={}
        for year in YEARS:
            observed=[row for row in records if row['year']==year];usable=[row for row in observed if row['eligible']]
            annual[year]={'comment_count':len(observed),'eligible_record_count':len(usable),
                'eligible_word_count':sum(row['retained_words'] for row in usable),
                'whole_record_3000word_8record_capacity':windows(usable,3000,minimum_records)}
        candidate={'inventory_alias':alias(account),'source_account':account,'comment_count':len(records),
            'status_counts':dict(sorted(Counter(row['status'] for row in records).items())),
            'eligible_record_count':len(eligible),'eligible_word_count':sum(row['retained_words'] for row in eligible),
            'first_utc':min((row['created_utc'] for row in records if row['created_utc']),default=None),
            'last_utc':max((row['created_utc'] for row in records if row['created_utc']),default=None),
            'community_labels':sorted({str(row['subreddit']) for row in records}),
            'years':annual,'full_history_default_windows':windows(eligible,target,minimum_records),
            'full_history_3000word_8record_capacity':windows(eligible,3000,minimum_records)}
        candidates.append(candidate)
        candidate_record_rows.extend({'inventory_alias':candidate['inventory_alias'],**row} for row in records)
    annual_summary={}
    for year in YEARS:
        periods=[candidate['years'][year] for candidate in candidates]
        capacity=[period['whole_record_3000word_8record_capacity']['qualified_unit_count'] for period in periods]
        annual_summary[year]={'accounts_with_comments':sum(period['comment_count']>0 for period in periods),
            'comment_count':sum(period['comment_count'] for period in periods),
            'eligible_record_count':sum(period['eligible_record_count'] for period in periods),
            'eligible_word_count':sum(period['eligible_word_count'] for period in periods),
            'accounts_with_at_least_one_3000word_unit':sum(count>=1 for count in capacity),
            'accounts_with_at_least_two_3000word_units':sum(count>=2 for count in capacity),
            'complete_3000word_units':sum(capacity),'per_account_eligible_words':distribution([p['eligible_word_count'] for p in periods if p['comment_count']])}
    intersections={a+'_'+b:sum(all(candidate['years'][year]['whole_record_3000word_8record_capacity']['qualified_unit_count']>=1 for year in (a,b)) for candidate in candidates)
                   for a,b in [('2016','2017'),('2017','2018'),('2016','2018')]}
    full_counts=[candidate['full_history_default_windows']['qualified_unit_count'] for candidate in candidates]
    summary={'inventory_version':'1.0.0','purpose':'Pre-score local data capacity inventory; no selected cohort, style distances, or change candidates.',
        'source':{'archive_sha256':archive_sha,'archive_bytes':ARCHIVE.stat().st_size,'member_sha256':{'utterances.jsonl':utterance_hash.hexdigest()},
                  'members':member_inventory,'reference':'https://convokit.cornell.edu/documentation/subreddit.html','corpus_version':0,
                  'first_utc':minimum_time,'last_utc':maximum_time,'coverage_status':'partial_or_unknown_historical_corpus'},
        'analysis_binding':{'suite_version':__version__,'implementation_fingerprint':fp,'config_sha256':digest(config.analytical()),
                            'reference_environment':environment,'resource_sha256':resources},
        'old_pilot_exclusion':{'account_count':len(excluded),'cohort_sha256':hash_file(old_cohort_path),'source_map_sha256':hash_file(old_map_path)},
        'assumptions':{'default_language':'en','basis':'Corpus-level English assumption; no language detection or verification.',
                       'text_format':'markdown','minimum_record_words':minimum_words,'sample_target_words':3000,'minimum_sample_records':minimum_records,
                       'default_window_target_words':target,'minimum_temporal_windows':minimum_windows,
                       'units':'Whole eligible records greedily accumulated in canonical chronological order; overshoot and largest-record share retained in restricted capacity metadata.'},
        'source_counts':{**dict(sorted(source_counts.items())),'unique_record_ids':len(ids),'unique_nonblank_account_keys':len(named_accounts),
                         'duplicate_id_occurrences':sum(duplicate_ids.values()),'duplicated_id_count':len(duplicate_ids),'conflicting_duplicate_id_count':len(conflicting_ids)},
        'source_status_counts':dict(sorted(source_statuses.items())),'source_calendar_year_counts':dict(sorted(source_years.items())),
        'source_field_patterns':[{'fields':list(fields),'rows':count} for fields,count in sorted(field_patterns.items())],
        'source_meta_field_presence':dict(sorted(meta_fields.items())),'missing_metadata_counts':dict(sorted(missing.items())),
        'community_counts':dict(sorted(communities.items())),'excluded_comment_counts':dict(sorted(exclusions.items())),
        'additional_account_count':len(candidates),'additional_comment_count':len(candidate_record_rows),
        'additional_eligible_comment_count':sum(candidate['eligible_record_count'] for candidate in candidates),
        'additional_eligible_words':sum(candidate['eligible_word_count'] for candidate in candidates),
        'calendar_capacity':annual_summary,'accounts_with_one_3000word_unit_in_both_years':intersections,
        'full_history_capacity':{'accounts_with_at_least_8_default_windows':sum(count>=8 for count in full_counts),
                                 'accounts_with_at_least_12_default_windows':sum(count>=12 for count in full_counts),
                                 'accounts_with_at_least_16_default_windows':sum(count>=16 for count in full_counts),
                                 'default_windows_per_account':distribution(full_counts)},
        'exact_text_inventory_only':{'normalization':'NFC after CRLF/CR to LF; case preserved; this is not semantic or near-duplicate grouping.',
            'source_normalized_text_groups_repeated_across_accounts':sum(len(accounts)>1 for accounts in raw_text_hashes.values()),
            'repeated_source_text_occurrences_beyond_first':sum(count-1 for count in duplicate_text_occurrences.values()),
            'retained_segment_groups_repeated_across_accounts':sum(len(accounts)>1 for accounts in retained_hashes.values()),
            'scope':'All present comment source accounts including excluded accounts; zero records removed by this audit.'},
        'limitations':['Only authorized local Cornell data were inventoried; one community cannot support the requested multi-community condition.',
            'Account-ID labels are proxies, not verified authorship, person identity, or human-only accounts.',
            'Excluding named AutoModerator does not establish that remaining accounts are human or singly operated.',
            'Near-duplicate/template clusters and independent related-unit groups are not supplied; exact counts do not establish their absence.',
            'Annual capacity is before any future split/thread/near-duplicate restrictions; it is an upper bound on qualifying final sampling units.',
            'No held-out cohort or pair was selected and no style score, reuse match, change segmentation, threshold, or accuracy was computed.',
            'Greedy window counts are representation-capacity observations, not detected changes or grid-error diagnostics.',
            'Historical corpus coverage is incomplete/unknown; observed timestamps do not establish inactivity outside supplied rows.']}
    args.out.mkdir(parents=True);private=args.out/'private';private.mkdir(mode=0o700)
    for path,data in [(private/'candidate-accounts.json',canonical_bytes({'scope':'Restricted local candidate volume map; inventory aliases are not final sampling identities.','accounts':candidates})),
                      (private/'candidate-records.jsonl',b''.join(canonical_bytes(row) for row in candidate_record_rows))]:
        path.write_bytes(data);path.chmod(0o600)
    (args.out/'summary.json').write_bytes(canonical_bytes(summary))
    paragraphs=['# Authorized local Cornell capacity inventory','',summary['purpose'],'',
        f"Source: {source_counts['rows']:,} utterances; {len(ids):,} unique IDs; {len(candidates):,} additional accounts after excluding all 12 prior-pilot accounts, placeholders and AutoModerator.",'',
        '| Calendar year | Additional accounts | Eligible comments | Eligible words | Accounts with one 3,000-word unit | Accounts with two units |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for year,value in annual_summary.items():paragraphs.append(f"| {year} | {value['accounts_with_comments']} | {value['eligible_record_count']} | {value['eligible_word_count']} | {value['accounts_with_at_least_one_3000word_unit']} | {value['accounts_with_at_least_two_3000word_units']} |")
    paragraphs+=['',f"Full-history capacity: {sum(count>=8 for count in full_counts)} additional accounts have at least eight default 1,000-word/eight-record windows before split/group restrictions.",'',
        'Only one source community is available. Several-community and cross-community comparisons require separately authorized data; this local inventory cannot supply them.','',
        'Private local files contain candidate names and record-level metadata/word counts, but no source prose. They are not included in this aggregate document. No cohort or held-out sample has been chosen.','',
        '## Limitations','',*['- '+item for item in summary['limitations']],'']
    (args.out/'INVENTORY.md').write_text('\n'.join(paragraphs))
    all_paths=[args.out/'summary.json',args.out/'INVENTORY.md',private/'candidate-accounts.json',private/'candidate-records.jsonl']
    (args.out/'sha256.json').write_bytes(canonical_bytes({str(path.relative_to(args.out)):hash_file(path) for path in all_paths}))
    receipt={'argv':sys.argv,'source_script_sha256':hash_file(__file__),'network_isolation':os.environ['AHAS_NETWORK_ISOLATION'],
             'elapsed_seconds':time.monotonic()-started,'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
             'phase_seconds':phases,'output_bytes':sum(path.stat().st_size for path in args.out.rglob('*') if path.is_file()),
             'style_scores_computed':False,'cohort_selected':False,'source_prose_exported':False}
    (args.out/'run-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'status':'inventoried','additional_accounts':len(candidates),'calendar_capacity':annual_summary,
                      'full_history_capacity':summary['full_history_capacity'],'resources':receipt}))


if __name__=='__main__':main()
