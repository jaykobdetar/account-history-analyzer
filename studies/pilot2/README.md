# AHAS: RW-001 closure and second Reddit pilot

Start with [the human-readable review](review/REVIEW.html). Full [paired outcomes](review/PAIRED_OUTCOMES.html), [chronological outcomes](review/STREAM_OUTCOMES.html), [preparation coverage](review/PREPARATION_REVIEW.md), [resource costs](review/RESOURCE_COST.md), [actual commands](review/COMMANDS.md), and the [registered protocol](protocol/PROTOCOL.md) remain separate artifacts.

The 1.0.4 production release closes the report-only RW-001 repair. The second pilot preserves the same analytical methods, default guards, dependency locks and PR #383 optimizer. It uses newly authorized local ConvoKit corpora, account-ID proxies and constructed source-account transitions. `real_world_validation: not_established` remains unchanged. The confirmation reserve was not scored.

## Install the working software

Use the separately supplied `account-history-analyzer-1.0.4-source-and-reports.tar.gz` working-source release. Its SHA-256 is `c1f4985fb484698e055a8ee045b42b5ecfb7377b7958bfa2778a7b6e639564cb`. Extract it and run these commands from its project root using CPython 3.12.3 and uv 0.9.21:

```bash
uv venv --python python3.12 .venv
uv pip install --python .venv/bin/python --require-hashes \
  -r requirements.lock.txt -r containers/build-requirements.lock
uv pip install --python .venv/bin/python --no-deps --no-build-isolation .
```

Setup may acquire the exact locked dependencies. Analyses need no network. Linux `libseccomp` is required for the supplied fail-closed offline runner. The source release includes the digest-pinned reference container recipe in `containers/README.md`; the installed 1.0.4 wheel was tested in that dependency environment with `--network none`.

```bash
.venv/bin/python scripts/offline_exec.py .venv/bin/ahas analyze \
  --input fixtures/arithmetic.jsonl --manifest fixtures/arithmetic.snapshot.json \
  --out fresh-example-report
.venv/bin/python scripts/offline_exec.py .venv/bin/ahas verify \
  --input fixtures/arithmetic.jsonl --manifest fixtures/arithmetic.snapshot.json \
  --analysis-dir fresh-example-report --recompute
.venv/bin/python scripts/offline_exec.py .venv/bin/python -m pytest -q
```

## Replay this local study

The complete task workspace retains source archives and protected preparation data in their original local locations. Set `PILOT2_ROOT` to the complete study directory, then run from the software project root. These commands create new output directories and refuse to overwrite prior runs:

```bash
PILOT2_ROOT=/absolute/path/to/ahas-pilot2-20260914
.venv/bin/python scripts/offline_exec.py .venv/bin/python \
  "$PILOT2_ROOT/scripts/run_pairs.py" --jobs 2 --destination outputs/paired-new-replay
.venv/bin/python scripts/offline_exec.py .venv/bin/python \
  "$PILOT2_ROOT/scripts/run_stream_batch.py" --jobs 2 --destination outputs/streams-new-replay
```

Both drivers require every existing scoring-freeze hash to match, including the original prepared sources and study scripts. They never score confirmation files. The full chronological command repeats forty runnable analyses and records twenty unfilled slots; it is not a lightweight integrity-only check. Resource receipts are separate from canonical output.

The sanitized review handoff intentionally omits raw corpora, original prose, account maps, prepared record streams and native source-containing reports. It therefore supports artifact review, not an independent numerical replay by itself. The protected complete local workspace supplies those inputs. Frozen paths/hashes record their identity without redistributing their contents. The user's original private export and first-pilot records remain outside the review handoff and the production source release.

## Actual checks

The repair release passed 658 repository tests with one separately exercised browser skip on both reference host and installed-wheel container, eight original audit/adversarial regressions, 24 reviewer regressions, and the separate browser test. The new study passed 68 combined preparation/driver/oracle tests plus five checks against actual chronological archives. All 72 paired batches and forty available chronological/operational analyses exited successfully; twenty planned slots remain explicitly unfilled.

Independent metric checks covered all 144 paired partitions. Separate process replays reproduced three paired evaluator files, three splice evaluator files and the splice grid diagnostic; natural-history recomputation reproduced fourteen canonical files including Markdown, HTML and five SVGs. Cross-platform byte identity is not claimed. Failed setup/preparation/review-build attempts remain failed in their original logs and explanatory notes.

See `review/BUILD_NOTES.md` for review-only build corrections. No successful historical command was relabeled as executing new code.

Final review commands are indexed in [FINAL_COMMANDS.md](review/FINAL_COMMANDS.md). Navigation-only edits in this distributable copy are recorded in [PORTABLE_LINK_EDITS.json](review/PORTABLE_LINK_EDITS.json). The final ZIP verification and completed packaging receipts are supplied beside the archive.
