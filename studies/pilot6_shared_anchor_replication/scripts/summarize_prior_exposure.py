"""Reporting-only metadata provenance; written after buffer registration.

Reads only source selection/account and retained-word metadata. It neither
changes selection nor opens writing, audit content relations, or style results.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import resource
import signal
import time
from check_replication_prepared import exclusions,sha,read,require


def build(buffer_plan_path,pilot3_selection,pilot4_selection,out):
    plan=read(buffer_plan_path);provisional=read(plan['provisional_pairs']);pairs=provisional['pairs']
    excluded,capacity=exclusions(read(plan['exposure_flags']),read(plan['pilot5_selection']))
    accounts={p[k] for p in pairs for k in ('account_a','account_b')}
    require(len(pairs)==20 and len(accounts)==40 and not accounts&excluded,'fixed_twenty_disjoint_new_pairs')
    three=read(pilot3_selection);four=read(pilot4_selection)
    p3_buffer={r['account_key'] for r in three['selected_record_metadata'].values()}
    p4_buffer={r['account_key'] for r in four['selected_metadata'].values()}
    old_metadata=set();supplement_metadata=set();hashes={};rows=bytes_read=0
    metadata_plan=read(plan['metadata_plan'])
    require(provisional['plan_sha256']==sha(plan['metadata_plan']),'metadata_plan_binding')
    require([str(Path(r['path']).resolve()) for r in metadata_plan['source_metadata']]==[str(Path(p).resolve()) for p in plan['metadata_files']],'metadata_source_list_binding')
    for i,source in enumerate(metadata_plan['source_metadata'],1):
        path=Path(source['path']);require(path.stat().st_size==source['bytes'] and sha(path)==source['sha256'],'metadata_source_identity')
        is_supplement='pilot6_private' in path.parts
        require(is_supplement or 'pilot3_private' in path.parts or 'pilot4_private' in path.parts,'unexpected_metadata_source_category')
        source_rows=0
        with path.open('rb') as f:
            for line in f:
                rows+=1;source_rows+=1;bytes_read+=len(line)
                require(rows<=3000000 and bytes_read<=1024**3,'reporting_metadata_ceiling')
                r=json.loads(line)
                if r['account_key'] in accounts:(supplement_metadata if is_supplement else old_metadata).add(r['account_key'])
        hashes[f'metadata_source_{i:02d}']={'sha256':source['sha256'],'bytes':source['bytes'],'rows':source_rows,
            'scope':'pilot6_supplement_metadata' if is_supplement else 'prior_eligibility_metadata'}
    require(accounts<=old_metadata|supplement_metadata,'provisional_account_metadata_coverage')
    any_buffer=p3_buffer|p4_buffer
    categories={
      'prior_pilot4_preparation_and_audit_accounts':p4_buffer,
      'prior_pilot3_preparation_and_audit_accounts':p3_buffer,
      'prior_preparation_in_either_study_accounts':any_buffer,
      'prior_metadata_without_known_preparation_accounts':old_metadata-any_buffer,
      'first_eligibility_metadata_from_pilot6_supplement_accounts':supplement_metadata-old_metadata-any_buffer,
      'pilot6_supplement_metadata_accounts':supplement_metadata,
      'prior_capacity_only_exposure_flag_accounts':capacity}
    pair_rows=[]
    for pair in pairs:
        names={pair[k] for k in ('account_a','account_b')}
        pair_rows.append({'pair_id':pair['pair_id'],**{k:len(names&v) for k,v in categories.items()},'previously_scored_or_protected_accounts':len(names&excluded)})
    totals={k:len(accounts&v) for k,v in categories.items()}
    require(totals['prior_preparation_in_either_study_accounts']+totals['prior_metadata_without_known_preparation_accounts']+
        totals['first_eligibility_metadata_from_pilot6_supplement_accounts']==40,'exclusive_history_categories_cover_accounts')
    result={'status':'reported','reporting_only_after_buffer_registration':True,'selection_criteria_changed':False,
       'provisional_pairs':20,'distinct_source_accounts':40,'previously_scored_or_protected_accounts':0,
       'counts':totals,'pairs':pair_rows,
       'definitions':{
         'prior_preparation_and_audit':'An account with at least one original record in the completed Pilot3 or Pilot4 pre-score candidate buffer. This is exposure to preparation and leakage auditing, not an AHAS style-analysis result.',
         'prior_metadata_without_known_preparation':'Appears in prior saved eligibility metadata but neither known Pilot3 nor Pilot4 candidate buffer. This does not establish that the account was never observed outside the documented study inputs.',
         'first_eligibility_metadata_from_pilot6_supplement':'Appears in Pilot6 supplement metadata and no consumed prior eligibility metadata or known Pilot3/Pilot4 candidate buffer. New refers to this recorded metadata intake, not account creation or independent collection.',
         'supplement_metadata':'At least one saved eligibility-metadata row from the Pilot6 supplement. This flag overlaps earlier metadata or preparation exposure.',
         'capacity_only_exposure_flag':'The unchanged prior exposure ledger flag. It can overlap a later preparation/audit exposure and therefore is not used as the exclusive history category.',
         'exclusions':'The independently verified distinct57 prior protected/private +60 Pilot3 scored +2 Pilot5 scored identities remain excluded. Pilot4 produced zero scoreable blocks and no analyzer runs.',
         'scope':'Counts describe the twenty fixed provisional pairs before current audit/final selection; they are not selected-cohort counts. No source identities, prose, feature vectors, candidate scores, or alternative directions were examined or published.'},
       'input_hashes':{'buffer_plan':sha(buffer_plan_path),'metadata_plan':sha(plan['metadata_plan']),
         'provisional_pairs':sha(plan['provisional_pairs']),'pilot3_candidate_selection_metadata':sha(pilot3_selection),
         'pilot4_candidate_selection_metadata':sha(pilot4_selection),'exposure_flags':sha(plan['exposure_flags']),
         'pilot5_selection_metadata':sha(plan['pilot5_selection']),'record_metadata_inputs':hashes},
       'new_preprocessing_calls':0,'new_style_calls':0,'source_prose_read':False,'source_identifiers_published':False,
       'script_sha256':sha(__file__),'recorded_utc':datetime.now(timezone.utc).isoformat()}
    with Path(out).open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'provisional_pairs':20,'accounts':40,'counts':totals}),flush=True)


def main():
    p=argparse.ArgumentParser()
    for k in ('buffer-plan','pilot3-selection','pilot4-selection','out'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('reporting_wall_limit')));signal.alarm(600)
    build(a.buffer_plan,a.pilot3_selection,a.pilot4_selection,a.out)

if __name__=='__main__':main()
