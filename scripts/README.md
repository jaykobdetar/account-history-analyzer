# Developer and historical validation helpers

The installed application is the `ahas` CLI and Python package under `src/`. These 15 helpers support development, engineering measurements and preserved release audits. Run them from the repository root with the [locked development environment](../docs/USAGE.md#install). They are not needed for an ordinary installed-package import.

## Routine development

| Helper | Purpose and use |
| --- | --- |
| [offline_exec.py](offline_exec.py) | Run a command and its children with Linux network sockets denied. Requires `libseccomp` and fixes numerical workers to one. Use it for ordinary tests, analysis and validation. |
| [sync_schemas.py](sync_schemas.py) | Check or regenerate the root and packaged schema copies. Prefer `--check` for validation; without it, the helper writes both copies. |
| [browser_offline_exec.py](browser_offline_exec.py) | Run the separate browser audit with internet sockets denied while allowing the Unix IPC that Chrome needs. |
| [check_report_browser.cjs](check_report_browser.cjs) | Inspect a supplied local HTML report in headless Chrome, including intercepted resource requests. Requires Node and Chrome already installed; used by the optional browser test. |

```bash
python3.12 scripts/offline_exec.py .venv/bin/python scripts/sync_schemas.py --check
python3.12 scripts/offline_exec.py .venv/bin/python -m pytest -q
```

The [development guide](../docs/DEVELOPMENT.md#routine-verification) gives the separate browser-test command. The browser helper permits different IPC from the ordinary offline runner; use the documented wrapper for each task.

## Engineering workloads and historical release validation

These helpers retain the paths and assumptions of their original audits. Review their arguments and the linked release record before running them. Supply new output and receipt destinations rather than overwriting historical evidence. Some require a separately available frozen release archive or explicitly supplied private study; those inputs are not fetched by the helper.

| Helper | Purpose and required context |
| --- | --- |
| [generate_benchmark.py](generate_benchmark.py) | Generate the fixed 1,000-record synthetic workload from the fixture constructor. `--out` defaults to the tracked `benchmarks/input/`; choose a new destination for a comparison copy. |
| [probe_reuse_resources.py](probe_reuse_resources.py) | Measure reuse work on generated exact/edited text after preprocessing. Requires the offline runner and an explicit `--out`; produces engineering cost evidence. |
| [check_audit_roundtrip.py](check_audit_roundtrip.py) | Analyze, verify, recompute and render the fixed `benchmarks/input/` workload. Requires explicit `--out` and `--receipts` directories; belongs to the [audit repair](../docs/AUDIT_REPAIR.md) lifecycle checks. |
| [check_release_reproducibility.py](check_release_reproducibility.py) | Compare canonical artifacts across independent offline processes with changed paths, ordering and environment settings. Give a new destination for reports and operational receipts; run against a fixed package/environment. |
| [benchmark_pelt_pr383.py](benchmark_pelt_pr383.py) | Compare the original optimizer and pinned PR #383 wrapper using the frozen 1.0.0 archive. `--archive` supplies the historical input; `--describe` validates provenance without running an optimizer. See [PR383](../docs/PR383.md). |
| [check_pr383_fixture_reports.py](check_pr383_fixture_reports.py) | Recompute fixture reports and compare the original PR #383 measurements. Defaults refer to `output/pr383/` and `qa/pr383/`; use fresh `--outroot` and `--qa` paths. |
| [check_audit_fixture_reports.py](check_audit_fixture_reports.py) | Analyze, recompute and rerender all six fixtures for the audit repairs. Defaults refer to `output/audit-repair/` and `qa/audit-repair/`; use fresh paths and the intended frozen fingerprint. |
| [check_rw001_preservation.py](check_rw001_preservation.py) | Compare the 1.0.4 presentation repair with the immutable 1.0.3 source archive. This is a source-preservation audit, not a new numerical analysis. Requires the original baseline and a new receipt. See [RW001](../docs/RW001.md). |
| [check_rw001_private.py](check_rw001_private.py) | Rerender an explicitly supplied protected study into a new private directory outside the study and repository. It reads the original study without modifying it and preserves stored numerical results; it does not supply the private inputs. |
| [render_rw001_fixture.py](render_rw001_fixture.py) | Create synthetic presentation-regression reports using a helper in `tests/test_sensitivity_overview.py`. Candidate/status facts are deliberately constructed; these outputs are renderer checks, not optimizer accuracy evidence. |
| [package_release.py](package_release.py) | Historical source-and-reports collector. It recursively collects files with a small exclusion list and writes versioned release artifacts. It is not the sanitized study-publication workflow. |

**Do not run `package_release.py` in a workspace containing private data.** It does not honor `.gitignore` or restrict collection to tracked files, and it does not exclude private study inputs or results. It can also replace artifacts under the current `release/<version>/` path. Preserve the existing release assets and use the reviewed publication process for study evidence.

The root [schema copies](../schemas/), [configuration](../config/), [fixtures](../fixtures/), [tests](../tests/) and these script paths are active developer dependencies. Moving them can break helper imports, historical comparisons or packaging. A new validation run has its own receipts; an old receipt continues to describe its original code, paths and environment.
