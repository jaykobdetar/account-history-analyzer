# Paired-study preparation and coverage review

This review describes frozen prepared inputs and default word/record eligibility. It contains no comparison scores, distance-qualified result counts, or confirmation representations. All counts below precede scoring and are derived from existing preparation artifacts.

The registered plan is [hash-bound here](../protocol/registration.json). The source is AHAS 1.0.4; configuration and implementation hashes are recorded in the companion [aggregate JSON](preparation-coverage.json).

## Sampling and exclusions

The three local archives contain 1,997,146 records and 1,754,805 comments. Global casefolded account identity yields 117,621 additional account keys after the original 12 pilot accounts and fixed placeholders/AutoModerator exclusions. Home community is assigned from 2017–2018 present raw character volume. The salted split and volume shortlist select 20 accounts in each of nine community/split strata; retained-word capacity then selects four in each stratum. All 36 slots were filled before purges; 144 shortlisted accounts were not selected.

| Community | Source records | Comments | Removed/deleted comments | Additional account/community keys | Duplicate IDs |
|---|---:|---:|---:|---:|---:|
| ApplyingToCollege | 1,148,299 | 1,027,292 | 68,034 | 46,335 | 0 |
| Cornell | 74,467 | 63,723 | 4,986 | 6,149 | 0 |
| college | 774,380 | 663,790 | 42,689 | 72,185 | 0 |

Account/community counts overlap across corpora and are not additive counts of people. Source-account metadata, raw prose, individual IDs and maps are excluded from this review.

The fixed January–September cells in 2017 and 2018 required 108,881 shortlisted comments to be preprocessed; 40,339 fell below the 20-word record guard. Another 65,797 shortlisted source records were outside those cells, and 2,818 were submissions. The selected-account candidate pool contained 33,190 records and 3,026,159 retained words.

The completed graph audit examined 358,744 candidate pairs under the registered 2,000,000-pair ceiling. It marked six records for cross-split component removal. Symmetric thread purging removed 8,311 records in 2,433 threads; four records overlapped the component purge. The union removed 8,313 records, leaving 24,877 candidates. No account replacement or record refill followed purging.

## Dependence and what “qualified” means

There are 12 selected accounts and six disjoint two-account blocks in each split: 36 accounts and 18 blocks overall. Each block yields four account-ID proxy pairs per condition and arm; the same records are reused across methods, conditions and omissions. The 72 scored dataset documents contain 384 pair occurrences before the three-method repetition, or 1,152 afterward. These are repeated observations of 24 scored accounts, not 1,152 independent people. The 12 confirmation accounts have 192 reserved units and zero entries in scored dataset documents.

The unchanged default guard requires at least eight eligible records and 1,000 retained words in each unit; every selected record already has at least 20 retained words. Shared B is bounded at 1,000–3,000 words per block/condition, with whole-record overshoot and the eight-record guard retained. Deletion arms use the original base unit and never refill. Word/record qualification is necessary but does not establish that a distance vector is nondegenerate or a method is available. Actual distance-qualified counts are deliberately null in this review.

| Split | Condition | Qualified units / planned | Empty units | Qualified proxy pair slots / planned |
|---|---|---:|---:|---:|
| development | within_community | 24/24 | 0 | 24/24 |
| development | cross_community | 13/24 | 10 | 2/24 |
| evaluation | within_community | 22/24 | 0 | 20/24 |
| evaluation | cross_community | 12/24 | 10 | 2/24 |
| confirmation | within_community | 24/24 | 0 | 24/24 |
| confirmation | cross_community | 12/24 | 10 | 0/24 |

This table is the full arm. Confirmation pair slots describe reserved sampling capacity only. Within-community full-arm qualification is 24/24 development and 20/24 evaluation pairs. The four inadequate evaluation pairs occur in Cornell after the registered purges. Cross-community qualification is 2/24 in each scored split; its sparse or empty units remain in the planned denominator.

## All planned conditions and omission arms

Every row has four accounts, two blocks, eight unit slots and eight proxy-pair slots. Confirmation rows have no scored-dataset pairs. “Missing groups” counts units without observed thread/source/near-component metadata; author and related-sample labels remain known. These three missing-group counts coincide because their corresponding units are empty.

| Split | Home | Condition | Arm | Qualified units / 8 | Qualified pairs / 8 | Empty units | Missing groups |
|---|---|---|---|---:|---:|---:|---:|
| development | ApplyingToCollege | within_community | full | 8/8 | 8/8 | 0 | 0 |
| development | ApplyingToCollege | within_community | hash50 | 8/8 | 8/8 | 0 | 0 |
| development | ApplyingToCollege | within_community | middle50 | 8/8 | 8/8 | 0 | 0 |
| development | ApplyingToCollege | within_community | drop_Cornell | 8/8 | 8/8 | 0 | 0 |
| development | ApplyingToCollege | cross_community | full | 4/8 | 0/8 | 4 | 4 |
| development | ApplyingToCollege | cross_community | hash50 | 0/8 | 0/8 | 4 | 4 |
| development | ApplyingToCollege | cross_community | middle50 | 0/8 | 0/8 | 4 | 4 |
| development | ApplyingToCollege | cross_community | drop_Cornell | 4/8 | 0/8 | 4 | 4 |
| development | Cornell | within_community | full | 8/8 | 8/8 | 0 | 0 |
| development | Cornell | within_community | hash50 | 5/8 | 2/8 | 0 | 0 |
| development | Cornell | within_community | middle50 | 6/8 | 5/8 | 0 | 0 |
| development | Cornell | within_community | drop_Cornell | 0/8 | 0/8 | 8 | 8 |
| development | Cornell | cross_community | full | 4/8 | 0/8 | 4 | 4 |
| development | Cornell | cross_community | hash50 | 0/8 | 0/8 | 4 | 4 |
| development | Cornell | cross_community | middle50 | 0/8 | 0/8 | 4 | 4 |
| development | Cornell | cross_community | drop_Cornell | 0/8 | 0/8 | 8 | 8 |
| development | college | within_community | full | 8/8 | 8/8 | 0 | 0 |
| development | college | within_community | hash50 | 7/8 | 6/8 | 0 | 0 |
| development | college | within_community | middle50 | 7/8 | 6/8 | 0 | 0 |
| development | college | within_community | drop_Cornell | 8/8 | 8/8 | 0 | 0 |
| development | college | cross_community | full | 5/8 | 2/8 | 2 | 2 |
| development | college | cross_community | hash50 | 0/8 | 0/8 | 3 | 3 |
| development | college | cross_community | middle50 | 0/8 | 0/8 | 2 | 2 |
| development | college | cross_community | drop_Cornell | 5/8 | 2/8 | 2 | 2 |
| evaluation | ApplyingToCollege | within_community | full | 8/8 | 8/8 | 0 | 0 |
| evaluation | ApplyingToCollege | within_community | hash50 | 7/8 | 6/8 | 0 | 0 |
| evaluation | ApplyingToCollege | within_community | middle50 | 8/8 | 8/8 | 0 | 0 |
| evaluation | ApplyingToCollege | within_community | drop_Cornell | 8/8 | 8/8 | 0 | 0 |
| evaluation | ApplyingToCollege | cross_community | full | 4/8 | 0/8 | 4 | 4 |
| evaluation | ApplyingToCollege | cross_community | hash50 | 0/8 | 0/8 | 4 | 4 |
| evaluation | ApplyingToCollege | cross_community | middle50 | 0/8 | 0/8 | 4 | 4 |
| evaluation | ApplyingToCollege | cross_community | drop_Cornell | 4/8 | 0/8 | 4 | 4 |
| evaluation | Cornell | within_community | full | 6/8 | 4/8 | 0 | 0 |
| evaluation | Cornell | within_community | hash50 | 0/8 | 0/8 | 0 | 0 |
| evaluation | Cornell | within_community | middle50 | 0/8 | 0/8 | 0 | 0 |
| evaluation | Cornell | within_community | drop_Cornell | 0/8 | 0/8 | 8 | 8 |
| evaluation | Cornell | cross_community | full | 3/8 | 0/8 | 3 | 3 |
| evaluation | Cornell | cross_community | hash50 | 0/8 | 0/8 | 4 | 4 |
| evaluation | Cornell | cross_community | middle50 | 0/8 | 0/8 | 3 | 3 |
| evaluation | Cornell | cross_community | drop_Cornell | 0/8 | 0/8 | 7 | 7 |
| evaluation | college | within_community | full | 8/8 | 8/8 | 0 | 0 |
| evaluation | college | within_community | hash50 | 8/8 | 8/8 | 0 | 0 |
| evaluation | college | within_community | middle50 | 8/8 | 8/8 | 0 | 0 |
| evaluation | college | within_community | drop_Cornell | 8/8 | 8/8 | 0 | 0 |
| evaluation | college | cross_community | full | 5/8 | 2/8 | 3 | 3 |
| evaluation | college | cross_community | hash50 | 0/8 | 0/8 | 3 | 3 |
| evaluation | college | cross_community | middle50 | 0/8 | 0/8 | 3 | 3 |
| evaluation | college | cross_community | drop_Cornell | 5/8 | 2/8 | 3 | 3 |
| confirmation | ApplyingToCollege | within_community | full | 8/8 | 8/8 | 0 | 0 |
| confirmation | ApplyingToCollege | within_community | hash50 | 8/8 | 8/8 | 0 | 0 |
| confirmation | ApplyingToCollege | within_community | middle50 | 8/8 | 8/8 | 0 | 0 |
| confirmation | ApplyingToCollege | within_community | drop_Cornell | 8/8 | 8/8 | 0 | 0 |
| confirmation | ApplyingToCollege | cross_community | full | 4/8 | 0/8 | 4 | 4 |
| confirmation | ApplyingToCollege | cross_community | hash50 | 0/8 | 0/8 | 4 | 4 |
| confirmation | ApplyingToCollege | cross_community | middle50 | 0/8 | 0/8 | 4 | 4 |
| confirmation | ApplyingToCollege | cross_community | drop_Cornell | 4/8 | 0/8 | 4 | 4 |
| confirmation | Cornell | within_community | full | 8/8 | 8/8 | 0 | 0 |
| confirmation | Cornell | within_community | hash50 | 4/8 | 4/8 | 0 | 0 |
| confirmation | Cornell | within_community | middle50 | 3/8 | 2/8 | 0 | 0 |
| confirmation | Cornell | within_community | drop_Cornell | 0/8 | 0/8 | 8 | 8 |
| confirmation | Cornell | cross_community | full | 4/8 | 0/8 | 3 | 3 |
| confirmation | Cornell | cross_community | hash50 | 0/8 | 0/8 | 3 | 3 |
| confirmation | Cornell | cross_community | middle50 | 0/8 | 0/8 | 3 | 3 |
| confirmation | Cornell | cross_community | drop_Cornell | 0/8 | 0/8 | 7 | 7 |
| confirmation | college | within_community | full | 8/8 | 8/8 | 0 | 0 |
| confirmation | college | within_community | hash50 | 7/8 | 6/8 | 0 | 0 |
| confirmation | college | within_community | middle50 | 8/8 | 8/8 | 0 | 0 |
| confirmation | college | within_community | drop_Cornell | 8/8 | 8/8 | 0 | 0 |
| confirmation | college | cross_community | full | 4/8 | 0/8 | 3 | 3 |
| confirmation | college | cross_community | hash50 | 0/8 | 0/8 | 3 | 3 |
| confirmation | college | cross_community | middle50 | 0/8 | 0/8 | 3 | 3 |
| confirmation | college | cross_community | drop_Cornell | 4/8 | 0/8 | 3 | 3 |

Empty units use valid empty JSONL files. Their group arrays are omitted rather than invented because the external schema requires nonempty arrays when present. The frozen evaluator can consequently label a group dimension `not_auditable` for that dataset despite the completed upstream candidate audit. This caveat is different from a detected cross-split overlap.

## Word volume, overshoot and timing

The following full-arm summaries show minimum / median / maximum across eight units in each community/split/condition. Zero words and records describe known empty units; a largest-record share is unavailable when its denominator is zero. The companion JSON includes these summaries for every arm, observed/unavailable counts, target B, record counts, and UTC bounds.

| Split | Home | Condition | Eligible words | Overshoot words | Largest-record share | Unavailable shares |
|---|---|---|---:|---:|---:|---:|
| development | ApplyingToCollege | within_community | 3,007 / 3,014 / 3,146 | 7 / 14 / 146 | 0.055 / 0.079 / 0.129 | 0 |
| development | ApplyingToCollege | cross_community | 0 / 500 / 1,186 | 0 / 0 / 186 | 0.109 / 0.160 / 0.226 | 4 |
| development | Cornell | within_community | 1,973 / 2,602 / 3,049 | 0 / 30 / 228 | 0.060 / 0.118 / 0.316 | 0 |
| development | Cornell | cross_community | 0 / 510 / 1,249 | 0 / 10 / 249 | 0.125 / 0.232 / 0.298 | 4 |
| development | college | within_community | 3,004 / 3,044 / 3,269 | 4 / 44 / 269 | 0.051 / 0.110 / 0.332 | 0 |
| development | college | cross_community | 0 / 1,126 / 1,468 | 0 / 126 / 468 | 0.136 / 0.294 / 1.000 | 2 |
| evaluation | ApplyingToCollege | within_community | 3,006 / 3,160 / 3,895 | 6 / 160 / 895 | 0.083 / 0.165 / 0.254 | 0 |
| evaluation | ApplyingToCollege | cross_community | 0 / 508 / 1,095 | 0 / 8 / 95 | 0.123 / 0.222 / 0.257 | 4 |
| evaluation | Cornell | within_community | 988 / 1,044 / 1,413 | 0 / 44 / 407 | 0.151 / 0.267 / 0.498 | 0 |
| evaluation | Cornell | cross_community | 0 / 524 / 1,413 | 0 / 3 / 413 | 0.157 / 0.263 / 1.000 | 3 |
| evaluation | college | within_community | 3,013 / 3,052 / 3,365 | 13 / 52 / 365 | 0.034 / 0.066 / 0.137 | 0 |
| evaluation | college | cross_community | 0 / 1,002 / 1,851 | 0 / 2 / 851 | 0.104 / 0.195 / 0.299 | 3 |
| confirmation | ApplyingToCollege | within_community | 3,018 / 3,060 / 3,133 | 18 / 60 / 133 | 0.060 / 0.086 / 0.099 | 0 |
| confirmation | ApplyingToCollege | cross_community | 0 / 516 / 1,146 | 0 / 16 / 146 | 0.139 / 0.158 / 0.186 | 4 |
| confirmation | Cornell | within_community | 1,558 / 2,068 / 2,391 | 0 / 26 / 242 | 0.079 / 0.133 / 0.333 | 0 |
| confirmation | Cornell | cross_community | 0 / 786 / 1,387 | 0 / 9 / 387 | 0.124 / 0.284 / 0.432 | 3 |
| confirmation | college | within_community | 3,006 / 3,102 / 3,143 | 6 / 102 / 143 | 0.078 / 0.109 / 0.183 | 0 |
| confirmation | college | cross_community | 0 / 640 / 1,606 | 0 / 1 / 606 | 0.149 / 0.273 / 0.565 | 3 |

Pairing minimized differences in source-account cell-median timestamps among the three possible matchings, using metadata before selecting centered whole records. It cannot make the resulting samples perfectly matched in date or length. Below are the observed full-arm median gaps in days between each pair’s two sample medians, by proxy class. Each class has four planned pairs per row; empty-sided gaps remain unavailable. The difference is same-account minus different-account, not an effect estimate.

| Split | Home | Condition | Same-account gap median days (observed / 4) | Different-account gap median days (observed / 4) | Median gap difference days |
|---|---|---|---:|---:|---:|
| development | ApplyingToCollege | within_community | 380.1 (4/4) | 373.9 (4/4) | 6.2 |
| development | ApplyingToCollege | cross_community | unavailable (0/4) | unavailable (0/4) | unavailable |
| development | Cornell | within_community | 361.6 (4/4) | 361.6 (4/4) | 0.0 |
| development | Cornell | cross_community | unavailable (0/4) | unavailable (0/4) | unavailable |
| development | college | within_community | 365.9 (4/4) | 365.5 (4/4) | 0.4 |
| development | college | cross_community | 306.5 (2/4) | 306.5 (2/4) | 0.0 |
| evaluation | ApplyingToCollege | within_community | 365.1 (4/4) | 365.1 (4/4) | 0.0 |
| evaluation | ApplyingToCollege | cross_community | unavailable (0/4) | unavailable (0/4) | unavailable |
| evaluation | Cornell | within_community | 395.5 (4/4) | 393.0 (4/4) | 2.5 |
| evaluation | Cornell | cross_community | 312.6 (1/4) | 345.7 (1/4) | -33.0 |
| evaluation | college | within_community | 346.5 (4/4) | 337.9 (4/4) | 8.6 |
| evaluation | college | cross_community | 376.0 (1/4) | 370.8 (1/4) | 5.2 |
| confirmation | ApplyingToCollege | within_community | 353.8 (4/4) | 358.6 (4/4) | -4.8 |
| confirmation | ApplyingToCollege | cross_community | unavailable (0/4) | unavailable (0/4) | unavailable |
| confirmation | Cornell | within_community | 357.7 (4/4) | 341.7 (4/4) | 16.0 |
| confirmation | Cornell | cross_community | 318.5 (1/4) | 351.5 (1/4) | -33.0 |
| confirmation | college | within_community | 358.1 (4/4) | 357.5 (4/4) | 0.5 |
| confirmation | college | cross_community | 244.6 (1/4) | 241.2 (1/4) | 3.4 |

The JSON additionally reports absolute left/right word and record imbalances for both classes in every arm. These preparation comparisons are descriptive, use repeated samples, and do not imply control of topic or verified continuity of a human author.

## Failure history and actual verification

The first candidate process began at 2026-09-14T19:11:44.582168+00:00; registration occurred at 2026-09-14T19:11:48.324571+00:00. The in-memory plan copy lacked only the additive missing-content clarification. Finalization exited 1 before writing units because the saved plan differed from the registered plan. The original candidate files and failed receipt remain unchanged. A fresh replay in `prepared/paired-registered` began after registration, reproduced the pool byte-for-byte and all selected metadata/ranks exactly, and then finalized successfully. The original run is not relabeled as registered. [Exact provenance and delta](../inventory/paired-registered-replay.json).

Seven synthetic adapter checks passed. Independent checks reconstructed all 180 shortlist capacities and all 33,190 candidate word counts, verified original-source fidelity, and verified all 576 actual prepared units and 72 dataset schemas. All 8,239 exported record occurrences, representing 2,485 distinct source records, preserved their source record values. Observed author, thread, source-document, audited-component and related-sample groups were disjoint across all three splits.

The following links lead to actual recorded argv, exit status and timing. Times are operational measurements during concurrent study work; they are not canonical results or performance guarantees.

| Executed check | Exit | Wall seconds | Receipt with actual command |
|---|---:|---:|---|
| Seven synthetic adapter checks | 0 | 2.268 | [Receipt](../inventory/paired-adapter-final-tests.receipt.json) |
| Independent retained-word/ranking preflight | 0 | 97.239 | [Receipt](../inventory/paired-preflight-run.receipt.json) |
| Actual source fidelity | 0 | 13.497 | [Receipt](../logs/candidate-fidelity.receipt.json) |
| Original candidate process | 0 | 101.275 | [Receipt](../inventory/paired-candidates.receipt.json) |
| Preserved failed original finalize | 1 | 0.170 | [Receipt](../inventory/paired-finalize-run.receipt.json) |
| Registered candidate replay | 0 | 102.457 | [Receipt](../inventory/paired-registered-candidates-run.receipt.json) |
| Replay identity verification | 0 | 0.183 | [Receipt](../inventory/paired-registered-replay-check-run.receipt.json) |
| Completed paired leakage audit | 0 | 61.586 | [Receipt](../logs/paired-leakage-audit.receipt.json) |
| Registered finalization | 0 | 4.030 | [Receipt](../inventory/paired-registered-finalize-run.receipt.json) |
| Independent actual prepared-input checks | 0 | 3.661 | [Receipt](../inventory/paired-prepared-check-run.receipt.json) |

## Limits of this pilot

- This is a volume-selected pilot from three educational communities in one historical ConvoKit/Pushshift Reddit collection, not a probability sample of Reddit accounts or independent corpus replications.
- Labels denote equality or inequality of casefolded source account keys only. Shared or automated accounts and multiple accounts belonging to one person remain possible.
- English is a corpus assumption; original authorship, language, edit history and complete account coverage are not established.
- Four pairs share each two-account block; methods, conditions and omission arms reuse sources. Pair counts are not independent people and do not justify IID intervals or broad accuracy claims.
- The initial historical pilot was inspected and is development evidence; its 12 accounts were excluded rather than relabeled as held-out.
- Missing group arrays in empty units are omitted to satisfy the external schema. The evaluator can therefore report not_auditable for a dimension despite the completed candidate-population audit; no passed labels are fabricated.
- Observed group disjointness covers the registered exact/near/template/recognized-quotation audit. Unmarked/indirect quotations, paraphrases and shared outside sources may remain.
- Pre-score word/record qualification is necessary but does not certify nondegenerate distance vectors, method availability or scientific validity. Actual distance-qualified counts are unexamined/null here.
- Confirmation metadata and preparation budgets are summarized only for capacity inspection. Confirmation records are physically absent from all scored dataset documents; no confirmation representation or distance is examined here.
- Cross-community support is sparse and remains as empty or insufficient units; no replacement, refill, changed threshold or post-score selection improves those counts.

This review covers paired preparation only. Chronological construction, its joint group audit, final scoring authorization, and later numerical results have separate artifacts. Engineering checks and a useful local pilot do not establish real-world authorship validation.
