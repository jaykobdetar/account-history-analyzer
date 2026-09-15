# Install and use AHAS

[Repository overview](../README.md) · [Development and checks](DEVELOPMENT.md) · [Documentation index](DOCUMENTATION_INDEX.md)

AHAS 1.0.4 analyzes supplied local records. Setup may download packages; analysis runs offline. The commands below run from the repository root.

## Install

Reference development host: CPython 3.12.3 on Linux x86_64. `uv` 0.9.21 was used for setup. Run these commands from the repository root. To install the current checkout, create an environment and install the exact hash-locked runtime, test and build dependencies:

```bash
uv venv --python python3.12 .venv
uv pip install --python .venv/bin/python --require-hashes \
  -r requirements.lock.txt -r containers/build-requirements.lock
uv pip install --python .venv/bin/python --no-deps --no-build-isolation .
```

Setup may download the frozen package artifacts. Analysis needs no network. `uv.lock` is the resolved dependency contract; `requirements.lock.txt` is its hash-bearing export. `containers/build-requirements.lock` freezes the build backend and its dependencies. For the exact frozen distribution, download the [1.0.4 wheel](https://github.com/jaykobdetar/account-history-analyzer/releases/download/v1.0.4/account_history_analyzer-1.0.4-py3-none-any.whl) and [release checksums](https://github.com/jaykobdetar/account-history-analyzer/releases/download/v1.0.4/SHA256SUMS.release.txt). Verify the wheel hash, then install it with `--no-deps` after installing the locked dependencies. Generated distributions are no longer duplicated in Git.

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

## Supplied evidence in AHIF

[AHIF 0.1.1](AHIF.md) is a separate evidence format. Its JSONL is not accepted directly by this CLI. The companion AHIF repository provides a versioned offline Reddit export normalizer and an explicit metadata-only projection into these existing record/snapshot inputs. Read the [supported contract and limitations](AHIF.md#supported-boundaries) before using its outputs. Retained-prose projection is not supported by that profile; ordinary insufficient-data outcomes remain valid.

## Python API

```python
from account_history_analyzer import AnalysisConfig, load_snapshot, analyze, write_artifacts

config = AnalysisConfig.from_toml("config/default.toml")
snapshot = load_snapshot("fixtures/arithmetic.jsonl", "fixtures/arithmetic.snapshot.json", config)
result = analyze(snapshot, config)
write_artifacts(result, "my-report")
```

Snapshots, configuration and result stage boundaries are immutable. Public functions have type hints, and the wheel includes `py.typed`. Stable exception classes live in `account_history_analyzer.errors`. Normal insufficient data stays in result statuses. Numerical primitives are independently callable from `style`, `reuse`, and `changepoints`; their tiny-vector tests do not relax product sample guards.

## Interpretation and further reading

A pattern does not establish its cause. Style distance is not an authorship probability; parameter stability is not confidence. See [methods](METHODS.md), [limitations](LIMITATIONS.md), [configuration](../config/README.md), and [external evaluation formats](EXTERNAL_EVALUATION.md). The [study catalog](../studies/README.md) records what has actually been evaluated.
