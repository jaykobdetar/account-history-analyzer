# AHAS 1.0.2 — focused independent verification

## Decision

**Accept the four original repairs for the component and artifact cases exercised in this review. Keep 1.0.2 as the repaired baseline.** One separate presentation defect remains: significant whitespace in character n-gram labels disappears in the HTML tables. The underlying exported feature strings preserve that whitespace.

This is not a universal correctness certification, an independent rerun of the complete reference release, or evidence of real-world bot/authorship-detection accuracy. The next step should be a small lossless-label repair followed by realistic, explicitly labeled evaluation—not another optimizer replacement or broad rewrite.

No application source files were modified during this review. Reviewer scripts, temporary inputs, test outputs, and re-published reports are separate from the extracted source.

## Inputs and identity

The supplied archives are:

- `account-history-analyzer-1.0.2-source-and-reports.tar.gz`
- `account-history-analyzer-1.0.2-benchmark-report.tar.gz`

They were inspected before extraction; the 697 source/archive entries and 17 benchmark entries contained no traversal paths, symbolic/hard links, or special-file entries. Their hashes and sizes are in `evidence/archives.json`.

Independent source fingerprint calculation gives:

```text
583043074c28db2c91b62c33dc0197a569e863f4c83a80197c509324d9cb4fac
```

It matches the release declaration. All **54 package files** in the 1.0.2 wheel match the extracted source. The wheel hash matches the declared tested wheel:

```text
f0f1fdd9e07c29f35510d77a06fa8319ddd431d45accdfc380f587491e3b1eb6
```

All **91 checksum entries** across the six new fixture bundles and the separate benchmark bundle match their actual files. The benchmark's 16 file sizes, total size, canonical checksums, and supplied-input hashes match `qa/audit-repair/benchmark-lifecycle-receipt.json`.

These checks establish internal correspondence among supplied source, package, reports, and receipts. They do not independently establish that a supplied historical execution log was produced on the stated hardware.

## Execution environment and limits of this review

The available runtime is CPython **3.13.5**, Linux x86_64, with NumPy **2.3.5**, SciPy **1.17.0**, markdown-it-py **4.2.0**, jsonschema **4.26.0**, and pytest **9.0.2**. It is **not** the project's reference environment. `ruptures` and `hypothesis` are unavailable. Attempting to provision CPython 3.12.3 failed because DNS resolution was unavailable; the setup log is retained.

The final component tests and CLI commands import the actual public package initializer and unmodified application modules normally through `PYTHONPATH=src`. No numerical substitute, fake `ruptures` implementation, or altered optimizer was used. An initial exploratory component bootstrap was unnecessary and is not the basis of the final test results.

Selected pytest runs use `--noconftest` because the repository's global conftest imports unavailable Hypothesis. The selected tests do not use Hypothesis. Final analysis-related execution uses the supplied `scripts/offline_exec.py`; its seccomp installation and socket-denial self-check complete successfully.

**Not independently executed:** the full 553-test reference suite; Docker; Chrome; a fresh end-to-end numerical analysis of the 1,000-record benchmark; numerical `verify --recompute`; or an external research corpus evaluation.

The full reference-environment analyze/recompute results remain **supplied execution evidence**, backed here by inspection of the implementation and narrower independent execution. Re-rendering or re-publishing stored measurements must not be described as recomputing those measurements.

## Independent test results

| Run | Actual result | Evidence |
|---|---:|---|
| Selected unmodified repository component tests | 152 passed, 4 deliberately deselected pipeline cases | `evidence/component-tests-direct.log` and XML |
| Reviewer-authored independent checks | 23 passed | `evidence/reviewer-tests.log` and XML |
| Original supplied audit regression file | 2 passed, 1 explicit opt-in full-pipeline skip | `evidence/original-audit-tests.log` and XML |
| New lossless n-gram presentation regression | 1 failed, as expected for the remaining defect | `evidence/ngram-regression.log` and XML |

The 23 new checks include 3,000 fresh substring-enumeration comparisons against the actual reusable token matcher; streaming canonical-byte equivalence; exact and next-byte reader limits; refusal of a sparse 256 MiB + 1 byte file before opening it; strict malformed JSON rejection; and atomic rollback under file, total-byte, and file-count limits.

The matcher checks include repeated calls on the same index, equal inputs, reversed segments, empty segments, variable minimum lengths, and independently enumerated tie outcomes. They exercise a different procedure from the production suffix automaton.

The supplied logs were also inspected. They contain the declared 553-pass host/container summaries, separately passing browser test, and three passing original audit regressions with the full round trip enabled. Those figures are not added to the independent execution counts above.

## AHAS-AUD-001 — generated artifacts exceed the reader limit

**Disposition: repaired in the exercised artifact workflow.**

Source inspection confirms a distinct generated-artifact policy in `artifact_io.py`, rather than raising or removing the source-history ceiling. Generated file, directory, file-count, and metadata bounds are applied by the readers and publisher. `canonical_chunks` streams the result, checksum reads are chunked, and the publisher stages a complete directory before replacement.

The actual supplied benchmark has:

```text
results.json:       92,002,224 bytes
Entire 16-file set: 119,192,853 bytes
```

The actual unmodified `verify` CLI, supplied with the benchmark's source records and manifest, now returns exit **0**, status `integrity_only`, and **13 checked artifacts**. The old 50 MiB source-reader rejection does not occur.

The actual unmodified `render` CLI also returns exit **0**. Markdown, HTML, all five SVGs, and the copied config and registry are byte-identical to their corresponding supplied files.

Separately, the saved analytical result was loaded, reconstructed as an immutable `AnalysisResult`, and passed through the **actual `write_artifacts` publisher** into a fresh directory. All **14 canonical files**, including the checksum manifest, match the original. The resulting bundle also passes the actual artifact verifier.

This last test proves that the writer can publish the large stored values and that the resulting files can be read and checked. **It does not execute the original numerical analysis again.** Its operational receipts explicitly say that the inputs are stored measurements, not a new analysis.

Independent reader/publisher checks confirm that the repair has not simply disabled size limits. Over-limit files are refused before reading; a failed publication leaves an existing directory unchanged and removes staging directories.

Evidence: `benchmark-verify.*`, `benchmark-render.*`, `benchmark-rerender-comparison.json`, `benchmark-republished.json`, and the reviewer tests. The supplied full numerical lifecycle receipt remains in the project at `qa/audit-repair/benchmark-lifecycle-receipt.json`.

## AHAS-AUD-002 — mapping order changes rendered reports

**Disposition: repaired in all six fixtures and the benchmark examined here.**

For each of the six `output/audit-repair/` histories, the actual renderer reconstructed the original Markdown, HTML, and five SVGs byte-for-byte from saved results, evidence, and windows. That is **42 matching presentations** across the fixtures; adding the benchmark gives **49**.

Recursive reversal of dictionary order leaves both Markdown and HTML unchanged in both excerpt modes, across all six fixtures. List order is preserved by the reviewer transformation. Input-result digests before and after rendering also agree.

The original audit's mapping-order regression now passes as written. Source inspection shows the fixed semantic text-status order and sorted mapping-derived rows, rather than reliance on insertion order. The evaluator renderer also serializes structured mappings deterministically.

`verification.py` now compares the regenerated checksum mapping **and** canonical checksum-manifest bytes after writing all regenerated artifacts. Original excerpt mode comes from verified canonical config, not mutable run receipts. The supplied all-artifact replay tests explicitly exercise forged presentation files with correspondingly updated checksums, absent receipts, and altered receipt flags.

**Scope qualification:** I inspected those full-replay tests and their supplied passing logs, but did not execute their numerical replay path here because of the missing dependency/reference environment. The independently executed re-render and publication checks support the repair without being mislabeled as full numerical replay.

Evidence: `report-roundtrips.json`, `benchmark-rerender-comparison.json`, `original-audit-tests.log`, source `reporting.py`, `evaluation_reporting.py`, and `verification.py`.

## AHAS-AUD-003 — unbounded work inside repetitive comparisons

**Disposition: repaired on the exercised exact and non-identical repetitive cases, with explicit resource exhaustion.**

The old exact-passage matching path has been replaced by `TokenMatcher` in `reuse_matching.py`. It respects segment boundaries, operates on token equality, retains documented tie rules, and charges work inside index construction, repeated posting visits, matching, and evidence materialization.

I compared the actual 1.0.1 `reuse.py` method with the actual 1.0.2 method in the same runtime, using identical prepared features. Single-run reuse-stage timings at **8,000 words per record**, excluding preprocessing:

| Constructed pair | 1.0.1 | 1.0.2 | Complete pair payload |
|---|---:|---:|---|
| Identical repeated token | 6.8071 s | 0.0081 s | Identical |
| Repeated token, one edit | 6.8378 s | 0.0172 s | Identical |
| Three-token period, one edit | 2.3369 s | 0.0174 s | Identical |
| Shifted three-token period | 2.3225 s | 0.0192 s | Identical |
| 31-token period, one edit | 0.2386 s | 0.0185 s | Identical |

The equality check covers the entire pair payload, including passages, offsets, token lists, similarity values, and flags—not just the longest-match length. Different resource-accounting metadata is intentionally outside this cross-version pair comparison.

The repaired implementation was also measured at 1,000, 2,000, and 4,000 words for each construction. Its logical work counters grow approximately linearly across these examples. This is not a universal speed guarantee or a maximum-permitted-input benchmark.

The executed repository tests cover every new zero budget, exact versus insufficient reservations, repeated posting encounters, late/mid-match exhaustion, lossless exact results, and withholding partial near results. The actual non-identical cases matter: an exact-equality shortcut alone would not have closed this finding.

Evidence: `reuse-growth.json`, `reuse-growth.log`, `component-tests-direct.log`, `reviewer-tests.log`. The five baseline/current pair hashes are recorded in `reuse-growth.json`.

## AHAS-AUD-004 — hyperlink label double counting

**Disposition: repaired in the original regression and exercised context variants.**

The original one-hyperlink example now returns one occurrence. The executed `test_link_labels.py` cases cover descriptive, formatted, URL-only, code-containing, quoted, malformed, and plain-text inputs, different label/destination hosts, titles, and repeated genuine links.

In particular, separate hyperlinks to the same destination remain separate occurrences; they are not globally deduplicated. The source tracks hyperlink-label context while preserving text-exclusion boundaries.

Evidence: the original audit regression log and selected repository component-test log. Relevant implementation: `text.py`.

## Remaining issue: lossless n-gram label display

**Identifier: AHAS-REPORT-005. Scope: presentation and auditability, not an established distance-calculation error.**

The earlier HTML-only suspicion is now resolved by comparing the source, generated HTML, and actual `results.json`.

The export preserves significant whitespace, but `reporting.py` passes the strings through `md_text` into ordinary Markdown table cells. The HTML table parser strips structural leading/trailing whitespace. Examples in the inspected report:

| n | Stored feature, shown as a quoted string | HTML cell text |
|---:|---|---|
| 3 | `" th"` | `th` |
| 3 | `"he "` | `he` |
| 4 | `" the"` | `the` |
| 4 | `"the "` | `the` |
| 5 | `" the "` | `the` |

Two distinct four-character features therefore receive the same visible label. The new full-renderer regression fails because the ten displayed n=4 rows contain only eight distinct labels.

I checked **124,714 exported character n-gram coordinates** in the style-shift fixture: **zero** have the wrong code-point length for their declared n. That does not independently recompute all their counts, but it rules out truncation of these stored feature IDs and localizes the observed loss to presentation. Reconstructed HTML matches the supplied HTML exactly, so this is not an incidental preview difference.

The fix should use a reversible escaped label representation. Significant whitespace, tabs/newlines, backslashes, quotes, and markup characters must remain distinguishable and inert. Keep original feature IDs, counts, distances, and ranking unchanged. Preserve excerpt-free omission of source-derived strings.

Relevant source: `reporting.py` around `md_text`, `_table`, and the representation-contribution row at line 304. Evidence: `ngram-labels.json`, `ngram-regression.log`, `probe_ngram_labels.py`, `test_ngram_label_contract.py`.

The earlier suggestions to prefer supported nonzero stable features and add a fixed-template overview remain usability improvements. They are not additional claims that the original four repairs failed.

## Recommended next milestone

1. Close the original four audit findings with the scope above; retain the existing optimizer and numerical/resource regressions.
2. Repair the small lossless-label defect and rerun safety, excerpt-mode, and byte-reconstruction checks. This should be a report-focused patch, not a statistical redesign.
3. Freeze the analytical baseline and begin realistic local evaluation: same-author natural variation, different-author matched contexts, differing sample lengths, and deliberately selective/incomplete histories. Keep available-data coverage and abstention separate from classification outcomes.

The suite's own release note correctly retains `real_world_validation: not_established`. Nothing in this review changes that scientific status.
