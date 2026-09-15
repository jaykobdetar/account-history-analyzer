# Fixture pack — synthetic inputs, not a trained model or detector benchmark

All histories in this folder are artificial. No real Reddit account or person is represented. AHAS uses these inputs for software tests and synthetic evaluation. The `.truth.json` sidecars describe construction operations and hand-checkable expected results, not human/bot/AI identity labels. Measured software results are documented in the [engineering evaluation](../docs/EVALUATION.md) and [release repair records](../docs/DOCUMENTATION_INDEX.md).

## Cases

| Case | Input size | Purpose |
|---|---:|---|
| `arithmetic` | 7 rows, 6 unique IDs | Hand-checkable timing, quote/code removal, short-text abstention, host counts, and ingestion-versus-content duplicates. |
| `stable_constructed_style` | 320 records | Fixed writing template; changing equal-length content words, constant registered surface/function feature structure. |
| `constructed_style_shift` | 320 records | At record 161, uppercasing, comma→semicolon substitution, and contraction expansion are deliberately introduced. |
| `constructed_topic_shift` | 320 records | At record 161, equal-length vocabulary substitutions preserve the designed masked structure. |
| `edge_cases` | 6 records | Missing time, removed text, sentinels, declared non-English, hostile markup/URLs, pathlike IDs. |
| `empty` | 0 records | Empty-snapshot behavior without made-up reassuring scores. |

The 320-record histories are formulaic by design. A single repeated template makes arithmetic and invariance checks easy; it makes these histories inappropriate for estimating performance on ordinary people. Exact three-hour timestamps are also artificial.

## Regeneration

Keep the shipped files unchanged. From the repository root, generate a comparison copy in a temporary directory:

```bash
ahas_fixture_dir="$(mktemp -d)"
python3.12 scripts/offline_exec.py .venv/bin/python \
  fixtures/generate_fixtures.py --out "$ahas_fixture_dir"
```

The generator uses only the standard library, fixed strings, fixed dates, and SHA-256-based deterministic content-word selection. It does not call a model, read a clock, download anything, or perform analysis. The [fixture integrity tests](../tests/test_fixture_integrity.py) check the stored hashes and regenerate every data/index file in two separate processes with different hash seeds and timezones.

## Analyze a fixture

After following the [installation instructions](../docs/USAGE.md#install), run these commands from the repository root. Each output directory must be new:

```bash
python3.12 scripts/offline_exec.py .venv/bin/ahas analyze \
  --input fixtures/arithmetic.jsonl \
  --manifest fixtures/arithmetic.snapshot.json \
  --config config/default.toml --out my-report-arithmetic

python3.12 scripts/offline_exec.py .venv/bin/ahas analyze \
  --input fixtures/constructed_style_shift.jsonl \
  --manifest fixtures/constructed_style_shift.snapshot.json \
  --config config/default.toml --out my-report-style-shift
```

The offline runner requires Linux and `libseccomp`; the [reference container](../containers/README.md) provides the separately documented Docker workflow. Existing report bundles and their historical receipts remain unchanged.

Pass only the input history and manifest to `analyze`. Truth files belong to the evaluation harness. The file index contains SHA-256 checksums so that accidental changes are detectable.

## Numerical oracles

`numerical_oracles.json` specifies expected cosine, Jensen–Shannon, shingle, Delta, and small change-point arithmetic. Its tiny inputs exercise low-level mathematics and are not permitted to bypass the product's minimum-text safeguards. `arithmetic.truth.json` contains expected event and token counts after the specified preprocessing. These expectations are test inputs; actual analyzer results and execution receipts are separate artifacts.
