# Fixture pack — synthetic inputs, not a trained model or detector benchmark

All histories in this folder are artificial. No real Reddit account or person is represented. The `.truth.json` sidecars describe construction operations and hand-checkable expected results, not human/bot/AI identity labels. The analysis implementation does not exist in this handoff and has not produced measured results.

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

```bash
python fixtures/generate_fixtures.py
```

The generator uses only the standard library, fixed strings, fixed dates, and SHA-256-based deterministic content-word selection. It does not call a model, read a clock, download anything, or implement the proposed analyzer. To check byte stability, generate into two temporary directories and compare the files.

## Feeding an eventual implementation

```bash
ahas analyze --input fixtures/arithmetic.jsonl \
  --manifest fixtures/arithmetic.snapshot.json \
  --config config/default.toml --out output/arithmetic/

ahas analyze --input fixtures/constructed_style_shift.jsonl \
  --manifest fixtures/constructed_style_shift.snapshot.json \
  --config config/default.toml --out output/style_shift/
```

These are **target commands** for the implementation agent to make work; they do not run before the agent builds `ahas`.

Pass only the input history and manifest to `analyze`. Truth files belong to the evaluation harness. The file index contains SHA-256 checksums so that accidental changes are detectable.

## Numerical oracles

`numerical_oracles.json` specifies expected cosine, Jensen–Shannon, shingle, Delta, and small change-point arithmetic. Its tiny inputs exercise low-level mathematics and are not permitted to bypass the product's minimum-text safeguards. `arithmetic.truth.json` contains expected event and token counts after the specified preprocessing. It must not be presented as output already calculated by an AHAS implementation.
