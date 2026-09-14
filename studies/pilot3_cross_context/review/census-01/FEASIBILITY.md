# Score-free feasibility result: census-01

**Gate A status: failed_capacity. No new style scores were computed.**

The proposed calendar grid supports 4 disjoint two-account blocks (8 account slots), against a target of 30 blocks/60 accounts in three strata. These counts precede shared-thread/content filtering and ordinary method qualification; they are ceilings on usable final study capacity. No final cohort was selected and no reduced design is approved.

| Proposed stratum | Calendar scheme | Four-cell accounts | Disjoint blocks / target |
|---|---|---:|---:|
| ApplyingToCollege / Cornell | matched2017_2018 | 0 | 0 / 10 |
| ApplyingToCollege / college | cut2016 | 9 | 4 / 10 |
| Cornell / college | matched2017_2018 | 0 | 0 / 10 |

## Source and exclusion evidence

The fresh source scan read 1,997,146 unique original records in 3 archives. It found 117,577 nonexcluded account keys with comments; 472 had at least 16 present timestamped comments in each of two communities. This necessary prefilter cannot exclude an account capable of supplying two eight-record cells in both communities. Provider speaker totals are not used as complete-history counts.

Exactly 57 known source-account identities are excluded: 12 pilot 1 accounts, 24 scored pilot 2 paired accounts, 12 protected reserve accounts, eight chronological accounts (including failed attempts), and the private export account. The last identity comes from the historical export filename; private prose was not reopened. A further 145 previously capacity-inspected but unscored identities are flagged, not silently treated as scored or excluded to manufacture scarcity. Reserve writing/features were not inspected for this design.

The frozen preprocessor ran on 142,821 comments; 83,953 met its record guard and contained 5,954,075 retained word tokens. English is an unverified corpus-level assumption. Raw text length was never substituted for eligible words. All relevant candidate records are accounted for in private metadata, with source-line hashes, record IDs, times, retained word counts and exclusion reasons. No original prose is exported by the census.

## Dates and what the bounds mean

- ApplyingToCollege / Cornell: early [2017-01-01, 2017-10-01); late [2018-01-01, 2018-10-01), UTC.
- ApplyingToCollege / college: early [2008-01-01, 2016-01-01); late [2016-01-01, 2018-11-01), UTC.
- Cornell / college: early [2017-01-01, 2017-10-01); late [2018-01-01, 2018-10-01), UTC.

All four tested schemes are preserved in `period-capacity.csv`. Every cell uses the same dates within its stratum. The 2,000-word/eight-record requirement applies independently to all four cells of each account. The all-history bound instead requires at least 4,000 eligible words and 16 eligible records per community over all observed dates. It is only a necessary condition for two disjoint periods. Even that bound cannot establish feasible shared calendar cells. Neither a provider account count nor all-history volume is a substitute for matched-cell capacity.

## Interpretation and next gate

This is evidence about input feasibility, not evidence for or against cross-context discrimination. Cross-community ordering, its within-community difference, method sensitivity, omission coverage, ROC-AUC/AP and uncertainty are not estimated here. Shared-thread/content audits, final 60-account selection, scored inputs, Gate B registration, scoring and canonical scoring replay have not run. Missing strata remain missing.

Production feature extraction, masking, vocabulary, distances, guards, optimizer and resource limits remain frozen. The census uses installed AHAS 1.0.4 with the required fingerprint/configuration; the stale editable 1.0.0 metadata was resolved through an isolated noneditable wheel installation. See the environment evidence and command receipts.

These archives are historical convenience samples with incomplete histories, missing/deleted writing, unknown edits, unverified language and coarse community contexts. Their known source-account labels do not establish human authorship, bot/human identity, account takeover or cross-platform accuracy. Corpus redistribution rights were not inferred; archives, source-account mappings and per-record provenance remain private.

## Observed resources

Two source passes completed in 148.17 seconds with 261.11 MiB peak RSS. Private metadata output occupied 63,147,321 bytes. The run completed within its predeclared bounds. Operational receipts retain actual commands, exit codes, wall time and artifact hashes. These successful receipts are fresh census runs, not scoring reruns.
