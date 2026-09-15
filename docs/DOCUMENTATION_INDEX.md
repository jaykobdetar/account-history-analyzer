# Documentation

The current software is **AHAS 1.0.4**, with a frozen analytical baseline. The RW-001 presentation repair is complete. Engineering verification and the five local studies do not establish real-world authorship or takeover validity.

## Use and understand AHAS

- [Project overview](../README.md) · [Installation, CLI and Python API](USAGE.md)
- [Development and verification commands](DEVELOPMENT.md) · [Reference container and offline execution](../containers/README.md)
- [Methods](METHODS.md) · [Limitations](LIMITATIONS.md) · [Design decisions](DECISIONS.md)
- [Configuration](../config/README.md) · [External evaluation input contracts](EXTERNAL_EVALUATION.md)
- [Dependency and license notices](DEPENDENCIES.md) · [Research sources](../SOURCES.md)
- [Deterministic reuse resource accounting](REUSE_RESOURCE_POLICY.md)

## Study evidence

The [study index](../studies/README.md) distinguishes completed analyses, unavailable outcomes and the unscored confirmation reserve across all five studies. Start with each final report; the individual study records remain unchanged.

| Study | Final report | Status |
| --- | --- | --- |
| Pilot 1 | [Historical public-cohort review](../studies/pilot1/historical-1.0.3/review/PUBLIC_REVIEW.md) | Completed on 1.0.3; exposed development evidence. |
| Pilot 2 | [Expanded Reddit evaluation](../studies/pilot2/review/REVIEW.md) | Paired and available chronological analyses completed; sparse cross-community coverage, unfilled slots, confirmation unscored. |
| Pilot 3 | [Cross-community comparison review](../studies/pilot3_cross_context/review/REVIEW.md) | Completed 60-account/30-block comparison study; omission-related unavailable outcomes retained. |
| Pilot 4 | [Strict chronological-control outcome](../studies/pilot4_chronological_controls/review/OUTCOME_REPORT.md) | Zero final eligible blocks; corpus chronology unmeasured. |
| Pilot 5 | [Shared-anchor diagnostic outcome](../studies/pilot5_shared_anchor/review/OUTCOME_REPORT.md) | Four full histories and four replays completed; one exploratory unit. |

These are sanitized review packages. Source-dependent numerical replay requires separately retained private inputs; public protocols and hashes do not contain the omitted writing or identities.

## Release and engineering history

- [1.0.4 RW-001: stored sensitivity-candidate visibility](RW001.md)
- [1.0.3 REPORT-005: reversible character n-gram labels](REPORT005.md)
- [1.0.2 AUD-001–004 repairs](AUDIT_REPAIR.md)
- [Pinned ruptures PR #383 update](PR383.md)
- [Original 1.0.0 engineering execution log](EVALUATION.md) · [Historical implementation checklist](MILESTONES.md) · [Acceptance-to-test map](TEST_MAP.md)
- [Raw engineering and regression evidence](../qa/) · [Measured synthetic workload](../benchmarks/README.md)
- [Arithmetic source report](../output/rw001/arithmetic-source/report.md) · [Renderer regression examples and their constructed-outcome caveat](../output/rw001/synthetic/README.md)

Historical test counts, fingerprints, timings and statements such as “external datasets were not supplied” describe their original release or run. They are not current study summaries or newly executed checks of this checkout. Renderer-only constructed outcomes are not optimizer-validation results.

## Frozen downloads and provenance

Get the original wheel, source distribution, source-and-reports archive and sanitized review bundle from the [1.0.4 release downloads](https://github.com/jaykobdetar/account-history-analyzer/releases/tag/v1.0.4). [Release manifests](../provenance/releases/1.0.4/) retain their exact identities; [GitHub import provenance](GITHUB_IMPORT.md) explains the initial repository snapshot and omitted material.

The [original handoff archive](archive/original-handoff/) groups the preserved `AGENT_PROMPT.md`, `BUILD_SPEC.md`, `ACCEPTANCE_TESTS.md`, `PACKAGE_VALIDATION.md` and `SHA256SUMS.txt`. These are historical specification inputs. In particular, `PACKAGE_VALIDATION.md` describes checks of the pre-implementation package; its “application remains to be built” statement is not the present software status. The original checksum list describes that handoff, not the current checkout.
