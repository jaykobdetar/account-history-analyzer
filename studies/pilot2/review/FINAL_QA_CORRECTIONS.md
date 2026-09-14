# Review-only QA corrections

The first final-handoff checker stopped on a false positive: the frozen `protocol/resolved_config.json` has a legitimate `text` configuration object, and the generic private-field rule rejected that key. This was a checker error, not evidence that source prose had entered the handoff. The failed checker source is preserved in `review/final-handoff-check-first.source.py`; its actual failing command, exit code and traceback remain in `review/final-handoff-check-first.receipt.json` and the corresponding raw logs.

The exception is narrow: only the exact `protocol/resolved_config.json` path may use that typed configuration object, and the staged file must be byte-identical to the frozen original. String-valued `text`, other private source fields, and `text` objects in other JSON documents remain rejected. A regression tests the permitted configuration mapping and both forbidden cases. The review-checker test run passed 19 tests under network-denying seccomp; see `review/final-handoff-regression-tests.receipt.json` and its stdout/stderr logs. No production source, configuration, frozen study script, prepared input or recorded numerical outcome changed.

The independent outcome check also requires `final_source_accounts` to be an integer equal to eight and independently counts eight saved source-account files. This guards the main review builder's earlier `len(integer)` source-count mistake without changing the frozen adapter. That builder's own failed source/log remain preserved by the root workflow.

The separate resource-cost helper correction is documented in `review/RESOURCE_COST.md`: it initially compared an unexpanded configuration mapping against the analytical resource-bound identity. Its failed source/receipt and corrected identity regression are preserved there. It did not reflect any change to the frozen configuration.

These are corrections to review tooling. The final independent QA result and its receipt state which final checks actually completed; a failed attempt is not counted as a passed run.
