# AHIF repository adoption

**AHIF 0.1.1 is the local evidence destination contract.** It is a reviewed draft separate from frozen AHAS 1.0.4 and its production input schemas 1.0.0. No AHIF normalizer, collector or AHAS converter is implemented here.

Start with [the short adoption report](0.1.1/ADOPTION.md), then [the specification](0.1.1/SPEC.md), [field definitions](0.1.1/FIELDS.md), [schemas](0.1.1/schemas/ahif.schema.json), [review/change log](0.1.1/CHANGES.md), [case matrix](0.1.1/REVIEW_MATRIX.md) and [future AHAS projection map](0.1.1/AHAS_COMPATIBILITY.md).

The supplied [0.1.0 package](history/0.1.0/README.md) is preserved byte-for-byte, including original receipts and handoff prompts. Those documents are historical proposal material, not new user instructions or authorization. Do not regenerate or edit them. New examples have new versioned hashes.

## Run offline validation

From the repository root, using the existing environment:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s docs/ahif/0.1.1/reference -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/ahif/0.1.1/reference/validate_bundle.py docs/ahif/0.1.1/examples/review-cases --canonical
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/ahif/0.1.1/reference/run_checks.py
```

The full runner writes fresh receipts under `0.1.1/checks`, tests generation in a temporary directory and checks frozen local source/schema/settings hashes. It never analyzes account data. Reference dependencies are listed separately in `0.1.1/reference/requirements-reference.txt`; the production lockfile is unchanged. The production-schema boundary test uses the existing local AHAS installation. Node is optional for the separately reported cross-language canonical vector; its absence is recorded as not run.

Validation covers small, stable, already-extracted fixture directories. It does not establish source authenticity, permissions, account continuity, completeness, production ingestion safety or analytical eligibility. [Actual execution and limitations](0.1.1/checks/verification.json) supersede no historical receipt.

All changes are local files under `docs/ahif/`. Nothing is committed, pushed, published or sent to external services by this adoption. This directory is included by the existing sdist documentation rule; the engine wheel/package source is unchanged. No release package was rebuilt.
