"""Synthetic saved-artifact adapter checks; no analyzer or source prose is used."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import csv
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from chronology_math import factorial_cases, reconstruct_windows
from run_full_chronology import CONFIG, FINGERPRINT, artifact_inventory, extract_primary, sha
from score_saved_chronology import checked_windows, replay_check, score


def put(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True) + '\n')


def metadata(count=80):
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    return [{'record_id': f'synthetic-record-{i}', 'retained_words': 125,
             'style_eligible': True, 'created_utc': (start + timedelta(days=i)).isoformat()}
            for i in range(count)]


def result_stub(*, boundary=True, native='ok'):
    return {'analysis': {'implementation_fingerprint': FINGERPRINT, 'config_sha256': CONFIG},
            'modules': {'style': {'status': 'ok', 'reason_codes': [], 'payload': {
                'streams': [
                    {'scope_type': 'community', 'kind': 'comment', 'subreddit': 'synthetic', 'stream_id': 'community'},
                    {'scope_type': 'pooled', 'kind': 'submission', 'subreddit': None, 'stream_id': 'submissions'},
                    {'scope_type': 'pooled', 'kind': 'comment', 'subreddit': None, 'stream_id': 'primary',
                     'window_ids': ['primary-window-'+str(i) for i in range(10)]},
                ],
                'changes': [
                    {'stream_id': 'community', 'status': 'ok', 'reason_codes': [],
                     'boundaries': [{'record_interval': [63, 64]}]},
                    {'stream_id': 'primary', 'status': native, 'reason_codes': [],
                     'boundaries': [{'record_interval': [39, 40]}] if boundary else []},
                ]}}, 'text': {'status': 'ok', 'reason_codes': [], 'payload': {}}}}


def put_windows(directory, records):
    with (directory/'windows.jsonl').open('w') as handle:
        for index, window in enumerate(reconstruct_windows(records)):
            saved = {**window, 'record_ids': [records[p]['record_id'] for p in window['record_positions']],
                     'stream_id': 'primary', 'window_id': 'primary-window-'+str(index)}
            del saved['record_positions']
            handle.write(json.dumps(saved) + '\n')


class SyntheticRun:
    def __init__(self, root):
        self.root = Path(root)
        self.prepared = self.root/'prepared'
        self.prepared.mkdir()
        self.run = self.root/'first'
        self.run.mkdir()
        self.index_path = self.prepared/'index.json'
        self.cases = []
        bound = []
        for descriptor in factorial_cases('synthetic-block'):
            case = {**descriptor, 'stratum_id': 'synthetic-stratum',
                    'truth_k': 40 if descriptor['source_switch'] else None,
                    'control_junction_k': None if descriptor['source_switch'] else 40}
            for field, content in [('input', {'records': []}), ('manifest', {'synthetic': True}),
                                   ('metadata', {'records': metadata()})]:
                path = self.prepared/(descriptor['case_id'] + '.' + field + '.json')
                put(path, content)
                case[field] = str(path)
                bound.append({'path': str(path), 'sha256': sha(path)})
            self.cases.append(case)
            analysis = self.run/case['case_id']/'analysis'
            analysis.mkdir(parents=True)
            put(analysis/'results.json', result_stub(boundary=case['source_switch']))
            put_windows(analysis, metadata())
            put(analysis/'ingest_receipt.json', {'operational': 'first-ingest'})
            put(analysis/'run_receipt.json', {'operational': 'first-run'})
            put(analysis/'other_receipt.json', {'canonical_despite_name': True})
        put(self.index_path, {'cases': self.cases, 'bound_files': bound})
        self.execution = {'cases': [], 'replay': False}
        for case in self.cases:
            receipt = {'case_id': case['case_id'], 'exit_code': 0, 'wall_seconds': 1,
                       'child_peak_rss_mib': 1, 'external_wall_limit_reached': False,
                       'artifacts': artifact_inventory(self.run/case['case_id']/'analysis')}
            put(self.run/case['case_id']/'receipt.json', receipt)
            self.execution['cases'].append({'case_id': case['case_id'], 'status': 'attempted', 'receipt': receipt})
        put(self.run/'execution.json', self.execution)
        put(self.run/'start-binding.json', {
            'case_ids': [case['case_id'] for case in self.cases], 'replay': False,
            'index_sha256': sha(self.index_path), 'registration_sha256': 'synthetic-registration',
            'runner_sha256': 'synthetic-runner'})

    def refresh(self, root, case_id, exit_code=None):
        execution = json.loads((root/'execution.json').read_bytes())
        attempt = next(row for row in execution['cases'] if row['case_id'] == case_id)
        receipt = attempt['receipt']
        if exit_code is not None:
            receipt['exit_code'] = exit_code
        receipt['artifacts'] = artifact_inventory(root/case_id/'analysis')
        put(root/case_id/'receipt.json', receipt)
        put(root/'execution.json', execution)

    def replay(self):
        target = self.root/'replay'
        shutil.copytree(self.run, target)
        execution = json.loads((target/'execution.json').read_bytes())
        execution['replay'] = True
        put(target/'execution.json', execution)
        binding = json.loads((target/'start-binding.json').read_bytes())
        binding['replay'] = True
        put(target/'start-binding.json', binding)
        for case in self.cases:
            analysis = target/case['case_id']/'analysis'
            put(analysis/'ingest_receipt.json', {'operational': 'different-relocated-ingest'})
            put(analysis/'run_receipt.json', {'operational': 'different-relocated-run'})
            self.refresh(target, case['case_id'])
        return target


class WindowReconciliation(unittest.TestCase):
    def test_private_original_memberships_counts_and_gaps(self):
        records = metadata(82)
        records[1]['style_eligible'] = False
        records[5]['style_eligible'] = False
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            put_windows(directory, records)
            expected, check = checked_windows(records, directory, 'primary', ['primary-window-'+str(i) for i in range(10)])
            self.assertEqual(check, 'all_primary_memberships_counts_positions_verified')
            self.assertEqual(expected[0]['record_positions'], [0, 2, 3, 4, 6, 7, 8, 9])
            self.assertEqual(expected[0]['record_count'], 8)
            self.assertEqual(expected[0]['word_count'], 1000)
            self.assertEqual(expected[0]['last_record_position'], 9)

    def test_same_endpoints_and_counts_do_not_hide_wrong_membership(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            records = metadata()
            put_windows(directory, records)
            rows = [json.loads(line) for line in (directory/'windows.jsonl').read_text().splitlines()]
            rows[0]['record_ids'][2] = rows[0]['record_ids'][3]
            (directory/'windows.jsonl').write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
            with self.assertRaisesRegex(ValueError, 'membership'):
                checked_windows(records, directory, 'primary', ['primary-window-'+str(i) for i in range(10)])

    def test_word_counts_and_extra_or_missing_windows_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            records = metadata()
            for mutation in ('words', 'missing', 'extra'):
                with self.subTest(mutation=mutation):
                    put_windows(directory, records)
                    rows = [json.loads(line) for line in (directory/'windows.jsonl').read_text().splitlines()]
                    if mutation == 'words':
                        rows[0]['word_count'] += 1
                    elif mutation == 'missing':
                        rows.pop()
                    else:
                        rows.append(rows[-1])
                    (directory/'windows.jsonl').write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
                    with self.assertRaises(ValueError):
                        checked_windows(records, directory, 'primary', ['primary-window-'+str(i) for i in range(10)])

    def test_exact_primary_ids_exclude_sensitivity_rows_with_same_stream_id(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            records = metadata(81)
            put_windows(directory, records)
            requested = ['primary-window-'+str(i) for i in range(11)]
            with (directory/'windows.jsonl').open('a') as handle:
                for target in (500, 2000):
                    handle.write(json.dumps({'window_id': f'sensitivity-{target}', 'stream_id': 'primary',
                        'qualified': True, 'first_record_position': 0, 'last_record_position': 15,
                        'record_count': 16, 'word_count': 2000, 'record_ids': ['irrelevant']})+'\n')
            expected, validation = checked_windows(records, directory, 'primary', requested)
            self.assertEqual(len(expected), 11)
            self.assertFalse(expected[-1]['qualified'])
            self.assertEqual(validation, 'all_primary_memberships_counts_positions_verified')
            for wrong in (None, requested[:-1], requested+[requested[0]], list(reversed(requested))):
                with self.subTest(requested=wrong), self.assertRaises(ValueError):
                    checked_windows(records, directory, 'primary', wrong)

    def test_metadata_duplicate_ids_rejected(self):
        records = metadata()
        records[1]['record_id'] = records[0]['record_id']
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(ValueError):
            checked_windows(records, temp, None)


class SavedExtraction(unittest.TestCase):
    def test_primary_scope_and_single_conversion(self):
        extracted = extract_primary(result_stub(), 0)
        self.assertEqual(extracted['candidate_intervals'], [[40, 40]])
        self.assertEqual(extracted['stream_id'], 'primary')
        self.assertEqual(extracted['native_change_status'], 'ok')

    def test_constant_and_pipeline_failure_native_status_preserved(self):
        constant = extract_primary(result_stub(boundary=False, native='no_measurable_variation'), 0)
        self.assertIn(constant['status'], {'ok', 'no_measurable_variation'})
        self.assertEqual(constant['native_change_status'], 'no_measurable_variation')
        self.assertEqual(constant['candidate_intervals'], [])
        failed = extract_primary(result_stub(), 4)
        self.assertEqual(failed['status'], 'resource_limit')
        self.assertIn('whole_pipeline_incomplete', failed['reason_codes'])

    def test_identity_mismatch_rejected(self):
        result = result_stub()
        result['analysis']['config_sha256'] = 'changed'
        with self.assertRaises(ValueError):
            extract_primary(result, 0)


class CompleteScoreIntegration(unittest.TestCase):
    def test_all_sixteen_cases_four_conditions_exact_summaries_and_csv_nulls(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = SyntheticRun(temp)
            out = Path(temp)/'scores'
            score(fixture.index_path, fixture.run, out)
            rows = json.loads((out/'cases.json').read_bytes())
            summary = json.loads((out/'summary.json').read_bytes())
            self.assertEqual(len(rows), 16)
            self.assertTrue(all(row['primary_window_check'] == 'all_primary_memberships_counts_positions_verified' for row in rows))
            self.assertEqual(summary['all_strata']['planned_cases'], 16)
            self.assertEqual(summary['all_strata']['planned_blocks'], 1)
            for condition in summary['all_strata']['conditions']:
                expected = condition['condition'].startswith('switch_')
                self.assertEqual(condition['executed_cases'], 4)
                self.assertEqual(condition['metrics']['candidate_occurrence']['complete_block_equal_mean'], int(expected))
            with (out/'cases.csv').open() as handle:
                csv_rows = list(csv.DictReader(handle))
            self.assertEqual(csv_rows[0]['switch_matched_within_10'], '')
            self.assertEqual(csv_rows[0]['control_junction_matched_within_10'], 'False')
            self.assertNotIn('synthetic-record-', (out/'cases.json').read_text())

    def test_failed_partial_window_artifact_is_unavailable_not_an_observed_zero(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = SyntheticRun(temp)
            case_id = next(row['case_id'] for row in fixture.cases if row['source_switch'])
            (fixture.run/case_id/'analysis'/'windows.jsonl').write_text('{partial')
            fixture.refresh(fixture.run, case_id, exit_code=4)
            out = Path(temp)/'scores'
            score(fixture.index_path, fixture.run, out)
            rows = json.loads((out/'cases.json').read_bytes())
            failed = next(row for row in rows if row['case_id'] == case_id)
            self.assertFalse(failed['score']['executed'])
            self.assertIsNone(failed['score']['candidate_count'])
            self.assertIsNone(failed['score']['switch_localization']['matched_within_tolerance'])
            self.assertEqual(failed['primary_window_check'], 'unavailable_partial_windows_unverified')
            summary = json.loads((out/'summary.json').read_bytes())['all_strata']
            condition = next(row for row in summary['conditions'] if row['condition'] == failed['condition'])
            self.assertEqual(condition['executed_cases'], 3)
            self.assertEqual(condition['metrics']['candidate_occurrence']['complete_blocks'], 0)

    def test_executed_case_requires_saved_primary_windows(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = SyntheticRun(temp)
            case_id = fixture.cases[0]['case_id']
            (fixture.run/case_id/'analysis'/'windows.jsonl').unlink()
            fixture.refresh(fixture.run, case_id)
            with self.assertRaisesRegex(ValueError, 'saved-window'):
                score(fixture.index_path, fixture.run, Path(temp)/'scores')

    def test_constant_native_status_is_observed_zero_and_cannot_have_candidates(self):
        for boundary in (False, True):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as temp:
                fixture = SyntheticRun(temp)
                case_id = fixture.cases[0]['case_id']
                put(fixture.run/case_id/'analysis'/'results.json',
                    result_stub(boundary=boundary, native='no_measurable_variation'))
                fixture.refresh(fixture.run, case_id)
                out = Path(temp)/'scores'
                if boundary:
                    with self.assertRaises(ValueError):
                        score(fixture.index_path, fixture.run, out)
                else:
                    score(fixture.index_path, fixture.run, out)
                    row = json.loads((out/'cases.json').read_bytes())[0]
                    self.assertEqual(row['native_change_status'], 'no_measurable_variation')
                    self.assertTrue(row['score']['executed'])
                    self.assertEqual(row['score']['candidate_count'], 0)

    def test_duplicate_execution_index_binding_and_unbound_metadata_rejected(self):
        for mutation in ('duplicate', 'index', 'unbound_metadata'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                fixture = SyntheticRun(temp)
                if mutation == 'duplicate':
                    execution = json.loads((fixture.run/'execution.json').read_bytes())
                    execution['cases'].append(execution['cases'][0])
                    put(fixture.run/'execution.json', execution)
                elif mutation == 'index':
                    binding = json.loads((fixture.run/'start-binding.json').read_bytes())
                    binding['index_sha256'] = 'wrong'
                    put(fixture.run/'start-binding.json', binding)
                else:
                    index = json.loads(fixture.index_path.read_bytes())
                    index['bound_files'] = [row for row in index['bound_files'] if row['path'] != fixture.cases[0]['metadata']]
                    put(fixture.index_path, index)
                with self.assertRaises(ValueError):
                    score(fixture.index_path, fixture.run, Path(temp)/'scores')

    def test_saved_results_changed_after_receipt_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = SyntheticRun(temp)
            put(fixture.run/fixture.cases[0]['case_id']/'analysis'/'results.json', result_stub(boundary=True))
            with self.assertRaisesRegex(ValueError, 'artifact inventory'):
                score(fixture.index_path, fixture.run, Path(temp)/'scores')


class ReplayComparison(unittest.TestCase):
    def test_only_two_operational_receipts_are_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = SyntheticRun(temp)
            replay = fixture.replay()
            out = Path(temp)/'check.json'
            replay_check(fixture.run, replay, out)
            report = json.loads(out.read_bytes())
            self.assertTrue(report['all_passed'])
            self.assertEqual(len(report['cases']), 16)
            self.assertTrue(all(row['canonical_file_count'] == 3 for row in report['cases']))
            self.assertEqual(report['excluded_operational_files'], ['ingest_receipt.json', 'run_receipt.json'])

    def test_other_receipt_named_file_remains_canonical(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = SyntheticRun(temp)
            replay = fixture.replay()
            case_id = fixture.cases[0]['case_id']
            put(replay/case_id/'analysis'/'other_receipt.json', {'changed': True})
            fixture.refresh(replay, case_id)
            out = Path(temp)/'check.json'
            replay_check(fixture.run, replay, out)
            report = json.loads(out.read_bytes())
            self.assertFalse(report['all_passed'])
            self.assertEqual(report['cases'][0]['differing_files'], ['other_receipt.json'])

    def test_missing_canonical_file_fails_comparison(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = SyntheticRun(temp)
            replay = fixture.replay()
            case_id = fixture.cases[0]['case_id']
            (replay/case_id/'analysis'/'windows.jsonl').unlink()
            fixture.refresh(replay, case_id)
            out = Path(temp)/'check.json'
            replay_check(fixture.run, replay, out)
            report = json.loads(out.read_bytes())
            self.assertFalse(report['all_passed'])
            self.assertEqual(report['cases'][0]['differing_files'], ['windows.jsonl'])

    def test_empty_or_incomplete_replay_and_changed_binding_rejected(self):
        for mutation in ('empty', 'incomplete', 'registration'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temp:
                fixture = SyntheticRun(temp)
                replay = fixture.replay()
                execution = json.loads((replay/'execution.json').read_bytes())
                binding = json.loads((replay/'start-binding.json').read_bytes())
                if mutation == 'registration':
                    binding['registration_sha256'] = 'different'
                else:
                    execution['cases'] = [] if mutation == 'empty' else execution['cases'][:-1]
                    binding['case_ids'] = [row['case_id'] for row in execution['cases']]
                put(replay/'execution.json', execution)
                put(replay/'start-binding.json', binding)
                with self.assertRaises(ValueError):
                    replay_check(fixture.run, replay, Path(temp)/'check.json')


if __name__ == '__main__':
    unittest.main()
