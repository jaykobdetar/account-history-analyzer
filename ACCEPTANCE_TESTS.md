# V1 acceptance tests and release gates

This is a test specification for the implementation agent. The analyzer is not shipped in this planning package. Expected values in the fixture sidecars are construction facts and numerical oracles, not measurements already produced by an implemented suite.

Use `BUILD_SPEC.md` as the normative method contract. Every test should have a stable identifier. Maintain a requirement→test mapping in the implementation repository. Tests must exercise public functions and the CLI where appropriate, not merely duplicate the implementation's formulas in assertions.

## 1. Test layers

**Unit tests** check normalization, token boundaries, field validation, denominators, and registry contracts. **Numerical tests** compare against manually solved cases and independent libraries/oracles. **Integration tests** run supplied fixtures through the whole suite. **Property tests** explore permutations, empty inputs, Unicode, and boundary values. **Reproducibility tests** run separate processes. **Security tests** challenge rendering, local paths, and network isolation.

Passing all of these establishes engineering behavior, not real-world author/bot detection accuracy. External-validity tests are separately reported and may legitimately remain unavailable at the engineering release.

## 2. Input and canonicalization

| ID | Test | Required result |
|---|---|---|
| IN-01 | Valid six-event arithmetic snapshot | Schema and semantic validation succeed; seven physical input rows become six events. |
| IN-02 | Invalid JSON, duplicate object keys, NaN, Infinity | Strict error; no successful analytical report. |
| IN-03 | Same ID, identical expanded fields | Collapse ingestion duplicate; do not double activity or text counts. |
| IN-04 | Same ID, conflicting text or timestamp | Explicit conflicting-record error; do not choose arbitrarily. |
| IN-05 | Two IDs with identical prose | Keep both events; report reuse separately. |
| IN-06 | Mixed account IDs | Reject one-account run. |
| IN-07 | Unknown record/config keys | Reject with location/key and documented code. |
| IN-08 | Invalid calendar date; timestamp without UTC `Z`; excessive fractional precision | Reject rather than guess timezone/precision. |
| IN-09 | Missing timestamps | Keep text for applicable analyses; omit event from chronological analysis; show missing count. |
| IN-10 | Known edit preceding creation | Semantic error. An edited record with unknown edit time is allowed. |
| IN-11 | Deleted status with ordinary string text | Reject contradictory input; a present `[deleted]` string is instead a sentinel warning/exclusion. |
| IN-12 | Input/record-size limit exceeded | Clear limit error before truncation or misleading partial success. |
| IN-13 | Empty JSONL plus valid manifest | Valid empty snapshot; coverage count zero and appropriate insufficient-data states. |
| IN-14 | Row order, JSON key order, harmless JSON whitespace changed | Same canonical snapshot and analytical results; raw-file receipt/hash may differ. |
| IN-15 | Input text or coverage declaration changed | Relevant canonical hash changes. |
| IN-16 | Identical external reference bytes at different file paths | Same analytical config identity and numerical results; operational receipts may differ. |

Validate JSON Schema `format` annotations with an enabled format checker and additional semantic validation. Merely loading a schema is not a date-validity test. Default insertion must be implemented explicitly.

## 3. Text extraction and direct features

| ID | Test | Required result |
|---|---|---|
| TXT-01 | Arithmetic quote/code record | Retained words are exactly `I`, `think`, `it`, `works`; quoted/code words excluded. |
| TXT-02 | Same source flagged `plain` versus `markdown` | Different processing is permitted and reflected in config/source identity; plain mode does not pretend markup was parsed. |
| TXT-03 | Explicit link with descriptive label | Retain label words, exclude destination, count destination once. |
| TXT-04 | Bare HTTP(S) URL ending before sentence punctuation | URL excluded; punctuation preserved; no synthetic n-grams across removed URL. |
| TXT-05 | Removed inline code between `alpha` and `beta` | Never form an `alpha beta` shingle or cross-exclusion character n-gram. |
| TXT-06 | Adjacent emphasis delimiters | Ordinary retained words are not split merely by emphasis markup. |
| TXT-07 | Paragraph/record boundary | No shingle or n-gram crosses it. |
| TXT-08 | NFC-equivalent strings | Normalized feature representations agree; source/canonical snapshot hashes can differ because supplied originals differ. |
| TXT-09 | Straight versus curly apostrophe | Literal surface counts differ; normalized contraction token matching agrees. |
| TXT-10 | Em dash, ASCII hyphen, ellipsis glyph, and `...` | Distinct registered counts; ASCII period runs do not replace literal period counts. |
| TXT-11 | Code-only, quote-only, URL-only, whitespace-only text | Correct exclusion/empty denominators; no perfect style similarity by default. |
| TXT-12 | Unknown/Spanish language | No English-specific profile/segmentation; generic counts, reuse, and activity remain available. |
| TXT-13 | Quotation marks in ordinary prose | No semantic quotation removal just because quote characters appear. |
| TXT-14 | Mentions and source IDs | No handle/ID leakage into style feature vectors. |
| TXT-15 | Different-length records aggregated | Window rate is pooled numerator/denominator, not unlabelled mean of per-record rates. |
| TXT-16 | Ten-opportunity contraction guard | 9 opportunities: insufficient; 10: display qualified literal fraction. Counts always shown. |
| TXT-17 | Empty word/cased-letter denominators | Null plus reason, not NaN, Infinity, or a fake zero rate. |
| TXT-18 | Normalized text offsets | Each evidence slice recovers the actual stored normalized segment; raw offsets are never invented. |

Arithmetic fixture word counts in unique-event order: **8, 8, 9, 4, 4, 3**, totaling **36**. There are two literal `don't` matches and one `do not` match. The raw fraction is 2/3, but three opportunities do not satisfy the default display guard.

Add tokenizer tests for digits, underscores, accented letters, combining marks, internal apostrophes, emoji, URLs, and unusual Unicode numerals. Expected behavior must follow the operational regex and be documented, not be retrofitted to a guessed natural-language interpretation.

## 4. Numerical oracles

Read `fixtures/numerical_oracles.json`. Verify the following independently:

**Cosine:** identical unit vectors → 0; orthogonal unit vectors → 1; `[1,0]` versus `[1,1]` → `1-1/sqrt(2)`. Zero norm → not computable. Compare random nonnegative finite vectors against SciPy with fixed test seeds and defined tolerances.

**Jensen–Shannon:** base-2 distance of identical distributions → 0; `[1,0]` versus `[0,1]` → 1. Swapping inputs does not change the result. The returned distance is the square root of divergence. Do not accidentally use natural logs or omit `OTHER_WORD`.

**Shingles:** for the supplied seven-token examples, both sets have 3 elements, intersection 2, union 4, Jaccard 1/2, and directed containment 2/3. A contiguous embedded sequence has directed containment 1 without necessarily having Jaccard 1. Empty sets abstain. Repeating a shingle does not add set multiplicity.

**Thresholds:** exactly 4/5 meets a 0.80 threshold; 799/1000 does not. Use integer cross-multiplication. A displayed rounded 0.80 must not silently pass when the exact fraction is below it.

**Delta:** frequencies A=`[40,140]`, B=`[60,100]`, reference mean=`[50,100]`, SD=`[10,20]` yield mean absolute standardized difference **2**. Exclude zero-SD coordinates; reject incompatible lengths/units. No reference means no Delta result. Toy reference requires the explicit test override and warning.

**PELT:** unscaled scalar sequence `[0,0,0,0,10,10,10,10]`, min segment size 3, penalty 1 per internal change has a unique optimum at boundary 4. No-change SSE is 200; optimal penalized objective is 1. The final endpoint 8 is not an internal change. Constant series must not invent a boundary with a positive penalty.

Implement a brute-force partition oracle for N≤10. Compare objective values and legal segment sizes across several small series and penalties. When optima tie, compare optimal cost rather than demand an unspecified tie order. Separately test that the pinned production implementation repeats its chosen partition across processes.

## 5. Reuse, evidence, and limits

| ID | Test | Required result |
|---|---|---|
| RE-01 | Arithmetic records 1 and 2 | Normalized prose identical; raw text differs in spacing. |
| RE-02 | Distinct source strings, same normalized lexical tokens | Token-sequence match, not byte-identity claim. |
| RE-03 | Same code/blockquote in otherwise different records | No retained-prose match caused solely by excluded material. |
| RE-04 | Very short identical text | Count if appropriate, but no substantial-reuse headline under the minimum-length rule. |
| RE-05 | A~B and B~C but A not~C | A connected group may exist, but all-pairs similarity is not asserted. |
| RE-06 | Matching shingles in disconnected positions | No invented long contiguous passage. |
| RE-07 | Reconstructed contiguous match | Exact normalized slice exists in both cited segments. |
| RE-08 | Shingle inverted index versus brute force | Same qualifying pair set and numerical counts on small/random fixtures. |
| RE-09 | Candidate-pair budget exceeded | Exact results preserved; near module marked resource-limited, nonzero incomplete exit; no silent sampling. |
| RE-10 | Exact repeat-reduced sensitivity | Original primary/activity data unchanged; deterministic earliest representatives and exclusion relationships exported. |
| RE-11 | Optional greedy near deweighting | Exclusion is against a retained representative satisfying the rule, not merely an arbitrary component member. |
| RE-12 | Persistent hashes | No process-randomized Python `hash()` used as feature identity; any lookup digest collision requires actual equality checking. |

## 6. Temporal windows and change analysis

| ID | Test | Required result |
|---|---|---|
| WIN-01 | Window with enough words but too few records | Continues accumulating; both guards required. |
| WIN-02 | Final short remainder | Visible in coverage; excluded from segmentation, not from global summaries. |
| WIN-03 | Long dominant post | Whole record retained; dominance fraction and flag shown. |
| WIN-04 | Comments, submissions, and titles | Never silently pooled into one primary style stream. |
| WIN-05 | Fewer than 8 qualified windows | No PELT result; direct/adjacent measurements may remain. |
| WIN-06 | Constant/missing dimensions | Drop/log according to the exact scaling rule; no hidden zero imputation. |
| WIN-07 | Function-family dimensionality | Divide by specified family coordinate counts and number of nonempty families. |
| WIN-08 | PELT `jump` and `min_size` | Explicit values match config; library defaults cannot override silently. |
| WIN-09 | Candidate mapping | Correct left/right IDs, time intervals, and window membership; no exact takeover timestamp. |
| WIN-10 | Known edited records | Default observed-text warning and qualified unedited-only sensitivity; unknown edits not reclassified as absent. |
| WIN-11 | Within-community analysis underpowered | Explicit not-run/insufficient status, not false confirmation. |
| WIN-12 | Different window targets | Compare record/time boundary intervals, never unrelated window indices. |
| WIN-13 | Same-window stability matching | One-to-one matches with defined tolerance/ties; executed-setting denominator excludes skipped settings. |
| WIN-14 | Overlapping manual selections | Refuse unless explicit diagnostic override; overlap then labeled dependent. |
| WIN-15 | Shift sample | Surface measurements reflect actual uppercase/comma/semicolon/contraction transformation. Unique numerical sequence test, not ad hoc real-world thresholds, governs optimizer correctness. |
| WIN-16 | Vocabulary-only constructed shift | Designed function mask/surface/function profiles remain invariant; raw vocabulary representation may change. |

For the constructed shift fixture, log the resulting candidate boundary intervals and whether they overlap or neighbor the known construction boundary. Do not quietly change penalty settings until that one fixture is perfect. An unexpected outcome requires a debug explanation distinguishing a software bug from a methodological limitation; the numerical oracle remains the hard algorithmic gate.

## 7. Activity, link-host, and parent calculations

For the arithmetic fixture, event offsets are **0, 10, 20, 60, 120, 180 seconds** after the fixed start. Gaps are **10, 10, 40, 60, 60**, mean **36**, population variance **504**, and median **40**. The quartiles under the specified convention are **10** and **60**.

Maximum inclusive sliding-window counts are **3** for 30 seconds, **5** for 120 seconds, and **6** for 3,600 seconds. The greedy 30-second burst rule finds only IDs 1–3. All six supplied events fall in the same UTC hourly bin. The extra ingestion row is not a seventh event.

The arithmetic link-host result for `example.test` is **2 occurrences in 1 record**. Record 4 has a supplied creation-to-parent-creation difference of **60 seconds**, not a typing-time estimate.

Additional tests must cover simultaneous timestamps, exact-duration inclusivity, missing events, dates crossing midnight/year boundaries, empty/single-event histories, all-zero gaps, missing parent metadata, contradictory internal parent timestamps, cycles, incomplete edge days, known collection gaps, and hostname normalization. Verify repeated links in a single record do not inflate records-with-host counts.

## 8. Reporting, security, and deterministic reproduction

| ID | Test | Required result |
|---|---|---|
| OUT-01 | Every emitted source/window/evidence ID | Resolves to an actual supplied/calculated object. |
| OUT-02 | Unknown module result | `not_run`/`insufficient_data`, never a reassuring green score. |
| OUT-03 | HTML/source injection | `<script>`, attributes, entities, and unsafe links rendered inert; nothing executes. |
| OUT-04 | Remote URL/image/font/asset | No automatic network request or DNS resolution at analysis/render/open time. |
| OUT-05 | Pathlike ID and malicious output path | No writing outside output root or shell interpolation. |
| OUT-06 | Existing nonempty output directory | Refuse absent explicit overwrite. |
| OUT-07 | Mid-run interruption | No valid-looking finished report/checksums for an incomplete result. |
| OUT-08 | Results JSON | Finite values/null only; stable key/array order; no current time, hostname, absolute paths, wall-clock durations, or random IDs. |
| OUT-09 | Two separate processes in reference environment | Byte-identical canonical results and Markdown. |
| OUT-10 | Different `PYTHONHASHSEED`, TZ, working directory | Same analytical output; operational receipts may differ. |
| OUT-11 | Input row permutation | Same canonical output; raw-file hash differs as expected. |
| OUT-12 | Rendering `--excerpts none` | No prose excerpts in rendered report; underlying analytical values unchanged; warning that output is not necessarily anonymous. |
| OUT-13 | Verify without recompute | Says integrity-only, not independently reproduced. |
| OUT-14 | Tampered artifact/source/config | Verify fails with an explicit mismatch. |
| OUT-15 | Findings language | No human/bot/AI probability, statistically significant author-change claim, inferred health/location, or causal takeover narrative. |
| OUT-16 | HTML/chart data | Corresponds to exported canonical measurements, with missingness preserved. |

Run the analysis test process with networking blocked, not merely absent API keys. Run a local-browser check or an equivalent resource-request interception test on the HTML report. No image URL embedded in a source comment may become a tracking request.

## 9. Evaluation and release checks

The evaluator alone reads `.truth.json` files. Editing truth labels must not change analyzer output. Synthetic generator reruns must be byte-identical. Pair/stream splits must respect available groups; unavailable authors/thread metadata must result in a documented leakage limitation. Held-out evaluation labels may not select preprocessing, references, feature vocabulary, or thresholds.

Reports of external performance must include dataset and method/config hashes, denominators, abstentions, label definitions, and actual run commands. If an external dataset or labels were not supplied, record `not_evaluated`; do not fabricate scores or block correct engineering work unnecessarily.

A release requires all hard correctness/security/reproducibility tests to pass, measured rather than invented performance figures, and an honest limitations file. A method can remain uncalibrated and still be part of the measurement suite, but its outputs must remain descriptive candidates rather than validated author/automation conclusions.
