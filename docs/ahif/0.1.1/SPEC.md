# Account History Interchange Format (AHIF)
## Draft 0.1.1 — a platform-neutral evidence format for AHAS

**Status:** locally adopted repository evidence contract, reviewed draft 0.1.1. It is not an Internet standard or an AHAS engine release. Reviewed 2026-09-15. This revision supersedes 0.1.0 for new local format work; the original package and receipts remain unchanged under `../history/0.1.0/`. This package defines the destination format. It does not implement website collection, source-specific extraction, database merging, or conversion into the production analyzer.

**Compatibility reference:** the actual local `schemas/record.schema.json`, `schemas/snapshot.schema.json`, their installed package copies, and `src/account_history_analyzer/io.py` were inspected. AHAS remains 1.0.4; its input schemas still declare `schema_version: "1.0.0"`. AHIF uses `format_version: "0.1.1"`. See `checks/frozen-boundary.json` for local hashes. The workspace exposes no readable Git metadata, so no local commit identity is asserted. The original proposal's upstream commit reference is historical.

The normative contract consists of this specification, `FIELDS.md`, the four versioned schemas, and the semantic rules implemented and enumerated here. `CHANGES.md` records each revision and rationale; `AHAS_COMPATIBILITY.md` defines a future bridge, not an implemented capability. The decisions below apply only to 0.1.1. Existing AHAS constraints are identified in `AHAS_COMPATIBILITY.md`; they are not silently changed by this format.

## 1. Purpose and scope

AHIF is a common representation of supplied online contributions and the evidence about them. A Reddit export, an X export, an unfamiliar forum page, or a research corpus can eventually be converted into it. Once that conversion has been tested, downstream components need not understand every source's original file layout.

The intended pipeline is:

```text
Original files or permitted observations
        -> source-specific normalizer (later)
        -> AHIF evidence bundle (this specification)
        -> explicit selection/projection for an analyzer (later)
        -> existing AHAS input contract
        -> unchanged measurements and reports
```

The common format preserves distinctions the current analyzer cannot yet represent. It MUST NOT silently flatten those distinctions just to fit the current analyzer. In particular, a valid AHIF observation may have too little text, an unknown author, no precise posting time, or an unsupported markup format. **Format validity is not analytical eligibility.**

Core scope is text-bearing contributions and public-action observations with no supplied text, including posts, replies, repost actions, and quoted-post commentary. Native titles, quotes, signatures, link destinations, and optional account-profile observations can be retained. Media files may be referenced as artifacts or attachment links; image/audio/video analysis is not provided. Other action types can be preserved as `other` with `native_kind`, without asserting that any AHAS module supports them.

This is not a bot-label schema, an identity-linking service, a universal social graph, a collector protocol, or a research ground-truth format. Predicted bot status, stylistic scores, inferred human identity, embeddings, and change-point labels belong in separate analysis/evaluation artifacts, not in this evidence format.

## 2. Physical layout

A minimal bundle contains two files:

```text
bundle/
  manifest.json
  records.jsonl
```

An enriched bundle can add:

```text
  accounts.jsonl             # optional account/profile observations
  raw/source.json           # optional permitted original evidence
  raw/capture.html
  records-0002.jsonl         # optional further shards
```

The filenames other than `manifest.json` are declared in the manifest. Multiple `records` or `accounts` shards are permitted. At least one `records` file is required; it may be empty. Accounts need not have profile rows for their source keys to be usable in records.

JSONL is UTF-8 without a BOM, with one JSON object on each LF-delimited line. Embedded newlines inside source strings are JSON escapes, not record separators. U+2028, U+0085, and similar Unicode characters inside strings MUST NOT split a record. Empty files mean zero rows; blank lines are invalid. Ordinary validation permits CRLF, insignificant JSON whitespace, unsorted rows and an absent final LF; these are not canonical exports. Canonical export requires exactly C(row) followed by one LF per row and C(manifest) followed by one LF. `--canonical` enforces bytes and ordering; ordinary validation reports `canonical_export` separately. Files MAY be compressed for transport, but the declared hashes and lengths refer to their uncompressed members. Compression-container bytes are not a dataset identity.

Manifest paths are relative to the bundle root, use `/`, and MUST NOT be absolute or contain empty components, `.` or `..`, backslashes, colons, ASCII controls (including NUL and DEL), or symlinks. Every regular file under the dedicated bundle root must be listed, except `manifest.json`; unlisted files and nonregular members are refused. Every listed raw member must be referenced by a source artifact descriptor. Directory entries themselves are not listed. This is a POSIX directory contract, not a portable archive-extraction specification. Implementations never execute or automatically retrieve a referenced file/URL. Transport archive extraction and raw-source redaction are separate security responsibilities.

## 3. What one records.jsonl row means

**One row is one normalized observation of one source contribution or action. It is not necessarily a unique posting event.**

The same contribution can have several rows because it was observed at different times, supplied by different captures, edited, or represented inconsistently by different sources. Repeated observations do not create additional posting events. A later projection chooses at most one observation per logical contribution for a particular ordinary AHAS history and records that choice.

Example: a comment is observed on Monday, observed again unchanged on Tuesday, and observed with an edit on Wednesday. That is three observations of one contribution, not three comments. Its creation time remains Monday in all three; Wednesday may have a supplied edit time. If editing is unknown, a changed observation is not automatically labeled an edit: extraction differences, source disagreement, or an incorrect attribution remain possible.

## 4. Keys identify source entities, not people

A key is a four-field object:

```json
{
  "namespace": "https://forum.example.org",
  "collection": "posts",
  "id_type": "native",
  "id": "812"
}
```

All four values participate in key comparison. For handle labels, equal keys alone do not establish identity across captures; apply the source scope below. IDs MUST be strings, even if a provider supplies a decimal-looking identifier. No numeric conversion, universal lowercasing, Unicode normalization, URL redirect following, or trimming is applied to the key by AHIF.

| Field | Meaning |
|---|---|
| `namespace` | Stable absolute URI naming the identity authority/site. It is not the endpoint used to fetch the data. |
| `collection` | Provider/entity ID scope, such as `posts`, `comments`, `members`, or `accounts`. |
| `id_type` | `native`, `uri`, or `source_local` for contribution/action keys; account and container keys also permit `handle`. |
| `id` | Exact source identifier, original identity URI, observed handle, or source-local token. |

`namespace` and `id_type: "uri"` IDs must use ASCII URI syntax with a scheme (RFC 3986), with percent encoding where needed; optional fragments are allowed. This does not validate ownership, canonical spelling, or destination safety. A handle identifies a label, not a posting event, and is forbidden in `record_key` and record-target relationships.

The draft's symbolic service namespaces are `urn:ahif:service:reddit` and `urn:ahif:service:x`; they are design identifiers, not existing provider endpoints. For an unfamiliar independent forum, a stable site origin URI is suitable. A future source profile defines canonical authority spelling and any documented hostname aliases. Two collectors using different namespaces have not automatically established identical entities.

Use a native account ID when genuinely available. `handle` explicitly marks an observed username rather than a stable native account ID. Matching handles across dates can involve rename/reuse ambiguity and must not silently establish continuity. In the absence of a separately reviewed continuity assertion, consumers scope every handle label (account or container) by `(source_id, key)` using the referencing observation/coverage source, even when the four key fields match across captures. No account grouping or continuity resolver is supplied here. A missing author is `actor: null`, not an account called `unknown`, `deleted`, or `guest`. Generic shared guest labels do not establish a single account.

A `source_local` record identity is scoped to an evidence source: its `id` starts with the full `source_id` followed by `#` and a stable source locator. It permits storage when no dependable global contribution ID exists. It does not establish cross-source deduplication. If the original site/authority is unknown, a source-local key may name the intake authority instead: the design namespace `urn:ahif:source-local` with collection `records` is suitable, while the ID still binds the source descriptor and locator. This asserts no original site identity. Source-local identity can also be used for unidentifiable account observations, with the same scope warning. Primary record/account keys, record actors and coverage account keys using `source_local` must carry their own observation/coverage source ID and a nonempty locator after `#`. Source-local attribution, context and relationship references may name another source declared in the same manifest. Every such typed reference must carry a declared source ID. Extensions do not introduce core references. Never substitute a hash of text for a native event ID: two genuine events may have identical wording.

Two sites can both have post `812` or member `17`. They remain distinct. Same-account cross-site inference and native-ID/URI alias reconciliation are not performed by this format. Native names, profile handles, and self-descriptions are observations, not verified human identities.

## 5. Manifest and source descriptions

The manifest's mandatory properties are `format`, `format_version`, `dataset_id`, `sources`, `coverage`, and `files`. `description` and namespaced `extensions` are optional. `dataset_id` is a human-managed label, not a trusted uniqueness guarantee or cryptographic identity.

Each source describes an evidence input or capture, not a platform. At least one source and one coverage entry are required, and every source must have coverage; all-unknown coverage with a truthful scope description is valid. This does not require a contributor to know source completeness.

Source fields:

| Source field | Contract |
|---|---|
| `source_id` | Domain-separated SHA-256 of the source descriptor, as specified below. |
| `mode` | `account_export`, `api_response`, `web_capture`, `research_corpus`, `manual_entry`, `synthetic`, `other`, or `unknown`. |
| `description` | What the input actually is; cannot substitute for evidence. |
| `acquired_at` | When this source was acquired; explicitly unknown is valid. |
| `content_as_of` | Source-declared capture/as-of time; may differ from acquisition and individual observation times. |
| `origin` | Optional source URL/identifier string. It is never automatically followed. |
| `artifacts` | Original-evidence metadata, with hash and byte length when known. |
| `access` | Supplier declaration: public, restricted, private, or unknown. |
| `redistribution` | Supplier declaration and basis, not a permission grant generated by the format. |

Downloading a 2018 corpus in 2026 does not make its records observations of the website in 2026. Do not populate `content_as_of` or a row's `observed_at` with the import run time simply because no better time is available.

Raw artifacts are optional. Their omission MUST NOT require inventing hashes or claiming original bytes can be recovered. Each artifact has `sha256`, `byte_length`, `media_type`, `label`, and `included_path`; unknown hashes/lengths and an external/not-included path use null. Included artifacts must also occur in `files` as `raw` and have matching actual hashes/lengths. Shared bundles may retain only identifiers and hashes while permitted original bytes remain private. A supplied locator artifact hash must match an artifact hash declared by its observation source, whether or not bytes are included. This checks descriptor linkage, not the locator against raw content.

The source descriptor hash proves correspondence with a descriptor, and an artifact hash proves correspondence with bytes. Neither establishes the source's authenticity, who wrote text, access rights, completeness, or independence of observers. A malicious submitter can hash fabricated content. Future verification/crowdsourcing must evaluate evidence separately.

## 6. Mandatory record fields

Every row carries these fields (unknown states are legitimate values):

| Field | Purpose |
|---|---|
| `format_version` | Exact draft version. |
| `observation_id` | Content-bound identity of this complete normalized observation. |
| `record_key` | Logical source contribution/action identity. |
| `source_id` | The evidence source supporting this row. |
| `observed_at` | When this contribution state was observed, not when normalized. |
| `actor` | Source-attributed account key, or null. |
| `kind` | `post`, `reply`, `repost`, `quote_post`, `article`, `review`, `other`, or `unknown`. |
| `created_at` | When this contribution/action was created, if known. |
| `updated_at` | Supplied content-edit time, or unknown. |
| `lifecycle` | Observed visibility/deletion state, edit state, optional native revision ID. |
| `visibility` | Observed public/restricted/private/unknown access classification. |
| `content` | Captured text availability, completeness and ordered attributed parts. |
| `provenance` | Source locator, normalizer identity and declared transformations. |

Optional fields are `native_kind`, `permalink`, `contexts`, `relations`, `links`, `metrics`, `field_coverage`, and `extensions`. Unknown native types use `other`/`unknown` with the original name retained, rather than misclassifying a record to fit an analyzer.

A repost action's `actor` is the sharer and its `created_at` is the time of sharing, not the quoted/reposted object's original creation time. The original object is referenced separately. A quote post has its own commentary and timestamp plus a relationship to the quoted object. An edit observation remains the same `record_key`; an import, observation or edit is not counted as another original post.

`lifecycle.state` is `visible`, `deleted`, `removed`, `restricted`, or `unknown`. `edit_state` is `edited`, `not_edited`, or `unknown`. A known `updated_at` requires `edited`. `not_edited` requires supporting source evidence; an absent edit field is not evidence of no edits. A native revision ID alone does not prove that the item changed after creation.

Lifecycle and captured-content availability are different. A source can report removal while retaining some authorized archived text/title. Keep the declaration and the capture context; do not synthesize missing original text. Inconsistent source dates are retained and flagged, not corrected using the machine clock. The checker warns for known creation after observation, update before creation, update after observation and reversed known coverage/gap endpoints. An internally inverted tagged interval is invalid. Other uncertainty comparisons are not inferred.

## 7. Time, uncertainty and precision

Time is a tagged object, never an unqualified integer of unknown units. Known instants use a strict UTC RFC-3339 subset (years 0001–9999, ASCII digits, no leap-second spelling) with an explicit precision:

```json
{"status":"known","value":"2026-09-01T12:05:17Z","precision":"second","basis":"source"}
```

Other valid forms include:

```json
{"status":"date_only","value":"2026-09-01","utc_offset":null,"basis":"source"}
{"status":"interval","start":"2026-09-01T12:00:00Z","end":"2026-09-01T13:00:00Z","bounds":"closed_open","basis":"derived","raw":"during this hour"}
{"status":"unknown","reason":"timezone_not_available","raw":"yesterday at 5 pm"}
```

The optional `raw` string preserves the original displayed value. Resolved time branches require `basis`, which distinguishes source-supplied, documented conversion, derived, or supplier-declared information. Unknown time instead requires `reason` and has no `basis`. A derived interval is not silently upgraded to an exact source timestamp.

Known times allow seconds and up to nine fractional digits; precision is second, millisecond, microsecond, or nanosecond. Do not add finer digits than the declared precision. Source precision is recorded resolution, not a guarantee of the event's physical timing. Tied timestamps do not establish an actual within-tie order. Nanoseconds are preserved even though the current AHAS contract accepts at most six fractional digits.

Date-only values stay date-only. An unknown timezone does not become UTC. A source displaying only minutes/hours can be represented as a supported uncertainty interval or left unresolved; do not invent a second-resolution event by assigning a midpoint. UTC conversion requires evidence for the offset. Store leap-second or unsupported timestamp spellings as unresolved raw values rather than silently dropping precision. For intervals, bounds explicitly say closed or closed-open, and bounds must be valid and ordered. No timestamp validation depends on today's clock.

## 8. Content: preserve authorship context and literal text

`content` has mandatory `availability`, `completeness`, `reason`, and `parts`.

| Availability | Meaning |
|---|---|
| `present` | One or more captured text parts; at least one contains text. |
| `empty` | The supplied contribution is known to have no textual content. Parts is empty and completeness is complete. |
| `unavailable` | No usable text was supplied; reason is mandatory. |
| `redacted` | The supplier intentionally withheld some or all text; reason is mandatory. |

Completeness is `complete`, `partial`, `truncated`, `unknown`, or `not_applicable`, with schema-enforced combinations. Complete means the contribution/action’s textual scope, not that images or missing original events have been analyzed. It cannot be made complete by arbitrarily narrowing the scope to a captured title or preview. For a pure repost, known absence of added text may be represented as empty when the original object is only a relationship target; captured original text instead uses other/unknown-attributed parts. A truncated preview MUST NOT be labeled full text. A media-only record with known absent caption differs from a record whose caption was not collected. If only a title is supplied and body availability is unknown, content is partial/unknown, not proof of an empty body. Title-only complete content requires an explicit source declaration that no body exists, recorded in `reason`/provenance. `redacted` with retained parts requires `partial`; with no parts it requires `not_applicable`.

`parts` is an ordered list. Each part has a unique `part_id`, `role`, `attribution`, `format`, exact `text`, `fidelity`, and `language`. An optional locator points to the specific original field/element; a format variant can name a source dialect.

Roles are body, title, quote, signature, code, caption, link_preview, interface, and unknown. They describe source structure, not which words the analyzer should include. A raw Markdown body can remain one body part with its quote syntax intact. Alternatively, a verified source structure can be represented as separate parts. These are distinct observations/normalizer profiles, not automatically interchangeable analysis inputs.

Attribution is:

```json
{"relation":"record_actor","account_key":null}
{"relation":"other","account_key":{"namespace":"urn:ahif:service:x","collection":"accounts","id_type":"native","id":"123"}}
{"relation":"other","account_key":null}
{"relation":"unknown","account_key":null}
```

`record_actor` refers to the row's non-null actor; in an account profile it refers to that row’s `account_key`. It means the source attributes that part to that account, not that a verified person wrote it without assistance. `other` can indicate another contributor even when their identity is unknown. `system` marks platform-generated/interface material. Known source attribution is not semantic plagiarism detection. For an unsplit source field, attribution identifies the account to which the source attributes the field; it does not assert that embedded quotations are that account’s original prose. A future projection must verify markup/quotation boundaries before treating any such field as authored body text. It cannot rely on this tag alone.

A pure repost MUST NOT contain actor-attributed nonempty body/title commentary. Original text, if captured with it, is attributed to the original source or explicitly unknown. Added commentary calls for `quote_post` or a more appropriate supported kind. Quoted text, titles, signatures, and previews are never concatenated into the actor's body without a declared analysis projection.

Formats are plain, commonmark, html, bbcode, other, and unknown. The original text payload retains whitespace, Unicode code points, punctuation, spelling, mentions, hashtags, URLs, quotations and code as represented in its declared format. Parsing JSON escapes to recover a field string is not spelling/style normalization. Do not force HTML or BBCode through a Markdown parser by changing the label.

Fidelity distinguishes `source_field`, `rendered_text`, `transcription`, `transformed`, and `unknown`. A DOM text extraction is not an original source field. OCR/transcription is not verified original prose. No OCR or speech recognition is required or supplied here. Every lossy transformation must be declared in provenance, and available originals should remain referenced when retention is permitted.

No whitespace collapse, case folding, punctuation replacement, spelling correction, URL removal, Unicode NFC conversion, quote stripping, translation, summarization, or post concatenation is performed by the storage format itself. The analyzer can create derived views later, preserving their identities. Text segmentation and original-source attribution must not be guessed to make a sample qualify.

## 9. Language and context

Every text part has a language tag and a basis. `{"tag":"und","basis":"unknown"}` is the explicit unknown value. An English-language website or interface does not automatically make every comment English. Dataset-wide English assumptions can be represented but remain `dataset_assumption`; model-derived annotations require `model_annotation` and an identifiable method and do not become verified source declarations. The reference checker enforces basic shape and unknown semantics, not the complete BCP-47 language-tag registry. Its restricted tag shape is 2–8 ASCII letters followed by optional 1–8 alphanumeric subtags; valid BCP-47 private-use-only/grandfathered forms outside this shape need an explicit later profile, or `und` with the literal in a namespaced extension. `model_annotation` requires a nonempty `method`; `basis: "unknown"` requires `tag: "und"`. A source can itself declare `und`, so the converse is not required.

Context is an optional array of typed containers: community, forum_section, thread, channel, group, or other. Each has a source key, optional label and source/derived/supplier basis. Several contexts can coexist. A forum thread is not a community, and a reply parent is not necessarily the thread root. A hashtag is not automatically a community. Topic interpretation and sensitive-trait inference are outside this format.

Optional relationships independently identify `reply_to`, `quotes`, `reposts`, `crossposts`, `mentions`, or other. Targets can be known account/record keys, locator-only references, or explicitly unknown. Target records need not be present in the bundle. Missing parents MUST NOT trigger creation of invented target records, authors or timestamps.

`field_coverage` optionally states complete/partial/unknown/not_applicable for context, relationship, link and metric lists. In its absence, list completeness is unknown. Declaring a list complete or partial requires actually supplying that list; not_applicable permits only an absent or empty list. Unknown imposes no presence requirement. An absent list means no list was supplied; an empty list means the supplied list has no entries. **Neither asserts no relationship/link exists unless completeness and source evidence support that assertion.**

## 10. Links and observed metrics

A link records its original supplied destination, optional source-provided/separately observed resolved destination, role, and optional span. A URL is data, never an instruction to fetch. Roles distinguish inline links, native post destinations, attachments, profile links and other locations. Supplied URL text and expanded destinations must not overwrite one another. A URL label and hyperlink destination are not automatically two link occurrences.

Spans use zero-based half-open `[start,end)` Unicode-code-point indices into the named part's **exact decoded `text`**, not bytes, UTF-16 units, grapheme clusters or later normalized text. The span may describe the displayed label rather than the destination text. Future converters must translate a source's coordinate system explicitly. No claim is made that all source extraction operations can be represented by a simple span; a locator and transformation record can be more appropriate.

Metrics are optional observations, not inferred qualities. Every metric has a name, decimal-string value, unit, precision, as-of time, source-field name and scope. Preserve distinct native concepts: score is not automatically upvotes, views are not unique viewers, and rounded displayed totals are not exact counts. A missing metric is absent, not zero. Decimal strings avoid precision loss and keep arbitrary external numerical formats out of the canonical core.

Platform-reported contribution totals belong under the coverage entry's `reported_totals` or an account observation's metrics. Store their as-of time, rounding and inclusion scope. Do not use an unexplained total as a completeness denominator. Counts of observations, logical contributions, available text and analytical samples are different quantities.

## 11. Optional account observations

`accounts.jsonl` uses the same source/observation-hash approach. Required fields are version, observation ID, account key, source ID, observed time, aliases and provenance. Optional account creation time, state, profile text parts, observed metrics and extensions may be supplied.

An alias is a username, display name, profile URL, or other observed label. Account state is active, deleted, suspended, restricted, or unknown. These are source statements at an observation time. No legal name, location, real-person ID, inferred personality, biometric identity or mental state is required. Profile text must not enter the ordinary posting timeline or be counted as a new post. Different captures of a changed bio are account observations, not extra contributions.

## 12. Coverage and selection provenance

Every coverage entry identifies a source and optional account key, declares a textual scope, selection method, completeness status and basis, supplies known or unknown start/end values, and lists known gaps and any reported totals. Optional structured context keys/kinds narrow the scope. Null means not established, not all possible contexts. Empty known-gaps means no documented gaps, not proof that there were none.

`complete_for_declared_scope` is only a source/supplier claim tied to a stated scope and basis. “All rows in this exported file” is not “all posts ever made by this account.” Search results, selected threads, date cutoffs, removed communities, source outages, hidden profile listings, and partial pagination must remain visible. Changing acquisition methods across a time range must remain attributable to the particular source observations.

No program can infer completeness from successfully validating this schema. The reference checker reports validity and distinct supplied keys; it neither estimates unseen comments nor certifies authenticity.

## 13. Canonical representation and identifiers

Use a restricted JCS-compatible JSON domain: nonempty printable ASCII property names, Unicode-scalar string values, booleans, null, arrays, and integers within ±(2^53−1). Floating-point tokens are forbidden, including `1.0`, exponent notation, NaN and infinity. Duplicate properties and lone surrogates are refused. The valid integer token `-0` canonicalizes to `0`. Syntax must be checked before a parser erases distinctions such as `1.0` versus `1`; JSON Schema alone cannot enforce token spelling. Values requiring decimal precision use decimal strings. Original bytes with unsupported JSON types/keys can remain raw artifacts; adapters must not silently lose them.

Within this restricted domain, canonical values use UTF-8, recursively sorted ASCII object keys, no insignificant JSON whitespace, ordinary JSON string escaping, and preserved array order. Source-string whitespace and Unicode normalization are untouched. The reference Python serializer covers this restricted domain only; it is not a general RFC-8785 implementation.

Let C(x) be these canonical bytes, with **no final newline**. IDs are:

```text
source_id = "sha256:" + SHA256(
  UTF8("AHIF:source:0.1.1\n") + C(source descriptor without source_id)
).hexdigest()

record observation_id = "sha256:" + SHA256(
  UTF8("AHIF:record:0.1.1\n") + C(record without observation_id)
).hexdigest()

account observation_id = "sha256:" + SHA256(
  UTF8("AHIF:account:0.1.1\n") + C(account observation without observation_id)
).hexdigest()
```

The source binds all declared descriptor/evidence metadata. Indistinguishable descriptors yield the same source ID: hashes cannot prove two independent captures occurred. If two otherwise identical capture instances need separate representation, a supplier may assign an opaque capture token in a namespaced source extension, explicitly as intake metadata; it must not invent a source observation time or independence claim. Changing descriptor metadata (including included paths) also changes source-local keys bound to that descriptor; 0.1.1 performs no cross-descriptor reconciliation. The record hash covers the source ID and all declared observation fields. Changing source wording, attribution, precision or provenance changes the observation ID. It is an identity/integrity mechanism, not a trust mechanism.

For canonical transport, source descriptors sort by source ID, file descriptors by relative path, coverage entries by C(entry), and rows by observation ID within each shard. Observation IDs are unique across structured rows in a snapshot. Content-part and other source-ordered arrays retain order. Identical observation duplication within a snapshot is an error, not a second event. Different observations of the same record key remain valid.

Manifest file hashes are SHA-256 of actual uncompressed file bytes including final newlines; include lengths and row counts. Do not list the manifest inside itself. A separate digest of C(manifest) can identify that package layout. Repacking shards or changing provenance can change the package identity while leaving a later analysis projection identical. A distinct, versioned projection identity must bind the exact selected input values, not simply reuse a whole-bundle hash as a promise of identical science.

A root-directory move leaves relative paths and values intact. Renaming an included evidence member, changing normalizer version, or revising the manifest is an observable evidence change. Do not equate byte reproducibility with identical real-world truth.

## 14. Multiple observations, conflict and retention

Records are not automatically resolved by last-write-wins, majority vote, newest collection time, highest engagement, or a judgment of suspiciousness. Multiple observers agreeing can all be copying the same source. Equal creation times do not prove two observations are the same event if identity is source-local. A failed later fetch does not prove deletion.

The later projection stage must explicitly bind which observation was selected for each logical contribution, how conflicts/edits were handled, what as-of rule was used, and every exclusion. No hidden mixing of a title from one revision, a body from another, and metadata from a third is permitted. Cross-source field fusion creates a separately documented derived observation with source lineage; it is not provided in draft 0.1.1.

Retention/deletion controls are outside schema syntax but not outside the product. Immutable IDs do not require permanent storage of personal text. When material must be withdrawn, remove affected copies/derived outputs as appropriate and issue a new snapshot or withdrawal record. An older digest must not be used to promise access to unavailable content. Raw excerpts, usernames, URLs, timestamps, and even hashes can remain identifying. The format's access/redistribution labels are declarations, not enforcement or legal determinations.

## 15. Validation levels and implementation boundaries

Validation should distinguish:

1. **Syntax/schema:** legal JSON, supported version, expected field types/enums, explicit unknowns.
2. **Bundle/semantic integrity:** IDs/digests, local references, interval order, source links, bounds, attribution consistency, unique part/observation IDs and file inventories.
3. **Evidence authenticity:** whether a source actually supplied these facts. Not established by levels 1–2.
4. **Projection compatibility:** whether a particular analyzer can represent the selected records honestly.
5. **Scientific applicability:** whether that analyzer's measurements have been evaluated for this source/task.

The supplied reference checker implements the published schema checks and selected bundle/semantic rules, including hash verification and precise span/time arithmetic. Typed time validation never interprets extension payloads or transformation parameters as core time objects. Explicit offline URI checks do not rely on jsonschema’s optional URI dependencies.

It does not verify raw DOM/CSV/JSON locators against every external original, detect all source conflicts or cycles, validate the entire language registry, implement an archive-extraction service, enforce legal permissions, or analyze text. Raw origins and schema URIs are never fetched.

Its fixture-oriented limits are 4 MiB manifest, 64 MiB per file, 256 MiB bundle, 100,000 structured rows, 16 MiB per structured line and depth 64. These are **reference-checker operating limits**, not posting-history eligibility rules or a production-scale memory guarantee. JSON schemas separately bound individual strings/arrays. An exceeded bound is an explicit refusal; no silent truncation or sampling is allowed. A production importer needs streaming, bounded decompression and additional hostile-input review. This checker reads/rechecks fixture files using ordinary filesystem APIs, retains rows, and does not prevent concurrent mutation, hard-link aliasing, filesystem races or unbounded directory-entry enumeration. No production memory/CPU/security guarantee is claimed. It never extracts archives, renders markup, executes text or fetches schemas/origins/links.

## 16. Versioning and next step

Strict schemas reject unknown core properties; the versioned `extensions` object permits namespaced source metadata only. Extension keys use a producer namespace followed by `:`, e.g. `org.example:provider-metadata`; their content must use the restricted JSON domain. Extensions are not a place to smuggle inferred identities, bot scores or ground-truth labels into the analyzer. Preserve native source metadata without pretending it has common semantics.

No new method, normalization policy, field reinterpretation or timestamp convention may be silently introduced under the same format/normalizer identity. Draft minor versions may be breaking and must be explicitly selected. The frozen AHAS schemas, configuration and test outcomes remain untouched.

The next implementation milestone, under separate implementation authorization, is a limited normalizer for one real source plus its projection to a supported AHAS profile. That milestone must test raw-field fidelity, event/observation deduplication, exclusion reasons, source text boundaries and retained analytical results. This package does not claim that milestone has already been implemented.

## Sources

Standards and actual repository constraints used to inform this proposal are listed, with pinned source locations, in `SOURCES.md`. The design is intentionally not a complete ActivityStreams or PROV serialization; it borrows the useful distinctions between activity, attributed content and provenance without requiring JSON-LD expansion or remote contexts.
