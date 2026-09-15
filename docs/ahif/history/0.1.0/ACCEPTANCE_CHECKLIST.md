# Format-implementation acceptance checklist

These are intended requirements for a later production implementation. The supplied fixture checker implements only its documented subset; read `checks/verification.json` for what was actually executed.

## Contract and fidelity

- Reject unsupported versions, unknown core fields, duplicate JSON keys, malformed UTF-8, invalid scalar Unicode, nonfinite/floating numeric tokens and out-of-range integers.
- Preserve decoded source strings exactly across serialization, including CR/LF, leading/trailing spaces, curly punctuation, combining sequences, emoji and literal backslash escape text.
- Do not split JSONL on Unicode separators inside strings. Do not treat a missing field, null, empty text, known absent text, deleted text and redacted text as interchangeable.
- IDs from distinct namespaces/collections remain distinct; long numeric-looking IDs remain strings. Handles are explicitly weaker than native IDs. Anonymous/guest labels cannot combine unrelated people.
- Source-local keys remain source-local and cannot be deduplicated across captures solely from repeated wording.
- Each cited original locator is checked against the supported real input format by its eventual normalizer. A matching digest is not enough to claim original field fidelity.

## Observations and chronology

- Several observations of a native contribution count as one logical record for unique-record inventory, while all allowed observations remain inspectable.
- Two separate events with identical text remain two events. Pure share actions have the sharer's time, not the original object's time.
- Date-only, unknown-offset, interval and sub-microsecond times stay distinguishable. Never manufacture midnight, midpoint, UTC or posting time from acquisition time.
- Unknown edit state remains unknown. A changed observation is not automatically an edit, and a failed re-fetch is not automatically deletion.
- Contradictory evidence produces a visible conflict for later selection; it must not be silently resolved by highest engagement, majority vote or latest import order.
- The later projector selects at most one observation per event and records every choice/exclusion. Changing import order does not choose a different revision implicitly.

## Content ownership and structure

- Preserve a quote-post's commentary separately from embedded text. Pure reposts cannot assert actor-authored commentary. Unknown attribution remains unknown.
- Retain raw markup/dialect/fidelity, distinguishing source fields, rendered text and transcription. Unsupported formats remain data rather than being mislabeled Markdown.
- Keep title, body, quoted text, signature, code, captions, link previews and interface text distinguishable when the source establishes the distinction.
- No record concatenation to meet scientific minimums. No artificial cross-gap word/character sequences when later projecting multipart text.
- A post's native destination and source-provided expanded URL remain metadata, not added body text. Explicit link occurrence identity prevents label double counting.
- Validate half-open code-point spans against exact named part text. Never silently interpret UTF-16 positions as code-point positions.
- Account biographies are profile observations, not posting events. Context-only records from other accounts cannot leak into the target account's text/activity.

## Evidence, coverage and privacy

- Verify supplied file lengths/hashes and references independently of a source-authenticity status.
- Source capture time, acquisition time and normalization-run time remain separate. Dataset selection and acquisition changes must be visible.
- Declared scope/completeness is not inferred from successful parsing, an empty next page or matching an unexplained displayed count.
- Missing context/link/relation arrays do not become confirmed negative observations. Incomplete lists must not acquire exhaustive status.
- Keep reported contribution totals, actual unique captured records, available bodies and analytical sample sizes separate.
- Do not execute embedded markup, follow URL references, load remote schemas, process credentials or expose private exports automatically.
- Bounded archive extraction, symlink/path protection, nesting/string/row limits and decompression limits must be tested before an untrusted-ingestion service exists.
- Withdrawal/deletion processes invalidate dependent material where needed; content hashing must not imply mandatory indefinite retention.

## Compatibility and outcome claims

- Do not modify the frozen engine while testing this format. Use explicit later source/projection profiles and a complete loss/availability receipt.
- Unsupported native record types or text/time formats produce a reason, not a dishonest fallback type or silently altered text.
- Separate structural validity, evidence checks, projection compatibility, runtime completion and scientific accuracy in output statuses.
- New normalizer/profile versions and source-selection changes have visible identities. Schema drift cannot silently change stored semantics.
- Source-specific round-trip fixtures and existing AHAS fixture equivalence tests belong to the future converter milestone, not a claim made by this design package.
