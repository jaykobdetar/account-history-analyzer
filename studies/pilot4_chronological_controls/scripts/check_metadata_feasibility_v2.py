"""Independent metadata-only recomputation of all fixed extended pilot4 feasibility cuts.

No AHAS, preparation, or feasibility implementation is imported. This check
reads the existing eligibility metadata once, reconstructs prefixes and exact
matching objectives, and checks private witnesses without publishing identities.
"""
from collections import Counter,defaultdict
from datetime import datetime,timezone
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import resource
import signal
import time

DAY=86400
CELLS=('X/early','X/late','Y/early','Y/late')
EPOCH=datetime(1970,1,1,tzinfo=timezone.utc)


def require(value,code):
    if not value:
        raise ValueError(code)


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def canonical(v):
    return (json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()


def read(path):
    return json.loads(Path(path).read_bytes())


def save(path,v):
    with Path(path).open('xb') as f:
        f.write(canonical(v))


def stamp(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    require(dt.utcoffset() is not None and dt.utcoffset().total_seconds()==0 and dt.microsecond==0,'noninteger_UTC')
    return (dt-EPOCH).days*DAY+(dt-EPOCH).seconds


def rank(a):
    return hashlib.sha256(('pilot4-feasibility-identity-order-v1\0'+a.casefold()).encode()).hexdigest()


def rat(x):
    x=Fraction(x)
    return {'numerator':x.numerator,'denominator':x.denominator}


def cell(records,cut,period):
    # Records are timestamp, source-ID, retained-words tuples. Filter first,
    # then independently scan chronological order outward from the cut.
    lo,hi=(cut-180*DAY,cut) if period=='early' else (cut,cut+180*DAY)
    selected=[r for r in records if lo<=r[0]<hi and 20<=r[2]<=500]
    selected.sort(key=(lambda r:(-r[0],r[1])) if period=='early' else (lambda r:(r[0],r[1])))
    words=0
    for i,r in enumerate(selected,1):
        words+=r[2]
        if words>5500 or i>200:
            return None
        if words>=5000 and i>=40:
            kept=sorted(selected[:i])
            median=Fraction(kept[(i-1)//2][0]+kept[i//2][0],2)
            return {'records':i,'words':words,'median':median,'rows':kept}
    return None


def compatible(a,b):
    cells=[*a.values(),*b.values()]
    words=[r['words'] for r in cells]; counts=[r['records'] for r in cells]
    return (max(words)*10<=min(words)*11 and max(counts)*4<=min(counts)*5 and
            all(max(side[c+'/'+period]['median'] for side in (a,b) for c in 'XY')-
                min(side[c+'/'+period]['median'] for side in (a,b) for c in 'XY')<=30*DAY
                for period in ('early','late')))


def pair_cost(a,b):
    return sum((abs(a[k]['median']-b[k]['median'])/(180*DAY)+
                Fraction(abs(a[k]['words']-b[k]['words']),5000)+
                Fraction(abs(a[k]['records']-b[k]['records']),40) for k in CELLS),Fraction())


def matching(names,edges):
    """Independent first-vertex exhaustive recurrence with optional unmatched."""
    names=tuple(names); costs={(names.index(a),names.index(b)):Fraction(v) for (a,b),v in edges.items()}
    @lru_cache(None)
    def solve(vertices):
        if not vertices:
            return (0,Fraction(),())
        a,rest=vertices[0],vertices[1:]
        possibilities=[solve(rest)]
        for b in rest:
            if (a,b) in costs:
                count,cost,pairs=solve(tuple(c for c in rest if c!=b))
                possibilities.append((count-1,cost+costs[a,b],((a,b),)+pairs))
        return min(possibilities)
    negative,cost,pairs=solve(tuple(range(len(names))))
    return -negative,cost,[(names[a],names[b]) for a,b in pairs]


def verify(plan_path,flags_path,registration_path,census,private,receipt_path,prior_check_path):
    plan,registration,summary,witness=map(read,(plan_path,registration_path,census/'feasibility-summary.json',private))
    require(summary['plan_sha256']==sha(plan_path)==registration['plan_sha256'],'plan_binding')
    require(summary['registration_sha256']==sha(registration_path)==witness['registration_sha256'],'registration_binding')
    require(summary['exposure_flags_sha256']==sha(flags_path)==plan['exposure_flags_sha256'],'flags_binding')
    receipt=read(receipt_path)
    require(receipt['exit_code']==0 and registration['registered_utc']<receipt['started_utc'],'fresh_successful_registered_run')
    fixed={'half_band_days':180,'record_word_min':20,'record_word_max':500,'half_target_words':5000,
           'half_min_records':40,'half_max_words':5500,'half_max_records':200,
           'all_eight_cell_word_ratio_max':'11/10','all_eight_cell_record_ratio_max':'5/4',
           'within_period_four_cell_median_span_days_max':30,'intended_maximum_blocks_per_stratum':2}
    require(all(plan[k]==v for k,v in fixed.items()),'fixed_criteria_changed')
    require(len(plan['cuts'])==101 and len(set(plan['cuts']))==101 and len(plan['community_pairs'])==2 and plan['stratum_ids']==['stratum-04','stratum-05'],'fixed_grid_changed')
    flags=read(flags_path)['accounts']
    mandatory={r['account_key'] for r in flags if r['pilot1_or_pilot2_or_private_mandatory_exclusion']}
    scored={r['account_key'] for r in flags if r['pilot3_selected_scored_exposure']}
    require(len(mandatory)==57 and len(scored)==60 and not mandatory&scored,'known_exclusion_counts')
    excluded=mandatory|scored
    capacity_only={r['account_key'] for r in flags if r['prior_capacity_only_exposure']}
    requested={c for pair in plan['community_pairs'] for c in pair}
    chosen_rows={r['record_id']:r for s in witness['strata'].values() for a in s['candidate_cells'].values()
                 for c in a.values() for r in c['rows']}
    require(all(r['account_key'].casefold() not in excluded for r in chosen_rows.values()),'protected_witness')
    seen=set(); timelines=defaultdict(list); counts=Counter(); confirmed=set(); total_bytes=0
    for source in plan['source_metadata']:
        digest=hashlib.sha256(); size=0
        with Path(source['path']).open('rb') as f:
            for raw in f:
                size+=len(raw);total_bytes+=len(raw);digest.update(raw)
                require(total_bytes<=1024**3,'metadata_byte_cap')
                counts['metadata_rows']+=1
                require(counts['metadata_rows']<=3000000,'metadata_row_cap')
                r=json.loads(raw);rid=r['record_id'];a=r['account_key'].casefold()
                require(rid not in seen,'duplicate_metadata_record');seen.add(rid)
                if a in excluded:
                    counts['excluded_rows']+=1;continue
                if r['reason'] is not None:
                    counts['prior_ineligible_rows']+=1;continue
                if r['community'] not in requested:
                    counts['outside_registered_communities']+=1;continue
                if type(r['retained_words']) is not int or not 20<=r['retained_words']<=500:
                    counts['outside_registered_record_word_bounds']+=1;continue
                ts=stamp(r['created_utc']);timelines[a,r['community']].append((ts,rid,r['retained_words']))
                counts['eligible_registered_metadata_rows']+=1;counts['eligible_registered_words']+=r['retained_words']
                if rid in chosen_rows:
                    require(chosen_rows[rid]=={**r,'timestamp':ts},'witness_original_metadata_changed')
                    confirmed.add(rid)
        require(size==source['bytes'] and digest.hexdigest()==source['sha256'],'source_metadata_hash')
    require(confirmed==set(chosen_rows),'witness_record_membership')
    require(dict(counts)==summary['counts'],'metadata_flow_counts')
    table=read(census/'all-calendar-cuts.json')
    require(len(table)==202 and len({(r['stratum_id'],r['cut']) for r in table})==202,'calendar_table_coverage')
    observed={(r['stratum_id'],r['cut']):r for r in table}
    all_accounts={a for a,c in timelines};best={};checked_cells=0
    for i,(x,y) in enumerate(plan['community_pairs'],1):
        sid=plan['stratum_ids'][i-1]
        necessary=[a for a in all_accounts if all(len(timelines[a,c])>=80 and sum(r[2] for r in timelines[a,c])>=10000 for c in (x,y))]
        for cut_text in plan['cuts']:
            cut=stamp(cut_text);prepared={};four=0
            for a in necessary:
                cells={role+'/'+period:cell(timelines[a,c],cut,period) for role,c in zip('XY',(x,y)) for period in ('early','late')}
                if all(v is not None for v in cells.values()):
                    four+=1
                    if compatible(cells,cells):prepared[a]=cells
            names=sorted(prepared,key=rank)
            edges={(a,b):pair_cost(prepared[a],prepared[b]) for n,a in enumerate(names) for b in names[n+1:] if compatible(prepared[a],prepared[b])}
            cardinality,cost,pairs=matching(names,edges)
            expected={'stratum_id':sid,'communities':[x,y],'cut':cut_text,'whole_history_necessary_accounts':len(necessary),
                      'accounts_with_four_volume_cells':four,'accounts_passing_internal_gates':len(names),
                      'compatible_edges':len(edges),'maximum_disjoint_blocks':cardinality,
                      'minimum_exact_matching_cost':rat(cost),'intended_block_deficit':max(0,2-cardinality)}
            actual=observed[sid,cut_text]
            require({k:actual[k] for k in expected}==expected,'calendar_capacity_or_exact_cost_mismatch')
            key=(-cardinality,cost,cut)
            if sid not in best or key<best[sid]['key']:
                best[sid]={'key':key,'row':expected,'cells':prepared,'edges':edges,'pairs':pairs}
        original=witness['strata'][sid];selected=best[sid]
        public_selected=next(r for r in summary['selected_calendar_witnesses'] if r['stratum_id']==sid)
        require({k:public_selected[k] for k in selected['row']}==selected['row'],'public_chosen_calendar_mismatch')
        require({k:original['public'][k] for k in selected['row']}==selected['row'],'chosen_calendar_mismatch')
        require(set(original['candidate_cells'])==set(selected['cells']),'chosen_candidate_account_set')
        for a,cells in selected['cells'].items():
            for key,stat in cells.items():
                actual=original['candidate_cells'][a][key];kept=stat['rows']
                require(actual['records']==stat['records'] and actual['retained_words']==stat['words'] and
                        actual['median_timestamp']==rat(stat['median']) and
                        actual['first_timestamp']==kept[0][0] and actual['last_timestamp']==kept[-1][0] and
                        [r['record_id'] for r in actual['rows']]==[r[1] for r in kept],'selected_prefix_or_statistics_mismatch')
                checked_cells+=1
        m=original['maximum_matching']
        require(m['cardinality']==len(selected['pairs']) and m['cost']==selected['row']['minimum_exact_matching_cost'] and
                m['pairs']==[list(p) for p in selected['pairs']],'chosen_exact_matching_identity_mismatch')
        require(original['capacity_only_accounts']==[a for a in sorted(selected['cells'],key=rank) if a in capacity_only],
                'capacity_exposure_flag_mismatch')
    require(summary['capacity_only_exposed_candidate_counts_at_chosen_cuts']==
            {sid:sum(a in capacity_only for a in v['cells']) for sid,v in best.items()},'public_capacity_exposure_counts')
    require(plan['global_witness_quotas']=={'stratum-02':1,'stratum-04':2,'stratum-05':2},'fixed_global_quotas')
    prior=read(prior_check_path)
    references=plan['external_fixed_witnesses']
    require(len(references)==1 and references[0]['stratum_id']==references[0]['source_stratum_id']=='stratum-02','fixed_prior_scope')
    reference=references[0]
    require(prior['status']=='passed' and prior['maximum_blocks_by_stratum']['stratum-02']==1 and
            prior['input_hashes']['private']==reference['sha256']==sha(reference['path']),'prior_independent_witness_binding')
    source=read(reference['path'])['strata']['stratum-02']
    pairs=[tuple(sorted(pair,key=rank)) for pair in source['maximum_matching']['pairs']]
    pairs.sort(key=lambda pair:tuple(rank(a) for a in pair))
    require(len(pairs)==1 and len(set(pairs[0]))==2 and not excluded.intersection(pairs[0]),'prior_fixed_pair')
    expected_external={'source_sha256':reference['sha256'],'source_stratum_id':'stratum-02',
            'public':source['public'],'fixed_pairs':[list(p) for p in pairs],
            'candidate_cells':{a:source['candidate_cells'][a] for pair in pairs for a in pair}}
    require(witness['external_fixed_strata']=={'stratum-02':expected_external} and
            witness['global_witness_quotas']==plan['global_witness_quotas'],'external_private_witness_changed')
    require(summary['global_witness_quotas']==plan['global_witness_quotas'] and summary['global_witness_target_blocks']==5,'public_global_quotas')
    # Independently enumerate two-edge choices per new stratum, with the
    # one fixed prior edge already occupied. No alternate calendars are used.
    def joint_search(remaining,occupied,selected):
        if not remaining:return selected
        sid,*rest=remaining
        ordered=sorted(best[sid]['edges'],key=lambda pair:tuple(rank(a) for a in pair))
        for choice in combinations(ordered,2):
            accounts={a for pair in choice for a in pair}
            if len(accounts)==4 and not accounts&occupied:
                result=joint_search(rest,occupied|accounts,{**selected,sid:[list(p) for p in choice]})
                if result is not None:return result
        return None
    expected_joint=joint_search(sorted(best),set(pairs[0]),{'stratum-02':[list(p) for p in pairs]})
    require(witness['globally_disjoint_intended_block_witness']==expected_joint,'independent_global_witness_mismatch')
    feasible=expected_joint is not None
    require(summary['globally_disjoint_intended_blocks_exist'] is feasible and
            summary['global_witness_joint_deficit'] is (not feasible) and
            summary['status']==('feasible_before_contamination_audit' if feasible else 'fixed_design_capacity_deficit'),
            'public_joint_feasibility_mismatch')
    # Compare CSV values to the canonical JSON table, including rational costs.
    with (census/'all-calendar-cuts.csv').open(newline='') as f:
        csv_rows=list(csv.DictReader(f))
    require(len(csv_rows)==202,'csv_row_count')
    for row,actual in zip(csv_rows,table):
        require(row['stratum_id']==actual['stratum_id'] and row['cut']==actual['cut'],'csv_calendar_identity')
        require(row['communities']==' / '.join(actual['communities']),'csv_community_mismatch')
        for field in ('whole_history_necessary_accounts','accounts_with_four_volume_cells',
                      'accounts_passing_internal_gates','compatible_edges','maximum_disjoint_blocks',
                      'matching_dp_states','intended_block_deficit'):
            require(int(row[field])==actual[field],'csv_capacity_mismatch')
        require(int(row['cost_numerator'])==actual['minimum_exact_matching_cost']['numerator'] and
                int(row['cost_denominator'])==actual['minimum_exact_matching_cost']['denominator'],'csv_exact_cost_mismatch')
    return {'status':'passed','metadata_rows':counts['metadata_rows'],'metadata_bytes':total_bytes,
            'calendar_rows_independently_recomputed':202,'chosen_candidate_cells_verified':checked_cells,
            'chosen_candidate_records_verified':len(confirmed),'all_exact_matching_objectives_and_cut_ties_verified':True,
            'maximum_blocks_by_stratum':{'stratum-02':1,**{s:len(v['pairs']) for s,v in best.items()}},
            'prior_independent_check_sha256':sha(prior_check_path),
            'chosen_cuts':{s:v['row']['cut'] for s,v in best.items()},
            'global_registered_1_2_2_target_feasible':feasible,'preprocessor_calls':0,'style_scores_computed':0,
            'source_archive_reads':0,'private_identifiers_published':False}


def main():
    p=argparse.ArgumentParser()
    for n in ('plan','flags','registration','census','private','receipt','prior-check','out'):
        p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();start=time.monotonic()
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError()))
    signal.alarm(600);a.out.parent.mkdir(parents=True,exist_ok=True)
    binding={'checker_sha256':sha(__file__),'status':'bound_before_independent_metadata_read',
             'input_hashes':{n:sha(getattr(a,n)) for n in ('plan','flags','registration','private','receipt','prior_check')},
             'census_hashes':{f.name:sha(f) for f in a.census.glob('*') if f.is_file()},
             'wall_seconds_limit':600,'address_space_bytes':4*1024**3,'metadata_rows_limit':3000000,'metadata_bytes_limit':1024**3}
    save(a.out.with_suffix('.start-binding.json'),binding)
    try:
        result=verify(a.plan,a.flags,a.registration,a.census,a.private,a.receipt,a.prior_check)
    except Exception as error:
        result={'status':'failed','reason':str(error) if type(error) is ValueError else type(error).__name__,
                'private_identifiers_published':False,'preprocessor_calls':0,'style_scores_computed':0}
    result.update(checker_sha256=binding['checker_sha256'],wall_seconds=time.monotonic()-start,
                  peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
                  input_hashes=binding['input_hashes'],census_hashes=binding['census_hashes'])
    save(a.out,result);signal.alarm(0)
    print(json.dumps(result,sort_keys=True))
    return 0 if result['status']=='passed' else 1


if __name__=='__main__':
    raise SystemExit(main())
