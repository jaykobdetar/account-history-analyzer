# Compatibility with frozen AHAS 1.0.4

This is a proposed future projection contract, not an implemented converter. Inspected repository commit: `6f465bd95fa3c12df41235986a96a04cf6c332d0` (2026-09-15). See the two current upstream schemas listed in SOURCES.md.

## Why this is a layer, not a drop-in schema replacement

The current record schema requires `schema_version`, `id`, `account_id`, `kind`, `text`, and `status`; only `comment` and `submission` are legal kinds. Optional fields include creation/edit time, language, `subreddit`, title, parent/thread references and permalink. The snapshot schema binds one account, one text format (`plain` or `markdown`), a default language, source category and coverage declaration. Unknown extra properties are forbidden.

AHIF intentionally retains more evidence: multiple observations/revisions, unknown or coarse time, heterogeneous formats, multipart attribution, generic contexts, pure share actions, capture provenance and source metrics. Sending an AHIF row directly to the current loader is therefore an error, not interoperability.

## Projection design

A future projection should emit:

```text
projection/
  records.jsonl                 # current AHAS schema
  snapshot.json                # current AHAS schema
  projection-receipt.json       # selected observations, rules and losses
```

The receipt must bind format version, source snapshot/file hashes, selected actor/source scope, normalizer/profile version, every selected observation ID, generated record IDs and any excluded/quarantined facts. It stays outside the frozen record schema. Reproducibility uses the unchanged engine contract plus this auditable bridge, not a claim that the new raw bundle hash equals the old snapshot hash.

## Field mapping and limits

| AHIF evidence | Existing AHAS field | Honest rule |
|---|---|---|
| Selected contribution `record_key` | `id` | Stable digest-derived alias of the full structured key when necessary, with a map in the receipt. One selected observation per contribution. Do not use observation_id as posting-event identity. |
| Explicit actor key | `account_id` / manifest account | One account per ordinary snapshot. Unknown actors remain in AHIF; they are not mixed into a fake `unknown` account. Same usernames on different services never collapse. |
| `kind`, `native_kind`, source profile | `kind` | Existing Reddit comment/submission mappings can be preserved exactly. Generic replies/posts/articles/reviews need explicit profile mappings; name compatibility alone is not scientific validation. No global `everything=comment` conversion. |
| Chosen authored body | `text` | Preserve an exact supported source field when possible. Multiple parts or other formats require a separately tested projection. Quoted/embedded material must not become actor-authored prose. No combining separate posts to satisfy minimum-length guards. |
| Chosen authored title | `title` | Only for a submission. Thread titles are not automatically a reply's authored title. |
| Availability/lifecycle | `status` | Present, known empty and unavailable have distinct mappings. `present` permits `text:""` in the old schema; unavailable text requires null. Truncated text cannot be silently treated as a complete body. Either refuse/exclude under a stated policy or name a partial-text experiment and preserve its limitation. |
| Known UTC `created_at` | `created_utc` | Point timestamps with at most six fractional digits can fit. Unknown becomes null. Date-only, intervals and nanosecond values remain in AHIF; do not invent a precise moment, round silently or use observed_at instead. |
| Source edit status/time | `edit_state`, `edited_utc` | Unknown stays unknown. Do not infer no edits from missing metadata. A newly observed version does not create a new post. |
| One compatible body language | `language` | Unknown maps explicitly to `und`, not null inheriting an English default. Mixed-language parts and regional tags require a documented profile decision; exact `en` eligibility is not assumed. |
| Reddit community | `subreddit` | Map genuine subreddit metadata. For other platforms retain null or use a separately declared/reviewed grouping profile; do not tell the report a forum section is literally a subreddit. Thread and hashtag are different contexts. |
| Known reply/thread keys | `parent_id`, `thread_id` | Same deterministic identity mapping as contributions; missing targets can remain references. Only supplied parent creation times may populate `parent_created_utc`. |
| Original permalink | `permalink` | Preserve inert source string; no fetch. |
| Source category | manifest `source_category` | Synthetic/user-supplied/research-corpus origin must be mapped explicitly. Capture method and platform remain in provenance; a converter must not invent a new enum accepted by a frozen loader. |
| Text representation | manifest `text_format` | One supported plain/Markdown format per snapshot. HTML, BBCode or mixed formats need a tested declared conversion, separate analysis scopes, or refusal. |
| Coverage | manifest `coverage` + receipt | Do not upgrade partial/unknown scope. Extra exclusions, omitted reposts and unsupported records belong in the receipt and scope notes. |
| Context records belonging to other accounts | Not ordinary same-account event rows | Keep separately; inserting them would contaminate activity/style. |
| Pure reposts and other unsupported actions | No lossless current kind | Preserve in AHIF. An authored-post-only projection can explicitly exclude them and disclose reduced activity scope. Do not label a pure share as an authored comment simply to count it. |
| Account profiles/metrics, native links, raw captures | Not consumed by current core fields | Remain in AHIF/receipt; do not append them to body text. |

## Source-preserving acceptance tests for a later bridge

1. Current conforming Reddit fixtures pass through the bridge with the same expanded source values and numerical outputs, except explicitly documented source-identity changes. Do not claim byte equality if identifiers/provenance genuinely changed.
2. Multiple observations of the same native contribution emit one chosen event, with the chosen version and alternatives recorded. A source-local conflict is not guessed away.
3. Pure repost text never enters the sharer's style, a quote's commentary remains distinct from the embedded quote, and profile biography text does not enter the posting timeline.
4. Unknown time, unknown language, missing parent and partial text remain explicit. No midnight placeholder, English fallback or fake parent is introduced.
5. Conversion from HTML/BBCode is tested separately against captured structure, with code/quote/signature boundaries retained; output formatting must not manufacture cross-gap phrases.
6. At least one incompatible record produces an explicit per-record reason, not silent dropping. Exceeded resource limits refuse rather than truncate.
7. The source format, projection profile, engine and original private evidence retain separate identities. A passed input test does not claim validated cross-platform authorship performance.

Do not change the frozen analyzer, its word/record guards, PELT implementation or statistical settings to adopt the storage schema. Platform support and useful analytical transfer are separate milestones.
