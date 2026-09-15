# Future projection contract to frozen AHAS 1.0.4

**Status: design only; no converter or accepted source-specific projection profile exists.**
AHIF 0.1.1 cannot be passed directly to AHAS. Actual local production schemas and loader were read; their hashes are in [checks/frozen-boundary.json](checks/frozen-boundary.json). The engine version is 1.0.4 and both input schemas still require `schema_version: "1.0.0"`. The original proposal's remote commit is not a verified local checkout identity.

## Selection and refusal rules before field mapping

A future ordinary snapshot selects exactly one source account and at most one whole observation for each full `record_key`. Native and URI keys compare exactly, including namespace and collection; URI/native aliases are not inferred. Different event keys remain distinct even when all text and times match. No text hashing as event ID, concatenation of events, newest-capture default, field fusion or majority vote is allowed.

Select observations using an explicit versioned profile and as-of rule. A rule may select a documented source revision. Where competing observations disagree on actor, wording, timestamps or revision and the rule cannot resolve them with supplied evidence, quarantine the logical key with `unresolved_observation_conflict`. Record every alternative and decision. Repeated captures of one native key emit at most one event. Edit observations retain the creation time supplied by the selected observation, not their edit/import time.

Anonymous actors are excluded (`actor_unknown`). A handle is only a capture-scoped label: use `(source_id, actor_key)` for selection and aliasing, and refuse automatic cross-capture continuity (`identity_continuity_unestablished`). Source-local keys stay bound to their descriptor source and cannot be merged across descriptors without a future explicit reconciliation contract. This means distinct source-local keys can describe the same real event; the format does not certify an event total.

All excluded/quarantined observations require receipt entries, including those outside selected actor, source, date, kind and text scope. Exclusion is permitted only by the declared selection profile; otherwise stop the projection. No silent dropping or sampling. Valid AHIF does not guarantee even one eligible AHAS record.

## Every production record field

“Refuse” means quarantine the record or stop, according to the declared policy, with the stated loss/reason. Null is never a fabricated value. Bounds below are actual schema bounds; frozen configured input limits may be stricter.

| AHAS target | AHIF source and proposed rule | Loss / refusal |
|---|---|---|
| `schema_version` | Literal `1.0.0`. | AHIF version remains in receipt; never substitute `0.1.1`. |
| `id` | `ahas-r:` + lowercase SHA-256 of `UTF8("AHIF:projection-record-key:1\n") + C(record_key)`. Store full key/alias map and check for collisions. | Opaque alias (71 characters); do not use observation ID. Different observation choices can share the event ID. Refuse detected alias collision. |
| `account_id` | `ahas-a:` + SHA-256 of `UTF8("AHIF:projection-account-key:1\n") + C(identity)`, where identity is `{account_key: key}` for native/URI, or `{account_key: key, source_id: sid}` for handle/source-local. Same alias in every row and snapshot. | One account only; refuse unknown actor and unestablished continuity. Key map stays with the private receipt when identifying. |
| `kind` | Only `comment` or `submission`. A later source profile may map a supplied Reddit `reply`/native `comment` to comment and a supplied native submission to submission. Generic reply/post/article/review mappings require their own declared profile. | No blanket reply→comment or post→submission support is adopted today. Reposts, `other`, `unknown` excluded/refused as `kind_unsupported`. Quote posts need a tested commentary-only profile. Names do not establish scientific transfer. |
| `text` | One exact, complete, supported authored body field/part under a tested profile, or `""` only when the source establishes no body text. Maximum 200,000 code points. | Title-only with unknown body, partial/truncated/redacted bodies, ambiguous embedded attribution, multiple disjoint bodies, unsupported markup or excess length refuse (`body_incomplete`, `authorship_boundary_unresolved`, `text_projection_unsupported`, `text_limit`). Do not invent missing prose or join across excluded quote/signature gaps. |
| `status` | Apply the state table below. | AHAS collapses lifecycle and captured-text availability; preserve both originals in receipt. |
| `created_utc` | Exact known UTC value with ≤6 fractional digits and supported precision; unknown→null. | Date-only/interval→null only under an explicitly declared non-temporal selection policy with `coarse_time_omitted`; otherwise refuse. Nanosecond precision or >6 digits refuse (`timestamp_precision_unsupported`), never round. No observed/acquired/update time substitution. Basis/resolution/raw spelling are lost from AHAS and retained in receipt. |
| `edit_state` | Exact `lifecycle.edit_state`. | Absent edit evidence stays `unknown`; never infer `not_edited`. Native revision ID goes to receipt. |
| `edited_utc` | Exact supported known `updated_at`, requiring `edited`. Unknown→null. Coarse times follow the declared null/refusal policy above. | Refuse known edit before creation (`edit_before_creation`), which the production loader rejects. Do not “repair” dates. Nanosecond precision refuses. |
| `language` | Explicit compatible selected-body tag; unknown→`und`. | Never null/inherit English for unknown. AHAS syntax is `[a-z]{2,3}(-[A-Za-z0-9]{2,8})*`; incompatible tags refuse or require a separately declared mapping with recorded loss. Differently labeled body parts refuse. Tag casing/mapping is not automatic; `en-US` is not the engine's exact `en`. Attribution basis/method retained in receipt. |
| `title` | Exact authored title for submission, ≤20,000 code points; absent→null. | Comment title must be null. A thread title is not a reply's title. Ambiguous/truncated titles refuse if included. Never put a title into body to satisfy word guards. |
| `subreddit` | Source-provided Reddit community label, ≤256 code points; otherwise null. | Keep forum section/channel/thread/context keys in receipt. No fabricated subreddit. Ambiguous multiple communities refuse field projection or record, according to an explicit null policy. |
| `parent_id` | Single known `reply_to` record key through the identical event alias rule; missing target may remain an external reference. Unknown/locator-only→null with loss. | Multiple conflicting parents refuse (`parent_ambiguous`). No fake target row or inferred time/actor. |
| `thread_id` | Source-supplied thread identity through a declared key mapping. If the provider establishes that thread ID equals its root post key, use that post key's alias; otherwise use the full distinct thread key. | Null for absent/ambiguous thread under declared policy. Do not equate a parent, thread root and community, or silently reconcile different collections. |
| `parent_created_utc` | Null by default: AHIF relationship has no parent-time field. A separately selected existing parent observation may supply its exact supported creation time, with receipt binding that observation. | Do not infer from child, ID or import time. Refuse contradiction with an internal parent and internal child-before-parent chronology, which the production loader rejects. Context from another account stays outside the ordinary account timeline. |
| `permalink` | Exact supplied string if ≤4096 code points; absent→null. | AHIF permits up to 8192; overlength refuses or is omitted only by a named metadata-loss rule, never truncated or fetched. |

### Lifecycle / body state table

| AHIF evidence | Future conservative AHAS representation |
|---|---|
| Visible + complete supported body | `status: "present"`, exact `text` (after a separately approved source profile). |
| Visible + known absent body | `status: "present"`, `text: ""`. This is zero words, not invented prose. |
| Deleted/removed + no retained text | Corresponding `deleted`/`removed`, `text: null`; no fabricated title. |
| Unavailable for another/unknown reason, no retained text | `unavailable`, `text: null`, original reason in receipt. Unknown lifecycle is not automatically visible. |
| Deleted/removed/restricted/unknown lifecycle + retained text | No lossless mapping. Conservative text projection refuses (`lifecycle_content_unrepresentable`). A later explicitly named archive profile may deliberately project a different as-of state only with evidence and receipt. |
| Partial/truncated/redacted or title-only with unknown body | Conservative text projection refuses. Storage remains valid; a future partial-text experiment would need separate authorization and labeling. |

The actual AHAS schema allows titles on a non-present submission, but using this permissiveness as an implicit archive/body rule is not adopted. Its `status != present` forces `text: null`; a removed AHIF record with retained text cannot be losslessly represented. Literal sentinel bodies `[deleted]` and `[removed]` are warned about and treated as unusable by existing preprocessing; refuse an authored-body promise for those strings unless a later profile explicitly handles that limitation.

## Every production snapshot field

| AHAS target | Proposed source/rule | Loss / refusal |
|---|---|---|
| `schema_version` | `1.0.0`. | No engine/schema upgrade. |
| `snapshot_id` | A ≤256-character label bound in receipt to the exact projection definition and emitted values; e.g. a domain-separated projection digest. | Not the AHIF dataset label or whole-bundle hash reused as a scientific identity. Receipt needs its own future versioned schema before implementation. |
| `account_id` | Same selected identity alias as rows. | Mixed accounts refuse. |
| `source_category` | `synthetic` for purely fictional input, `research_corpus` for explicitly supplied corpus origin, otherwise explicitly classified `user_supplied`. | Capture mode alone does not prove rights or authenticity. Mixed categories need separated snapshots or a reviewed rule, not a new enum. |
| `capture_utc` | Exact supported `content_as_of` only when one common source as-of instant is established for selected data; otherwise null. | Never acquisition/normalization time or a manufactured max/mean of observations. Individual observed/acquired/as-of times retained in receipt. |
| `text_format` | One `plain` or `markdown` value from tested profile. CommonMark→markdown requires tests against frozen markdown-it behavior/settings. | HTML/BBCode/other/unknown/mixed formats refuse absent separate tested conversion or split into compatible scopes. Markup relabeling is not conversion. |
| `default_language` | Use `und`; every row should carry its explicit tag. | No implicit English. Mixed-language limitations stay explicit. |
| `source_notes` | Brief truthful source/selection/projection description. | Not a place to smuggle evidence fields into analysis; exact provenance remains in receipt. |
| `license_notes` | Supplied license/access information only; null when unknown. | `allowed_by_supplier` is neither a dataset license nor consent. No invented license, consent or verification. |
| `coverage.status` | `unknown` remains unknown. Deliberate source/projection selection→`sampled`. `complete_for_declared_scope` only retains a supported claim for exactly the narrowed scope. | Do not upgrade partial/unknown to complete. `partial` can mean undocumented missingness, so map to `unknown` with notes unless a sampling/selection description actually supports `sampled`. |
| `coverage.start_utc`, `end_utc` | Supported exact declared endpoints, else null with original uncertainty in receipt. | Do not infer from min/max observed rows. Refuse reversed exact endpoints (`coverage_inverted`) instead of swapping. |
| `coverage.known_gaps[].start_utc/end_utc/note` | Only gaps with both supported exact endpoints fit; carry reason in note. | Uncertain gaps stay in receipt and coverage notes. Empty projected gaps do not mean no gaps. Reversed exact gaps refuse. |
| `coverage.notes` | Preserve scope, source claims, selection limitations and omitted uncertainty. | Source reported totals do not yield a completeness denominator or percentage. |

## Facts retained only in evidence / receipt

Source descriptors, original artifacts/locators, account profiles/aliases, native metrics/totals, native destination links, quote/signature/interface/preview parts, additional contexts/relations, availability reasons, field coverage, language/time basis, transformations and extensions are not ordinary AHAS body text. Their omission from analyzed fields must be declared. Native destination links are not automatically counted by the current body's link extractor; append-to-body is refused. Profile revisions and third-party context rows must never inflate account posting counts.

## Required future receipt and acceptance gates

The future receipt must bind: its own schema/profile versions; AHIF version; exact manifest and file hashes; selected actor and source scope; full key-to-alias maps; every selected/alternative/excluded/quarantined observation ID and reason; as-of/conflict policy; retained part IDs and exact transformations; field-level loss decisions; emitted record/snapshot hashes and expanded production values; unchanged engine/config identities. It must distinguish integrity from authenticity, analysis eligibility from format validity, and preserve unknowns. Receipt-only context references must not be silently fused into a record.

Before implementation is called supported: freeze its receipt schema and one source profile; test raw-field fidelity and identities; show one observation per native event; test quote/repost/signature/HTML/BBCode and native-link losses; demonstrate explicit refusals; validate actual production inputs including loader chronology and resource limits; and compare retained existing-source values and numerical outputs under unchanged settings. Projection limits are the engine's frozen limits (defaults 10,000 unique records, 50 MiB combined input, body/title schema bounds), not the larger AHIF reference-checker limits. Exceeding limits refuses instead of truncating/sampling. No such conversion, output comparison, normalizer, real-source evaluation or new scientific pilot was performed for this adoption.
