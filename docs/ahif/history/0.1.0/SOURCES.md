# Sources and boundary between fact and design

All AHIF field names, layouts, identity conventions, semantic rules and examples in this package are a new design proposal. The source references below inform particular choices; they do not endorse AHIF or establish it as an existing standard.

## Current project contracts (inspected through the connected GitHub tool)

Repository snapshot: `6f465bd95fa3c12df41235986a96a04cf6c332d0`.

- Record schema: https://github.com/jaykobdetar/account-history-analyzer/blob/6f465bd95fa3c12df41235986a96a04cf6c332d0/schemas/record.schema.json
  Observed Git blob SHA: `2cdbc9e14d7e67dc2365a233dad17fc8104bb054`.
  Supports comment/submission, body/status, optional timestamps/language/subreddit/title/parent/thread/permalink and strict extra-field rejection.
- Snapshot schema: https://github.com/jaykobdetar/account-history-analyzer/blob/6f465bd95fa3c12df41235986a96a04cf6c332d0/schemas/snapshot.schema.json
  Observed Git blob SHA: `793fa04bf05cdef0a41ef6f71803efaf699db396`.
  Binds account, source category, one plain/Markdown text format, default language and declared coverage.

The review did not change the repository or run the engine on AHIF.

## External primary references (checked 2026-09-15)

- JSON Lines: https://jsonlines.org/ — UTF-8, one JSON value per line and LF framing. AHIF narrows each value to an object and requires a final newline for canonical export.
- JSON Schema 2020-12: https://json-schema.org/draft/2020-12 — machine-readable constraints; local `$defs` and references.
- JSON Schema validation vocabulary: https://json-schema.org/draft/2020-12/json-schema-validation — `format` annotation is not necessarily a complete validation assertion; additional calendar and cross-field checks are necessary.
- RFC 3339: https://www.rfc-editor.org/rfc/rfc3339.html — timestamp representation. AHIF explicitly narrows known instants to UTC, records precision, and separately represents uncertain/date-only values.
- RFC 8785: https://www.rfc-editor.org/rfc/rfc8785.html — JSON canonicalization, string preservation and deterministic property ordering. AHIF uses a restricted integer/ASCII-property-name domain so its fixture serializer is not represented as a full JCS implementation.
- W3C Activity Vocabulary: https://www.w3.org/TR/activitystreams-vocabulary/ — useful distinctions among actor, object, attributed content, publication/update and reply references. AHIF is not an ActivityStreams-conformant serialization and requires no JSON-LD processing or remote context.
- W3C PROV overview: https://www.w3.org/TR/prov-overview/ — provenance distinguishes entities, activities and responsible agents. AHIF's small capture/normalizer/locator design is informed by this distinction, not a claim to implement the full PROV model.

Sources are information references only; all format validation is offline. URI strings in schemas, records and citations must not initiate network access.
