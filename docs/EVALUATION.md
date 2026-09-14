# Executed verification log

Engineering behavior and scientific validation are separate. Real-world validation: `not_established`; external datasets were not supplied. Numbers below are actual executions, not targets.

## Environment setup and M0

- `uv sync --python /usr/bin/python3.12 --cache-dir /tmp/ahas-uv-cache`: first sandbox attempt failed DNS resolution; setup-only escalation succeeded, installing the pinned direct dependencies and writing uv.lock with resolved transitive versions/hashes.
- `unshare -n true`: failed `Operation not permitted` on the host.
- `python3.12 scripts/offline_exec.py python3.12 -c 'import socket; socket.socket()'`: failed with `PermissionError` as intended after the runner's own denial self-test. All commands below use this inherited Linux seccomp isolation unless explicitly stated.
- `python3.12 scripts/offline_exec.py .venv/bin/python -m pytest -q tests/test_config.py`: 15 passed.
- Config and registry test run: 16 passed.
- One premature test invocation before the ingestion test file existed returned pytest exit 4 (`file or directory not found`); no tests ran in that invocation.
- `python3.12 scripts/offline_exec.py .venv/bin/ahas validate --input fixtures/arithmetic.jsonl --manifest fixtures/arithmetic.snapshot.json`: exit 0, 6 unique records, stable known-edit warning. Canonical snapshot SHA-256 `03e3cc8c2acc90dcb0e26cb6de0f88bc883aa091de96cda70d10fe7a53a20898`.
- M0 hard gate: 17 tests passed, including strict malformed-input cases and row-order hash invariance, before starting M1.
- Expanded M0 ingestion tests: 43 passed. Bugs found and fixed with regressions: optional JSON Schema date-time checker was absent in the environment; explicit checker now enforces calendar validity. JSONL now splits on LF only, preserving literal U+2028/U+0085 inside JSON strings.

## M1 executable slice

- Full then-available suite: `python3.12 scripts/offline_exec.py .venv/bin/python -m pytest -q`: 76 passed in 2.22 seconds before further tests landed.
- Activity plus ingestion: 53 passed. Arithmetic observed gaps 10,10,40,60,60 seconds; mean36, population variance504, median40, quartiles10/60; inclusive maxima3/5/6; greedy burst first three IDs.
- Both `ahas analyze --input fixtures/arithmetic.jsonl --manifest fixtures/arithmetic.snapshot.json --out output/arithmetic` and equivalent empty run under offline_exec returned exit0 and generated JSON/Markdown/HTML plus receipts.
- Inspected arithmetic Markdown: 36 retained words, 6 events, known edit warning, explicit not-run later modules and unavailable scientific validation. Arithmetic unique-record word counts match [8,8,9,4,4,3]. Empty report uses insufficient-data states.
- Minor renderer key mismatch (`distinct_event_days` versus actual `event_bearing_days`) fixed before continuing.
- M1 audit found bare HTTP URLs containing Markdown emphasis characters could be split by the parser before URL removal. Paused M2, protected URL spans before parsing with collision-free placeholders, and added URL-only-label/autolink/explicit-destination regressions. Full offline suite after fixes: 123 passed in 4.03 seconds. M2 then resumed.
- Original handoff checksum verification: all original fixtures/resources/specs matched; results.schema.json intentionally differs because its generic module payloads have been tightened. Original SHA256SUMS.txt is retained as a provenance record, not a checksum of the implemented release.

## M2 reuse and evidence gate

- Offline full suite: 174 passed in 4.74 seconds.
- Dedicated reuse numerical/property suite: 19 passed. Hand shingle oracle: 3/3 shingles, intersection2, union4, Jaccard0.5, both containments2/3. Exact rational thresholds, segment boundaries, connected non-equivalence, actual reconstructed passages, deterministic representative reductions and explicit pair limits tested.
- Arithmetic CLI rerun succeeded, now reporting normalized/token exact groups separately from raw strings; short text remains below substantial finding guards.
- Stable constructed fixture reuse-only profile: 320 records, 51,040 candidate pairs, 0 qualifying pairs, complete exact search in 0.560 seconds (excludes preprocessing). Defaults unchanged; this is software behavior, not real-world accuracy.

## M3 representations, windows and manual comparison gate

- Offline full suite: 227 passed in 10.76 seconds; no skipped tests in that run. Includes supplied cosine/JS/Delta oracles, fixed-seed independent SciPy comparisons, manual CLI cases, and window/schema/evidence tests.
- `ahas compare --input fixtures/arithmetic.jsonl --manifest fixtures/arithmetic.snapshot.json --selection design_examples/comparison.json --out output/comparison --overwrite` (offline wrapper): exit0. Raw distances are available with explicit insufficient-comparable-text qualification; no author score.
- Actual stable fixture M3 run: 29 qualified pooled comment windows and94-word remainder,56 adjacent comparisons across pooled/community scopes; analysis phase9.730 seconds, peak RSS163,636KiB reported before disk publication. results.json28,714,632bytes. These are stage measurements, not the final release benchmark.
- Vocabulary-only fixture has one designed masked representation and one surface/function profile across320records; raw n-grams differ. Identifier/file renaming does not affect numerical features. Canonical snapshot hashes correctly reflect supplied metadata changes.
- Bugs fixed with regressions: JS one-sided subnormal midpoint underflow; classical Delta cancellation with a large reference mean (algebraically equivalent abs(fA-fB)/sigma); English subset changes in mixed-language comparisons; selected feature excerpts now use a segment containing the feature when available.
- Reference configuration now parses/hashes one immutable byte buffer, exports that exact reference, and preserves it through sensitivity overrides even if its original file moves. Regression removes the source after config loading and confirms the frozen identity persists.

## M4 optimization development

- Independent exhaustive check caught a pinned ruptures PELT minimum-segment-size pruning defect on [0,9,2,8,3,0,10], penalty0.1/minimum3. Returned cost111.51666666666667 exceeded the legal optimum107.51666666666667. This is an implementation defect, not an unexpected scientific finding.
- Delayed-pruning adaptation initial checks now return boundary4/objective1 for the supplied unique-optimum eight-point oracle, and boundary3/objective107.51666666666667 for the library counterexample. Full exhaustive/DP/scaling/sensitivity gate results are recorded after their execution below.
- Corrected M4 optimizer/scaling tests: 10 passed in2.05seconds, including320 exhaustive N3–10 cases,36 longer multivariate DP comparisons (N11/20/50; minimum sizes1/2/3/4), supplied oracle, upstream counterexample, missing/family scaling, boundary source ranges and process determinism. An additional exploratory1,280 exhaustive cases also agreed.
- Sensitivity tests:14 passed in1.77seconds, including120 independently checked matching cases, record-interval comparisons, executed-setting denominators, edit/repeat views and unchanged primary data.
- Full M4 offline gate:255 passed in17.37seconds. Default pooled-comment outcomes: stable and vocabulary-only fixtures29windows/no_measurable_variation; style-shift fixture29windows/boundary15, record interval[164,165],objective4.183359912439892. No default was tuned to that fixture.

## M5 report, integrity and security gate

- `python3.12 scripts/offline_exec.py .venv/bin/python -m pytest -q`: **285 passed, 1 skipped in 27.38 seconds** before the final placeholder-resource and report-detail checks below. The skipped test is the actual Chromium check, whose required Unix IPC is denied by the analyzer's stronger seccomp filter.
- The same browser regression ran separately: `.venv/bin/python scripts/browser_offline_exec.py env AHAS_RUN_BROWSER_AUDIT=1 .venv/bin/python -m pytest tests/test_security.py::test_out04_real_browser_remote_requests_intercepted -q`: **1 passed in 2.15 seconds**. Its inherited seccomp filter allows only Unix-domain sockets; internet sockets remain denied. CDP also sets offline mode and intercepts resource requests. Chromium needed a narrowly approved execution outside the host's ambient sandbox to initialize its local IPC.
- Chrome 150.0.7871.128 hostile-source audit recorded zero remote requests, dialogs, active source elements, event handlers or unsafe links; injected script marker remained unset. Actual receipt and visually inspected screenshot are in `qa/browser-audit.json` and `qa/hostile-report-browser.png`.
- Separate verification/security/reproduction suite: **16 passed, 1 browser skip in 10.34 seconds**. Whole canonical exports, Markdown, HTML and SVG bytes matched across processes with different hash seeds, timezones, working directories, input row/key ordering and reference-file locations. Tampered artifacts, source and config failed verification; frozen reference replay succeeded after its original file was removed.
- Fixed dedicated-output path handling to reject current-directory ancestors expressed through lexical `..` and symlink ancestors. Targeted artifact tests: **9 passed in 0.05 seconds**.
- Independent audit measured an adversarial placeholder-prefix source at 200,000 code points: **14.886636 seconds** before correction. This is a preprocessing resource bug, not an analytical threshold problem. The final correction and regression outcome are recorded below when completed.
- Corrected URL-placeholder prefix selection uses one bounded raw/entity-decoded marker scan, bounded integer membership probes, and skips setup when no URLs exist. Targeted text/resource/reuse/style-invariance gate: **58 passed in 5.26 seconds**. The same 200,000-codepoint input now takes **0.038016 seconds**; a same-size input including a URL takes **0.040925 seconds**. Dense markers and entity-decoded marker collisions have regression coverage.

- Final focused report gate: **9 passed in 1.71 seconds**, covering arithmetic output, SVG/export equality, corrected label geometry, missing-value breaks, safe source markers/fingerprints, internal references, excerpt omission, empty charts and deterministic render bytes. Corrected arithmetic activity screenshot re-inspected in Chrome; six events in the first UTC-hour bin and one daily bin agree with JSON. M5 closed before M6 implementation began.

## M6 release preparation

- Initial 1,000-record/94,000-retained-word offline preflight, all default modules enabled: **48.72 seconds total wall time**, **707,496 KiB peak RSS**, exit0;178 style comparisons. `/usr/bin/time -v` includes analysis, serialization, charts and atomic publication. Exact command and raw receipt: `benchmarks/preflight-time.txt`. Host: AMD Ryzen7 5800X,16logical processors,16.68GB installed RAM, single numerical worker. This is a constructed formulaic workload, not a worst-case or representative-account guarantee.
- Built the actual reference image from Python3.12.3 slim-bookworm digest `sha256:afc139a0a640942491ec481ad8dda10f2c5b753f5c969393b12480155fe15a63`, with hash-locked runtime/test/build dependencies. Setup used networking; container analyses/tests used `--network none`.
- First container suite: `docker run --rm --network none --env AHAS_NETWORK_ISOLATION=docker_network_none --entrypoint python ahas-reference:1.0.0 -m pytest -q`: **298 passed,1 skipped in37.12seconds**. Chrome/Node are deliberately not shipped in the reference image; that browser regression ran and passed separately on the host. Final source-frozen container checks follow below.

- Full M6 integration before final artifact runs: **353 passed,1 covered browser skip in36.86seconds** under the analyzer seccomp filter. Synthetic evaluator alone:10tests passed5.52seconds; external adapters+metrics:44tests passed4.92seconds. A compact stream-evaluation cache retains only needed summaries and releases full analyses, verified by a weak-reference regression.
- Fresh isolated setup check found the initial documented editable build required the optional `editables` helper. The release instructions now use the ordinary installed wheel build (`--no-build-isolation .`) with the frozen build requirements. That exact installation succeeded in `/tmp/ahas-release-install`; its `ahas validate` returned six arithmetic events and the expected canonical snapshot hash. No global Python packages were changed. Initial offline cache-only dependency setup failed because artifact/index metadata was unavailable; setup was then performed with network access and required hashes. Runtime checks remained kernel-isolated.

## Final frozen-source release results

Engineering status: **complete**. Real-world validation: **not_established**. External corpus evaluation: **not_evaluated — no suitable independently labeled corpus was supplied**. No source-paper accuracy was transferred to this pipeline.

- Frozen implementation fingerprint: `e4c53004244b72b117d1ad900a3b76afa1ecc5a0f4b0a5fa62930e92a04f83a0`.
- Host command `python3.12 scripts/offline_exec.py .venv/bin/python -m pytest -q`: **360 passed, 1 skipped in 38.68 seconds**. Raw log: `qa/host-tests.txt`.
- Rebuilt pinned container, then `docker run --rm --network none --env AHAS_NETWORK_ISOLATION=docker_network_none --entrypoint python ahas-reference:1.0.0 -m pytest -q`: **360 passed, 1 skipped in 52.77 seconds**. Raw logs: `qa/container-build.log`, `qa/container-tests.txt`.
- The skipped test in both suites is Chrome. Frozen-source separate browser command documented above: **1 passed in 2.36 seconds**. Actual Chrome150.0.7871.128 audit recorded no remote requests, dialogs, active source elements, event handlers or unsafe links. Screenshot and receipt were refreshed and inspected. This check is covered, not an unresolved skipped requirement.
- `ahas evaluate --suite synthetic --fixtures fixtures --out evaluation/synthetic` under the offline runner: **67 passed, 0 failed, 0 not-evaluated checks; all six shipped scenarios present**. `evaluation/synthetic/evaluation.json` contains actual per-file hashes, observations, expected arithmetic and construction-boundary geometry; its SHA-256 is `0ad5dca03f5207d79f24a67378c13565f55c2c517ca66127cf701d95f06fdefb`.
- All six original fixture histories were analyzed through the CLI with defaults and exit0. JSON/Markdown/HTML/SVG reports are under `output/<fixture>/`. Their canonical result hashes match the independently executed evaluator runs; every artifact checksum was verified against the supplied snapshot (`qa/final-fixture-integrity.json`).
- `.venv/bin/python scripts/check_release_reproducibility.py qa`: six independent seccomp-denied analyzer processes over the style-shift and edge-case histories. **All 13 checksummed artifacts plus checksums.json (14 files per run) were byte-identical** across original, renamed and reordered inputs, varied nested JSON keys, CWD, TZ and PYTHONHASHSEED. Separate timings:55.64 seconds total. See `qa/reproduction.json` and `qa/reproduction_receipts.json`.
- Arithmetic and constructed-style-shift outputs were regenerated inside the frozen Docker image with `--network none`: **all14 files per fixture match native-host bytes exactly**, including HTML/SVG. See `qa/container-analysis.txt`, `qa/container-reproduction.json`. This establishes those tested host/container combinations only.
- Installed the final wheel in a fresh environment with hash-locked dependencies, ran arithmetic analysis from `/tmp` under seccomp, and compared14artifacts: **all bytes match**. See `qa/wheel-install-verification.json`. Wheel and source distribution built successfully with `uv build --offline`; build log in `qa/build-artifacts.log`.
- Actual CLI comparison and excerpt-free derivative rendering succeeded. `ahas verify ... --recompute` for arithmetic and style-shift both reported **reproduced**; receipts in `qa/verify-arithmetic.json` and `qa/verify-style-shift.json`.
- Final full workload command in `benchmarks/final-time.txt`: **1,000records,94,000retained words,51.13seconds total wall,707,636KiB peak process RSS (691.05MiB),exit0**. Includes all modules, sensitivities, full contribution exports, charts and publication. Both measured targets (<120seconds,<2GiB) were met on the stated Ryzen5800X desktop. `benchmarks/performance.json` preserves input/result hashes and operational analysis receipt. This does not claim worst-case performance at500,000words or performance on every laptop.
- Final style-report review independently recovered **1,187 evidence excerpts** from supplied records/stored offsets and checked all finding/window references and1,292HTMLanchors. Candidate interval[164,165] lies between windows15/16 and supplied IDs ending165/166. Independent SciPy checks matched raw4-gram cosine0.37449014446822915, masked4-gram cosine0.05792072408657245 and base2JS0.04342964020726491 within registered tolerances. Penalized objective4.183359912439892 equals SSE0.8160640824534182 plus ln(29). See `qa/final_style_report_review.json` and the inspected `qa/style-candidates-browser.png`. The construction transition is nearby within a neighboring whole window; no defaults were tuned to align it exactly.

Untested scope: Windows/macOS, other Python versions/CPU architectures, arbitrary math-library builds, worst-case permitted input sizes, and real-world scientific calibration. Optional PAN adapters and all-pair heatmaps are not implemented and are not required V1 modules. A project redistribution license remains the owner's choice. No mandatory V1 engineering requirement is left unimplemented.

## Subsequent releases

This file retains the original1.0.0 operational record. The exact PR #383 update and1.0.1 receipts are documented in [PR383.md](PR383.md). The subsequent four-finding repair, new full workload lifecycle, complete-artifact replay contract, current tests and1.0.2 reports are documented in [AUDIT_REPAIR.md](AUDIT_REPAIR.md). Historical test totals and timings above must not be presented as measurements of the later implementation.
