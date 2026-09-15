"""Select one five-sample diagnostic using only already-audited metadata."""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
from itertools import combinations, permutations
import json
import os
from pathlib import Path
import resource
import signal
import sys

P4 = Path(__file__).resolve().parents[2]/'pilot4_chronological_controls'
sys.path.insert(0, str(P4/'scripts'))
from metadata_feasibility import select_prefix, seconds, jsonable
from chronology_math import reconstruct_windows, legal_grid
from run_full_chronology import sha, write

KEYS = ('anchor', 'late_AX', 'late_BX', 'late_AY', 'late_BY')
CONDITIONS = ('continuity_same_community', 'switch_same_community',
              'continuity_changed_community', 'switch_changed_community')


def identity(value):
    return hashlib.sha256(('pilot5-anchor-order-v1\0'+value.casefold()).encode()).hexdigest()


def metadata(cell, entries):
    return [{'record_id':r['record_id'], 'created_utc':entries[r['record_id']]['record']['created_utc'],
             'retained_words':r['retained_words'], 'kind':'comment', 'style_eligible':True}
            for r in cell['rows']]


def evaluate(samples, entries):
    failures=[]
    missing=[k for k in KEYS if samples[k] is None]
    if missing:
        return {'valid':False, 'reason_codes':['unavailable_sample:'+k for k in missing],
                'cost':None, 'qualified_window_counts':None}
    cells=[samples[k] for k in KEYS]
    if Fraction(max(c['retained_words'] for c in cells),min(c['retained_words'] for c in cells)) > Fraction(11,10):
        failures.append('five_sample_word_ratio_above_11_over_10')
    if Fraction(max(c['records'] for c in cells),min(c['records'] for c in cells)) > Fraction(5,4):
        failures.append('five_sample_record_ratio_above_5_over_4')
    late=cells[1:]
    if max(c['median_timestamp'] for c in late)-min(c['median_timestamp'] for c in late)>30*86400:
        failures.append('four_late_median_span_above_30_days')
    windows=[sum(w['qualified'] for w in reconstruct_windows(metadata(cells[0],entries)+metadata(c,entries))) for c in late]
    if min(windows)<8:
        failures.append('fewer_than_eight_qualified_windows')
    cost=sum((abs(a['median_timestamp']-b['median_timestamp'])/Fraction(180*86400)
              for a,b in combinations(late,2)),Fraction())
    cost+=sum((Fraction(abs(a['retained_words']-b['retained_words']),5000)+
               Fraction(abs(a['records']-b['records']),40) for a,b in combinations(cells,2)),Fraction())
    return {'valid':not failures,'reason_codes':failures,'cost':cost,
            'qualified_window_counts':windows,
            'late_median_span_days':Fraction(max(c['median_timestamp'] for c in late)-min(c['median_timestamp'] for c in late),86400),
            'five_sample_word_ratio':Fraction(max(c['retained_words'] for c in cells),min(c['retained_words'] for c in cells)),
            'five_sample_record_ratio':Fraction(max(c['records'] for c in cells),min(c['records'] for c in cells))}


def quantile(values,p):
    values=sorted(values);at=(len(values)-1)*p;lo=int(at)
    return values[lo]+(values[min(lo+1,len(values)-1)]-values[lo])*(at-lo)


def public_cell(key,cell):
    lengths=[r['retained_words'] for r in cell['rows']]
    return {'sample_key':key,'records':cell['records'],'retained_words':cell['retained_words'],
            'word_target_overshoot':cell['retained_words']-5000,
            'longest_record_word_share':max(lengths)/sum(lengths),
            'word_length_quantiles':{str(p):quantile(lengths,p) for p in (0,.25,.5,.75,1)},
            'median_timestamp':jsonable(cell['median_timestamp']),
            'first_timestamp':cell['first_timestamp'],'last_timestamp':cell['last_timestamp']}


def prepare(plan_path,out,public_out):
    if os.environ.get('AHAS_NETWORK_ISOLATION')!='linux_seccomp_socket_denial':
        raise RuntimeError('Offline wrapper required')
    plan=json.loads(Path(plan_path).read_bytes())
    if plan['phase']!='frozen_before_five_sample_enumeration' or plan['script_sha256']!=sha(__file__):
        raise ValueError('Pre-enumeration registration changed')
    for row in plan['bindings']:
        if sha(row['path'])!=row['sha256']:raise ValueError('Bound input changed')
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);signal.alarm(600)
    out=Path(out);out.mkdir(mode=0o700,exist_ok=False)
    public_out=Path(public_out);public_out.mkdir(exist_ok=False)
    write(out/'start-binding.json',{'plan_sha256':sha(plan_path),'script_sha256':sha(__file__),
          'started_utc':datetime.now(timezone.utc).isoformat(),'style_calls':0})
    audit=json.loads(Path(plan['audit']).read_bytes());old_plan=json.loads(Path(plan['preparation_plan']).read_bytes())
    if not audit['summary']['gate_b_ready']:raise ValueError('Completed available-content audit required')
    entries={r['record']['id']:r for r in map(json.loads,Path(plan['pool']).read_text().splitlines())}
    survivors=set(audit['surviving_candidate_ids'])
    if len(entries)!=2447 or len(survivors)!=2252 or not survivors<=set(entries):raise ValueError('Audited pool changed')
    design=json.loads(Path(plan['original_prefix_rules']).read_bytes())
    cells={};candidates=[];sample_maps={}
    for spec in old_plan['strata']:
        sid=spec['stratum_id'];cut=seconds(spec['cut'])
        for account in spec['accounts']:
            for community in spec['communities']:
                for period in ('early','late'):
                    rows=[{'record_id':rid,'timestamp':seconds(e['record']['created_utc']),
                           'retained_words':e['retained_words']} for rid,e in entries.items()
                          if rid in survivors and (e['account_key'],e['community'],e['period'])==(account,community,period)]
                    cells[account,community,period]=select_prefix(rows,cut,period,design)
        for a,b in permutations(sorted(spec['accounts'],key=identity),2):
            for x,y in permutations(sorted(spec['communities']),2):
                samples=dict(zip(KEYS,[cells[a,x,'early'],cells[a,x,'late'],cells[b,x,'late'],cells[a,y,'late'],cells[b,y,'late']],strict=True))
                cid='candidate-'+str(len(candidates)+1).zfill(2)
                result=evaluate(samples,entries)
                candidates.append({'candidate_id':cid,'stratum_id':sid,'cut':spec['cut'],'account_a':a,'account_b':b,
                                   'community_x':x,'community_y':y,**result})
                sample_maps[cid]=samples
    if len(candidates)!=20:raise ValueError('Expected all20 directional candidates')
    valid=[c for c in candidates if c['valid']]
    winner=min(valid,key=lambda c:(c['cost'],c['stratum_id'],identity(c['account_a']),identity(c['account_b']),c['community_x'],c['community_y'])) if valid else None
    public_candidates=[{k:jsonable(v) for k,v in c.items() if k not in ('account_a','account_b')} for c in candidates]
    write(public_out/'candidate-enumeration.json',{'candidates':public_candidates,'valid_candidates':len(valid),
          'selected_candidate_id':winner['candidate_id'] if winner else None,'selection_uses_style_results':False,
          'registration_sha256':sha(plan_path)})
    if winner is None:
        write(out/'selection.json',{'candidates':jsonable(candidates),'selected':None});return
    samples=sample_maps[winner['candidate_id']]
    sample_ids={k:[r['record_id'] for r in c['rows']] for k,c in samples.items()}
    flat=[rid for ids in sample_ids.values() for rid in ids]
    if len(flat)!=len(set(flat)):raise ValueError('Five original samples must be disjoint')
    block='pilot5-diagnostic-01';cases=[];bound=[]
    for condition,late in zip(CONDITIONS,KEYS[1:],strict=True):
        switch=condition.startswith('switch_');changed=condition.endswith('changed_community')
        case_id=block+':AX:'+condition;directory=out/case_id;directory.mkdir(mode=0o700)
        ids=sample_ids['anchor']+sample_ids[late]
        if ids!=sorted(ids,key=lambda rid:(seconds(entries[rid]['record']['created_utc']),rid)):
            raise ValueError('Source chronology differs from early-plus-late ordering')
        records=[dict(entries[rid]['record'],account_id=case_id) for rid in ids]
        input_path=directory/'records.jsonl';manifest_path=directory/'snapshot.json';meta_path=directory/'metadata.json'
        with input_path.open('x') as f:
            for record in records:f.write(json.dumps(record,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n')
        write(manifest_path,{'schema_version':'1.0.0','snapshot_id':case_id,'account_id':case_id,
            'source_category':'research_corpus','text_format':'markdown','default_language':'en',
            'source_notes':'Exploratory shared earlier sample with four continuations; source account proxies, original writing and dates preserved. English is a corpus-level assumption.',
            'coverage':{'status':'sampled','start_utc':records[0]['created_utc'],'end_utc':records[-1]['created_utc'],
                        'notes':'Whole-comment sample, not a complete account history.'}})
        meta=metadata(samples['anchor'],entries)+metadata(samples[late],entries);write(meta_path,{'records':meta})
        windows=reconstruct_windows(meta)
        cases.append({'case_id':case_id,'block_id':block,'stratum_id':winner['stratum_id'],'anchor_id':'AX',
            'condition':condition,'source_switch':switch,'community_change':changed,
            'left_cell_id':block+':A:X:early','right_cell_id':block+':'+late[-2]+':'+late[-1]+':late',
            'input':str(input_path.resolve()),'manifest':str(manifest_path.resolve()),'metadata':str(meta_path.resolve()),
            'truth_k':len(sample_ids['anchor']) if switch else None,
            'control_junction_k':None if switch else len(sample_ids['anchor']),
            'prescore_qualified_windows':sum(w['qualified'] for w in windows),'prescore_legal_grid':legal_grid(windows)})
        bound.extend({'path':str(f.resolve()),'sha256':sha(f)} for f in (input_path,manifest_path,meta_path))
    write(out/'selection.json',{'candidates':jsonable(candidates),'selected':jsonable(winner),
          'source_samples':sample_ids,'plan_sha256':sha(plan_path),'audit_sha256':sha(plan['audit'])})
    bound.append({'path':str((out/'selection.json').resolve()),'sha256':sha(out/'selection.json')})
    write(out/'index.json',{'cases':cases,'bound_files':bound,'prepared_block_count':1})
    write(public_out/'samples.json',[public_cell(k,samples[k]) for k in KEYS])
    write(public_out/'selection-summary.json',{'selected_candidate_id':winner['candidate_id'],'stratum_id':winner['stratum_id'],
          'community_x':winner['community_x'],'community_y':winner['community_y'],'cut':winner['cut'],
          'source_samples':5,'source_accounts':2,'independent_diagnostic_units':1,'histories':4,
          'unique_records':len(flat),'unique_retained_words':sum(entries[r]['retained_words'] for r in flat),
          'shared_anchor_records':len(sample_ids['anchor']),'qualified_windows_per_history':winner['qualified_window_counts'],
          'metadata_cost':jsonable(winner['cost']),'index_sha256':sha(out/'index.json'),
          'selection_sha256':sha(out/'selection.json'),'style_calls':0,'new_preprocessor_calls':0,
          'audit_reuse':'Subset of2252survivors; prior conservative cross-cell and historical purges retained.'})
    total=sum(f.stat().st_size for f in out.rglob('*') if f.is_file())
    if total>64*1024**2:raise RuntimeError('Prepared output exceeds64MiB')
    for f in out.rglob('*'):
        if f.is_file():f.chmod(0o600)
    print(json.dumps({'candidate_directions':20,'valid_directions':len(valid),'selected':winner['candidate_id'],
                      'histories':4,'prepared_bytes':total,'style_calls':0}))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('plan','out','public-out'):p.add_argument('--'+key,required=True,type=Path)
    a=p.parse_args();prepare(a.plan,a.out,a.public_out)
