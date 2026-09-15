# Develop and verify AHAS

Start with the [repository overview](../README.md) and [locked installation](USAGE.md#install). Run commands from the repository root. The engine is frozen at 1.0.4; repository organization and evaluation work must keep its source, configuration, resources and dependency versions unchanged.

## Code and contract map

| Area | Responsibility |
| --- | --- |
| [cli.py](../src/account_history_analyzer/cli.py), [pipeline.py](../src/account_history_analyzer/pipeline.py) | CLI dispatch and analysis orchestration |
| [io.py](../src/account_history_analyzer/io.py), [config.py](../src/account_history_analyzer/config.py) | Snapshot loading, validation and configuration |
| [src/account_history_analyzer/](../src/account_history_analyzer/) | Preprocessing, feature extraction, numerical comparisons, reuse, chronological candidates, artifact writing and reporting |
| [Packaged contracts](../src/account_history_analyzer/contracts/), [schemas/](../schemas/) | Runtime schemas and synchronized source copies |
| [Packaged resources](../src/account_history_analyzer/resources/), [resources/](../resources/), [config/](../config/README.md) | Frozen numerical resources and defaults; matching copies are intentional |
| [tests/](../tests/), [fixtures/](../fixtures/README.md), [design_examples/](../design_examples/) | Unit/integration checks, synthetic construction inputs, comparison/reference examples |
| [scripts/](../scripts/README.md), [containers/](../containers/README.md) | Offline runners, maintenance helpers and reference-container recipe |

The wheel contains `src/account_history_analyzer/`. The source distribution also includes tests, contracts, fixtures, documentation, scripts and the reference-container recipe, as specified in [pyproject.toml](../pyproject.toml). Root configuration/schema/resource copies are developer and packaging inputs; the installed package loads its bundled copies. Keep their existing paths and use the schema checker to detect drift.

The implementation fingerprint hashes package code and numerical resources. Reformatting or moving those files changes that identity even when intended behavior is unchanged. A future engine revision needs its own release and verification; it must not replace the engine bound by an earlier study.

## Routine verification

```bash
python3.12 scripts/offline_exec.py .venv/bin/python -m pytest -q
python3.12 scripts/offline_exec.py .venv/bin/python scripts/sync_schemas.py --check
python3.12 scripts/offline_exec.py .venv/bin/ahas evaluate \
  --suite synthetic --fixtures fixtures --out my-synthetic-evaluation
```

Choose checks appropriate to the change. For navigation-only edits, inspect Markdown links and examples and confirm preserved file identities. For contract, packaging or engine work, run the affected checks and required suite. Historical test outcomes in [engineering records](DOCUMENTATION_INDEX.md#release-and-engineering-history) are evidence from their original runs; record new outcomes separately.

The [acceptance-to-test map](TEST_MAP.md) describes executable coverage. The synthetic evaluator reads construction truth; ordinary `analyze` never receives truth sidecars. A passing software check does not establish real-account accuracy.

The optional browser audit runs separately because Chrome requires Unix IPC that the stricter analyzer wrapper denies:

```bash
.venv/bin/python scripts/browser_offline_exec.py env AHAS_RUN_BROWSER_AUDIT=1 \
  .venv/bin/python -m pytest \
  tests/test_security.py::test_out04_real_browser_remote_requests_intercepted -q
```

It requires the tested Chrome executable and Node.js already installed and downloads nothing. The wrapper denies internet sockets. See the [container guide](../containers/README.md) for the separate Docker workflow and its historical test scope.

## Where new work belongs

- Put current usage, maintenance and interpretation guides in `docs/`; link them from the [documentation index](DOCUMENTATION_INDEX.md).
- Put a new experiment in its own `studies/` directory with an overview, protocol, preparation rules, evaluation code, results and review. Update the [study catalog](../studies/README.md). Preserve earlier registrations, failed attempts and execution receipts.
- Keep original writing, account maps and prepared real-text inputs outside the public tree. Study publication uses explicitly reviewed sanitized exports. The generic [package collector](../scripts/README.md#engineering-workloads-and-historical-release-validation) does not apply those exclusions.
- Write local runs into fresh ignored `my-report*`, `my-comparison*` or `my-synthetic-evaluation*` directories. Do not reuse tracked evidence destinations under `qa/`, `output/`, `evaluation/` or `studies/`.
- Keep generated wheels and source archives in ignored build directories. Frozen binaries belong in [release downloads](https://github.com/jaykobdetar/account-history-analyzer/releases/tag/v1.0.4), with their checksums. Do not overwrite an existing frozen release when checking a changed source distribution.

The [original handoff](archive/original-handoff/README.md) is archived specification history. [Provenance](../provenance/README.md) explains which files were imported, relocated or deduplicated and how to recover exact historical artifacts. Original receipts may require their original layout and protected inputs; they are not instructions to recreate private data from the public clone.
