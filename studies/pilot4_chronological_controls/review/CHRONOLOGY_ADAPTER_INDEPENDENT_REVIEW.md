# Independent pre-score adapter verification

No original corpus was analyzed in this verification. Exactly one ordinary frozen CLI analysis used an explicitly synthetic 64-comment, 8,000-word constant history. The primary stream had eight qualified 1,000-word, eight-record windows and native `no_measurable_variation`. Its normalized status is `ok`, with an executed zero-candidate outcome.

The first synthetic check (`chronology-ordinary-synthetic-smoke-01`) failed after that successful analysis. It exposed a real adapter mismatch: `windows.jsonl` includes sensitivity windows with the same stream identifier. Filtering only by stream identifier incorrectly selected 21 windows. The corrected saved-output adapter uses the exact primary stream's declared `window_ids`, validates every declared ID exactly once and in order, and independently checks whole-record membership and volume. This selected eight primary windows and separated 13 sensitivity windows. The legal original-record split intervals were `[24,24]`, `[32,32]`, and `[40,40]`.

The original failed check, successful underlying analyzer receipt and artifacts remain preserved. `tests/smoke_full_chronology.py` retains the original check's pre-correction call signature as the historical attempt. `tests/check_chronology_smoke_saved.py` is the corrected saved-output verification. Rechecking the original artifacts passed in 0.159 seconds, with no additional analyzer or preprocessing invocation. The original ordinary CLI took 8.736 seconds and 153.64 MiB peak child RSS; its 16 saved artifacts total 16,108,518 bytes.

The final combined synthetic runner/scorer suite passed 61 tests and 15 subtests in 0.90 seconds (`logs/chronology-runner-synthetic-02`). It covers exact factorial membership and replay selection, both frozen identities, actual installed distribution/source path and dependency environment, native constant status, missing primary scope, full-pipeline failure, original-record interval validation, 630-second outer worker limits, 600-second analyzer limits, remaining global wall time, process-group cleanup, preserved failure rows, artifact reservations and relocation byte equality. The unchanged production 512 MiB artifact envelope yields a 56 GiB upper bound for 96 primary plus 16 replay cases, below the 64 GiB registered ceiling. Operational logs and study receipts are separate from this analysis-artifact bound.

Final identities:

- Runner: `2318580a40888b1d21ba8036f4f7efdb1cbe9af7d5724361dfedcbf7ec9bc5d8`.
- Runner tests: `0fad15c68e02d4b44300585dc81a599a8b6967de1544c59e708a185105586c07`.
- Saved-output scorer: `1e1e9c39d7fa88a31fc7a0f90647edc52a11deea21ccbc18117e8d9d2463c512`.
- Successful saved synthetic check: `e36ddb45bb527e0ed314495193410a0d5b8e7ebe8c37c792d6c400b564dd31a7`.

These checks establish adapter correctness on the stated synthetic cases, not chronological performance on the planned study. Real execution remains subject to the final pre-score registration and construction gates.
