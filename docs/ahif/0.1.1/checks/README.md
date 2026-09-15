# Actual execution receipts

These receipts concern this local contract review on 2026-09-15. The immutable original `../../history/0.1.0/checks/` receipts are historical and were not edited.

- `verification.json` and `tests.log`: latest actual run of `reference/run_checks.py`, with runtime/dependency versions, test outcomes, per-bundle counts, canonical status, input hashes, regeneration, frozen-file checks and explicit non-execution claims.
- `historical-rerun.log`: new execution of the unchanged 0.1.0 reference suite (40 tests), kept separate from new-version outcomes. `historical-members.json` binds all 35 preserved original files; 34 entries in the original SHA256SUMS are checked independently.
- `initial-revision-tests.log`: intermediate 0.1.1 run of the inherited 40 cases.
- `review-tests-attempt1.log`: intermediate 58-test expanded suite, before the last exact-token/list-coverage cases.
- `final-run-attempt1-tests.log` / `final-run-attempt1-verification.json`: preserved failed 60-test run (12 failures, 29 errors, including subtest outcomes). An introduced UTC regex accidentally omitted the minute component while replacing Unicode digit classes. The existing timestamp/bundle tests exposed it; it was corrected before final verification. These are failures, not skipped or successful checks.
- `regeneration.log`: schema/example generation in an isolated temporary directory, compared byte-for-byte with 27 checked-in generated files. Historical generators/files are never regenerated in place.
- `frozen-boundary.json`: before-review hashes for 74 frozen code/schema/settings/resource/root files, rechecked after work. Studies, private exports, output evidence and credentials were not opened for validation. There is no readable Git checkout metadata; no commit or Git cleanliness claim is made.
- `historical-source.json`: digest of the supplied ZIP and direct member-byte comparison against the preserved history (not an authenticity claim).

The final run checks six canonical positive bundles, 24 named negative mutation recipes plus adversarial tests, and a fixed 25-vector restricted-domain Python/Node canonical comparison. That comparison is not a full RFC 8785 conformance suite. Negative fixture and resource-limit tests are not production ingestion assurance. No engine numerical analysis, real-source pilot, source normalizer, converter, collector, publication or external account action ran.

Run the commands in `../../README.md` to obtain fresh results. The runner refreshes its latest receipt/logs and leaves the named development-attempt logs intact. A future dependency/runtime/fixture change needs new evidence; these results are scoped to the recorded inputs and environment.
