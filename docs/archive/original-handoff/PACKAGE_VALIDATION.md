# Handoff package validation

The checks below were actually run on the **specification and fixture package**. They do not test an AHAS analyzer implementation; that application remains to be built.

- 5 JSON Schemas pass Draft 2020-12 schema checks.
- 973 fixture rows and 6 snapshot manifests validate against their schemas.
- Toy-reference and manual-comparison example files validate.
- Default TOML parses and includes the declared offline V1 settings.
- Fixture generator reproduced all 20 data/index files byte-for-byte in two independent runs.
- All 19 fixture-index sizes and SHA-256 hashes agree.
- Arithmetic token, ingestion-duplicate, interval, variance, and inclusive-window expectations checked independently.
- Cosine/JS examples cross-checked with SciPy; shingle/Delta arithmetic and unique change-point optimum independently verified.
- All 320 vocabulary-only control texts preserve their intended function-mask shape while changing source vocabulary.
- Required handoff documents/resources are present.

## Not tested or claimed

No account-history analysis engine, PELT integration, full text-extraction implementation, report renderer, performance target, detector, or real-world authorship/automation accuracy was tested. The numerical checks verify the plan's example values only. The fixture generator is reproducible; that does not establish the future application's reproducibility.

The implementation agent must perform the tests in `ACCEPTANCE_TESTS.md` against the actual software and report the real outcomes.
