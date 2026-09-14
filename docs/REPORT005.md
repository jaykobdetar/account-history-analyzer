# AHAS 1.0.3: lossless n-gram display labels

This is the focused AHAS-REPORT-005 presentation correction. The independent 1.0.2 review accepts AUD-001–004 for its exercised component/artifact cases. Its nonreference environment rerendered and republished saved measurements; it did not independently perform numerical recomputation. Those qualifications and all historical reports/receipts are preserved. No optimizer, feature, threshold, evidence-selection or statistical-method change is part of this patch.

## Representation and implementation

`src/account_history_analyzer/reporting.py:ngram_label` converts a source-derived character n-gram to an ASCII JSON string, then replaces each literal ordinary space with `\u0020`. The existing `md_text` layer escapes the notation for Markdown/HTML text. No new active markup, hidden attributes, hover strings, scripts or auxiliary HTML is introduced.

| Original feature, described explicitly | Visible label text |
| --- | --- |
| space, t, h | `"\u0020th"` |
| t, h, e, space | `"the\u0020"` |
| a, two spaces, b | `"a\u0020\u0020b"` |
| a tab | `"\t"` |
| literal backslash followed by t | `"\\t"` |
| literal backslash followed by u 0020 | `"\\u0020"` |

Apply JSON decoding to the displayed table-cell text to recover the exact original string. Quotes are part of the representation. All ordinary spaces are escaped, including repeated internal and all-whitespace features, so neither Markdown table trimming nor browser whitespace collapse can merge coordinates. JSON escaping keeps actual controls/Unicode distinct from literal escape-looking text. Non-ASCII characters, including invisible and directional controls, use explicit Unicode escapes; astral characters use JSON surrogate-pair notation. Raw Markdown has the usual additional text-escaping entities; decode the displayed label, not the source markup.

Only cosine contribution labels use this representation. Registered surface/function feature names retain their existing display. The fixed legend is included only when source-derived n-gram labels are shown. The existing `--excerpts none` skip remains before the cosine contribution table, and its output must be identical after substituting private n-grams/evidence text. Analytical JSON, generation, counts, distances, contribution ranking, source selection, charts and thresholds remain unchanged. The stable-zero feature presentation and a prose overview remain a separate usability backlog.

## Release and contract identities

Package/suite and template versions are 1.0.3. The analytical registry remains 1.0.2, with all method versions unchanged; the pinned PR #383 method/source is untouched. `payload_schemas.py` extends the existing strict reuse-resource release guard to 1.0.3 as well as 1.0.2, and both generated result-schema copies are synchronized. No payload field or validation rule changes. This prevents the new release from accidentally falling through to the legacy payload allowance.

The implementation fingerprint is `c63f7130067baef0d8eeddcff30cf1c99ba31b8b69816ca843db03a917d9789a`. The reference environment remains `CPython-3.12.3;Linux;x86_64;numpy=2.4.2;scipy=1.17.1;ruptures=1.1.10;markdown-it-py=3.0.0;jsonschema=4.26.0`. Runtime, build and resource pins remain unchanged. Source comparison and fresh result comparison explicitly distinguish metadata changes from analytical changes.

## Actual regression evidence

The supplied full-renderer test, unchanged from the handoff, failed before the patch: ten exported n=4 coordinates produced eight distinct labels. It passed after the patch. These are new local reference-environment runs, distinct from the reviewer's supplied logs.

```bash
python3.12 scripts/offline_exec.py env AHAS_SOURCE_ROOT="$PWD" \
  .venv/bin/python -m pytest --noconftest -q \
  qa/report005/handoff/scripts/test_ngram_label_contract.py
```

- Before: 1 failed in 2.58 s, exit 1 (`qa/report005/label-before.log`).
- After: 1 passed in 2.63 s, exit 0 (`qa/report005/label-after.log`).
- New actual Markdown/HTML tests: 63 passed in 11.51 s (`ngram-label-tests-final.log`), covering 55 explicit strings plus 100 generated compositions, full-report label/rate/order checks, immutable inputs and privacy. The initial two failures were in the new test harness's context regex, which consumed explanatory prose; that harness was corrected and rerun. The initial log remains available and is not counted as a passing run.
- New metadata/schema tests: 11 passed in 1.71 s (`independent-metadata-tests.log`), retaining strict resource accounting for 1.0.2/1.0.3 and typed 1.0.1 legacy readability.
- The supplied reviewer tests plus label regression: 24 passed in 2.99 s (`reviewer-after.log`), including the reviewer's 3, 000 independent substring-oracle comparisons. These fresh executions used the actual pinned reference environment, not the reviewer's different runtime.

The full fresh reference-host suite passed **627 tests**, with one browser-only skip in **97.05 s** (`full-tests.log`, `full-tests.xml`). The full digest-pinned container suite passed **627 tests**, with one Chrome/Node-unavailable skip in **145.74 s** (`container-tests.log`); this also exercised the new full-report test fallback without saved output bundles. The separate browser regression passed **1 test in 2.12 s** (`browser-test.log`).

The preserved AUD-001–004 component/property/integration suites ran as part of that full suite: artifact streaming/bounds and replay; deterministic map/list ordering; exact reuse matching and resource exhaustion; and hyperlink-label counts. The unchanged original supplied regression file additionally passed **all 3 tests**, including its opt-in 1, 000-record full analyze/publish/verify-recompute/rerender path, in **164.65 s** (`original-audit-tests.log`, XML). This is a fresh correctness execution; no new isolated throughput benchmark or universal memory/runtime bound is claimed.

All **18 actual CLI processes** across the six fresh fixture analyses, full recomputations and saved-result rerenders exited 0. All 14 canonical artifacts reproduced per fixture, all 7 presentation files matched byte for byte, and 3, 539 source-evidence slices resolved. `fixture-command.json`, `fixture-receipts.json`, `fixture-validation.json` and `fixture-driver.log` retain exact commands and results. Driver duration 203.156 s is an operational observation during concurrent QA, not a performance comparison.

The strict analytical freeze **passed**: all six results differ from 1.0.2 at exactly the three specified metadata paths. No measurement/finding exception was needed. All 60 config/registry/JSONL/SVG comparisons were byte-identical (`analytical-freeze.json`).

Actual Chrome 150.0.7871.128 browser inspection decoded all ten visible n=4 label cells to the exact stored source strings, retaining ten distinct labels. The screenshot was inspected for readability. No remote requests, active elements, event handlers, unsafe links, dialogs or source execution were observed (`ngram-browser.json`, `ngram-labels.png`). Its inspection script is QA-only and is never embedded in a product report.

## Commands and artifacts

Setup and public CLI commands remain in `README.md`. Commands below use fresh output locations and the existing kernel network-denial runner. Container execution uses the unchanged digest-pinned recipe with `--network none`.

```bash
python3.12 scripts/offline_exec.py .venv/bin/python -m pytest -q \
  --junitxml=qa/report005/full-tests.xml
python3.12 scripts/offline_exec.py env AHAS_RUN_LARGE_ROUNDTRIP=1 AHAS_REPO="$PWD" \
  .venv/bin/python -m pytest qa/audit-repair/supplied-probes/test_review_regressions.py -q \
  --junitxml=qa/report005/original-audit-tests.xml
python3.12 scripts/offline_exec.py .venv/bin/python scripts/check_audit_fixture_reports.py \
  --outroot output/report005 --qa qa/report005 \
  --expected-fingerprint c63f7130067baef0d8eeddcff30cf1c99ba31b8b69816ca843db03a917d9789a
```

Fresh command logs, test XML, source-change inventory and review evidence use `qa/report005/`; new fixture reports use `output/report005/`. Historical 1.0.2 files and receipts are never rewritten to represent the new source. The original source/archive hashes and the independent handoff hashes are preserved in the new audit directory.

## Analytical freeze and subsequent work

The freeze gate requires fresh results for all six fixtures to equal 1.0.2 exactly except three explicit paths: `analysis.suite_version`, `analysis.implementation_fingerprint`, and `analysis.resource_sha256.report_templates`. Every remaining field, including findings and complete numerical contributions, is compared with no tolerance or measurement exception. Config, registry, three JSONL exports and five SVGs must be byte-identical to 1.0.2. Canonical outputs under the new implementation must separately reproduce all 14 files; both excerpt modes and map/list ordering remain covered by repository tests.

This patch does not undertake realistic external evaluation. The next substantial task is appropriately sourced local paired-text/account-stream evaluation with explicit ground-truth limits, held-out separation, natural within-author variation and selectively incomplete histories. No external corpus or authorship labels were invented. `real_world_validation: not_established` remains unchanged; engineering success is not scientific validation.

## Changed files and preservation

Runtime presentation changes are confined to `reporting.py` (the helper, included-mode legend, cosine label cell, and template version). Release metadata changes are `__init__.py`, `pyproject.toml`, `uv.lock`, and the release guard in `payload_schemas.py` plus its two generated `results.schema.json` copies. New tests are `tests/test_ngram_labels.py` and `tests/test_report005_metadata.py`. Documentation updates are listed with these files in `qa/report005/changed-files.json`; `source.patch` is the focused unified diff against the preserved 1.0.2 archive.

The prepatch inventory contains 2, 579 files. Only the five intended existing package/schema files differ within its scope; no existing test, accepted audit implementation, optimizer/dependency code, source fixture, configuration, reference resource, old report, receipt or archive was modified (`preservation.json`). Root project metadata and documentation changes are separately identified by the archive-based diff. The 1.0.2 source archive still has SHA-256 `8a5be86a5cb4a264368e50c1ecfd3109ebaad4e89405ec870bc8c05b82cd92ae`.

New results and logs are deliberately separate from supplied historical receipts. External scientific validation, worst-case resource performance and unsupported-platform byte identity were not newly established. No requested REPORT-005 correction remains unimplemented; the package and archive checks below complete delivery without extending numerical scope.

## Package verification and deliverables

The fresh installed 1.0.3 wheel passed offline arithmetic analysis and full recomputation from an unrelated `/tmp` working directory. All 14 canonical files match the source run, all 54 package files match source/wheel/installation, and installed label round trips pass. The wheel is 197, 078 bytes, SHA-256 `4b472fa9d44d0803ab8f510eedc5a8bac5db454c5363dae81bd322511a59934d`. Exact setup, installation, execution and comparison receipts are in `qa/report005/wheel-verification.json`. An initial validation-harness inventory omitted the existing `py.typed` marker; that assertion and logs are retained, the inventory was corrected, and the completed comparison includes the marker. No installed package byte was wrong.

Final documentation is rebuilt into the source distribution, with an isolated offline rebuild required to match that already tested wheel. The final build/archival verification records are separate from numerical tests. The complete working source and fresh fixture reports are packaged at `release/1.0.3/account-history-analyzer-1.0.3-source-and-reports.tar.gz`; checksums and archive verification are alongside it. The focused patch is `qa/report005/source.patch`. Source report examples are in `output/report005/constructed_style_shift/` and the other five fixture directories.

The analytical baseline is frozen at the fingerprint above. No paired-text/account-stream real-world evaluation was claimed or begun by this report patch.
