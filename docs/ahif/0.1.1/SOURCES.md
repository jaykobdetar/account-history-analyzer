# Review sources and evidence boundary

The proposed 0.1.0 package's [original sources](../history/0.1.0/SOURCES.md) and original compatibility analysis remain historical. This local review first read its SPEC.md and AHAS_COMPATIBILITY.md, then inspected actual local production files:

- `schemas/record.schema.json`, `schemas/snapshot.schema.json` and the matching `src/account_history_analyzer/contracts/` copies.
- `src/account_history_analyzer/schemas.py` for local schema resolution and time validation.
- `src/account_history_analyzer/io.py` for defaults, identity, chronology, account and resource constraints.
- `src/account_history_analyzer/text.py` for status/sentinel, language and separate title/body treatment.
- `pyproject.toml` for engine version and runtime dependencies.

The frozen-boundary receipt records actual local hashes. No readable local Git metadata is available; this review does not assert the historical remote commit is the current local checkout.

[RFC 8785, JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785) was checked on 2026-09-15, especially §§3.1–3.2 on string preservation, primitive serialization and property ordering. The reviewed inference is narrow: ASCII property names avoid UTF-16 versus scalar-order differences, and safe integers avoid floating-point serialization differences. Fixed byte/hash vectors and a bounded Python/Node comparison exercise this restricted domain; they are not a general JCS compliance certification.

[RFC 3986, URI syntax](https://www.rfc-editor.org/rfc/rfc3986) defines the generic ASCII absolute-URI component syntax used by namespace/URI-key validation. Source ownership, service-specific scheme semantics and aliases are outside syntax checking. URL-bearing text fields remain inert literal source strings, and are never automatically retrieved.

No external site was queried for account history. No profile, real-account export, credential or account mapping was inspected or included. No new scientific study, live collector, source-specific converter or publication action was performed. Source/profile conventions not established by this review remain explicit future work.
