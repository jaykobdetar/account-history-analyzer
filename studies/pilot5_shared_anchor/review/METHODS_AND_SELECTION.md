# Pilot 5 methods and selection

Pilot 5 is a separately registered, exploratory **shared-anchor diagnostic**. Pilot 4's reciprocal eight-cell design produced zero eligible final blocks, and that result remains unchanged. Pilot 5 uses one earlier sample from source account A in Physics, then appends four later samples: A/Physics, B/Physics, A/AskPhysics and B/AskPhysics. These form the four source-account continuity/switch × same/changed-community conditions. The same earlier sample is reused in every history; reciprocal earlier samples from the other account/community combinations are not required. The four histories constitute **one dependent diagnostic unit**, not four independent replications.

## Frozen source and selection rules

Selection used only the **2,252 audited survivors from Pilot 4's 2,447-record pool**, preserving all 195 purges and the same three community-pair cuts. No new archive, audit, preprocessing or style score was used to select samples. The inherited policy excludes 57 prior-pilot/protected/private identities and 60 Pilot 3 scored identities. One of the two selected accounts carries the permitted prior capacity-only exposure flag; neither belongs to the 117 excluded identities. Source-account labels are dataset proxies, and the inherited English label is a corpus-level assumption. Available-content protection does not establish independence from unavailable or unsupplied writing.

For each ordered account pair and ordered community pair, take one early anchor and four late samples. Each sample uses whole comments of 20–500 retained words, nearest the fixed cut first, until both 5,000 words and 40 comments are reached, with ceilings of 5,500 words and 200 comments. Early is `[T−180 days,T)` and late is `[T,T+180 days)`. Across the five samples, the maximum/minimum word ratio must be ≤1.10 and comment-count ratio ≤1.25. The four later medians must span ≤30 days. The earlier anchor remains subject to its own band and prefix rules; its median is absent from the four-late alignment gate and selection cost.

Every constructed history must independently provide at least eight qualified primary windows. A window closes only after both 1,000 words and eight whole eligible comments; a short final remainder is unqualified. No boundary-grid attainability filter or analysis result enters selection.

The [selection registration](../protocol/SELECTION_REGISTRATION_V1.json) froze the rule before enumeration. All **20 directional candidates** are retained; **three passed**. Candidate **04**, stratum 02, with Physics as X and AskPhysics as Y, minimizes the exact cost:

`sum of 6 late–late median distances / 180 days + sum of 10 five-sample word differences / 5,000 + sum of 10 five-sample comment-count differences / 40`.

Ties use stratum ID, then the A and B account hashes, then the exact X/Y community names. Each hash uses the fixed `pilot5-anchor-order-v1` domain followed by one NUL character and the canonical casefolded account key. The selected direction was fixed before chronology execution; this document does not report its analysis outcomes.

## Selected five samples

The shared cut is **2017-11-01T00:00:00Z**. The five disjoint samples contain **216 unique comments and 25,179 retained words**. Their word ratio is **5133/5005 = 1.025574**, comment-count ratio **47/41 = 1.146341**, and later-median span **329251/14400 = 22.864653 days**. The exact selection cost is **37451111/31104000**.

| Sample | Comments | Retained words | Longest comment: words / sample-word share |
|---|---:|---:|---:|
| Shared early A / Physics | 42 | 5,012 | 490 / 9.78% |
| Late A / Physics | 44 | 5,133 | 451 / 8.79% |
| Late B / Physics | 41 | 5,019 | 314 / 6.26% |
| Late A / AskPhysics | 47 | 5,010 | 394 / 7.86% |
| Late B / AskPhysics | 42 | 5,005 | 293 / 5.85% |

All dates below are original UTC timestamps. The gap is the first later comment minus the last shared-anchor comment; it is a sampling gap, not an estimated change time.

| Sample | First UTC | Median UTC | Last UTC | Gap from anchor end, days |
|---|---|---|---|---:|
| Shared early A / Physics | 2017-10-12T14:03:43Z | 2017-10-18T16:47:57Z | 2017-10-27T16:56:47Z | — |
| Late A / Physics | 2017-11-05T10:18:52Z | 2017-11-17T12:43:05Z | 2017-12-02T18:15:53Z | 8.723669 |
| Late B / Physics | 2017-11-01T01:41:50Z | 2017-11-09T11:58:57Z | 2017-11-22T01:40:55Z | 4.364618 |
| Late A / AskPhysics | 2017-11-04T07:26:24Z | 2017-12-02T08:44:03Z | 2018-01-04T15:10:01Z | 7.603900 |
| Late B / AskPhysics | 2017-11-02T15:04:02Z | 2017-11-14T11:20:59.5Z | 2017-11-29T04:11:16Z | 5.921701 |

The anchor has **42 comments and 5,012 words**. Appending the four late samples yields, in condition order, **86, 83, 89 and 84 supplied comments**, with **9, 9, 8 and 8 qualified primary windows**. Repetition produces 342 supplied-record occurrences across the four histories, while the unique source count remains 216. Original writing and record IDs remain private; creation timestamps are preserved in the constructed inputs. Every history uses one consistent study account alias. Switch truth is the fixed split after the 42nd anchor comment. Continuity uses that junction only as a diagnostic.

## Independent verification

[Twenty-four synthetic tests](../logs/shared-anchor-checker-tests-01.stdout.log) passed before the [independent metadata check](shared-anchor-independent-check-01.json). That checker recomputed the prefixes, gates and costs for all 20 directions and the exact winner from the frozen survivors, then verified the five original record sets, public sample statistics and four history metadata files. It passed in 0.343 seconds outer wall at 132.12 MiB peak RSS, using metadata without accessing source prose or calling a detector. The separately retained source-fidelity check verifies original input preservation.

This report is descriptive documentation prepared after selection; it is not a new preregistration. The [protocol](../protocol/PROTOCOL_V1.md), [complete candidate enumeration](../inventory/prepared-01/candidate-enumeration.json), [sample statistics](../inventory/prepared-01/samples.json), [selection summary](../inventory/prepared-01/selection-summary.json), [independent check receipt](../logs/shared-anchor-independent-check-01.receipt.json), and [source-fidelity check](source-fidelity-01.json) retain the evidence. Analysis outcomes are reported separately.
