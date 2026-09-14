#!/usr/bin/env python3
"""Run the frozen metadata-only shared-calendar refinement, never scoring."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import time

from calendar_capacity import best_calendar_pairs
from expanded_capacity import choose_three_strata

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def write(path,obj,private=False):
    with path.open('x') as f:json.dump(obj,f,indent=2,sort_keys=True);f.write('\n')
    if private:path.chmod(0o600)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--amendment',type=Path,required=True)
    p.add_argument('--census',type=Path,required=True)
    p.add_argument('--private-root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    started=time.monotonic()
    resource.setrlimit(resource.RLIMIT_AS,(4294967296,)*2)
    args.out.mkdir(parents=True,exist_ok=False)
    private_out=args.private_root/args.out.name
    private_out.mkdir(mode=0o700,exist_ok=False)
    plan=json.loads(args.plan.read_text())
    records_path=args.private_root/args.census.name/'record-eligibility.jsonl'
    source_binding=json.loads((args.census/'private-artifact-hashes.json').read_text())
    if sha(records_path)!=source_binding['record-eligibility.jsonl']['sha256']:
        raise ValueError('Metadata bytes differ from completed census')
    exclusion=json.loads((args.private_root/'exclusions-mandatory.json').read_text())
    excluded={r['account_key'] for r in exclusion['accounts']}
    previous={r['account_key'] for r in exclusion['prior_capacity_only_accounts']}
    binding={'utc':datetime.now(timezone.utc).isoformat(),'phase':'before_metadata_calendar_refinement',
             'source_census':args.census.name,'plan_sha256':sha(args.plan),
             'amendment_sha256':sha(args.amendment),'eligibility_metadata_sha256':sha(records_path),
             'source_inventory_sha256':sha(args.census/'source-inventory.json'),
             'scripts':{name:sha(Path(__file__).with_name(name)) for name in
                        ('run_calendar_census.py','calendar_capacity.py','expanded_capacity.py','study_math.py')},
             'new_source_prose_reads':0,'new_preprocessing_calls':0,'style_scores_computed':0}
    write(args.out/'start-binding.json',binding)
    rows=[]
    total=0
    with records_path.open() as f:
        for line in f:
            total+=1
            if total>1000000 or time.monotonic()-started>300:
                raise RuntimeError('Predeclared metadata/time budget exhausted')
            row=json.loads(line)
            if row['account_key'] in excluded:
                raise ValueError('Excluded identity in input metadata')
            if row['reason'] is None:rows.append(row)
    choices=best_calendar_pairs(rows,[s['community'] for s in plan['sources']],
                                '2008-01-01','2018-11-01')
    by_pair={k:set(v['accounts']) for k,v in choices['pairs'].items()}
    selected=choose_three_strata(by_pair)
    write(private_out/'calendar-capacities.json',choices,True)
    write(private_out/'capacity-witness.json',selected,True)
    summary={'gate_a_status':'capacity_pass_requires_contamination_audit' if selected['feasible_target'] else 'failed_capacity',
             'phase':'metadata_only_calendar_refinement','planned_accounts':60,'planned_blocks':30,
             'selected_pair_strata':selected['selected_pairs'],
             'disjoint_capacity':{k:v for k,v in selected['capacity'].items() if k!='assigned'},
             'pair_capacities':{k:{'maximum_four_cell_accounts':v['maximum_accounts'],
                                   'chosen_calendar_scheme':v['scheme'],
                                   'prior_capacity_inspected_accounts':len(set(v['accounts']) & previous)}
                                for k,v in choices['pairs'].items()},
             'metadata_rows_read':total,'eligible_metadata_rows':len(rows),
             'selection_reason':selected['selection_reason'],
             'full_target_feasible_triple_count':selected['full_target_feasible_triple_count'],
             'final_cohort_selected':False,'style_scores_computed':0,
             'source_prose_reads':0,'preprocessing_calls':0,
             'leakage_audit_status':'not_run; capacities precede contamination filtering',
             'scope':'All shared UTC midnight cuts inside [2008-01-01,2018-11-01); whole records and unchanged2000word/eightrecord fourcell guards.'}
    write(args.out/'capacity.json',summary)
    private_bytes=sum(p.stat().st_size for p in private_out.iterdir())
    if private_bytes>104857600 or time.monotonic()-started>300:
        raise RuntimeError('Declared output/time budget exceeded; gate incomplete')
    write(args.out/'private-artifact-hashes.json',{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in private_out.iterdir()})
    write(args.out/'resources.json',{'wall_seconds':time.monotonic()-started,
          'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
          'metadata_rows':total,'private_output_bytes':private_bytes,
          'source_prose_reads':0,'preprocessing_calls':0,'resource_outcome':'completed_within_predeclared_limits'})
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
