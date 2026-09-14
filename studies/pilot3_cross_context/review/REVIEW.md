# AHAS pilot 3: account-related comparison across discussion communities

The frozen comparison methods retained account-related ordering in this selected corpus. With full supplied samples, the primary method ordered different-account writing farther away than same-account writing in **92.5% of academic, 72.5% of physics, and 72.5% of mathematics anchor comparisons**. All 30 blocks were complete. This supports useful comparison signal under the registered sampling rules, with substantial context and missing-history limits; it is not an identity decision rule.

The study is complete: 60 previously unscored accounts, three fixed community-pair strata, 30 two-account blocks, three methods, four arms, and all 5,760 planned case rows. No production change, fitted threshold, reserve scoring, account substitution, or post-result refill occurred. Both gates passed before the first score. The 120-batch replay and independent numerical/statistical checks passed.

## Full samples: signal survives, with different context effects

Each stratum has 20 accounts/10 blocks, four early anchors per block, and 160 qualified comparisons per method. An ordering is 1 when the different-account distance exceeds the same-account distance, 0 if less, and 1/2 for an exact tie. Equal block means retain repeated-anchor dependence. Within and cross changes use the same ten complete blocks. “Stress” compares different-account/same-community with same-account/different-community writing.

|Method|Stratum|Cross ordering|95% block-bootstrap interval|Within ordering|Cross minus within|Hard stress|
|---|---|---:|---|---:|---:|---:|
|Prose n4 (primary)|Academic|92.5%|withheld*|85.0%|+7.5 pp|87.5%|
|Prose n4 (primary)|Physics|72.5%|59.1%–86.1%|82.5%|-10.0 pp|67.5%|
|Prose n4 (primary)|Mathematics|72.5%|61.4%–84.1%|85.0%|-12.5 pp|70.0%|
|Function-mask n4|Academic|75.0%|withheld*|77.5%|-2.5 pp|72.5%|
|Function-mask n4|Physics|80.0%|67.5%–91.7%|80.0%|+0.0 pp|75.0%|
|Function-mask n4|Mathematics|77.5%|63.9%–90.9%|92.5%|-15.0 pp|70.0%|
|Function-word JS|Academic|75.0%|withheld*|80.0%|-5.0 pp|82.5%|
|Function-word JS|Physics|72.5%|59.1%–86.1%|82.5%|-10.0 pp|72.5%|
|Function-word JS|Mathematics|82.5%|71.7%–92.5%|92.5%|-10.0 pp|77.5%|

Academic = AskAcademia/GradSchool; Physics = AskPhysics/Physics; Mathematics = learnmath/math. These are related forum scopes, not verified topic labels. The primary method is retained-prose character n=4 cosine; the two other methods remain secondary.

The primary context change is +7.5 percentage points in academic discussion, −10.0 in physics, and −12.5 in mathematics. The physics paired-change interval is [−22.7,+2.8] points; mathematics is [−20.5,−4.2]. Function masking has the largest observed mathematics decrease (−15.0 points), while function-word JS has the largest descriptive equal-stratum full-sample decrease (−8.3 points). Neither secondary method is consistently strongest across strata; no winner replaces the registered primary. The primary descriptive equal-stratum cross mean is 79.17%, versus 84.17% within, a −5.0-point change.

*The registered global bootstrap had one of its 10,000 draws with no academic block. Its rule therefore withholds academic intervals, including the full-arm result. This is preserved rather than changing the generator, rerolling draws, or dropping the missing draw. Physics and mathematics full-arm intervals are available. All intervals concern only the selected-corpus block resampling model; no representative-population accuracy or formal power claim follows.*

Primary cross-context descriptive ROC-AUC is 0.8125/0.7125/0.75125 and noninterpolated AP is 0.7840/0.6768/0.6882 for academic/physics/mathematics. Each uses 40 qualified different-account and 40 qualified same-account proxies per stratum. Their distinction from matched ordering matters: they compare scores across anchors, whereas the primary outcome pairs distances from one anchor. All method/context/arm rankings, class counts, unavailable cases, and raw-distance distributions are retained in the [summary tables](../results/tables/method-context-missingness.csv) and [distance tables](../results/tables/distance-distributions.csv); no pooled cross-stratum AUC is the primary evidence.

## Omissions mainly remove analytical availability

Every arm retains all 240 planned units, and every unit is nonempty. Ordinary guards still require 1,000 eligible words and eight eligible records. Full input preparation targeted 2,000 words/eight records and did not lower either production guard. The following coverage is identical for all three methods; comparison denominators are per method, not independent subjects.

|Arm|Units meeting ordinary guards|Qualified comparisons|Complete primary blocks|Median remaining words/unit|Remaining word range|
|---|---:|---:|---:|---:|---:|
|full|240/240|480/480|30/30|2,057.5|2,000–2,844|
|hash75|223/240|426/480|21/30|1,566.0|452–2,366|
|hash50|128/240|149/480|0/30|1,066.5|112–2,070|
|middle50|129/240|140/480|0/30|1,069.5|563–1,973|

Hash75 retains 88.75% of comparisons but only 70% of complete blocks. Hash50 and middle50 retain 31.04% and 29.17% of comparisons and **zero complete primary blocks in every stratum and method**. Their primary estimates and equal-stratum macros remain unavailable. All 2,175 unavailable method/arm comparison rows carry `insufficient_comparable_text`; none is an execution failure. Unavailable qualified scores remain null; their 2,175 corresponding raw distances are retained separately.

Hash75 has 6 units below the word guard and 14 below the record guard (3 overlap); hash50 has 98 and 46 (32 overlap); middle50 has 83 and 41 (13 overlap). Deletion is by whole records, so half the records is not exactly half the words. No arm refills its missing writing.

The valid hash75 comparison is against full scores on the same surviving complete blocks:

|Method|Stratum|Shared complete blocks|Full ordering on intersection|Hash75 ordering|Paired change|
|---|---|---:|---:|---:|---:|
|Prose n4 (primary)|Academic|7/10|92.9%|82.1%|-10.7 pp|
|Prose n4 (primary)|Physics|6/10|66.7%|66.7%|+0.0 pp|
|Prose n4 (primary)|Mathematics|8/10|71.9%|75.0%|+3.1 pp|
|Function-mask n4|Academic|7/10|78.6%|78.6%|+0.0 pp|
|Function-mask n4|Physics|6/10|79.2%|70.8%|-8.3 pp|
|Function-mask n4|Mathematics|8/10|71.9%|68.8%|-3.1 pp|
|Function-word JS|Academic|7/10|78.6%|67.9%|-10.7 pp|
|Function-word JS|Physics|6/10|66.7%|79.2%|+12.5 pp|
|Function-word JS|Mathematics|8/10|81.2%|75.0%|-6.2 pp|

Every hash75 interval is withheld: the academic/physics/mathematics series have 6/10/1 missing bootstrap replicates. These small selected intersections support descriptive changes only. Apparent gains, such as the physics function-word result, are not unconditional robustness gains. The half-deletion arms still expose available-anchor and qualifying-pair diagnostics, but those cannot supply the missing complete-block outcome. [Every anchor](../results/analysis/anchor_rows.csv), [registered omission intersection](../results/analysis/omission_intersections.csv), and [qualifying-case distance change](../results/tables/distance-omission-intersections.csv) is retained.

## What was controlled, and what remains uncertain

Ten authorized historical ConvoKit archives were considered under bounded acquisition/census plans. Seven additional archives totaled 618,530,464 bytes. Earlier 8-, 48-, and 52-account capacity results, the mathematics metadata-cap failure, all amendments, and failed setup/test attempts remain in their original records. The final six-source cohort passed the full 60-account target after the frozen automatic audit purged 2,082 candidate records. Mandatory exclusions covered 57 prior/protected/private identities; none of the additional 145 previously capacity-inspected identities entered the final cohort. The protected confirmation reserve remains unscored.

Final full cells contain 5,773 distinct comments and 502,546 eligible words, with 2,000–2,844 words and 8–50 whole comments per cell. Shared early/late periods and exact minimum-cost time/volume matching were frozen before scoring. They did not make realized dates or lengths equal. Across the 120 matched A/B cell pairs, the median absolute difference between their median writing dates is **205.4 days**, with a maximum of **1583.0 days**; within-account early/late median gaps have a median of 1032.1 days. A single comment contributes up to 64.1% of one full cell. [Cell statistics](../results/tables/full-cell-statistics.csv) and [pair/time-gap records](../results/tables/pairing-and-time-gaps.csv) preserve these imbalances. Results cannot isolate a causal effect of community or remove all timing, subtopic, demographic, or account-specific confounding.

Available source IDs, original bytes, omissions, pair sides, thread/content components, and all 6,120 batch input files passed independent preparation checks. No observed residual thread/content dependency crosses blocks under the registered definitions, leaving 30 resampling units. This is an available-content audit: 17 unavailable historical bodies, unsupplied writing, unmarked quotations, short reuse, and paraphrases remain unknown. The evaluator's development/evaluation split audit remains `not_auditable` because these batches contain no development split; the separate Gate B protection audit is not a claim that that evaluator status passed.

The population is a convenience sample of prolific surviving accounts in related historical Reddit communities, selected for four-cell capacity. English is a corpus assumption, not a verified per-record label; archives are supplied records, not complete account histories. Source-account labels do not verify human authorship, one human per account, bot/human identity, account takeover, cross-platform accuracy, temporal boundary localization, other modules, or the whole suite. Public redistribution rights for original prose were not established, so originals, source-account maps, conforming snapshots, grouping provenance, and unredacted engine outputs stay private.

## Verification, execution and evidence

The installed noneditable AHAS 1.0.4 package matches reviewed commit `ea41d82ecc3f6585a7dc2bca92ede34740f0b62d`, implementation fingerprint `bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179`, and analytical configuration `8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925`. Stale editable distribution metadata was explained before scoring. All 59 frozen production checks and 414 study synthetic tests passed; the initial combined suite's missing audit-engine location setting and other genuine failed attempts remain recorded.

The [final scoring freeze](../protocol/scoring-freeze.json), SHA256 `78b0f84cd0d451b3ebb53eac68ad297e959c0f273b5e5d1873ded836a374ab94`, bound 6,917 input/code/environment artifacts at 22:27:44 UTC before the main run began on 2026-09-14. The [protocol](../protocol/PROTOCOL.md) and [analysis plan](../protocol/analysis-plan.json) remain unchanged. No numerical defect or engine repair was needed. Reporting helpers and formatted tables written afterward are identified as post-registration presentation, not new registered outcomes.

All 360 main and 120 replay batches exited successfully within their unchanged input limits and declared operational ceilings. Observed outer wall times were 244.23 seconds for the main run and 83.69 seconds for replay, with at most two evaluator processes concurrently. [Per-batch resources](../results/normalized/batch-resources.json) retain actual wall time, peak memory, input/eligible words/records, and artifact bytes. Raw actual commands, exit codes, and receipts remain preserved; sanitized execution exports identify any local-path redaction explicitly. The [complete execution resource table](../results/execution/batch-resources.json) and [resource summary](../results/execution/resource-summary.json) include all 480 main/replay invocations. Main output artifacts totaled 27,460,954 bytes, with a maximum individual-process peak of 71.16 MiB; replay artifacts totaled 9,170,563 bytes with a 69.34 MiB maximum. Main invocations processed 4,172,841 eligible words and replay processed 1,411,713, counting intentional reuse across methods and arms; these are not unique-corpus totals. Individual-process maxima are not simultaneous combined memory. Resource use is observational, not a production optimization claim.

The [raw-distance check](raw-distance-independent-check-01.json) independently verified all 72 predetermined cases (36 qualified, 36 unavailable), with maximum absolute numerical difference 3.33×10⁻¹⁶ against a fixed 10⁻¹² tolerance. The [independent statistics check](analysis-independent-check-01.json) verified all 5,760 cases, 960 unit observations, 1,440 anchors, 360 block outcomes, 36 summaries, 27 omission intersections, 12 macros, and 171 shared-bootstrap series. The [replay check](replay-check-01.json) found all 360 canonical artifact comparisons byte-identical across 120 freshly executed batches under changed hash seed/timezone and relocated equivalent inputs. The draw digest is `659947266f26c12acd85fa1d8196890c3f2169d312b3fe8e700a1f2df6c89eac`.

The product implication is bounded: the existing comparison components carry account-related ranking information in sufficiently supplied samples from these contexts. They remain sensitive to context and become frequently unavailable when these particular approximately 2,000-word inputs lose records. This study supports that comparison use with its qualification and uncertainty limits; it supplies no portable identity threshold or detector.
