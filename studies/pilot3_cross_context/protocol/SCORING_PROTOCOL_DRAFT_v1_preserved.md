# Cross-context paired study: conditional scoring protocol

**Status: NOT REGISTERED FOR SCORING.** This document is a preparatory draft.
Only the bounded Gate A census has been authorized to run at this stage. A
failed capacity gate is a completed feasibility result, not a scored study or a
negative result about the methods. No reduced design is implicitly approved.
The frozen assignment is implemented conditionally on adequate authorized data.

## Baseline and question

Use reviewed repository commit `ea41d82ecc3f6585a7dc2bca92ede34740f0b62d`, installed
AHAS 1.0.4. Its implementation fingerprint is
`bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179`, and default
analytical configuration hash is
`8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925`.
No feature, vocabulary, distance, sample guard, resource limit, optimizer or
production code changes are permitted. No threshold or reference is fitted.

The question is whether different-source-account late writing has greater
distance than same-source-account late writing when both undergo the same
community change. Source-account identity supplies proxy labels; it does not
establish individual human authorship, bot/human identity, takeover, or whether
multiple accounts belong to one person. This study does not evaluate full-stream
boundary localization or the accuracy of the whole suite.

## Gates and selection

The target is 60 previously unscored accounts in 30 disjoint two-account blocks,
10 blocks in each of three community-pair strata. Every account supplies four
cells: each community in a shared early and late calendar period. Each cell must
supply at least 2,000 frozen-preprocessor eligible words in at least eight whole
eligible records. Production qualification remains 1,000 words and eight records
per side. Every eligible comment has at least 20 retained word tokens.

`gate_a_plan.json` fixes the initial archive list, finite date grid, necessary
record-count prefilter, eligibility, resource ceilings and exact disjoint-capacity
calculation. No home-community selection or fixed next-community rule is used.
All period alternatives remain in the census. Broad history periods are useful
for feasibility bounds but do not make realized posting dates identical.

Exclude all pilot 1 accounts, all scored pilot 2 paired and chronological accounts,
the entire protected confirmation reserve, and the private export account.
Previously volume-preprocessed but unscored accounts are not silently equated
with scored accounts: retain their prior-exposure flags and disclose them.
Private exclusion identities are not a public anonymization scheme.

Gate A counts precede contamination filtering and are ceilings on the final
eligible cohort. Gate B must audit the candidate pool before freezing membership,
so final selection can use surviving capacity. No account replacements or cell
refills may follow the final membership freeze or analytical abstention.

Proposed deterministic final selection, to be implemented and tested before
registration if capacity permits:

1. Freeze authorized archives, date schemes and stratum quotas from availability
   only. Retain all unfilled strata; require explicit approval for a smaller design.
2. Audit all otherwise capacity-eligible candidate cells and registered development
   protection sources. Use the existing exact, five-shingle near, 15-word template
   and recognized-blockquote definitions and connected components. The audit is
   an evaluation adaptation, not a production reuse-score change.
3. Remove observed shared-content contamination before ranking candidates. Purge
   records whose source thread or content component crosses intended comparison
   cells or protected development/reserve boundaries. Preserve exclusion IDs and
   reasons privately. Protected reserve audits must be automated and restricted to
   exclusion enforcement; do not inspect reserve prose or vectors to design rules.
4. Missing grouping information or exhaustion of the 2,000,000 candidate-pair
   ceiling blocks an independence claim. Verify broad five-shingle cap accounting
   independently; the previous pilot's agreement does not guarantee new agreement.
5. Choose globally disjoint accounts by a deterministic quota-feasible allocation
   ordered by SHA256(`ahas-pilot3-account-rank-v1:` + casefolded source identity).
   Retain a witness of feasibility; the Gate A witness is not the final cohort.
6. Select whole records by absolute integer UTC distance from the period midpoint,
   then original timestamp and original record ID. Stop only when both 2,000 words
   and eight records are reached. Do not cut or fabricate records. Export original
   chronology. Record all actual counts, overshoots, longest-record share, nearest-
   rank length quantiles, date endpoints, median times and early/late gaps.
7. For the 20 accounts in a stratum, choose a minimum-cost perfect matching by
   exhaustive subset dynamic programming. The additive pair cost is the sum over
   four cells of `abs(median_time_A - median_time_B)/period_duration` plus
   `abs(words_A - words_B)/2000 + abs(records_A - records_B)/8`, using exact rational
   arithmetic. Break equal-cost matchings by sorted source-identity hash pairs.
   Every account belongs to one block and one stratum. Missing required medians
   fail preparation, rather than receiving invented timestamps.

These pending Gate B steps must have executable tests and their own frozen source
identity before scoring. This draft does not claim they have run or passed.

## Comparisons and omissions

Each block has A/X, A/Y, B/X and B/Y in early and late periods. For each of the
four early anchors, compare its late counterpart in all four fixed categories:
same account/same community, different account/same community, same account/
different community, and different account/different community. This gives
16 comparisons per block per method/arm. Repeated anchors retain dependence;
the two sides of any one comparison must contain disjoint original record IDs.

Primary method: `cosine_distance_v1`, `retained_prose`, n=4. Secondary methods:
`cosine_distance_v1`, `function_mask_v1`, n=4; and `function_word_js_v1`,
`lexical_tokens`, n=null. All planned comparisons use all three. The evaluator's
`same_author`/`different_author` enums remain required implementation labels;
`label_definition` and all prose explicitly mean same-source-account and
different-source-account proxies. No combined score or fitted decision threshold.

Four arms, with no refill or changed record text/timestamps:

- Full prepared cell.
- Hash75: retain records whose SHA256 hash integer is below three quarters of
  `2**256`.
- Hash50: retain records below one half of the same hash space; this is nested
  within hash75. Salt: `ahas-pilot3-omission-v1`, joined to original record ID with
  a colon and encoded in UTF-8.
- Middle50: sort by original timestamp and ID; delete indices from `floor(n/4)`
  through `floor(3*n/4)-1`. Empty and undersized results remain in denominators.

## Outcomes and uncertainty

For each anchor, the primary cross-context outcome compares different-account
distance with same-account distance in the other community: 1 if greater, 0 if
less, 1/2 on an exact stored-score tie. Either distance unavailable makes the
anchor unavailable. Average the four anchors only if all four are available to
obtain a complete block score. Show available-anchor summaries separately.

Publish stratum-specific equal-block means first. Any equal-stratum macro mean
requires all three planned strata; do not silently renormalize missing strata.
Compute within-community ordering and cross-minus-within change on the same
complete blocks. Keep every per-anchor outcome and raw distance. Report the
separate harder stress contrast: different-account/same-community distance versus
same-account/different-community distance.

Secondary ROC-AUC uses pairwise rankings with one half for exact ties;
noninterpolated AP adds recall increments at complete tied-score groups.
Different-source-account is the positive proxy. Publish both class counts,
qualification denominators and unavailable reasons by method, stratum, context
and arm. Pooled differently scaled distances are not the primary evidence.

Preserve account blocks across every method/arm/anchor. Merge blocks linked by
any residual audited shared thread/content component into resampling units.
Disclose each stratum's effective independent-unit count. With fewer than five
units, report descriptive estimates and unavailable uncertainty. Otherwise use
10,000 deterministic cluster-bootstrap resamples, fixed SHA256 counter generator
`sha256-json-counter-rejection-v1`, seed
`ahas-pilot3-cross-context-block-bootstrap-v1`, exact arithmetic for orderings,
and nearest-rank 2.5th/97.5th percentiles. Resample the same unit draws for paired
method and arm comparisons; preserve every associated block in a drawn unit.
Freeze/export draw identity hashes, generator version and arithmetic. These
intervals describe only the selected-corpus resampling model.

For each deletion arm report planned units, nonempty units, word/record-qualified
units, method-qualified pairs, complete primary blocks, all abstention reasons
and observed remaining words. Compare separation changes on the intersection
that qualifies in both arms alongside coverage for all planned cases. Attrition
cannot turn a selected-case improvement into an unconditional improvement.

## Execution contract pending successful gates

Use the existing offline paired evaluator. Batch one account block per method/
arm: eight subset-only snapshots and 16 pairs. Validate all source bytes plus
dataset bytes against 50 MiB, all unique records against 10,000, and every text
against 200,000 codepoints; fail rather than trimming. The largest target design
has 360 batches and 5,760 method/arm comparison rows, representing 60 accounts.
At most two processes run concurrently. Export compact evaluator outputs; no
chronological full-report runs are part of this study. Preserve wall time, peak
memory, words, byte sizes, exit codes and failed attempts for every command.

Before the first style score, hash protocol, inventory, exclusions, audit rules,
all cohort/cell/record/group manifests, pair tables, omissions, scoring/analysis/
check code, batches and environment. Preserve this draft and every amendment.
Do not label a post-score amendment as preregistered confirmation.

Independently check source membership and byte fidelity, whole-record budgets,
omissions, pair identities, leakage/grouping and metric arithmetic. Verify a
preselected distance sample by direct feature/distance arithmetic independent
of evaluator metric aggregation. Replay a complete stratum for all three methods
and four arms in another process with a different hash seed, timezone and relocated
equivalent inputs, comparing canonical evaluator bytes. Operational paths and
timing may differ. A saved receipt is not a fresh replay.

If Gate A fails, stop without new distances and report the actual census,
unfilled quotas, authorized-source limitations and smallest concrete additional
data request supported by the evidence. If any repair is needed later, preserve
the frozen-baseline failure, separately review a narrow patch and identify every
affected rerun. Neither a positive result nor an accuracy target defines success.
