# Adoption report — AHIF 0.1.1

**Adopt the reviewed 0.1.1 draft as this repository's evidence destination contract.** The supplied 0.1.0 proposal, examples and receipts remain historical. Production AHAS 1.0.4, input schema versions 1.0.0, numerical settings, studies and private evidence are unchanged. AHIF JSONL is deliberately not accepted as direct AHAS input.

## Minimum incoming normalized record

A row supplies the exact format version, observation hash, compound logical record key, source ID, observed/created/updated time objects, nullable actor, kind (unknown allowed), lifecycle/edit state, visibility, content and provenance. Content declares availability/completeness/reason plus ordered parts. Each retained part has an ID, role, attribution, format, exact text, fidelity and language (`und` may be unknown). Provenance names the normalizer/version, local evidence locator and declared transformations; these are intake metadata, not facts the original site must reveal.

Unknown author, creation/observation time, language, lifecycle, revision and source completeness are valid. A contributor must not invent them. IDs are strings and include site/collection scope. If no native contribution identity exists, a source-local locator permits storage without claiming cross-capture continuity. Observation hashes identify normalized observations; posting-event selection uses logical keys. Text equality does not collapse different events.

A minimal bundle still has only `manifest.json` and `records.jsonl` (which can be empty). The manifest supplies a dataset label, source descriptors, explicit coverage for each source and actual file hashes/sizes/counts. Descriptors may report unknown times/access/redistribution and have no origin or artifacts. Raw evidence is optional. Coverage may say unknown; validation never computes a completeness percentage.

## Optional information

Account/profile observations, source origin, original raw bytes/hashes, native type, title/quote/signature parts, context, parent/repost references, native links, observed metrics, field coverage and namespaced extensions may be retained when supplied. Missing parents do not need stub rows. Profiles and repeated captures never become additional posting events. No source verification, consent or dataset license is fabricated. Fictional fixtures contain no private exports, credentials or source-account mappings.

## Review outcome and next work

The [case matrix](REVIEW_MATRIX.md) covers the requested examples without a new mandatory module/file. The [change log](CHANGES.md) records concrete 0.1.0 ambiguities and checker gaps, and the [field dictionary](FIELDS.md) and four schemas define their versioned corrections. Fresh execution results and limitations are in [checks/verification.json](checks/verification.json); historical pass counts are not new production evidence.

Next, separately authorize and implement one source-specific normalizer, a versioned selection/projection receipt and the [AHAS field map](AHAS_COMPATIBILITY.md). That work must test raw fidelity, actor/event identity, quote/markup boundaries, conflicting observations, exclusions and unchanged-engine input/output behavior. Source acquisition and any scientific pilot remain separate decisions. This adoption delivers a validated storage contract; it does not create analysis-ready histories or establish cross-platform analytical validity.
