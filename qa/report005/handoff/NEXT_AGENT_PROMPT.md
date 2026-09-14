# Next agent task: close the four repairs, fix lossless report labels

The independent 1.0.2 review accepts AHAS-AUD-001–004 for the exercised component/artifact cases. Preserve all four implementations, the pinned PR #383 optimizer, existing tests, thresholds, feature definitions, and reference-environment contracts. Do not repeat the optimizer investigation, undo the repairs, add a collector/extension, or introduce an AI classifier.

The review independently ran 152 repository component tests, 23 reviewer tests (including 3,000 new substring-oracle comparisons), and the two small original audit regressions. It verified/re-rendered the actual 92,002,224-byte benchmark result and republished saved values with 14 matching canonical artifacts. Its environment was not the reference environment; full numerical recomputation remains supported by your supplied reference receipts, not independently rerun there.

## Required remaining correction: AHAS-REPORT-005

Significant whitespace is lost from character n-gram labels in generated HTML. The original strings remain correct in `results.json`.

Actual examples:

```text
stored n=3 " th"   -> HTML cell "th"
stored n=3 "he "   -> HTML cell "he"
stored n=4 " the"  -> HTML cell "the"
stored n=4 "the "  -> HTML cell "the"
stored n=5 " the " -> HTML cell "the"
```

The relevant path is `reporting.py`: `md_text(feature_id)` passes the string into `_table`, and `render_html` sends that Markdown table to the parser. Surrounding whitespace is treated as table formatting. Distinct feature identifiers collapse to one displayed label.

The attached `test_ngram_label_contract.py` executes the full renderer on the existing style-shift fixture and currently fails: ten distinct exported n=4 labels become eight distinct displayed labels. Run it with `AHAS_SOURCE_ROOT` set to the project root. It is not a test of a proposed new helper.

### Acceptance requirements

Implement a deterministic, explicitly documented, reversible representation for source-derived n-gram display labels. A quoted escaped representation is suitable, provided ordinary spaces and other significant/invisible characters remain unambiguous after HTML rendering; quoting alone must not collapse repeated internal spaces. Distinguish actual whitespace from literal backslash escape sequences.

Do not change feature IDs in analytical JSON, n-gram generation, counts, distance calculations, contribution ordering, evidence selection, thresholds, or statistical scope merely to fix display. Do not strip whitespace or merge coordinates. Do not solve this by rendering untrusted strings as active HTML or Markdown.

Test actual Markdown-to-HTML output using leading, trailing, repeated and all-whitespace features; tabs/newlines; quotes; backslashes; vertical bars; angle brackets; ampersands; asterisks; and literal escape-looking text. Add focused unit cases and at least one full-report regression. Verify distinct source strings remain distinguishable and the displayed representation can recover the original feature string.

Preserve `--excerpts none`: it must continue omitting source-derived n-gram examples, not leak them through hidden attributes, hover labels, script data, or auxiliary HTML.

Keep source-content escaping, static/no-remote report behavior, input immutability, semantic list ordering, deterministic map ordering, JSON reload equivalence, and MD/HTML/SVG reconstruction checks passing. Update the appropriate template/release/fingerprint metadata transparently. Keep old release files and receipts historical.

Re-run the relevant reference-environment tests and the four original audit regressions after the patch. Provide the changed files, a short explanation, failing-before/passing-after label regression, and actual command logs. Do not relabel historical test runs as executions of the new source.

## Scope discipline

Do not start a broad rewrite. The zero-versus-zero stable-feature presentation and a short deterministic overview can remain a separate usability backlog. They are not reasons to change numerical methods during this patch.

After the report-label patch is verified, freeze the analytical baseline. The next substantial task is realistic, appropriately sourced local evaluation using the existing paired-text and account-stream interfaces, with explicit ground-truth limits, held-out separation, natural within-author variation, and selectively incomplete histories. Engineering test success does not change `real_world_validation: not_established` by itself.
