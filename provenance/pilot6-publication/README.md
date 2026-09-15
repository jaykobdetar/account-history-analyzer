# Pilot 6 publication receipts

Pilot 6 adds a bounded replication with nine new account-disjoint pairs, 36 main analyses and 36 verified replays. The ten-pair target produced a one-pair source-feasibility shortfall. All eleven unavailable provisional pairs and all unfavorable analyzer outcomes remain in the study record.

The publication baseline is `b86da4fda97c0ccc4a54040d573527e64bd05027`. Existing engine and study files are preserved. Only the repository README, study catalog and documentation index change to link the new study.

- [Publication manifest and preservation check](publication-check.json): exported bytes reconcile with the original source/export manifest; pre-existing repository files reconcile with baseline Git objects, apart from the three navigation documents.
- [Independent lexical privacy check](privacy-check.json): known account/record/group tokens and 15-word candidate-source sequences.
- [Second publication check](privacy-second-check.json): exact quoted identities/group IDs, 16-token source sequences, user links and cache/symlink exclusions.
- [Staged export check](staged-export-check.json): all 237 scanned study files, including intentionally retained log files, are present in the Git index with identical bytes.
- [Verification code](check_publication.py): read-only source/export, baseline and local-link checks. The lexical scanners remain the unchanged Pilot 4 tools.

The checks scan the complete final study export, including its manifest. Their source-free result receipts live outside that export to avoid changing the scanned files. The original [independent results check](../../studies/pilot6_shared_anchor_replication/review/results-independent-check-01.json) and [earlier-study preservation check](../../studies/pilot6_shared_anchor_replication/environment/preservation-final-01.json) remain separate evidence.

Public result files omit original writing, source-account mappings, prepared real-text inputs and full native outputs. Path substitutions and original/published hashes are recorded in the study's `PUBLIC_EXPORT_MANIFEST.json`; executable study code is unchanged. The checks are bounded and do not establish human identity, population detection accuracy or complete independence from unobserved reuse.

Failed synthetic stdout logs retain their original trailing whitespace as receipt evidence. The source/document whitespace check passes when raw `.log` files are excluded; no receipt bytes were cleaned up.
