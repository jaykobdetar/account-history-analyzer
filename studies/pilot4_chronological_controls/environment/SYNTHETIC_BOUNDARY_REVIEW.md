# Focused account-stream and boundary-grid checks

Reviewed against the unchanged source at `ea41d82ecc3f6585a7dc2bca92ede34740f0b62d`. No tests, corpus preprocessing, or analyses were executed for this review. Baseline identity checks passed separately; repeating the full production suite is unnecessary while that baseline remains unchanged.

The production segmentation coordinate is a boundary between the original canonical positions `a` and `b` of the last left-window record and first right-window record. The external account-stream evaluator converts this to the **inclusive split interval `[a+1,b]`**. Truth split `k` is the zero-based canonical ordinal of the first record on the right, so its interval distance is `max(a+1-k, k-b, 0)`. A truth position inside the interval has zero distance; tolerance comparison includes equality. This is an ordinal interval, not an inferred event timestamp.

Primary default windows require at least 1,000 eligible retained words and eight eligible records, with whole-record overshoot retained. Eligible records need at least 20 retained words, declared English, a timestamp, and the matching record kind. Primary segmentation requires eight qualified windows, ignores the final unqualified remainder, uses `jump=1`, and requires at least three qualified windows per segment. These are separate gates: a legal geometric split need not produce a detected change, and insufficient data is unavailable rather than a zero-boundary success.

## Existing tests with the most direct value

The following node IDs are relative to the reviewed repository's `tests/` directory. They can be run as one narrowly selected suite through the installed target if pilot 4 integration later warrants it. They have been inspected here, not newly executed.

| Test node | What it verifies |
|---|---|
| `test_evaluation_metrics.py::test_boundary_intervals_use_original_split_positions_and_inclusive_tolerance` | Interval interiors/endpoints, exact tolerance equality, unmatched candidates, precision/recall and location error |
| `test_evaluation_metrics.py::test_boundary_matching_matches_unrestricted_exhaustive_oracle` | Tiny unrestricted bipartite matching oracle versus the production ordered algorithm; maximum match count, minimum distance, deterministic tie outcome, original input indices |
| `test_evaluation_metrics.py::test_boundary_denominators_and_unchanged_stream_aggregation` | No-candidate/no-truth undefined ratios, false candidates on unchanged executed streams, coverage and abstention denominators |
| `test_evaluation_metrics.py::test_invalid_boundary_coordinates_rejected` | Duplicate truths, touching/overlapping inclusive candidate intervals, zero/reversed coordinates, negative and Boolean tolerance |
| `test_changepoints.py::test_WIN_09_actual_boundary_mapping_retains_full_ranges_and_record_intervals` | Window boundary to original record positions with gaps; last-left/first-right records and UTC ranges; final remainder excluded |
| `test_changepoints.py::test_WIN_05_WIN_08_minimum_windows_and_constant_abstention` | Seven-window insufficiency, eight-window constant status, no fabricated change, minimum-segment feasibility |
| `test_windows.py::test_WIN_10_edited_observed_and_exclusion_positions_remain_original` | Omitted records do not renumber canonical positions; unknown edits remain |
| `test_windows.py::test_WIN_12_targets_never_relabel_indices_as_same_boundaries` | Different window budgets create different record-position grids; equal window indices do not imply equal boundaries |

Four small account-stream adapter tests additionally check the end-to-end schema and coordinate contract: `test_evaluation_external.py::test_EVAL_EXT_09_stream_runs_whole_pipeline_and_maps_split_coordinates`, `test_EVAL_EXT_10_stream_abstention_is_not_zero_false_boundaries`, `test_EVAL_EXT_11_stream_truth_bounds_and_protocol_hash_are_checked`, and `test_EVAL_EXT_14_eligible_constant_stream_counts_in_unchanged_denominator` (the last three use the same file prefix). These fixtures intentionally lower record/window word and record-count guards for cheap software tests; their success would not establish empirical feasibility under the frozen defaults.

If grid comparisons use production sensitivity outputs, add `test_sensitivity.py::test_WIN_12_different_windows_use_record_intervals_not_indices`, `test_interval_endpoint_touch_and_absence_are_explicit`, and `test_WIN_13_executed_denominator_skips_insufficient_but_counts_constant`. Sensitivity interval touching uses its own descriptive relation semantics; do not substitute those for the external evaluator's inclusive split interval matching.

The existing penalized-L2 tests already provide exhaustive and unpruned numerical oracles. They are useful if segmentation implementation identity changes, but baseline identity passed and does not justify rerunning all of them now.

## Proposed independent pilot 4 arithmetic fixtures

These are preparatory expectations for a separate study-level checker. They use synthetic metadata and independent arithmetic, not production boundary/grid helper functions as the answer oracle. Register any study-specific grid statistic before viewing results.

1. **Default-sized aligned grid.** Give 64 chronological eligible records exactly 125 retained words each. A whole-prefix reconstruction yields eight eight-record windows. Single-split legality with minimum segment size three admits internal window indices 3, 4 and 5, giving split intervals `[24,24]`, `[32,32]`, `[40,40]`. The terminal endpoint at window eight is not a candidate boundary. Truth at 32 has zero nearest-grid distance; truth at 33 has distance one. This tests representational resolution without asserting that any split must be detected.
2. **Original ordinal gaps.** Use a last eligible record at canonical position 23 and the next eligible record at position 26, separated by ineligible original records. The candidate split interval is `[24,26]`, not `[23,26]`, not a midpoint, and not an index in the filtered stream. Truth positions 24, 25 and 26 all have zero distance; 23 and 27 have distance one.
3. **Word and record guards together.** Build whole-record prefixes with a large first record, small following records, exact threshold equality, and target overshoot. A first record exceeding 1,000 words still cannot finish a window until eight records are present. Independently check no record splitting, reuse, or refill and that an unfinished final remainder creates no segmentation window.
4. **Unavailable versus executed no-change.** Seven qualified windows have no executed change metric even if some geometric window edges exist. Eight eligible constant windows count as an executed unchanged stream with zero candidates. Keep those denominators distinct.
5. **Unrestricted boundary assignment.** Exhaustively enumerate all partial one-to-one assignments for up to four disjoint candidate intervals and four truth positions. Choose maximum cardinality, then smallest total interval distance, then lexicographically earliest interval/truth pairs. Exercise shuffled inputs, competition for a single truth, exact tolerance equality, no truth, and no candidates. Test provenance indices separately from sorted matching order.
6. **Grid coarsening and segment legality.** Rebuild the same chronological records at each prespecified word budget; do not compare raw window indices across budgets. Enumerate legal full partitions with the minimum segment length when calculating any multi-boundary grid oracle; a union of individually legal edges need not be jointly legal. Return unavailable when the registered oracle's conditions cannot be met rather than selecting a different tolerance or construction after outcomes.

The study-level checker should compute fixed truth-to-grid quantities from registered truth and independently reconstructed eligible-window metadata, and compare observed candidate matching separately. It should never use observed boundaries to choose an easier construction, window budget, or tolerance.
