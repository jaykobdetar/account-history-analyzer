"""Independent prepared-input verification; no style computation or archive scan.

The checker uses only private prepared records, original source-line copies,
audit metadata and registered designs. It never imports the pool/finalizer or
chronology aggregation code. At most20 fixed record-word checks may invoke the
unchanged preprocessor; no original writing or private identity is reported.
"""
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

DAY=86400
EPOCH=datetime(1970,1,1,tzinfo=timezone.utc)
CELL_KEYS=('X/early','X/late','Y/early','Y/late')
CONDITIONS=('continuity_same_community','switch_same_community','continuity_changed_community','switch_changed_community')
PAIR_CAPS={frozenset(('AskPhysics','Physics')):1,frozenset(('linux','linuxquestions')):2,
           frozenset(('programming','learnprogramming')):2}
FP='bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179'
CONFIG='8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925'
COUNTERS={'preprocessor_calls':0}
ENV='CPython-3.12.3;Linux;x86_64;numpy=2.4.2;scipy=1.17.1;ruptures=1.1.10;markdown-it-py=3.0.0;jsonschema=4.26.0'


def require(test,reason):
    if not test:raise ValueError(reason)


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def read(path):return json.loads(Path(path).read_bytes())


def save(path,value):
    with Path(path).open('x') as f:json.dump(value,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n')


def seconds(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    require(dt.utcoffset()==timedelta(0) and dt.microsecond==0,'noninteger_UTC_record')
    return (dt-EPOCH).days*DAY+(dt-EPOCH).seconds


def iso(value):
    return (EPOCH+timedelta(microseconds=int(Fraction(value)*1000000))).isoformat().replace('+00:00','Z')


def identity_rank(account):
    return hashlib.sha256(('pilot4-feasibility-identity-order-v1\0'+account.casefold()).encode()).hexdigest()


def rational(value):
    value=Fraction(value);return {'numerator':value.numerator,'denominator':value.denominator}


def prefix(rows,cut,period):
    require(period in ('early','late'),'unknown_period')
    lo,hi=(cut-180*DAY,cut) if period=='early' else (cut,cut+180*DAY)
    ordered=sorted((r for r in rows if lo<=r['timestamp']<hi and 20<=r['retained_words']<=500),
        key=lambda r:(abs(r['timestamp']-cut),r['timestamp'],r['record_id']))
    count=words=0
    for row in ordered:
        count+=1;words+=row['retained_words']
        if count>200 or words>5500:return None
        if count>=40 and words>=5000:
            kept=sorted(ordered[:count],key=lambda r:(r['timestamp'],r['record_id']))
            times=[r['timestamp'] for r in kept]
            return {'records':count,'words':words,'median':Fraction(times[(count-1)//2]+times[count//2],2),'rows':kept}
    return None


def compatible(left,right):
    all_cells=[left[key] for key in CELL_KEYS]+[right[key] for key in CELL_KEYS]
    w=[r['words'] for r in all_cells];n=[r['records'] for r in all_cells]
    return max(w)*10<=min(w)*11 and max(n)*4<=min(n)*5 and all(
        max(side[c+'/'+period]['median'] for side in (left,right) for c in 'XY')-
        min(side[c+'/'+period]['median'] for side in (left,right) for c in 'XY')<=30*DAY for period in ('early','late'))


def cost(left,right):
    return sum((abs(left[k]['median']-right[k]['median'])/(180*DAY)+
                Fraction(abs(left[k]['words']-right[k]['words']),5000)+
                Fraction(abs(left[k]['records']-right[k]['records']),40) for k in CELL_KEYS),Fraction())


def capped_matching(nodes,edges,cap):
    """Independent vertex-subset recurrence, with a separate remaining edge cap."""
    require(type(cap) is int and cap in (1,2),'block_cap')
    nodes=tuple(sorted(nodes,key=identity_rank));order={a:i for i,a in enumerate(nodes)}
    weights={tuple(sorted((order[a],order[b]))):Fraction(c) for (a,b),c in edges.items()}
    @lru_cache(None)
    def solve(vertices,remaining):
        if not vertices or not remaining:return (0,Fraction(),())
        first,*rest=vertices;best=solve(tuple(rest),remaining)
        for second in rest:
            edge=(first,second)
            if edge in weights:
                count,total,pairs=solve(tuple(i for i in rest if i!=second),remaining-1)
                best=min(best,(count-1,total+weights[edge],(edge,)+pairs))
        return best
    negative,total,pairs=solve(tuple(range(len(nodes))),cap)
    return [(nodes[a],nodes[b]) for a,b in pairs],total


def factorial(block):
    result=[]
    for account in 'AB':
        for community in 'XY':
            for condition in CONDITIONS:
                switch=condition.startswith('switch_');changed=condition.endswith('changed_community')
                other_account=('B' if account=='A' else 'A') if switch else account
                other_community=('Y' if community=='X' else 'X') if changed else community
                anchor=account+community
                result.append({'case_id':block+':'+anchor+':'+condition,'block_id':block,'anchor_id':anchor,
                    'condition':condition,'source_switch':switch,'community_change':changed,
                    'left_cell_id':f'{block}:{account}:{community}:early',
                    'right_cell_id':f'{block}:{other_account}:{other_community}:late'})
    return result


def window_grid(metadata):
    windows=[];start=0;words=0
    for i,row in enumerate(metadata):
        words+=row['retained_words']
        if words>=1000 and i-start+1>=8:
            windows.append((start,i));start=i+1;words=0
    grid=[{'window_index':i,'split_interval':[windows[i-1][1]+1,windows[i][0]]}
          for i in range(3,len(windows)-2)] if len(windows)>=8 else []
    return len(windows),grid


def quantile_type7(values,p):
    values=sorted(values);position=(len(values)-1)*p
    i=position.numerator//position.denominator;frac=position-i
    return float(values[i]+frac*(values[min(i+1,len(values)-1)]-values[i]))


def cell_stats(cell):
    words=[r['retained_words'] for r in cell['rows']]
    return {'records':len(words),'retained_words':sum(words),'word_overshoot':sum(words)-5000,
        'largest_record_words':max(words),'largest_record_share':max(words)/sum(words),
        'comment_length_quantiles':{str(p):quantile_type7(words,p) for p in (Fraction(0),Fraction(1,4),Fraction(1,2),Fraction(3,4),Fraction(1))},
        'first_utc':iso(cell['rows'][0]['timestamp']),'last_utc':iso(cell['rows'][-1]['timestamp']),
        'median_utc':iso(cell['median'])}


def source_projection(source):
    require(source['root']!=source['id'],'source_submission')
    return {'schema_version':'1.0.0','id':source['id'],'account_id':source['user'],'kind':'comment',
        'text':source['text'],'status':'present','created_utc':iso(source['timestamp']),
        'subreddit':source['meta']['subreddit'],'language':None,'edit_state':'unknown','edited_utc':None,
        'title':None,'parent_id':source.get('reply_to'),'thread_id':source.get('root'),
        'parent_created_utc':None,'permalink':source['meta'].get('permalink')}


def source_metadata_binding(paths,bindings,selection):
    """Bind private source-line copies directly to upstream frozen census rows."""
    found=set();count=total_bytes=0
    for name in paths:
        path=Path(name);digest=hashlib.sha256()
        with path.open('rb') as source:
            for raw in source:
                count+=1;total_bytes+=len(raw);digest.update(raw)
                require(count<=3000000 and total_bytes<=1024**3,'upstream_metadata_cap')
                row=json.loads(raw);rid=row['record_id']
                if rid in selection:
                    require(rid not in found,'duplicate_selected_upstream_metadata')
                    expected=selection[rid]
                    require(row['reason'] is None and {**row,'stratum_id':expected['stratum_id'],'period':expected['period']}==expected,
                            'upstream_census_metadata_or_source_hash')
                    found.add(rid)
        require(digest.hexdigest()==bindings[str(path.resolve())],'upstream_metadata_file_hash')
    require(found==set(selection),'upstream_selected_record_coverage')
    return {'rows_read':count,'bytes_read':total_bytes,'selected_source_hashes_verified':len(found)}


def audit_membership(entries,audit):
    summary=audit['summary']
    require(audit['actionable'] is True and summary['status']=='audited' and
            summary['gate_b_ready'] is True and summary['available_content_and_grouping_audit_complete'] is True and
            summary['scores_computed'] is False and audit['engine_audit']['status']=='audited','audit_incomplete')
    survivors=set(audit['surviving_candidate_ids']);purged=set(audit['purge_record_ids']);provenance=audit['record_provenance']
    require(len(survivors)==len(audit['surviving_candidate_ids']) and len(purged)==len(audit['purge_record_ids']) and
            not survivors&purged and survivors|purged==set(entries),'audit_partition')
    require(all(type(r['historical']) is bool for r in provenance.values()) and
            {rid for rid,r in provenance.items() if not r['historical']}==set(entries),'audit_provenance_partition')
    for rid,row in entries.items():
        expected={'source_record_id':rid,'source_kind':'comment','text_component':'body','historical':False,
            'account_key':row['account_key'],'stratum_id':row['stratum_id'],
            'cell':[row['account_key'],row['community'],row['period']],
            'thread_id':row['record']['thread_id'],'declared_retained_words':row['retained_words']}
        require(all(provenance[rid].get(k)==v for k,v in expected.items()),'audit_record_provenance')
    components=[c['record_ids'] for c in audit['engine_audit']['components']]
    flat=[rid for component in components for rid in component]
    require(len(flat)==len(set(flat)) and set(flat)==set(provenance),'audit_component_partition')
    threads=defaultdict(list)
    for rid,row in provenance.items():
        if row['thread_id']:threads[row['thread_id']].append(rid)
    expected_purge=set()
    for group in [*components,*threads.values()]:
        candidates=set(group)&set(entries)
        if any(provenance[rid]['historical'] for rid in group) or len({tuple(provenance[rid]['cell']) for rid in candidates})>1:
            expected_purge.update(candidates)
    require(expected_purge==purged and set(audit['purge_reasons'])==purged and all(audit['purge_reasons'].values()),'symmetric_audit_purge')
    require(summary['candidate_records']==len(entries) and summary['candidate_retained_words']==sum(r['retained_words'] for r in entries.values()) and
            summary['purged_candidate_records']==len(purged) and summary['surviving_candidate_records']==len(survivors),'audit_counts')
    return survivors


def word_sample(entries,selected,preprocessing=None,config=None):
    """Predetermined lowest hashes; only aggregate confirmation leaves this function."""
    if preprocessing is None:
        import account_history_analyzer as ahas
        from account_history_analyzer.pipeline import implementation_identity
        from account_history_analyzer.io import digest
        from account_history_analyzer.config import AnalysisConfig
        from account_history_analyzer.text import preprocess
        require(Path(ahas.__file__).resolve()==Path('/tmp/ahas-pilot3-installed/account_history_analyzer/__init__.py'),'word_check_install_path')
        actual,environment,_=implementation_identity();config=AnalysisConfig.from_toml()
        require(actual==FP and environment==ENV and digest(config.analytical())==CONFIG,'word_check_frozen_identity')
        preprocessing=preprocess
    ordered=sorted(selected,key=lambda rid:hashlib.sha256(('pilot4-prepared-word-check-v1:'+rid).encode()).digest())[:20]
    words=0
    for rid in ordered:
        record=entries[rid]['record']
        before=json.dumps(record,sort_keys=True,ensure_ascii=False)
        COUNTERS['preprocessor_calls']+=1
        view=preprocessing(record,{'text_format':'markdown','default_language':'en'},config)
        count=sum(token['kind']=='word' for offsets in view['token_offsets'] for token in offsets)
        require(view['usable'] is True and count==entries[rid]['retained_words'],'sampled_retained_word_mismatch')
        require(json.dumps(record,sort_keys=True,ensure_ascii=False)==before,'word_check_mutated_source')
        words+=count
    return {'sampled_records':len(ordered),'sampled_words':words,'preprocessor_calls':len(ordered),
            'selection_rule':'lowest SHA256(pilot4-prepared-word-check-v1: + original record ID)',
            'word_representation':'independent count of kind=word token_offsets, no word_tokens sum'}


def verify(plan_path,pool_path,audit_path,audit_freeze,audit_public,prepared,public,*,sample=True,preprocessing=None,config=None):
    COUNTERS['preprocessor_calls']=0
    plan=read(plan_path);pool_path=Path(pool_path);prepared=Path(prepared);public=Path(public)
    cohort=read(prepared/'cohort.json');index=read(prepared/'index.json');summary=read(public/'selection-summary.json')
    audit=read(audit_path);freeze=read(audit_freeze);audit_receipt=read(audit_public)
    require(plan['phase']=='frozen_before_candidate_pool','plan_phase')
    plan_bindings={str(Path(r['path']).resolve()):r['sha256'] for r in plan['bound_artifacts']}
    require(len(plan_bindings)==len(plan['bound_artifacts']),'duplicate_plan_binding')
    skipped={str(Path(p).resolve()) for p in plan['metadata_files']}|{str(Path(s['archive']).resolve()) for s in plan['sources']}
    for path,digest in plan_bindings.items():
        if path not in skipped:require(sha(path)==digest,'registered_preparation_dependency_hash')
    require(all(str(Path(plan[k]).resolve()) in plan_bindings for k in ('exposure_flags','feasibility_rules')),'flags_rules_binding_coverage')
    design=read(plan['feasibility_rules'])
    fixed={'half_band_days':180,'half_target_words':5000,'half_min_records':40,'half_max_words':5500,'half_max_records':200,
           'record_word_min':20,'record_word_max':500,'all_eight_cell_word_ratio_max':'11/10',
           'all_eight_cell_record_ratio_max':'5/4','within_period_four_cell_median_span_days_max':30}
    require(all(design[k]==v for k,v in fixed.items()),'fixed_chronological_design')
    require(len(plan['strata'])==3 and {frozenset(s['communities']) for s in plan['strata']}==set(PAIR_CAPS),'fixed_strata')
    all_accounts=[a for s in plan['strata'] for a in s['accounts']]
    require(len(all_accounts)==len(set(all_accounts))<=26 and all(a==a.casefold() for a in all_accounts),'pool_account_allocation')
    require(all(s['block_cap']==PAIR_CAPS[frozenset(s['communities'])] for s in plan['strata']),'registered_pair_caps')
    flags=read(plan['exposure_flags'])['accounts'];flag_keys=[r['account_key'] for r in flags]
    require(len(flag_keys)==len(set(flag_keys)) and all(a==a.casefold() for a in flag_keys),'exposure_identity_format')
    keys=('pilot1_or_pilot2_or_private_mandatory_exclusion','pilot3_selected_scored_exposure','prior_capacity_only_exposure')
    require(all(type(r[k]) is bool for r in flags for k in keys),'exposure_flags')
    old={r['account_key'] for r in flags if r[keys[0]]};pilot3={r['account_key'] for r in flags if r[keys[1]]}
    capacity={r['account_key'] for r in flags if r[keys[2]]}
    require(len(old)==57 and len(pilot3)==60 and not old&pilot3 and not set(all_accounts)&(old|pilot3),'fixed117_exclusions')
    # Check the complete input/audit hash chain without reopening protected prose or archives.
    paths={'plan':plan_path,'pool':pool_path,'audit':audit_path,'audit_freeze':audit_freeze,'audit_public':audit_public}
    final_start=read(prepared/'start-binding.json')
    for key,path in paths.items():
        require(cohort[key+'_sha256']==sha(path)==final_start[key+'_sha256'],'cohort_'+key+'_binding')
    require(final_start['style_scores_computed']==0 and final_start['script_sha256']==plan['finalizer_sha256'],'finalizer_start_binding')
    preparation=read(pool_path.parent/'preparation.json');start=read(pool_path.parent/'start-binding.json')
    require(preparation['status']=='candidate_pool_prepared_not_audited_or_scored' and preparation['plan_sha256']==sha(plan_path)==start['plan_sha256'],'pool_preparation_binding')
    for key,path in [('candidate_pool',pool_path),('selection',pool_path.parent/'selection.json'),
                     ('original_source_lines',pool_path.parent/'original-source-lines.jsonl'),
                     ('original_source_index',pool_path.parent/'original-source-index.json'),('start_binding',pool_path.parent/'start-binding.json')]:
        require(preparation[key+'_sha256']==sha(path),'preparation_artifact_hash')
    require(freeze['state']=='frozen_before_audit' and freeze['candidate_pool_sha256']==sha(pool_path),'audit_pool_freeze')
    for key,name in [('historical_inventory','historical_inventory'),('engine','audit_engine'),('wrapper','audit_wrapper'),('rules','audit_rules')]:
        require(freeze[key+'_sha256']==sha(plan[name]),'audit_dependency_hash')
    require(audit_receipt['private_audit_sha256']==sha(audit_path) and audit_receipt['freeze_sha256']==sha(audit_freeze) and
            all(audit_receipt[k]==v for k,v in audit['summary'].items()),'audit_receipt_hash_summary')
    require(all(audit_receipt[k+'_sha256']==freeze[k+'_sha256'] for k in ('engine','wrapper','rules')),'audit_code_bindings')
    bindings={str(Path(r['path']).resolve()):r['sha256'] for r in index['bound_files']}
    require(len(bindings)==len(index['bound_files']),'duplicate_prepared_binding')
    expected_files={str((prepared/'cohort.json').resolve())}|{str(Path(c[k]).resolve()) for c in index['cases'] for k in ('input','manifest','metadata')}
    require(set(bindings)==expected_files,'prepared_file_binding_coverage')
    for path,digest in bindings.items():
        require(Path(path).is_relative_to(prepared.resolve()) and sha(path)==digest,'prepared_file_hash_or_location')
    actual_files={str(p.resolve()) for p in prepared.rglob('*') if p.is_file()}
    require(actual_files==expected_files|{str((prepared/n).resolve()) for n in ('index.json','start-binding.json')},'unexpected_prepared_files')
    require(sum(Path(p).stat().st_size for p in actual_files)<=256*1024**2,'prepared_byte_cap')
    entries={};assignments={a:s for s in plan['strata'] for a in s['accounts']}
    require(pool_path.stat().st_size<=256*1024**2,'pool_byte_cap')
    with pool_path.open() as handle:
        for line in handle:
            row=json.loads(line);record=row['record'];rid=record['id'];a=row['account_key']
            require(rid not in entries and len(entries)<100000,'pool_record_identity_or_cap')
            require(a in assignments and a not in old|pilot3 and record['account_id'].casefold()==a,'pool_protected_or_account')
            spec=assignments[a];period=row['period'];cut=seconds(spec['cut']);timestamp=seconds(record['created_utc'])
            require(period in ('early','late'),'pool_period')
            lo,hi=(cut-180*DAY,cut) if period=='early' else (cut,cut+180*DAY)
            require(lo<=timestamp<hi and row['stratum_id']==spec['stratum_id'] and row['community'] in spec['communities'] and
                    record['subreddit']==row['community'],'pool_cell_or_date')
            require(type(row['retained_words']) is int and 20<=row['retained_words']<=500 and
                    record['kind']=='comment' and record['status']=='present' and isinstance(record['text'],str) and
                    record['thread_id'] and record['language'] in (None,'en'),'pool_comment_guard')
            entries[rid]=row
    require(sum(r['retained_words'] for r in entries.values())<=2000000,'pool_word_cap')
    selection=read(pool_path.parent/'selection.json')['selected_metadata'];offsets=read(pool_path.parent/'original-source-index.json')
    require(set(selection)==set(offsets)==set(entries),'original_source_copy_coverage')
    upstream=source_metadata_binding(plan['metadata_files'],plan_bindings,selection)
    cursor=0
    with (pool_path.parent/'original-source-lines.jsonl').open('rb') as original:
        for rid in sorted(offsets,key=lambda rid:offsets[rid]['offset']):
            offset=offsets[rid];require(offset['offset']==cursor and 0<offset['bytes']<=256*1024**2,'source_copy_offsets')
            raw=original.read(offset['bytes']);cursor+=len(raw);meta=selection[rid];entry=entries[rid]
            require(len(raw)==offset['bytes'] and hashlib.sha256(raw).hexdigest()==offset['sha256']==meta['source_line_sha256'],'source_copy_hash')
            require(source_projection(json.loads(raw))==entry['record'],'source_copy_field_fidelity')
            require(meta['record_id']==rid and meta['created_utc']==entry['record']['created_utc'] and
                    all(meta[k]==entry[k] for k in ('account_key','community','stratum_id','period','retained_words')),'source_selection_metadata')
        require(not original.read(1),'source_copy_trailing_bytes')
    require(preparation['records']==len(entries) and preparation['retained_words']==sum(r['retained_words'] for r in entries.values()) and
            preparation['accounts']==len(all_accounts),'preparation_counts')
    survivors=audit_membership(entries,audit)
    cells=defaultdict(list)
    for rid in survivors:
        r=entries[rid];cells[r['account_key'],r['community'],r['period']].append({'record_id':rid,
            'timestamp':seconds(r['record']['created_utc']),'retained_words':r['retained_words']})
    expected_blocks=[];expected_stats=[];strata_stats=[];selected=set();selected_accounts=set()
    for spec in plan['strata']:
        sid=spec['stratum_id'];cut=seconds(spec['cut']);prepared_accounts={}
        for a in spec['accounts']:
            parts={role+'/'+period:prefix(cells[a,c,period],cut,period) for role,c in zip('XY',spec['communities']) for period in ('early','late')}
            if all(parts.values()) and compatible(parts,parts):prepared_accounts[a]=parts
        names=sorted(prepared_accounts,key=identity_rank)
        edges={(a,b):cost(prepared_accounts[a],prepared_accounts[b]) for a,b in combinations(names,2) if compatible(prepared_accounts[a],prepared_accounts[b])}
        pairs,total=capped_matching(names,edges,spec['block_cap'])
        strata_stats.append({'stratum_id':sid,'communities':spec['communities'],'cut':spec['cut'],'pool_accounts':len(spec['accounts']),
            'post_audit_qualified_accounts':len(names),'compatible_edges':len(edges),'planned_block_cap':spec['block_cap'],
            'selected_blocks':len(pairs),'block_deficit':spec['block_cap']-len(pairs),'selected_matching_cost':rational(total)})
        for number,pair in enumerate(pairs,1):
            block=sid+'-block-'+str(number).zfill(2);members={}
            require(not set(pair)&selected_accounts,'global_account_reuse');selected_accounts.update(pair)
            for role,a in zip('AB',pair):
                for key,part in prepared_accounts[a].items():
                    community,period=key.split('/');cid=f'{block}:{role}:{community}:{period}'
                    ids=[r['record_id'] for r in part['rows']]
                    require(not selected&set(ids),'cell_record_reuse');selected.update(ids);members[cid]=ids
                    expected_stats.append({'cell_id':cid,'block_id':block,'stratum_id':sid,'account_role':role,
                        'community_role':community,'period':period,**cell_stats(part)})
            expected_blocks.append({'block_id':block,'stratum_id':sid,'account_keys':list(pair),'communities':spec['communities'],'cut':spec['cut'],'cells':members})
    require(cohort['blocks']==expected_blocks and cohort['selected_record_ids']==sorted(selected),'cohort_prefix_matching_or_membership')
    require(read(public/'cells.json')==expected_stats,'public_cell_statistics')
    expected_summary={'strata':strata_stats,'blocks':len(expected_blocks),'accounts':len(selected_accounts),
        'selected_prior_capacity_only_exposure_accounts':len(selected_accounts&capacity),'source_records':len(selected),
        'planned_cases':16*len(expected_blocks),'independent_source_account_blocks':len(expected_blocks),
        'candidate_pool_sha256':sha(pool_path),'audit_sha256':sha(audit_path),'index_sha256':sha(prepared/'index.json'),
        'source_words':sum(entries[rid]['retained_words'] for rid in selected),'style_scores_computed':0}
    require(summary==expected_summary,'public_selection_counts_or_cost')
    expected_cases=[(block,row) for block in expected_blocks for row in factorial(block['block_id'])]
    require(index['prepared_block_count']==len(expected_blocks) and len(index['cases'])==len(expected_cases)<=80,'factorial_case_count')
    all_record_appearances=0
    for actual,(block,descriptor) in zip(index['cases'],expected_cases):
        require(all(actual[k]==v for k,v in descriptor.items()) and actual['stratum_id']==block['stratum_id'],'factorial_descriptor')
        left=block['cells'][descriptor['left_cell_id']];right=block['cells'][descriptor['right_cell_id']]
        ids=left+right
        require(ids==sorted(ids,key=lambda rid:(seconds(entries[rid]['record']['created_utc']),rid)) and len(ids)==len(set(ids)),'canonical_order')
        with Path(actual['input']).open() as f:records=[json.loads(line) for line in f]
        require(len(records)==len(ids),'case_record_count')
        for rid,record in zip(ids,records):
            expected={**entries[rid]['record'],'account_id':actual['case_id']}
            require(record==expected,'exported_record_changed_beyond_uniform_alias')
        metadata=[{'record_id':rid,'retained_words':entries[rid]['retained_words'],'created_utc':entries[rid]['record']['created_utc'],
                   'style_eligible':True,'kind':'comment'} for rid in ids]
        require(read(actual['metadata'])=={'records':metadata},'exported_metadata')
        manifest=read(actual['manifest'])
        require(set(manifest)=={'schema_version','snapshot_id','account_id','source_category','text_format','default_language','source_notes','coverage'} and
            manifest['schema_version']=='1.0.0' and manifest['snapshot_id']==manifest['account_id']==actual['case_id'] and
            manifest['source_category']=='research_corpus' and manifest['text_format']=='markdown' and manifest['default_language']=='en' and
            manifest['coverage']['status']=='sampled' and manifest['coverage']['start_utc']==records[0]['created_utc'] and
            manifest['coverage']['end_utc']==records[-1]['created_utc'],'manifest_identity_or_coverage')
        require(actual['truth_k']==(len(left) if descriptor['source_switch'] else None) and
                actual['control_junction_k']==(None if descriptor['source_switch'] else len(left)),'truth_first_late_position')
        require(all(seconds(entries[rid]['record']['created_utc'])<seconds(block['cut']) for rid in left) and
                all(seconds(entries[rid]['record']['created_utc'])>=seconds(block['cut']) for rid in right),'truth_period_membership')
        count,grid=window_grid(metadata)
        require(actual['prescore_qualified_windows']==count and actual['prescore_legal_grid']==grid,'prescore_window_or_grid')
        all_record_appearances+=len(ids)
    sample_result=word_sample(entries,selected,preprocessing,config) if sample else {'sampled_records':0,'preprocessor_calls':0,'synthetic_word_sampling_disabled':True}
    return {'status':'passed','pool_records_checked':len(entries),'pool_survivors':len(survivors),'selected_records':len(selected),
        'source_copy_bytes_verified':cursor,'upstream_metadata_verification':upstream,'selected_accounts':len(selected_accounts),'selected_blocks':len(expected_blocks),
        'prepared_cases':len(expected_cases),'prepared_record_appearances_verified':all_record_appearances,'public_cells_checked':len(expected_stats),
        'strata':strata_stats,'fixed117_exclusions_verified':True,'all_factorial_records_and_aliases_verified':True,
        'exact_capped_matching_and_prefixes_verified':True,'audit_purge_graph_verified':True,'word_sample':sample_result,
        'source_archive_reads':0,'style_scores_computed':0,'private_identifiers_published':False}


def main():
    p=argparse.ArgumentParser()
    for name in ('plan','pool','audit','audit-freeze','audit-public','prepared','public','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();start=time.monotonic()
    require(os.environ.get('AHAS_NETWORK_ISOLATION')=='linux_seccomp_socket_denial','offline_wrapper_required')
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('checker_wall_limit')));signal.alarm(1800)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    binding={'phase':'before_independent_prepared_check','checker_sha256':sha(__file__),
        'input_hashes':{key:sha(getattr(a,key)) for key in ('plan','pool','audit','audit_freeze','audit_public')},
        'prepared_index_sha256':sha(a.prepared/'index.json'),'cohort_sha256':sha(a.prepared/'cohort.json'),
        'maximum_preprocessor_calls':20,'word_check_salt':'pilot4-prepared-word-check-v1:',
        'wall_seconds_limit':1800,'address_space_bytes':4*1024**3,'source_archive_reads':0,
        'maximum_upstream_metadata_rows':3000000,'maximum_upstream_metadata_bytes':1024**3}
    save(a.out.with_suffix('.start-binding.json'),binding)
    try:result=verify(a.plan,a.pool,a.audit,a.audit_freeze,a.audit_public,a.prepared,a.public)
    except Exception as error:
        result={'status':'failed','reason':str(error) if type(error) is ValueError else type(error).__name__,
                'style_scores_computed':0,'private_identifiers_published':False,'preprocessor_calls':COUNTERS['preprocessor_calls']}
    result.update(checker_sha256=binding['checker_sha256'],wall_seconds=time.monotonic()-start,
        peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    save(a.out,result);signal.alarm(0);print(json.dumps(result,sort_keys=True))
    return 0 if result['status']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
