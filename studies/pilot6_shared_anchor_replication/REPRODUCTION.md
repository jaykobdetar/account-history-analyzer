# Reproducing Pilot 6

Exact reproduction requires the private evidence bundle. The public repository contains methods, programs, aggregate records and hashes; it omits source writing, source-account identities, exclusion maps, constructed histories and native analyzer artifacts. Public files alone cannot reconstruct the cohort or repeat its content audit.

The [execution registration](protocol/EXECUTION_REGISTRATION_V1.json) freezes **nine new source-account pairs, 36 main histories and 36 replays**. The target was ten pairs; the one-pair shortfall is fixed before scoring. The [cohort registration](protocol/COHORT_REGISTRATION_V1.json) and [preparation check](review/prepared-independent-check-01.json) bind that selection. Pilot 5 supplies preserved methods and a prior diagnostic; its cases do not count as new replications.

This guide documents the registered procedure. It does not authorize a new search, replacement cohort, altered tolerance or larger resource limit.

## Required private files and environment

Use the original frozen AHAS 1.0.4 installation and the input locations recorded in the private plans. Those plans contain absolute paths and reject changed hashes. A different host needs a controlled restoration of the recorded layout or a separately recorded relocation/re-registration that preserves every scientific input and rule. Do not edit the archived registrations to make a path check pass.

The bundle must include:

- The ten bound community archives, earlier eligibility metadata, the technical intake supplement, and the exact 119-account exclusion union.
- The protected historical source inventory, its Pilot 5 extension, all candidate buffers, original-source lines/indexes, the completed audit and its registration.
- `prepared-01/cohort-prepared.json`, every pair's `index.json`, `selection.json`, four inputs, manifests and record-metadata files.
- `COHORT_EXECUTION_V1.json`, `EXECUTION_REGISTRATION_V1.json`, per-pair registrations under `execution-registration-01/`, and the independent preparation receipts.
- The preserved earlier-study manifests and all execution dependencies named by those registrations.

The registered interpreter is CPython 3.12.3 on Linux x86_64. The engine uses NumPy 2.4.2, SciPy 1.17.1, ruptures 1.1.10, markdown-it-py 3.0.0 and jsonschema 4.26.0. The complete environment and expanded default configuration are recorded in the execution registration. No analyzer configuration override is supplied.

The original runtime paths are `<INSTALLED_BASELINE>` for the frozen engine and `<REVIEWED_REPO>` for the reviewed source. Preparation matching also uses `<ISOLATED_MATCHING_LIBRARY>`; that isolated matching backend belongs to preparation, not the analyzer. The ordinary analysis workers receive only the engine import path. `scripts/offline_exec.py` installs inherited Linux seccomp socket denial and fixes numerical-library thread counts to one. Setting an environment flag alone does not provide that isolation.

## Verify saved results without rerunning the analyzer

Set the following locations to the restored evidence bundle. `AHAS_REPRO` must be a fresh private directory outside the archived run. Run these commands from the repository root.

```bash
AHAS_REPO=/path/to/account_history_analyzer_v1
AHAS_P6=/path/to/private-evidence/pilot6_private
AHAS_REPRO=/path/to/new-private-review
AHAS_PY="$AHAS_REPO/.venv/bin/python"
AHAS_S6="$AHAS_REPO/studies/pilot6_shared_anchor_replication"
export PYTHONPATH=<INSTALLED_BASELINE>
export PYTHONDONTWRITEBYTECODE=1
mkdir -m 700 "$AHAS_REPRO"
cd "$AHAS_REPO"

"$AHAS_PY" -B studies/pilot4_chronological_controls/scripts/run_logged.py \
  --log-prefix "$AHAS_REPRO/independent-results-check" -- \
  "$AHAS_PY" -B scripts/offline_exec.py "$AHAS_PY" -B \
  "$AHAS_S6/scripts/check_replication_results.py" \
  --registration "$AHAS_P6/EXECUTION_REGISTRATION_V1.json" \
  --run "$AHAS_P6/replication-01" \
  --out "$AHAS_REPRO/independent-results-check.json"
```

These exports apply to the parent verification and orchestration processes as well as their children. The engine import path must match the restored installation path bound by the registrations; using a different editable installation does not reproduce this environment. Metadata enumeration and its independent selection check additionally require `PYTHONPATH=<INSTALLED_BASELINE>:<ISOLATED_MATCHING_LIBRARY>` for the isolated matching backend. Restore the engine-only export before result verification or chronology execution.

This check requires the completed saved run. It makes zero analyzer calls. It reuses the unchanged independent Pilot 5 checker for native primary/window arithmetic and separately verifies every pair's four conditions, all interval errors, full temporal/grid descriptions, unavailable values, operating costs, relocated replay inputs and canonical hashes. Its limit is 600 seconds, 4 GiB address space and 20 MiB of report output. A nonzero exit or a report whose status is not `passed` remains a failed verification.

## Re-execute the frozen cohort

With all bound inputs still present, the runner accepts a fresh private output directory:

```bash
"$AHAS_PY" -B studies/pilot4_chronological_controls/scripts/run_logged.py \
  --log-prefix "$AHAS_REPRO/replication-rerun" -- \
  "$AHAS_PY" -B scripts/offline_exec.py "$AHAS_PY" -B \
  "$AHAS_S6/scripts/run_replication.py" \
  --registration "$AHAS_P6/EXECUTION_REGISTRATION_V1.json" \
  --out "$AHAS_REPRO/replication"
```

Run the independent check above again with `--run "$AHAS_REPRO/replication"` and a new output/receipt prefix. A repeated execution supplies reproducibility evidence and adds no new source-account pairs.

For each registered pair, the wrapper invokes unchanged Pilot 5 `run_diagnostic.py` in this order: `run`, `score`, replay `run`, `replay-check`. Scoring and replay verification call its saved-execution checks. Pair groups run sequentially; each group retains two parallel case workers. Originals use hash seed 0 and UTC. Replays relocate byte-identical inputs and use seed 73129 and Pacific/Honolulu. Every canonical artifact is compared; exactly `ingest_receipt.json` and `run_receipt.json` are excluded.

Per-case limits are 600 seconds, 4 GiB address space and 512 MiB analysis artifacts, with a 630-second outer cleanup guard. A pair retains the 3,600-second dispatch ceiling and 8 GiB original-plus-replay ceiling. The global runner allows 14,400 seconds from first dispatch and 12 GiB execution artifacts, reserving eight × 512 MiB before another pair begins. It stops detached descendants when required, preserves oversized or partial evidence, and retains unavailable/not-dispatched rows. These are termination thresholds; they do not justify deleting evidence that crosses a threshold.

Successful zero-candidate behavior is distinct from unavailability. The fixed inclusive tolerance is ten supplied-record split positions. Source-switch truth remains at the unsnapped construction junction. Continuity-junction alignment is descriptive. Primary windows are selected by their declared `window_ids`, which excludes same-stream sensitivity windows from the primary calculation. All sensitivity artifacts remain private.

## Reconstruct preparation from archived plans

Preparation is a separate reconstruction task. Execute the following entry points only in a staged restoration whose target output paths do not exist. Existing evidence must remain intact. The exact original arguments, environment prefixes, resource wrappers and working directory are retained in the listed command receipts; the saved plans are the authoritative inputs.

| Stage | Entry point and principal arguments | Original command receipt |
| --- | --- | --- |
| Preserve earlier studies and engine | `environment/preserve_prior_studies.py freeze --private-parent ... --private-out ... --public-out ...` | Private `environment-logs/preservation-baseline-01.receipt.json`; public [summary](environment/baseline-execution-summary.json) |
| Supplement technical eligibility | `scripts/intake_supplement.py --plan INTAKE_SUPPLEMENT_PLAN_V1.json --registration INTAKE_SUPPLEMENT_REGISTRATION_V1.json --out ... --private-out ...` | [intake-supplement-01](logs/intake-supplement-01.receipt.json) |
| Extend historical protection | `scripts/prepare_replication.py protect --plan HISTORICAL_EXTENSION_PLAN_V2.json --out ... --public ...` | [historical-extension-01](logs/historical-extension-01.receipt.json) |
| Enumerate the finite metadata universe | `scripts/metadata_replication.py --plan METADATA_PLAN_V2.json --out ... --private-out ...` | [metadata-feasibility-02](logs/metadata-feasibility-02.receipt.json) |
| Independently verify metadata selection | `scripts/check_metadata_replication.py --plan ... --public ... --private ... --out ...` | [metadata-independent-check-03](logs/metadata-independent-check-03.receipt.json) |
| Extract fixed source buffers | `scripts/prepare_replication.py buffer --plan BUFFER_PLAN_V1.json --out ... --public ...` | [buffer-preparation-01](logs/buffer-preparation-01.receipt.json) |
| Verify original-source fidelity and buffers | `scripts/check_replication_prepared.py --buffer-plan ... --buffer ... --buffer-receipt ... --out ...` | [buffer-independent-check-01](logs/buffer-independent-check-01.receipt.json) |
| Audit candidate content and original threads | Pilot 3 `scripts/audit_candidates.py --candidate-pool ... --historical-inventory ... --engine-path ... --rules ... --freeze ... --out-private ... --out-public ...` | [content-audit-01](logs/content-audit-01.receipt.json) |
| Finalize fixed audited samples and cohort | `scripts/prepare_replication.py finalize --plan FINALIZATION_PLAN_V1.json --out ... --public ...` | [cohort-preparation-01](logs/cohort-preparation-01.receipt.json) |
| Independently verify the complete prepared cohort | `scripts/check_replication_prepared.py`, with the buffer arguments plus `--final-plan --prepared --public --audit-freeze --audit-public` | [prepared-independent-check-01](logs/prepared-independent-check-01.receipt.json) |
| Assemble final execution registrations | Private `execution-registration-01/registration-helper.py` | [execution-registration-01](logs/execution-registration-01.receipt.json) |

For example, inspect a recorded command without executing it:

```bash
"$AHAS_PY" -B - "$AHAS_S6/logs/cohort-preparation-01.receipt.json" <<'PY'
import json, pathlib, shlex, sys
receipt = json.loads(pathlib.Path(sys.argv[1]).read_bytes())
print("Recorded working directory:", receipt["cwd"])
print(shlex.join(receipt["argv"]))
PY
```

Metadata selection used exactly 505 community-pair/calendar combinations. The initial metadata failure and the failed independent-check dependency preflight remain archived. The successful lineage is metadata attempt 02 and independent check 03; changing the matching dependency import path did not change a scientific selection rule. No additional cuts, directions, accounts or replacement candidates may be introduced during reconstruction.

The local JSON assembly helper for buffer, audit and finalization is preserved privately as `registration-stage-helper-final.py`, SHA256 `9f7a7e95964205105de4702799a5d5e84a4139750227f77fcf001c876fa332e1`. Its [preservation receipt](environment/registration-assembly-preservation.json) explicitly limits that claim to those later stages. This copy is not claimed to be the byte-original assembler for every earlier metadata registration. Preserve any local assembly helper and its hash before relying on it; the generated frozen stage plans remain the canonical record.

The separate execution assembler is preserved as `execution-registration-01/registration-helper.py`, SHA256 `ada21a6c756059881dff1df9cc8c6eab5f490fa88049353a1437646afd4b2496`, and is bound by the global registration. It requires passing metadata, buffer and final-cohort checks; verifies the audit, exclusions and installed engine; rejects evidence of prior Pilot 6 scoring; and writes a distinct `COHORT_EXECUTION_V1.json`. It cannot be rerun into an already registered evidence directory. Its original local `/tmp` path is not a dependency of future verification.

The private global execution registration has SHA256 `7358f1207b0eab49edc0bc0d20d238b31f36afb7b8a73bd1351656f18518a719` and 367 bindings. Reporting code is separate from those scientific execution bindings. Format a results report only after the independent results check passes, and retain the original aggregate/native artifacts regardless of the resulting interpretation.
