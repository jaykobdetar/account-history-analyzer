# Recorded resource and storage costs

Both registered batches finished before this review. This report reads receipts, file sizes, and hashes; it runs no new analyses and makes no scientific accuracy claim.

| Execution class | Slots / analyzer invocations | Outer elapsed seconds, min–max | Outer process RSS MiB, min–max | Supplied record rows, min–max | Output MiB, min–max |
| --- | ---: | ---: | ---: | ---: | ---: |
| account id continuity proxy evaluation | 16 / 16 | 5.150–48.493 | 178.469–1144.633 | 101–249 | 0.015–0.017 |
| constructed splice evaluation | 16 / 16 | 14.060–71.705 | 310.352–1667.781 | 140–434 | 0.015–0.017 |
| operational omission availability analysis | 6 / 6 | 25.088–93.515 | 238.605–646.961 | 101–241 | 38.320–145.675 |
| paired comparison evaluation | 72 / 72 | 0.273–3.069 | 41.672–95.180 | 0–650 | 0.068–0.073 |
| unfilled slot no analyzer invocation | 20 / 0 | 0.553–0.593 | 30.715–31.438 | not measured | not measured |
| unknown truth full natural analysis | 2 / 2 | 50.861–93.971 | 377.492–646.512 | 207–241 | 79.908–145.675 |

| Completed batch | Jobs | Wall seconds | Sum of case elapsed seconds | Receipt peak RSS MiB |
| --- | ---: | ---: | ---: | ---: |
| paired | 2 | 48.401 | 93.000 | 95.180 |
| streams | 2 | 700.749 | 1339.331 | 1667.781 |

Outer case elapsed includes startup and orchestration; stream cases also verify the frozen inventory and reconstruct the legal grid after execution. Inner run receipts are reported separately in JSON: their timer and RSS are captured before final report/artifact publication. Concurrent job elapsed times overlap and are not CPU time. RSS is a process high-water mark reported by the command/descendant receipt, not the sum of simultaneous process memory; system-wide peak RAM was not measured.

Unfilled preparation slots are counted as no analyzer invocation. Their short wrapper costs are real; absent scientific results are not zero measurements.

The highest-RSS splice, `chrono-college-pair2-splice-drop_Cornell`, used 1667.781 MiB by the outer receipt and took 70.873 seconds. Its 434 records contain 31,847 retained body words, including 30,524 eligible style words in 303 records. Its published evaluator bundle is 0.017 MiB; compact evaluator output does not imply a small intermediate analysis. Word counts were obtained afterward by the unchanged preprocessor only, with a separate receipt and no style/optimizer invocation.

The largest supplied constructed/omission case has 434 records. The 200–400-comment selection bounds apply to complete available source-account histories; combining one account's earlier portion and another account's later portion can exceed 400. Word volume, windows, comparisons, and intermediate serialization also affect cost. The earlier 400-comment development profile is not an upper bound for later histories or splices.

| Recorded preparation or prior development check | Exit status | Elapsed seconds | Peak RSS MiB |
| --- | ---: | ---: | ---: |
| logs/approved-acquisition.receipt.json | 1 | 0.060 | 21.902 |
| logs/approved-acquisition-network.receipt.json | 0 | 34.020 | 23.688 |
| inventory/cornell-inventory.receipt.json | 0 | 43.032 | 254.250 |
| inventory/source-frame-run.receipt.json | 0 | 36.338 | 412.723 |
| inventory/paired-candidates.receipt.json | 0 | 101.275 | 461.379 |
| inventory/paired-registered-candidates-run.receipt.json | 0 | 102.457 | 461.668 |
| inventory/paired-finalize-run.receipt.json | 1 | 0.170 | 29.891 |
| inventory/paired-registered-finalize-run.receipt.json | 0 | 4.030 | 189.504 |
| logs/paired-leakage-audit.receipt.json | 0 | 61.586 | 1612.980 |
| logs/chronological-preparation.receipt.json | 1 | 37.865 | 297.559 |
| logs/chronological-preparation-retry.receipt.json | 0 | 104.154 | 1736.441 |
| inventory/paired-preflight-run.receipt.json | 0 | 97.239 | 140.965 |
| inventory/paired-registered-replay-check-run.receipt.json | 0 | 0.183 | 46.223 |
| inventory/paired-prepared-check-run.receipt.json | 0 | 3.661 | 222.016 |
| logs/paired-leakage-independent-check.receipt.json | 0 | 22.502 | 360.852 |
| logs/audit-cap-and-joint-bridges.receipt.json | 0 | 45.654 | 966.000 |
| logs/chronological-prepared-artifact-tests.receipt.json | 0 | 15.500 | 77.293 |
| logs/exposed-development-profile.receipt.json | 0 | 195.994 | 458.930 |
| logs/exposed-development-recompute.receipt.json | 0 | 74.462 | 454.242 |
| review/paired-replay-run.receipt.json | 0 | 3.574 | 94.426 |
| logs/natural-canonical-recompute.receipt.json | 0 | 59.545 | 377.352 |
| logs/splice-canonical-replay.receipt.json | 0 | 41.441 | 725.188 |
| review/largest-cost-word-characterization.receipt.json | 0 | 0.688 | 33.137 |
| review/resource-cost-build.receipt.json | 1 | 1.745 | 30.750 |

Failed preparation/acquisition attempts are preserved and remain failures. The first resource-review build also failed because the review helper initially compared an unexpanded configuration mapping with the analytical resource-bound identity; its exact failed source/receipt are preserved, and a regression checks the corrected identity. No frozen configuration had changed. The registered paired replay reproduced the earlier cohort and candidate bytes after registration; it is additional preparation cost. The joint chronological audit is included in the successful chronological preparation receipt, with no separately recorded stage time. These selected receipts are not an accounting of all engineering work or test runs.

The development resource probe is an already exposed 400-comment history. cProfile adds instrumentation overhead. Its canonical serialization and schema-validation cumulative times overlap and must not be added as independent phases; the separate unprofiled recomputation includes artifact verification, full analysis, and publication replay. No optimization or limit change was made.

| Storage scope | Files | Logical MiB | Allocated MiB |
| --- | ---: | ---: | ---: |
| prepared datasets and sidecars | 1413 | 113.246 | 116.480 |
| primary paired outputs with logs | 505 | 5.372 | 6.754 |
| primary stream outputs with logs | 617 | 662.332 | 663.812 |
| profiled development bundle | 16 | 101.794 | 101.832 |
| development profile and resources | 19 | 102.594 | 102.641 |
| three source archives | 3 | 286.247 | 286.262 |

Storage is the sum of final regular-file sizes; allocated bytes use Linux st_blocks × 512. Transient staging space and peak disk usage were not measured. Primary output directories include operational logs and receipts; per-case bundle sizes and canonical bytes are separated in JSON. Storage scopes may overlap (for example the profiled bundle is within resources), so these rows must not be blindly summed.

The unchanged frozen limits are 50 MiB cumulative input, 10,000 unique records, and 200,000 codepoints per text; each published bundle allows at most 256 MiB per file, 512 MiB total, and 32 files including receipts/checksums. Metadata JSON has a fixed 1 MiB cap. The evaluator enforces cumulative distinct snapshot/input budgets across the dataset. The table counts rows across distinct supplied input files, a conservative upper bound if multiple files encode the same canonical snapshot. One registered case per invocation keeps these limits local and explicit.

Near reuse remains capped at 2,000,000 candidate pairs, 2,000,000 record/shingle postings, 250,000,000 work units, 2,000,000 evidence tokens, and 8,000,000 evidence codepoints. Artifact size limits are not a universal RAM bound. The preparation graph audits used a 3 GiB address-space ceiling; ordinary measurement batches used at most two workers and have no claimed system-wide RAM cap. The full resolved limits and observed headroom are in JSON.

Binding checks passed: True. All 1448 frozen study files, three source archives, implementation/resources/lockfiles, and 465 original-study files were checked without exporting private text or source maps. Implementation: `bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179`. Scoring freeze: `fba67a5a1c8ddc51c66cbe67c0ff02c317a776df382d5cd3c412d858e7de8df5`.

No monetary cost is inferred: local elapsed time and memory/storage observations are available, while electricity, hardware depreciation, cloud billing, and human effort were not measured. No cross-platform byte identity or general performance guarantee is claimed.
