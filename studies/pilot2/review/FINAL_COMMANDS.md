# Final packaging and review commands

These completed receipts supplement COMMANDS.md. They are review, browser and packaging preparation checks, not new analytical runs.

Final staging, ZIP creation and post-ZIP verification occur after this snapshot; their raw receipts are delivered beside the archive.

## logs/final-review-render-corrected.receipt.json

Started UTC: 2026-09-14T19:55:49.525415+00:00; exit: 0; wall seconds: 0.08915991199319251.

[Actual receipt](../logs/final-review-render-corrected.receipt.json)

```json
[
  ".venv/bin/python",
  "scripts/offline_exec.py",
  ".venv/bin/python",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/build_final_review.py"
]
```

## logs/handoff-staging.receipt.json

Started UTC: 2026-09-14T20:03:13.243840+00:00; exit: 0; wall seconds: 0.10275377499056049.

[Actual receipt](../logs/handoff-staging.receipt.json)

```json
[
  ".venv/bin/python",
  "scripts/offline_exec.py",
  ".venv/bin/python",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/stage_handoff.py"
]
```

## logs/paired-review-browser.receipt.json

Started UTC: 2026-09-14T20:09:54.608934+00:00; exit: 0; wall seconds: 0.4358841420034878.

[Actual receipt](../logs/paired-review-browser.receipt.json)

```json
[
  ".venv/bin/python",
  "scripts/browser_offline_exec.py",
  "node",
  "scripts/check_report_browser.cjs",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/PAIRED_OUTCOMES.html",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/PAIRED_OUTCOMES.png"
]
```

## logs/reproduction-comparison.receipt.json

Started UTC: 2026-09-14T19:55:49.349131+00:00; exit: 0; wall seconds: 0.04282780800713226.

[Actual receipt](../logs/reproduction-comparison.receipt.json)

```json
[
  ".venv/bin/python",
  "scripts/offline_exec.py",
  ".venv/bin/python",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/verify_reproductions.py"
]
```

## logs/review-browser.receipt.json

Started UTC: 2026-09-14T19:57:28.418108+00:00; exit: 0; wall seconds: 0.4446798909921199.

[Actual receipt](../logs/review-browser.receipt.json)

```json
[
  ".venv/bin/python",
  "scripts/browser_offline_exec.py",
  "node",
  "scripts/check_report_browser.cjs",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/REVIEW.html",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/REVIEW.png"
]
```

## logs/streams-review-browser.receipt.json

Started UTC: 2026-09-14T20:09:57.488452+00:00; exit: 0; wall seconds: 0.41401281699654646.

[Actual receipt](../logs/streams-review-browser.receipt.json)

```json
[
  ".venv/bin/python",
  "scripts/browser_offline_exec.py",
  "node",
  "scripts/check_report_browser.cjs",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/STREAM_OUTCOMES.html",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/STREAM_OUTCOMES.png"
]
```

## review/final-handoff-check-first.receipt.json

Started UTC: 2026-09-14T20:10:33.470638+00:00; exit: 1; wall seconds: 9.401693988998886.

[Actual receipt](../review/final-handoff-check-first.receipt.json)

```json
[
  ".venv/bin/python",
  "scripts/offline_exec.py",
  ".venv/bin/python",
  "-B",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/check_final_handoff.py",
  "--handoff",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/public-handoff",
  "--out",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/final-handoff-check-first.json"
]
```

## review/final-handoff-check-second.receipt.json

Started UTC: 2026-09-14T20:12:25.775431+00:00; exit: 0; wall seconds: 20.776334697991842.

[Actual receipt](../review/final-handoff-check-second.receipt.json)

```json
[
  ".venv/bin/python",
  "scripts/offline_exec.py",
  ".venv/bin/python",
  "-B",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/check_final_handoff.py",
  "--handoff",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/public-handoff",
  "--out",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/final-handoff-check-second.json"
]
```

## review/final-handoff-regression-tests.receipt.json

Started UTC: 2026-09-14T20:12:25.268494+00:00; exit: 0; wall seconds: 0.3786430320178624.

[Actual receipt](../review/final-handoff-regression-tests.receipt.json)

```json
[
  ".venv/bin/python",
  "scripts/offline_exec.py",
  ".venv/bin/python",
  "-B",
  "-m",
  "pytest",
  "-q",
  "-p",
  "no:cacheprovider",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/test_postfreeze_review.py"
]
```

## review/largest-cost-word-characterization.receipt.json

Started UTC: 2026-09-14T19:58:09.655787+00:00; exit: 0; wall seconds: 0.6879358439764474.

[Actual receipt](../review/largest-cost-word-characterization.receipt.json)

```json
[
  ".venv/bin/python",
  "-B",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/characterize_largest_cost_case.py",
  "--root",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914",
  "--out",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/largest-cost-word-volume.json"
]
```

## review/portable-links-before-run.receipt.json

Started UTC: 2026-09-14T20:14:08.998749+00:00; exit: 1; wall seconds: 0.22781002402189188.

[Actual receipt](../review/portable-links-before-run.receipt.json)

```json
[
  ".venv/bin/python",
  "scripts/offline_exec.py",
  ".venv/bin/python",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/portable_handoff_links.py",
  "--stage",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/public-handoff",
  "--receipt",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/portable-links-before.json"
]
```

## review/resource-accounting-final-tests.receipt.json

Started UTC: 2026-09-14T20:00:37.582230+00:00; exit: 0; wall seconds: 0.3453769879997708.

[Actual receipt](../review/resource-accounting-final-tests.receipt.json)

```json
[
  ".venv/bin/python",
  "-B",
  "-m",
  "pytest",
  "-p",
  "no:cacheprovider",
  "-q",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/test_resource_cost_report.py"
]
```

## review/resource-accounting-tests.receipt.json

Started UTC: 2026-09-14T19:56:53.914896+00:00; exit: 0; wall seconds: 0.3179793329909444.

[Actual receipt](../review/resource-accounting-tests.receipt.json)

```json
[
  ".venv/bin/python",
  "-B",
  "-m",
  "pytest",
  "-p",
  "no:cacheprovider",
  "-q",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/test_resource_cost_report.py"
]
```

## review/resource-cost-build-final.receipt.json

Started UTC: 2026-09-14T20:00:56.906063+00:00; exit: 0; wall seconds: 1.4984472029900644.

[Actual receipt](../review/resource-cost-build-final.receipt.json)

```json
[
  ".venv/bin/python",
  "-B",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/build_resource_cost_report.py",
  "--root",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914",
  "--old-study",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-realworld-review",
  "--repo",
  "/home/jaykob/Downloads/Account_History_Analyzer_V1_Agent_Handoff/account_history_analyzer_v1",
  "--out-json",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/resource-cost.json",
  "--out-markdown",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/RESOURCE_COST.md"
]
```

## review/resource-cost-build.receipt.json

Started UTC: 2026-09-14T19:59:08.076275+00:00; exit: 1; wall seconds: 1.744540699000936.

[Actual receipt](../review/resource-cost-build.receipt.json)

```json
[
  ".venv/bin/python",
  "-B",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/build_resource_cost_report.py",
  "--root",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914",
  "--old-study",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-realworld-review",
  "--repo",
  "/home/jaykob/Downloads/Account_History_Analyzer_V1_Agent_Handoff/account_history_analyzer_v1",
  "--out-json",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/resource-cost.json",
  "--out-markdown",
  "/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914/review/RESOURCE_COST.md"
]
```

