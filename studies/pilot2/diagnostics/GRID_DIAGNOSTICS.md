# Old splice output-grid diagnostic

Verified with ordinary AHAS 1.0.4 package imports and unchanged analytical components. The current preprocessor supplied word counts; a separate whole-record accumulator reconstructed the windows. No optimizer ran and no historical scores or the ten-record tolerance changed.

| Existing case | Qualified windows | Reported nearest error | Best legal error | Grid within tolerance 10 | Candidate state |
|---|---:|---:|---:|---|---|
| splice-1-full | 23 | 22 | 5 | yes | off_target_candidate |
| splice-1-hash50 | 12 | 11 | 11 | no | off_target_candidate |
| splice-2-full | 35 | 9 | 9 | yes | within_tolerance |
| splice-2-hash50 | 18 | no candidate | 9 | yes | no_candidate |

The hash-half variant of splice 1 cannot satisfy the registered tolerance at any legal output interval. Its reported interval is already the nearest attainable interval. This explains a representation limit; it does not convert that original failure into a pass. The hash-half variant of splice 2 had adequate input and no candidate even though a nine-record-error legal interval was available.

Legal cuts require at least three qualified windows on each side. Intervals use original full-record ordinals, so skipped short or otherwise ineligible records remain in the coordinate system. A split interval is [last eligible left ordinal + 1, first eligible right ordinal], inclusive. Final unqualified remainders are excluded.

All four reconstructions match newly exported production window memberships and all independent-review reference values. The old account-stream evaluator did not retain per-splice window exports; this missing artifact is explicit. Two existing natural-report exports independently corroborate the reconstruction against historical memberships.

All 465 historical files retain their exact hashes. Private record membership maps and exact operational commands remain outside the public repository.

This is post-hoc development evidence. Source-account construction labels do not establish human authorship, and no new held-out evaluation was scored.
