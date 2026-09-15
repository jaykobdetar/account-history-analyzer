# Practical sufficiency matrix

All examples are fictional. Paths below are relative to this revision. Negative fixtures are [named mutation recipes](fixtures/negative-cases.json) applied to `examples/minimal/records.jsonl`; the test runner recomputes observation IDs before checking the intended semantic rejection. They are not standalone valid bundles.

| Required case | Representation / fixture | Limitation or refusal demonstrated |
|---|---|---|
| Normal post | minimal; forum post in mixed-platform | Unknown times/language remain valid. |
| Reply, absent parent | mixed-platform `c_demo` known external key; `bbcode_1` unknown target | No placeholder parent record. Locator-only also valid by schema. |
| Original short post | mixed-platform `18446744073709551615` | Text remains short; no aggregation to meet engine guards. |
| Quote commentary + third-party text | mixed-platform `quote_1` | Separate body and other-attributed quote; raw CommonMark field separately retains embedded syntax. |
| Pure repost | mixed-platform `repost_action_1`; review-cases `repost_captured` | No added text or other-attributed original. Actor body/title commentary refused. |
| HTML / BBCode | mixed-platform `html_1` / `bbcode_1` | Exact markup kept; relabeling as Markdown is unsupported. |
| Signature | mixed-platform `html_1` signature part | Separate from body; storage attribution is not permission to analyze it. |
| Native destination link | review-cases `native_link` | URL outside body retained; AHAS link extractor cannot consume it directly. |
| Title-only unknown body | review-cases `title_only` | `partial`, not empty/complete body. |
| Partial/truncated | review-cases `redacted_partial`; mixed-platform `partial_1` | Explicit reason and state. |
| Removed, retained archive | review-cases `removed_archive` | Lifecycle and availability independent; no lossless AHAS status. |
| Deleted/unavailable | mixed-platform `deleted_1` | Null actor, no fabricated original prose. |
| Fully redacted | mixed-platform `redacted_1` | Empty parts + not_applicable; no placeholder text. |
| Known empty/media-only | mixed-platform `media_1` | Source explicitly reports no caption. |
| Empty snapshot | empty-bundle | Zero-byte records file, declared source/scope; zero supplied rows proves no source completeness. |
| Anonymous retained text | hostile-and-identity `anon` | Actor null, attribution unknown. record_actor without actor refuses. |
| ID beyond JavaScript safe integer | mixed-platform numeric-looking ID | String kept exactly; JSON numeric ID/unsafe integer refuse. |
| Equal local IDs on different sites | minimal and hostile-and-identity `812`, plus namespace/key-field tests | Full key comparison; no numeric or case/Unicode normalization. |
| Handle-only identity | review-cases `handle_actor`; handle tests | Account label capture-scoped; handle event IDs refuse. |
| Source-local identity | review-cases source-bound record; local-key tests | Unknown original site represented by intake authority; nonempty source locator, no inferred cross-capture deduplication. |
| Repeated capture / unresolved conflict | review-cases four `repeated` observations from two descriptors | One distinct supplied key; no selection or last-write-wins. |
| Explicit edit | mixed-platform two `edited_1` observations | One logical record with supplied edit metadata. |
| Identical text, separate events | review-cases `same_text_1` / `same_text_2` | Two distinct keys remain; no text deduplication. |
| Date-only / uncertain / nanoseconds | uncertain-time four cases | Date/interval/unresolved display preserved; no midnight/current-time substitution. |
| Unknown language | minimal and mixed-platform | `und`, unknown; English website not a language declaration. |
| Scope / retrieval / source totals | review-cases two coverage declarations + rounded total | Descriptors retain different acquisition context; no computed completeness percentage. |
| Unknown permissions / omitted raw | omitted-raw and optional-metadata tests | Hash/length/path may be null; no license or source verification inferred. |
| JCS restricted profile | canonical known-answer tests, runner Python/Node vector | ASCII keys, scalar strings, exact integers; floats/exponents/surrogates/duplicate keys refuse. |
| File/hash/path integrity | manifest, path, raw, canonical and multishard tests | Digests bind bytes; traversal/symlink/unlisted files/duplicate observations refuse. |
| Opaque extensions | review-cases `opaque_extensions`; transform test | Status-looking objects do not become core timestamps. |

The checker reports supplied observations, distinct keys and keys with repeats, separately from profile observations. It never returns “posts ever made”, a verified account identity, estimated unseen records, completeness percentage, source authenticity or scientific eligibility.
