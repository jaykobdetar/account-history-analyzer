"""Independent read-only preflight: hashes, allocation, exclusions and byte limits.

No construction helper, analyzer, corpus decompressor, writing feature or score
is imported. Source ZIP central directories and metadata line counts are read;
all other file content is hashed or treated as registered non-writing metadata.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import signal
import zipfile

ENGINE_SHA = 'f080682bc5beac251f9fb07404d0c9a9093aab04deff8d53997708d05dd01e92'
WRAPPER_SHA = '93d99004d7ea406bd7e44cfcc8997a8abad69508c9cb84cc0c35d5783cb88b1f'
LIMITS = {'metadata_rows':3000000,'source_rows':15000000,'source_uncompressed_bytes':10000000000,
          'combined_private_output_bytes':268435456,'wall_seconds':1800,'address_space_bytes':4294967296}
GATES = {'half_band_days':180,'half_target_words':5000,'half_min_records':40,'half_max_words':5500,
         'half_max_records':200,'record_word_min':20,'record_word_max':500,
         'all_eight_cell_word_ratio_max':'11/10','all_eight_cell_record_ratio_max':'5/4',
         'within_period_four_cell_median_span_days_max':30}
STRATA = {'stratum-02':({'AskPhysics','Physics'},1,2),
          'stratum-04':({'linux','linuxquestions'},2,12),
          'stratum-05':({'programming','learnprogramming'},2,12)}


def require(value, code):
    if not value:raise ValueError(code)


def sha(path):
    with Path(path).open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def bindings(rows):
    result={}
    for row in rows:
        path=Path(row['path'])
        require(path.is_absolute() and path.is_file() and not path.is_symlink(),'binding_path_invalid')
        canonical=str(path.resolve())
        require(canonical not in result,'duplicate_binding')
        require(sha(path)==row['sha256'],'bound_file_hash_changed')
        result[canonical]=row['sha256']
    return result


def lines(path):
    count=0;last=b''
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):
            count+=chunk.count(b'\n');last=chunk[-1:]
    return count+int(bool(last) and last!=b'\n')


def stratum_summary(rows):
    require(len(rows)==3 and {r['stratum_id'] for r in rows}==set(STRATA),'stratum_set_mismatch')
    all_accounts=[];public=[]
    for row in rows:
        communities,cap,maximum=STRATA[row['stratum_id']]
        count=len(row['accounts'])
        require(len(row['communities'])==2 and set(row['communities'])==communities,'community_pair_mismatch')
        require(type(row['block_cap']) is int and row['block_cap']==cap,'block_cap_changed')
        require((cap==2 and count==0) or 2<=count<=maximum,'candidate_account_count_invalid')
        require(all(isinstance(a,str) and a and a==a.casefold() for a in row['accounts']),'source_identity_not_canonical')
        stamp=datetime.fromisoformat(row['cut'].replace('Z','+00:00'))
        require(stamp.tzinfo is not None and stamp.utcoffset().total_seconds()==0 and stamp.timestamp().is_integer(),'cut_not_integer_utc')
        all_accounts.extend(row['accounts'])
        public.append({k:v for k,v in row.items() if k!='accounts'}|{'candidate_accounts':count})
    require(len(all_accounts)==len(set(all_accounts)) and len(all_accounts)<=26,'candidate_accounts_not_disjoint')
    return public,set(all_accounts)


def review(plan_path,registration_path,allocation_path,allocation_registration_path,expected_sha):
    require(sha(plan_path)==expected_sha,'plan_does_not_match_requested_frozen_identity')
    plan,registration,allocation,areg=map(load,(plan_path,registration_path,allocation_path,allocation_registration_path))
    require(plan['phase']==registration['phase']=='frozen_before_candidate_pool','preparation_phase_invalid')
    require(registration['private_plan_sha256']==expected_sha,'public_private_plan_hash_mismatch')
    require(plan['limits']==registration['limits']==LIMITS,'resource_limits_changed')
    bound=bindings(plan['bound_artifacts'])
    require(len(bound)==registration['bound_artifact_count'],'public_binding_count_mismatch')
    scripts=Path(__file__).resolve().parent
    required={str((scripts/name).resolve()) for name in ('prepare_chronology_pool.py','finalize_chronology_inputs.py',
        'chronology_math.py','metadata_feasibility.py','run_full_chronology.py','allocate_candidate_accounts.py',
        'run_candidate_allocation.py')}
    required.update(str(Path(plan[k]).resolve()) for k in ('converter','feasibility_rules','exposure_flags',
        'audit_wrapper','audit_engine','audit_rules','historical_inventory'))
    required.update(str(Path(p).resolve()) for p in plan['metadata_files'])
    required.update(str(Path(s['archive']).resolve()) for s in plan['sources'])
    required.update(str(Path(p).resolve()) for p in (allocation_path,allocation_registration_path))
    required.add(str((Path(plan['converter']).resolve().parent/'cohort_selection.py').resolve()))
    require(required<=set(bound),'consumed_dependency_not_bound')
    for key,name in (('script_sha256','prepare_chronology_pool.py'),('finalizer_sha256','finalize_chronology_inputs.py')):
        require(plan[key]==registration[key]==sha(scripts/name),'construction_script_identity_mismatch')
    require(sha(plan['audit_engine'])==ENGINE_SHA and sha(plan['audit_wrapper'])==WRAPPER_SHA,'frozen_audit_identity_changed')
    design=load(plan['feasibility_rules'])
    require(all(design[k]==v for k,v in GATES.items()),'original_date_volume_gate_changed')
    public,accounts=stratum_summary(plan['strata'])
    require(public==registration['strata'],'public_stratum_metadata_mismatch')
    require(plan['strata']==allocation['strata'],'plan_differs_from_registered_allocation')
    require(sha(allocation_path)==registration['allocation_sha256'],'allocation_hash_mismatch')
    require(allocation['registration_sha256']==sha(allocation_registration_path) and allocation['style_scores_computed']==0,
            'allocation_registration_or_score_free_flag_mismatch')
    require(areg['phase']=='frozen_before_metadata_allocation','allocation_phase_invalid')
    allocation_bindings=bindings(areg['bound_artifacts'])
    require(set(allocation_bindings)<=set(bound),'allocation_evidence_not_bound')
    seen=set()
    for sid in STRATA:
        pairs=allocation['reserved_witness'][sid]
        members=[account for pair in pairs for account in pair]
        require(all(len(pair)==2 for pair in pairs) and len(members)==len(set(members)),'reserved_witness_not_disjoint')
        require(not seen.intersection(members),'reserved_witness_crosses_strata');seen.update(members)
        require(set(members)<=set(allocation['assigned'][sid]),'reserved_accounts_missing_from_pool')
        require(set(members)==set(allocation['reserved_witness_accounts'][sid]),'reserved_membership_summary_mismatch')
        require(len(pairs)==allocation['attainable_reserved_block_counts'][sid],'witness_block_count_mismatch')
        require(allocation['registered_target_deficits'][sid]==STRATA[sid][1]-len(pairs),'witness_deficit_mismatch')
    flags=load(plan['exposure_flags'])['accounts']
    require(len({r['account_key'] for r in flags})==len(flags),'exposure_identity_duplicate')
    fields=('pilot1_or_pilot2_or_private_mandatory_exclusion','pilot3_selected_scored_exposure','prior_capacity_only_exposure')
    require(all(type(row[k]) is bool for row in flags for k in fields),'exposure_flags_not_boolean')
    protected={r['account_key'] for r in flags if r[fields[0]]};scored={r['account_key'] for r in flags if r[fields[1]]}
    require(len(protected)==57 and len(scored)==60 and not protected&scored,'historical_exclusion_counts_changed')
    require(not accounts.intersection(protected|scored),'excluded_account_in_candidate_pool')
    metadata_rows=sum(lines(path) for path in plan['metadata_files'])
    require(metadata_rows<=LIMITS['metadata_rows'],'metadata_rows_exceed_preparation_cap')
    source_bytes=0;source_summaries=[]
    communities=[s['community'] for s in plan['sources']]
    require(len(communities)==6 and set(communities)==set().union(*(r[0] for r in STRATA.values())),
            'source_community_set_mismatch')
    for source in plan['sources']:
        require(bound[str(Path(source['archive']).resolve())]==source['sha256'],'source_binding_disagrees')
        with zipfile.ZipFile(source['archive']) as archive:
            matching=[r for r in archive.infolist() if r.filename=='utterances.jsonl']
            require(len(matching)==1 and not matching[0].is_dir(),'source_member_missing_or_ambiguous')
            size=matching[0].file_size;source_bytes+=size
        source_summaries.append({'community':source['community'],'archive_sha256':source['sha256'],
                                 'declared_utterances_bytes':size})
    require(source_bytes<=LIMITS['source_uncompressed_bytes'],'declared_source_bytes_exceed_preparation_cap')
    return {'status':'passed','plan_sha256':expected_sha,'verified_bound_artifacts':len(bound),
        'strata':public,'candidate_accounts':len(accounts),'global_accounts_distinct':True,
        'reserved_block_counts':allocation['attainable_reserved_block_counts'],
        'registered_target_deficits':allocation['registered_target_deficits'],
        'excluded_accounts':117,'selected_excluded_accounts':0,'metadata_rows':metadata_rows,
        'source_archives':source_summaries,'declared_source_uncompressed_bytes':source_bytes,'limits':LIMITS,
        'source_rows_must_be_counted_during_preparation':True,'source_archives_decompressed':False,
        'writing_or_feature_values_inspected':False,'style_scores_computed':0,'scoring_permitted':False}


def main():
    parser=argparse.ArgumentParser()
    for key in ('plan','registration','allocation','allocation-registration','out'):
        parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--expected-plan-sha256',required=True)
    args=parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(4294967296,)*2)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('review_wall_limit')))
    signal.alarm(300)
    binding={'checker_sha256':sha(__file__),'expected_plan_sha256':args.expected_plan_sha256,
             'started_utc':datetime.now(timezone.utc).isoformat(),'style_scores_computed':0}
    start=Path(str(args.out)+'.start-binding.json')
    with start.open('x') as handle:json.dump(binding,handle,sort_keys=True,indent=2);handle.write('\n')
    try:
        report=review(args.plan,args.registration,args.allocation,args.allocation_registration,args.expected_plan_sha256)
    except (ValueError,KeyError,TimeoutError,OSError) as error:
        report={'status':'failed','reason':str(error) if type(error) is ValueError else type(error).__name__,
                'style_scores_computed':0,'scoring_permitted':False}
    report['checker_sha256']=binding['checker_sha256']
    with args.out.open('x') as handle:json.dump(report,handle,sort_keys=True,indent=2);handle.write('\n')
    print(json.dumps(report,sort_keys=True))
    raise SystemExit(0 if report['status']=='passed' else 1)


if __name__=='__main__':main()
