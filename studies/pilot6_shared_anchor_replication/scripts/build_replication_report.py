"""Deterministic public reporting from independently verified saved Pilot6 results.

No analyzer imports, native artifact reads, source prose, or new selection.
Complete safe global JSON is copied byte-for-byte; operational receipts are
projected without commands, private paths, or stdout/stderr contents.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re

CONDITIONS = ('continuity_same_community', 'switch_same_community',
              'continuity_changed_community', 'switch_changed_community')
LABELS = dict(zip(CONDITIONS, ('Continuity / same community', 'Source switch / same community',
                              'Continuity / changed community', 'Both switches')))
MAX_INPUT_BYTES = 32 * 1024**2
MAX_OUTPUT_BYTES = 64 * 1024**2
CASE_FIELDS = {'case_id', 'block_id', 'stratum_id', 'anchor_id', 'condition', 'source_switch',
    'community_change', 'left_cell_id', 'right_cell_id', 'score', 'primary_window_check',
    'native_change_status', 'record_count', 'retained_words', 'full_pipeline_statuses', 'resources',
    'effective_exit_code', 'dispatch_status', 'external_wrapper_artifact_limit_reached',
    'artifact_bytes', 'results_sha256', 'pair_id', 'all_candidate_interval_errors_records',
    'main_operation', 'replay_operation', 'replay_verification'}
SUMMARY_FIELDS = {'study', 'target_new_pairs', 'registered_new_pairs', 'prescore_pair_shortfall',
    'planned_main_histories', 'planned_replay_histories', 'main_dispatched_histories',
    'replay_dispatched_histories', 'main_executed_primary_histories', 'main_unavailable_primary_histories',
    'pairs_with_four_executed_primary_histories', 'pairs_with_four_verified_replays', 'stop_reason',
    'global_wall_seconds_since_first_dispatch', 'artifact_bytes_before_final_reports', 'condition_counts',
    'registration_sha256', 'cohort_sha256', 'pair_statuses', 'counting_note', 'intervals_and_missingness'}
FORBIDDEN_KEYS = {'text', 'body', 'title', 'excerpt', 'quote', 'tokens', 'features', 'account_id',
    'account_key', 'account_a', 'account_b', 'source_account_keys', 'record_id', 'record_ids',
    'source_samples', 'selected_record_ids', 'input', 'manifest', 'metadata', 'argv', 'cwd',
    'source_path', 'permalink', 'thread_id', 'parent_id', 'user', 'author'}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    path = Path(path)
    require(path.is_file() and path.stat().st_size <= MAX_INPUT_BYTES, 'Input missing or exceeds reporting ceiling')
    return json.loads(path.read_bytes())


def safe(value, *, module_statuses=False):
    """Refuse source fields or local paths rather than silently redact science."""
    if isinstance(value, dict):
        if module_statuses:
            require(all(isinstance(item, dict) and set(item) == {'status', 'reason_codes'} for item in value.values()),
                    'Module status projection contains native payload')
        else:
            require(not FORBIDDEN_KEYS.intersection(value), 'Source-containing field cannot be published')
        for key, item in value.items():
            safe(item, module_statuses=key == 'full_pipeline_statuses')
    elif isinstance(value, list):
        for item in value:
            safe(item)
    elif isinstance(value, float):
        require(math.isfinite(value), 'Nonfinite report value')
    elif isinstance(value, str):
        require(not re.search(r'(?:/home/|/tmp/|file://|https?://)', value), 'Private path or external text link in scientific copy')
    else:
        require(value is None or type(value) in (bool, int), 'Unsupported report value')


def encoded(value):
    safe(value)
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n').encode()


def location(row):
    return row['score']['switch_localization' if row['source_switch'] else 'control_junction_diagnostic']


def validate_cases(cases, summary):
    require(set(summary) == SUMMARY_FIELDS and summary['study'] == 'pilot6_shared_anchor_replication', 'Unexpected global summary schema')
    require(type(summary['registered_new_pairs']) is int and 0 <= summary['registered_new_pairs'] <= 10,
            'Invalid registered replication denominator')
    by_pair = defaultdict(list)
    for row in cases:
        require(set(row) == CASE_FIELDS, 'Unexpected global case schema')
        pid, condition = row['pair_id'], row['condition']
        require(re.fullmatch(r'pilot6-pair-\d{2}', pid) and condition in CONDITIONS, 'Invalid public case identity')
        require(row['case_id'] == pid + ':AX:' + condition and row['block_id'] == pid and row['anchor_id'] == 'AX',
                'Case identity does not match its pair')
        require(row['source_switch'] is condition.startswith('switch_') and
                row['community_change'] is condition.endswith('changed_community'), 'Condition labels changed')
        score = row['score']
        require(type(score['executed']) is bool and score['tolerance_records'] == 10, 'Execution or tolerance contract changed')
        intervals, errors, loc = score['candidate_intervals'], row['all_candidate_interval_errors_records'], location(row)
        other = score['control_junction_diagnostic' if row['source_switch'] else 'switch_localization']
        require(other is None and isinstance(loc, dict), 'Control and switch localization mixed')
        k = score['grid_resolution']['reference_split_k']
        require(score['truth_boundaries'] == ([k] if row['source_switch'] else []), 'Control junction is not positive truth')
        if score['executed']:
            require(isinstance(intervals, list) and score['candidate_count'] == len(intervals) and
                    score['candidate_occurrence'] is bool(intervals), 'Executed candidate denominator mismatch')
            expected = [max(i['split_interval'][0] - k, k - i['split_interval'][1], 0) for i in intervals]
            require(errors == expected, 'Candidate intervals and every error must be preserved')
            require(loc['nearest_interval_error_records'] == (min(errors) if errors else None), 'Nearest error mismatch')
            require(loc['matched_within_tolerance'] is bool(errors and min(errors) <= 10) and
                    loc['exact_interval_containment'] is bool(errors and min(errors) == 0), 'Localization Boolean mismatch')
            if row['native_change_status'] == 'no_measurable_variation':
                require(not intervals and score['candidate_count'] == 0, 'No measurable variation is executed zero')
        else:
            require(intervals is None and errors is None and score['candidate_count'] is None and score['candidate_occurrence'] is None,
                    'Unavailable detection cannot become zero')
            require(all(loc[k] is None for k in ('nearest_interval_error_records', 'matched_within_tolerance',
                'exact_interval_containment', 'excess_error_over_best_grid_records')), 'Unavailable localization cannot be reported')
        by_pair[pid].append(row)
    require(all([r['condition'] for r in rows] == list(CONDITIONS) for rows in by_pair.values()), 'Every pair needs all four ordered conditions')
    require([r for rows in by_pair.values() for r in rows] == cases, 'Pair rows must remain contiguous')
    p = len(by_pair)
    require(summary['registered_new_pairs'] == p and summary['target_new_pairs'] == 10 and
            summary['prescore_pair_shortfall'] == 10 - p, 'Pair denominator mismatch')
    require(summary['planned_main_histories'] == summary['planned_replay_histories'] == len(cases) == 4 * p,
            'Main and replay denominators mismatch')
    require(summary['main_executed_primary_histories'] == sum(r['score']['executed'] for r in cases) and
            summary['main_unavailable_primary_histories'] == sum(not r['score']['executed'] for r in cases), 'Execution denominator mismatch')
    require(summary['condition_counts'] == dict(Counter(r['condition'] for r in cases)), 'Condition denominator mismatch')
    safe(cases); safe(summary)
    return dict(by_pair)


def condition_aggregates(cases):
    output = []
    for condition in CONDITIONS:
        rows = [r for r in cases if r['condition'] == condition]
        executed = [r for r in rows if r['score']['executed']]
        switches = condition.startswith('switch_')
        output.append({'condition': condition, 'interpretation': 'source_switch_truth' if switches else 'descriptive_control_junction',
            'planned_histories': len(rows), 'executed_histories': len(executed), 'unavailable_histories': len(rows) - len(executed),
            'candidate_present_histories': sum(r['score']['candidate_occurrence'] for r in executed),
            'executed_zero_candidate_histories': sum(r['score']['candidate_count'] == 0 for r in executed),
            'executed_no_measurable_variation_histories': sum(r['native_change_status'] == 'no_measurable_variation' for r in executed),
            'observed_candidate_count_sum': sum(r['score']['candidate_count'] for r in executed) if executed else None,
            'localization_label': 'switch_match' if switches else 'control_junction_alignment',
            'within_ten_records': {'numerator': sum(location(r)['matched_within_tolerance'] for r in executed), 'denominator_executed': len(executed)},
            'exact_interval_containment': {'numerator': sum(location(r)['exact_interval_containment'] for r in executed), 'denominator_executed': len(executed)},
            'metadata_grid_attainable_within_ten': {'numerator': sum(r['score']['grid_resolution']['attainable_within_tolerance'] is True for r in rows),
                'denominator_with_grid': sum(r['score']['grid_resolution']['attainable_within_tolerance'] is not None for r in rows)},
            'status_counts': dict(Counter(r['score']['status'] for r in rows)),
            'reason_counts': dict(Counter(reason for r in rows for reason in r['score']['reason_codes']))})
    return output


def operation_totals(cases, label):
    rows = [r[label] for r in cases]
    wall = [r['wall_seconds'] for r in rows if r['wall_seconds'] is not None]
    rss = [r['child_peak_rss_mib'] for r in rows if r['child_peak_rss_mib'] is not None]
    return {'planned_histories': len(rows), 'dispatched_histories': sum(r['dispatched'] for r in rows),
        'recorded_case_wall_time_histories': len(wall), 'sum_case_wall_seconds': sum(wall) if wall else None,
        'maximum_recorded_case_child_peak_rss_mib': max(rss) if rss else None,
        'native_artifact_bytes': sum(r['artifact_bytes'] for r in rows)}


def receipt_ledger(roots):
    rows, seen = [], set()
    for i, root in enumerate(roots, 1):
        root = Path(root)
        require(root.is_dir(), 'Receipt root missing')
        paths = sorted(set(root.rglob('*.receipt.json')) | set(root.rglob('*.invocation-error.json')))
        for path in paths:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            require(len(seen) <= 2000, 'Receipt count ceiling')
            doc = read(path)
            name = path.relative_to(root).as_posix()
            require(re.fullmatch(r'[A-Za-z0-9_./-]+', name), 'Unsafe receipt label')
            row = {'receipt_id': f'receipt-root-{i:02d}/' + name, 'receipt_sha256': sha(path),
                'status': ('completed' if doc.get('exit_code') == 0 else 'failed') if 'exit_code' in doc else doc.get('status', 'unavailable'),
                **{k: doc.get(k) for k in ('exit_code', 'started_utc', 'finished_utc', 'wall_seconds', 'child_peak_rss_mib')},
                'runner_sha256': doc.get('runner_sha256')}
            for key in ('wall_seconds', 'child_peak_rss_mib'):
                require(row[key] is None or type(row[key]) in (int, float) and math.isfinite(row[key]) and row[key] >= 0,
                        'Invalid receipt cost')
            rows.append(row)
    safe(rows)
    return rows


def display(value):
    if value is None:
        return 'unavailable'
    if type(value) is bool:
        return 'yes' if value else 'no'
    if isinstance(value, float):
        return f'{value:.3f}'
    return str(value).replace('|', '\\|').replace('\n', ' ')


def interval_text(row):
    intervals = row['score']['candidate_intervals']
    if intervals is None:
        return 'unavailable'
    if not intervals:
        return '0; none'
    return f'{len(intervals)}; ' + '; '.join(f"[{i['split_interval'][0]}, {i['split_interval'][1]}] → {e}"
        for i, e in zip(intervals, row['all_candidate_interval_errors_records'], strict=True))


def operation_text(value):
    return (f"{display(value['status'])}; exit {display(value['exit_code'])}; {display(value['wall_seconds'])} s; "
            f"{display(value['child_peak_rss_mib'])} MiB; {value['artifact_bytes']:,} bytes")


def bracket_text(value):
    return 'unavailable' if value is None else f"{display(value['left_utc'])} → {display(value['right_utc'])} ({display(value['elapsed_seconds'])} s)"


def markdown(summary, groups, availability, aggregates, ledger, cost, context=None):
    p = len(groups)
    lines = ['# Pilot 6: bounded shared-anchor replication', '',
        f"{p} new account-disjoint pairs supplied {4*p} planned main histories and {4*p} replay slots. "
        f"The target was 10 pairs; the pre-score shortfall is {10-p}. "
        f"{summary['main_executed_primary_histories']} main histories executed and {summary['main_unavailable_primary_histories']} are unavailable. "
        f"{summary['pairs_with_four_verified_replays']} pairs have all four canonical replays verified.", '',
        'Each pair is one replication unit. Its four histories share the same earlier sample; replays add no new units. '
        'Source accounts are identity proxies, and distinct accounts need not represent distinct people. '
        'Pilot 5 is excluded from new-pair counts. These are descriptive results, with no population accuracy, verified-authorship, or real-takeover claim.', '',
        'The frozen primary is AHAS 1.0.4 pooled-comment surface/function-word chronology, 1,000-word/eight-record windows, '
        'minimum segment length three, and the primary log(N) penalty. The constructed junction is never snapped to the grid; tolerance is inclusive at ten records. '
        'Ten records has no fixed calendar-time width; UTC brackets describe the actual spacing.', '',
        '## Complete result files', '',
        '[cases.json](cases.json) and [summary.json](summary.json) are byte-identical copies of the independently checked safe global outputs. '
        '[pair-availability.json](pair-availability.json) retains every provisional pair, including unscored failures and eligible pairs outside the fixed cohort. '
        '[condition-summary.json](condition-summary.json), [pair-ledgers.json](pair-ledgers.json), and [operating-costs.json](operating-costs.json) provide derived counts and costs. '
        'Input and output hashes are in [REPORT_MANIFEST.json](REPORT_MANIFEST.json).', '',
        '## Per-condition denominators', '',
        'Candidate, zero-candidate, and unavailable categories retain every planned slot. Localization fractions below use executed histories; '
        'the planned and unavailable denominators remain visible. For controls, localization means descriptive construction-junction alignment, not positive switch truth.', '',
        '| Condition | Planned / executed / unavailable | Candidate / executed zero | Native no variation | Within 10 / executed | Exact / executed | Grid attainable / known |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for a in aggregates:
        w, e, g = a['within_ten_records'], a['exact_interval_containment'], a['metadata_grid_attainable_within_ten']
        lines.append(f"| {LABELS[a['condition']]} | {a['planned_histories']} / {a['executed_histories']} / {a['unavailable_histories']} | "
            f"{a['candidate_present_histories']} / {a['executed_zero_candidate_histories']} | {a['executed_no_measurable_variation_histories']} | "
            f"{w['numerator']} / {w['denominator_executed']} | {e['numerator']} / {e['denominator_executed']} | {g['numerator']} / {g['denominator_with_grid']} |")
    if context:
        feasibility, audit, cohort = (context[k] for k in ('source_feasibility', 'audit', 'selected_cohort'))
        exposure = cohort['prior_preparation_exposure']
        lines += ['', '## Preparation, protection and source coverage', '',
            f"The fixed search evaluated {feasibility['pair_cut_count']} community-pair/calendar cuts and found "
            f"{feasibility['unique_valid_unordered_edges']} valid unordered account-pair edges. The maximum matching contained "
            f"{feasibility['global_maximum_matching_pairs']} pairs; its fixed first {feasibility['provisional_pairs']} entered auditing. "
            f"{context['unavailable_provisional_pairs']} provisional pairs were unavailable after auditing and the unchanged final gates.", '',
            f"The combined pool contained {audit['candidate_records']:,} original comments. Auditing purged "
            f"{audit['purged_candidate_records']:,}, leaving {audit['surviving_candidate_records']:,}. "
            f"The broad candidate-pair count was {audit['independent_candidate_pairs']:,}, within the fixed {audit['max_candidate_pairs']:,} ceiling. "
            f"{audit['content_unobservable_record_count']} historical records remained unobservable; unknown content relationships are not treated as absent.", '',
            f"The selected cohort contains {cohort['source_accounts']} source accounts, {cohort['unique_original_comments']:,} distinct original comments "
            f"and {cohort['unique_retained_words']:,} retained words. {exposure['prior_preparation_in_either_study_accounts']} selected accounts had prior "
            f"unscored preparation/audit exposure ({exposure['prior_pilot3_preparation_and_audit_accounts']} from Pilot 3 and "
            f"{exposure['prior_pilot4_preparation_and_audit_accounts']} from Pilot 4); {exposure['prior_metadata_without_known_preparation_accounts']} appeared "
            f"only in prior eligibility metadata. Newly supplemented accounts in the final cohort: {exposure['first_eligibility_metadata_from_pilot6_supplement_accounts']}.", '',
            '| Registered community pair | Selected replication pairs |', '|---|---:|']
        community_pairs = ('AskAcademia / GradSchool', 'AskPhysics / Physics', 'math / learnmath', 'linux / linuxquestions', 'programming / learnprogramming')
        lines += [f"| {label} | {cohort['stratum_pair_counts'].get(f'stratum-{i:02d}', 0)} |" for i, label in enumerate(community_pairs, 1)]
        lines += ['', 'All preparation failure reasons and exposure counts are preserved in [study-context.json](study-context.json). '
            'Reason counts are nonexclusive; zero selected pairs remain visible. English remains a corpus-level assumption.', '']
    lines += ['', 'Successful native `no_measurable_variation` is executed zero-candidate behavior. Unavailable results retain null measurements; '
        'a missing nearest distance is not zero. Metadata grid/time resolution is separate from observed localization. '
        'The frozen `matched_candidate_count` is a one-truth 0/1 match indicator, not a count of every interval within tolerance.', '',
        '## All provisional pairs', '', '| Pair | Stratum | Direction | Cut | Selection status | Reasons |', '|---|---|---|---|---|---|']
    by_id = {r['pair_id']: r for r in availability}
    for a in availability:
        lines.append(f"| {a['pair_id']} | {a['stratum_id']} | {display(a['community_x'])} → {display(a['community_y'])} | "
            f"{display(a['cut'])} | {display(a['selection_status'])} | {display(', '.join(a['reason_codes']) or 'none')} |")
    for pid, rows in groups.items():
        a = by_id[pid]
        lines += ['', f'## {pid}', '', f"{a['stratum_id']}: {a['community_x']} → {a['community_y']}; fixed cut {a['cut']}. "
            'All four histories use the identical earlier anchor.', '',
            '| Condition | Executed / native status | Count; every split interval → error (records) | Nearest / best grid / excess (records) | Within 10 / exact | Qualified windows |',
            '|---|---|---|---|---|---:|']
        for row in rows:
            s, loc = row['score'], location(row)
            lines.append(f"| {LABELS[row['condition']]} | {display(s['executed'])} / {display(row['native_change_status'])} | {interval_text(row)} | "
                f"{display(loc['nearest_interval_error_records'])} / {display(s['grid_resolution']['best_interval_error_records'])} / "
                f"{display(loc['excess_error_over_best_grid_records'])} | {display(loc['matched_within_tolerance'])} / "
                f"{display(loc['exact_interval_containment'])} | {s['grid_resolution']['qualified_window_count']} |")
        lines += ['', 'Intervals are inclusive split positions, after conversion from production bounding records `[a,b]` to `[a+1,b]`. '
            'Errors use the unsnapped junction. Continuity rows report control-junction alignment.', '',
            '| Condition | Main operation: status; exit; wall; peak RSS; bytes | Replay operation: status; exit; wall; peak RSS; bytes | Canonical replay identical |',
            '|---|---|---|---|']
        for row in rows:
            lines.append(f"| {LABELS[row['condition']]} | {operation_text(row['main_operation'])} | {operation_text(row['replay_operation'])} | "
                         f"{display(row['replay_verification']['all_files_byte_identical'])} |")
        lines.append('')
        for row in rows:
            s, grid, temporal = row['score'], row['score']['grid_resolution'], row['score']['temporal_resolution']
            modules = row['full_pipeline_statuses']
            statuses = '; '.join(f"{name}: {v['status']} ({', '.join(v['reason_codes']) or 'no reasons'})" for name, v in sorted(modules.items())) if modules is not None else 'unavailable'
            lines += [f"**{LABELS[row['condition']]}:** {row['record_count']} records / {row['retained_words']} retained words; "
                f"normalized status {display(s['status'])}; reasons {display(', '.join(s['reason_codes']) or 'none')}; "
                f"window verification {display(row['primary_window_check'])}. Full module statuses: {display(statuses)}.", '',
                f"Junction k={grid['reference_split_k']}: {bracket_text(temporal['construction_junction'])}. "
                f"Nearest legal boundary: {bracket_text(grid['nearest_legal_boundary'])}; within-ten attainment {display(grid['attainable_within_tolerance'])}. "
                f"Supplied time span: {display(temporal['first_utc'])} → {display(temporal['last_utc'])}. "
                'Complete candidate UTC brackets and all legal boundaries remain in cases.json.', '']
    lines += ['## Operating cost and stopping', '',
        f"Elapsed time from first analyzer dispatch: {display(summary['global_wall_seconds_since_first_dispatch'])} seconds. "
        f"Global stop reason: {display(summary['stop_reason'])}. "
        f"Execution artifact bytes before final aggregate reports: {summary['artifact_bytes_before_final_reports']:,}.", '',
        f"Recorded main case wall-time sum: {display(cost['main']['sum_case_wall_seconds'])} seconds across "
        f"{cost['main']['recorded_case_wall_time_histories']} receipted histories. Replay case wall-time sum: "
        f"{display(cost['replay']['sum_case_wall_seconds'])} seconds across {cost['replay']['recorded_case_wall_time_histories']} receipted histories. "
        'These sums are separate from elapsed study duration because cases run in parallel. Peak RSS values are per-process maxima and are not summed.', '',
        'Every discovered study receipt, including failed and synthetic attempts, is listed below. Receipts can overlap or contain nested phases; '
        'their wall times must not be added to case times or interpreted as unique elapsed study duration. '
        'Resource thresholds trigger termination; retained oversized evidence remains recorded. '
        'Canonical replay excludes exactly ingest_receipt.json and run_receipt.json.', '',
        '| Receipt | Status / exit | Wall seconds | Peak child RSS MiB |', '|---|---|---:|---:|']
    lines += [f"| {r['receipt_id']} | {display(r['status'])} / {display(r['exit_code'])} | {display(r['wall_seconds'])} | {display(r['child_peak_rss_mib'])} |" for r in ledger]
    return ('\n'.join(lines) + '\n').encode()


def build(run, results_check, prepared_public, receipt_roots, out, *, study_context=None):
    run, results_check, prepared_public, out = map(Path, (run, results_check, prepared_public, out))
    require(not out.exists(), 'Refusing to overwrite an existing report')
    passed = read(results_check)
    require(passed['status'] == 'passed' and passed['analyzer_calls'] == 0, 'Independent result check must pass before reporting')
    require(passed['aggregate_cases_sha256'] == sha(run/'cases.json') and
            passed['aggregate_summary_sha256'] == sha(run/'summary.json'), 'Independently checked results changed')
    cases, summary = read(run/'cases.json'), read(run/'summary.json')
    require(passed['registration_sha256'] == summary['registration_sha256'], 'Independent registration binding differs')
    groups = validate_cases(cases, summary)
    require(passed['new_source_account_pairs'] == len(groups) and passed['planned_main_histories'] == len(cases), 'Checked cohort denominator differs')
    availability = read(prepared_public/'pair-availability.json')
    selection = read(prepared_public/'selection-summary.json')
    require(len(availability) == selection['provisional_pairs'] <= 20 and len({r['pair_id'] for r in availability}) == len(availability),
            'Every provisional pair must remain visible')
    require({r['pair_id'] for r in availability if r['selection_status'] == 'selected_for_replication'} == set(groups), 'Availability and scored cohort mismatch')
    require(selection['selected_new_pairs'] == len(groups) and selection['eligible_after_audit'] == sum(r['valid'] for r in availability), 'Post-audit denominator mismatch')
    require(all(r['selection_status'] == ('selected_for_replication' if r['pair_id'] in groups else
        'eligible_outside_fixed_ten_pair_cohort' if r['valid'] else 'unavailable_after_audit') for r in availability), 'Unscored availability status mismatch')
    safe(availability); safe(selection)
    context = read(study_context) if study_context else None
    if context:
        safe(context)
        require(context['reporting_only'] is True and context['analyzer_calls'] == 0, 'Context must contain reporting-only aggregates')
        require(context['selected_cohort']['pairs'] == len(groups) and context['selected_cohort']['source_accounts'] == 2 * len(groups)
                and context['unavailable_provisional_pairs'] == sum(not r['valid'] for r in availability), 'Context cohort denominators mismatch')
        require(context['selected_cohort']['stratum_pair_counts'] == dict(Counter(rows[0]['stratum_id'] for rows in groups.values())),
                'Context stratum coverage mismatch')
        require(context['audit']['candidate_records'] == context['audit']['purged_candidate_records'] + context['audit']['surviving_candidate_records'],
                'Audit context partition mismatch')
        study_root = Path(study_context).resolve().parent.parent
        for name, digest in context['input_sha256'].items():
            reference = (study_root/name).resolve()
            require(reference.is_relative_to(study_root) and sha(reference) == digest, 'Study context source binding changed')
    payloads = {name: (run/name).read_bytes() for name in ('cases.json', 'summary.json')}
    source_hashes = {name: sha(run/name) for name in payloads}
    if context:
        payloads['study-context.json'] = Path(study_context).read_bytes()
        source_hashes['study-context.json'] = sha(study_context)
    for name in ('pair-availability.json', 'selection-summary.json'):
        payloads[name] = (prepared_public/name).read_bytes(); source_hashes[name] = sha(prepared_public/name)
    pair_ledgers = []; unique_records = unique_words = 0
    for pid, rows in groups.items():
        saved = read(run/pid/'pair-summary.json')
        require(saved['pair_id'] == pid and saved['cases'] == rows, 'Pair ledger and checked global cases differ')
        ledger = {k: saved[k] for k in ('pair_id', 'status', 'phases', 'artifact_bytes', 'replay_all_passed')}
        safe(ledger); pair_ledgers.append(ledger)
        source_hashes[pid + '/pair-summary.json'] = sha(run/pid/'pair-summary.json')
        name = pid + '-samples.json'; sample = read(prepared_public/name)
        safe(sample); require(sample['pair_id'] == pid and len(sample['samples']) == 5, 'Missing five-sample metadata')
        require(sample['unique_comments'] == sum(s['records'] for s in sample['samples']) and
                sample['unique_retained_words'] == sum(s['retained_words'] for s in sample['samples']), 'Public five-sample totals mismatch')
        unique_records += sample['unique_comments']; unique_words += sample['unique_retained_words']
        payloads[name] = (prepared_public/name).read_bytes(); source_hashes[name] = sha(prepared_public/name)
    if context:
        require(context['selected_cohort']['unique_original_comments'] == unique_records and
                context['selected_cohort']['unique_retained_words'] == unique_words, 'Selected source-volume context mismatch')
    aggregates = condition_aggregates(cases)
    receipts = receipt_ledger(receipt_roots)
    costs = {'main': operation_totals(cases, 'main_operation'), 'replay': operation_totals(cases, 'replay_operation'),
        'elapsed_seconds_since_first_dispatch': summary['global_wall_seconds_since_first_dispatch'],
        'execution_artifact_bytes_before_final_reports': summary['artifact_bytes_before_final_reports'],
        'stop_reason': summary['stop_reason'], 'study_receipts': receipts, 'study_receipt_count': len(receipts),
        'failed_study_receipt_count': sum(r['status'] == 'failed' for r in receipts),
        'receipt_accounting_note': 'Receipt durations can overlap/nest and include synthetic/failed attempts. Do not add them to per-case sums or call them elapsed study duration.',
        'receipt_discovery_note': 'All *.receipt.json and *.invocation-error.json files beneath the supplied receipt roots, deduplicated by source path. The report-build invocation itself finishes after this snapshot.'}
    payloads.update({'condition-summary.json': encoded(aggregates), 'pair-ledgers.json': encoded(pair_ledgers),
                     'operating-costs.json': encoded(costs), 'REPORT.md': markdown(summary, groups, availability, aggregates, receipts, costs, context)})
    source_hashes['independent-results-check.json'] = sha(results_check)
    manifest = {'report_builder_sha256': sha(__file__), 'independent_results_check_sha256': sha(results_check),
        'registration_sha256': summary['registration_sha256'], 'source_artifact_sha256': source_hashes,
        'copied_json_byte_identical': ['cases.json', 'summary.json', 'pair-availability.json', 'selection-summary.json'] +
            [pid + '-samples.json' for pid in groups] + (['study-context.json'] if context else []),
        'derived_outputs': ['condition-summary.json', 'pair-ledgers.json', 'operating-costs.json', 'REPORT.md'],
        'outputs': {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for name, data in sorted(payloads.items())},
        'analyzer_calls': 0, 'source_prose_reads': 0, 'private_paths_or_identity_maps_published': False,
        'manifest_excludes_itself_to_avoid_circular_hash': True}
    payloads['REPORT_MANIFEST.json'] = encoded(manifest)
    require(sum(map(len, payloads.values())) <= MAX_OUTPUT_BYTES, 'Public report output ceiling')
    # Recheck the outcome bindings just before writing the new public artifact tree.
    require(sha(run/'cases.json') == passed['aggregate_cases_sha256'] and sha(run/'summary.json') == passed['aggregate_summary_sha256'],
            'Results changed during report construction')
    out.mkdir(parents=True, exist_ok=False)
    for name, data in payloads.items():
        with (out/name).open('xb') as stream:
            stream.write(data)
    require(sha(out/'cases.json') == passed['aggregate_cases_sha256'] and sha(out/'summary.json') == passed['aggregate_summary_sha256'],
            'Exact scientific copy verification failed')
    return {'status': 'reported', 'new_pairs': len(groups), 'main_case_rows': len(cases),
            'provisional_availability_rows': len(availability), 'study_receipts': len(receipts),
            'public_files': len(payloads), 'public_bytes': sum(map(len, payloads.values()))}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('run', 'results-check', 'prepared-public', 'out'):
        parser.add_argument('--' + key, required=True, type=Path)
    parser.add_argument('--receipt-root', required=True, type=Path, action='append')
    parser.add_argument('--study-context', type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.run, args.results_check, args.prepared_public, args.receipt_root, args.out, study_context=args.study_context), sort_keys=True))
