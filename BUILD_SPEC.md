# Account History Analysis Suite — V1 Build Specification

**Working package name:** `account_history_analyzer`  
**Working CLI name:** `ahas`  
**Specification version:** 1.0.0  
**Status:** Implementation plan, not an implemented or validated analyzer  
**Target:** Offline, reproducible analysis of one account's supplied text and activity history  
**Reference development environment:** Python 3.12 on Linux, CPU only

## Read this first

Build a measurement instrument, not a verdict machine. The program must analyze supplied account-history records, describe writing patterns and their changes, quantify content reuse and activity, and show the evidence behind every reported finding. It must run without a generative model, network connection, Reddit credentials, or proprietary API.

The current task ends at a working Python library, command-line interface, machine-readable results, deterministic Markdown report, and static local HTML report. **Do not build Reddit collection, a website, an account-search service, or a browser extension.** Integration and acquisition are separate future work.

This document is self-contained. Read it with `ACCEPTANCE_TESTS.md`, `AGENT_PROMPT.md`, the schemas, and the example configuration. Do not depend on an earlier chat. Research references are identified as [S1]–[S15] and described in `SOURCES.md`.

All numerical thresholds below are **engineering defaults or experiment settings**, not validated cutoffs between human and automated behavior. No research source establishes this complete proposed pipeline's accuracy on real accounts. Implementations of established methods, our adaptations of them, and new product-design choices must be distinguished in the method registry.

---

## 1. Product contract

### 1.1 Questions V1 must answer

1. What records were supplied, what can actually be analyzed, and what coverage limitations exist?
2. What measurable writing habits appear in the supplied text?
3. How similar or different are comparable bundles of writing, and which features account for those differences?
4. Where does a specified segmentation procedure identify changes in a sequence of writing-feature measurements?
5. Which texts are identical, contain the same normalized wording, or share substantial passages?
6. What activity, timing, link-host, and interaction-structure patterns are observable?
7. Do descriptive findings persist when we change predefined analytical settings or exclude potentially confounding material?
8. Can another user reproduce the results from the same snapshot and reference environment?

### 1.2 Explicit non-goals

No bot probability, human probability, AI percentage, deception score, account-sale verdict, identity attribution, cross-account identity linking, or assertion of an author's mental state. No inference of sensitive personal traits, nationality, political identity, medical conditions, sleep schedule, or real-world identity. No automated moderation or public accusations.

No AI-writing detector in V1. Reserve a clean future extension interface, but do not manufacture a detector from punctuation, sentence length, word lists, or supposed "AI phrases." The report must say `not_implemented_in_v1`, not `low_risk`, when describing that capability. RAID illustrates why a future detector needs its own challenging evaluation [S11].

No LLM-generated summaries, embeddings, pretrained language identification, part-of-speech parser, sentiment system, web search, scraping, or database server. Do not build speculative machine-learning infrastructure. No GPU dependency.

### 1.3 What completion means

V1 is complete as an **engineering release** when the required modules run on local inputs, the acceptance tests pass, outputs are reproducible in the reference environment, and the evaluation harness honestly reports available evidence and missing validation.

Engineering completion does not imply research validation. A correct analyzer can be released with `real_world_validation: not_established`. Missing real-world labels must not be replaced with labels invented by the implementation agent. Conversely, do not stop implementing arithmetic, software tests, or evaluation tooling simply because broader scientific validation is unfinished.

---

## 2. Deliverables and priorities

### Required V1 deliverables

- Installable typed Python package and documented CLI.
- Strict local JSON Lines ingestion and manifest validation.
- Explicit, versioned preprocessing and retained-text representations.
- Direct textual measurements and inspectable feature tables.
- Character n-gram, function-word, and masked-text comparisons.
- A tested Delta calculation that runs only when a valid frozen reference is supplied.
- Exact and shingle-based reuse analysis, with matching-text evidence.
- Activity, link-host, and limited interaction-structure analysis.
- Non-overlapping chronological writing windows, adjacent comparisons, and descriptive change-point analysis.
- Predefined sensitivity reruns, including repeat-reduced and known-edit-excluded views.
- Canonical results JSON, evidence exports, Markdown and local HTML reports.
- Unit, integration, security, reproducibility, property, and numerical-oracle tests.
- Offline synthetic-fixture evaluation and an external-data evaluation harness.
- Dependency lock, reference-container recipe, method registry, and limitations documentation.

### Required implementation order

Deliver vertical slices: ingestion → a small real analysis → report → numerical methods → temporal analysis → evaluation. Do not spend the first implementation phase polishing a dashboard. Do not write empty module skeletons and then claim the suite exists.

### Defer unless explicitly approved

Trained classifiers, automatic language detection, neural stylometry, formal significance tests, confidence intervals for authorship, FFT-based periodicity detection, topic modeling, semantic conversation analysis, generic CSV guessing, document export, large-scale cross-account search, ANN/MinHash optimization, and network integrations.

---

## 3. Architecture and repository

Use small, testable stages with immutable data objects at stage boundaries:

```text
Input files + snapshot manifest + explicit config
                  |
          strict validation
                  |
       canonical record snapshot
                  |
    raw views / retained prose / tokens
                  |
     per-record counts and feature vectors
                  |
  +---------------+---------------+----------------+
  |               |               |                |
reuse          activity        link hosts      interactions
  |
repeat-reduced eligibility mask
                  |
         chronological windows
                  |
     comparisons / segmentation / sensitivity
                  |
       evidence-backed finding objects
                  |
    canonical JSON → template reports
```

The dependency from reuse into repeat-reduced windows is intentional. Do not create a circular dependency in which the reuse algorithm depends on style conclusions.

Proposed repository:

```text
pyproject.toml
uv.lock                       # or one equivalent fully resolved lock
README.md
LICENSE                       # project owner's choice; audit dependencies
src/account_history_analyzer/
  cli.py
  config.py
  errors.py
  schemas.py
  io/{jsonl,manifest,canonical,artifacts}.py
  text/{markdown,segments,tokenize,views}.py
  features/{surface,function_words,chargrams,registry}.py
  analysis/{coverage,reuse,activity,links,interactions}.py
  style/{windows,distances,delta,compare,changepoints,sensitivity}.py
  findings/{models,rules,evidence}.py
  reporting/{json_export,markdown,html,charts,templates}.py
  evaluation/{fixtures,paired_text,account_stream,metrics}.py
  resources/                  # versioned lists and optional reference files
schemas/
config/
tests/{unit,numerical,integration,properties,security,reproducibility}/
fixtures/
docs/{METHODS,LIMITATIONS,EVALUATION,DECISIONS}.md
containers/Dockerfile
```

Prefer the standard library where adequate. Suitable dependencies to evaluate and pin include NumPy, SciPy, `markdown-it-py`, `ruptures`, Jinja2, JSON Schema validation, pytest, and Hypothesis. Matplotlib is acceptable for local charts. Do not add pandas, scikit-learn, PyTorch, or a web framework unless a concrete V1 requirement actually needs them. Check package compatibility before locking versions; this specification does not prescribe untested version combinations.

Use `dataclasses` or one consistent validation-model library. The JSON Schemas in the handoff define external contracts; internal models must agree with them. No database is required. Keep the computational library independent of the CLI and report templates.

---

## 4. Input data contract

### 4.1 Format and scope

Input consists of `records.jsonl` plus `snapshot.json`. Each nonempty JSONL line is one record conforming to `schemas/record.schema.json`. The manifest conforms to `schemas/snapshot.schema.json`. Support exactly this documented format in V1. A future collector can adapt Reddit responses to it.

Analyze one `account_id` per run. Reject mixed target-account IDs. Separate-account evaluation datasets consist of separate snapshots. IDs may be pseudonymous. Treat record contents and claimed provenance as supplied information, not verified facts.

### 4.2 Core fields

| Field | Meaning |
|---|---|
| `schema_version` | Literal `1.0.0`. |
| `id` | Stable, opaque, nonempty record ID; never used as a stylistic feature. |
| `account_id` | Must equal the manifest's account ID. |
| `kind` | `comment` or `submission`. |
| `text` | Body text, or null when unavailable. |
| `status` | `present`, `deleted`, `removed`, or `unavailable`. |
| `created_utc` | RFC3339 UTC timestamp ending in `Z`, or null. |
| `subreddit` | Supplied community label, or null. No network resolution. |
| `language` | Supplied language code, or null to inherit the manifest. |
| `edit_state` | `unknown`, `not_edited`, or `edited`. |
| `edited_utc` | Known last-edit timestamp, or null. |
| `title` | Submission title if supplied; analyzed separately from body. |
| `parent_id`, `thread_id` | Optional opaque IDs for local structural counts. |
| `parent_created_utc` | Optional supplied timestamp; not independently verified. |
| `permalink` | Optional source reference; never fetched. |

Canonical ingestion expands documented omitted optional fields to null/default values. Use a whitelist; unknown fields are errors rather than silently becoming features. Arbitrary extractor metadata belongs outside the record format in the extraction system, not in the statistical feature vector.

A `present` record must have a string `text`, including the possibility of an empty string. Other statuses must have null text. Treat a present string consisting only of `[deleted]` or `[removed]` as a sentinel: preserve it in the supplied snapshot, exclude it from text analysis, and issue a stable warning. It may still contribute a supplied timestamp to activity counts.

### 4.3 Manifest

The manifest records snapshot ID, account ID, source category, optional capture timestamp, text format (`plain` or `markdown`), declared default language, provenance note, and coverage declaration.

Coverage must allow `unknown`, `sampled`, or `complete_for_declared_scope`. Even the latter is a **supplier declaration**; do not advertise independent verification. Optional declared start/end and known missing intervals describe the collection, not the user's activity. Reject inverted intervals.

A hash proves correspondence with supplied bytes, not truthfulness, authorship, completeness, or authenticity of those bytes.

### 4.4 Validation and duplicates

Strict mode is mandatory and default. Invalid JSON, duplicate JSON object keys, NaN/Infinity, malformed timestamps, contradictory status/text fields, mixed accounts, and conflicting versions of the same ID are errors. Do not partially analyze a malformed file while displaying a successful full report.

Identical repeated records with the same ID are ingestion duplicates, not multiple posting events. Collapse them after canonical field expansion. Record their count in `ingest_receipt.json`, not in the canonical analytical result. Two different IDs with identical text remain two posting events and must be handled by the reuse module.

Sort records by `(timestamp_missing, created_epoch_microseconds, id)`. Use UTC-aware datetime parsing and integer microseconds; do not rely on binary-floating Unix timestamps or local system timezone [S12]. Missing-time records sort last by ID, are available to text/reuse analyses, and are excluded from chronological/activity analyses.

Known edits must not precede creation. A known edited timestamp requires `edit_state=edited`; `edited` with unknown edit time is allowed. Future-relative-to-now checks are forbidden because they would make results depend on execution date. Compare with a supplied capture timestamp only, if present.

### 4.5 Resource bounds

Initial configurable limits: 10,000 unique records, 200,000 Unicode code points per text, and 50 MiB input bytes. Exceeding them produces a clear pre-analysis limit error, not truncation. These are safety limits, not Reddit limits. Large pairwise-work budgets are separately controlled in Section 11.

---

## 5. Reproducibility contract

### 5.1 Canonical analytical outputs

With the same canonical supplied snapshot, expanded analysis configuration, code/resource versions, and reference numerical environment, `results.json` must be byte-identical.

It must not contain current time, wall-clock duration, hostname, absolute local paths, randomized IDs, raw-file line numbers, or nondeterministically ordered objects. Operational metadata belongs in `run_receipt.json`.

JSON serialization: UTF-8, sorted object keys, compact separators, no NaN/Infinity, one final newline. Arrays have an explicitly defined stable order. Integers remain integers. Finite floating results are serialized using the pinned Python encoder; normalize negative zero to positive zero. Preserve unrounded numerical results in canonical JSON; round only presentation text. Python exposes the relevant serialization controls [S13].

Do not claim universal byte identity across arbitrary operating systems or math-library builds. Require byte identity in the reference environment and test numerical agreement separately on other supported environments. If a platform moves a value across a decision threshold, disclose the mismatch; do not hide it through rounding.

### 5.2 Hashes

Keep separate:

- Raw input-file SHA-256: stored in the ingest receipt; changes with whitespace or row order.
- Canonical snapshot SHA-256: hashes expanded, deduplicated, chronologically sorted records plus analysis-relevant manifest content.
- Expanded-config SHA-256.
- Resource hashes: tokenizer/mask lists, feature registry, reference profiles, templates.
- Analysis implementation fingerprint: package version, source revision or source-tree digest, and reference-environment identifier.
- Results SHA-256: stored in a separate checksum file, avoiding self-referential hashes.

Changes in file names, input row order, or harmless JSON key order must not change analytical results. Changes in supplied text, included records, relevant provenance/coverage, configuration, or methods must be visible in the corresponding hashes.

For hashing, the expanded analytical configuration replaces local resource paths with content digests and stable method/resource identifiers. Keep the original path only in the operational receipt. The resolved configuration export must distinguish analytical resource identity from operational file location; moving an identical reference file cannot change analytical identity.

### 5.3 Deterministic computation

Use stable traversal of feature vocabularies and sparse-vector indices. Do not use Python's process-randomized `hash()` as a persistent feature or sampling identifier. Use sorted exact strings or a documented cryptographic digest. Fix parallel-reduction behavior in the reference environment; prefer one worker initially.

V1 production analysis needs no random sampling. Tests may generate data using explicit seeds. Any future randomized statistical procedure must record its PRNG/version/seed and is a new method version.

Reports are generated from results, not recomputed independently. The canonical numerical result is the reproducibility target. Markdown should also be byte-identical under the same template version. HTML and charts must be deterministic in the pinned rendering environment, but font/image encoding differences outside it do not invalidate identical canonical measurements.

### 5.4 Artifact privacy

Default reports may contain excerpts, IDs, and sensitive user-supplied prose. Clearly mark them as containing source text. Do not describe pseudonymized IDs or text hashes as anonymization. Support `--excerpts none` for render-time omission of prose excerpts, while warning that remaining data may still identify an account. This display setting must not alter analytical measurements.

---

## 6. Preprocessing: preserve evidence, separate views

### 6.1 Never overwrite original text

Maintain the original supplied string, its digest, and the sequence of transformations. Normalization is a derived view, not correction of the source.

Use NFC Unicode normalization and `CRLF/CR → LF` in analysis views. Do not apply NFKC, autocorrect spelling, smart-quote conversion, punctuation cleanup, sentence rewriting, or stemming. Normalization and parser versions are part of the method identity.

### 6.2 Markdown processing

For markdown input, use a pinned `markdown-it-py` CommonMark parser with typography replacement disabled. The parser exposes tokens and block maps [S14]. Do not assume Reddit's complete dialect is identical to CommonMark; document unsupported constructs rather than guessing their meaning.

Retained prose rules:

- Remove explicit blockquotes and their nested content from authored-prose views.
- Remove fenced code, indented code, inline code, image tokens, raw HTML blocks, and inline HTML tokens. Exclusion of HTML tags does not establish whether surrounding text is authored; retain ordinary text nodes and flag HTML presence.
- Retain ordinary text inside emphasis, headings, lists, and explicit descriptive link labels.
- Exclude link destinations from prose; record them separately. Exclude labels that are themselves just a URL.
- Recognize bare `http://` and `https://` URLs using a documented conservative scanner and exclude their spans from prose. Unknown formats remain text and are disclosed as a limitation.
- Do not remove text merely because it is enclosed in ordinary quotation marks. V1 cannot identify all copied or quoted material semantically.
- Strip display-only markdown delimiters while separately counting structural features such as list items and blockquotes.

For plain text, do not interpret `>` or backticks as markup. Only URL/handle span exclusions and documented lexical transformations apply. The explicit format flag matters and is hashed.

Remove syntactically recognized `u/name`, `/u/name`, `r/name`, and `/r/name` mentions from style views with a boundary marker; count them separately. Do not extract embedded real-world identities.

### 6.3 Segments and boundaries

Represent retained prose as ordered segments. A paragraph boundary or excluded span creates a hard analysis boundary. Formatting delimiters that merely surround retained text do not create new words or boundaries.

Never create character n-grams, word shingles, or phrase matches across records, paragraphs, or excluded spans. This prevents removal of code/quotes from manufacturing an apparent adjacent phrase.

Each segment records its text, source record ID, source field, and original source block/line range when available. Store normalized-segment offsets for exact feature evidence. **Do not label normalized offsets as raw-source offsets.** If exact source mapping is unavailable, cite the record and its original block rather than inventing a raw character location.

### 6.4 Tokenization

Use one pinned, explicitly tested lexical tokenizer. V1's specified Python regular expression is:

```python
r"(?u)[^\W\d_]+(?:['’][^\W\d_]+)*|\d+"
```

Classify all-digit matches as number tokens; other matches are word tokens. Hyphens split words. Internal straight/curly apostrophes are retained. This is an operational tokenizer, not a claim of perfect linguistic segmentation; document its behavior for unusual Unicode numerals and combining marks.

For case-insensitive lexical counts, apply `casefold()` and map internal `’` to `'`. Preserve the original case/apostrophe forms in surface features. Contractions remain one token: `don't` is not silently changed to `do not`.

Style eligibility uses word-token counts, excluding number tokens. Reuse token streams include both normalized word and number tokens. Do not remove function words from either stream.

### 6.5 Views to implement

Trim leading/trailing horizontal whitespace in retained segments and drop all-whitespace segments; retain internal line breaks. An explicit link destination is markup metadata, not a deleted visible-text span: keeping a descriptive link label does not split surrounding prose merely because a destination was omitted. A removed bare URL or inline code span does create a boundary.

1. `raw_source`: evidence only, not a mixed-content style representation.
2. `retained_prose`: case/punctuation preserved; horizontal whitespace runs normalized to a single space within segments; original structural counts stored separately.
3. `lexical_tokens`: casefolded words/numbers with apostrophe normalization.
4. `function_mask_v1`: retain tokens in the bundled fixed function-word list; for other word tokens replace each letter with `*` while retaining internal apostrophe positions; replace each number digit with `#`. Preserve separators and retained function-word case.

`function_mask_v1` is an explicit project adaptation motivated by text-distortion research [S2], not a claim to reproduce that paper's trained/frequency-selected configurations. The bundled curated function-word list is an engineering resource, not a validated authorship fingerprint. Hash it. Masking reduces some visible vocabulary information but does not make text provably topic-free.

### 6.6 Language and eligibility

Language comes from record/manifest metadata. If absent, use `und` and do not infer English from a Latin alphabet. English-specific function-word/masked comparisons require a declared `en` language. Unknown/other languages retain activity, link, reuse, and generic character counts, with appropriate limitations. Future language support needs separate resources and validation.

A record is eligible for primary style windows when it has present usable body text, a valid creation time, declared English, at least 20 retained word tokens, and the selected kind/community scope. This 20-word guard is a product default, not a scientifically sufficient sample size.

Known edited texts remain in the default observed-text analysis with a warning. Also calculate an unedited-only sensitivity view when enough data exists. Unknown edit history cannot be treated as proof of no editing.

---

## 7. Feature registry and direct measurements

Implement a machine-readable registry containing `feature_id`, description, view, formula, unit, numerator, denominator, missingness rule, evidence rule, version, and whether it is a direct measurement or derived comparison.

### 7.1 Required per-record counts

Count retained words, number tokens, code points, cased letters, uppercase letters, paragraphs/segments, retained word-character total, literal punctuation characters, removed quote/code/URL spans, headings, list items, links, and mentions.

For punctuation, keep separate counts for comma, period, question mark, exclamation mark, semicolon, colon, ASCII apostrophe, curly apostrophe, ASCII double quote, left/right curly double quotes, ASCII hyphen, en dash, em dash, and U+2026 ellipsis. Also count **runs** of three or more ASCII periods as a separate feature. That run feature intentionally overlaps the literal-period count; never add them as though they were disjoint.

Use `str.isupper()` / `str.islower()` to identify cased code points. Uppercase fraction is `uppercase / (uppercase + lowercase)`, null if there are no cased letters. This measures case use, not emotional intensity.

Count exact standalone `i` and `I` word tokens for an English pronoun-case descriptor. Do not label every such occurrence a verified pronoun.

### 7.2 Rates and summaries

Use pooled counts when aggregating windows: total numerator divided by total denominator. Do not average comment-level rates unless the output explicitly says `record_weighted_mean`.

Provide literal counts plus punctuation-per-1,000-words, punctuation-per-1,000-retained-code-points, average word length, words-per-record distribution, and uppercase fraction. For word length, count Unicode alphabetic code points within word tokens, excluding apostrophes.

Medians/quantiles use a documented fixed definition: NumPy `quantile(method="linear")`, equivalent to interpolation at `(n-1)q`. Keep raw sample sizes. Empty denominator → null plus reason, never zero/NaN.

Sentence-length and readability scores are not required. The absence of a trusted sentence segmenter is not a reason to approximate grammatical sentences with periods and call the result exact. A later rule-based sentence module must be separately named and tested.

### 7.3 Function words and contractions

Count each entry in `resources/function_words_en_v1.txt` per 1,000 word tokens. Export counts and pooled frequencies.

Also count the exact pairs in `resources/contraction_pairs.json`. Detect expanded multi-token forms only within segments, case-insensitively, with exact token adjacency. A contracted occurrence and an expanded occurrence form the denominator for a literal preference fraction. Report counts even when zero; display a preference fraction as `insufficient_opportunities` until the denominator reaches 10, while retaining the raw arithmetic fraction in the evidence object if nonzero.

Do not disambiguate `it's`, `I'd`, etc. semantically; ambiguous expansions are excluded from the bundled list. These are matched string alternatives, not proof they were interchangeable in context. Function-word methods have an established authorship-analysis literature, but individual features are not identity proofs [S3].

---

## 8. Style representations and distances

### 8.1 Character n-grams

Count overlapping character sequences of length 3, 4, and 5, separately for each `n` and each view (`retained_prose`, `function_mask_v1`). Use Unicode code points, case-sensitive, within segments only. No start/end padding. Keep exact strings and integer counts.

For each length/view, compute cosine distance between pooled count vectors:

```text
d_cos(x,y) = 1 - dot(x,y)/(norm(x)*norm(y))
```

Align coordinates using the sorted union of observed n-grams. Zero-norm vectors produce `not_computable`; empty texts must not produce a perfect match. Clamp only mathematically impossible numerical excursions smaller than the documented tolerance; do not erase meaningful small distances. Test against hand examples and an independent SciPy calculation [S7].

Character n-grams are an established stylometric feature family [S1]. V1 is not reproducing every affix/punctuation subgroup from that research. Do not claim its published classification accuracy transfers to our unsupervised distances.

Keep 3-, 4-, and 5-gram distances separate. They are correlated views, not three independent witnesses. Do not average all methods into a mystery score.

### 8.2 Function-word distribution distance

Construct a probability vector containing the fixed function-word categories plus an `OTHER_WORD` category. The denominator is all retained word tokens. A word belongs to exactly one category. Including the residual preserves changes in the total proportion of function words.

Compute Jensen–Shannon **distance**, not divergence, using logarithm base 2:

```text
m = (p+q)/2
JSD = 0.5 * sum(p_i*log2(p_i/m_i)) + 0.5 * sum(q_i*log2(q_i/m_i))
d_JS = sqrt(JSD)
```

Use `0*log(0/...) = 0`. Empty sample → not computable. SciPy's `jensenshannon(..., base=2)` returns the square-root distance [S8]. Verify disjoint singleton distributions give 1 and identical distributions give 0. No smoothing is necessary for this metric; do not add undocumented pseudocounts.

### 8.3 Delta with a frozen reference

Implement the classic mean absolute standardized-frequency difference:

```text
z_Aj = (f_Aj - mu_j)/sigma_j
z_Bj = (f_Bj - mu_j)/sigma_j
Delta(A,B) = mean_j(abs(z_Aj - z_Bj))
```

For an imported reference, require method/resource version, ordered vocabulary, frequency unit, reference mean, reference standard deviation, fitting description, and training-corpus provenance. This file must pass `schemas/delta_reference.schema.json`.

The bundled `design_examples/delta_reference_toy.json` exists only to test arithmetic. A runtime guard must prevent it from being used for real-account interpretation without an explicit `--allow-toy-reference` test flag, which prominently marks outputs `toy_reference`.

Zero or near-zero reference variance (`sigma <= 1e-12` in the specified unit) means the coordinate is excluded and counted. No valid coordinates → not computable. The unit of `f`, `mu`, and `sigma` must agree. Never divide by a magically substituted standard deviation of 1.

Without a valid reference, return `not_run_missing_reference`. Do not fit a reference secretly from the two compared texts. V1 does not need to acquire or train a reference corpus. A future reference-building utility must define sample size, balance, and leakage controls. `stylo` documents reference implementations and Delta variants; do not silently substitute a cosine variant [S4].

### 8.4 Contributions and interpretation

For function-word JS, show per-category nonnegative divergence contributions (before square root), plus absolute rate changes. For Delta, show `abs(z_Aj-z_Bj)` contributions. For character cosine, show n-grams with the greatest absolute normalized-frequency differences and label this **feature difference**, not an exact causal decomposition of cosine distance.

Sort explanations by descending unrounded value, then feature ID. Select at most 10 in the human-facing view, retain all in exports where within resource budgets.

Always identify comparison scope, representation, word counts, record counts, and confounds. Do not convert distance to "percent different author" or "percent similar style." A distance of zero establishes identity of that representation, not identical wording or authorship.

---

## 9. Bundling text and comparisons over time

### 9.1 Primary windows

Build separate streams for comments and submission bodies. Titles are not concatenated into bodies. For each stream, sort eligible records chronologically and accumulate **whole records** until both conditions hold: at least 1,000 retained word tokens and at least 8 records. Close that window and start the next.

Windows are non-overlapping. Do not split or truncate comments, duplicate text to pad a window, or bridge into another content kind. The word budget is a target, not exact equality. Record actual word count and the largest single-record share. Flag share > 0.50 as `single_record_dominance` rather than pretending eight records guarantee independent evidence.

Retain a final short window as a visible remainder in coverage. Exclude it from primary segmentation; report its actual size and why. Do not silently discard it from all text summaries.

A 1,000-word window is an engineering choice to evaluate. It does not establish statistical sufficiency or accuracy. Evaluate 500/1,000/2,000-word settings rather than declaring a universal threshold.

### 9.2 Context controls

Produce a pooled stream and separately qualified within-subreddit streams. Choose up to 10 communities by descending eligible word volume, ties by community label. Record omitted communities. Null community is its own unknown scope, not silently merged into every subreddit.

Compare different kinds/languages separately. Changes in community mix, record lengths, or missingness must be reported beside pooled writing changes. Same subreddit is only a partial context control, not verified same topic.

Do not run an unbounded Cartesian product of every community, length bin, and parameter combination. Required comparisons are adjacent qualified windows, manual user-specified slices, and the predefined sensitivity cases below. All-pair heatmaps are optional and limited to at most 100 windows; no silently truncated "all pair" claim.

### 9.3 Manual comparison API

A selector contains an inclusive start timestamp, exclusive end timestamp, optional explicit IDs, optional kind, and optional subreddit. It selects only from the supplied snapshot. Time filters omit missing-time records; an ID selector may include them for pooled text comparison.

Refuse overlapping left/right IDs by default. An explicit `allow_overlap` setting may permit a diagnostic comparison but labels it dependent. Apply the same preprocessing and representation parameters to both sides.

Return raw measurements at any size, but qualified style-comparison findings require at least 8 eligible records and 1,000 words per side by default. Show `insufficient_comparable_text` otherwise; do not invent an author score. Direct numerical functions may still be tested on tiny vectors outside that product gate.

### 9.4 Timeline semantics

Call the timeline **observed text ordered by record creation time**. With only one snapshot, the text of an edited comment is not proven to be the wording present at creation. A finding locates a boundary between observed windows, not an exact takeover date.

Each boundary records the last eligible record of the left window and first eligible record of the right window, their timestamps, and both windows' full ranges. Gaps in supplied data widen uncertainty about timing; never interpolate a specific event into a missing interval.

---

## 10. Change-point detection and sensitivity

### 10.1 Core approach

Use penalized L2 segmentation on a small explicitly defined vector per qualified window. PELT is an established optimization method for penalized segmentation [S5]; its `ruptures` implementation exposes `min_size` and `jump` [S6]. The use of that method does **not** supply a hypothesis test for a changed author.

V1 segmentation vector has two families:

- `surface`: rates per 1,000 words of comma, period, question mark, exclamation mark, semicolon, colon, straight apostrophe, curly apostrophe, em dash, and ellipsis character; plus uppercase fraction and average word length.
- `function`: individual fixed function-word frequencies per 1,000 words, excluding `OTHER_WORD` to avoid adding a completely dependent residual coordinate.

Do not include text IDs, community labels, URLs, user handles, supplied truth labels, future windows' labels, or raw topical vocabulary in this segmentation vector.

### 10.2 Scaling

For one complete stream of N windows, compute mean and population standard deviation (`ddof=0`) of each selected feature across those N windows. Exclude any feature missing in any window, or having standard deviation <= 1e-12 in its registered unit. Log every excluded feature. Do not impute zero for missing rates.

Standardize each retained feature to z-scores. Within each family divide coordinates by `sqrt(number_of_retained_features_in_family)`; then divide all coordinates by `sqrt(number_of_nonempty_families)`. This is a proposed family-weighting convention, not a learned probability model. It avoids automatic dominance just because one family has many coordinates.

Persist scaling parameters and retained feature order. This account-local scaling is for descriptive segmentation of the supplied series. Adding new history can legitimately alter it and the resulting boundaries. Do not call it a frozen authorship baseline.

### 10.3 Objective and parameters

Minimize:

```text
sum_over_segments sum_{i in segment} ||z_i - mean(z_segment)||^2
    + beta * number_of_internal_change_points
```

Use `model="l2"`, `min_size=3`, `jump=1`, `beta=lambda*ln(N)` with primary lambda 1.0 and predefined sensitivity lambdas 0.5, 2.0, and 4.0. Minimum N=8 qualified windows. If no nonconstant dimensions remain, return `no_measurable_variation`, not an exception.

These penalty settings are **uncalibrated experimental defaults**. Do not label boundaries statistically significant. Save the objective definition, penalty, exact window indices, and total objective. Exclude the terminal endpoint N from the list of detected changes; many libraries return it as part of the partition format.

Test optimization against a simple exhaustive/dynamic-programming oracle for small series. Equal-cost solutions are equally optimal; do not claim a universal library tie order. Pin the production implementation and test its determinism. Where the test requires a specific boundary, use a unique-optimum fixture.

### 10.4 Sensitivity outputs

Required reruns, subject to enough text:

1. The four fixed penalty settings on the same windows.
2. 500- and 2,000-word window targets, retaining the record-count guard.
3. Within-community streams that qualify.
4. Exclusion of known-edited records.
5. Repeat-reduced text view described in Section 11.

For same-window penalty comparisons, match boundaries within ±1 window using one-to-one maximum matching, ties resolved by smallest total boundary displacement, then lexicographic pairs. Report `matched_in_k_of_m_executed_settings`; this is parameter stability, not a confidence probability.

For different window constructions, do **not** match indices. Compare the record-order boundary intervals; report overlap or explicit separation in retained record positions/time. A point-count percentage across unrelated windows is misleading.

Also display raw/masked n-gram and function-word distances around candidate boundaries. Agreement between related measurements is descriptive corroboration, not multiplication of independent evidence.

No p-values, significance stars, authorship confidence intervals, or benchmark-calibrated alerts belong in V1 until a separate registered validation/calibration design is implemented.

---

## 11. Content reuse: exact, near, and contained text

### 11.1 Separate match types

Implement three distinct notions:

- `raw_text_identical`: exact original strings, on different record IDs.
- `normalized_prose_identical`: retained prose segment sequences match after the specified whitespace normalization; case and punctuation are preserved.
- `token_sequence_identical`: sequences of normalized lexical tokens and segment boundaries match. Punctuation/case differences may remain in the source and must be mentioned.

Do not call all three byte-identical copies. Empty text or removed-content sentinels never form meaningful duplicate clusters. Exact short phrases may be counted but receive `short_common_text` and are excluded from headline substantial-reuse findings below 20 word tokens.

### 11.2 Shingles and formulas

Construct sets of consecutive 5-token tuples within each retained segment, including number tokens and function words. No cross-boundary shingles. For sets A and B:

```text
Jaccard(A,B) = |A intersect B| / |A union B|
Containment(A in B) = |A intersect B| / |A|
```

Keep directed containment both ways. Empty sets return `not_computable`. Sets, not bags, are the specified default, so repetitions of one shingle do not inflate its count. These document-resemblance measures have an established foundation [S9].

Default near-duplicate edge: both records contain at least 20 retained word tokens and Jaccard >= 0.80. Default containment finding: shorter record has at least 50 retained words and containment >= 0.90. Thresholds identify matches under these rules, not copying intent or automation.

For exact threshold decisions, use integer cross-multiplication against configured rational thresholds (e.g., intersection*100 >= union*80), avoiding floating-point boundary ambiguity.

### 11.3 Evidence and grouping

For each qualifying pair save token counts, shingle counts, intersection/union counts, both directed containment fractions, normalized matching passages, and source IDs. Distinguish "shared 5-token shingles" from one long contiguous shared passage. Only claim an N-token contiguous match after reconstructing that actual contiguous sequence within both segments.

Connected components in a similarity graph are **connected reuse groups**, not pairwise-equivalent clusters. A≈B and B≈C does not guarantee A≈C. Export pair edges and display this qualification.

For the repeat-reduced sensitivity view, first retain only the earliest member of each `normalized_prose_identical` group. Then optionally apply the explicitly configured greedy representative method to near-duplicate records: process chronological records; discard a record only if it meets the Jaccard threshold against an already retained representative; choose highest similarity, tie earliest representative. Record every excluded→representative relationship. This is content deweighting, not identification of unoriginal authors.

The default sensitivity uses normalized-prose exact deweighting. Near-deweighting is a separate labeled optional sensitivity because it can remove genuinely relevant changed wording. Neither changes activity counts or the original primary style analysis.

### 11.4 Performance and completeness

Implement an exact inverted index of shingle→record IDs or a brute-force oracle for small fixtures. An exact index can skip pairs sharing no shingles without approximation. Preserve full string/tuple equality; hashes may accelerate lookup but must not replace collision verification.

Default candidate-pair limit: 2,000,000. Check the budget deterministically. If near-reuse work exceeds the budget, retain exact-duplicate results and mark the near-reuse module `resource_limit`; do not present partial pair findings as a complete search. Do not silently sample, remove high-frequency shingles, cap histories, or switch to approximate matching.

---

## 12. Activity and interaction measurements

### 12.1 Activity scope

Use all distinct supplied target-account events with valid creation timestamps, including deleted/removed records when their timestamps were supplied. Say **observed supplied events**, not the account's complete history. Style exclusions do not erase activity events.

Required outputs: event count; earliest/latest supplied timestamp; observed span; events per UTC day and hour; weekday counts; distinct event-bearing days; zero-event days **in the supplied range**; inter-event gaps; gap quantiles; simultaneous-timestamp groups; maximum events in a sliding 30-second, 120-second, and 3,600-second inclusive window.

A gap does not establish sleep, a break, or a lack of deleted/uncollected activity. Hourly charts aggregate event counts over dates; activity in all 24 bins does not establish any day of uninterrupted use.

### 12.2 Exact definitions

Intervals are integer microsecond differences between chronologically adjacent events. Simultaneous events have zero gaps and are retained. Do not infer their true sub-resolution order.

For interval variability use population standard deviation / mean, with null when there are fewer than two intervals or mean=0. Display interval count and units. This is descriptive variation, not an automation test.

UTC calendar bins include all calendar dates from the earliest to latest event inclusively. Flag first/last dates as edge days and all known coverage gaps; zero bins mean no supplied events, not verified inactivity. Aggregate days per weekday and supplied events per weekday so unequal exposure is visible.

### 12.3 Burst rule

Provide an explicitly named `greedy_nonoverlapping_fixed_window_bursts` measurement, default duration 30 seconds and minimum 3 events:

```text
i = 0
while i < N:
    j = greatest index with t[j] - t[i] <= duration
    if j-i+1 >= minimum_events:
        emit events[i:j+1]
        i = j+1
    else:
        i += 1
```

Do not describe this as the only possible definition of a burst. It differs from gap-connected sessions and from overlapping sliding-window counts. Include the actual event IDs so the calculation can be checked.

### 12.4 Interaction structure

Count target-account replies per supplied thread, repeat participation in threads, and transitions across supplied community labels. Resolve parent links only within the supplied data. Missing parents mean missing context, not evasion.

Where both timestamps are supplied, calculate `creation_to_parent_creation_seconds`; explicitly state it is **not typing time or read-to-reply time**. Negative differences are validation warnings/errors according to whether the parent is an internal contradictory record or unverified external metadata. Detect cycles in supplied parent references and do not recurse forever.

Do not score relevance, empathy, intent, contradiction, or whether an author "understood" a discussion.

---

## 13. Links and observable distribution changes

Extract explicit link destinations and recognized bare HTTP(S) URLs from source text, without fetching. Deduplicate the same detected occurrence if both a parser token and bare-URL scan refer to it.

Normalize hostname by URL parsing, lowercase, IDNA conversion where supported by the pinned implementation, and removal of a final DNS dot. Keep `www.example.test` distinct from `example.test` unless a future explicit equivalence rule says otherwise. Do not confuse hostname with registrable domain: public-suffix grouping is out of scope, and there must be no automatic list download.

Reject unsafe/non-HTTP(S) links for clickable rendering. Count malformed links separately. Ignore URL userinfo for display and never expose it in a clickable URL. Source URLs are untrusted inputs; do not send HTTP requests or resolve DNS.

Report total link occurrences, distinct linked hosts, number/share of records linking each host, hosts per time window, and community distribution. Distinguish percentage of links from percentage of records containing links. A record linking the same host three times contributes three occurrences but one record-with-host count.

Do not label repeated links advertisements, shilling, sponsorship, or payment. No product-name recognition is required in V1. The report can say, for example, "18 of 40 supplied records include a link to this hostname."

---

## 14. Findings and evidence model

Each finding must be a structured object conforming to the results schema's finding contract:

```text
finding_id              stable digest-derived identifier
finding_type            e.g. normalized_text_reuse, style_boundary_candidate
epistemic_level         measurement | derived_comparison
status                  observed | candidate | insufficient_data | not_run
scope                   selected records/windows, kind, language, community
method_id/version       fully qualified registry key
parameters              or a stable config reference
values                  named units and counts, never an unexplained score
source_record_ids       existing supplied IDs only
window_ids              existing calculated window IDs only
evidence_refs           actual evidence objects, not prose guesses
limitations             stable reason codes rendered with templates
related_finding_ids     non-causal cross-references
```

No `suspicious`, `bot`, `human`, `likely_author`, or sensitive-trait label fields. Do not hide such labels in severity enums. Module status can be `ok`, `insufficient_data`, `not_run`, `resource_limit`, or `error`.

Feature-comparison findings must provide sample sizes and opposing evidence. A boundary report should show both the largest-changing features and selected stable features, using fixed sorting. Do not claim a hand-picked example represents the entire period.

For each selected feature choose at most two examples per side by the registered evidence rule: highest qualifying per-record rate with at least the configured denominator, then chronological/ID tie order. Show source context rather than inventing a sentence that demonstrates the feature. Also include a deterministic ordinary-context example (e.g., record nearest the window's median length), labeled as context rather than evidence of the feature.

A coincidence between a style boundary and increased posting is a cross-reference with observed dates, not a causal account-takeover narrative. No automatic addition of correlated signals into a combined risk score.

---

## 15. Output artifacts and reports

### 15.1 Required outputs

```text
results.json              canonical analysis and module summaries
records_features.jsonl    sorted per-record measurements
windows.jsonl             membership and feature summaries
evidence.jsonl            source-linked finding evidence
report.md                 deterministic template narrative
report.html               static, local, readable report
checksums.json            hashes of analytical artifacts
resolved_config.json      full expanded configuration
ingest_receipt.json       raw-file details and validation/duplicate counts
run_receipt.json          wall-clock runtime and actual execution environment
```

Module-specific large pair tables may live in additional JSONL files with hashes referenced from results. No silent truncation. A report page can show a top-N preview as long as the complete computed artifact and truncation count are available.

`schemas/results.schema.json` fixes the top-level contract and the finding envelope. Before completing the relevant module, the agent must add strict module-payload schemas and schema tests. The supplied generic payload slots are **extension points**, not permission to make outputs inconsistent or untyped.

### 15.2 Report order

Start with a neutral title and coverage/limitations. Then show direct text and activity summaries, reuse evidence, style-window comparisons, candidate changes and sensitivity, link/interaction summaries, methods/parameters, and reproducibility information.

Every metric label explains its denominator, unit, and observation scope. Show UTC explicitly. Show `not run`, `insufficient text`, and `missing reference` as normal outcomes. Never transform missing results into green "passed" checks.

Use plain-language fixed templates, for example:

> Under the 1,000-word-window configuration, the segmentation method identifies a candidate boundary between windows 7 and 8. This describes a change in measured writing features; it does not identify its cause or establish a change of author.

> The raw 4-gram distance was X and the masked 4-gram distance was Y. These are different representations and not directly interchangeable probability scales.

Don't call Y "lower suspicion" merely because it is numerically smaller; cross-representation distance distributions can differ.

### 15.3 Visualizations

Use simple local charts: supplied event counts by date, a UTC hourly histogram, eligible word volume, selected feature trajectories, adjacent distance trajectories, and segmentation boundaries where computable. Generate charts from exported data only. Charts should remain legible for sparse samples, display missing values as missing, and not interpolate across missing data without a visible convention.

Use no remote assets, tracking pixels, external fonts, CDNs, or JavaScript dependencies. Matplotlib-generated SVG/PNG is sufficient. Chart metadata/IDs must be stabilized for reproducible renders. HTML uses local CSS and native disclosure elements; JavaScript is not required.

### 15.4 Security

Never render raw input as trusted HTML or executable Markdown. Escape all source strings in HTML. Raw `<script>`, malicious URLs, `</script>`, HTML entities, and markdown links must not execute code. Do not execute shell commands composed from IDs or load Python pickles supplied as data.

Resolve file output paths safely. Never use a record ID directly as a filesystem path. Prevent path traversal. Default to refusing output into a nonempty directory unless explicit overwrite is requested. Write artifacts atomically so interruption cannot leave a valid-looking partial report. No telemetry or runtime network access.

---

## 16. CLI and library API

Required command behavior:

```bash
ahas validate --input records.jsonl --manifest snapshot.json
ahas analyze --input records.jsonl --manifest snapshot.json \
  --config config/default.toml --out output/
ahas compare --input records.jsonl --manifest snapshot.json \
  --selection comparison.json --config config/default.toml --out comparison/
ahas render --results output/results.json --artifacts output/ \
  --format html --excerpts none --out rendered/
ahas verify --input records.jsonl --manifest snapshot.json --analysis-dir output/
ahas evaluate --suite synthetic --fixtures fixtures/ --out evaluation/
```

`verify` checks hashes and, when invoked with `--recompute`, reruns the analysis in the available environment and compares canonical results. Without recomputation it must say `integrity_only`, not `reproduced`.

External-data evaluation commands may be added in the evaluation milestone, but must consume local files and refuse absent datasets rather than auto-download them.

Library sketch:

```python
snapshot = load_snapshot(records_path, manifest_path)
config = AnalysisConfig.from_toml(config_path)
result = analyze(snapshot, config)
write_artifacts(result, output_dir)
```

Public functions have type hints, documented return/missingness behavior, and stable exceptions. No function should assume a current working directory or silently mutate supplied records.

Exit codes: 0 successful analysis/validation (including normal insufficient-data modules), 2 input/configuration errors, 3 unexpected computation failure, 4 explicit resource-limit/incomplete requested analysis, 5 failed integrity/reproduction check. If a resource-limited report is written, label it partial and return 4. Logs go to stderr; machine-readable stdout is clean when requested.

---

## 17. Evaluation: do not confuse demonstration with validation

### 17.1 Three distinct evidence levels

**Numerical correctness:** hand-checkable fixtures prove formulas, sorting, normalization, and decisions are implemented as specified.

**Synthetic signal tests:** controlled constructed texts/timestamps test whether the pipeline reacts to deliberately changed measured features and survives nuisance transformations. They do not measure accuracy on humans, bots, AI text, or real account takeovers.

**External validity:** independently labeled, appropriately sourced text is needed to estimate real performance. Report this separately and do not claim it when only the first two levels exist.

### 17.2 Required synthetic scenarios

Build/use the supplied deterministic fixtures for stable constructed style, deliberately changed punctuation/case, vocabulary-only changes under a shared template, repeated passages, activity bursts, short-data abstention, missing/edited/removed content, and hostile markup.

The provided generated texts are overtly synthetic, formulaic, and not representative Reddit conversations. They are software test inputs, not a training corpus or an accuracy benchmark. Ground-truth sidecars describe construction operations only.

Truth files must be read by the evaluator, never by the analyzer. Changing a truth label must not change `results.json`. Do not place known change boundaries or scenario names into analysis features or tune rules to fixture IDs.

### 17.3 External evaluation harness

Support two local formats:

- `paired_text`: labeled same-author/different-author pairs, with text IDs and grouping metadata. Evaluate distances as rankings and, only for development-selected thresholds, decisions.
- `account_stream`: complete supplied chronological streams with provenance and known/annotated changes where justified. Evaluate the whole search procedure, not only preselected easy pairs.

Keep authors, threads, source documents, near-duplicate clusters, and related constructed samples separated across development and evaluation whenever available. If grouping metadata is absent, state that author/thread leakage was not auditable; do not assert disjointness you cannot verify. Preprocessing, reference fitting, vocabulary choices, and thresholds must not learn from held-out evaluation labels [S10].

Metrics: sample coverage/abstention; pair-distance ROC-AUC where both labels exist; average precision with the positive class named; confusion counts at frozen thresholds; false-positive rate; recall; and, for streams, false candidate boundaries per unchanged stream, boundary precision/recall with a preregistered tolerance, and boundary-location error. Always expose denominators and label definitions. Do not invent 95% accuracy acceptance targets.

For correlated pairs, do not manufacture uncertainty intervals by treating every pair as independent. V1 can report descriptive metrics without confidence intervals; any later interval must use an appropriate grouped design.

### 17.4 PAN: useful but not interchangeable

PAN 2025's multi-author task uses Reddit-derived texts and sentence-level author-change labels, including same-topic hard cases [S15]. It is a useful later external stress test for style features. It is **not** a labeled chronological account-history dataset and not bot/AI ground truth.

Do not manufacture real timestamps or thread membership for PAN examples. A dedicated adapter must preserve the released units and available labels, state any limitations, and evaluate sentence/document tasks separately. Use the official scoring definition if claiming a PAN-comparable score. Do not require access to hidden test labels or assume every listed split has public truth.

V1's 1,000-word account-window guard cannot be silently relaxed to get a PAN score and then advertised as the same method. Any short-text experiment is a separate named configuration with its own coverage and evaluation.

### 17.5 Release documentation

`EVALUATION.md` must include commands actually run, dataset/fixture hashes, real results, failures, and untested assumptions. It should contain an explicit statement of what is and is not validated. Never make up benchmark numbers or report an unrun test as passed.

---

## 18. Milestones and gates

### M0 — Contracts and executable skeleton

Create package, strict schemas, config loading, canonical I/O, method registry, and CLI validation. Add arithmetic fixture tests. Gate: malformed records fail clearly; identical input reordered produces identical canonical snapshot hashes; no runtime network calls.

### M1 — First end-to-end report

Implement coverage, retained text, tokenization, direct counts, activity basics, JSON results, and a minimal Markdown report. Gate: supplied arithmetic fixture produces the expected timestamps, duplicates-at-ingestion behavior, and exact counts; empty/short histories produce informative nonverdict reports.

### M2 — Reuse and evidence

Implement exact match types, exact shingle comparisons, directed containment, deterministic pairs/groups, and source evidence. Gate: numerical oracles pass; quote/code-only matches are excluded from retained-prose reuse; connected groups do not falsely claim pairwise equivalence; resource limits are explicit.

### M3 — Stylometric comparisons

Implement n-gram representations, JS, Delta with reference validation, window construction, and manual comparisons. Gate: independent numerical tests pass; empty denominators abstain; no n-grams cross records or excluded spans; context/sample sizes accompany every distance.

### M4 — Temporal candidates and sensitivity

Implement the specified standardized family vector, PELT, oracle checks, boundary mapping, and required sensitivity reruns. Gate: no-change and unique-optimum numerical sequences behave correctly; minimum samples are enforced; sensitivity is not labeled probability; edited text limitations remain visible.

### M5 — Complete reporting, links, and structure

Implement static HTML, charts, evidence inspection, link-host summaries, limited thread structure, privacy display options, and artifact verification. Gate: malicious markup cannot execute, no report asset accesses the network, charts correspond to JSON, and references resolve to actual supplied IDs.

### M6 — Evaluation and release hardening

Implement local paired/stream evaluation, run synthetic tests and reproducibility tests, profile performance, document real-world validation status, freeze dependencies, and create reference container. Gate: all required engineering tests pass; all unvalidated claims are labeled; no fabricated accuracy or unrun-test claims; final handoff includes commands, results, and remaining research limitations.

Do not proceed with a known failure of an earlier correctness gate merely to produce screenshots. Record genuine method/design ambiguities in `DECISIONS.md` and choose the simplest scope-preserving resolution. Scientific calibration questions may remain open; software contracts may not remain contradictory.

---

## 19. Performance targets and failure behavior

Initial engineering target: analyze a normal 1,000-record, at-most-500,000-retained-word snapshot on a CPU laptop without a GPU and with peak process memory below 2 GiB. Aim for under two minutes on the documented reference machine; these are goals to measure, not preclaimed benchmarks. Record hardware and timing in the operational receipt.

Avoid dense record×record×vocabulary tensors. Use counters/sparse structures for n-grams, streaming per-record feature extraction, and window-level rather than universal pairwise style comparisons. Large connected reuse groups should be represented by edges and membership rather than duplicated prose.

Timing/memory results must be measured on specified fixtures. If targets fail, profile and optimize without silently weakening accuracy, changing preprocessing, sampling evidence, or disabling expensive modules. An optimization that changes the result is a new method/configuration, not a free implementation detail.

Exception handling must distinguish bad inputs, missing data, resource exhaustion, and programmer errors. Insufficient text is not an exception. Never swallow an analysis exception and substitute a reassuring report value.

---

## 20. Final agent handoff requirements

At completion, provide:

1. Working source repository/archive with dependencies locked.
2. Exact setup, test, and sample-analysis commands.
3. A generated example report and canonical output from the shipped fixtures.
4. An actual test summary, including any skipped tests and why.
5. A method registry identifying literature-backed primitives versus project adaptations/defaults.
6. Measured performance and reproduction results in the reference environment.
7. An honest scientific-validation statement and specific unresolved limitations.

Do not ask the user for Reddit API keys, a live account, a hosting platform, or a generative-model choice. Those are intentionally unnecessary for this version. The next integration can simply turn extracted records into the specified input format once the analysis suite works.

**Final product principle:** every important sentence in the report must be traceable to an explicit calculation, a supplied source record, or a clearly labeled limitation. The report should remain useful even when it cannot say why a pattern occurred.
