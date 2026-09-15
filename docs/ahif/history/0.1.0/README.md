# AHIF 0.1.0 — proposed shared input format

**Account History Interchange Format** is a platform-neutral evidence layer for the Account History Analysis Suite. It is a new draft, not an existing Internet standard or an input the frozen AHAS loader already accepts.

Start with **SPEC.md** for the contract and **AHAS_COMPATIBILITY.md** for the boundary with the existing engine. The format is defined here; collection and source-specific transformation are intentionally later work.

## The short model

- A **record key** identifies the original contribution or action within its source namespace.
- An **observation** records one supplied state of that contribution, with provenance. Multiple observations do not mean multiple posts.
- **Text parts** preserve body/title/quoted/signature content, original format, attribution and language evidence.
- A **source descriptor** explains where the evidence came from. Coverage says how the records were selected and what is missing.
- A later **analysis projection** selects one allowed state per event and makes current AHAS input, explicitly reporting unsupported/lost information.

Minimum dataset: `manifest.json` + `records.jsonl`. Optional: `accounts.jsonl`, raw evidence and additional JSONL shards. No SQL database, network service, embeddings, model or source collector is required by this format.

## Included files

| File/directory | Purpose |
|---|---|
| `SPEC.md` | Field semantics, keys, attribution, time, evidence, coverage, hashes and versioning |
| `schemas/` | Three entry schemas plus locally resolved shared definitions, JSON Schema 2020-12 |
| `AHAS_COMPATIBILITY.md` | Exact current-schema constraints and a proposed projection policy |
| `examples/minimal/` | Complete valid two-file dataset with unknown time/language |
| `examples/mixed-platform/` | Fictional Reddit/X/forum-like records; quote/repost, markup, truncation, deletion and an edit observation |
| `examples/uncertain-time/` | Date-only, unresolved relative, interval and nanosecond timestamps |
| `examples/hostile-and-identity/` | Inert malicious-looking text, Unicode fidelity, namespaced identity and anonymous writing |
| `examples/*-record-readable.json` | Pretty-printed full specimen rows, for reading rather than JSONL ingestion |
| `reference/validate_bundle.py` | Offline fixture-oriented checker; not a production importer |
| `reference/test_format.py` | Executed format and adverse-input checks |
| `reference/build_schemas.py`, `build_examples.py` | Recreate the supplied design artifacts; no collection or conversion of real sources |
| `checks/` | Actual test outcomes, environment and example checks |
| `ACCEPTANCE_CHECKLIST.md` | Contract checks for future implementations |
| `AGENT_PROMPT.md` | Next-agent instruction restricted to format review/adoption |
| `SOURCES.md` | Primary standards and pinned existing AHAS schema sources |

All examples are fictional. They include **20 record observations representing 19 distinct source record keys, plus five optional account observations**. These examples are not sufficient samples for meaningful AHAS style analysis and were not used to claim such results.

## Try the format checker

Python dependencies for the small reference checker are `jsonschema` and `referencing`. This environment used the versions recorded in `checks/verification.json`. Use an isolated environment; installing them is setup, not a network requirement during validation.

```sh
python reference/validate_bundle.py examples/minimal
python reference/validate_bundle.py examples/mixed-platform
cd reference
python -m unittest -v test_format
```

The schema URI is an identifier, not something the checker downloads. All schema references resolve from the bundled files. The checker prints `projection_status: not_performed` and `authenticity_status: not_established` even for valid data.

The actual checks are in `checks/`. Passing these establishes the exercised draft-format rules, not correctness of unimplemented adapters, authenticity of arbitrary evidence, cross-platform author detection or production ingestion security. The current AHAS runtime is not invoked by these commands.

## Keep these distinctions

`unknown` is not false. An empty list is not proof of exhaustive absence. Observed-time is not posting-time. A quote is not the sharer's own wording. An account is not a verified person. A hash is not source verification. A valid record is not necessarily analyzable. Raw strings are not cleaned to satisfy word-count thresholds.

There is no repository write, live collection or production-schema migration in this package.
