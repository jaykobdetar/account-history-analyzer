# Pilot 5: one shared anchor, four full chronological histories

This exploratory protocol is frozen before five-sample enumeration and any Pilot5 corpus chronology scores. A separate selection registration binds the exact source inputs and construction code; a subsequent execution registration binds the selected four histories, code, environments and checks. Pilot4 and its zero-block result remain unchanged. Pilot5 must execute the ordinary full analyzer on all four selected histories, preserve failures, and report observed results.

## Source construction and selection

Use only the **2,252 audited survivors from the existing 2,447-record Pilot4 candidate pool**, retaining all its content/thread/historical purges. Source selection performs no acquisition, fresh preprocessing, refill or source-text editing; subsequent full analyses retain their ordinary preprocessing. The seven previously allocated accounts and three fixed pair dates remain: AskPhysics/Physics at 2017-11-01, linux/linuxquestions at 2015-03-01, and programming/learnprogramming at 2012-03-01, all UTC. These are previously examined metadata and audited writing, not a fresh held-out cohort. All 117 earlier protected/scored account exclusions remain effective.

For each direction, A/B are distinct source accounts and X/Y the two communities. Select exactly five disjoint source samples: **A/X early** as the common anchor, followed by four late samples A/X, B/X, A/Y and B/Y. Do not require the three unused reciprocal early samples. Enumerate all ordered account pairs and both community directions in each retained stratum: four physics, twelve Linux and four programming directions, **20 total**. Preserve every direction and its availability/gate result.

Reuse the fixed nearest-cut whole-comment prefix rule on survivors. Early lies in `[T−180 days,T)` and late in `[T,T+180 days)`. Records have 20–500 frozen retained words. Order by distance from T, timestamp, then original ID; stop when both 5,000 words and 40 records are reached. Exceeding 5,500 words or 200 records makes the prefix unavailable. Restore canonical timestamp/ID order for input; do not split, pad, retime or skip comments to repair a prefix.

A valid direction requires all five prefixes, maximum/minimum word ratio ≤11/10 and record ratio ≤5/4 across those five samples, and a median-date span ≤30 days across the **four late samples only**. The single early anchor is not compared with unused early cells. Independently reconstructed whole-record primary windows must give **at least eight qualified windows in each of the four histories**. This is metadata adequacy, not evidence of measurable feature variation or a guaranteed detected boundary.

Choose the valid direction with minimum exact rational cost:

`sum over 6 late-sample pairs |median difference|/(180×86400)`

`+ sum over 10 five-sample pairs |word difference|/5000`

`+ sum over those 10 pairs |record-count difference|/40`.

The early anchor's date is absent from this cost; its volume contributes. Break exact ties by stratum ID, then the full SHA256 of casefolded A, then casefolded B, each prefixed by UTF-8 `pilot5-anchor-order-v1` and one NUL byte, then literal corpus-community X and Y in lexicographic order. No scores, analyzer change candidates, features or favorable grid localization enter selection. If enumeration has no valid direction, retain that explicit failure; do not silently alter this rule.

## Four actual analyses and fixed outcomes

| History | Early sample | Late sample | Constructed switch truth |
| --- | --- | --- | --- |
| Continuity, same community | A/X | A/X | None |
| Switch, same community | A/X | B/X | Junction k |
| Continuity, changed community | A/X | A/Y | None |
| Switch, changed community | A/X | B/Y | Junction k |

Here k is the number of anchor records, the zero-based position of the first late record. All four inputs share the exact anchor apart from their uniform account alias. Preserve source text, original IDs, times, community, thread and other record fields. The only changed field is `account_id`, uniformly set to that history's alias. Bind inputs, manifests, metadata, original-source provenance, audit and selection before execution. Independently check all 20 directional results, the winner, five samples and four input memberships without recomputing writing features.

Execute unchanged **AHAS 1.0.4 ordinary full `analyze`**, including all normal modules and sensitivities. The fixed primary is the pooled-comments surface/function-word temporal method: the release's standardization, L2 PELT search, primary 1,000-word/eight-record windows, minimum segment length three and `log(N)` penalty remain unchanged. Preserve complete canonical output privately. Read primary windows by the exact ordered IDs declared by the primary summary, including the remainder; sensitivity rows can share a stream ID and cannot replace the primary result. Confirm installed bytes, configuration and dependency identity in each execution environment.

Keep **τ=10 supplied-record positions, inclusive**. Convert a production bounding-record interval `[a,b]` once to split interval `[a+1,b]`; its error from k is zero inside the interval and distance to the nearest endpoint otherwise. Report candidate occurrence anywhere and candidate count separately from switch localization within τ. Also report exact containment, nearest-candidate error, best error attainable on the legal window grid, excess over that best error, grid attainability and timestamp/record resolution. Enumerate legal boundaries after qualified windows `j=3,…,N−3` only for N≥8; do not snap truth to that grid. Continuity junction alignment is a separate diagnostic, not positive switch truth.

Preserve per-history full-pipeline/native status and reasons. A successful native `no_measurable_variation` is an **executed zero-candidate result**. An unavailable or nonzero full run has null candidate/localization outcomes even if partial artifacts exist. An executed switch with no candidate has false match and null nearest error. Metadata-supported resolution remains separately labeled. Do not tune, substitute sensitivities, increase tolerance, omit unsuccessful histories or replace the source direction after seeing outputs.

## Execution limits, replay and interpretation

Use socket-denied offline workers: **two parallel histories, 600 seconds and 4 GiB address space per analyzer case, 3,600 seconds per dispatch, and 8 GiB for original-plus-replay artifacts**. Retain the ordinary 512-MiB per-case artifact envelope and 630-second outer worker cleanup guard. Preparation uses 600 seconds, 4 GiB and a 64-MiB private-output ceiling. Preserve every attempt and limit failure; these ceilings do not authorize repeated selection or analysis.

Run all four original histories with `PYTHONHASHSEED=0`, `TZ=UTC`, then replay **all four** in fresh processes with byte-identical relocated inputs/manifests, `PYTHONHASHSEED=73129`, `TZ=Pacific/Honolulu`. Use the same unchanged installed package. Compare every canonical output by bytes/SHA256, excluding exactly `ingest_receipt.json` and `run_receipt.json`. Report replay equality separately from analytical availability. Independently reconcile saved primary windows, interval arithmetic, outcomes and comparisons; do not run a replacement detector.

This is **one experimental unit with a shared anchor and four related outcomes**, not four independent replications. It is nonreciprocal and exploratory. Report per-history results and common-anchor condition differences descriptively, with no bootstrap, IID intervals, p-values, population accuracy or causal claims. Source-account labels do not verify human authorship, continuity of one person's style or a takeover. Report actual sample dates, volume differences, long-comment contribution, remaining contextual mismatch and prior Pilot4 exposure. Available-content auditing leaves 17 unavailable historical bodies and other unobserved relationships unknown. The final report must distinguish detection, localization, attainable resolution and abstention, including unfavorable results, and retain the original Pilot4 conclusion.
