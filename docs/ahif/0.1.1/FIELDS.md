# Field dictionary — AHIF 0.1.1

Normative companion to [SPEC.md](SPEC.md). Exact required arrays, enums, string/array limits and conditions are in [schemas/ahif.schema.json](schemas/ahif.schema.json); entry points are manifest, record and account schemas with IDs `urn:ahif:schema:0.1.1:{manifest,record,account}`. There are no implicit defaults. Missing optional fields mean not supplied, never zero/false/complete. Null is legal only where the schema says so. Core unknown properties are rejected.

## Manifest and source scope

| Field(s) | Definition |
|---|---|
| `format`, `format_version` | Literal AHIF and exact contract version. |
| `dataset_id` | Supplier-managed bundle label, no uniqueness/authenticity guarantee. |
| `description` | Optional human description, not evidence of any claim. |
| `sources`, `coverage`, `files` | Source descriptors, scoped selection/completeness declarations, and actual member-byte inventory. All are nonempty; every source needs coverage and at least one records shard exists. |
| `extensions` | Optional producer-namespaced restricted JSON; opaque to core interpretation. No automatic inferred identity/quality semantics. |
| `source.source_id` | Versioned domain-separated descriptor hash; excludes itself. |
| `source.mode` | How the evidence input was supplied/captured; `unknown` allowed. Does not identify the service or prove verification. |
| `source.description` | What the input actually is. |
| `source.acquired_at` | Time this evidence input was acquired, possibly unknown. |
| `source.content_as_of` | Source-declared state/capture time, possibly unknown; not downloader time. |
| `source.origin` | Optional nullable literal origin identifier/link, inert. |
| `source.artifacts` | Supplied original-evidence descriptors; `[]` requires no raw bytes or invented hashes. |
| `source.access` | Supplier-reported access class; unknown allowed. |
| `source.redistribution.status`, `.basis` | Supplier declaration and rationale. Unknown with an empty/unknown basis is valid; does not generate permission, consent or a license. |
| `artifact.sha256`, `.byte_length` | Actual byte digest (without `sha256:` prefix) and length when known; null when unavailable. Included artifacts require both. |
| `artifact.media_type`, `.label` | Declared media type and human label. Use `application/octet-stream` when format is not established. |
| `artifact.included_path` | Nullable safe path to included raw bytes; null means not included. No external path is followed. |
| `file.path`, `.role` | Safe relative member path and records/accounts/raw interpretation. |
| `file.sha256`, `.byte_length` | Digest and size of actual uncompressed member bytes, including line endings. |
| `file.row_count` | Exact JSONL row count for structured members (zero allowed); null for raw. |
| `coverage.source_id`, `.account_key` | Evidence source to which the declaration applies; optional identity represented by required nullable account key. Null does not establish all accounts. |
| `coverage.scope_description` | Explicit universe the source claim concerns, even if only supplied rows. |
| `coverage.status`, `.basis` | Unknown/partial/complete-for-declared-scope claim and basis. Validation is not proof of completeness. |
| `coverage.selection_description` | Known retrieval/filter/sampling method or explicit uncertainty. |
| `coverage.start`, `.end` | Declared temporal scope endpoints, not automatically the observed min/max; unknown is valid. |
| `coverage.known_gaps` | Documented gaps only; `[]` means none documented. |
| `gap.start`, `.end`, `.reason` | Known/uncertain gap endpoints and explanation. |
| `coverage.context_keys`, `.kinds` | Optional nullable structured scope filters. Absent/null means not established. Empty arrays are explicitly supplied empty filters; no universal scope assertion. |
| `coverage.reported_totals` | Native totals with metric precision, as-of and scope. Never an invented completeness denominator. |

## Keys, time and provenance

| Field(s) | Definition |
|---|---|
| `key.namespace`, `.collection` | Exact absolute ASCII identity-authority URI and provider/entity ID scope. |
| `key.id_type`, `.id` | Exact native/URI/source-local ID string; handles also allowed for account/container labels. Event and record-target handles are forbidden. No normalization or numeric conversion. |
| `time.status` | `known`, `date_only`, `interval`, `unknown`; selects the schema branch. |
| `known.value`, `.precision` | Strict UTC instant and recorded second/milli/micro/nanosecond resolution; precision is not accuracy. |
| `date_only.value`, `.utc_offset` | Source calendar date and nullable known offset (`Z` or ±HH:MM); unknown offset must be null. |
| `interval.start`, `.end`, `.bounds` | Ordered exact UTC bounds; closed permits equal endpoints, closed_open does not. |
| `time.basis` | Source, documented source conversion (known instants only), derived, or supplier-declared basis; mandatory for resolved branches. |
| `unknown.reason` | Nonempty description of why time is unresolved. No basis field in this branch. |
| `time.raw` | Optional nullable original timestamp display, never an instruction to parse heuristically. |
| `provenance.locator` | Local position of evidence supporting this observation; manual/other description if no machine locator exists. |
| `provenance.normalizer.name`, `.version` | Identity of the process that formed the normalized observation, including manual entry/fixture builder. No source revelation required. |
| `normalizer.configuration_sha256` | Optional nullable digest of a separately defined configuration representation; not an unspecified automatic hash policy. |
| `provenance.transformations` | Ordered declared operations, possibly empty. Every known lossy operation must be declared. |
| `provenance.notes` | Optional freeform limitations/extraction context. |
| `locator.kind`, `.value` | Locator syntax label and literal position. JSON pointer refers to decoded source JSON; jsonl_line/csv_row/dom_selector/archive_member/source_id/manual/other are preserved source-profile locators, with conventions documented in provenance. Core does not evaluate them. |
| `locator.artifact_sha256` | Optional nullable binding to a hash in this observation source's artifact descriptors. No hash required if source bytes are unavailable. |
| `transform.operation`, `.version` | Named, versioned transformation. |
| `transform.parameters`, `.input_locator`, `.notes` | Optional restricted JSON parameters, nullable input position and explanation; no execution. |

## Record and text

| Field(s) | Definition |
|---|---|
| `observation_id` | Hash of the complete normalized row except itself, under record/account domain and version. Not the event key. |
| `record_key`, `source_id` | Logical contribution/action identity and its supporting evidence descriptor. |
| `observed_at`, `actor`, `kind` | Observed state time, nullable source-attributed account, and broad contribution/action class. All can explicitly be unknown. |
| `created_at`, `updated_at` | Original action creation and supplied edit time; never inferred from capture/import. |
| `lifecycle.state`, `.edit_state`, `.native_revision_id` | Observed lifecycle, supplied edit evidence and required nullable source revision token. A revision token alone proves no edit. |
| `visibility` | Observed access class, including unknown, independent of lifecycle. |
| `native_kind`, `permalink` | Optional nullable source type and inert canonical/original contribution link. |
| `content.availability`, `.completeness`, `.reason`, `.parts` | Captured text availability, textual scope completeness, required nullable explanation and ordered attributed parts. Use unknown/reason honestly, not placeholder prose. |
| `part.part_id`, `.role` | Unique position identifier within the observation and source structural role (body/title/quote/signature/code/caption/link_preview/interface/unknown). |
| `part.attribution.relation`, `.account_key` | Field/part attribution to subject account, other nullable identity, system, or unknown. Only other accepts a non-null account key. `record_actor` in an account row means account_key. |
| `part.format`, `.format_variant` | Literal text representation and optional nullable dialect/version. No relabeling HTML as Markdown. |
| `part.text` | Exact decoded field string, including whitespace, code points and markup. Empty individual parts allowed if content-state conditions hold. |
| `part.fidelity` | Original source field, rendered extraction, transcription, transformed representation, or unknown. Does not itself prove original authorship. |
| `part.language.tag`, `.basis`, `.method` | Restricted tag shape, declaration/annotation provenance and optional nullable method; model annotations require a nonempty method. `und` is valid. |
| `part.locator` | Optional nullable original field/element location. |
| `contexts`, `relations`, `links`, `metrics` | Optional observed lists. Absent means not supplied, empty means no entries supplied. |
| `field_coverage.{contexts,relations,links,metrics}` | Optional per-list complete/partial/unknown/not_applicable declaration. Absence is unknown; complete/partial requires the corresponding list, and not_applicable permits only absent/empty. No inference of no relationships without supplied source evidence. |

## Context, links, metrics and account observations

| Field(s) | Definition |
|---|---|
| `context.kind`, `.key`, `.label`, `.basis` | Typed community/section/thread/channel/group/other container, exact source key, optional label and declaration basis. |
| `relation.type`, `.target_type` | Reply/quote/repost/crosspost/mention/other relationship and record/account target class. Reply/quote/repost/crosspost require a record target. |
| `relation.target_key`, `.target_url`, `.resolution` | Known identity, locator-only link, or unknown. The target need not have a row. Unknown requires both null; locator-only requires URL and null key. |
| `relation.source_field` | Optional nullable native relationship field name. |
| `link.link_id`, `.role` | Unique local link observation ID and inline/native_destination/attachment/profile/other role. |
| `link.url_as_supplied` | Literal supplied destination, including unsupported/unsafe schemes; stored inertly. |
| `link.resolved_url`, `.resolution_basis` | Nullable separately supplied/observed destination and basis. Unknown/not_attempted requires null. A supplied basis with null may mean no resolved destination was supplied; it is not success proof. |
| `link.span` | Optional nullable association with an exact text slice; label can differ from URL. |
| `span.part_id`, `.start`, `.end`, `.unit`, `.coordinate_space` | Existing part and zero-based half-open nonempty Unicode-code-point span into `part.text`; bounds checked on decoded original string. |
| `link.source_field` | Optional nullable source link field name. |
| `metric.name`, `.value`, `.unit` | Native measure name, ASCII decimal-string value and unit. Missing metric is omitted, never zero. |
| `metric.precision`, `.as_of`, `.source_field`, `.scope` | Exact/rounded/bounded/unknown precision, observed time, native field and inclusion scope. No inferred scores. |
| `account.account_key`, `.source_id`, `.observed_at`, `.observation_id` | Profile subject, supporting capture, state time and versioned account-domain hash. |
| `account.aliases` | Required array, possibly empty; observed labels do not establish permanent identity. |
| `alias.kind`, `.value` | Username/display name/profile URL/other observed label. |
| `account.created_at`, `.state`, `.profile_parts`, `.metrics` | Optional supplied account creation/lifecycle/profile text/native metrics. Profile observations never become posting events. |
| `account.provenance`, `.extensions`, `.format_version` | Same provenance/restricted extension/version rules as record observations. |
