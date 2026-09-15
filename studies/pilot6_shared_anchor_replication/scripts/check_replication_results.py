"""Independent Pilot6 saved-result review; no runner/math/analyzer imports.

Reuses only the unchanged independent Pilot5 native/window arithmetic checker.
All source-containing artifacts stay private; this report contains safe counts,
intervals, timestamps, numeric costs, hashes and opaque case identifiers.
"""
from collections import Counter
from datetime import datetime, timezone
import argparse
import importlib.util
import json
import math
from pathlib import Path
import resource
import signal
import time

ROOT = Path(__file__).resolve().parents[3]
PRIOR = ROOT/'studies/pilot5_shared_anchor/scripts/check_saved_results_independent.py'
P5_RUNNER = ROOT/'studies/pilot5_shared_anchor/scripts/run_diagnostic.py'
RUNNER = Path(__file__).with_name('run_replication.py')
SPEC = importlib.util.spec_from_file_location('pilot6_independent_prior_check', PRIOR)
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
sha, read, require = prior.sha, prior.read, prior.require
CONDITIONS = prior.CONDITIONS
EXCLUDED_OPERATIONAL = {'ingest_receipt.json', 'run_receipt.json'}
GLOBAL_LIMITS = {'global_wall_seconds':14400, 'global_artifact_bytes':12884901888,
                 'max_pairs':10, 'pair_reserved_artifact_bytes':4294967296}
ORIGINAL_ENV = {'PYTHONPATH':'/tmp/ahas-pilot3-installed', 'PYTHONHASHSEED':'0', 'TZ':'UTC'}
REPLAY_ENV = {**ORIGINAL_ENV, 'PYTHONHASHSEED':'73129', 'TZ':'Pacific/Honolulu'}
PAIR_LIMITS = {'parallel_cases':2,'case_wall_seconds':600,'process_address_space_bytes':4294967296,
               'dispatch_wall_seconds':3600,'run_artifact_bytes':8589934592}
HELPER_NAMES = {'run_full_chronology.py','chronology_math.py','score_saved_chronology.py','matched_condition_changes.py'}
DESCRIPTORS = ('case_id','block_id','stratum_id','anchor_id','condition','source_switch',
               'community_change','left_cell_id','right_cell_id')
ADDED_FIELDS = {'pair_id','all_candidate_interval_errors_records','main_operation',
                'replay_operation','replay_verification'}
REVIEW_LIMITS = {'wall_seconds':600, 'address_space_bytes':4294967296, 'output_bytes':20971520}


def tree_bytes(root):
    return sum(p.stat().st_size for p in Path(root).rglob('*') if p.is_file())


def inventory(root):
    return [{'name':p.name,'bytes':p.stat().st_size,'sha256':sha(p),
             'canonical':p.name not in EXCLUDED_OPERATIONAL}
            for p in sorted(Path(root).iterdir()) if p.is_file()] if Path(root).is_dir() else []


def bound_files(rows):
    bound = {}
    for row in rows:
        path = str(Path(row['path']).resolve())
        require(path not in bound and sha(path) == row['sha256'], 'changed_or_duplicate_binding')
        bound[path] = row['sha256']
    return bound


def registration(path):
    plan = read(path)
    require(plan['phase'] == 'frozen_before_pilot6_replication' and plan['limits'] == GLOBAL_LIMITS,
            'global_execution_registration_changed')
    require(plan['runner_sha256'] == sha(RUNNER), 'registered_runner_changed')
    bindings = bound_files(plan['bound_artifacts'])
    cohort_path = Path(plan['cohort_index'])
    require(plan['cohort_sha256'] == sha(cohort_path), 'registered_cohort_changed')
    required = {str(p.resolve()) for p in (Path(__file__), PRIOR, RUNNER, P5_RUNNER, cohort_path)}
    cohort = read(cohort_path)
    require(cohort['target_pairs'] == 10 and 0 <= len(cohort['pairs']) <= 10, 'cohort_count_mismatch')
    excluded = cohort['excluded_account_keys']
    require(len(excluded) == len(set(excluded)) == 119 and all(k == k.casefold() for k in excluded), 'exclusion_union_mismatch')
    account_seen, pair_seen, case_seen, record_seen = set(), set(), set(), set()
    indices = {}
    for pair in cohort['pairs']:
        pid = pair['pair_id']
        require(isinstance(pid,str) and Path(pid).name == pid and pid.startswith('pilot6-pair-') and
                '\\' not in pid and pid not in pair_seen, 'unsafe_duplicate_pair')
        pair_seen.add(pid)
        accounts = pair['source_account_keys']
        require(len(accounts) == len(set(accounts)) == 2 and all(a == a.casefold() for a in accounts) and
                not set(accounts) & (set(excluded)|account_seen), 'source_accounts_not_new_disjoint')
        account_seen.update(accounts)
        required.update(str(Path(pair[f]).resolve()) for f in ('index','registration'))
        pplan, index = read(pair['registration']), read(pair['index'])
        require(pplan['prepared_index_sha256'] == sha(pair['index']) and pplan['runner_sha256'] == sha(P5_RUNNER),
                'per_pair_registration_changed')
        require(pplan['phase'] == 'frozen_before_shared_anchor_diagnostic' and pplan['limits'] == PAIR_LIMITS
                and pplan['execution_environment'] == ORIGINAL_ENV and pplan['replay_environment'] == REPLAY_ENV,
                'unchanged_pair_contract_changed')
        pbound = bound_files(pplan['bound_artifacts'])
        require({str((ROOT/'studies/pilot4_chronological_controls/scripts'/n).resolve()) for n in HELPER_NAMES}
                <= pbound.keys(), 'per_pair_helper_not_bound')
        ibound = bound_files(index['bound_files'])
        require([c['condition'] for c in index['cases']] == list(CONDITIONS), 'all_four_conditions_required')
        pair_records = set()
        for case in index['cases']:
            condition = case['condition']
            switched, changed = condition.startswith('switch_'), condition.endswith('changed_community')
            require(case['block_id'] == pid and case['case_id'] == f'{pid}:AX:{condition}' and case['anchor_id'] == 'AX'
                    and case['source_switch'] is switched and case['community_change'] is changed, 'four_case_descriptor_mismatch')
            require(case['case_id'] not in case_seen, 'duplicate_case')
            case_seen.add(case['case_id'])
            require(all(str(Path(case[f]).resolve()) in ibound for f in ('input','manifest','metadata')), 'unbound_case_file')
            rows = read(case['metadata'])['records']
            ids = [m['record_id'] for m in rows]
            require(len(ids) == len(set(ids)), 'duplicate_original_metadata_id')
            pair_records.update(ids)
        require(not pair_records & record_seen, 'original_record_repeated_between_pairs')
        record_seen.update(pair_records)
        indices[pid] = index
    require(required <= bindings.keys(), 'independent_checker_or_input_not_preregistered')
    return plan, cohort, indices


def receipt(path, case_id):
    try:
        doc = read(path)
        required = ('exit_code','wall_seconds','child_peak_rss_mib','external_wall_limit_reached','external_artifact_limit_reached')
        if not isinstance(doc,dict) or doc.get('case_id') != case_id or not all(k in doc for k in required):
            return None
        return doc
    except (OSError, ValueError, TypeError):
        return None


def operational_records(directory, case_ids, strict=False, pair=None, replay=False):
    """Complete verified receipts or explicit unverified partial-operation evidence."""
    receipts = {cid:receipt(directory/cid/'receipt.json',cid) for cid in case_ids}
    try:
        execution = read(directory/'execution.json')
        rows = execution['cases']
        require([r['case_id'] for r in rows] == case_ids and all(isinstance(r.get('status'),str) and
                (r.get('receipt') is None or r['receipt'] == receipts[r['case_id']]) for r in rows), 'execution_receipt_membership_mismatch')
    except (OSError, ValueError, TypeError, KeyError):
        require(not strict, 'complete_phase_missing_valid_execution')
        rows = [{'case_id':cid,'status':'incomplete_execution_manifest','receipt':receipts[cid]}
                for cid in case_ids if (directory/cid/'receipt.json').exists() or (directory/(cid+'.worker.json')).exists()]
    if strict:
        binding = read(directory/'start-binding.json')
        require(binding['case_ids'] == case_ids and binding['replay'] is replay and execution['replay'] is replay,
                'execution_start_membership_mismatch')
        require(binding['registration_sha256'] == sha(pair['registration']) and binding['index_sha256'] == sha(pair['index'])
                and binding['runner_sha256'] == sha(P5_RUNNER), 'per_pair_execution_hash_mismatch')
        pplan = read(pair['registration'])
        env = REPLAY_ENV if replay else ORIGINAL_ENV
        require(binding['environment'] == env == pplan['replay_environment' if replay else 'execution_environment'],
                'execution_environment_changed')
        require(set(binding['helper_sha256']) == HELPER_NAMES, 'executed_helper_set_changed')
        for name, digest in binding['helper_sha256'].items():
            require(sha(ROOT/'studies/pilot4_chronological_controls/scripts'/name) == digest, 'executed_helper_changed')
        for row in rows:
            saved = row.get('receipt')
            inv = inventory(directory/row['case_id']/'analysis')
            if saved is not None:
                require(row['status'] == 'attempted' and saved['environment'] == env and saved['artifacts'] == inv,
                        'receipt_artifact_or_environment_mismatch')
            else:
                require(row['status'] != 'attempted' and row.get('surviving_artifacts',[]) == inv, 'unreceipted_artifact_mismatch')
    return {r['case_id']:r for r in rows}


def metadata_check(case, public, fallback):
    """Reconstruct grid and full temporal description independently for all slots."""
    rows = read(case['metadata'])['records']
    times = [prior.timestamp(r['created_utc']) for r in rows]
    require(times == sorted(times), 'metadata_time_order_changed')
    windows, k = prior.reconstruct(rows), case['truth_k'] if case['source_switch'] else case['control_junction_k']
    legal = prior.grid(windows)
    nearest = min(legal,key=lambda b:(prior.error(b['split_interval'],k),b['window_index'])) if legal else None
    best = prior.error(nearest['split_interval'],k) if nearest else None
    qualify = [w for w in windows if w['qualified']]
    grid = {'reference_type':'source_switch_truth' if case['source_switch'] else 'control_construction_junction',
        'reference_split_k':k,'qualified_window_count':len(qualify),'minimum_qualified_windows':8,'minimum_segment_windows':3,
        'adequate_window_count':len(qualify)>=8,'legal_boundary_count':len(legal),'best_interval_error_records':best,
        'attainable_within_tolerance':best<=10 if best is not None else None,
        'exact_containment_attainable':best==0 if best is not None else None,
        'nearest_legal_boundary':{**nearest,**prior.bracket(nearest['split_interval'],times)} if nearest else None,
        'legal_boundaries':[{**g,**prior.bracket(g['split_interval'],times)} for g in legal]}
    temporal = {'supplied_record_count':len(rows),'missing_timestamp_count':0,'first_utc':prior.stamp(times[0]),
        'last_utc':prior.stamp(times[-1]),'elapsed_seconds':(times[-1]-times[0]).total_seconds(),
        'construction_junction':prior.bracket([k,k],times),
        'qualified_windows':[{'window_index':i,'first_record_position':w['positions'][0],
            'last_record_position':w['positions'][-1],'record_count':len(w['positions']),'word_count':w['word_count'],
            'first_utc':prior.stamp(times[w['positions'][0]]),'last_utc':prior.stamp(times[w['positions'][-1]]),
            'straddles_construction_junction':w['positions'][0]<k<=w['positions'][-1]} for i,w in enumerate(qualify)]}
    score = public['score']
    require(score['grid_resolution'] == grid and score['temporal_resolution'] == temporal, 'independent_grid_or_temporal_mismatch')
    require(public['record_count'] == len(rows) and public['retained_words'] == sum(r['retained_words'] for r in rows), 'volume_mismatch')
    require(score['schema_version'] == 'pilot4-chronology-math-v1' and score['tolerance_records'] == 10, 'frozen_math_contract_changed')
    if fallback:
        expected = {'status':'unavailable','executed':False,'candidate_occurrence':None,'candidate_count':None,
            'candidate_intervals':None,'truth_boundaries':[k] if case['source_switch'] else [],
            'switch_localization':prior.localization(None,k,best,times) if case['source_switch'] else None,
            'control_junction_diagnostic':None if case['source_switch'] else prior.localization(None,k,best,times)}
        require(all(score[key] == value for key,value in expected.items()), 'unverified_result_not_null')
        require(public['native_change_status'] is None and public['results_sha256'] is None and
                public['full_pipeline_statuses'] is None and public['effective_exit_code'] is None and
                public['primary_window_check'] == 'metadata_reconstruction_only_unverified_execution', 'fallback_falsely_claims_verified_native_result')
    intervals = score['candidate_intervals']
    errors = [prior.error(i['split_interval'],k) for i in intervals] if intervals is not None else None
    require(public['all_candidate_interval_errors_records'] == errors, 'every_candidate_error_mismatch')
    return {'candidate_count':score['candidate_count'],'executed':score['executed'],
            'qualified_windows':len(qualify),'best_grid_error_records':best,'all_candidate_errors_records':errors}


def operation_check(public, attempt, directory, case_id):
    rec = attempt.get('receipt') if attempt else None
    expected = {'dispatched':bool(attempt and attempt['status'] not in ('not_dispatched_wall_limit','not_dispatched_artifact_limit')),
        'status':attempt['status'] if attempt else 'not_dispatched_or_unrecorded',
        'exit_code':attempt.get('effective_exit_code',rec['exit_code'] if rec else None) if attempt else None,
        'wall_seconds':rec['wall_seconds'] if rec else None,'child_peak_rss_mib':rec['child_peak_rss_mib'] if rec else None,
        'artifact_bytes':tree_bytes(directory/case_id/'analysis')}
    require(public == expected, 'operating_cost_or_dispatch_mismatch')
    for key in ('wall_seconds','child_peak_rss_mib'):
        require(public[key] is None or isinstance(public[key],(int,float)) and math.isfinite(public[key]) and public[key]>=0,
                'invalid_operating_cost')
    return expected


def replay_check(pair, index, directory, enabled, aggregate):
    if not enabled:
        require(aggregate['replay_all_passed'] is None and all(r['replay_verification']['all_files_byte_identical'] is None
                and r['replay_verification']['canonical_file_count'] is None for r in aggregate['cases']), 'unverified_replay_claimed')
        return None
    saved = read(directory/'replay-check.json')
    require(saved['excluded_operational_files'] == sorted(EXCLUDED_OPERATIONAL) and saved['replayed_histories'] == 4
            and saved['independent_replicates_estimated'] is False and saved['original_environment'] == ORIGINAL_ENV
            and saved['replay_environment'] == REPLAY_ENV, 'replay_design_changed')
    require([r['case_id'] for r in saved['cases']] == [c['case_id'] for c in index['cases']], 'four_replay_slots_required')
    passed = []
    for case, reported, public in zip(index['cases'],saved['cases'],aggregate['cases'],strict=True):
        for field in ('input','manifest'):
            relocated = directory/'replay/relocated'/(case['case_id']+'.'+field+Path(case[field]).suffix)
            require(relocated.is_file() and sha(relocated) == sha(case[field]), 'relocated_input_changed')
        inventories = [{r['name']:{k:r[k] for k in ('bytes','sha256')} for r in inventory(directory/phase/case['case_id']/'analysis')
                        if r['canonical']} for phase in ('main','replay')]
        same = bool(inventories[0]) and inventories[0] == inventories[1]
        different = sorted(k for k in inventories[0].keys()|inventories[1].keys() if inventories[0].get(k)!=inventories[1].get(k))
        expected = {'case_id':case['case_id'],'canonical_file_count':len(inventories[0]),'all_files_byte_identical':same,
            'differing_files':different,'original_dispatch_status':public['main_operation']['status'],
            'replay_dispatch_status':public['replay_operation']['status']}
        require(reported == expected == public['replay_verification'], 'independent_replay_hash_mismatch')
        passed.append(same)
    require(saved['all_passed'] is all(passed) and aggregate['replay_all_passed'] is all(passed), 'replay_summary_mismatch')
    require(tree_bytes(directory/'main')+tree_bytes(directory/'replay') <= 8*1024**3, 'per_pair_artifact_limit_exceeded')
    return all(passed)


def check(registration_path, run_root):
    plan, cohort, indices = registration(registration_path)
    root = Path(run_root)
    summary, public, start = read(root/'summary.json'), read(root/'cases.json'), read(root/'start-binding.json')
    case_ids = [c['case_id'] for pair in cohort['pairs'] for c in indices[pair['pair_id']]['cases']]
    require([c['case_id'] for c in public] == case_ids, 'aggregate_lost_or_reordered_case_slots')
    require(start['registration_sha256'] == sha(registration_path) and start['cohort_sha256'] == plan['cohort_sha256']
            and start['runner_sha256'] == sha(RUNNER) and start['unchanged_pilot5_runner_sha256'] == sha(P5_RUNNER)
            and start['limits'] == GLOBAL_LIMITS and start['case_ids'] == case_ids
            and start['pair_ids'] == [p['pair_id'] for p in cohort['pairs']], 'global_execution_binding_mismatch')
    pairs, checked_cases, rows_flat = [], [], []
    preceding_pair_bytes, earlier_dispatch = 0, False
    for pair in cohort['pairs']:
        directory, index = root/pair['pair_id'], indices[pair['pair_id']]
        aggregate = read(directory/'pair-summary.json')
        phases = aggregate['phases']
        require({'main','score','replay','replay-check'} <= phases.keys(), 'lost_phase_slot')
        pre_pair_bytes = (root/'start-binding.json').stat().st_size+preceding_pair_bytes
        if earlier_dispatch:
            pre_pair_bytes += (root/'first-dispatch.json').stat().st_size
        pair_dispatched = (not phases['main']['status'].startswith('not_dispatched')
                           and phases['main'].get('wall_seconds') != 0)
        if pair_dispatched:
            require(pre_pair_bytes+GLOBAL_LIMITS['pair_reserved_artifact_bytes'] <= GLOBAL_LIMITS['global_artifact_bytes'],
                    'pair_dispatched_without_full_artifact_reservation')
            earlier_dispatch = True
        elif phases['main']['status'] == 'not_dispatched_global_artifact_reservation':
            require(pre_pair_bytes+GLOBAL_LIMITS['pair_reserved_artifact_bytes'] > GLOBAL_LIMITS['global_artifact_bytes'],
                    'artifact_reservation_stop_not_supported_by_saved_bytes')
        require(aggregate['pair_id'] == pair['pair_id'] and [r['case_id'] for r in aggregate['cases']] ==
                [c['case_id'] for c in index['cases']], 'pair_case_slots_changed')
        failed_collection = 'collection' in phases
        scored = phases['score']['status'] == 'completed' and not failed_collection
        verified_replay = phases['replay-check']['status'] == 'completed' and not failed_collection
        main = operational_records(directory/'main',[c['case_id'] for c in index['cases']],
            strict=phases['main']['status']=='completed',pair=pair)
        replay = operational_records(directory/'replay',[c['case_id'] for c in index['cases']],
            strict=phases['replay']['status']=='completed',pair=pair,replay=True)
        inherited = None
        if scored:
            inherited = prior.check(pair['index'],pair['registration'],directory/'main',directory/'scores')
            original = read(directory/'scores/cases.json')
            require([{k:v for k,v in row.items() if k not in ADDED_FIELDS} for row in aggregate['cases']] == original,
                    'aggregate_changed_original_adapter_scores')
        require(aggregate['inherited_adapter_summary']['study_label'] == 'pilot5_shared_anchor_exploratory' and
                aggregate['inherited_adapter_summary']['sha256'] == (sha(directory/'scores/summary.json') if scored else None),
                'inherited_adapter_summary_mismatch')
        for case, row in zip(index['cases'],aggregate['cases'],strict=True):
            require(all(row[k] == case[k] for k in DESCRIPTORS) and row['pair_id'] == pair['pair_id'], 'reported_descriptor_mismatch')
            checked = metadata_check(case,row,not scored)
            if not scored:
                require(row['score']['reason_codes'] == [aggregate['status']], 'unavailable_reason_mismatch')
            for label, records, phase in (('main_operation',main,'main'),('replay_operation',replay,'replay')):
                operation_check(row[label],records.get(case['case_id']),directory/phase,case['case_id'])
            rec = receipt(directory/'main'/case['case_id']/'receipt.json',case['case_id'])
            resources = {k:rec[k] for k in ('exit_code','wall_seconds','child_peak_rss_mib',
                         'external_wall_limit_reached','external_artifact_limit_reached')} if rec else None
            require(row['resources'] == resources, 'reported_main_resources_mismatch')
            require(row['artifact_bytes'] == tree_bytes(directory/'main'/case['case_id']/'analysis'), 'reported_native_artifact_bytes_mismatch')
            if scored:
                attempt = main[case['case_id']]
                require(row['dispatch_status'] == attempt['status'] and row['effective_exit_code'] == row['main_operation']['exit_code']
                        and row['external_wrapper_artifact_limit_reached'] == attempt.get('artifact_limit_reached',False),
                        'reported_execution_status_mismatch')
                result_path = directory/'main'/case['case_id']/'analysis/results.json'
                try:
                    native = read(result_path) if result_path.exists() else None
                except json.JSONDecodeError:
                    require(row['effective_exit_code'] != 0, 'successful_invalid_native_json')
                    native = None
                module_status = {k:{'status':v['status'],'reason_codes':v['reason_codes']}
                                 for k,v in native['modules'].items()} if native else None
                require(row['full_pipeline_statuses'] == module_status, 'reported_full_module_status_mismatch')
            checked_cases.append({'pair_id':pair['pair_id'],'condition':case['condition'],**checked})
        replay_ok = replay_check(pair,index,directory,verified_replay,aggregate)
        require(aggregate['artifact_bytes'] == tree_bytes(directory)-(directory/'pair-summary.json').stat().st_size,
                'pair_total_artifact_cost_mismatch')
        pairs.append({'pair_id':pair['pair_id'],'status':aggregate['status'],'replay_all_passed':replay_ok,
                      'independent_main_arithmetic_check':inherited['status'] if inherited else 'unavailable_preserved_null',
                      'all_four_primary_executed':all(r['score']['executed'] for r in aggregate['cases'])})
        rows_flat.extend(aggregate['cases'])
        preceding_pair_bytes += tree_bytes(directory)
    require(rows_flat == public, 'pair_to_global_case_reconciliation_failed')
    expected = {'study':'pilot6_shared_anchor_replication','target_new_pairs':10,'registered_new_pairs':len(pairs),
        'prescore_pair_shortfall':10-len(pairs),'planned_main_histories':len(public),'planned_replay_histories':len(public),
        'main_dispatched_histories':sum(r['main_operation']['dispatched'] for r in public),
        'replay_dispatched_histories':sum(r['replay_operation']['dispatched'] for r in public),
        'main_executed_primary_histories':sum(r['score']['executed'] for r in public),
        'main_unavailable_primary_histories':sum(not r['score']['executed'] for r in public),
        'pairs_with_four_executed_primary_histories':sum(p['all_four_primary_executed'] for p in pairs),
        'pairs_with_four_verified_replays':sum(p['replay_all_passed'] is True for p in pairs),
        'condition_counts':dict(Counter(r['condition'] for r in public)),
        'registration_sha256':sha(registration_path),'cohort_sha256':plan['cohort_sha256'],
        'pair_statuses':[{k:p[k] for k in ('pair_id','status','replay_all_passed')} for p in pairs],
        'artifact_bytes_before_final_reports':tree_bytes(root)-(root/'summary.json').stat().st_size-(root/'cases.json').stat().st_size}
    require(all(summary[k] == v for k,v in expected.items()), 'independent_aggregate_denominator_or_cost_mismatch')
    dispatched = (root/'first-dispatch.json').exists()
    wall = summary['global_wall_seconds_since_first_dispatch']
    require((wall is not None) == dispatched and (wall is None or math.isfinite(wall) and wall>=0), 'global_wall_receipt_mismatch')
    if wall is not None and wall > GLOBAL_LIMITS['global_wall_seconds']:
        require(summary['stop_reason'] is not None or all(p['status']=='completed' for p in pairs), 'unreported_global_wall_overrun')
    # The watchdog bounds execution artifacts. Fresh terminal summary files are
    # written after dispatch stops and are reported separately, not retrospectively
    # treated as evidence that another analyzer was dispatched over budget.
    guarded_bytes = expected['artifact_bytes_before_final_reports']
    if guarded_bytes > GLOBAL_LIMITS['global_artifact_bytes']:
        require(summary['stop_reason'] is not None and 'artifact' in summary['stop_reason'], 'unreported_global_artifact_overrun')
    costs = {}
    for label in ('main_operation','replay_operation'):
        operations = [r[label] for r in public]
        times = [o['wall_seconds'] for o in operations if o['wall_seconds'] is not None]
        rss = [o['child_peak_rss_mib'] for o in operations if o['child_peak_rss_mib'] is not None]
        costs[label] = {'recorded_wall_time_histories':len(times),'sum_case_wall_seconds':sum(times),
                        'maximum_recorded_child_peak_rss_mib':max(rss) if rss else None,
                        'native_artifact_bytes':sum(o['artifact_bytes'] for o in operations)}
    return {'status':'passed','analyzer_calls':0,'new_source_account_pairs':len(pairs),
        'planned_main_histories':len(public),'planned_replay_histories':len(public),
        'main_executed_primary_histories':expected['main_executed_primary_histories'],
        'main_unavailable_primary_histories':expected['main_unavailable_primary_histories'],
        'pairs_with_four_verified_replays':expected['pairs_with_four_verified_replays'],
        'cases':checked_cases,'pairs':pairs,'independent_sampling_units':len(pairs),
        'counting_note':'Each source-account pair is one replication unit. Shared-anchor histories and deterministic replays are dependent observations, not additional independent replications.',
        'prior_independent_checker_sha256':sha(PRIOR),'registration_sha256':sha(registration_path),
        'aggregate_cases_sha256':sha(root/'cases.json'),'aggregate_summary_sha256':sha(root/'summary.json'),
        'operating_costs':costs,'execution_artifact_bytes_before_final_reports':guarded_bytes,
        'final_reports_bytes':(root/'summary.json').stat().st_size+(root/'cases.json').stat().st_size,
        'resource_limit_note':'Limits trigger termination; oversized evidence is preserved. Independent cost checks distinguish execution artifacts from the final aggregate reports.',
        'source_prose_inspected':False,'scope':'Frozen bindings; all four-condition slots; unchanged independent Pilot5 native/window/grid checks; independent full temporal/null arithmetic, all interval distances, receipt costs, canonical replay hashes and aggregate denominators.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration',required=True,type=Path)
    parser.add_argument('--run',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(REVIEW_LIMITS['address_space_bytes'],)*2)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('independent_review_time_limit')))
    signal.alarm(REVIEW_LIMITS['wall_seconds'])
    started = time.monotonic()
    start = {'started_utc':datetime.now(timezone.utc).isoformat(),'checker_sha256':sha(__file__),
             'prior_independent_checker_sha256':sha(PRIOR),'registration_sha256':sha(args.registration),
             'aggregate_cases_sha256':sha(args.run/'cases.json'),'aggregate_summary_sha256':sha(args.run/'summary.json'),
             'limits':REVIEW_LIMITS}
    with Path(str(args.out)+'.start-binding.json').open('x') as handle:
        json.dump(start,handle,sort_keys=True,indent=2); handle.write('\n')
    try:
        report = check(args.registration,args.run)
    except Exception as error:
        report = {'status':'failed','error_type':type(error).__name__,'analyzer_calls':0}
        if isinstance(error,ValueError) and len(str(error)) < 160 and all(c.isalnum() or c=='_' for c in str(error)):
            report['check_code'] = str(error)
    report.update(checker_sha256=start['checker_sha256'],wall_seconds=time.monotonic()-started)
    data = json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n'
    require(len(data.encode()) <= REVIEW_LIMITS['output_bytes'], 'review_output_limit')
    with args.out.open('x') as handle:
        handle.write(data)
    print(json.dumps({'status':report['status'],'analyzer_calls':0}))
    return 0 if report['status']=='passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
