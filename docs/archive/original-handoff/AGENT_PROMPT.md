# Prompt to give the implementation agent

You are implementing an offline, deterministic account-history analysis suite. The attached directory contains its specification, schemas, default configuration, original synthetic fixtures, numerical oracles, and research references.

Read `BUILD_SPEC.md` completely, then `ACCEPTANCE_TESTS.md`, `config/default.toml`, and the schemas. Treat this as a new standalone project; do not assume access to previous conversation history.

## Objective

Build the actual working Python 3.12 library and `ahas` CLI described in the specification. It consumes already-extracted local JSONL histories plus a manifest. It produces numerical measurements, evidence-linked stylistic comparisons, content-reuse findings, activity summaries, descriptive change-point candidates, and deterministic reports.

No Reddit fetching, website, browser extension, API credentials, generative AI, embeddings, neural network, AI-writing detector, or bot/human probability belongs in V1. Do not ask me to choose or connect any of those. Do not turn this into another planning-only deliverable: implement, execute, test, and fix the software.

## Working procedure

1. Inspect the supplied files and create a concise milestone checklist in the repository. Record genuine ambiguities in `docs/DECISIONS.md`; resolve ordinary engineering details using the simplest scope-preserving choice. Preserve the scientific limitations and reproducibility contract.
2. Implement milestone M0, then the M1 end-to-end slice before expanding the analysis. Proceed through M2–M6 only after their prior correctness gates pass. Keep the package, CLI, and report renderer separated.
3. Use the supplied schemas as external contracts. Tighten the explicitly generic per-module result payload schemas as each module is implemented; add schema tests. Expand defaults deliberately; don't rely on JSON Schema to insert them.
4. Use established numerical primitives where appropriate, with explicit parameters and pinned dependencies. Implement our named adaptations exactly and identify them as adaptations. Do not copy a paper's claimed accuracy onto this pipeline.
5. Write independent numerical tests and property/integration tests alongside the code. Use the hand-checkable oracles before testing larger constructed histories. Add regression tests for every bug found.
6. Treat the synthetic truth sidecars as evaluator-only construction facts. Never feed them, fixture filenames, scenario names, account IDs, or boundary labels into feature calculations. Do not tune to a single fixture or fabricate authorship ground truth.
7. Run analyses with networking disabled. Re-run in separate processes and verify byte-identical canonical output in the reference environment. Record actual test commands, actual outcomes, and any skipped checks.
8. Produce a sample JSON/Markdown/HTML report from the shipped fixtures. Inspect its correctness, references, safety, and readability. Every source example must come from the supplied records; prose must be template-generated.
9. Freeze dependency/resource versions and provide a reproducible setup and reference-container recipe. Do not claim cross-platform byte identity unless tested and supported; keep receipts separate from canonical results.

## Non-negotiable interpretation rules

A measured pattern is not proof of its cause. A style distance is not an authorship probability. Parameter stability is not confidence. A content match is not proof of deceptive intent. A timestamp gap is not sleep. A reply's delay is not typing time. Unknown/insufficient data must not become a reassuring zero score.

Missing external research data may leave real-world validation unestablished; it must not lead you to invent accuracy claims or abandon the functioning analysis suite. Report engineering completion separately from scientific validation.

## Final deliverable

Return the working source repository/archive, exact install and run commands, an actual test summary, generated fixture reports, measured performance/reproducibility results, and specific remaining limitations. Cite code paths for important design choices. Clearly identify any requirement you could not complete and the concrete reason; never label unrun tests as passed.

Begin by reading the specification and implementing the contracts and first executable end-to-end slice.
