# Setup and discovery attempts outside the logged study runners

These are operational setup observations, not experiment results. Tool outputs
from this task recorded the following failures, which were not reruns of data.

- Workspace discovery returned exit2 because a pre-existing `qa/rw001/container-wheel/arithmetic`
  directory was unreadable. An independent directory listing and targeted reads
  continued; that directory was not needed for this study.
- Git status/remotes failed because the supplied handoff workspace's `.git`
  directory is empty. No repository history was overwritten or reconstructed.
- Initial `git ls-remote` for the supplied GitHub repository returned exit128
  because the sandbox could not resolve github.com. An approved isolated clone
  to `<PINNED_SOURCE>` succeeded with exit0, followed by a detached
  checkout of `ea41d82ecc3f6585a7dc2bca92ede34740f0b62d` with exit0.
- One setup read expected `prepare_paired.py`; the pinned filename is
  `prepare_pairs.py`. The corrected read succeeded. No code or data was run.
- A staging helper returned exit1 when the physics metadata proposal had not yet
  been written by its independent researcher. Its prior actions preserved the
  original scoring draft and corrected the current draft's bootstrap percentile
  description to match the tested type-7 implementation. No data or scores ran.
- A readiness listing for `expanded_capacity.py` returned missing-file diagnostics
  while that helper was still being implemented. No census was launched by it.

Exact evaluation/preprocessing/acquisition/test commands, starts, finishes,
stdout/stderr hashes and exit codes are retained in the adjacent JSON receipts.
The discovery receipt labels observed and unavailable telemetry explicitly.

Further setup observations, before the final mathematics census:

- A read looked for offline_exec.py under the new study scripts directory; it is the existing workspace scripts/offline_exec.py. The subsequent logged census launcher initially omitted its Python executable, returned exit1 without opening corpus inputs, and was corrected in a separately retained attempt02 receipt.
- A discovery search again encountered the same pre-existing unreadable qa directory; it did not affect the study. A schema lookup initially used schemas/record*; the installed schema is contracts/record.schema.json.
- A source-schema projection read one first-row JSON object from the already acquired AskAcademia archive solely to confirm top-level and metadata keys. Text and identifiers were withheld from its output; it performed zero preprocessing or scoring calls. This extra one-record metadata read is outside the two census passes.
- census-04 attempt02 exhausted the source-record limit at its2,010,000-row checkpoint before preprocessing. Its genuine failure is documented in AMENDMENT_04_METADATA_LIMIT_CORRECTION.md, and census-04b is a new bounded attempt, not a retroactive successful receipt.

- A final export orchestration call contained a JavaScript syntax error before any process launch; the unchanged exporter then ran successfully in registered-export-01. The first combined pre-score synthetic test launch omitted AHAS_PILOT3_ENGINE_PATH, producing398 passes and16 fixture setup errors because the handoff workspace lacks pilot2/scripts/leakage_audit.py. No assertions failed. Attempt02 supplies the pinned audit engine path and retains the original failure receipt. No study scores were computed by either test run.
