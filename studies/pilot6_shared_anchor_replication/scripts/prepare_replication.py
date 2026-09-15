"""Reuse frozen buffer, source-conversion and shared-anchor helpers for Pilot6."""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime,timezone
from fractions import Fraction
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[3]
P4=ROOT/'studies/pilot4_chronological_controls/scripts'
P5=ROOT/'studies/pilot5_shared_anchor/scripts'
sys.path[:0]=[str(Path(__file__).parent),str(P5),str(P4)]
from metadata_replication import flags_excluded,tie,DESIGN
from metadata_feasibility import select_prefix,seconds,jsonable
from prepare_chronology_pool import buffer_prefix
from prepare_shared_anchor import KEYS,CONDITIONS,evaluate,metadata,public_cell
from chronology_math import reconstruct_windows,legal_grid
from run_full_chronology import sha,write


def read(path):return json.loads(Path(path).read_bytes())


def checked_plan(path,phase):
    plan=read(path)
    if os.environ.get('AHAS_NETWORK_ISOLATION')!='linux_seccomp_socket_denial':raise ValueError('Offline wrapper required')
    if plan['phase']!=phase or plan['script_sha256']!=sha(__file__):raise ValueError('Frozen preparation plan required')
    bindings={str(Path(row['path']).resolve()):row['sha256'] for row in plan['bindings']}
    if len(bindings)!=len(plan['bindings']):raise ValueError('Duplicate preparation binding')
    needed=[__file__,str(Path(__file__).parent/'metadata_replication.py')]
    needed += [str(P4/name) for name in ('metadata_feasibility.py','metadata_feasibility_v2.py','chronology_math.py','run_full_chronology.py','prepare_chronology_pool.py')]
    needed += [str(P5/'prepare_shared_anchor.py'),plan['protocol']]
    fields={'frozen_before_pilot5_protection_extension':('old_inventory','pilot5_selection','pilot4_pool'),
            'frozen_before_replication_buffer':('provisional_pairs','exposure_flags','pilot5_selection','converter'),
            'frozen_before_replication_final_cohort':('buffer_selection','audit','pool','exposure_flags','pilot5_selection')}
    needed += [plan[k] for k in fields[phase]]
    if phase=='frozen_before_replication_buffer':
        needed += plan['metadata_files']+[row['archive'] for row in plan['sources']]
        needed += [str(Path(plan['converter']).parent/'cohort_selection.py')]
    if not {str(Path(p).resolve()) for p in needed}<=set(bindings):raise ValueError('Missing consumed preparation binding')
    for path,digest in bindings.items():
        if sha(path)!=digest:raise ValueError('Preparation binding changed')
    resource.setrlimit(resource.RLIMIT_AS,(4294967296,)*2)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Preparation wall limit')));signal.alarm(1800)
    return plan


def protect(plan_path,out,public):
    plan=checked_plan(plan_path,'frozen_before_pilot5_protection_extension')
    old=read(plan['old_inventory']);selection=read(plan['pilot5_selection'])
    ids=[rid for values in selection['source_samples'].values() for rid in values]
    if len(ids)!=216 or len(set(ids))!=216:raise ValueError('Pilot5 distinct216 original comments required')
    accounts={selection['selected'][k] for k in ('account_a','account_b')}
    out=Path(out);out.mkdir(mode=0o700,parents=True,exist_ok=False);path=out/'pilot5-scored-original-records.jsonl'
    found=set();records=[]
    with Path(plan['pilot4_pool']).open() as source,path.open('x') as target:
        for line in source:
            row=json.loads(line);rid=row['record']['id']
            if rid not in ids:continue
            if rid in found or row['account_key'] not in accounts:raise ValueError('Pilot5 original membership mismatch')
            found.add(rid);target.write(json.dumps({'record':row['record'],'account_key':row['account_key'],'split':'evaluation'},sort_keys=True,ensure_ascii=False)+'\n')
            records.append({'record_id':rid,'account_key':row['account_key'],'original_split':'evaluation'})
    if found!=set(ids):raise ValueError('Missing Pilot5 original source')
    source={'path':str(path.resolve()),'bytes':path.stat().st_size,'sha256':sha(path),'source_id':'pilot5_scored_shared_anchor',
      'collection':'pilot5_scored_shared_anchor','format':'wrapped_record_jsonl','record_count':216,'records_metadata':records,
      'account_keys':sorted(accounts),'distinct_source_accounts':2,'prose_inspected_by_model':False,'feature_vectors_read':False}
    extended={**old,'files':old['files']+[source],'total_source_files':old['total_source_files']+1,
              'total_source_record_rows':old['total_source_record_rows']+216,'total_source_file_bytes':old['total_source_file_bytes']+path.stat().st_size,
              'pilot6_extension':{'old_inventory_sha256':sha(plan['old_inventory']),'selection_sha256':sha(plan['pilot5_selection']),'plan_sha256':sha(plan_path)}}
    write(out/'historical-audit-source-inventory.json',extended)
    write(public,{'added_original_comments':216,'added_source_accounts':2,'historical_inventory_sha256':sha(out/'historical-audit-source-inventory.json'),
        'plan_sha256':sha(plan_path),'style_calls':0,'source_text_changed':False,'prior_inventory_changed':False})
    for p in out.iterdir():p.chmod(0o600)


def cell_specs(pair):
    a,b=pair['account_a'],pair['account_b'];x,y=pair['community_x'],pair['community_y']
    return dict(zip(KEYS,[(a,x,'early'),(a,x,'late'),(b,x,'late'),(a,y,'late'),(b,y,'late')],strict=True))


def buffer(plan_path,out,public):
    started=time.monotonic();plan=checked_plan(plan_path,'frozen_before_replication_buffer')
    pairs=read(plan['provisional_pairs'])['pairs']
    excluded,_=flags_excluded(read(plan['exposure_flags']),read(plan['pilot5_selection']))
    accounts=[p[k] for p in pairs for k in ('account_a','account_b')]
    if len(pairs)>20 or len(accounts)!=len(set(accounts)) or set(accounts)&excluded:raise ValueError('Provisional pool identity violation')
    timelines=defaultdict(list);seen=set();count=0
    for source in plan['metadata_files']:
        with Path(source).open() as f:
            for line in f:
                count+=1
                if count>3000000:raise RuntimeError('Metadata row cap')
                row=json.loads(line)
                if row['account_key'] not in accounts or row['reason'] is not None:continue
                rid=row['record_id']
                if rid in seen:raise ValueError('Duplicate original source metadata')
                seen.add(rid);timelines[row['account_key'],row['community']].append(row)
    selected={};memberships={};stats=[]
    for pair in pairs:
        pstats=[]
        for key,(account,community,period) in cell_specs(pair).items():
            rows=buffer_prefix(timelines[account,community],seconds(pair['cut']),period)
            memberships[pair['pair_id'],key]=[r['record_id'] for r in rows]
            for row in rows:
                if row['record_id'] in selected:raise ValueError('Original record reused across source buffers')
                selected[row['record_id']]={**row,'stratum_id':pair['stratum_id'],'period':period,'pair_id':pair['pair_id'],'sample_key':key}
            pstats.append({'sample_key':key,'records':len(rows),'retained_words':sum(r['retained_words'] for r in rows)})
        stats.append({'pair_id':pair['pair_id'],'samples':pstats})
    if len(selected)>100000 or sum(r['retained_words'] for r in selected.values())>2000000:raise RuntimeError('Candidate pool ceiling')
    out=Path(out);out.mkdir(mode=0o700,parents=True,exist_ok=False)
    write(out/'selection.json',{'pairs':pairs,'selected_metadata':selected,'sample_memberships':[{'pair_id':pid,'sample_key':key,'ids':ids} for (pid,key),ids in memberships.items()]})
    if not selected:
        write(public,{'status':'empty_provisional_pool','candidate_records':0,'provisional_pairs':len(pairs),'style_calls':0});return
    sys.path.insert(0,str(Path(plan['converter']).parent))
    spec=importlib.util.spec_from_file_location('p6_bound_converter',plan['converter']);converter=importlib.util.module_from_spec(spec);spec.loader.exec_module(converter)
    found=set();index={};source_rows=0;uncompressed=0;receipts=[];written=0
    with (out/'candidate-pool.jsonl').open('xb') as pool,(out/'original-source-lines.jsonl').open('xb') as originals:
        for source in plan['sources']:
            digest=__import__('hashlib').sha256();rows=0
            with zipfile.ZipFile(source['archive']) as z:
                member=z.getinfo('utterances.jsonl');uncompressed+=member.file_size
                if uncompressed>16*1024**3:raise RuntimeError('Source expansion ceiling')
                with z.open(member) as f:
                    for line in f:
                        rows+=1;source_rows+=1;digest.update(line)
                        if source_rows>25000000:raise RuntimeError('Source row ceiling')
                        raw=json.loads(line)
                        if raw.get('root')==raw['id'] or raw['id'] not in selected:continue
                        expected=selected[raw['id']]
                        if raw['id'] in found or expected['community']!=source['community'] or __import__('hashlib').sha256(line).hexdigest()!=expected['source_line_sha256']:
                            raise ValueError('Selected original source identity changed')
                        found.add(raw['id']);record=converter.convert_source(raw,expected)
                        entry={k:expected[k] for k in ('account_key','community','period','stratum_id','retained_words','pair_id','sample_key')};entry['record']=record
                        encoded=(json.dumps(entry,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode();written+=len(encoded)+len(line)
                        if written>256*1024**2:raise RuntimeError('Candidate output ceiling')
                        index[raw['id']]={'offset':originals.tell(),'bytes':len(line),'sha256':__import__('hashlib').sha256(line).hexdigest()}
                        originals.write(line);pool.write(encoded)
            receipts.append({'community':source['community'],'rows':rows,'utterances_sha256':digest.hexdigest(),'archive_sha256':sha(source['archive'])})
            print(json.dumps({'source_community':source['community'],'matched_original_records':len(found),'style_calls':0}),flush=True)
    if found!=set(selected):raise ValueError('Missing original selected records')
    write(out/'original-source-index.json',index)
    if sum(p.stat().st_size for p in out.iterdir())>256*1024**2:raise RuntimeError('Final candidate output ceiling')
    write(public,{'status':'prepared_not_audited','provisional_pairs':len(pairs),'candidate_records':len(selected),'candidate_retained_words':sum(r['retained_words'] for r in selected.values()),
       'samples':stats,'sources':receipts,'source_rows':source_rows,'source_uncompressed_bytes':uncompressed,'candidate_pool_sha256':sha(out/'candidate-pool.jsonl'),
       'selection_sha256':sha(out/'selection.json'),'plan_sha256':sha(plan_path),'wall_seconds':time.monotonic()-started,
       'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,'style_calls':0})
    for p in out.iterdir():p.chmod(0o600)


def finalize(plan_path,out,public):
    plan=checked_plan(plan_path,'frozen_before_replication_final_cohort')
    selection=read(plan['buffer_selection']);pairs=selection['pairs'];audit=read(plan['audit'])
    if not (audit['summary'].get('gate_b_ready') is True and audit.get('actionable') is True
            and audit['summary'].get('available_content_and_grouping_audit_complete') is True):
        raise ValueError('Completed available-content audit required')
    excluded,_=flags_excluded(read(plan['exposure_flags']),read(plan['pilot5_selection']))
    accounts=[p[k] for p in pairs for k in ('account_a','account_b')]
    if len(pairs)>20 or len(accounts)!=len(set(accounts)) or set(accounts)&excluded:raise ValueError('Final source identity violation')
    if len({p['pair_id'] for p in pairs})!=len(pairs):raise ValueError('Repeated provisional pair ID')
    entries={}
    for r in map(json.loads,Path(plan['pool']).read_text().splitlines()):
        rid=r['record']['id']
        if rid in entries:raise ValueError('Repeated pool original ID')
        entries[rid]=r
    surviving=audit['surviving_candidate_ids'];purged=audit['purge_record_ids']
    survivors=set(surviving);purges=set(purged)
    if len(surviving)!=len(survivors) or len(purged)!=len(purges) or survivors&purges or survivors|purges!=set(entries):
        raise ValueError('Audit partition differs from candidate pool')
    available=[];all_rows=[];sample_maps={}
    for pair in pairs:
        samples={}
        for key,(a,c,period) in cell_specs(pair).items():
            rows=[{'record_id':rid,'timestamp':seconds(e['record']['created_utc']),'retained_words':e['retained_words']} for rid,e in entries.items()
                  if rid in survivors and (e['account_key'],e['community'],e['period'])==(a,c,period)]
            samples[key]=select_prefix(rows,seconds(pair['cut']),period,DESIGN)
        result=evaluate(samples,entries)
        row={**pair,'five_sample_word_ratio':None,'five_sample_record_ratio':None,'late_median_span_days':None,**result}
        all_rows.append(row);sample_maps[pair['pair_id']]=samples
        if row['valid']:available.append(row)
    chosen=sorted(available,key=lambda row:(row['cost'],tie(row)))[:10]
    chosen_ids={r['pair_id'] for r in chosen};out=Path(out);out.mkdir(mode=0o700,parents=True,exist_ok=False);pub=Path(public);pub.mkdir(parents=True,exist_ok=False)
    public_rows=[];cohort=[]
    for row in all_rows:
        status='selected_for_replication' if row['pair_id'] in chosen_ids else ('eligible_outside_fixed_ten_pair_cohort' if row['valid'] else 'unavailable_after_audit')
        public_rows.append({k:jsonable(v) for k,v in dict(row,selection_status=status).items() if k not in ('account_a','account_b')})
    for pair in chosen:
        pid=pair['pair_id'];directory=out/pid;directory.mkdir(mode=0o700);samples=sample_maps[pid]
        sample_ids={key:[r['record_id'] for r in value['rows']] for key,value in samples.items()}
        flat=[rid for ids in sample_ids.values() for rid in ids]
        if len(flat)!=len(set(flat)):raise ValueError('Five source samples overlap')
        write(directory/'selection.json',{'selected':jsonable(pair),'source_samples':sample_ids,'plan_sha256':sha(plan_path),'audit_sha256':sha(plan['audit'])})
        cases=[];bound=[{'path':str((directory/'selection.json').resolve()),'sha256':sha(directory/'selection.json')}]
        for condition,late in zip(CONDITIONS,KEYS[1:],strict=True):
            cid=pid+':AX:'+condition;case_dir=directory/cid;case_dir.mkdir(mode=0o700)
            ids=sample_ids['anchor']+sample_ids[late]
            if ids!=sorted(ids,key=lambda rid:(seconds(entries[rid]['record']['created_utc']),rid)):raise ValueError('Original chronology differs')
            records=[dict(entries[rid]['record'],account_id=cid) for rid in ids]
            input_path=case_dir/'records.jsonl';manifest=case_dir/'snapshot.json';meta_path=case_dir/'metadata.json'
            with input_path.open('x') as f:
                for r in records:f.write(json.dumps(r,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n')
            write(manifest,{'schema_version':'1.0.0','snapshot_id':cid,'account_id':cid,'source_category':'research_corpus','text_format':'markdown','default_language':'en',
                'source_notes':'Registered bounded shared-anchor replication; source-account proxies, original writing and timestamps. English is a corpus-level assumption.',
                'coverage':{'status':'sampled','start_utc':records[0]['created_utc'],'end_utc':records[-1]['created_utc'],'notes':'Whole-comment sample, not a complete account history.'}})
            meta=metadata(samples['anchor'],entries)+metadata(samples[late],entries);write(meta_path,{'records':meta});windows=reconstruct_windows(meta)
            switch=condition.startswith('switch_')
            cases.append({'case_id':cid,'block_id':pid,'stratum_id':pair['stratum_id'],'anchor_id':'AX','condition':condition,'source_switch':switch,
                'community_change':condition.endswith('changed_community'),'left_cell_id':pid+':A:X:early','right_cell_id':pid+':'+late[-2]+':'+late[-1]+':late',
                'input':str(input_path.resolve()),'manifest':str(manifest.resolve()),'metadata':str(meta_path.resolve()),'truth_k':len(sample_ids['anchor']) if switch else None,
                'control_junction_k':None if switch else len(sample_ids['anchor']),'prescore_qualified_windows':sum(w['qualified'] for w in windows),'prescore_legal_grid':legal_grid(windows)})
            bound.extend({'path':str(p.resolve()),'sha256':sha(p)} for p in (input_path,manifest,meta_path))
        write(directory/'index.json',{'cases':cases,'bound_files':bound,'prepared_block_count':1})
        cohort.append({'pair_id':pid,'index':str((directory/'index.json').resolve()),'source_account_keys':[pair['account_a'],pair['account_b']]})
        write(pub/(pid+'-samples.json'),{'pair_id':pid,'samples':[public_cell(key,samples[key]) for key in KEYS],'unique_comments':len(flat),
            'unique_retained_words':sum(entries[rid]['retained_words'] for rid in flat),'shared_anchor_records':len(sample_ids['anchor'])})
    excluded,_=flags_excluded(read(plan['exposure_flags']),read(plan['pilot5_selection']))
    write(out/'cohort-prepared.json',{'target_pairs':10,'pairs':cohort,'excluded_account_keys':sorted(excluded),'finalization_plan_sha256':sha(plan_path)})
    write(pub/'pair-availability.json',public_rows)
    write(pub/'selection-summary.json',{'target_new_pairs':10,'provisional_pairs':len(pairs),'eligible_after_audit':len(available),'selected_new_pairs':len(chosen),
          'selected_source_accounts':len(chosen)*2,'planned_main_histories':len(chosen)*4,'planned_replays':len(chosen)*4,
          'pair_shortfall':10-len(chosen),'cohort_prepared_sha256':sha(out/'cohort-prepared.json'),'finalization_plan_sha256':sha(plan_path),
          'style_calls':0,'grid_locations_used_for_selection':False})
    if sum(p.stat().st_size for p in out.rglob('*') if p.is_file())>256*1024**2:raise RuntimeError('Final prepared output ceiling')
    for p in out.rglob('*'):
        if p.is_file():p.chmod(0o600)
    print(json.dumps({'selected_pairs':len(chosen),'main_histories':len(chosen)*4,'unavailable_provisional_pairs':len(pairs)-len(available),'style_calls':0}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=('protect','buffer','finalize'))
    for n in ('plan','out','public'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();globals()[a.command](a.plan,a.out,a.public)
