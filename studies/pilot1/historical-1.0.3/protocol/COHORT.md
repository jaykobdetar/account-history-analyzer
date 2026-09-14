# Frozen Cornell account-proxy cohort

Protocol: ahas-realworld-cornell-account-proxy-v1. Frozen UTC: 2026-09-14T11:37:43.000844Z.

No style distance, change candidate, or outcome has been calculated by preparation. No selection will be adjusted after scoring. AHAS 1.0.3, all method definitions, resources, and default guards remain unchanged. No threshold is trained.

Source archive SHA-256: `f153a56a343e6d9568d90b635d44d1ccca71479ac19cd28e075587485bad715d`. Corpus version 0; original 74,467 rows. Exact member hashes, configuration/implementation identity, selected IDs and dataset hashes are in `cohort.json`.

## Selection fixed before scoring

Use unique source comments only. A source submission is identified by root==id and reply_to==null; these tests agree for every source row. Remove placeholder account keys (null/blank or [deleted], [removed], [unknown], [missing]) and non-present text. Empty strings are present observations. No language detector, score, word-count guard or style measurement selects accounts.

Partition an original account by SHA256("ahas-realworld-v1:author:"+account) interpreted as a big-endian integer: remainder 0 modulo 3 is development; otherwise evaluation. Independently partition each whole original thread using "ahas-realworld-v1:thread:"+root. Retain only comments where account and thread partitions agree. Then remove every candidate comment whose exact normalized source text occurs in both splits. Normalization is NFC after CRLF/CR to LF; preserve case and all other whitespace. This selection-only rule is separate from analytical reuse methods.

Within each split rank accounts by descending remaining present-comment count, then ascending full account hash. Select 4 development and 8 evaluation accounts. Sort each selected account by actual integer creation timestamp then original record ID; retain the earliest 400 at most. Alias metadata is "cornell-" plus the first 20 hexadecimal characters of the same account hash. Never use account hashes or names in feature calculations.

## Paired units and fixed missingness arms

For each account, let n=min(100,floor(retained_record_count/2)). Early uses the first n records and late the last n; their IDs are disjoint. Same-account pairs compare these units. Different-account controls use an alias-sorted cyclic ring within each split: account A early versus next account B late. This yields 12 same-account and 12 different-account pairs. The schema labels same_author/different_author are explicitly account-ID proxies, not verified human authorship.

Each arm is a separate dataset, preserving baseline unit and pair IDs. Full keeps the early/late unit. first8 keeps its first 8 chronological records. hash50 keeps original IDs whose SHA256("ahas-realworld-v1:mask:"+id) integer is even; retention is approximately 50%, not exactly 50%. middle50_removed removes floor(n/2) consecutive middle records, starting at floor((n-floor(n/2))/2). All surviving records retain original order, wording and UTC times. Never replenish records to satisfy guards.

Twelve evaluation datasets predeclare retained_prose cosine n=4 (primary), function_mask_v1 cosine n=4 and function-word Jensen-Shannon (secondary), across those four arms. Every frozen_threshold is null. Default comparison guards remain 1,000 retained words and 8 eligible records per side; complete stream default windows/changes also remain unchanged. Report score overlap, rankings and actual abstention; no corpus-wide accuracy claim.

## Provenance, grouping and limits

Full account files are bounded sampled Cornell comment streams, not complete accounts. Source text and record IDs are exact; integer Unix seconds convert exactly to UTC. Thread and reply IDs are preserved. If the source archive contains a parent, its actual creation timestamp supplies parent_created_utc even when the parent is outside the account sample. Missing parents remain null. No edit metadata exists here, so edit_state is unknown. Corpus English is an explicit unverified assumption; manifests declare sampled coverage and retain unknown gaps.

Evaluator groups use account alias, actual selected thread IDs, original comment IDs as source_document, and account alias as related_sample. These groups are checked disjoint across development/evaluation for every arm. No near_duplicate_cluster values are invented: that dimension remains not_auditable. Original account mappings and source-line/text hashes are evaluator-only in inputs/public/source-map.json. Public source text is not copied into protocol summaries.

Prepared 3362 distinct records in 4374802 bytes of public preparation artifacts; below 10,000 records and 50 MiB. Each dataset's complete unique source-file plus dataset bytes is checked separately. No reduced guards or changed defaults.

| Split | Rank | Alias | Comments before cap | Selected comments | Records per early/late unit |
| --- | --- | --- | ---: | ---: | ---: |
| development | 1 | cornell-d9b97c556976bc362f36 | 135 | 135 | 67 |
| development | 2 | cornell-9f55cc9a5bd6e7e492cb | 118 | 118 | 59 |
| development | 3 | cornell-aace307097328019cc11 | 73 | 73 | 36 |
| development | 4 | cornell-9cd0240931d106c5857f | 66 | 66 | 33 |
| evaluation | 1 | cornell-6e9168d005b3c484038b | 690 | 400 | 100 |
| evaluation | 2 | cornell-463ca2188f079b5ee7f3 | 646 | 400 | 100 |
| evaluation | 3 | cornell-ac5c3d0db88aeeabab62 | 635 | 400 | 100 |
| evaluation | 4 | cornell-acaa1ca858f6c690fd71 | 533 | 400 | 100 |
| evaluation | 5 | cornell-6a157f6dc8f76021b0de | 394 | 394 | 100 |
| evaluation | 6 | cornell-7be713a7213d7e24c81c | 373 | 373 | 100 |
| evaluation | 7 | cornell-59640f33b1f68427439f | 346 | 346 | 100 |
| evaluation | 8 | cornell-477fd5bdee3213ea8c97 | 257 | 257 | 100 |

The small development streams are retained as selected. Joint partitioning disproportionately removes their comments; possible abstention is an expected review finding, not a reason to select replacements.

## Limitations

- Corpus account-ID equivalence is a proxy, not verified person or authorship identity.
- English is a corpus-level operational assumption, not per-record language verification.
- One historical university community is not representative of Reddit or the personal history.
- Joint author/thread splitting and activity ranking create strong selection bias.
- Retaining earliest 400 comments per account deliberately omits later history.
- Near-duplicate cluster grouping is absent and therefore not fully auditable.
- Exact duplicate exclusion uses NFC plus LF over whole source text; it is not semantic or near-duplicate filtering.
- Shared samples and related pairs are dependent; pair counts are not independent subject counts.
- No threshold is trained; no authorship, bot, takeover, or AI-text accuracy is established.
- Corpus-specific redistribution license was not specified in the reviewed official sources.

Official provenance: [Cornell corpus documentation](https://convokit.cornell.edu/documentation/subreddit.html), [ConvoKit paper](https://aclanthology.org/2020.sigdial-1.8/), and [Pushshift paper](https://ojs.aaai.org/index.php/ICWSM/article/view/7347). Archive acquisition metadata is recorded separately in logs/public-download.json.
