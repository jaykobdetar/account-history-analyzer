# Public Cornell pilot: scientific review

The frozen pilot produced usable descriptive distances and explicit abstention on historical public text. It does not establish real-world authorship accuracy, a decision threshold, or the ability to identify a person, bot, AI-written text, deceptive reuse, or an account takeover. The strongest result here is that the existing methods and sample guards execute on authentic supplied records with inspectable coverage limitations. The observed ranking separation is conditional on a small, selected cohort and on which pairs qualify.

This review reads the already generated results and original-source metadata. It does not rerun distances, select another cohort, adjust a threshold, change defaults, or alter frozen protocols. Sources are the [cohort protocol](../protocol/COHORT.md), [cohort hashes and selected IDs](../protocol/cohort.json), [conversion audit](../inputs/public/conversion-audit.json), evaluator-only [source mapping](../inputs/public/source-map.json), and linked evaluation outputs. The 12 original paired executions have exit-code-0 receipts in `logs/paired-<arm>-<method>.receipt.json`; successful execution is distinct from every pair being measurable.

## Account identity and population

The source mapping contains 12 selected, distinct, non-placeholder corpus account keys. None is the literal account `AutoModerator` (case-insensitive check), and none matches null, blank, anonymous/[anonymous], unknown/[unknown], [deleted], [removed], or [missing]. This is only an observation about supplied identifiers. It does not classify the remaining accounts as human, establish who used an account, or rule out shared/automated account use. No behavior-based classification was performed.

The cohort contains 3,362 comments from one historical university community. Development contains 4 accounts and 392 retained comments (66–135 per account); evaluation contains 8 accounts and 2,970 comments (257–400 per account). The selection removes comments that disagree with the independent author/thread partition, excludes literal cross-split exact text, ranks accounts by surviving comment count, and caps the earliest 400. This strongly favors active accounts and differentially reduces development volume. The archive is a sampled historical source, not a complete history of these accounts. Missing records and nonverified English labels limit interpretation; every selected edit state remains unknown.

The paired full arm uses only the early/late units: 390 development comments across 8 unique units, and 1,600 evaluation comments across 16 unique units. Development units have 33–67 records; evaluation units each have 100. The generated sample summaries show 25,694 total retained words across development units (unit range 1,682–7,087; median 2,492), and 74,979 across evaluation units (range 1,411–8,003; median 4,232.5). Larger record counts do not guarantee enough eligible text: the full evaluation late unit `cornell-59640f33b1f68427439f-late` has 100 comments and 1,411 retained words, but only 817 words in records meeting the 20-word eligibility guard. Its same-account comparison and one ring comparison abstain under the unchanged 1,000-eligible-word guard.

## What the paired scores show

Each arm has **16 held-out pairs from 8 accounts**: 8 same-account and 8 different-account proxies. These are not 16 independent people. Each early/late unit is reused in a same-account pair and a ring control; the three methods and four missingness arms reuse the same underlying accounts and records. Do not pool the 12 evaluations into 192 independent held-out examples or interpret arm-to-arm stability as confidence. Development has a further 8 pairs from 4 different accounts, with no threshold fitted.

Larger distance is the positive ranking direction for the different-account label. ROC-AUC and average precision below are the exact exported floating-point values, calculated only on scored pairs. The null threshold means decision precision, recall, false-positive rate, and a confusion matrix were not run.

| Arm and exact result | Method | Scored held-out pairs | ROC-AUC | Average precision |
| --- | --- | ---: | ---: | ---: |
| [full](../results/paired-full-retained_prose_n4/evaluation.json) | Retained prose cosine n=4 | 14/16 | 0.8979591836734694 | 0.8954648526077097 |
| [full](../results/paired-full-function_mask_n4/evaluation.json) | Function mask cosine n=4 | 14/16 | 0.8979591836734694 | 0.9404761904761905 |
| [full](../results/paired-full-function_word_js/evaluation.json) | Function-word JS | 14/16 | 0.9387755102040817 | 0.9379251700680272 |
| [first8](../results/paired-first8-retained_prose_n4/evaluation.json) | Retained prose cosine n=4 | 0/16 | not computable | not computable |
| [first8](../results/paired-first8-function_mask_n4/evaluation.json) | Function mask cosine n=4 | 0/16 | not computable | not computable |
| [first8](../results/paired-first8-function_word_js/evaluation.json) | Function-word JS | 0/16 | not computable | not computable |
| [hash50](../results/paired-hash50-retained_prose_n4/evaluation.json) | Retained prose cosine n=4 | 14/16 | 0.7346938775510204 | 0.7548546691403833 |
| [hash50](../results/paired-hash50-function_mask_n4/evaluation.json) | Function mask cosine n=4 | 14/16 | 0.7755102040816326 | 0.8691308691308691 |
| [hash50](../results/paired-hash50-function_word_js/evaluation.json) | Function-word JS | 14/16 | 0.8163265306122449 | 0.8214285714285714 |
| [middle50_removed](../results/paired-middle50_removed-retained_prose_n4/evaluation.json) | Retained prose cosine n=4 | 14/16 | 0.7551020408163265 | 0.7858070500927644 |
| [middle50_removed](../results/paired-middle50_removed-function_mask_n4/evaluation.json) | Function mask cosine n=4 | 14/16 | 0.7551020408163265 | 0.804421768707483 |
| [middle50_removed](../results/paired-middle50_removed-function_word_js/evaluation.json) | Function-word JS | 14/16 | 0.8571428571428571 | 0.8486394557823129 |

Full, hash50, and middle50_removed each score 14/16 held-out pairs: 7 same-account and 7 different-account; coverage is 87.5%, with 12.5% abstention. All first8 comparisons abstain in both partitions for all methods, so those ranking values are unknown, not zero. In the full primary retained-prose result, scored same-account distances range 0.068278637652471–0.12583340228257756 (median 0.09518094504233998), while different-account distances range 0.10680903447478873–0.15787769096804172 (median 0.12333756045838995). These ranges overlap. Function-mask and JS full-arm ranges overlap as well. A distance is not a probability of the proxy label or its cause.

Removing roughly half the data reduces held-out ranking separation for all three methods on this frozen cohort. This is a descriptive comparison of correlated conditions, not evidence that one missingness process will behave similarly in another history. `first8` changes both amount and temporal coverage; hash50 approximates a fixed identifier-based removal mask; middle50_removed deletes a contiguous portion of record order. These masks do not model the many reasons real records can be absent.

Development illustrates why coverage must accompany rankings. Full scores all 8 development pairs. Hash50 scores only 3/8 (2 same-account and 1 different-account); all three exported AUCs equal 1.0 on that tiny surviving subset. That is not convincing validation or grounds to tune a threshold. Middle50_removed scores only 2/8, both same-account, and correctly has no computable AUC/AP. First8 scores 0/8. Lower-volume development samples are therefore unsuitable for calibrating the evaluation ranking values seen here.

## Temporal mismatch and within-split dependence

Temporal matching was not part of the frozen ring protocol. For each full unit, take the median original Unix creation time; for each pair, take the absolute difference between its two medians. The following values are in days, rounded to three decimals, and come only from supplied timestamps and frozen IDs:

| Split | Pair proxy | Pairs | Median absolute separation | Minimum–maximum separation |
| --- | --- | ---: | ---: | ---: |
| Development | Same account | 4 | 509.931 | 243.409–516.013 |
| Development | Different accounts | 4 | 602.142 | 442.133–1,107.571 |
| Evaluation | Same account | 8 | 333.887 | 118.623–1,956.175 |
| Evaluation | Different accounts | 8 | 434.567 | 82.494–1,387.800 |

Same-account early/late ranges are disjoint by construction. One different-account pair in each split has overlapping outer timestamp ranges; one development different-account pair has a right-unit median earlier than the left-unit median. These asymmetries can entangle account identity with era, conversation context, topic, and ordinary within-account change. They make the ring controls imperfect comparisons for authorship-related claims. Development selected records span 2014-03-26 to 2018-10-30; evaluation spans 2012-01-24 to 2018-10-31.

All 24 full-arm pairs use disjoint original record IDs between their two sides. However, one held-out different-account pair shares five original threads across its two units; the other full-arm pairs share no threads. Partition-level thread separation prevents development/evaluation thread overlap, but does not remove conversational dependence within the held-out comparisons. The pair is `different-cornell-59640f33b1f68427439f-cornell-6a157f6dc8f76021b0de`; the observation does not imply a cause for its measured distance.

## Leakage audit scope

The evaluator reports author, thread, source_document, and related_sample as audited disjoint across development/evaluation. Full-arm source_document group counts are 390 and 1,600; thread group counts are 282 and 1,083. Source-document IDs identify actual original comments, not the shared archive. The frozen conversion excluded 365 candidate records in 54 exact-normalized text groups spanning both splits. Normalization was only NFC with CRLF/CR converted to LF; case and other whitespace remained intact.

Those checks are useful but do not establish complete independence. Near-duplicate-cluster metadata is absent and explicitly `not_auditable` in every output. Reworded copies, shared quotations, templates, related conversations and the common community can remain. Among all 3,362 selected records, 10 exact-normalized text groups containing 24 records remain entirely within individual accounts; none spans selected accounts. One held-out same-account early/late pair shares one such full-text value. Exact cross-split exclusion therefore should not be described as a full reuse audit or as removing all within-account repetition. No additional exclusion was made after observing this.

## Account-stream interpretation and next evaluation

The separate [stream protocol](../protocol/STREAMS.md) uses metadata-ranked account-continuity controls and two prescribed author-splice constructions, with actual timestamps preserved and removal variants predeclared. An empty boundary list for an account-continuity control means no supplied construction boundary, not verified absence of real changes. Its candidates cannot be labeled confirmed false alarms. Conversely, finding a candidate near a splice only measures agreement with a construction operation; it does not validate detection of naturally occurring authorship changes or account compromise. This document's score table covers paired results only; account-stream execution outcomes are reported separately.

For a next evaluation, preserve this pilot and preregister a new, larger cohort before examining its scores. Use documented labels with an explicit account-versus-person distinction; obtain comparable development/evaluation text volume and match temporal spans, community context and text amount without altering method definitions. Audit near-duplicate/quotation/template grouping, keep all grouping dimensions separated across partitions, and measure coverage as a primary outcome. Use independent account groups when quantifying uncertainty rather than treating correlated pairs or arms as independent replicates. If a threshold is needed for a clearly defined downstream decision, set it on qualifying development data only and report its untouched held-out errors alongside abstention. None of these next steps requires a new distance method.

The reviewed official corpus sources did not supply a clear corpus-specific redistribution license; the software license is not evidence of a corpus license. Keep this local review and evaluator-only source mappings separate from any decision to redistribute the underlying text.
