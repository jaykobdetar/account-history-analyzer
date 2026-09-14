# Acceptance coverage map

This map names executable checks; test results and skipped checks are recorded separately in EVALUATION.md. Passing synthetic checks does not establish external accuracy.

| Acceptance area | Executable coverage |
| --- | --- |
| IN-01–15, strict JSON/calendar/parent semantics, canonical row ordering | tests/test_ingestion.py, tests/test_m0_smoke.py |
| IN-07, IN-16, explicit defaults/reference path identity/toy guard | tests/test_config.py |
| TXT-01–18, tokenizer Unicode, segmentation and pooled counts | tests/test_text.py, tests/test_evidence.py |
| Registry contracts and caller immutability | tests/test_registry.py |
| Arithmetic and empty end-to-end M1 reports | tests/test_m1.py |
| Activity oracles, UTC bins, exact inclusive windows, simultaneous/missing times | tests/test_activity.py |
| Strict schemas and valid source/reference contracts | tests/test_schemas.py |
| OUT-05–07 atomic publication and dedicated output paths | tests/test_artifacts.py |

| RE-01–12 exact/shingle reuse, independent brute-force candidate oracle, containment and thresholds | tests/test_reuse.py, tests/test_reuse_properties.py, tests/test_m2.py |
| Cosine, base-2 JS, frozen-reference Delta, random SciPy comparisons | tests/test_style.py |
| WIN-01–04 and WIN-14 whole-record windows and explicit comparisons | tests/test_windows.py |
| WIN-05–09 PELT exhaustive and dynamic-programming oracles, family scaling and boundary mapping | tests/test_changepoints.py |
| WIN-10–13 edit/repeat/window/penalty sensitivity and independent one-to-one matching oracle | tests/test_sensitivity.py |
| WIN-15–16 constructed surface shift and vocabulary-only invariance | tests/test_style_invariance.py |
| Link occurrence/record denominators, IDNA/hostname safety, reply delays and parent cycles | tests/test_links_interactions.py |
| OUT-01–04, OUT-12, OUT-15–16 safe reports, native evidence links and exported-data SVGs | tests/test_reporting.py, tests/test_security.py |
| OUT-13–14 integrity-only versus actual replay, tampering and safe reference replay | tests/test_verification.py |
| Original fixture hashes and generator bytes across separate processes | tests/test_fixture_integrity.py |

The browser request/DOM audit runs separately under `scripts/browser_offline_exec.py`, because the stricter analyzer filter also blocks Chromium's required Unix-domain IPC. Both filters deny internet socket creation. Actual execution receipts distinguish the runs.

| Additional hardening requirement | Executable coverage |
| --- | --- |
| OUT-09–11 separate process bytes across TZ/hash seed/CWD/row order; IN-16 relocated reference | tests/test_reproducibility.py |
| Bounded preprocessing on permitted 200,000-codepoint marker inputs; raw/entity-decoded collision preservation | tests/test_text_resources.py |

| Evaluation and release requirement | Executable coverage |
| --- | --- |
| Hand ranking ties, independent boundary matching, confusion/coverage/abstention denominators | tests/test_evaluation_metrics.py |
| Strict local pair/stream formats, held-out isolation, frozen methods/thresholds, group leakage, whole-stream search, resource budgets | tests/test_evaluation_external.py |
| Evaluator-only truth, actual fixture measurements, numerical oracles, strict evaluation schema, evaluator process identity | tests/test_evaluation_synthetic.py |
| Evaluate CLI generated artifacts, missing datasets, failed-check exit status | tests/test_evaluation_cli.py |
| Complex style/edge-case release reproduction under input/environment permutations | scripts/check_release_reproducibility.py; actual receipt qa/reproduction.json |
| Locked wheel installation, network-disabled reference container and full workload timing | Actual commands/outcomes in docs/EVALUATION.md; raw receipts in qa/ and benchmarks/ |

## Four-finding audit repair (1.0.2)

| Repair contract | Executable coverage |
| --- | --- |
| Bounded artifact file/bundle/count/metadata envelope; real over-limit sparse-file refusal; atomic rollback; streaming canonical identity | tests/test_artifact_streaming.py |
| Actual default1,000-record analyze/publish/verify/full-recompute/render lifecycle with process timing and peak RSS | scripts/check_audit_roundtrip.py; supplied opt-in regression under qa/audit-repair/supplied-probes |
| Nested mapping-order invariance; immutable and parsed inputs; publication/rerender in both excerpt modes; evaluator structured values | tests/test_render_order.py |
| Forged report/chart with replaced checksum fails full replay; receipts excluded; canonical checksum bytes reproduced | tests/test_recompute_artifacts.py |
| General exact repeated-token matching, tie/segment oracles, all budget limits, repeated postings, mid-match/late exhaustion, retained exact output | tests/test_reuse_resources.py; tests/test_reuse_adversarial_review.py |
| Old/new genuine qualifying near-duplicate payload agreement and repeated-text growth | scripts/probe_reuse_resources.py; qa/audit-repair/reuse-growth-comparison.json |
| Mixed/autolink/formatted/code/quoted labels, distinct label host, independent same-destination links, excluded-span boundaries | tests/test_link_labels.py |

Actual repair outcomes and specific remaining validation limits are in docs/AUDIT_REPAIR.md. Earlier rows refer to historical release receipts.

## REPORT-005: reversible display labels (1.0.3)

| Contract | Executable coverage |
| --- | --- |
| Actual HTML cell labels decode exactly, remain distinct, preserve significant/invisible characters and stay inert | tests/test_ngram_labels.py |
| Full saved/generated style report, unchanged rates/rank order, input immutability, excerpt-none byte identity without hidden leakage | tests/test_ngram_labels.py; unchanged test_render_order.py/test_security.py |
| New release keeps strict reuse-resource schema while old typed payload remains readable | tests/test_report005_metadata.py |
| Supplied ten-coordinate/eight-label failure before; distinct labels after | qa/report005/handoff/scripts/test_ngram_label_contract.py; label-before.log; label-after.log |
| Actual reference-environment commands and analytical freeze | docs/REPORT005.md; qa/report005/ |
