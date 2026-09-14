# AHAS 1.0.2: four audit repairs

This update addresses AHAS-AUD-001–004 at the user's direct request. It preserves the exact pinned ruptures PR #383 backport from 1.0.1. Engineering checks and synthetic construction checks do not establish real-world scientific validity.

## Changes and independent gates

| Finding | Reproduced failure in installed 1.0.1 | Repair and executable contract |
| ---| ---| ---|
| AUD-001 | Default 1, 000-record analysis published 92, 001, 915 bytes of results; verification exited 4 at the 50 MiB source limit. | `artifact_io.py` separates generated-file/bundle/count/metadata bounds from input. `io.py:canonical_chunks` streams canonical JSON; `artifacts.py` stages bounded complete publication and streams checksum reads. `tests/test_artifact_streaming.py` checks actual 256 MiB+1 sparse-file refusal before opening, configured exact/+1 edges, strict readers, immutable canonical-byte equivalence and atomic rollback. |
| AUD-002 | All six 1.0.1 initial reports differed from canonical-JSON rerenders; recursive map reversals changed MD/HTML in both excerpt modes. | `reporting.py` fixes semantic status order and sorts map-derived rows; `evaluation_reporting.py` serializes nested maps deterministically while preserving lists. `tests/test_render_order.py` exercises immutable inputs, nested reversals, actual CLI publication/rerender, both modes and structured evaluator values. |
| AUD-003 | Quadratic repeated-token evidence work survived a distinct-candidate limit of one. | `reuse_matching.py` uses exact segmented suffix-automaton matching; `reuse.py` budgets repeated posting visits, matching and evidence work, withholding all partial near outputs on exhaustion. Independent substring-table and exhaustive scan oracles verify ties/segments; see `REUSE_RESOURCE_POLICY.md` and `tests/test_reuse_resources.py`, `test_reuse_adversarial_review.py`. |
| AUD-004 | A hyperlink with a URL inside a descriptive label counted twice, including different label/destination hosts. | `text.py` tracks hyperlink-label context, retains descriptive words and URL exclusion boundaries, and counts the destination only. `tests/test_link_labels.py` covers plain/autolink/mixed/formatted/code/quoted labels, different hosts, and independent same-destination hyperlinks. |

`verification.py` additionally makes `verify --recompute` a complete canonical-artifact replay. The independent `tests/test_recompute_artifacts.py` gate proves that forged MD/HTML/SVG with correspondingly edited checksums passes integrity-only checking but fails replay (CLI exit 5). Original excerpt mode is derived from canonical config, never operational receipts. Receipts may be absent or edited without changing replay. The checksum manifest itself must reproduce byte for byte.

The source input ceiling is unchanged. Generated bundles support 256 MiB per file, 512 MiB total, 32 files, and 1 MiB each for config/checksum metadata. Config may tighten ceilings. Full feature contributions and source evidence are retained; no serialization rounding, sampling, truncation or statistical threshold change was used. JSON parsing remains in memory within these bounds; the envelope is not a universal memory/runtime guarantee. See `DECISIONS.md` for the scope and version compatibility decisions.

## Actual validation record

The complete host suite passed **553 tests**, with one browser-only skip in **83.75 s** (`qa/audit-repair/full-tests.log`). The separate browser test passed **1 test in 2.06 s** under internet-socket denial (`browser-test.log`). The synthetic evaluator passed **67 checks**, with 0 failed and 0 not evaluated (`evaluation/audit-repair/synthetic/evaluation.json`). Dependency pins and scientific thresholds are unchanged. All release checks below were executed; no pending check is counted as passed.

Completed focused gates: 145 combined artifact/reuse/schema/verification tests; 9 independent all-artifact replay tests; 34 reporting/evaluator/safety tests with one separately runnable browser test skipped. The broader report test run initially encountered a temporary old-schema/new-payload transition and one test that incorrectly changed a receipt instead of canonical excerpt config. These were corrected and the clean gate rerun; failed intermediate logs are retained. Independent link-label tests passed 72 tests. The supplied baseline regression file produced 2 failures and 1 opt-in skip before the repair; all three tests, including the opt-in full pipeline round trip, subsequently passed in 160.78 s (`supplied-regressions-after.log`).

## Measured complete artifact lifecycle

The installed 1.0.1 baseline analysis took 48.50 s and peaked at 721, 376 KiB RSS; it published 92, 001, 915 bytes of results and then failed verification with exit 4. The repaired release completed every required stage in a separate network-denied process, with no other AHAS validation job intentionally started during these measurements:

| Stage | Wall seconds | Peak RSS KiB | Exit |
| --- | ---: | ---: | ---: |
| analyze | 71.36 | 534, 452 | 0 |
| verify | 25.45 | 346, 472 | 0 |
| recompute | 77.41 | 533, 844 | 0 |
| render | 27.75 | 349, 356 | 0 |

The repaired result is **92, 002, 224 bytes**, and its full 16-file bundle is 119, 192, 853 bytes. Reuse completed all 499, 500 candidates within 209, 280, 929 work units, with 70, 977 postings; no partial near findings were emitted. Full replay reproduced all 13 checksummed artifacts plus `checksums.json` (**14 canonical files**). A separate render regenerated Markdown, HTML and five SVGs with **exact byte equality**. Every full feature contribution remains in `results.json`.

Analysis/publication met the stated <120 s/<2 GiB goals on this Ryzen 5800X reference desktop: 71.36 s and 521.93 MiB. The baseline was faster at 48.50 s and used 704.47 MiB. The repaired pipeline is slower in this observation; it performs additional work accounting and streams serialization to reduce large temporary copies. These are measured trade-offs, not a claim of overall throughput improvement. Replay/render durations are separately reported and are not included in the analysis-stage target.

The complete command list, per-stage timing/stdout/stderr, all artifact hashes/sizes, input hashes and comparisons are in `qa/audit-repair/benchmark-lifecycle-receipt.json`; machine information is in `hardware.json`. The full generated bundle is `benchmarks/audit-repair-report/`. The baseline failure is preserved in `baseline-benchmark-verify-receipt.json`, with its actual exit 4, input limit and result size.

## Commands

Install and basic commands are in `../README.md`; exact dependency pins and accepted hashes are unchanged. The supported reference is Linux x 86_64 CPython 3.12.3 with the locked numerical dependencies. Analysis/test commands use the Linux seccomp network-denial runner; container executions use `--network none`. Build setup uses frozen hashes and the existing offline dependency cache. Use fresh output destinations when rerunning these commands; existing release bundles are preserved by default.

```bash
python3.12 scripts/offline_exec.py .venv/bin/python -m pytest -q
python3.12 scripts/offline_exec.py .venv/bin/python scripts/check_audit_roundtrip.py \
  --out benchmarks/audit-repair-report --receipts qa/audit-repair
python3.12 scripts/offline_exec.py env AHAS_RUN_LARGE_ROUNDTRIP=1 \
  .venv/bin/python -m pytest qa/audit-repair/supplied-probes/test_review_regressions.py -q
python3.12 scripts/offline_exec.py .venv/bin/python scripts/check_release_reproducibility.py qa/audit-repair
python3.12 scripts/offline_exec.py .venv/bin/ahas evaluate \
  --suite synthetic --fixtures fixtures --out evaluation/audit-repair/synthetic
```

## Scope limits

The 1, 000-record workload is formulaic, contains 94, 000 retained words, and is not a maximum-input or representative real-account study. Work counters are deterministic engineering reservations, not probabilities, confidence or measured CPU instructions. Exact grouping and feature extraction remain separately input-bounded. Resource-limited near search remains explicitly incomplete; the presence of exact results does not reassure about missing near results.

No external research dataset was fabricated or downloaded, and real-world validation remains `not_established`. No cross-platform byte-identity claim is made. Only environments, workloads, processes and tests with actual receipts below count as observed results. Historical 1.0.0/1.0.1 archives and operational receipts retain their original meaning.

## Completed release checks and artifacts

| Actual check | Outcome | Durable receipt |
| --- | --- | --- |
| Full host suite | 553 passed; 1 browser-only skip; 83.75 s |`qa/audit-repair/full-tests.log` |
| Full reference-container suite, network disabled | 553 passed; 1 Chrome/Node-unavailable skip; 112.43 s |`container-tests.log` |
| Separate host browser regression, internet sockets denied | 1 passed; 2.06 s |`browser-test.log` |
| Supplied audit regression file, large round trip enabled | 3 passed; 160.78 s |`supplied-regressions-after.log` |
| Synthetic construction/numerical evaluator | 67 passed; 0 failed; 0 not evaluated |`evaluation/audit-repair/synthetic/evaluation.json` |
| Six fresh fixture analyses/full replays/rerenders | 18 CLI processes succeeded; 14 canonical files reproduced and 7 presentations byte-identical per fixture; 3, 539 evidence slices resolved |`fixture-validation.json`, `fixture-receipts.json` |
| Six separate processes: 2 fixtures × 3 path/input/key-order/hash-seed/TZ variants | All 14 canonical files byte-identical per fixture |`reproduction.json`, `reproduction_receipts.json` |
| Source host versus reference container: arithmetic and style-shift | 14 canonical files per fixture byte-identical; full replay passed |`container-comparison.json`, `container-fixture-receipt.json` |
| Two isolated wheel builds and fresh installed package | Identical wheels; installed import/fingerprint/vendor provenance and 14-file arithmetic replay/source comparison passed |`wheel-verification.json` |
| Style HTML top, reuse resource table and candidate section in Chrome 150.0.7871.128 | Screenshots inspected; no remote requests, active elements, event handlers, unsafe links, dialogs or source execution |`style-browser.json`, `style-reuse-browser.json`, `style-changes-browser.json` and corresponding PNGs |
| Historical preservation and frozen dependencies/PR 383 | 777 historical files unchanged; dependency locks and all vendor bytes unchanged (only project metadata version normalized) |`preservation.json` |

Receipt basenames in this table are relative to `qa/audit-repair/`, except explicitly rooted paths. Container and fixture durations may include concurrent validation jobs; only the separately described benchmark and repeated-text probes are performance observations. Browser checks are skipped in the strict analyzer/container suites for explicit environment reasons and passed in their separate supported host run. Windows/macOS, other architectures/library builds, worst-case permitted histories and real-world datasets were not tested.

Commands for the additional release checks:

```bash
python3.12 scripts/offline_exec.py .venv/bin/python scripts/check_audit_fixture_reports.py \
  --expected-fingerprint 583043074c28db2c91b62c33dc0197a569e863f4c83a80197c509324d9cb4fac
docker build --network none --pull=false -f containers/Dockerfile -t ahas-reference:1.0.2 .
docker run --rm --network none --env AHAS_NETWORK_ISOLATION=docker_network_none \
  --entrypoint python ahas-reference:1.0.2 -m pytest -q
.venv/bin/python scripts/browser_offline_exec.py env AHAS_RUN_BROWSER_AUDIT=1 \
  .venv/bin/python -m pytest tests/test_security.py::test_out04_real_browser_remote_requests_intercepted -q
.venv/bin/python scripts/browser_offline_exec.py node scripts/check_report_browser.cjs \
  output/audit-repair/constructed_style_shift/report.html qa/audit-repair/style-report.png
UV_CACHE_DIR=/tmp/ahas-uv-cache uv build --python .venv/bin/python \
  --offline --no-build-isolation --out-dir dist
```

Exact isolated wheel setup/build/install commands are in `qa/audit-repair/wheel-verification.json` and its adjacent script/logs; they use cached hash-locked dependencies, then run installed analyses under seccomp from an unrelated working directory. The tested wheel SHA-256 is `f0f1fdd9e07c29f35510d77a06fa8319ddd431d45accdfc380f587491e3b1eb6`. Final documentation-only source-distribution rebuilding is separately checked against that identical tested wheel; it does not imply an additional numerical test run.

The implementation fingerprint is `583043074c28db2c91b62c33dc0197a569e863f4c83a80197c509324d9cb4fac`. Its reference environment is `CPython-3.12.3;Linux;x86_64;numpy=2.4.2;scipy=1.17.1;ruptures=1.1.10;markdown-it-py=3.0.0;jsonschema=4.26.0`. The tested host/container identity is the scope of the byte-reproduction claim. Source/data files and operational receipts remain separate.

Fresh JSON/Markdown/HTML samples for all six shipped fixtures are in `output/audit-repair/`. The source-and-sample-report archive is `release/1.0.2/account-history-analyzer-1.0.2-source-and-reports.tar.gz`. The full benchmark bundle is separately packaged as `release/1.0.2/account-history-analyzer-1.0.2-benchmark-report.tar.gz`, avoiding the need to read a 92 MB JSON file through a document previewer. Release checksum inventories are alongside those archives. Setup and exact public CLI commands are in `README.md`; the digest-pinned container recipe is in `containers/README.md`.

All four requested repairs and their mandatory correctness/resource/reproduction checks are complete. External scientific validation remains unestablished. No earlier release receipt was rewritten to claim these new outcomes.
