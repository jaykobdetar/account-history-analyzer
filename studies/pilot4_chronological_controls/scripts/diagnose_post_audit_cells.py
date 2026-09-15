"""Post-hoc metadata-only explanation of fixed pilot4 gates; never selects inputs.

This diagnostic does not modify or rerun the registered study and does not import
any preparation, matching, preprocessing or analysis implementation. Public
labels identify opaque account roles only; original identifiers stay in memory.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
from itertools import combinations
import json
from pathlib import Path
import resource
import signal
import time

DAY = 86400
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
KEYS = ('X/early', 'X/late', 'Y/early', 'Y/late')


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def stamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.utcoffset() != timedelta(0) or parsed.microsecond:
        raise ValueError('non_integer_UTC_timestamp')
    return int((parsed - EPOCH).total_seconds())


def fraction(value):
    value = Fraction(value)
    return {'numerator': value.numerator, 'denominator': value.denominator}


def iso(value):
    return (EPOCH + timedelta(microseconds=int(value * 1000000))).isoformat().replace('+00:00', 'Z')


def prefix_diagnosis(rows, cut, period):
    """Explain the single fixed whole-record prefix, including its first failure."""
    if period not in ('early', 'late'):
        raise ValueError('unknown_period')
    lo, hi = (cut - 180 * DAY, cut) if period == 'early' else (cut, cut + 180 * DAY)
    usable = [r for r in rows if lo <= r['timestamp'] < hi and 20 <= r['retained_words'] <= 500]
    ordered = sorted(usable, key=lambda r: (abs(r['timestamp'] - cut), r['timestamp'], r['record_id']))
    result = {
        'surviving_records': len(rows), 'surviving_retained_words': sum(r['retained_words'] for r in rows),
        'in_band_eligible_records': len(ordered), 'in_band_eligible_words': sum(r['retained_words'] for r in ordered),
        'out_of_band_or_word_bounds_records': len(rows) - len(ordered),
        'qualified': False, 'first_blocking_reasons': [], 'prefix_records': 0, 'prefix_words': 0,
        'selected_prefix': None,
    }
    word_deficit = max(0, 5000 - result['in_band_eligible_words'])
    count_deficit = max(0, 40 - len(ordered))
    result['necessary_volume_lower_bounds'] = {
        'additional_eligible_words': word_deficit, 'additional_eligible_records': count_deficit,
        'additional_comments_with_500_word_cap': max(count_deficit, (word_deficit + 499) // 500),
        'sufficient_for_qualification': False,
    }
    words = 0
    for i, row in enumerate(ordered, 1):
        words += row['retained_words']
        result['prefix_records'], result['prefix_words'] = i, words
        if words > 5500 or i > 200:
            result['first_blocking_reasons'] = (["prefix_word_ceiling"] if words > 5500 else []) + (["prefix_record_ceiling"] if i > 200 else [])
            result['blocking_prefix_previous_records'] = i - 1
            result['blocking_prefix_previous_words'] = words - row['retained_words']
            result['minimum_records_met_at_block'] = i >= 40
            result['minimum_words_met_at_block'] = words >= 5000
            break
        if words >= 5000 and i >= 40:
            times = sorted(r['timestamp'] for r in ordered[:i])
            median = Fraction(times[(i - 1) // 2] + times[i // 2], 2)
            result['qualified'] = True
            result['selected_prefix'] = {
                'records': i, 'retained_words': words, 'median_timestamp': fraction(median),
                'median_utc': iso(median), 'first_utc': iso(times[0]), 'last_utc': iso(times[-1]),
            }
            break
    else:
        result['first_blocking_reasons'] = (["insufficient_retained_words"] if words < 5000 else []) + (["insufficient_records"] if len(ordered) < 40 else [])
    return result


def compare_cells(cells):
    """Return all fixed volume/date predicates, or explicit unavailable status."""
    missing = sorted(label for label, cell in cells.items() if not cell['qualified'])
    if missing:
        return {'qualified': False, 'missing_qualified_cells': missing,
                'gate_measurements': None, 'failing_gates': ['one_or_more_cells_unqualified']}
    selected = [cell['selected_prefix'] for cell in cells.values()]
    words = [r['retained_words'] for r in selected]
    counts = [r['records'] for r in selected]
    wr, cr = Fraction(max(words), min(words)), Fraction(max(counts), min(counts))
    failures = []
    if wr > Fraction(11, 10):
        failures.append('word_ratio_exceeds_11_over_10')
    if cr > Fraction(5, 4):
        failures.append('record_ratio_exceeds_5_over_4')
    spans = {}
    for period in ('early', 'late'):
        medians = [Fraction(d['selected_prefix']['median_timestamp']['numerator'], d['selected_prefix']['median_timestamp']['denominator'])
                   for label, d in cells.items() if label.endswith('/' + period)]
        span = max(medians) - min(medians)
        spans[period] = {'span_seconds': fraction(span), 'span_days': fraction(span / DAY),
                         'minimum_span_reduction_seconds': fraction(max(Fraction(), span - 30 * DAY)),
                         'passes_30_day_gate': span <= 30 * DAY}
        if span > 30 * DAY:
            failures.append(period + '_median_span_exceeds_30_days')
    return {
        'qualified': not failures, 'missing_qualified_cells': [], 'failing_gates': failures,
        'gate_measurements': {
            'word_ratio': fraction(wr), 'record_ratio': fraction(cr),
            'minimum_cell_words': min(words), 'maximum_cell_words': max(words),
            'minimum_cell_records': min(counts), 'maximum_cell_records': max(counts),
            'required_minimum_records_if_largest_count_unchanged': (max(counts) * 4 + 4) // 5,
            'maximum_records_allowed_if_smallest_count_unchanged': min(counts) * 5 // 4,
            'period_median_spans': spans,
        },
    }


def diagnose(plan, selection, audit):
    metadata = selection['selected_metadata']
    survivors, purged = set(audit['surviving_candidate_ids']), set(audit['purge_record_ids'])
    if survivors & purged or survivors | purged != set(metadata):
        raise ValueError('audit_partition_does_not_match_selected_metadata')
    if len(survivors) != len(audit['surviving_candidate_ids']) or len(purged) != len(audit['purge_record_ids']):
        raise ValueError('duplicate_audit_partition_entry')
    all_cells, strata = [], []
    for spec in plan['strata']:
        accounts = sorted(spec['accounts'], key=lambda name: hashlib.sha256(('pilot4-feasibility-identity-order-v1\0' + name.casefold()).encode()).hexdigest())
        groups, account_reports = {}, []
        for ordinal, account in enumerate(accounts, 1):
            label = 'account-' + str(ordinal).zfill(2)
            cells = {}
            for role, community in zip('XY', spec['communities']):
                for period in ('early', 'late'):
                    cell_key = role + '/' + period
                    members = {rid: row for rid, row in metadata.items()
                               if (row['stratum_id'], row['account_key'], row['community'], row['period']) == (spec['stratum_id'], account, community, period)}
                    rows = [{'record_id': rid, 'timestamp': stamp(row['created_utc']), 'retained_words': row['retained_words']}
                            for rid, row in members.items() if rid in survivors]
                    cell = prefix_diagnosis(rows, stamp(spec['cut']), period)
                    cell.update({'stratum_id': spec['stratum_id'], 'account_role': label,
                                 'cell': cell_key, 'pool_records': len(members),
                                 'pool_retained_words': sum(row['retained_words'] for row in members.values()),
                                 'purged_records': len(set(members) & purged),
                                 'purged_retained_words': sum(row['retained_words'] for rid, row in members.items() if rid in purged),
                                 'purge_reasons': dict(sorted(Counter(reason for rid in set(members) & purged for reason in audit['purge_reasons'][rid]).items()))})
                    cells[label + '/' + cell_key] = cell
                    all_cells.append(cell)
            groups[label] = cells
            account_reports.append({'account_role': label, **compare_cells(cells)})
        pairs = [{'account_roles': [a, b], **compare_cells({**groups[a], **groups[b]})}
                 for a, b in combinations(groups, 2)]
        strata.append({'stratum_id': spec['stratum_id'], 'communities': spec['communities'], 'cut': spec['cut'],
                       'planned_block_cap': spec['block_cap'], 'accounts': account_reports, 'pairs': pairs,
                       'qualified_cells': sum(c['qualified'] for cells in groups.values() for c in cells.values()),
                       'internally_qualified_accounts': sum(a['qualified'] for a in account_reports),
                       'compatible_pairs': sum(p['qualified'] for p in pairs)})
    if sum(c['pool_records'] for c in all_cells) != len(metadata):
        raise ValueError('metadata_records_outside_fixed_plan_cells')
    return {
        'status': 'diagnosed', 'phase': 'post_hoc_fixed_gate_failure_explanation',
        'new_selection_performed': False, 'source_archive_reads': 0, 'preprocessor_calls': 0,
        'style_scores_computed': 0, 'private_identifiers_published': False,
        'opaque_role_definition': 'Within each stratum, account-01 onward follows ascending SHA256(pilot4-feasibility-identity-order-v1 + NUL + canonical account). No identity map or hashes are published.',
        'candidate_accounts': sum(len(s['accounts']) for s in plan['strata']), 'cells_examined': len(all_cells),
        'qualified_cells': sum(c['qualified'] for c in all_cells), 'failed_cells': sum(not c['qualified'] for c in all_cells),
        'failure_reason_counts': dict(sorted(Counter(r for c in all_cells for r in c['first_blocking_reasons']).items())),
        'pool_records': len(metadata), 'purged_records': len(purged), 'surviving_records': len(survivors),
        'cells': all_cells, 'strata': strata,
        'interpretation': [
            'The unchanged registered prepared-input checker separately verifies original source fidelity, upstream metadata, exclusions, symmetric audit purges and the empty exact matching result.',
            'Failure explanations inspect only the fixed candidate-pool metadata after the recorded audit. No outside-pool refill, alternative calendar cut or replacement account is attempted.',
            'Each volume lower bound is necessary only. A future independently registered candidate pool would still need audit-clean comments of 20 to 500 retained words inside the same 180-day half-open band, whose nearest-cut whole prefix reaches at least 5000 words and 40 comments without exceeding 5500 words or 200 comments.',
            'An account needs four qualified cells; a pair needs eight, at most 11/10 word ratio and 5/4 comment-count ratio across all eight, plus median date span at most 30 days across all four cells within each period.',
            'If a prefix hits a ceiling, having sufficient total words or comments does not establish a valid prefix. The required future comment lengths and timestamps cannot be inferred as a unique minimum addition from aggregate totals.',
            'Pair date and volume measurements are null when any required cell is unqualified. Missing cells are never imputed as zero.',
            'Zero prepared blocks means the chronological study could not run; it is not an analyzer score, zero candidates or evidence for continuity.',
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    for name in ('plan', 'selection', 'preparation', 'audit', 'prepared-check', 'out'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    start = time.monotonic()
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (100 * 1024**2, 100 * 1024**2))
    signal.alarm(300)
    paths = {name: getattr(args, name.replace('-', '_')) for name in ('plan', 'selection', 'preparation', 'audit', 'prepared-check')}
    binding = {'phase': 'post_hoc_metadata_diagnostic_before_execution', 'script_sha256': sha(__file__),
               'input_sha256': {key: sha(path) for key, path in paths.items()},
               'limits': {'wall_seconds': 300, 'address_space_gib': 4, 'output_mib': 100, 'preprocessor_calls': 0}}
    out = Path(args.out)
    with out.with_suffix('.start-binding.json').open('x') as handle:
        json.dump(binding, handle, sort_keys=True, indent=2); handle.write('\n')
    preparation, check = read(args.preparation), read(args.prepared_check)
    if preparation['selection_sha256'] != sha(args.selection) or preparation['plan_sha256'] != sha(args.plan):
        raise ValueError('preparation_metadata_hash_binding')
    if check['status'] != 'passed' or check['selected_blocks'] or check['prepared_cases']:
        raise ValueError('requires_verified_empty_prepared_study')
    result = diagnose(read(args.plan), read(args.selection), read(args.audit))
    if result['pool_records'] != check['pool_records_checked'] or result['surviving_records'] != check['pool_survivors']:
        raise ValueError('independent_check_counts')
    for observed, verified in zip(result['strata'], check['strata']):
        if (observed['stratum_id'], observed['internally_qualified_accounts'], observed['compatible_pairs']) != (verified['stratum_id'], verified['post_audit_qualified_accounts'], verified['compatible_edges']):
            raise ValueError('independent_check_stratum_gate_counts')
    result.update({'binding': binding, 'wall_seconds': time.monotonic() - start,
                   'peak_rss_mib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024})
    with out.open('x') as handle:
        json.dump(result, handle, sort_keys=True, indent=2, allow_nan=False); handle.write('\n')
    print(json.dumps({key: result[key] for key in ('status', 'cells_examined', 'qualified_cells', 'failed_cells', 'failure_reason_counts', 'preprocessor_calls', 'style_scores_computed', 'wall_seconds', 'peak_rss_mib')}))


if __name__ == '__main__':
    main()
