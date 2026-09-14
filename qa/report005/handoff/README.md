# AHAS 1.0.2 independent review handoff

Read REVIEW.md for findings and scope, NEXT_AGENT_PROMPT.md for the small remaining report task, and INDEPENDENT_CHECKS.json for structured results.

This archive is a review, not an updated analyzer. No repaired application or reference runtime is included. Original reference-host/container logs remain in the user-supplied source archive; this bundle contains the reviewer execution evidence.

## Re-running focused checks

Use the project's documented reference environment where available. Set paths explicitly:

```sh
ROOT=/path/to/account_history_analyzer_v1
HANDOFF=/path/to/this/handoff
export PYTHONPATH="$ROOT/src"
export AHAS_SOURCE_ROOT="$ROOT"
python -m pytest --noconftest -q "$HANDOFF/scripts/test_independent_repairs.py"
python -m pytest --noconftest -q "$HANDOFF/scripts/test_ngram_label_contract.py"
```

The second command is expected to fail on unchanged 1.0.2 and should pass after a correct lossless-label repair. The reference project itself should use its normal full test profile; `--noconftest` above concerns standalone reviewer tests, which do not need Hypothesis.

Additional scripts take positional paths:

```sh
python "$HANDOFF/scripts/check_package.py" "$ROOT" /path/to/audit-repair-report package.json /path/to/account-history-analyzer-1.0.1-source-and-reports.tar.gz
python "$HANDOFF/scripts/check_reports.py" "$ROOT" report-roundtrips.json
python "$HANDOFF/scripts/probe_ngram_labels.py" "$ROOT" ngram-labels.json
python "$HANDOFF/scripts/check_reuse_growth.py" "$ROOT" reuse-growth.json
python "$HANDOFF/scripts/republish_saved.py" /path/to/audit-repair-report /fresh/republished-directory republish.json
```

`check_reuse_growth.py` uses the unchanged 1.0.1 reuse module preserved in evidence/baseline_reuse_101.py, against the same prepared features as the current implementation. It performs single-run measurements; do not interpret its speed ratios as universal guarantees.

`republish_saved.py` deliberately re-publishes supplied analytical values. It does not recalculate those values and must not be called a full numerical reproduction.

All analytical checks during this review ran under the supplied seccomp runner. To use it, prefix a command with `python "$ROOT/scripts/offline_exec.py"`. Environment/version limitations and omitted checks are in REVIEW.md.
