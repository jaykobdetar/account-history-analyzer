# Task: review and adopt the common evidence format, not collect data

The owner is defining the destination format before building normalizers for Reddit, X/Twitter and other forums. Use the supplied AHIF 0.1.0 package as a concrete proposed contract. It contains SPEC.md, JSON schemas, complete fictional bundles, a small offline reference checker, selected tests and a compatibility analysis against the existing AHAS schemas.

## Scope

Review the format's field semantics and adopt a coherent versioned contract for this repository. Keep the frozen AHAS 1.0.4 engine, numerical settings, input schemas, previous studies and private evidence unchanged. Do not implement a live collector, browser extension, database backend, arbitrary web scraper, neural model or source-specific converter in this task. Do not run another scientific pilot.

First read SPEC.md and AHAS_COMPATIBILITY.md, then inspect the current actual production input schemas. They differ from the proposed evidence format intentionally. Do not tell the owner the new JSONL already works in AHAS. A later explicit projection is needed.

## Required review

Check that the contract can express a normal post, a reply with an absent parent, an original short post, quote commentary with embedded third-party text, a pure repost, HTML/BBCode forum text, a signature, a native destination link, title-only/partial/removed/redacted/empty text, an anonymous record, numeric IDs too large for a JavaScript integer, equal IDs on different sites, a handle-only identity, repeated captures, edits/conflicts, date-only/uncertain timestamps and unknown language.

Verify the distinction between logical record keys and observation IDs. Repeated observations must not inflate posting counts. Text equality must not merge genuine separate events. Source-local and handle identities must not silently become permanent cross-capture identities. Scope, retrieval provenance and source-reported totals must not create invented completeness percentages.

Review the JCS-compatible restricted JSON profile, domain-separated hashes, file manifests, safe paths and optional raw evidence handling. The reference checker is fixture-oriented and is not advertised as a production untrusted-ingestion service. Fix genuine contradictions between schema, prose and tests in an explicit draft revision. Record every change and rationale; do not silently reinterpret frozen version 0.1.0 examples.

## Deliverables

1. A reviewed specification and machine-readable schemas with stable versions and field definitions.
2. Positive and negative fixtures and runnable validation tests. Preserve existing draft receipts as historical; record actual new execution and limitations.
3. A concise open-issues/change log and the exact supported/non-supported contracts.
4. A future projection map to AHAS's existing fields with per-field loss and refusal rules. This is a contract, not converter implementation yet.
5. A short adoption report: what a minimal incoming normalized record contains, what remains optional, and which future work is necessary to turn it into analysis input.

Focus on practical sufficiency rather than building a universal ontology. Additional modules or mandatory files need a concrete otherwise-unrepresentable example. Do not require every contributor to supply metadata a source does not reveal. Unknown must be a valid outcome. Do not fabricate original timestamps, authorship, source verification, missing prose, consent or dataset licenses.

Keep all examples fictional/public-safe and keep private account exports, raw browser credentials and source-account mappings outside publication. Follow the owner's normal approval workflow for repository writes, commits and publication; this handoff does not itself authorize external actions.

Completion is a coherent validated format contract. It is not a new bot-detection accuracy claim, an implemented collection system or a completed platform port.
