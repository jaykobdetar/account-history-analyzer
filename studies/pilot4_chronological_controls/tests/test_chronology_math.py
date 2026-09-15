"""Synthetic checks only; no account writing or analyzer execution is used."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from chronology_math import (  # noqa: E402
    CONDITIONS, TOLERANCE_RECORDS, aggregate_cases, factorial_cases,
    interval_error, legal_grid, reconstruct_windows,
    record_boundary_to_split_interval, score_case,
)


def windows(count=8, span=10, occupied=None):
    occupied = span if occupied is None else occupied
    return [{"qualified": True, "first_record_position": i * span,
             "last_record_position": i * span + occupied - 1,
             "record_count": occupied, "word_count": 1000} for i in range(count)]


def timestamps(count):
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    return [(start + timedelta(days=i)).isoformat().replace("+00:00", "Z") for i in range(count)]


def score(*, candidates=(), status="ok", truth=40, control=None, win=None, times=None, reasons=()):
    win = windows() if win is None else win
    n = max(w["last_record_position"] for w in win) + 1 if win else 80
    return score_case(candidate_intervals=list(candidates) if candidates is not None else None,
                      status=status, reason_codes=list(reasons), truth_k=truth,
                      control_junction_k=control, windows=win,
                      record_timestamps=timestamps(n) if times is None else times)


class CoordinatesAndGrid(unittest.TestCase):
    def test_record_boundary_conversion_not_eligible_rank_or_double_shift(self):
        self.assertEqual(record_boundary_to_split_interval([27, 30]), [28, 30])
        self.assertEqual(record_boundary_to_split_interval([0, 1]), [1, 1])
        self.assertEqual(interval_error([28, 30], 28), 0)
        self.assertEqual(interval_error([28, 30], 30), 0)
        self.assertEqual(interval_error([28, 30], 27), 1)

    def test_exact_inclusive_tolerance_both_sides(self):
        self.assertEqual(TOLERANCE_RECORDS, 10)
        for k, error, matched in [(19, 11, False), (20, 10, True),
                                  (30, 0, True), (40, 10, True), (41, 11, False)]:
            with self.subTest(k=k):
                result = score(candidates=[[30, 30]], truth=k)["switch_localization"]
                self.assertEqual(result["nearest_interval_error_records"], error)
                self.assertEqual(result["matched_within_tolerance"], matched)
                self.assertEqual(result["exact_interval_containment"], error == 0)

    def test_invalid_coordinate_types_and_reversed_intervals(self):
        for value in ([False, 2], [2, 2], [4, 3], [-1, 3], [0]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                record_boundary_to_split_interval(value)
        for value in ([True, 3], [0, 3], [3, 2], [1, 2, 3]):
            with self.subTest(value=value), self.assertRaises(ValueError):
                interval_error(value, 2)
        with self.assertRaises(ValueError):
            interval_error([1, 3], True)

    def test_seven_is_unavailable_eight_has_three_legal_boundaries(self):
        self.assertEqual(legal_grid(windows(7)), [])
        self.assertEqual(legal_grid(windows()), [
            {"window_index": 3, "split_interval": [30, 30]},
            {"window_index": 4, "split_interval": [40, 40]},
            {"window_index": 5, "split_interval": [50, 50]},
        ])
        result = score(status="insufficient_windows", candidates=None, win=windows(7))
        self.assertFalse(result["executed"])
        self.assertIsNone(result["grid_resolution"]["attainable_within_tolerance"])
        with self.assertRaises(ValueError):
            score(win=windows(7))

    def test_original_ordinal_gaps_and_remainder_do_not_compress_grid(self):
        win = windows(8, occupied=8)
        win.append({"qualified": False, "first_record_position": 80, "last_record_position": 82})
        self.assertEqual([row["split_interval"] for row in legal_grid(win)], [[28, 30], [38, 40], [48, 50]])
        result = score(candidates=[[38, 40]], truth=39, win=win)
        interval = result["candidate_intervals"][0]
        self.assertEqual(interval["possible_split_position_count"], 3)
        self.assertEqual(interval["record_gap_positions"], 2)
        self.assertEqual((interval["left_record_position"], interval["right_record_position"]), (37, 40))
        self.assertEqual(interval["elapsed_seconds"], 3 * 86400)

    def test_grid_unattainable_remains_tolerance_failure_not_corrected_success(self):
        result = score(candidates=[[120, 120]], truth=100, win=windows(8, span=40))
        grid = result["grid_resolution"]
        self.assertEqual(grid["best_interval_error_records"], 20)
        self.assertFalse(grid["attainable_within_tolerance"])
        loc = result["switch_localization"]
        self.assertFalse(loc["matched_within_tolerance"])
        self.assertEqual(loc["nearest_interval_error_records"], 20)
        self.assertEqual(loc["excess_error_over_best_grid_records"], 0)

    def test_grid_better_than_chosen_candidate_is_reported_separately(self):
        result = score(candidates=[[120, 120]], truth=160, win=windows(8, span=40))
        self.assertTrue(result["grid_resolution"]["attainable_within_tolerance"])
        self.assertFalse(result["switch_localization"]["matched_within_tolerance"])
        self.assertEqual(result["switch_localization"]["excess_error_over_best_grid_records"], 40)

    def test_overlapping_windows_and_candidate_outside_legal_grid_rejected(self):
        bad = windows()
        bad[4]["first_record_position"] = 39
        with self.assertRaises(ValueError):
            legal_grid(bad)
        with self.assertRaises(ValueError):
            score(candidates=[[39, 40]])
        with self.assertRaises(ValueError):
            score(candidates=[[30, 30], [40, 40]])


class IndependentReconstruction(unittest.TestCase):
    def test_closes_only_after_word_and_record_guards_and_keeps_remainder(self):
        rows = [{"style_eligible": True, "retained_words": 120} for _ in range(10)]
        got = reconstruct_windows(rows)
        self.assertEqual([(w["word_count"], w["record_count"], w["qualified"]) for w in got],
                         [(1080, 9, True), (120, 1, False)])
        rows = [{"style_eligible": True, "retained_words": 2000}] + [
            {"style_eligible": True, "retained_words": 20} for _ in range(7)]
        self.assertEqual(reconstruct_windows(rows)[0]["record_count"], 8)

    def test_filters_body_metadata_preserves_ordinals_ignores_title_words(self):
        rows = [{"kind": "comment", "usable": True, "language": "en",
                 "created_utc": "2020-01-01T00:00:00Z", "retained_words": 125,
                 "title": {"retained_words": 9000}} for _ in range(13)]
        rows[1]["usable"] = False
        rows[3]["language"] = "und"
        rows[5]["created_utc"] = None
        rows[7]["retained_words"] = 19
        rows[9]["kind"] = "submission"
        got = reconstruct_windows(rows)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["record_positions"], [0, 2, 4, 6, 8, 10, 11, 12])
        self.assertEqual(got[0]["word_count"], 1000)
        self.assertTrue(got[0]["qualified"])

    def test_eligibility_projection_requires_boolean_and_frozen_minimum_words(self):
        for row in ({"style_eligible": 1, "retained_words": 125},
                    {"style_eligible": True, "retained_words": 19},
                    {"style_eligible": True, "retained_words": True}):
            with self.subTest(row=row), self.assertRaises(ValueError):
                reconstruct_windows([row])


class PerCaseOutcomes(unittest.TestCase):
    def test_adequate_no_candidate_is_observed_zero_with_null_error(self):
        result = score()
        self.assertTrue(result["executed"])
        self.assertFalse(result["candidate_occurrence"])
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["candidate_intervals"], [])
        self.assertFalse(result["switch_localization"]["matched_within_tolerance"])
        self.assertFalse(result["switch_localization"]["exact_interval_containment"])
        self.assertIsNone(result["switch_localization"]["nearest_interval_error_records"])
        self.assertTrue(result["grid_resolution"]["attainable_within_tolerance"])

    def test_constant_is_executed_zero_and_resource_failure_suppresses_partial_candidates(self):
        constant = score(status="no_measurable_variation")
        self.assertTrue(constant["executed"])
        self.assertEqual(constant["candidate_count"], 0)
        failed = score(status="resource_limit", candidates=[[40, 40]], reasons=["whole_pipeline_incomplete"])
        self.assertFalse(failed["executed"])
        for key in ("candidate_count", "candidate_occurrence", "candidate_intervals"):
            self.assertIsNone(failed[key])
        for key in ("matched_within_tolerance", "exact_interval_containment",
                    "nearest_interval_error_records", "unmatched_candidate_count"):
            self.assertIsNone(failed["switch_localization"][key])
        self.assertEqual(failed["reason_codes"], ["whole_pipeline_incomplete"])
        self.assertTrue(failed["grid_resolution"]["attainable_within_tolerance"])
        with self.assertRaises(ValueError):
            score(status="no_measurable_variation", candidates=[[40, 40]])

    def test_multiple_candidates_only_one_can_match_single_truth(self):
        result = score(candidates=[[30, 30], [60, 60], [90, 90]], truth=60, win=windows(12))
        self.assertEqual(result["candidate_count"], 3)
        self.assertTrue(result["candidate_occurrence"])
        loc = result["switch_localization"]
        self.assertEqual(loc["matched_candidate_count"], 1)
        self.assertEqual(loc["unmatched_candidate_count"], 2)
        self.assertEqual(loc["nearest_interval"]["split_interval"], [60, 60])
        tied = score(candidates=[[30, 30], [60, 60]], truth=45, win=windows(9))
        self.assertEqual(tied["switch_localization"]["nearest_interval"]["split_interval"], [30, 30])
        self.assertEqual(tied["switch_localization"]["unmatched_candidate_count"], 2)

    def test_control_seam_is_not_truth(self):
        result = score(candidates=[[40, 40]], truth=None, control=40)
        self.assertEqual(result["truth_boundaries"], [])
        self.assertIsNone(result["switch_localization"])
        self.assertTrue(result["control_junction_diagnostic"]["matched_within_tolerance"])
        self.assertEqual(result["grid_resolution"]["reference_type"], "control_construction_junction")
        with self.assertRaises(ValueError):
            score(truth=40, control=40)
        with self.assertRaises(ValueError):
            score(truth=None, control=None)

    def test_temporal_brackets_are_fixed_dates_not_estimated_change_times(self):
        result = score(candidates=[[40, 40]], truth=43)
        temporal = result["temporal_resolution"]
        self.assertEqual(temporal["supplied_record_count"], 80)
        self.assertEqual(temporal["construction_junction"]["left_utc"], "2020-02-12T00:00:00Z")
        self.assertEqual(temporal["construction_junction"]["right_utc"], "2020-02-13T00:00:00Z")
        self.assertEqual(temporal["construction_junction"]["elapsed_seconds"], 86400)
        self.assertEqual([w["window_index"] for w in temporal["qualified_windows"]
                          if w["straddles_construction_junction"]], [4])
        self.assertEqual(result["candidate_intervals"][0]["right_utc"], "2020-02-10T00:00:00Z")

    def test_timestamp_ties_missing_dates_and_canonical_order(self):
        times = ["2020-01-01T00:00:00Z"] * 80
        self.assertEqual(score(times=times)["temporal_resolution"]["construction_junction"]["elapsed_seconds"], 0)
        times[-1] = None
        self.assertEqual(score(times=times)["temporal_resolution"]["missing_timestamp_count"], 1)
        times[2] = None
        with self.assertRaises(ValueError):
            score(times=times)
        with self.assertRaises(ValueError):
            score(times=list(reversed(timestamps(80))))
        with self.assertRaises(ValueError):
            score(times=["2020-01-01"] * 80)


class FactorialAndAggregation(unittest.TestCase):
    def all_rows(self, blocks=("block-01",)):
        rows = []
        for block in blocks:
            for descriptor in factorial_cases(block):
                is_switch = descriptor["source_switch"]
                rows.append({**descriptor, "score": score(
                    candidates=[[40, 40]] if is_switch else [],
                    truth=40 if is_switch else None, control=None if is_switch else 40)})
        return rows

    def test_all_sixteen_have_exact_balance_and_reciprocal_cells(self):
        rows = factorial_cases("b1")
        self.assertEqual(len(rows), 16)
        self.assertEqual(len({r["case_id"] for r in rows}), 16)
        self.assertEqual(Counter(r["condition"] for r in rows), dict.fromkeys(CONDITIONS, 4))
        self.assertEqual(Counter(r["anchor_id"] for r in rows), {"AX": 4, "AY": 4, "BX": 4, "BY": 4})
        for row in rows:
            left = row["left_cell_id"].split(":")
            right = row["right_cell_id"].split(":")
            self.assertEqual(left[-1], "early")
            self.assertEqual(right[-1], "late")
            self.assertEqual(left[1] != right[1], row["source_switch"])
            self.assertEqual(left[2] != right[2], row["community_change"])
        self.assertEqual(sorted(Counter(r["left_cell_id"] for r in rows).values()), [4, 4, 4, 4])
        self.assertEqual(sorted(Counter(r["right_cell_id"] for r in rows).values()), [4, 4, 4, 4])

    def test_aggregate_per_condition_block_and_descriptive_only(self):
        result = aggregate_cases(self.all_rows(("b1", "b2")))
        self.assertEqual(result["planned_cases"], 32)
        self.assertEqual(result["planned_blocks"], 2)
        self.assertEqual(len(result["per_block"]), 8)
        self.assertIsNone(result["confidence_intervals"])
        self.assertEqual(result["analysis_type"], "descriptive_only")
        for condition in result["conditions"]:
            expected = condition["condition"].startswith("switch_")
            metric = condition["metrics"]["candidate_occurrence"]
            self.assertEqual(metric["complete_block_equal_mean"], int(expected))
            self.assertEqual(metric["complete_blocks"], 2)
            self.assertEqual(condition["executed_cases"], 8)
            loc = condition["metrics"]["switch_matched_within_tolerance"]
            self.assertEqual(loc["available_cases"], 8 if expected else 0)

    def test_unavailable_denominators_and_equal_block_weight_are_explicit(self):
        rows = self.all_rows(("b1", "b2"))
        target = "switch_same_community"
        for row in rows:
            if row["condition"] != target:
                continue
            if row["block_id"] == "b1":
                row["score"] = score()
            elif row["anchor_id"] != "AX":
                row["score"] = score(status="resource_limit", candidates=None, reasons=["whole_pipeline_incomplete"])
        result = aggregate_cases(rows)
        cond = next(r for r in result["conditions"] if r["condition"] == target)
        self.assertEqual(cond["planned_cases"], 8)
        self.assertEqual(cond["executed_cases"], 5)
        self.assertEqual(cond["unavailable_cases"], 3)
        self.assertEqual(cond["reason_code_case_counts"], {"whole_pipeline_incomplete": 3})
        metric = cond["metrics"]["candidate_occurrence"]
        self.assertEqual(metric["available_cases"], 5)
        self.assertEqual(metric["available_blocks"], 2)
        self.assertEqual(metric["available_block_equal_mean"], 0.5)
        self.assertEqual(metric["complete_blocks"], 1)
        self.assertEqual(metric["complete_block_equal_mean"], 0)
        self.assertNotEqual(metric["available_block_equal_mean"], 1 / 5)
        err = cond["metrics"]["switch_nearest_interval_error_records"]
        self.assertEqual(err["available_cases"], 1)
        self.assertEqual(err["complete_blocks"], 0)
        self.assertIsNone(err["complete_block_equal_mean"])

    def test_missing_duplicate_mutated_or_mislabeled_cases_rejected(self):
        rows = self.all_rows()
        for bad in (rows[:-1], rows + [rows[0]]):
            with self.assertRaises(ValueError):
                aggregate_cases(bad)
        bad = deepcopy(rows)
        bad[0]["right_cell_id"] = "unexpected"
        with self.assertRaises(ValueError):
            aggregate_cases(bad)
        bad = deepcopy(rows)
        bad[0]["score"] = score()
        with self.assertRaises(ValueError):
            aggregate_cases(bad)
        with self.assertRaises(ValueError):
            aggregate_cases(self.all_rows(tuple(f"b{i}" for i in range(7))))


if __name__ == "__main__":
    unittest.main()
