# Local external evaluation

The evaluator accepts explicitly supplied local datasets. No external labeled dataset was supplied with this project: **real-world external validation remains `not_evaluated`**. The tests below exercise adapters and numerical calculations with constructed labels; they are not authorship-accuracy evidence.

The public functions are `evaluate_external(dataset_path, suite, config=None)` and `freeze_pair_threshold(dataset_path, config=None, *, value, selection_rule, provenance)` in `src/account_history_analyzer/evaluation_external.py`. The first returns deterministic evaluation JSON with separate development/evaluation partitions. The second binds an explicitly selected cutoff to development data without opening held-out snapshot files or calculating held-out scores. Neither function fits preprocessing, references, vocabulary, thresholds, or stream parameters from evaluation labels.

After supplying a dataset, invoke either format through the CLI:

```bash
ahas evaluate --suite paired_text --dataset local_pairs.json --config config/default.toml --out pair_evaluation/
ahas evaluate --suite account_stream --dataset local_streams.json --config config/default.toml --out stream_evaluation/
```

## Shared contract

Strict schemas are shipped as `schemas/evaluation_paired_text.schema.json` and `schemas/evaluation_account_stream.schema.json`, and installed under the package's `contracts/` directory. Unknown fields, duplicate object keys, invalid numbers, unknown text IDs, duplicate evaluator IDs, inconsistent config hashes, and absent files are errors. JSON Schema does not insert defaults. Missing `groups` becomes an empty mapping; a missing text `selector` means all supplied records, with the ordinary comparison selector defaults expanded explicitly.

Every dataset declares:

- `schema_version: "1.0.0"`, `format`, `dataset_id`, `provenance`, and an operational `label_definition`.
- A `protocol` with `analysis_config_sha256`, `registered_before_evaluation: true`, and nonempty `preregistration_provenance`.
- Local `input` JSONL and `manifest` paths for each source. Relative paths resolve against the dataset document, never an implicit current working directory. The ordinary snapshot loader enforces the source contracts and retains supplier timestamps; the evaluator invents no timestamps or thread memberships.

Compute the configuration hash with `digest(config.analytical())`. A separately named short-text experiment may supply another explicit configuration. Its guards and hash remain visible; default 1,000-word/eight-record comparison guards are never relaxed silently.

```python
from account_history_analyzer import AnalysisConfig
from account_history_analyzer.io import digest
config = AnalysisConfig.from_toml("config/default.toml")
print(digest(config.analytical()))
```

Dataset identity replaces operational source paths with canonical snapshot hashes and normalized selectors. Moving identical files preserves this identity. Label, grouping, source-content, protocol, and configuration changes remain observable. Outputs expose dataset/config/method hashes, implementation fingerprint, numerical environment, resource hashes, coverage, abstention, and declared label meaning.

## Paired text

A `paired_text` dataset contains `texts` and `pairs`. Each text has a unique `text_id`, local snapshot paths, an optional ordinary comparison `selector`, and optional `groups`. Each pair has `pair_id`, two different referenced text IDs, `split` (`development` or `evaluation`), and `label` (`same_author` or `different_author`). The labels describe the supplied dataset's task, not a probability inferred by the analyzer.

The protocol selects exactly one distance through `{method_id, view, n}`. Supported combinations are `cosine_distance_v1` with a configured retained-prose/function-mask view and n=3,4,5; `function_word_js_v1` with `lexical_tokens` and n=null; or `classic_delta_v1` with `lexical_tokens` and n=null. Missing Delta reference causes abstention. The ordinary style comparison must qualify before its distance enters metrics. Calculable raw distances below sample guards are exported as `raw_distance` while `score` remains null.

Example shape (the referenced files must actually exist):

```json
{
  "schema_version": "1.0.0",
  "format": "paired_text",
  "dataset_id": "supplied_pairs_v1",
  "provenance": "Describe source, release, consent/license and split construction here.",
  "label_definition": "Describe the evidence supporting same_author/different_author labels here.",
  "protocol": {
    "analysis_config_sha256": "REPLACE_WITH_64_HEX_CONFIGURATION_HASH",
    "registered_before_evaluation": true,
    "preregistration_provenance": "Identify the frozen protocol and when/how it was established.",
    "distance": {"method_id": "function_word_js_v1", "view": "lexical_tokens", "n": null},
    "frozen_threshold": null
  },
  "texts": [
    {"text_id": "a", "input": "a.jsonl", "manifest": "a.snapshot.json",
     "selector": {"kind": "comment"}, "groups": {"author": ["author_a"]}},
    {"text_id": "b", "input": "b.jsonl", "manifest": "b.snapshot.json",
     "selector": {"kind": "comment"}, "groups": {"author": ["author_b"]}}
  ],
  "pairs": [
    {"pair_id": "pair_a_b", "left_text_id": "a", "right_text_id": "b",
     "split": "evaluation", "label": "different_author"}
  ]
}
```

With no frozen threshold, rankings run and decisions are `not_run_missing_threshold`. ROC-AUC requires both scored classes. Average precision names `different_author` as positive and uses noninterpolated recall increments after complete tied-score groups. Larger distance ranks as more different; a decision predicts the positive label exactly when `score >= threshold`. All ratio results retain numerator, denominator, and null/missingness reasons. No confidence interval assumes correlated pairs are independent.

To freeze a threshold, provide development pairs of both labels that qualify under the declared configuration. Select the value using development data only, document the selection rule, and call:

```python
import json
from pathlib import Path
from account_history_analyzer import AnalysisConfig
from account_history_analyzer.evaluation_external import freeze_pair_threshold
from account_history_analyzer.io import canonical_bytes

path = Path("local_pairs.json")
config = AnalysisConfig.from_toml("config/default.toml")
frozen = freeze_pair_threshold(path, config, value=0.25,
    selection_rule="Describe the actual development-only selection rule",
    provenance="Identify the development study and frozen cutoff artifact")
data = json.loads(path.read_text("utf-8"))
data["protocol"]["frozen_threshold"] = frozen
path.write_bytes(canonical_bytes(data))
```

The number 0.25 above is an API illustration, **not a recommended or calibrated cutoff**. Freezing binds all development pair IDs, development labels/source identities, analysis configuration, selected distance, implementation fingerprint, dependency environment, registry, and bundled resources. Evaluation checks those bindings and refuses mismatches. Code or dependency changes require an explicit new freeze. A supplied provenance claim cannot establish by itself that a human avoided held-out labels; that limitation is reported.

## Complete account streams

An `account_stream` dataset has `streams`, each with unique evaluator `stream_id`, local input/manifest, split, optional groups, `annotation_provenance`, a preregistered `scope`, and `truth_boundaries`. Scope is `{scope_type: "pooled"|"community", kind: "comment"|"submission", subreddit: null|string}`; pooled scope requires null subreddit. `protocol.boundary_tolerance_records` is a nonnegative integer fixed before evaluation.

The evaluator executes the entire `analyze(snapshot, config)` procedure, including preprocessing, complete-history window construction, primary change search, and sensitivity calculations. It then scores the preregistered primary scope. It does not replace the history with pairs around known boundaries. An unavailable community scope, insufficient qualified windows, or incomplete pipeline produces explicit abstention. A qualified constant-feature stream (`no_measurable_variation`) is an executed empty candidate result and belongs in the unchanged-stream denominator.

Truth split **k** means the first right-hand record has zero-based index k in the complete canonical snapshot, so 1 ≤ k < the number of supplied unique records. Production intervals `[last_left_record_position, first_right_record_position]` become split intervals `[last_left_record_position + 1, first_right_record_position]`. This preserves uncertainty from excluded intervening records and uses neither guessed exact timestamps nor incomparable window indices.

A candidate matches a truth split if its distance to the interval is within the preregistered tolerance. Matching is one-to-one: maximize matches, minimize total interval-location error, then use deterministic index ties. Location error is zero inside the candidate interval and otherwise distance to the nearest endpoint; it is explicitly **interval-location error**, not a precise estimated transition time. The shared implementation is `evaluation_metrics.boundary_metrics`.

Per-stream results retain scope, declared coverage, missing timestamps, full-analysis result hash, candidate intervals, truth splits, statuses, and metrics. Aggregation reports boundary precision/recall and interval-location errors over executed streams. False candidates per unchanged stream uses only executed unchanged streams as its denominator, alongside separate known-unchanged and abstained-unchanged counts. Missing/underpowered unchanged streams therefore cannot produce a reassuring zero.

## Group audits, limits and interpretation

For either format, optional grouping dimensions are `author`, `thread`, `source_document`, `near_duplicate_cluster`, and `related_sample`; each supplied dimension is a nonempty array of string IDs. Paired-text groups belong to each text unit, so missing metadata on either side stays visible. Stream groups describe the complete supplied stream; multiple known authors can be declared.

Any observed shared group across development and evaluation is rejected, even when other samples lack that dimension. Reusing a text ID or canonical supplied snapshot across splits is also rejected. Absent dimensions or absent splits are `not_auditable`, with missing-unit lists. The evaluator does not infer author groups from account IDs, invent clusters, or claim complete separation when metadata is missing. Supplied grouping correctness and label validity cannot be independently established by this adapter.

Resource limits apply to the whole evaluation invocation: dataset JSON plus unique source-file bytes share `input.max_input_bytes`, and distinct canonical snapshots share `input.max_unique_records`. Schemas additionally cap 1,000 text/stream units and 10,000 pairs. Limits fail explicitly; no automatic subsampling occurs. A resource-limited full pipeline marks evaluation incomplete and returns exit code 4.

No PAN adapter or PAN-comparable score is claimed. PAN sentence/document labels cannot supply real account chronology, and external corpus access is never requested automatically. All outputs remain descriptive measurements of supplier-defined tasks; they do not validate bot, AI-writing, or account-takeover detection.

## Checks actually run

The initial offline adapter integration run was:

```bash
python3.12 scripts/offline_exec.py .venv/bin/python -m pytest -q tests/test_evaluation_external.py
```

Actual initial result: **17 passed in 2.91 seconds**. After review fixes, the combined adapter/numerical gate was run:

```bash
python3.12 scripts/offline_exec.py .venv/bin/python -m pytest -q tests/test_evaluation_external.py tests/test_evaluation_metrics.py
```

Actual result: **44 passed in 4.92 seconds**. The added stream-cache lifetime regression verifies that the previous full analysis is released before another snapshot is analyzed. Further release test results are recorded in the central `EVALUATION.md`/test log. `tests/test_evaluation_external.py` exercises the public adapter on constructed local snapshots, exact JS ranking values, default-guard abstentions, each leakage dimension, missing metadata, threshold isolation and tamper detection, path identity, complete stream search and split mapping, strict schemas, and explicit resource limits. These tests establish engineering behavior only. No independently labeled real-world dataset has been evaluated.
