"""Independent saved-input check; no analyzer, preprocessing, or candidate search.

The frozen Pilot5 independent oracle supplies separately implemented prefix,
volume/date/cost and window arithmetic. This adapter checks only the registered
Pilot6 provisional pairs; it never considers another cut, direction, or pair.
Original writing is compared automatically in memory and never emitted.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import signal
import time

ORACLE_PATH=Path(__file__).resolve().parents[2]/'pilot5_shared_anchor/scripts/check_shared_anchor.py'
ORACLE_SHA='b83198971454e26f91bf7c4e20a2787cf6d1ad994da45d4be11a12bbcd97d0b5'

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def require(ok,code):
    if not ok:raise ValueError(code)

require(sha(ORACLE_PATH)==ORACLE_SHA,'independent_oracle_changed')
_spec=importlib.util.spec_from_file_location('pilot6_independent_prefix_oracle',ORACLE_PATH)
o=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(o)
KEYS=o.SAMPLES
CONDITIONS=('continuity_same_community','switch_same_community','continuity_changed_community','switch_changed_community')
PAIRS=(('AskAcademia','GradSchool'),('AskPhysics','Physics'),('math','learnmath'),('linux','linuxquestions'),('programming','learnprogramming'))
CUTS={f'{y}-{m:02d}-01T00:00:00Z' for y in range(2010,2019) for m in range(1,13) if (y,m)<=(2018,5)}


def read(path):return json.loads(Path(path).read_bytes())
def same(a,b,code):o.same(a,b,code)
def encoded(value):return o.encoded(value)
def identity(a):return hashlib.sha256(('pilot6-anchor-order-v1\0'+a).encode()).hexdigest()
def tie(p):return (p['stratum_id'],p['cut'],identity(p['account_a']),identity(p['account_b']),p['community_x'],p['community_y'])
def specs(p):
    a,b,x,y=(p[k] for k in ('account_a','account_b','community_x','community_y'))
    return dict(zip(KEYS,((a,x,'early'),(a,x,'late'),(b,x,'late'),(a,y,'late'),(b,y,'late')),strict=True))


def exclusions(flags,five):
    rows=flags['accounts'];names=[r['account_key'] for r in rows]
    fields=('pilot1_or_pilot2_or_private_mandatory_exclusion','pilot3_selected_scored_exposure','prior_capacity_only_exposure')
    require(len(set(names))==len(names) and all(isinstance(a,str) and a and a==a.casefold() for a in names),'canonical_unique_exposure_flags')
    require(all(type(r[f]) is bool for r in rows for f in fields),'boolean_exposure_flags')
    old={r['account_key'] for r in rows if r[fields[0]]};three={r['account_key'] for r in rows if r[fields[1]]}
    prior={five['selected'][k] for k in ('account_a','account_b')}
    require(all(isinstance(a,str) and a and a==a.casefold() for a in prior),'canonical_pilot5_exclusions')
    require(len(old)==57 and len(three)==60 and len(prior)==2 and len(old|three|prior)==119,'exact_119_exclusions')
    return old|three|prior,{r['account_key'] for r in rows if r[fields[2]]}


def validate_pairs(pairs,excluded,capacity):
    require(len(pairs)<=20,'provisional_pair_ceiling')
    accounts=[]
    for i,p in enumerate(pairs,1):
        require(p['pair_id']==f'pilot6-pair-{i:02d}','fixed_provisional_pair_order')
        require(p['stratum_id'] in {f'stratum-{n:02d}' for n in range(1,6)},'registered_stratum')
        require({p['community_x'],p['community_y']}==set(PAIRS[int(p['stratum_id'][-2:])-1]),'fixed_community_pair')
        require(p['cut'] in CUTS,'fixed_monthly_cut')
        require(p['valid'] is True,'provisional_pair_was_metadata_valid')
        names=[p['account_a'],p['account_b']]
        require(all(isinstance(a,str) and a and a==a.casefold() for a in names),'canonical_pair_accounts')
        if 'prior_capacity_only_accounts' in p:
            require(p['prior_capacity_only_accounts']==sum(a in capacity for a in names),'capacity_exposure_count')
        accounts+=names
    require(len(accounts)==len(set(accounts)) and not set(accounts)&excluded,'disjoint_new_pair_accounts')
    return set(accounts)


def buffer_prefix(rows,cut,period):
    """Independent fixed 8000/64 buffer, including exhausted partial prefixes."""
    require(period in ('early','late'),'buffer_period')
    low,high=(cut-180*86400,cut) if period=='early' else (cut,cut+180*86400)
    require(all(type(r['retained_words']) is int and r['retained_words']>=0 for r in rows),'buffer_integer_words')
    eligible=[r for r in rows if low<=o.seconds(r['created_utc'])<high and 20<=r['retained_words']<=500]
    require(len({r['record_id'] for r in eligible})==len(eligible),'buffer_duplicate_original_id')
    eligible.sort(key=lambda r:(abs(o.seconds(r['created_utc'])-cut),o.seconds(r['created_utc']),r['record_id']))
    result=[];words=0
    for r in eligible:
        if words+r['retained_words']>8500 or len(result)>=300:break
        result.append(r);words+=r['retained_words']
        if words>=8000 and len(result)>=64:break
    return result


def check_bindings(plan,phase,needed):
    require(plan['phase']==phase,'registered_preparation_phase')
    refs=plan['bindings'];bound={str(Path(r['path']).resolve()):r['sha256'] for r in refs}
    require(len(bound)==len(refs),'unique_preparation_bindings')
    require({str(Path(p).resolve()) for p in needed}<=set(bound),'all_consumed_inputs_bound')
    for path,digest in bound.items():require(sha(path)==digest,'registered_input_hash')
    return bound


def original_projection(raw):
    require(raw.get('root')!=raw['id'] and isinstance(raw['text'],str),'original_present_comment')
    require(raw['text'].strip() and raw['text'].strip().casefold() not in ('[removed]','[deleted]'),'original_observable_body')
    return {'schema_version':'1.0.0','id':raw['id'],'account_id':raw['user'],'kind':'comment','text':raw['text'],
        'status':'present','created_utc':datetime.fromtimestamp(raw['timestamp'],timezone.utc).isoformat().replace('+00:00','Z'),
        'subreddit':raw['meta']['subreddit'],'language':None,'edit_state':'unknown','edited_utc':None,'title':None,
        'parent_id':raw.get('reply_to'),'thread_id':raw.get('root'),'parent_created_utc':None,'permalink':raw['meta'].get('permalink')}


def check_originals(directory,selected,entries):
    index=read(directory/'original-source-index.json')
    require(set(index)==set(selected)==set(entries),'complete_original_source_coverage')
    cursor=0
    with (directory/'original-source-lines.jsonl').open('rb') as f:
        for rid,at in sorted(index.items(),key=lambda x:x[1]['offset']):
            require(type(at['offset']) is int and at['offset']==cursor and type(at['bytes']) is int and at['bytes']>0,'original_line_offsets')
            line=f.read(at['bytes']);cursor+=len(line)
            require(len(line)==at['bytes'] and line.count(b'\n')<=1 and (b'\n' not in line or line.endswith(b'\n')),'original_line_extent')
            require(hashlib.sha256(line).hexdigest()==at['sha256']==selected[rid]['source_line_sha256'],'original_line_metadata_hash')
            raw=json.loads(line);require(raw['id']==rid,'original_line_identity')
            same(entries[rid]['record'],original_projection(raw),'original_record_field_fidelity')
            e=entries[rid];m=selected[rid]
            require(e['record']['account_id'].casefold()==m['account_key'] and e['record']['subreddit']==m['community']
                and e['record']['created_utc']==m['created_utc'],'original_identity_timestamp_metadata')
        require(not f.read(1),'unindexed_original_source_bytes')
    return cursor


def verify_buffer(plan_path,directory,receipt_path):
    plan=read(plan_path);directory=Path(directory)
    needed=[plan[k] for k in ('provisional_pairs','exposure_flags','pilot5_selection','converter','protocol','metadata_plan')]+plan['metadata_files']+[r['archive'] for r in plan['sources']]
    bound=check_bindings(plan,'frozen_before_replication_buffer',needed)
    metadata_plan=read(plan['metadata_plan']);provisional=read(plan['provisional_pairs'])
    require(metadata_plan['phase']=='frozen_before_replication_metadata'
        and provisional['plan_sha256']==sha(plan['metadata_plan']),'provisional_search_plan_lineage')
    source_metadata=metadata_plan['source_metadata']
    same([str(Path(p).resolve()) for p in plan['metadata_files']],
        [str(Path(r['path']).resolve()) for r in source_metadata],'exact_search_metadata_inputs')
    for r in source_metadata:
        require(type(r['bytes']) is int and r['bytes']==Path(r['path']).stat().st_size
            and r['sha256']==bound[str(Path(r['path']).resolve())],'search_metadata_bytes_and_hashes')
    require(sha(metadata_plan['exposure_flags'])==sha(plan['exposure_flags'])
        and sha(metadata_plan['pilot5_selection'])==sha(plan['pilot5_selection']),'search_and_buffer_exclusion_lineage')
    excluded,capacity=exclusions(read(plan['exposure_flags']),read(plan['pilot5_selection']))
    pairs=provisional['pairs'];accounts=validate_pairs(pairs,excluded,capacity)
    timelines=defaultdict(list);seen=set();count=bytecount=0
    require(len({str(Path(p).resolve()) for p in plan['metadata_files']})==len(plan['metadata_files']),'unique_metadata_inputs')
    for path in plan['metadata_files']:
        with Path(path).open('rb') as f:
            for line in f:
                count+=1;bytecount+=len(line)
                require(count<=3000000 and bytecount<=1024**3,'metadata_resource_ceiling')
                r=json.loads(line)
                if r['account_key'] not in accounts or r['reason'] is not None:continue
                require(r['record_id'] not in seen,'metadata_duplicate_original_id');seen.add(r['record_id'])
                timelines[r['account_key'],r['community']].append(r)
    expected={};members=[];stats=[]
    for p in pairs:
        cells=[]
        for key,(a,c,period) in specs(p).items():
            rows=buffer_prefix(timelines[a,c],o.seconds(p['cut']),period)
            members.append({'pair_id':p['pair_id'],'sample_key':key,'ids':[r['record_id'] for r in rows]})
            for r in rows:
                require(r['record_id'] not in expected,'source_buffer_reuse')
                expected[r['record_id']]={**r,'stratum_id':p['stratum_id'],'period':period,'pair_id':p['pair_id'],'sample_key':key}
            cells.append({'sample_key':key,'records':len(rows),'retained_words':sum(r['retained_words'] for r in rows)})
        stats.append({'pair_id':p['pair_id'],'samples':cells})
    require(len(expected)<=100000 and sum(r['retained_words'] for r in expected.values())<=2000000,'candidate_pool_resource_ceiling')
    same(read(directory/'selection.json'),{'pairs':pairs,'selected_metadata':expected,'sample_memberships':members},'all_frozen_buffer_prefixes')
    receipt=read(receipt_path);entries={}
    if not expected:
        same(receipt,{'status':'empty_provisional_pool','candidate_records':0,'provisional_pairs':len(pairs),'style_calls':0},'empty_buffer_receipt')
        require(not (directory/'candidate-pool.jsonl').exists(),'empty_buffer_has_pool')
    else:
        with (directory/'candidate-pool.jsonl').open('rb') as f:
            for line in f:
                e=json.loads(line);rid=e['record']['id'];require(rid not in entries,'pool_duplicate_original_id');entries[rid]=e
                require(rid in expected,'pool_outside_frozen_buffer');m=expected[rid]
                same({k:v for k,v in e.items() if k!='record'},{k:m[k] for k in ('account_key','community','period','stratum_id','retained_words','pair_id','sample_key')},'pool_source_assignment')
        check_originals(directory,expected,entries)
        wanted={'status':'prepared_not_audited','provisional_pairs':len(pairs),'candidate_records':len(expected),
            'candidate_retained_words':sum(r['retained_words'] for r in expected.values()),'samples':stats,
            'candidate_pool_sha256':sha(directory/'candidate-pool.jsonl'),'selection_sha256':sha(directory/'selection.json'),
            'plan_sha256':sha(plan_path),'style_calls':0}
        for k,v in wanted.items():same(receipt[k],v,'buffer_receipt_arithmetic_and_binding')
        require(receipt['source_rows']<=25000000 and receipt['source_uncompressed_bytes']<=16*1024**3,'archive_scan_resource_ceiling')
        require(receipt['source_rows']==sum(r['rows'] for r in receipt['sources']),'archive_row_receipt_total')
        same([(r['community'],r['archive_sha256']) for r in receipt['sources']],[(r['community'],sha(r['archive'])) for r in plan['sources']],'archive_receipt_bindings')
    require(sum(p.stat().st_size for p in directory.iterdir() if p.is_file())<=256*1024**2,'buffer_private_output_ceiling')
    return {'pairs':pairs,'entries':entries,'metadata':expected,'excluded':excluded,'capacity':capacity,
        'metadata_rows_checked':count,'metadata_bytes_checked':bytecount}


def verify_audit(audit,entries):
    s=audit['summary']
    require(s.get('gate_b_ready') is True and s.get('available_content_and_grouping_audit_complete') is True
        and audit.get('actionable') is True and audit['engine_audit']['status']=='audited','complete_available_content_audit')
    require(s.get('max_candidate_pairs')==2000000 and s.get('independent_count_is_lower_bound') is False
        and type(s.get('independent_candidate_pairs')) is int and 0<=s['independent_candidate_pairs']<=2000000
        and s.get('independent_engine_eligible_candidate_pairs')==s.get('engine_candidate_pair_count')
        and type(s.get('engine_candidate_pair_count')) is int and 0<=s['engine_candidate_pair_count']<=s['independent_candidate_pairs'],
        'complete_fixed_candidate_pair_caps')
    kept=audit['surviving_candidate_ids'];gone=audit['purge_record_ids']
    require(len(kept)==len(set(kept)) and len(gone)==len(set(gone)) and not set(kept)&set(gone)
        and set(kept)|set(gone)==set(entries),'exact_audit_partition')
    provenance=audit['record_provenance'];candidate={rid:p for rid,p in provenance.items() if not p['historical']}
    require(set(candidate)==set(entries),'audit_candidate_provenance_coverage')
    historical=[p for p in provenance.values() if p['historical']]
    require(not {p['account_key'] for p in historical}&{e['account_key'] for e in entries.values()}
        and not {p['source_record_id'] for p in historical}&set(entries),'candidate_historical_identity_boundary')
    for rid,p in candidate.items():
        e=entries[rid];record=e['record'];thread=record['thread_id']
        require(isinstance(thread,str) and thread,'candidate_thread_required')
        same(p,{'source_record_id':rid,'source_kind':'comment','text_component':'body','historical':False,
            'account_key':e['account_key'],'stratum_id':e['stratum_id'],'cell':[e['account_key'],e['community'],e['period']],
            'thread_id':thread,'declared_retained_words':e['retained_words']},'audit_candidate_provenance')
    components=audit['engine_audit']['components'];allids=[rid for c in components for rid in c['record_ids']]
    require(len(allids)==len(set(allids)) and set(allids)==set(provenance),'audit_component_partition')
    reasons=defaultdict(set);threads=defaultdict(list)
    def mark(ids,kind):
        candidates=[rid for rid in ids if rid in candidate]
        cells={tuple(candidate[rid]['cell']) for rid in candidates}
        for rid in candidates:
            if any(provenance[i]['historical'] for i in ids):reasons[rid].add(kind+'_historical_boundary')
            if len(cells)>1:reasons[rid].add(kind+'_cross_candidate_cells')
    for c in components:mark(c['record_ids'],'content')
    for rid,p in provenance.items():
        if p['thread_id']:threads[p['thread_id']].append(rid)
    for ids in threads.values():mark(ids,'thread')
    same(audit['purge_reasons'],{rid:sorted(v) for rid,v in reasons.items()},'audit_saved_graph_purges')
    require(set(reasons)==set(gone),'audit_saved_graph_purge_partition')
    for key,value in {'candidate_records':len(entries),'candidate_retained_words':sum(e['retained_words'] for e in entries.values()),
        'purged_candidate_records':len(gone),'surviving_candidate_records':len(kept)}.items():same(s[key],value,'audit_summary_counts')
    return set(kept)


def verify_audit_binding(freeze_path,public_path,audit_path,pool_path):
    freeze=read(freeze_path);public=read(public_path);audit=read(audit_path)
    require(freeze.get('state')=='frozen_before_audit','audit_registered_before_run')
    require(freeze['candidate_pool_sha256']==sha(pool_path) and public['private_audit_sha256']==sha(audit_path)
        and public['freeze_sha256']==sha(freeze_path),'audit_run_input_and_output_binding')
    for key in ('wrapper_sha256','engine_sha256','rules_sha256'):same(public[key],freeze[key],'audit_implementation_binding')
    for key,value in audit['summary'].items():same(public[key],value,'audit_public_private_summary')
    return sha(freeze_path)


def post_rows(pairs,entries,survivors):
    rows=[];sample_maps={}
    for pair in pairs:
        samples={}
        for key,(a,c,period) in specs(pair).items():
            data=[{'record_id':rid,'timestamp':o.seconds(e['record']['created_utc']),'retained_words':e['retained_words']}
                for rid,e in entries.items() if rid in survivors and (e['account_key'],e['community'],e['period'])==(a,c,period)]
            samples[key]=o.select_prefix(data,o.seconds(pair['cut']),period)
        e=o.evaluate_samples(samples)
        reasons=['unavailable_sample:'+k for k in e['unavailable_samples']] if e['unavailable_samples'] else [
            'fewer_than_eight_qualified_windows' if r=='one_or_more_histories_below_eight_primary_windows' else r for r in e['failed_gates']]
        rows.append({**pair,'valid':e['valid'],'reason_codes':reasons,'cost':e['exact_cost'],
            'qualified_window_counts':None if e['histories'] is None else [e['histories'][k]['qualified_windows'] for k in KEYS[1:]],
            'late_median_span_days':e['late_median_span_days'],'five_sample_word_ratio':e['word_ratio'],'five_sample_record_ratio':e['record_ratio']})
        sample_maps[pair['pair_id']]=samples
    chosen=sorted((r for r in rows if r['valid']),key=lambda r:(r['cost'],tie(r)))[:10]
    return rows,chosen,sample_maps


def primary_grid(rows):
    ends=[];words=n=0
    for i,r in enumerate(rows):
        words+=r['retained_words'];n+=1
        if words>=1000 and n>=8:ends.append(i+1);words=n=0
    return len(ends),[{'window_index':j,'split_interval':[ends[j-1],ends[j-1]]} for j in range(3,len(ends)-2)] if len(ends)>=8 else []


def inside(path,directory):
    p=Path(path);require(p.is_absolute() and p.resolve().is_relative_to(directory.resolve()),'prepared_path_outside_directory')
    require(not p.is_symlink(),'prepared_symlink');return p


def verify_final(plan_path,prepared,public,buffer_plan_path,buffer_directory,checked):
    plan=read(plan_path);prepared=Path(prepared);public=Path(public);buffer_directory=Path(buffer_directory)
    check_bindings(plan,'frozen_before_replication_final_cohort',[plan[k] for k in ('buffer_selection','audit','pool','exposure_flags','pilot5_selection','protocol')])
    require(Path(plan['buffer_selection']).resolve()==(buffer_directory/'selection.json').resolve()
        and Path(plan['pool']).resolve()==(buffer_directory/'candidate-pool.jsonl').resolve(),'final_uses_checked_buffer')
    bp=read(buffer_plan_path)
    require(sha(plan['exposure_flags'])==sha(bp['exposure_flags']) and sha(plan['pilot5_selection'])==sha(bp['pilot5_selection']),'final_exclusion_sources_unchanged')
    entries=checked['entries'];pairs=checked['pairs'];audit=read(plan['audit']);survivors=verify_audit(audit,entries)
    rows,chosen,maps=post_rows(pairs,entries,survivors);chosen_ids={r['pair_id'] for r in chosen}
    expected_rows=[encoded({k:v for k,v in dict(r,selection_status=('selected_for_replication' if r['pair_id'] in chosen_ids else
        'eligible_outside_fixed_ten_pair_cohort' if r['valid'] else 'unavailable_after_audit')).items() if k not in ('account_a','account_b')}) for r in rows]
    same(read(public/'pair-availability.json'),expected_rows,'every_post_audit_candidate_and_cost_rank')
    cohort=read(prepared/'cohort-prepared.json');expected_cohort=[];unique=set();appearances=0
    for pair in chosen:
        pid=pair['pair_id'];directory=prepared/pid;sample_map=maps[pid]
        ids={k:[r['record_id'] for r in sample_map[k]['rows']] for k in KEYS}
        flat=[rid for v in ids.values() for rid in v]
        require(len(flat)==len(set(flat)) and not set(flat)&unique and set(flat)<=survivors,'final_unique_source_records')
        unique.update(flat)
        same(read(directory/'selection.json'),{'selected':encoded(pair),'source_samples':ids,'plan_sha256':sha(plan_path),'audit_sha256':sha(plan['audit'])},'five_fixed_post_audit_prefixes')
        idx=read(directory/'index.json');require(idx['prepared_block_count']==1 and len(idx['cases'])==4,'four_histories_per_pair')
        expected_bound=[{'path':str((directory/'selection.json').resolve()),'sha256':sha(directory/'selection.json')}]
        for case,condition,key in zip(idx['cases'],CONDITIONS,KEYS[1:],strict=True):
            cid=pid+':AX:'+condition;expected_ids=ids['anchor']+ids[key];appearances+=len(expected_ids)
            require(expected_ids==sorted(expected_ids,key=lambda rid:(o.seconds(entries[rid]['record']['created_utc']),rid)),'full_history_chronology')
            case_dir=directory/cid;paths={k:inside(case[k],directory) for k in ('input','manifest','metadata')}
            same({k:str(p) for k,p in paths.items()},{'input':str((case_dir/'records.jsonl').resolve()),'manifest':str((case_dir/'snapshot.json').resolve()),'metadata':str((case_dir/'metadata.json').resolve())},'exact_case_paths')
            records=[dict(entries[rid]['record'],account_id=cid) for rid in expected_ids]
            expected_bytes=b''.join((json.dumps(r,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode() for r in records)
            require(paths['input'].read_bytes()==expected_bytes,'original_fields_unchanged_except_account_alias')
            metadata=[{'record_id':rid,'created_utc':entries[rid]['record']['created_utc'],'retained_words':entries[rid]['retained_words'],'kind':'comment','style_eligible':True} for rid in expected_ids]
            same(read(paths['metadata']),{'records':metadata},'history_metadata_exact_source_membership')
            manifest={'schema_version':'1.0.0','snapshot_id':cid,'account_id':cid,'source_category':'research_corpus','text_format':'markdown','default_language':'en',
                'source_notes':'Registered bounded shared-anchor replication; source-account proxies, original writing and timestamps. English is a corpus-level assumption.',
                'coverage':{'status':'sampled','start_utc':records[0]['created_utc'],'end_utc':records[-1]['created_utc'],'notes':'Whole-comment sample, not a complete account history.'}}
            same(read(paths['manifest']),manifest,'snapshot_source_and_coverage_contract')
            qualified,grid=primary_grid(metadata);switch=condition.startswith('switch_')
            expected_case={'case_id':cid,'block_id':pid,'stratum_id':pair['stratum_id'],'anchor_id':'AX','condition':condition,'source_switch':switch,
                'community_change':condition.endswith('changed_community'),'left_cell_id':pid+':A:X:early','right_cell_id':pid+':'+key[-2]+':'+key[-1]+':late',
                **{k:str(p) for k,p in paths.items()},'truth_k':len(ids['anchor']) if switch else None,'control_junction_k':None if switch else len(ids['anchor']),
                'prescore_qualified_windows':qualified,'prescore_legal_grid':grid}
            same(case,expected_case,'case_conditions_truth_windows_and_grid')
            expected_bound += [{'path':str(paths[k]),'sha256':sha(paths[k])} for k in ('input','manifest','metadata')]
        same(idx['bound_files'],expected_bound,'complete_prepared_file_bindings')
        expected_cohort.append({'pair_id':pid,'index':str((directory/'index.json').resolve()),'source_account_keys':[pair['account_a'],pair['account_b']]})
        same(read(public/(pid+'-samples.json')),{'pair_id':pid,'samples':[o.sample_statistics(k,sample_map[k]) for k in KEYS],
            'unique_comments':len(flat),'unique_retained_words':sum(entries[rid]['retained_words'] for rid in flat),'shared_anchor_records':len(ids['anchor'])},'public_sample_statistics')
    same(cohort,{'target_pairs':10,'pairs':expected_cohort,'excluded_account_keys':sorted(checked['excluded']),'finalization_plan_sha256':sha(plan_path)},'exact_disjoint_top_ten_cohort')
    expected_summary={'target_new_pairs':10,'provisional_pairs':len(pairs),'eligible_after_audit':sum(r['valid'] for r in rows),'selected_new_pairs':len(chosen),
        'selected_source_accounts':len(chosen)*2,'planned_main_histories':len(chosen)*4,'planned_replays':len(chosen)*4,'pair_shortfall':10-len(chosen),
        'cohort_prepared_sha256':sha(prepared/'cohort-prepared.json'),'finalization_plan_sha256':sha(plan_path),'style_calls':0,'grid_locations_used_for_selection':False}
    same(read(public/'selection-summary.json'),expected_summary,'selection_summary')
    actual_indexes=list(prepared.rglob('index.json'))
    require({p.resolve() for p in actual_indexes}=={Path(r['index']).resolve() for r in expected_cohort},'no_unselected_prepared_histories')
    require(sum(p.stat().st_size for p in prepared.rglob('*') if p.is_file())<=256*1024**2,'prepared_private_output_ceiling')
    return {'post_audit_provisional_pairs_verified':len(rows),'eligible_pairs_verified':sum(r['valid'] for r in rows),'selected_pairs_verified':len(chosen),
        'prepared_histories_verified':4*len(chosen),'unique_selected_original_records':len(unique),'constructed_record_appearances':appearances,
        'purged_candidate_records':len(entries)-len(survivors),'surviving_candidate_records':len(survivors),
        'available_content_audit_complete':True,'unknown_historical_content_scope_disclosed':audit['summary'].get('independence_scope_complete') is not True,
        'final_plan_sha256':sha(plan_path),'cohort_prepared_sha256':sha(prepared/'cohort-prepared.json'),'audit_sha256':sha(plan['audit'])}


def main():
    p=argparse.ArgumentParser()
    for k in ('buffer-plan','buffer','buffer-receipt','out'):p.add_argument('--'+k,required=True,type=Path)
    for k in ('final-plan','prepared','public','audit-freeze','audit-public'):p.add_argument('--'+k,type=Path)
    a=p.parse_args();require(not a.out.exists(),'existing_check_output')
    final_args=(a.final_plan,a.prepared,a.public,a.audit_freeze,a.audit_public)
    require(all(final_args) or not any(final_args),'complete_optional_final_arguments')
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2)
    def stop(*_):raise TimeoutError('independent_check_wall_limit')
    signal.signal(signal.SIGALRM,stop);signal.alarm(1800);started=time.monotonic()
    try:
        checked=verify_buffer(a.buffer_plan,a.buffer,a.buffer_receipt)
        result={'status':'passed','provisional_pairs_verified':len(checked['pairs']),'buffer_cells_verified':5*len(checked['pairs']),
            'buffer_original_records_verified':len(checked['entries']),'buffer_retained_words_verified':sum(e['retained_words'] for e in checked['entries'].values()),
            'metadata_rows_checked':checked['metadata_rows_checked'],'metadata_bytes_checked':checked['metadata_bytes_checked'],
            'buffer_plan_sha256':sha(a.buffer_plan),'buffer_receipt_sha256':sha(a.buffer_receipt),'buffer_selection_sha256':sha(a.buffer/'selection.json')}
        if a.final_plan:
            fp=read(a.final_plan)
            result['audit_freeze_sha256']=verify_audit_binding(a.audit_freeze,a.audit_public,fp['audit'],fp['pool'])
            result.update(verify_final(a.final_plan,a.prepared,a.public,a.buffer_plan,a.buffer,checked))
        code=0
    except Exception as e:
        label=str(e) if isinstance(e,ValueError) and str(e).replace('_','').isalnum() else None
        result={'status':'failed','error_type':type(e).__name__,'check_code':label};code=1
    finally:signal.alarm(0)
    result.update(checker_sha256=sha(__file__),independent_oracle_sha256=ORACLE_SHA,source_text_compared_automatically=True,
        source_prose_emitted=False,original_source_identifiers_published=False,new_preprocessing_calls=0,new_style_calls=0,
        alternative_pairs_cuts_directions_examined=0,wall_seconds=time.monotonic()-started,
        peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,recorded_utc=datetime.now(timezone.utc).isoformat())
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({k:result[k] for k in ('status','provisional_pairs_verified','selected_pairs_verified') if k in result}),flush=True)
    return code

if __name__=='__main__':raise SystemExit(main())
