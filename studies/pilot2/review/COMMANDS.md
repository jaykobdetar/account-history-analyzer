# Actual command records

Each block below is an actual recorded invocation. Historical failed attempts stay failed. Complete stdout/stderr are beside the linked receipt; performance receipts are separate from canonical artifacts.

## approved-acquisition-network.receipt

Exit code: 0. Wall seconds: 34.01971768401563. [Receipt](../logs/approved-acquisition-network.receipt.json).

```bash
.venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/acquire_corpora.py
```

## approved-acquisition.receipt

Exit code: 1. Wall seconds: 0.05951771099353209. [Receipt](../logs/approved-acquisition.receipt.json).

```bash
.venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/acquire_corpora.py
```

## audit-cap-and-joint-bridges.receipt

Exit code: 0. Wall seconds: 45.65368596400367. [Receipt](../logs/audit-cap-and-joint-bridges.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py /usr/bin/prlimit --as=3221225472 .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/verify_audit_cap_and_bridges.py
```

## candidate-fidelity.receipt

Exit code: 0. Wall seconds: 13.496896619995823. [Receipt](../logs/candidate-fidelity.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/check_candidate_fidelity.py
```

## chronological-capped-launch-regression.receipt

Exit code: 0. Wall seconds: 0.23037868898245506. [Receipt](../logs/chronological-capped-launch-regression.receipt.json).

```bash
python3.12 scripts/offline_exec.py .venv/bin/python -B -c 'import os,resource,sys; resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3)); os.execv(sys.executable,[sys.executable,"-B",*sys.argv[1:]])' /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/test_prepare_streams.py
```

## chronological-driver-tests.receipt

Exit code: 0. Wall seconds: 0.13814448201446794. [Receipt](../logs/chronological-driver-tests.receipt.json).

```bash
python3.12 scripts/offline_exec.py .venv/bin/python -B /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/test_prepare_streams.py
```

## chronological-feature-contract-tests.receipt

Exit code: 0. Wall seconds: 0.21832547400845215. [Receipt](../logs/chronological-feature-contract-tests.receipt.json).

```bash
python3.12 scripts/offline_exec.py .venv/bin/python -B /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/test_prepare_streams.py
```

## chronological-final-guard-tests.receipt

Exit code: 0. Wall seconds: 0.23696894399472512. [Receipt](../logs/chronological-final-guard-tests.receipt.json).

```bash
python3.12 scripts/offline_exec.py .venv/bin/python -B -c 'import os,resource,sys; resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3)); os.execv(sys.executable,[sys.executable,"-B",*sys.argv[1:]])' /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/test_prepare_streams.py
```

## chronological-final-preparation-tests.receipt

Exit code: 0. Wall seconds: 0.22109582999837585. [Receipt](../logs/chronological-final-preparation-tests.receipt.json).

```bash
python3.12 scripts/offline_exec.py .venv/bin/python -B /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/test_prepare_streams.py
```

## chronological-preparation-preflight-tests.receipt

Exit code: 0. Wall seconds: 0.2224711720191408. [Receipt](../logs/chronological-preparation-preflight-tests.receipt.json).

```bash
python3.12 scripts/offline_exec.py .venv/bin/python -B /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/test_prepare_streams.py
```

## chronological-preparation-retry.receipt

Exit code: 0. Wall seconds: 104.15351053100312. [Receipt](../logs/chronological-preparation-retry.receipt.json).

```bash
python3.12 scripts/offline_exec.py .venv/bin/python -B -c 'import os,resource,sys; resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3)); os.execv(sys.executable,[sys.executable,"-B",*sys.argv[1:]])' /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/prepare_streams.py prepare --root /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914 --exclude-cohort /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/prepared/paired/private/selection.json --paired-pool /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/prepared/paired/private/candidate-pool.jsonl
```

## chronological-preparation.receipt

Exit code: 1. Wall seconds: 37.865410636004526. [Receipt](../logs/chronological-preparation.receipt.json).

```bash
python3.12 scripts/offline_exec.py .venv/bin/python -B -c 'import resource,runpy,sys; resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3)); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name="__main__")' /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/prepare_streams.py prepare --root /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914 --exclude-cohort /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/prepared/paired/private/selection.json --paired-pool /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/prepared/paired/private/candidate-pool.jsonl
```

## chronological-prepared-artifact-tests.receipt

Exit code: 0. Wall seconds: 15.500327051006025. [Receipt](../logs/chronological-prepared-artifact-tests.receipt.json).

```bash
python3.12 scripts/offline_exec.py .venv/bin/python -B /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/test_prepared_streams.py
```

## chronological-pure-tests.receipt

Exit code: 0. Wall seconds: 0.13261459302157164. [Receipt](../logs/chronological-pure-tests.receipt.json).

```bash
python3.12 scripts/offline_exec.py .venv/bin/python -B /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/test_prepare_streams.py
```

## exposed-development-profile.receipt

Exit code: 0. Wall seconds: 195.9935894740047. [Receipt](../logs/exposed-development-profile.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python -m cProfile -o /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/resources/exposed-development.pstats -m account_history_analyzer analyze --input /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-realworld-review/inputs/public/accounts/cornell-6e9168d005b3c484038b.jsonl --manifest /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-realworld-review/inputs/public/accounts/cornell-6e9168d005b3c484038b.snapshot.json --out /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/resources/exposed-development-report
```

## exposed-development-recompute.receipt

Exit code: 0. Wall seconds: 74.46209791098954. [Receipt](../logs/exposed-development-recompute.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python -m account_history_analyzer verify --input /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-realworld-review/inputs/public/accounts/cornell-6e9168d005b3c484038b.jsonl --manifest /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-realworld-review/inputs/public/accounts/cornell-6e9168d005b3c484038b.snapshot.json --analysis-dir /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/resources/exposed-development-report --recompute
```

## final-review-render.receipt

Exit code: 1. Wall seconds: 0.08667343997512944. [Receipt](../logs/final-review-render.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/build_final_review.py
```

## independent-pair-metrics.receipt

Exit code: 0. Wall seconds: 0.0696870029787533. [Receipt](../logs/independent-pair-metrics.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/check_pair_metrics.py
```

## leakage-audit-tests-final.receipt

Exit code: 0. Wall seconds: 0.6825068260077387. [Receipt](../logs/leakage-audit-tests-final.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python -m pytest -q -p no:cacheprovider /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/tests/test_leakage_audit.py
```

## leakage-audit-tests-initial.receipt

Exit code: 0. Wall seconds: 0.6223516140016727. [Receipt](../logs/leakage-audit-tests-initial.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python -m pytest -q /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/tests/test_leakage_audit.py
```

## leakage-audit-tests-memory-reporting.receipt

Exit code: 0. Wall seconds: 0.6310583469748963. [Receipt](../logs/leakage-audit-tests-memory-reporting.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python -m pytest -q -p no:cacheprovider /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/tests/test_leakage_audit.py
```

## metric-oracle-tests.receipt

Exit code: 0. Wall seconds: 0.3017425309808459. [Receipt](../logs/metric-oracle-tests.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python -m pytest -q -p no:cacheprovider /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/tests/test_pair_metric_oracle.py
```

## natural-canonical-recompute.receipt

Exit code: 0. Wall seconds: 59.54532668198226. [Receipt](../logs/natural-canonical-recompute.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py env PYTHONHASHSEED=2027 TZ=America/Los_Angeles .venv/bin/python -m account_history_analyzer verify --input /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/prepared/streams/accounts/chrono-6344efa4ef2577e2eb36.jsonl --manifest /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/prepared/streams/accounts/chrono-6344efa4ef2577e2eb36.snapshot.json --analysis-dir /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/outputs/streams/chrono-ApplyingToCollege-pair1-unknown-natural-full --recompute
```

## paired-batch.receipt

Exit code: 0. Wall seconds: 48.40069403900998. [Receipt](../logs/paired-batch.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/run_pairs.py --jobs 2
```

## paired-leakage-audit.receipt

Exit code: 0. Wall seconds: 61.585553626995534. [Receipt](../logs/paired-leakage-audit.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py /usr/bin/prlimit --as=3221225472 .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/leakage_audit.py --candidate-pool /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/prepared/paired/private/candidate-pool.jsonl --out /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/prepared/paired/private/leakage-audit.json
```

## paired-leakage-independent-check.receipt

Exit code: 0. Wall seconds: 22.501635647990042. [Receipt](../logs/paired-leakage-independent-check.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/verify_paired_leakage.py
```

## paired-scoring-gate-directory-tests.receipt

Exit code: 0. Wall seconds: 0.43592682998860255. [Receipt](../logs/paired-scoring-gate-directory-tests.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python -m pytest -q -p no:cacheprovider /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/tests/test_pair_scoring_gate.py
```

## paired-scoring-gate-tests.receipt

Exit code: 0. Wall seconds: 0.45413462599390186. [Receipt](../logs/paired-scoring-gate-tests.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python -m pytest -q -p no:cacheprovider /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/tests/test_pair_scoring_gate.py
```

## reproduction-comparison.receipt

Exit code: 0. Wall seconds: 0.04282780800713226. [Receipt](../logs/reproduction-comparison.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/verify_reproductions.py
```

## saved-outcome-summary.receipt

Exit code: 0. Wall seconds: 7.53649639498326. [Receipt](../logs/saved-outcome-summary.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/summarize_results.py
```

## scoring-freeze.receipt

Exit code: 0. Wall seconds: 0.43523399700643495. [Receipt](../logs/scoring-freeze.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/freeze_scoring.py
```

## splice-canonical-replay.receipt

Exit code: 0. Wall seconds: 41.44115023201448. [Receipt](../logs/splice-canonical-replay.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py env PYTHONHASHSEED=17 TZ=Pacific/Kiritimati .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/run_stream_batch.py --jobs 1 --only chrono-ApplyingToCollege-pair1-splice-full --destination outputs/replay-splice
```

## stream-batch.receipt

Exit code: 0. Wall seconds: 700.7485348590126. [Receipt](../logs/stream-batch.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/run_stream_batch.py --jobs 2
```

## study-tests-combined.receipt

Exit code: 0. Wall seconds: 2.78223803799483. [Receipt](../logs/study-tests-combined.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python -m pytest -q -p no:cacheprovider /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/tests /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/test_prepare_pairs.py /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/test_prepare_streams.py
```

## cornell-inventory.receipt

Exit code: 0. Wall seconds: 43.03178670501802. [Receipt](../inventory/cornell-inventory.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/inventory_local.py
```

## paired-adapter-final-tests.receipt

Exit code: 0. Wall seconds: 2.267669228982413. [Receipt](../inventory/paired-adapter-final-tests.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python -m pytest -p no:cacheprovider /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/test_prepare_pairs.py -q
```

## paired-adapter-tests.receipt

Exit code: 0. Wall seconds: 2.3646167450060602. [Receipt](../inventory/paired-adapter-tests.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python -m pytest -p no:cacheprovider /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/test_prepare_pairs.py -q
```

## paired-candidates.receipt

Exit code: 0. Wall seconds: 101.27491598401684. [Receipt](../inventory/paired-candidates.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/prepare_pairs.py candidates --plan /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/protocol/plan.json --out /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/prepared/paired
```

## paired-finalize-run.receipt

Exit code: 1. Wall seconds: 0.16973087799851783. [Receipt](../inventory/paired-finalize-run.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/prepare_pairs.py finalize --plan /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/protocol/plan.json --out /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/prepared/paired --audit /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/prepared/paired/private/leakage-audit.json
```

## paired-preflight-run.receipt

Exit code: 0. Wall seconds: 97.23947172300541. [Receipt](../inventory/paired-preflight-run.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/preflight_pairs.py
```

## paired-prepared-check-run.receipt

Exit code: 0. Wall seconds: 3.6605629319965374. [Receipt](../inventory/paired-prepared-check-run.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/check_paired_prepared.py --prepared /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/prepared/paired-registered --audit /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/prepared/paired/private/leakage-audit.json
```

## paired-registered-candidates-run.receipt

Exit code: 0. Wall seconds: 102.45684467098908. [Receipt](../inventory/paired-registered-candidates-run.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/prepare_pairs.py candidates --plan /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/protocol/plan.json --out /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/prepared/paired-registered
```

## paired-registered-finalize-run.receipt

Exit code: 0. Wall seconds: 4.029678254009923. [Receipt](../inventory/paired-registered-finalize-run.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/prepare_pairs.py finalize --plan /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/protocol/plan.json --out /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/prepared/paired-registered --audit /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/prepared/paired/private/leakage-audit.json
```

## paired-registered-replay-check-run.receipt

Exit code: 0. Wall seconds: 0.1829981199989561. [Receipt](../inventory/paired-registered-replay-check-run.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/check_registered_pair_replay.py
```

## source-frame-run.receipt

Exit code: 0. Wall seconds: 36.33801329397829. [Receipt](../inventory/source-frame-run.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/inventory_sources.py
```

## paired-replay-run.receipt

Exit code: 0. Wall seconds: 3.5735898800194263. [Receipt](../review/paired-replay-run.receipt.json).

```bash
env PYTHONHASHSEED=991 TZ=Pacific/Kiritimati .venv/bin/python scripts/offline_exec.py .venv/bin/python -B /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/scripts/run_pairs.py --only ApplyingToCollege.within_community.full.retained_prose_n4 --destination outputs/replay-paired --jobs 1
```

## postfreeze-manifest-check.receipt

Exit code: 0. Wall seconds: 0.8049667339946609. [Receipt](../review/postfreeze-manifest-check.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python -B /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/postfreeze_checks.py --phase frozen --out /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/postfreeze-manifest-check.json
```

## postfreeze-review-tests-final.receipt

Exit code: 0. Wall seconds: 0.3575428680051118. [Receipt](../review/postfreeze-review-tests-final.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python -B -m pytest -q -p no:cacheprovider /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/test_postfreeze_review.py
```

## postfreeze-review-tests.receipt

Exit code: 0. Wall seconds: 0.3879824129980989. [Receipt](../review/postfreeze-review-tests.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python -B -m pytest -q -p no:cacheprovider /home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/test_postfreeze_review.py
```

## preparation-review-build.receipt

Exit code: 0. Wall seconds: 0.14072195699554868. [Receipt](../review/preparation-review-build.receipt.json).

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/python /tmp/build_pilot2_preparation_review.py
```
