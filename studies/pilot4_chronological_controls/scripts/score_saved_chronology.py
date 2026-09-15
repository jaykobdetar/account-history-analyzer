"""Read-only evaluation of saved full-pipeline outputs against frozen metadata."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from chronology_math import aggregate_cases, factorial_cases, reconstruct_windows, score_case
from matched_condition_changes import matched_changes
from run_full_chronology import extract_primary, sha, write, artifact_inventory


def metadata_ids(metadata):
    ids = [row['record_id'] for row in metadata]
    if any(not isinstance(identifier, str) or not identifier for identifier in ids) or len(ids) != len(set(ids)):
        raise ValueError('Prepared metadata must preserve distinct original record identities')
    return ids


def checked_windows(metadata, analysis_dir, stream_id, primary_window_ids=None):
    metadata_ids(metadata)
    expected = reconstruct_windows(metadata)
    path = Path(analysis_dir)/'windows.jsonl'
    if not path.exists() or stream_id is None:
        return expected, 'no_saved_primary_windows'
    if (not isinstance(primary_window_ids, list) or len(primary_window_ids) != len(set(primary_window_ids))
            or any(not isinstance(identifier, str) or not identifier for identifier in primary_window_ids)):
        raise ValueError('Exact distinct primary window IDs from the saved stream summary are required')
    requested = set(primary_window_ids)
    actual = []
    with path.open() as handle:
        for line in handle:
            row = json.loads(line)
            if row['window_id'] in requested:
                if row['stream_id'] != stream_id:
                    raise ValueError('Declared primary window belongs to another stream')
                actual.append(row)
    if len(actual) != len(requested) or {row['window_id'] for row in actual} != requested:
        raise ValueError('Every declared primary window must occur exactly once')
    actual.sort(key=lambda row: row['first_record_position'])
    if [row['window_id'] for row in actual] != primary_window_ids:
        raise ValueError('Saved primary window summary is not in canonical order')
    fields = ('qualified', 'first_record_position', 'last_record_position', 'record_count', 'word_count')
    projection = lambda rows: [[r[f] for f in fields] for r in rows]
    if projection(expected) != projection(actual):
        raise ValueError('Saved primary windows differ from independently reconstructed whole-record windows')
    for reconstructed, saved in zip(expected, actual, strict=True):
        ids = [metadata[p]['record_id'] for p in reconstructed['record_positions']]
        if ids != saved['record_ids']:
            raise ValueError('Saved primary window membership differs from prepared metadata')
    return expected, 'all_primary_memberships_counts_positions_verified'


def checked_execution(run_root):
    """Reconcile saved dispatch membership and all currently saved artifact bytes."""
    root = Path(run_root)
    execution = json.loads((root/'execution.json').read_bytes())
    binding = json.loads((root/'start-binding.json').read_bytes())
    attempts = execution['cases']
    identifiers = [row['case_id'] for row in attempts]
    if not identifiers or len(identifiers) != len(set(identifiers)):
        raise ValueError('Execution manifest must contain distinct nonempty planned cases')
    if any(not isinstance(identifier, str) or not identifier or Path(identifier).name != identifier
           or identifier in {'.', '..'} for identifier in identifiers):
        raise ValueError('Unsafe saved case directory name')
    if identifiers != binding['case_ids'] or execution['replay'] != binding['replay']:
        raise ValueError('Execution manifest differs from its start binding')
    for attempt in attempts:
        receipt = attempt.get('receipt')
        if receipt is None:
            if attempt['status'] == 'attempted':
                raise ValueError('Attempted case has no execution receipt')
            continue
        if receipt['case_id'] != attempt['case_id'] or attempt['status'] != 'attempted':
            raise ValueError('Receipt identity differs from execution membership')
        case_root = root/attempt['case_id']
        if json.loads((case_root/'receipt.json').read_bytes()) != receipt:
            raise ValueError('Saved case receipt differs from execution manifest')
        if artifact_inventory(case_root/'analysis') != receipt['artifacts']:
            raise ValueError('Saved analysis artifact inventory differs from execution receipt')
    return execution, binding, {row['case_id']: row for row in attempts}


def score(index_path, run_root, out):
    index = json.loads(Path(index_path).read_bytes())
    bound = [str(Path(artifact['path']).resolve()) for artifact in index['bound_files']]
    if len(bound) != len(set(bound)):
        raise ValueError('Duplicate prepared file binding')
    required = {str(Path(case[field]).resolve()) for case in index['cases']
                for field in ('input', 'manifest', 'metadata')}
    if not required.issubset(set(bound)):
        raise ValueError('Every prepared input, manifest, and metadata file must be hash-bound')
    for artifact in index['bound_files']:
        if sha(artifact['path']) != artifact['sha256']:
            raise ValueError('Prepared input changed')
    execution, binding, attempts = checked_execution(run_root)
    if binding['index_sha256'] != sha(index_path) or binding['replay']:
        raise ValueError('Primary scoring requires the bound original complete execution')
    identifiers = [case['case_id'] for case in index['cases']]
    if len(identifiers) != len(set(identifiers)) or set(attempts) != set(identifiers):
        raise ValueError('Executed case list differs from all planned cases')
    rows = []
    for case in index['cases']:
        attempt = attempts[case['case_id']]
        receipt = attempt.get('receipt')
        directory = Path(run_root)/case['case_id']/'analysis'
        result_file = directory/'results.json'
        exit_code = receipt['exit_code'] if receipt else None
        try:
            result = json.loads(result_file.read_bytes()) if result_file.exists() else None
        except json.JSONDecodeError:
            if exit_code == 0:
                raise ValueError('Successful execution has invalid saved results') from None
            result = None
        primary = extract_primary(result, exit_code)
        metadata = json.loads(Path(case['metadata']).read_bytes())['records']
        metadata_ids(metadata)
        executed = primary['status'] in {'ok', 'no_measurable_variation'}
        if executed and primary['native_change_status'] == 'no_measurable_variation' and primary['candidate_intervals']:
            raise ValueError('A constant primary series cannot report candidates')
        try:
            windows, validation = checked_windows(metadata, directory, primary['stream_id'], primary['primary_window_ids'])
        except (ValueError, KeyError, json.JSONDecodeError):
            if executed:
                raise
            windows = reconstruct_windows(metadata)
            validation = 'unavailable_partial_windows_unverified'
        if executed and validation != 'all_primary_memberships_counts_positions_verified':
            raise ValueError('Executed primary result requires exact saved-window membership verification')
        scoring = score_case(candidate_intervals=primary['candidate_intervals'], status=primary['status'],
            reason_codes=primary['reason_codes'], truth_k=case['truth_k'],
            control_junction_k=case['control_junction_k'], windows=windows,
            record_timestamps=[r['created_utc'] for r in metadata])
        public = {k: case[k] for k in ('case_id','block_id','stratum_id','anchor_id','condition',
                    'source_switch','community_change','left_cell_id','right_cell_id')}
        public.update(score=scoring, primary_window_check=validation,
                      native_change_status=primary['native_change_status'],
                      record_count=len(metadata), retained_words=sum(r['retained_words'] for r in metadata),
                      full_pipeline_statuses={k: {'status': v['status'], 'reason_codes': v['reason_codes']}
                                              for k,v in result['modules'].items()} if result else None,
                      resources={k:receipt[k] for k in ('exit_code','wall_seconds','child_peak_rss_mib',
                                 'external_wall_limit_reached')} if receipt else None,
                      artifact_bytes=sum(a['bytes'] for a in receipt['artifacts']) if receipt else 0,
                      results_sha256=sha(result_file) if result_file.exists() else None)
        rows.append(public)
    summary = {'all_strata':aggregate_cases(rows),
        'by_stratum':{s:aggregate_cases([r for r in rows if r['stratum_id']==s])
                      for s in sorted({r['stratum_id'] for r in rows})},
        'matched_changes_all_strata':matched_changes(rows),
        'matched_changes_by_stratum':{s:matched_changes([r for r in rows if r['stratum_id']==s])
                                      for s in sorted({r['stratum_id'] for r in rows})},
        'input_index_sha256':sha(index_path), 'execution_manifest_sha256':sha(Path(run_root)/'execution.json')}
    out = Path(out)
    out.mkdir(exist_ok=False, parents=True)
    write(out/'cases.json', rows)
    write(out/'summary.json', summary)
    fields=['case_id','block_id','stratum_id','anchor_id','condition','executed','candidate_count',
            'candidate_occurrence','record_count','retained_words','native_change_status',
            'switch_matched_within_10','switch_nearest_error_records','control_junction_matched_within_10',
            'control_junction_nearest_error_records','artifact_bytes']
    with (out/'cases.csv').open('x') as f:
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader()
        for row in rows:
            record={k:row[k] for k in fields if k in row}
            record.update({k:row['score'][k] for k in ('executed','candidate_count','candidate_occurrence')})
            for prefix, field in [('switch','switch_localization'),('control_junction','control_junction_diagnostic')]:
                loc=row['score'][field]
                record[prefix+'_matched_within_10']=loc['matched_within_tolerance'] if loc else None
                record[prefix+'_nearest_error_records']=loc['nearest_interval_error_records'] if loc else None
            writer.writerow(record)


def replay_check(first, replay, out):
    first, replay = Path(first), Path(replay)
    _, first_binding, first_attempts = checked_execution(first)
    execution, replay_binding, replay_attempts = checked_execution(replay)
    if first_binding['replay'] or not replay_binding['replay']:
        raise ValueError('Replay comparison needs the original and relocated replay runs')
    if any(first_binding[key] != replay_binding[key] for key in ('index_sha256', 'registration_sha256', 'runner_sha256')):
        raise ValueError('Replay is not bound to the same registered inputs and runner')
    identifiers = list(replay_attempts)
    block = identifiers[0].rsplit(':', 2)[0]
    if set(identifiers) != {row['case_id'] for row in factorial_cases(block)} or not set(identifiers).issubset(first_attempts):
        raise ValueError('Replay must retain all 16 cases of one original factorial block')
    attempts = execution['cases']
    rows=[]
    for case in attempts:
        case_id=case['case_id']
        inventories=[]
        for root in (first,replay):
            inventories.append({r['name']:{k:r[k] for k in ('bytes','sha256')}
                                for r in artifact_inventory(root/case_id/'analysis') if r['canonical']})
        rows.append({'case_id':case_id,'canonical_file_count':len(inventories[0]),
                     'all_files_byte_identical':bool(inventories[0]) and inventories[0]==inventories[1],
                     'differing_files':sorted(k for k in set(inventories[0])|set(inventories[1])
                                             if inventories[0].get(k)!=inventories[1].get(k))})
    write(out,{'cases':rows,'all_passed':all(r['all_files_byte_identical'] for r in rows),
               'excluded_operational_files':['ingest_receipt.json','run_receipt.json']})


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--index',type=Path)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--replay',type=Path)
    args=p.parse_args()
    if args.replay:
        replay_check(args.run,args.replay,args.out)
    else:
        score(args.index,args.run,args.out)
