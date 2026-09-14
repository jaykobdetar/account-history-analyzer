# Current documentation index

The current software release is **AHAS 1.0.4**. The RW-001 presentation repair is complete; the analytical baseline and PR #383 optimizer remain frozen. Real-world validation is **not established**. The second-pilot confirmation reserve remains unscored.

## Using and reproducing the software

- [Installation, CLI and Python API](../README.md)
- [Digest-pinned reference container and offline execution](../containers/README.md)
- [Methods and named adaptations](METHODS.md), [limitations](LIMITATIONS.md), [decisions](DECISIONS.md)
- [Dependency/license notices](DEPENDENCIES.md), [research sources](../SOURCES.md)
- [Configuration](../config/README.md), [external evaluation interfaces](EXTERNAL_EVALUATION.md)
- [Acceptance-to-test map](TEST_MAP.md), [milestones](MILESTONES.md), [engineering evaluation](EVALUATION.md)
- [Original build specification](../BUILD_SPEC.md), [acceptance contract](../ACCEPTANCE_TESTS.md)

## Repairs and historical evidence

- [1.0.4 RW-001: visibility of stored sensitivity candidates](RW001.md)
- [1.0.3 REPORT-005: reversible character n-gram labels](REPORT005.md)
- [1.0.2 AUD-001–004 repairs](AUDIT_REPAIR.md)
- [Pinned ruptures PR #383 implementation](PR383.md)
- [Reuse resource accounting](REUSE_RESOURCE_POLICY.md)
- [Raw engineering logs and regression evidence](../qa/)
- [Current synthetic and arithmetic report bundles](../output/rw001/)
- [Original 1.0.4 release manifests and packaging receipts](../provenance/releases/1.0.4/)

Old receipts describe their original source and environment. They are not relabeled as fresh executions of this GitHub checkout.

## First-pilot historical context

[The preserved first-pilot public review and protocols](../studies/pilot1/historical-1.0.3/README.md) are exposed development evidence from 1.0.3. Private prose and maps remain omitted.

## Second Reddit pilot

- [Comprehensive interpretation](../studies/pilot2/review/REVIEW.md)
- [Registered protocol](../studies/pilot2/protocol/PROTOCOL.md) and [scoring freeze](../studies/pilot2/protocol/scoring-freeze.json)
- [Data acquisition and inventory](../studies/pilot2/inventory/)
- [Preparation coverage and grouping controls](../studies/pilot2/review/PREPARATION_REVIEW.md)
- [Every paired outcome](../studies/pilot2/review/PAIRED_OUTCOMES.md), [complete observations](../studies/pilot2/review/pair-observations.json), [metric CSV](../studies/pilot2/review/paired-metrics.csv)
- [All chronological and operating slots](../studies/pilot2/review/STREAM_OUTCOMES.md)
- [Measured resource costs](../studies/pilot2/review/RESOURCE_COST.md)
- [Actual command logs](../studies/pilot2/review/COMMANDS.md), [later review commands](../studies/pilot2/review/FINAL_COMMANDS.md)
- [Final independent archive checks](../studies/pilot2/delivery-verification/)

The study files are a sanitized review handoff. They omit raw corpora, the user's export, source-account maps, prepared prose and native source-containing reports. Full numerical replay requires the protected local inputs bound by the protocol; the documentation does not claim that a Git clone alone contains those inputs. Historical absolute paths in command receipts remain evidence of their actual execution locations.

## Frozen downloads and this import

[The private 1.0.4 release](https://github.com/jaykobdetar/account-history-analyzer/releases/tag/v1.0.4) carries the exact working-source-and-reports archive, production wheel, source distribution and sanitized pilot ZIP. This preserves complete historical synthetic report bundles without duplicating large generated outputs in Git history. [Import provenance](GITHUB_IMPORT.md) records what was copied and what stayed local.

The original `AGENT_PROMPT.md`, `BUILD_SPEC.md`, `ACCEPTANCE_TESTS.md`, `PACKAGE_VALIDATION.md` and original handoff checksum list remain historical specification inputs. In particular, PACKAGE_VALIDATION describes the pre-implementation handoff, not the current software status. Current completion evidence is in RW001.md and the second-pilot review.
