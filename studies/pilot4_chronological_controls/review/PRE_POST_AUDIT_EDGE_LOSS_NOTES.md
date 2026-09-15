# Fixed-pool audit edge-loss diagnosis

All 28 cell prefixes and all seven candidate accounts satisfied their internal gates before the audit. Applying exactly the 195 registered purges leaves 26 valid prefixes and two internally qualified accounts. The four previously compatible edges become zero: one physics edge, two Linux edges sharing an account, and one programming edge. The pre-audit maximum was one disjoint block in each stratum; the post-audit maximum is zero in each.

| Stratum | Blocking change after the audit |
|---|---|
| Physics | The required early AskPhysics prefix reaches 40 comments at 5,562 words, exceeding the 5,500-word ceiling. Its surviving pool still contains 57 comments and 7,520 words; total scarcity is not the blocker. |
| Linux | Every cell still passes the final volume rule, but median-date alignment fails. The two prior edges now fail both early and late 30-day spans. |
| Programming | A required late programming cell retains only 36 comments and 4,413 words, below both the 40-comment and 5,000-word minimums. |

For the two lost Linux edges, the exact eight-cell date-span checks are:

| Opaque endpoints | Early before → after (days) | Late before → after (days) |
|---|---:|---:|
| candidate-01 / candidate-02 | 26.180943 → 37.365509 | 21.985255 → 44.791956 |
| candidate-01 / candidate-03 | 20.888727 → 39.068241 | 21.935197 → 44.791956 |

The raw diagnostic reason token `whole_prefix_exceeds_5500_words_before_both_targets` names the ceiling check that runs before accepting a target-satisfying prefix. In the observed physics cell, the violation occurs on the 40th comment: both minimums are reached on that comment, while the maximum-word rule is violated. The recorded counts, rather than the abbreviated token, identify the exact failure.

Candidate ordinals follow frozen plan order within each stratum. They are distinct from the separate independent report's hash-ordered account ordinals; no correspondence should be inferred from equal ordinal numbers. Source account keys and original record IDs are omitted.

This report compares prefixes reconstructed from already-saved selection metadata, before and after the same audit partition. It does not add records, change cuts, relax gates, process writing or run a detector. Gate loss is an observed consequence of applying the frozen exclusion and construction procedure, not a causal estimate and not an analyzer abstention. All chronological metrics remain unmeasured because no eligible final block was constructed.

[Full metadata-only diagnostic](pre-post-audit-edge-losses-01.json) · [Execution receipt](../logs/pre-post-edge-diagnosis-01.receipt.json) · [Five synthetic endpoint checks](../logs/pre-post-edge-diagnosis-tests-01.stdout.log)
