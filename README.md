# Account History Analysis Suite (AHAS) 1.0.4

Version 1.0.4 repairs AHAS-RW-001: every stored penalty setting and stream has an explicit candidate/matching summary, including alternative-only intervals when the primary set is empty. The numerical baseline remains frozen. See [the narrow repair record](docs/RW001.md) for fresh evidence and limitations; earlier release receipts remain historical.

[Documentation index](docs/DOCUMENTATION_INDEX.md) · [Second-pilot review](studies/pilot2/review/REVIEW.md) · [Complete pilot outcomes](studies/pilot2/review/PAIRED_OUTCOMES.md) · [Frozen release downloads](https://github.com/jaykobdetar/account-history-analyzer/releases/tag/v1.0.4)

An implemented Python 3.12 library and `ahas` CLI for offline, deterministic measurements of supplied account histories. It reads local JSONL records and a snapshot manifest. It produces counts, source-linked reuse findings, descriptive style comparisons, activity/link/interaction summaries, change candidates, and static reports.

A pattern does not establish its cause. Style distance is not an authorship probability. Parameter stability is not confidence. The suite has no fetching, credentials, models, embeddings, AI-writing detector, bot/human score, website, or external service dependency at runtime. Real-world validation is **not established**.

Version 1.0.3 fixes loss of significant whitespace in displayed character n-gram labels. Labels use reversible quoted ASCII JSON notation, with ordinary spaces escaped as `\u0020`; analytical feature IDs, calculations, ordering and excerpt-free omission are unchanged. See [the focused report-label repair](docs/REPORT005.md) for fresh validation and the frozen analytical baseline.

Version 1.0.2 repairs all four attached audit findings: bounded artifact round trips, order-independent reports, bounded exact reuse matching on repeated text, and mixed hyperlink-label counting. See [the repair record](docs/AUDIT_REPAIR.md) for actual tests and measurements. The exact optimizer fix from [ruptures PR #383](https://github.com/deepcharles/ruptures/pull/383), pinned to commit `a28574d9e63b0c2a966e176a1d049d3c9deaaaaf`, is unchanged. [Its update record](docs/PR383.md) and all earlier release receipts remain historical.

## Install

Reference development host: CPython 3.12.3 on Linux x86_64. `uv` 0.9.21 was used for setup. From this repository, create an environment and install the exact hash-locked runtime, test and build dependencies:

```bash
uv venv --python python3.12 .venv
uv pip install --python .venv/bin/python --require-hashes \
  -r requirements.lock.txt -r containers/build-requirements.lock
uv pip install --python .venv/bin/python --no-deps --no-build-isolation .
```

Setup may download the frozen package artifacts. Analysis needs no network. `uv.lock` is the resolved dependency contract; `requirements.lock.txt` is its hash-bearing export. `containers/build-requirements.lock` freezes the build backend and its dependencies. A prebuilt wheel is provided under `dist/`; install it with `--no-deps` after installing the locked dependencies.

The Linux offline runner requires the host's `libseccomp` shared library. It fails closed if unavailable, denies socket creation/connections/sends for the process and its children, and fixes numerical workers to one. The separately documented Docker recipe uses `--network none`.

## Run

```bash
python3.12 scripts/offline_exec.py .venv/bin/ahas validate \
  --input fixtures/arithmetic.jsonl --manifest fixtures/arithmetic.snapshot.json

python3.12 scripts/offline_exec.py .venv/bin/ahas analyze \
  --input fixtures/arithmetic.jsonl --manifest fixtures/arithmetic.snapshot.json \
  --config config/default.toml --out my-report

python3.12 scripts/offline_exec.py .venv/bin/ahas compare \
  --input fixtures/arithmetic.jsonl --manifest fixtures/arithmetic.snapshot.json \
  --selection design_examples/comparison.json --out my-comparison

python3.12 scripts/offline_exec.py .venv/bin/ahas render \
  --results my-report/results.json --artifacts my-report \
  --format both --excerpts none --out my-report-no-excerpts

python3.12 scripts/offline_exec.py .venv/bin/ahas verify \
  --input fixtures/arithmetic.jsonl --manifest fixtures/arithmetic.snapshot.json \
  --analysis-dir my-report --recompute
```

Current sample outputs are under `output/rw001/`. Historical `output/report005/`, `output/audit-repair/`, `output/pr383/` and original sample bundles retain their unchanged receipts inside the frozen source-and-reports archive attached to the 1.0.4 release. The commands above use fresh directories. Add `--overwrite` only to replace your own earlier run. Without `--recompute`, verification reports `integrity_only`. Recomputation regenerates and compares every canonical artifact, including reports, charts and the checksum manifest; operational receipts are excluded. A source/code/resource/environment mismatch is a verification failure, not a reason to quietly replace the stored measurements.

HTML reports are local files containing inline CSS/SVG, native disclosure elements, and no JavaScript or remote assets. Open `my-report/report.html`. Reports contain supplied source prose by default. `--excerpts none` omits excerpts only from the derivative report; remaining identifiers and measurements can still identify an account, and the original analytical artifacts retain evidence.

Required analysis exports are `results.json`, per-record features, window memberships, evidence, expanded config, method registry, Markdown, HTML, five SVGs, and checksums. Input/runtime receipts are separate from canonical results. Missing data has explicit null values/reasons and module statuses. The AI-text capability is `not_implemented_in_v1`.

CLI exit codes: **0** success including ordinary insufficient data; **2** input/configuration error; **3** computation failure or failed synthetic checks; **4** explicit resource limit/incomplete analysis; **5** failed integrity/reproduction. Machine-readable summaries go to stdout and errors to stderr.

## Python API

```python
from account_history_analyzer import AnalysisConfig, load_snapshot, analyze, write_artifacts

config = AnalysisConfig.from_toml("config/default.toml")
snapshot = load_snapshot("fixtures/arithmetic.jsonl", "fixtures/arithmetic.snapshot.json", config)
result = analyze(snapshot, config)
write_artifacts(result, "my-report")
```

Snapshots, configuration and result stage boundaries are immutable. Public functions have type hints, and the wheel includes `py.typed`. Stable exception classes live in `account_history_analyzer.errors`. Normal insufficient data stays in result statuses. Numerical primitives are independently callable from `style`, `reuse`, and `changepoints`; their tiny-vector tests do not relax product sample guards.

## Test and evaluate

```bash
python3.12 scripts/offline_exec.py .venv/bin/python -m pytest -q
python3.12 scripts/offline_exec.py .venv/bin/ahas evaluate \
  --suite synthetic --fixtures fixtures --out my-synthetic-evaluation
python3.12 scripts/offline_exec.py .venv/bin/python scripts/sync_schemas.py --check
```

Actual commands, outcomes, reproduction receipts and measured performance are recorded in [docs/EVALUATION.md](docs/EVALUATION.md). The acceptance-to-test map is [docs/TEST_MAP.md](docs/TEST_MAP.md). The actual browser audit runs separately because Chromium needs Unix-domain IPC denied by the stricter analyzer filter:

```bash
.venv/bin/python scripts/browser_offline_exec.py env AHAS_RUN_BROWSER_AUDIT=1 \
  .venv/bin/python -m pytest tests/test_security.py::test_out04_real_browser_remote_requests_intercepted -q
```

This optional test needs the tested Chrome executable and Node.js already installed; it downloads nothing. Its filter denies internet sockets, and CDP intercepts resource requests. The release records its actual separate outcome and screenshots under `qa/`.

Local external evaluation is available as `ahas evaluate --suite paired_text --dataset DATASET.json --out DIRECTORY` and `--suite account_stream`. See [docs/EXTERNAL_EVALUATION.md](docs/EXTERNAL_EVALUATION.md) for strict input formats, grouping/leakage audits, frozen development thresholds, and preregistered stream tolerances. Missing datasets are refused; nothing is downloaded. Synthetic truth sidecars describe construction operations and are read only by the evaluator. No authorship ground truth is fabricated.

## Methods and limits

See [docs/METHODS.md](docs/METHODS.md), [docs/DECISIONS.md](docs/DECISIONS.md), [docs/LIMITATIONS.md](docs/LIMITATIONS.md), and [SOURCES.md](SOURCES.md). The feature/method registry distinguishes established primitives from project adaptations. In particular, the minimum-segment-size PELT control flow uses a verbatim private backport of PR #383 on locked ruptures 1.1.10. The source, license and exact commit are bundled; no GitHub access occurs during analysis. The L2 penalized objective remains unchanged.

Defaults require eight eligible records and 1,000 eligible words per side for qualified comparisons, and eight qualified windows for segmentation. English-specific features use supplied language declarations. Titles, kinds, missing timestamps, edits, community mixture and source coverage have explicit treatment. Delta runs only with a valid frozen reference; the bundled toy reference requires `--allow-toy-reference` and remains visibly marked.

Source limits are 10,000 unique records, 200,000 code points per text and 50 MiB of input. Generated artifacts have separate ceilings of 256 MiB per file, 512 MiB per bundle, 32 files and 1 MiB for each config/checksum metadata file; configuration can tighten these ceilings. Near-reuse work has deterministic limits for candidate pairs, postings, work reservations and evidence; see [the charging policy](docs/REUSE_RESOURCE_POLICY.md). Daily calendar expansion is limited to 366,000 bins. Exceeding a limit is explicit; inputs/evidence are not silently sampled or truncated. Human-facing previews identify omitted rows and point to complete exports. Optional all-pair heatmaps and PAN adapters are not part of this release.

Use [containers/README.md](containers/README.md) for the digest-pinned reference container and offline execution. Byte identity is claimed only for actually tested environments. The project owner has not selected a redistribution license; see `LICENSE` and the audited dependency notices in [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md).

The original `BUILD_SPEC.md`, `ACCEPTANCE_TESTS.md`, handoff `SHA256SUMS.txt`, and original synthetic fixtures are retained as provenance. The handoff checksum manifest describes the original inputs, not the implemented release; release checksums are supplied separately.
