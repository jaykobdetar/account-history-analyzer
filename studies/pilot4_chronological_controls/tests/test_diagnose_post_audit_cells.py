import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('post_audit_diagnostic', Path(__file__).parents[1] / 'scripts/diagnose_post_audit_cells.py')
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)


def rows(n, words=125, timestamp=0):
    return [{'record_id': f'r{i:04}', 'timestamp': timestamp, 'retained_words': words} for i in range(n)]


class DiagnosticTests(unittest.TestCase):
    def test_exact_whole_prefix(self):
        result = d.prefix_diagnosis(rows(50), 0, 'late')
        self.assertTrue(result['qualified'])
        self.assertEqual((result['prefix_records'], result['prefix_words']), (40, 5000))
        self.assertEqual(result['first_blocking_reasons'], [])

    def test_half_open_bands_and_word_filter(self):
        fixture = rows(40, timestamp=-180*d.DAY) + [{'record_id': 'excluded', 'timestamp': 0, 'retained_words': 500}]
        result = d.prefix_diagnosis(fixture, 0, 'early')
        self.assertTrue(result['qualified'])
        self.assertEqual(result['out_of_band_or_word_bounds_records'], 1)
        result = d.prefix_diagnosis(rows(40, timestamp=180*d.DAY), 0, 'late')
        self.assertEqual(result['in_band_eligible_records'], 0)

    def test_word_ceiling_before_count_minimum(self):
        result = d.prefix_diagnosis(rows(40, 500), 0, 'late')
        self.assertEqual(result['first_blocking_reasons'], ['prefix_word_ceiling'])
        self.assertEqual((result['prefix_records'], result['prefix_words']), (12, 6000))
        self.assertFalse(result['minimum_records_met_at_block'])
        self.assertEqual(result['necessary_volume_lower_bounds']['additional_comments_with_500_word_cap'], 0)

    def test_record_ceiling(self):
        result = d.prefix_diagnosis(rows(250, 20), 0, 'late')
        self.assertEqual(result['first_blocking_reasons'], ['prefix_record_ceiling'])
        self.assertEqual(result['prefix_records'], 201)

    def test_word_and_record_deficits(self):
        result = d.prefix_diagnosis(rows(39, 100), 0, 'late')
        self.assertEqual(result['first_blocking_reasons'], ['insufficient_retained_words', 'insufficient_records'])
        self.assertEqual(result['necessary_volume_lower_bounds']['additional_comments_with_500_word_cap'], 3)

    def test_inclusive_ratio_and_median_gates(self):
        cells = {}
        for account in ('a', 'b'):
            for role in 'XY':
                for period in ('early', 'late'):
                    cell = d.prefix_diagnosis(rows(40, timestamp=(-1 if period == 'early' else 0)), 0, period)
                    cells[f'{account}/{role}/{period}'] = cell
        cells['b/Y/early']['selected_prefix'].update(records=50, retained_words=5500, median_timestamp=d.fraction(-1-30*d.DAY))
        self.assertTrue(d.compare_cells(cells)['qualified'])
        cells['b/Y/early']['selected_prefix'].update(records=51, median_timestamp=d.fraction(-2-30*d.DAY))
        result = d.compare_cells(cells)
        self.assertEqual(result['failing_gates'], ['record_ratio_exceeds_5_over_4', 'early_median_span_exceeds_30_days'])
        self.assertEqual(result['gate_measurements']['period_median_spans']['early']['minimum_span_reduction_seconds'], d.fraction(1))

    def test_missing_cells_are_not_imputed(self):
        result = d.compare_cells({'account-01/X/early': d.prefix_diagnosis([], 0, 'early')})
        self.assertIsNone(result['gate_measurements'])
        self.assertEqual(result['missing_qualified_cells'], ['account-01/X/early'])


if __name__ == '__main__':
    unittest.main()
