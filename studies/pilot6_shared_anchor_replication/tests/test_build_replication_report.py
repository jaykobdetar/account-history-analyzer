"""Synthetic saved-output transforms only; no analyzer or source writing."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import pytest

S6 = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('pilot6_report', S6/'scripts/build_replication_report.py')
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
spec = importlib.util.spec_from_file_location('synthetic_chronology_math', S6.parent/'pilot4_chronological_controls/scripts/chronology_math.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


def put(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1) + '\n')


def fixture(root):
    run, public, logs = root/'run', root/'inventory/prepared', root/'logs'
    run.mkdir(); public.mkdir(parents=True); logs.mkdir()
    pid = 'pilot6-pair-01'
    origin = datetime(2017, 1, 1, tzinfo=timezone.utc)
    metadata = [{'record_id': f'synthetic-{i}', 'created_utc': (origin + timedelta(seconds=i)).isoformat(),
                 'retained_words': 125, 'kind': 'comment', 'style_eligible': True} for i in range(80)]
    windows = m.reconstruct_windows(metadata)
    cases = []
    for i, condition in enumerate(r.CONDITIONS):
        switched = condition.startswith('switch_')
        unavailable = i == 3
        score = m.score_case(candidate_intervals=None if unavailable else [[], [[24,24], [48,48]], [[40,40]]][i],
            status='unavailable' if unavailable else 'ok', reason_codes=['not_dispatched_global_wall_limit'] if unavailable else [],
            truth_k=40 if switched else None, control_junction_k=None if switched else 40,
            windows=windows, record_timestamps=[x['created_utc'] for x in metadata])
        operation = {'dispatched': not unavailable, 'status': 'not_dispatched_or_unrecorded' if unavailable else 'attempted',
            'exit_code': None if unavailable else 0, 'wall_seconds': None if unavailable else 1.25,
            'child_peak_rss_mib': None if unavailable else 30.0, 'artifact_bytes': 0 if unavailable else 100}
        cases.append({'case_id': pid+':AX:'+condition, 'block_id': pid, 'stratum_id': 'stratum-01', 'anchor_id': 'AX',
            'condition': condition, 'source_switch': switched, 'community_change': condition.endswith('changed_community'),
            'left_cell_id': pid+':A:X:early', 'right_cell_id': pid+':'+('B' if switched else 'A')+':'+('Y' if i>=2 else 'X')+':late',
            'score': score, 'primary_window_check': 'metadata_reconstruction_only_unverified_execution' if unavailable else 'all_primary_memberships_counts_positions_verified',
            'native_change_status': None if unavailable else 'no_measurable_variation' if i==0 else 'ok',
            'record_count': 80, 'retained_words': 10000,
            'full_pipeline_statuses': None if unavailable else {'change': {'status': 'no_measurable_variation' if i==0 else 'ok', 'reason_codes': []},
                                                             'text': {'status':'ok','reason_codes':[]}},
            'resources': None if unavailable else {'exit_code':0,'wall_seconds':1.25,'child_peak_rss_mib':30.0,'external_wall_limit_reached':False,'external_artifact_limit_reached':False},
            'effective_exit_code': None if unavailable else 0, 'dispatch_status': operation['status'],
            'external_wrapper_artifact_limit_reached': False, 'artifact_bytes': operation['artifact_bytes'],
            'results_sha256': None if unavailable else 'a'*64, 'pair_id': pid,
            'all_candidate_interval_errors_records': None if unavailable else [[],[16,8],[0]][i],
            'main_operation': operation, 'replay_operation': deepcopy(operation),
            'replay_verification': {'all_files_byte_identical': None if unavailable else True, 'canonical_file_count': None if unavailable else 3}})
    summary = {'study':'pilot6_shared_anchor_replication','target_new_pairs':10,'registered_new_pairs':1,'prescore_pair_shortfall':9,
        'planned_main_histories':4,'planned_replay_histories':4,'main_dispatched_histories':3,'replay_dispatched_histories':3,
        'main_executed_primary_histories':3,'main_unavailable_primary_histories':1,'pairs_with_four_executed_primary_histories':0,
        'pairs_with_four_verified_replays':0,'stop_reason':'not_dispatched_global_wall_limit','global_wall_seconds_since_first_dispatch':3.0,
        'artifact_bytes_before_final_reports':800,'condition_counts':dict.fromkeys(r.CONDITIONS,1),'registration_sha256':'b'*64,
        'cohort_sha256':'c'*64,'pair_statuses':[{'pair_id':pid,'status':'adapter_phase_failed','replay_all_passed':None}],
        'counting_note':'One pair shares one anchor.','intervals_and_missingness':'Unavailable is null.'}
    put(run/'cases.json', cases); put(run/'summary.json',summary)
    put(run/pid/'pair-summary.json', {'pair_id':pid,'cases':cases,'status':'adapter_phase_failed',
        'phases':{p:{'status':'completed','exit_code':0,'wall_seconds':.01} for p in ('main','score','replay','replay-check')},
        'artifact_bytes':600,'replay_all_passed':None})
    availability=[]
    for n in range(1,21):
        selected=n==1
        availability.append({'pair_id':f'pilot6-pair-{n:02d}','stratum_id':'stratum-01','community_x':'AskAcademia',
            'community_y':'GradSchool','cut':'2017-01-01T00:00:00Z','valid':selected,
            'selection_status':'selected_for_replication' if selected else 'unavailable_after_audit',
            'reason_codes':[] if selected else ['unavailable_sample:late_BY'],'cost':{'numerator':0,'denominator':1} if selected else None})
    put(public/'pair-availability.json',availability)
    put(public/'selection-summary.json',{'provisional_pairs':20,'selected_new_pairs':1,'eligible_after_audit':1})
    put(public/(pid+'-samples.json'),{'pair_id':pid,'unique_comments':200,'unique_retained_words':25000,
        'samples':[{'sample_key':k,'records':40,'retained_words':5000}
        for k in ('anchor','late_AX','late_BX','late_AY','late_BY')]})
    passed=root/'check.json'
    put(passed,{'status':'passed','analyzer_calls':0,'aggregate_cases_sha256':r.sha(run/'cases.json'),
        'aggregate_summary_sha256':r.sha(run/'summary.json'),'registration_sha256':'b'*64,
        'new_source_account_pairs':1,'planned_main_histories':4})
    for name,code in [('preparation',0),('first-failed-attempt',1)]:
        put(logs/(name+'.receipt.json'),{'argv':['private-command','/home/secret/private-input'], 'cwd':'/home/secret',
            'exit_code':code,'wall_seconds':2.0,'child_peak_rss_mib':20.0,'runner_sha256':'d'*64})
    return run,passed,public,logs,cases,summary


def test_exact_safe_copies_all_intervals_nulls_controls_and_twenty_availability_rows(tmp_path):
    run,passed,public,logs,cases,summary=fixture(tmp_path)
    result=r.build(run,passed,public,[logs],tmp_path/'results')
    assert result['main_case_rows']==4 and result['provisional_availability_rows']==20
    assert (tmp_path/'results/cases.json').read_bytes()==(run/'cases.json').read_bytes()
    assert (tmp_path/'results/summary.json').read_bytes()==(run/'summary.json').read_bytes()
    aggregates=r.read(tmp_path/'results/condition-summary.json')
    assert aggregates[0]['executed_no_measurable_variation_histories']==1
    assert aggregates[1]['within_ten_records']=={'numerator':1,'denominator_executed':1}
    assert aggregates[2]['localization_label']=='control_junction_alignment'
    assert aggregates[3]['unavailable_histories']==1 and aggregates[3]['observed_candidate_count_sum'] is None
    text=(tmp_path/'results/REPORT.md').read_text()
    assert '[24, 24] → 16; [48, 48] → 8' in text
    assert 'pre-score shortfall is 9' in text and 'pilot6-pair-20' in text
    assert 'private-command' not in text and '/home/secret' not in text
    costs=r.read(tmp_path/'results/operating-costs.json')
    assert costs['study_receipt_count']==2 and costs['failed_study_receipt_count']==1
    assert costs['main']['sum_case_wall_seconds']==3.75 and costs['elapsed_seconds_since_first_dispatch']==3


def test_deterministic_transform_and_receipt_roots_deduplicate_source_path(tmp_path):
    run,passed,public,logs,*_=fixture(tmp_path)
    r.build(run,passed,public,[logs,logs],tmp_path/'one')
    r.build(run,passed,public,[logs,logs],tmp_path/'two')
    assert {p.name:p.read_bytes() for p in (tmp_path/'one').iterdir()}=={p.name:p.read_bytes() for p in (tmp_path/'two').iterdir()}
    assert r.read(tmp_path/'one/operating-costs.json')['study_receipt_count']==2


@pytest.mark.parametrize('mutation',['failed_check','changed_cases','zero_imputation','missing_case','private_field','dropped_unavailable','pair_mismatch'])
def test_reporting_failures_leave_no_public_output(tmp_path,mutation):
    run,passed,public,logs,cases,summary=fixture(tmp_path)
    if mutation=='failed_check':
        doc=r.read(passed);doc['status']='failed';put(passed,doc)
    elif mutation=='changed_cases':
        with (run/'cases.json').open('a') as f:f.write(' ')
    elif mutation in ('zero_imputation','missing_case','private_field'):
        if mutation=='zero_imputation':cases[3]['score']['candidate_count']=0
        if mutation=='missing_case':cases.pop()
        if mutation=='private_field':cases[0]['text']='PRIVATE SOURCE'
        put(run/'cases.json',cases)
        doc=r.read(passed);doc['aggregate_cases_sha256']=r.sha(run/'cases.json');put(passed,doc)
    elif mutation=='dropped_unavailable':
        doc=r.read(public/'pair-availability.json');doc.pop();put(public/'pair-availability.json',doc)
    else:
        doc=r.read(run/'pilot6-pair-01/pair-summary.json');doc['cases'][0]['record_count']+=1;put(run/'pilot6-pair-01/pair-summary.json',doc)
    with pytest.raises(ValueError):r.build(run,passed,public,[logs],tmp_path/'results')
    assert not (tmp_path/'results').exists()


def test_safe_recursive_guard_and_manifest_hashes(tmp_path):
    for payload in ({'nested':{'record_ids':['secret']}},{'nested':'/tmp/private/file'},{'bad':float('nan')}):
        with pytest.raises(ValueError):r.safe(payload)
    run,passed,public,logs,*_=fixture(tmp_path)
    r.build(run,passed,public,[logs],tmp_path/'results')
    manifest=r.read(tmp_path/'results/REPORT_MANIFEST.json')
    for name,item in manifest['outputs'].items():
        assert item['sha256']==r.sha(tmp_path/'results'/name)
    with pytest.raises(ValueError):r.build(run,passed,public,[logs],tmp_path/'results')


def test_module_text_status_is_safe_but_native_text_payload_is_not():
    r.safe({'full_pipeline_statuses':{'text':{'status':'ok','reason_codes':[]}}})
    with pytest.raises(ValueError):
        r.safe({'full_pipeline_statuses':{'text':{'status':'ok','reason_codes':[],'data':{'body':'private'}}}})


def test_context_exact_copy_coverage_and_original_source_hash_binding(tmp_path):
    run,passed,public,logs,*_=fixture(tmp_path)
    context={'reporting_only':True,'analyzer_calls':0,'source_feasibility':{'pair_cut_count':505,'unique_valid_unordered_edges':76,
        'global_maximum_matching_pairs':32,'provisional_pairs':20},
        'audit':{'candidate_records':500,'purged_candidate_records':10,'surviving_candidate_records':490,'independent_candidate_pairs':100,
                 'max_candidate_pairs':2000000,'content_unobservable_record_count':17},
        'selected_cohort':{'pairs':1,'source_accounts':2,'unique_original_comments':200,'unique_retained_words':25000,
            'stratum_pair_counts':{'stratum-01':1},'prior_preparation_exposure':{'prior_preparation_in_either_study_accounts':1,
            'prior_pilot3_preparation_and_audit_accounts':1,'prior_pilot4_preparation_and_audit_accounts':0,
            'prior_metadata_without_known_preparation_accounts':1,'first_eligibility_metadata_from_pilot6_supplement_accounts':0}},
        'unavailable_provisional_pairs':19,'input_sha256':{'inventory/prepared/pair-availability.json':r.sha(public/'pair-availability.json')}}
    path=tmp_path/'inventory/study-context.json';put(path,context)
    r.build(run,passed,public,[logs],tmp_path/'results',study_context=path)
    assert (tmp_path/'results/study-context.json').read_bytes()==path.read_bytes()
    text=(tmp_path/'results/REPORT.md').read_text()
    assert '17 historical records remained unobservable' in text and '| AskPhysics / Physics | 0 |' in text
    context['input_sha256']['inventory/prepared/pair-availability.json']='0'*64;put(path,context)
    with pytest.raises(ValueError):r.build(run,passed,public,[logs],tmp_path/'bad',study_context=path)
