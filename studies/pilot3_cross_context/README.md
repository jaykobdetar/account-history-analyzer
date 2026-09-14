> **Publication copy.** Scientific results and Python code are preserved; operational paths are sanitized. Hashes stated in the study and `ARTIFACT_MANIFEST.json` refer to the original local artifacts. Use [PUBLICATION_MANIFEST.json](PUBLICATION_MANIFEST.json) for published-file hashes and [PUBLICATION_NOTE.md](PUBLICATION_NOTE.md) for the redaction policy. Redacted receipts preserve recorded evidence but require local path reconstruction before command reuse.

# AHAS pilot 3: completed cross-context comparison study

Start with the [decision report](review/REVIEW.md). The full registered design was executed: 60 previously unscored source accounts, 30 matched blocks, three community pairs, three methods, four omission arms, 360 main batches and 120 fresh replay batches. This evaluates account-related comparison ordering and availability, not a classifier or human/bot identity.

## Results and evidence

|Artifact|Contents|
|---|---|
|[Decision report](review/REVIEW.md)|Findings, uncertainty, context and omission effects, residual confounding, execution and limits|
|[Every case: CSV](results/analysis/case_rows.csv) / [JSON](results/analysis/case_rows.json)|All 5,760 planned observations, including null qualified scores and raw distances|
|[Anchors](results/analysis/anchor_rows.csv) / [blocks](results/analysis/block_rows.csv)|All repeated-anchor outcomes and complete/incomplete block counts|
|[Method/context/missingness tables](results/tables/method-context-missingness.csv)|All 36 method/arm/stratum summaries, class counts, rankings, intervals and reasons|
|[Omission intersections](results/analysis/omission_intersections.csv)|Registered paired complete-block changes on full/omission intersections|
|[Distance distributions](results/tables/distance-distributions.csv) / [case intersections](results/tables/distance-omission-intersections.csv)|Qualified and raw values separately; descriptive qualifying-case distance shifts|
|[Full cells](results/tables/full-cell-statistics.csv) / [matching and date gaps](results/tables/pairing-and-time-gaps.csv)|Actual whole-record budgets, overshoot, record lengths, longest-record shares, dates and residual imbalance|
|[Unit omissions](results/analysis/unit_rows.csv)|All 960 planned unit/arm observations and unchanged guard qualification|
|[Analysis metadata](results/analysis/analysis.json)|Registered methods, retained planned strata, dependency units, bootstrap generator/seed/draw digest and limitations|
|[Resource observations](results/normalized/batch-resources.json)|Main per-batch execution, sample volumes, peak memory and artifact bytes|
|[Complete execution receipts/resources](results/execution/batch-resources.json) / [summary](results/execution/resource-summary.json)|All 480 main/replay invocations; marked local-path substitutions, original receipt hashes and observed volumes|
|[Preparation check](review/prepared-independent-check-01.json)|Full membership, source preservation, pair matching, omissions, groups and batch hashes|
|[Raw-distance check](review/raw-distance-independent-check-01.json)|72 predetermined comparisons, including 36 unavailable qualified scores|
|[Arithmetic check](review/analysis-independent-check-01.json)|Independent calculation of every outcome and all 171 bootstrap series|
|[Replay check](review/replay-check-01.json)|120 fresh replay batches and 360 byte-identical canonical artifact comparisons|

## Registration and source history

The [registered protocol](protocol/PROTOCOL.md), [analysis plan](protocol/analysis-plan.json), and [final scoring freeze](protocol/scoring-freeze.json) were fixed before the first study score. The final freeze SHA256 is `78b0f84cd0d451b3ebb53eac68ad297e959c0f273b5e5d1873ded836a374ab94`; protocol SHA256 is `cee0c320b544e1b2d429adc827dff1475ea596494025ec7e82624611cd625337`.

[Gate A feasibility](review/gate-a-final/FEASIBILITY.md), [source inventory](review/gate-a-final/source-inventory.csv), [Gate B audit](review/gate-b-audit-01.json), and [final cohort metadata](review/final-cohort-01.json) explain the fixed community pairs, calendar boundaries, eligibility, mandatory exclusions and contamination filters. Earlier census failures, amendments, drafts, unsuccessful commands and their receipts remain in `protocol/`, `review/`, `inventory/` and `logs/`; later success does not replace those observations.

Original source text, account/source maps, conforming input snapshots, thread/content provenance, private exports and unredacted engine outputs are retained outside this study directory in a private workspace. They are not part of the publishable result tables. Archive data are authorized for this local analysis; public redistribution rights for original writing were not established. Public case IDs identify study positions rather than source usernames. The protected confirmation reserve was not scored.

The CSV/JSON `same_author` and `different_author` labels preserve the evaluator's required contract enums. Here they mean **same-source-account** and **different-source-account** proxies only; they do not identify verified human authors.

## Reproduction

The numerical baseline is the noneditable AHAS 1.0.4 installation from [reviewed commit ea41d82](https://github.com/jaykobdetar/account-history-analyzer/tree/ea41d82ecc3f6585a7dc2bca92ede34740f0b62d). `environment/` records the package wheel, pinned dependencies, resolved analytical configuration, explained editable-metadata discrepancy and actual installed guard tests. The unchanged wheel is archived privately as well as hash-bound in the environment evidence.

The original exact commands, working directories, environments, wall times and exit codes are recorded in the JSON receipts under `logs/`; per-batch originals accompany private main/replay execution indices. Start/finish timestamps establish that registration preceded scoring. Reproduction requires the authorized private files and the original hash-bound paths, or an explicitly documented operational relocation preserving all registered bytes and rules. Missing private data are not replaced by public case summaries or synthetic writing.

`run_scoring.py` validates the frozen package/configuration, 6,917 bound artifacts and complete 360-batch design before dispatch. It requires the existing socket-denial offline runner. Main environment is `PYTHONHASHSEED=0`, `TZ=UTC`, `LC_ALL=C.UTF-8`; the registered replay uses `73129`, `Pacific/Honolulu`, and `C.UTF-8` with copied equivalent inputs and a separate process. Use fresh output/log directories: runners refuse to overwrite evidence. The replay selector always retains all methods and arms in the fixed first stratum.

For normalized-output reproduction, run `analyze_cases.py` with the retained cases, units, dependency map and `protocol/analysis-plan.json`, choosing a fresh output directory; then run `check_analysis_results.py` against those outputs. This needs no original prose and computes no new distances. All 10,000 global dependency-unit draws and missing-replicate rules remain fixed. `output-hashes.json` binds the canonical analysis files.

Synthetic study checks are in `tests/`. The actual successful combined test receipt uses the isolated installed package and the pinned prior audit engine through `AHAS_PILOT3_ENGINE_PATH`; omitting that setting in this handoff workspace caused the preserved earlier fixture-setup errors. The successful run passed all 414 study tests, and the installed baseline guard run passed 59 checks.

`tabulate_results.py`, `build_decision_report.py`, and later receipt/privacy packaging helpers are explicitly post-registration reporting utilities. They expose already computed outcomes and execution observations; they do not change frozen selection, methods, arms, metrics, thresholds, code identities or any scoring result. Operational absolute paths in original evidence are preserved; any separately sanitized receipt copy identifies redactions and keeps the original hash.
