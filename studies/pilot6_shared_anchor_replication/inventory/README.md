# Source availability and cohort construction

These files describe preparation before chronological scoring. Here, a **candidate pool** means source comments considered for constructing inputs; it does not mean an analyzer change candidate.

Start with [final selection](prepared-01/selection-summary.json) and [all 20 pair decisions](prepared-01/pair-availability.json). Nine pairs passed; eleven were unavailable under the fixed post-audit rules. The target shortfall is one pair. No replacements were recruited. The selected sample summaries give five source samples per pair; their shared earlier sample is reused in four histories.

The preparation sequence is:

1. [Supplement intake](intake-supplement-01/intake-summary.json): repair the earlier technical-community intake prefilter using the frozen preprocessor and existing archives.
2. [Metadata feasibility](metadata-02/feasibility-summary.json): enumerate all 505 registered community/date combinations, then select the first 20 edges of the exact 32-pair disjoint matching. Neither style scores nor legal-grid error enters selection.
3. [Source buffers](buffer-preparation-01.json): recover 8,867 original comments, retaining original source-line hashes and fields privately.
4. [Content audit](content-audit-01.json): remove 857 records under the unchanged content/thread protections; 8,010 remain. Seventeen historical records have unobservable content, so passing this audit does not establish complete independence from all possible reuse.
5. [Final cohort](prepared-01/): apply the same fixed directions, dates, prefix rules, volume/date gates and exact-cost ordering to audited survivors. Keep all unavailable decisions visible.

[Prior preparation exposure](prior-preparation-exposure.json) distinguishes earlier metadata-only availability from unscored buffer/audit exposure. Its main counts concern all 20 provisional pairs. [Study context](study-context.json) projects those counts onto the nine selected pairs: two of the 18 accounts had prior preparation/audit exposure, sixteen appeared only in earlier eligibility metadata, and none entered from the new supplement. All 119 protected or previously scored accounts were excluded.

The first metadata attempt stopped before evaluating any dates because older ineligible rows can have null retained-word counts. Its [failure record](metadata-01/incomplete-metadata.json), executed code snapshot and logs remain preserved. The [second registration](../protocol/METADATA_REGISTRATION_V2.json) fixes that compatibility case before enumeration, with the same source files, limits and scientific rules.

Original prose, source account identities, record maps, metadata enumerations and prepared real-text inputs are private. Public files use opaque pair IDs. Numerical hashes bind the protected originals; they do not make a public Git checkout sufficient for exact real-text reproduction.
