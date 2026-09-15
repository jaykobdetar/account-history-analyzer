# Fixed chronological design: feasibility result

The registered design does not support the intended two matched account blocks in each of three strata using the existing approved metadata. Across all 101 monthly cuts per stratum, maximum compatible block capacity is **0 academic, 1 physics, and 0 math**. No final cohort was selected, and no new writing-comparison scores were computed.

The search kept the registered constraints: 180 days on each side of a shared cut, comments with 20–500 eligible words, nearest-cut whole-record prefixes reaching both 5,000 words and 40 comments, at most 5,500 words and 200 comments per cell, a maximum 30-day span among all four corresponding-period cell medians in a block, and maximum all-eight-cell word/count ratios of 1.10/1.25. It excluded the 57 protected/private identities and all 60 accounts scored in pilot3. Capacity-only exposure remained separately flagged and permitted.

| Stratum | Cuts examined | Largest number of accounts with four volume-qualified cells at any cut | Largest number passing internal matching gates at any cut | Cuts with any compatible account edge | Maximum disjoint blocks | Required blocks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AskAcademia / GradSchool | 101 | 4 | 3 | 0 | 0 | 2 |
| AskPhysics / Physics | 101 | 9 | 4 | 3 | 1 | 2 |
| learnmath / math | 101 | 9 | 3 | 0 | 0 | 2 |

Each maximum in this table is calculated separately over the registered cuts; the maxima need not occur at the same cut. Volume-qualified accounts existed at 60 academic, 29 physics, and 70 math cut dates. Thus the deficit includes the matching constraints, rather than simply the absence of any accounts with enough writing.

The physics calendar optimum is 2017-11-01 under maximum matching cardinality, then minimum exact normalized cost, then earliest cut. At that cut, nine accounts had four volume-qualified cells, three passed their internal gates, and one compatible edge remained. The exact minimum matching cost is 43876193/77760000. In the zero-block strata, the summary's 2010-01-01 date is the earliest all-zero matching tie; it is not a usable cohort date or a claim that later dates lacked volume-qualified accounts.

All 303 cut rows are preserved in [JSON](../inventory/feasibility-01/all-calendar-cuts.json) and [CSV](../inventory/feasibility-01/all-calendar-cuts.csv). The [summary](../inventory/feasibility-01/feasibility-summary.json) records plan, implementation, registration, exclusion, and input hashes. Original identities, selected-record metadata, and the limited feasibility witness remain private; they are not a final cohort or contamination clearance.

The implementation and independent suites passed 43 synthetic tests before the [pre-run registration](../protocol/FEASIBILITY_RUN_01_REGISTRATION.json). Tests cover exact band and budget boundaries, the conjunction of the word and comment floors, full block date/volume gates, unrestricted matching against an exhaustive oracle, exact rational costs, cross-stratum disjointness, exclusions, binding refusal, and resource-cap failure reporting.

The actual run processed 931,515 metadata rows from the two hash-bound files, totaling 226,521,186 input bytes. It retained 477,325 eligible records and 38,768,529 eligible words for the six registered communities after the exclusions and record-word cap. It finished successfully in 11.13 seconds externally measured wall time, with 569.52 MiB peak child RSS; the [execution receipt](../logs/feasibility-run-01.receipt.json) preserves the measured values and command. The process ran with network denial, a 600-second limit, and a 4 GiB address-space cap. It made zero source-archive reads, downloads, preprocessing calls, or style-distance calls.

This is a deficit under the frozen grid, prefix-selection rule, and matching gates. It is not a proof that every conceivable chronological design is impossible. No lower word/comment threshold, wider time band, different cut grid, relaxed matching tolerance, previously scored-account reuse, or additional acquisition was adopted. A different design requires an explicit prospective decision before another feasibility run or any scoring.
