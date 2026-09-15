# Verification evidence

Start with the [complete results report](../results/REPORT.md). The checks here retain unsuccessful attempts as well as their successful successors; a failed preflight is not a scientific analyzer outcome.

| Check | Current record | What it establishes |
| --- | --- | --- |
| Metadata enumeration | [Independent check 03](metadata-independent-check-03.json) | All 505 cuts, directions, exact costs, matching and exclusions agree. Attempt 02 stopped at dependency preflight and remains preserved. |
| Source buffers | [Independent buffer check 01](buffer-independent-check-01.json) | The 100 fixed source cells, metadata lineage and byte-original source fields agree. |
| Final construction | [Independent prepared check 01](prepared-independent-check-01.json) | All 20 post-audit decisions, nine selected pairs and 36 histories agree, including the unsnapped junctions and legal grids. |
| Native results and replays | [Independent results check 01](results-independent-check-01.json) | Saved primary windows, every interval/error, unavailable values, full module states, replay comparisons and operating ledgers are checked without new analyzer calls. |
| Earlier-study preservation | [Final preservation check](../environment/preservation-final-01.json) | Prior study inputs, registrations, results, receipts and frozen engine identities are compared with the initial inventory. |

The preliminary publication scan covers the files that existed before results were added. [Final publication verification](../PUBLICATION.md) is documented separately; a preliminary scan is not evidence for later files.

The new study tooling passed 162 combined synthetic checks; the report transformation passed 12 additional checks. Logs in `../logs/` and `../environment/` preserve individual draft failures, corrected checks, command timings and hashes. The original metadata-attempt code and the earlier prepared-checker draft remain archived for hash reconciliation. The report generator changes presentation only and is excluded from scientific execution bindings.
