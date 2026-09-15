# Account History Analysis Suite (AHAS)

AHAS is a Python 3.12 library and command-line tool for offline, deterministic analysis of supplied account histories. It measures writing style, content reuse, activity, links and interactions, and reports descriptive chronological change candidates.

The current engine is **1.0.4** and remains frozen. A style distance is not an authorship probability, and a change candidate does not establish an account takeover or its cause. Real-world validation is **not established**.

[Get started](docs/USAGE.md) · [Study results](studies/README.md) · [Documentation](docs/DOCUMENTATION_INDEX.md) · [Development](docs/DEVELOPMENT.md) · [Frozen downloads](https://github.com/jaykobdetar/account-history-analyzer/releases/tag/v1.0.4)

## Start here

- **Run an analysis:** follow the [installation and usage guide](docs/USAGE.md). Supply local JSONL records and a snapshot manifest; AHAS does not fetch account data.
- **Prepare supplied evidence:** [AHIF 0.1.1 and the offline Reddit bridge](docs/AHIF.md) define the separate evidence contract and its limited, explicit projection into AHAS.
- **Read the latest replication:** [Pilot 6](studies/pilot6_shared_anchor_replication/results/REPORT.md) applies the frozen five-sample design to nine new account-disjoint pairs. Its report keeps all four histories together, including every candidate interval, grid resolution, unavailable cases and operating costs. The target was ten pairs; the fixed source/audit rules left a one-pair shortfall. [Pilot 5](studies/pilot5_shared_anchor/review/OUTCOME_REPORT.md) remains the preserved exploratory diagnostic.
- **Understand the evidence:** the [study catalog](studies/README.md) distinguishes completed analyses, the Pilot 4 feasibility stop, and earlier development studies.
- **Maintain the project:** use the [development guide](docs/DEVELOPMENT.md) for source layout, checks, and where new work belongs.

## Quick example

After [installing the locked environment](docs/USAGE.md#install):

```bash
python3.12 scripts/offline_exec.py .venv/bin/ahas analyze \
  --input fixtures/arithmetic.jsonl \
  --manifest fixtures/arithmetic.snapshot.json \
  --config config/default.toml --out my-report
```

Open `my-report/report.html`. This tiny synthetic fixture demonstrates the pipeline and explicit insufficient-data statuses. See [larger synthetic inputs](fixtures/README.md) and [saved report examples](output/README.md). Reports include supplied prose by default; the [usage guide](docs/USAGE.md) explains excerpt omission and replay verification.

## Repository layout

| Location | What belongs here |
| --- | --- |
| [src/account_history_analyzer/](src/account_history_analyzer/) | Frozen analyzer, CLI, reporting, packaged contracts and resources |
| [tests/](tests/), [fixtures/](fixtures/README.md), [design_examples/](design_examples/) | Executable checks, synthetic inputs and comparison/reference examples |
| [config/](config/README.md), [schemas/](schemas/), [resources/](resources/) | Configuration and source copies of packaged contracts/resources |
| [docs/](docs/DOCUMENTATION_INDEX.md), [SOURCES.md](SOURCES.md) | Usage, methods, limits, engineering records and research references |
| [scripts/](scripts/README.md), [containers/](containers/README.md) | Offline execution, maintenance and the frozen reference environment |
| [studies/](studies/README.md) | Six studies, each with its own protocol, sanitized evidence and interpretation |
| [qa/](qa/README.md), [evaluation/](evaluation/README.md), [benchmarks/](benchmarks/README.md), [output/](output/README.md) | Preserved engineering receipts, evaluations, workload and sample reports |
| [provenance/](provenance/README.md), [original handoff](docs/archive/original-handoff/README.md) | Release/import records, cleanup recovery map and archived specification inputs |

Generated distributions are available from the [1.0.4 release](https://github.com/jaykobdetar/account-history-analyzer/releases/tag/v1.0.4). The [cleanup record](provenance/repository-cleanup/README.md) maps removed duplicates and moved documents to their exact preserved copies. Historical receipts keep their original paths and hashes.

The public studies omit raw corpora, private prose, account mappings and prepared real-text inputs. A Git clone supports software and synthetic checks; exact real-text study replay requires the protected inputs bound by each protocol. The AI-text detector is explicitly unimplemented. See [limitations](docs/LIMITATIONS.md) and [LICENSE](LICENSE).
