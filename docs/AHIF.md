# AHIF evidence contract and offline Reddit bridge

**AHIF draft 0.1.1 is the reviewed evidence destination contract.** The frozen
AHAS 1.0.4 engine still accepts its existing record/snapshot schemas **1.0.0**.
AHIF JSONL is not direct AHAS input; selection and projection are explicit steps.

The [companion AHIF repository](https://github.com/jaykobdetar/ahif) contains the
normalizer, projection CLI, profiles, tests and sanitized execution report. This
repository includes an unchanged copy of the reviewed format and its history.
The engine, numerical defaults, input schemas, dependencies, previous studies and
frozen releases are unchanged by this adoption.

## Supported boundaries

| Stage | Contract |
| --- | --- |
| Source | `reddit-export-csv` 1.0.0: the observed `comments.csv` and `posts.csv` layout from a supplied local account export; no live collection. |
| Evidence | AHIF 0.1.1 canonical bundle, full structural/semantic validation, exact text fields, hashes, locators and explicit unknowns. |
| Selection | One source-local export subject; at most one equivalent observation per full event key. Unresolved conflicts and ineligible observations receive explicit decisions. |
| Analysis projection | `ahas-conservative` 1.0.0: metadata-only unavailable records into existing AHAS 1.0.0 input schemas. Retained prose is not supported by this profile. |
| Supplied-field projection | Separately reviewed `reddit-export-observation` 1.0.0 carries eligible literal body/title fields with explicit CommonMark interpretation and a context-bearing presentation. See the [new integration note](EXPORT_OBSERVATION.md). |
| Engine | Unchanged AHAS 1.0.4 with existing defaults and normal replay verification. |

The source omits native author identity, edit evidence, explicit text completeness
and lifecycle/as-of declarations for retained text. These remain unknown. A
handle or source-local identity is not permanent cross-capture identity. Repeated
observations do not inflate event counts; equal text does not merge separate
native events. Source-reported totals never create completeness percentages.

## Reviewed format in this repository

- [Specification](ahif/0.1.1/SPEC.md), [field definitions](ahif/0.1.1/FIELDS.md)
  and [schemas](ahif/0.1.1/schemas/ahif.schema.json)
- [Adoption report](ahif/0.1.1/ADOPTION.md), [review/change log](ahif/0.1.1/CHANGES.md)
  and [case matrix](ahif/0.1.1/REVIEW_MATRIX.md)
- [AHAS projection map and loss/refusal rules](ahif/0.1.1/AHAS_COMPATIBILITY.md)
- [Original 0.1.0 package and receipts](ahif/history/0.1.0/README.md)

All 92 files under `docs/ahif/` are preserved verbatim. Their adoption-stage
statements about local-only work and a future converter describe that earlier
stage. This page and the companion implementation documentation describe the
current boundary. Historical prompts are records, not new execution instructions.
The old full runner may depend on its original workspace and write into historical
receipt directories; use the read-only checks below for this checkout.

## Use the companion implementation

The tested export-observation revision and immutable links are recorded in
[observation-profile provenance](../provenance/ahif-export-observation/README.md).
The original conservative revision remains in
[adoption provenance](../provenance/ahif-adoption/README.md). Follow the companion setup and
CLI guide from an AHIF checkout using an installed, unchanged AHAS 1.0.4 Python
environment. Keep source exports, bundles, full receipts, account maps and full
reports in a separate private directory. Only fictional fixtures and sanitized
aggregate evidence are in the public repositories.

After the bridge emits `records.jsonl` and `snapshot.json`, use the existing CLI:

```bash
python3.12 scripts/offline_exec.py .venv/bin/ahas validate \
  --input "$PRIVATE/projection/records.jsonl" \
  --manifest "$PRIVATE/projection/snapshot.json"
python3.12 scripts/offline_exec.py .venv/bin/ahas analyze \
  --input "$PRIVATE/projection/records.jsonl" \
  --manifest "$PRIVATE/projection/snapshot.json" --out "$PRIVATE/analysis"
python3.12 scripts/offline_exec.py .venv/bin/ahas verify \
  --input "$PRIVATE/projection/records.jsonl" \
  --manifest "$PRIVATE/projection/snapshot.json" \
  --analysis-dir "$PRIVATE/analysis" --recompute
```

Here `PRIVATE` is an existing private directory outside either repository and
`analysis` is a new destination. No defaults or sample guards are relaxed.

## Historical conservative validation

The companion implementation passed 39 bridge tests. Its one bounded private
integration normalized 247 observations and verified 300 body/title fields.
Eight metadata-only removed comments were projected; 239 observations were
quarantined by the frozen lifecycle/content rule. The matching prior-input subset
agreed after documented ID and unknown-language substitutions. AHAS analysis and
full recomputation passed, reproducing 14 canonical artifacts; text, reuse and
style remained `insufficient_data`. This was an ingestion regression check, not a
new pilot or evidence of scientific authorship accuracy.

For the copied format, run these read-only checks from this repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover \
  -s docs/ahif/0.1.1/reference -v
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  docs/ahif/0.1.1/reference/validate_bundle.py \
  docs/ahif/0.1.1/examples/review-cases --canonical
```

The reference checker is fixture-oriented; passing it does not prove source
authenticity, permissions, account continuity, completeness or production-safe
hostile ingestion. The separate [export-observation profile](EXPORT_OBSERVATION.md)
now implements supplied-field prose analysis while preserving unknown as-of,
completeness and visibility. No X/forum converter, scraper,
collector, database or model is introduced.
