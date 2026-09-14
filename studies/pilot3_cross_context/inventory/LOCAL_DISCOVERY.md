# Local source discovery and account exclusions

The bounded discovery found three previously authorized local ConvoKit archives: Cornell, ApplyingToCollege and college. Fresh compressed-file hashes match prior receipts. A fresh direct metadata pass counted the source records rather than relying on provider account totals.

| Archive | Compressed bytes | Source rows | Comments | Calendar coverage, UTC |
| --- | ---: | ---: | ---: | --- |
| Cornell | 11,186,877 | 74,467 | 63,723 | 2009-06-22–2018-10-31 |
| ApplyingToCollege | 155,300,755 | 1,148,299 | 1,027,292 | 2013-10-04–2018-10-31 |
| college | 133,664,381 | 774,380 | 663,790 | 2008-03-21–2018-10-31 |

Together these contain 1,997,146 source rows, including 1,754,805 comments. The archives total 300,152,013 bytes and their uncompressed utterance members total 1,219,854,895 bytes. The checked identifier, account, thread and timestamp fields are present throughout; comment parent identifiers are also present. Presence does not establish thread independence, eligible word counts or complete account histories.

The [discovery receipt](local-discovery.receipt.json) records the executed metadata command, the archive-hashing excerpt, hashes, source counts, successful exit codes, observed tool telemetry, and sanitization. Process wall time and peak memory were not captured for the metadata pass and remain null. Tool waiting durations are retained as such; they are not substituted for process wall time. The archive loop was part of a combined successful command, and its recorded duration covers that combined command.

This metadata pass is an additional source read performed during discovery. It is separate from the subsequently planned two-pass feasibility census and does not count as either census pass. No preprocessor, feature scoring, style distance, boundary search, cohort selection or download ran in this discovery pass. JSON decoding loaded source rows, but only identity/time/thread metadata were queried; source prose was not examined to design the study. Protected reserve writing and feature vectors were not inspected.

## Exclusion policy

The private mandatory manifest contains **57 distinct account identities**: 12 from pilot 1, 24 scored pilot 2 paired accounts, 12 protected pilot 2 confirmation accounts, eight chronological accounts including failed-attempt populations, and the user's private export account. The latter identity is derived from the prior conversion receipt's export filename; no additional private profile tables were opened.

All identities use case-insensitive source-account matching. The private manifests bind the exact metadata sources and hashes. The earlier paired preparation and registered preparation contain the same 36 selected identities. Chronological accepted/provisional populations contain the same eight identities used in scored attempts. Completeness is asserted for these known local pilot sources, not every possible unrelated experiment on the machine.

The original conservative manifest contains **202** identities. Its additional **145** accounts were inspected for writing capacity or eligibility previously, but were not thereby scored. They are disclosed separately in `prior_capacity_only_accounts` in the private mandatory manifest. Primary feasibility must use the 57 mandatory exclusions. A strict 202-account exclusion analysis can be reported as a sensitivity check; it must not be substituted for primary feasibility or used to create artificial infeasibility.

Private manifest SHA256 identities:

- Original conservative manifest: `a2ad340a0092a2b15b13703a7d19d2615d420eea3f7adc79d0c35c0583b545d3`.
- Mandatory manifest: `cce9c7980e8cee909318051a934eb99815ad0e5df8707e07026a08ffc3cad660`.

Both manifests remain outside the public repository, with file mode 600 and parent mode 700. The original manifest is preserved. No usernames, source-account maps, record IDs, searchable prose or feature vectors are included here.

## Source limits

No noneducation corpus archive was located in the bounded relevant Downloads, known workspace and prior AHAS artifact inventory. This does not establish that none exists elsewhere. The prior acquisition receipts authorize local evaluation of these archives; corpus-specific public redistribution licensing remains unestablished. Coverage is historical and incomplete or unknown. English is an operational assumption inherited from prior corpus use, not verified record-level language. Community names alone are not validated topic labels.
