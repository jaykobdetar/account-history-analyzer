# Exact reuse search and its resource policy

AUD-003 is repaired by an exact segmented suffix automaton and explicit resource reservations. The semantic method remains `one_longest_contiguous_lexical_match_per_pair_v1`: the result is one longest contiguous normalized lexical-token match, confined to a left and a right retained segment. Equal-length matches use left segment index, right segment index, left token offset, then right token offset, in that order. Set shingles, rational thresholds, eligibility guards, source offsets, and the meaning of connected groups are unchanged.

The implementation is in [`reuse.py`](../src/account_history_analyzer/reuse.py) and [`reuse_matching.py`](../src/account_history_analyzer/reuse_matching.py). The analysis does not interpret a match as evidence of deceptive intent or a cause of reuse.

## Exact matching

The matcher builds a suffix automaton over the left record's eligible token segments, separating them with `None`. Lexical tokens are strings, so the separator cannot equal a token. Each right segment begins a fresh scan; neither side can produce a match across retained segment boundaries. Standard suffix-link fallback tracks the longest suffix of the scanned right prefix that occurs on the left.

Each state receives its earliest original `(left_segment_index, local_end_offset)` occurrence. Occurrences propagate along suffix links in decreasing represented length, using linear counting sort. For a candidate length, the earliest end gives the earliest start. Comparing the full semantic tie tuple across right segments recovers the required global tie order. An index is retained for consecutive qualifying pairs with the same left record and released when the left record changes. It is not accumulated for all records.

Equal complete segment-token sequences admit a direct full-segment optimum; the earliest longest segment wins. This shortcut is supplementary. The same exact automaton handles edited, shifted, periodic, and irregular nonidentical sequences. It does not suppress common tokens, sample positions, lower thresholds, or approximate a passage. Actual source slices retain their original case and punctuation.

The matcher uses Python string equality and dictionary lookups internally. Interpreter hash values are not stored as feature identities or used to order decisions. Independent brute-force tests enumerate all legal start pairs and test multisegment ties; they do not reuse the automaton recurrence.

## Limits and deterministic counters

The explicit defaults in [`config/default.toml`](../config/default.toml) are:

| Limit | Default | Reserved quantity |
|---|---:|---|
| `max_candidate_pairs` | 2,000,000 | Distinct candidate pairs, retaining the existing budget-plus-one lower-bound convention on exhaustion |
| `max_index_postings` | 2,000,000 | Distinct eligible record/shingle incidences, reserved before insertion into the per-record shingle set |
| `max_work_units` | 250,000,000 | Logical work reservations described below |
| `max_evidence_tokens` | 2,000,000 | Token strings in the selected passage token lists |
| `max_evidence_codepoints` | 8,000,000 | Codepoints in both selected source slices plus the normalized token strings in the passage lists |

All limits accept zero. Zero is useful for explicit abstention tests; a phase that requires no reserved work can still complete. A failed bulk reservation consumes no units. Every successful reservation is checked before its associated allocation or action. Counters never exceed their corresponding new limits.

The payload exports `resource_usage.method = "reuse_work_units_v1"`, four usage counters, the four corresponding limits, and `resource_limit_reason`. These are deterministic logical reservations, not elapsed time, machine instructions, or counts of finally emitted data. For example, reservations made before a later failure remain reported even though partial near results are discarded.

The work method charges these operations:

- One unit per record and per retained segment visited during near-shingle construction; `n` units for every attempted `n`-token shingle copy, including repeated shingles.
- A sort reservation `count × max(1, count.bit_length()) × width`, with width `n` for shingle sorts and width two for candidate-pair sorts. Each index insertion reserves `n` units.
- One unit per posting list and per pair encounter within that list. Repeated encounters with the same distinct pair consume work again. At a zero similarity threshold, every eligible nonempty-set pair is considered, including disjoint pairs.
- `1 + n × min(left_shingle_count, right_shingle_count)` units for each candidate's set metrics.
- The total left and right token and segment counts for the initial sequence-equality check. Automaton construction charges state creation, transition additions, existing-transition decisions, clone copies including their transition count, and transition redirections. It reserves `3 × state_count + concatenated_length + 1` units for counting-sort occurrence propagation. The scan charges each right segment, right token, and suffix-link fallback.
- One work unit per selected evidence token while counting its codepoints. Evidence size limits are checked before materializing the token list and source slices.
- `8 × (record_count + qualifying_pair_count)` units for graph and repeat-reduction traversal. Connected-component edges are bucketed in a single pass; optional near reductions inspect sparse earlier-neighbor edges instead of scanning every previous representative.

This policy bounds the declared operations and allocation quantities; it is not a wall-clock deadline or a proof of a particular peak resident memory on every interpreter. Input limits remain a separate contract. The complete exact-identity grouping and exact repeat reductions run independently of these near-search budgets. `nonempty_shingle_records` still describes every usable record, including short records that cannot qualify for a near or containment pair; it does not describe only the materialized index.

## Exhaustion and completeness

Any exhausted near-search limit produces `near_status = "resource_limit"`, `budget_complete = false`, and the exact exhausted field in `resource_limit_reason`. No partial near pair table, connected group, or near reduction table is returned. Exact groups and exact reductions remain complete. Optional near sensitivity reports `not_run_resource_limit`; the pipeline records the reason and returns incomplete-analysis exit code 4.

`candidate_count_is_lower_bound` describes candidate generation specifically. It is true if index or candidate generation was interrupted, including the existing distinct-pair limit. If the complete candidate set exists and matching or evidence subsequently exhausts a limit, the candidate count remains exact and the flag is false. Missing near results therefore cannot appear as a reassuring zero-match conclusion.

## Capacity calibration and measurements

The existing 1,000-record, 94,000-word formulaic benchmark has 499,500 candidates and 70–71 distinct shingles per record. Its complete reuse stage reserved **209,280,929 work units** under this policy; the independent receipt is [`reuse-independent-benchmark.json`](../qa/audit-repair/reuse-independent-benchmark.json). A 20-million or 200-million default would intentionally abstain on that declared workload. The 250-million default provides bounded capacity for it. This is engineering resource calibration, with no change to feature thresholds, passage selection, or scientific claims. Larger or denser inputs may still need explicit higher limits or may abstain.

The old installed 1.0.1 package and the repaired source were run in separate processes through `scripts/offline_exec.py`, which denies socket networking. Preprocessing was completed before each timed reuse call. At 8,000 tokens per record, the single-run observations were:

| Constructed pair | Installed 1.0.1 | Repaired | Selected match length |
|---|---:|---:|---:|
| Identical repeated token | 5.3586 s | 0.0101 s | 8,000 |
| Repeated token with one edit | 5.4543 s | 0.0186 s | 4,000 |
| Three-token period with one edit | 1.7965 s | 0.0169 s | 4,000 |
| Shifted three-token period | 1.8197 s | 0.0174 s | 7,999 |
| 31-token period with one edit | 0.1887 s | 0.0164 s | 4,000 |

The last pair qualifies as a near duplicate at the original threshold: its shingle intersection is 31 and its union is 36. Its complete pair payload, including evidence offsets and source text, had identical SHA-256 hashes before and after the repair at every tested length: 500, 1,000, 2,000, 4,000, and 8,000. All 25 before/after cases agreed on candidate counts, completion state, pair counts, and longest-match lengths. Exact and nonidentical matcher work reservations grew approximately linearly over these constructions.

Raw timings and environment/command receipts remain separate from deterministic comparisons:

- [`baseline-reuse-growth.json`](../qa/audit-repair/baseline-reuse-growth.json) and [`repaired-reuse-growth.json`](../qa/audit-repair/repaired-reuse-growth.json)
- [`baseline-reuse-near-growth.json`](../qa/audit-repair/baseline-reuse-near-growth.json) and [`repaired-reuse-near-growth.json`](../qa/audit-repair/repaired-reuse-near-growth.json)
- [`reuse-growth-comparison.json`](../qa/audit-repair/reuse-growth-comparison.json)

These are controlled engineering observations from one reference machine, with one timed call per construction and length. They do not establish a universal speed ratio, a deadline for arbitrary permitted input, cross-platform byte identity, or external scientific validity.

## Regression coverage

[`test_reuse_resources.py`](../tests/test_reuse_resources.py) covers exhaustive binary single and multiple segments, 3,000 randomized multisegment comparisons against independent substring enumeration, source slices, tie order, general low-entropy matches, unchanged near thresholds, every new zero limit, exact-limit versus one-unit-short behavior, repeated posting encounters, late and mid-match exhaustion, no partial near output, retained exact output, identifier independence, separate-process hash seeds, and pipeline exit code/schema behavior. [`test_reuse_adversarial_review.py`](../tests/test_reuse_adversarial_review.py) adds an independent reviewer’s oracle and graph/resource tests. The original numerical reuse and property tests remain in place.
