# Engineering workload

`input/` contains 1,000 distinct generated events and 94,000 retained word tokens. `scripts/generate_benchmark.py` calls the original shipped `synthetic_text` constructor with indices 0–999, a fixed text setting and deterministic five-minute timestamps. It reads no truth sidecar. All default analysis modules and required sensitivity views remain enabled.

This is a formulaic constructed workload, not representative real account data. The measured size is below the 500,000-word upper bound; it does not establish worst-case performance for every permitted input. Exact full contribution exports account for much of the output and memory cost.

Reproduce the complete command, including serialization and publication:

```bash
python3.12 scripts/offline_exec.py .venv/bin/python scripts/generate_benchmark.py
/usr/bin/time -v -o benchmarks/final-time.txt \
  python3.12 scripts/offline_exec.py .venv/bin/ahas analyze \
  --input benchmarks/input/records.jsonl --manifest benchmarks/input/snapshot.json \
  --out benchmarks/final-report --overwrite
```

Raw timing receipts and reference hardware/numerical build metadata are separate from canonical results. `preflight-time.txt` records the initial completed run before final evaluator code was frozen. The final measurement is separately named; no timings from unrun commands are presented as observations.
