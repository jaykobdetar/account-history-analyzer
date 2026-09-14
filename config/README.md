# Configuration

`default.toml` contains the complete implemented defaults. Omitted settings are inserted by `AnalysisConfig`, not JSON Schema. Unknown keys, wrong types and unsupported methods fail. `schemas/config.schema.json` is the external contract; installed package defaults/contracts are tested against these copies.

Engineering thresholds are uncalibrated descriptive settings. They do not distinguish people from bots or establish author changes. Required output formats, offline operation, UTC, separate kinds, normalization/parser/tokenizer identities and the segmentation minimum of eight windows cannot be disabled silently.

Resources resolve inside the installed package. A nonempty Delta reference path must point to a local JSON file, relative to the TOML file if not absolute. It is read once, validated, hashed and frozen; canonical config identity replaces file location with resource ID/hash. Verification reuses the hashed `delta_reference.json` export. The toy example requires `--allow-toy-reference` for CLI analysis/evaluation.

`report.excerpts` controls default report presentation; `ahas render --excerpts none` changes presentation without changing the original results. V1 always exports all required formats. `style.max_all_pairs_windows` is the retained cap for optional heatmaps; this release computes adjacent, manual and predefined sensitivity comparisons and does not create optional heatmaps.
