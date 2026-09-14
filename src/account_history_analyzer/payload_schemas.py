"""Strict schemas for implemented result payloads.

This module is a build-time source for the bundled external JSON contract. It
never infers a schema from observed data, inserts defaults, or accepts new fields
merely because a particular fixture produced them. Unimplemented module slots
are closed empty objects until their versioned contract is implemented.
"""
from __future__ import annotations

from copy import deepcopy
import json
from importlib.resources import files
from typing import Any

Schema = dict[str, Any]


def obj(**properties: Schema) -> Schema:
    """A closed object with every named field required."""
    return {
        "type": "object", "additionalProperties": False,
        "required": list(properties), "properties": properties,
    }


def array(items: Schema, *, unique: bool = False) -> Schema:
    schema: Schema = {"type": "array", "items": items}
    if unique:
        schema["uniqueItems"] = True
    return schema


def nullable(schema: Schema) -> Schema:
    return {"anyOf": [schema, {"type": "null"}]}


INTEGER: Schema = {"type": "integer", "minimum": 0}
NUMBER: Schema = {"type": "number"}
STRING: Schema = {"type": "string"}
STRINGS: Schema = array(STRING)
IDS: Schema = array(STRING, unique=True)
TIMESTAMP: Schema = {
    "type": "string", "format": "date-time",
    "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$",
}

PUNCTUATION_KEYS = (
    "comma", "period", "question_mark", "exclamation_mark", "semicolon", "colon",
    "ascii_apostrophe", "curly_apostrophe", "ascii_double_quote",
    "left_curly_double_quote", "right_curly_double_quote", "ascii_hyphen", "en_dash",
    "em_dash", "ellipsis", "ascii_period_runs",
)


def pooled_text_schema() -> Schema:
    """Pooled numerator/denominator features, preserving explicit missingness."""
    resources = files("account_history_analyzer").joinpath("resources")
    vocabulary = resources.joinpath("function_words_en_v1.txt").read_text(encoding="utf-8").splitlines()
    pairs = json.loads(resources.joinpath("contraction_pairs.json").read_text(encoding="utf-8"))["pairs"]
    punctuation = obj(**{key: INTEGER for key in PUNCTUATION_KEYS})
    punctuation_rates = obj(**{key: nullable(NUMBER) for key in PUNCTUATION_KEYS})
    counts = obj(**{key: INTEGER for key in (
        "retained_words", "number_tokens", "retained_codepoints", "cased_letters",
        "uppercase_letters", "lowercase_letters", "segments", "paragraphs",
        "word_character_total", "standalone_i_lower", "standalone_i_upper",
        "removed_quote_spans", "removed_code_spans", "removed_url_spans", "headings",
        "list_items", "links", "mentions",
    )}, punctuation=punctuation)
    contraction = obj(
        contracted=nullable(INTEGER), expanded=nullable(INTEGER),
        opportunities=nullable(INTEGER), raw_fraction=nullable(NUMBER),
        fraction=nullable(NUMBER), status={"enum": ["ok", "insufficient_opportunities", "not_run"]},
    )
    return obj(
        record_count=INTEGER, usable_record_count=INTEGER,
        counts=counts,
        rates=obj(
            uppercase_fraction=nullable(NUMBER), average_word_length=nullable(NUMBER),
            punctuation_per_1000_words=punctuation_rates,
            punctuation_per_1000_codepoints=punctuation_rates,
        ),
        function_counts=obj(**{word: nullable(INTEGER) for word in vocabulary}),
        function_rates=obj(**{word: nullable(NUMBER) for word in vocabulary}),
        contractions=obj(**{pair["id"]: contraction for pair in pairs}),
        words_per_record=obj(
            count=INTEGER, min=nullable(NUMBER), max=nullable(NUMBER),
            median=nullable(NUMBER), q25=nullable(NUMBER), q75=nullable(NUMBER),
        ),
        rate_reason_codes=STRINGS, english_record_count=INTEGER, english_word_count=INTEGER,
    )


def coverage_schema(snapshot_schema: Schema) -> Schema:
    declared = deepcopy(snapshot_schema["properties"]["coverage"])
    # Results contain the explicitly expanded supplier declaration.
    declared["required"] = list(declared["properties"])
    declared["properties"]["known_gaps"]["items"]["required"] = [
        "start_utc", "end_utc", "note",
    ]
    return obj(
        unique_records=INTEGER,
        status_counts=obj(present=INTEGER, deleted=INTEGER, removed=INTEGER, unavailable=INTEGER),
        missing_timestamps=INTEGER,
        usable_body_records=INTEGER,
        eligible_style_records=INTEGER,
        declared_coverage=declared,
        warnings=array(obj(code=STRING, source_record_ids=IDS)),
        languages=array(obj(language=STRING, records=INTEGER)),
        kinds=obj(comment=INTEGER, submission=INTEGER),
    )


def activity_schema(snapshot_schema: Schema) -> Schema:
    summary = obj(
        count=INTEGER, unit={"const": "seconds"}, mean=nullable(NUMBER),
        population_variance_seconds_squared=nullable(NUMBER),
        population_standard_deviation=nullable(NUMBER), minimum=nullable(NUMBER),
        q25=nullable(NUMBER), median=nullable(NUMBER), q75=nullable(NUMBER),
        maximum=nullable(NUMBER), quantile_method={"const": "numpy_linear_n_minus_1"},
        coefficient_of_variation=nullable(NUMBER),
        coefficient_of_variation_reason={"enum": [None, "fewer_than_two_intervals", "zero_mean_interval"]},
        summary_reason={"enum": [None, "no_intervals"]},
    )
    return obj(
        timezone={"const": "UTC"}, scope={"const": "distinct_supplied_events_with_creation_timestamps"},
        event_count=INTEGER, missing_timestamp_records=INTEGER,
        earliest_utc=nullable(TIMESTAMP), latest_utc=nullable(TIMESTAMP),
        observed_span_seconds=nullable(NUMBER),
        events_per_day=array(obj(
            date={"type": "string", "format": "date"}, event_count=INTEGER,
            edge_day={"type": "boolean"}, known_gap={"type": "boolean"},
        )),
        hour_histogram={"type": "array", "items": INTEGER, "minItems": 24, "maxItems": 24},
        weekdays=array(obj(
            weekday={"enum": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]},
            days_in_supplied_range=INTEGER, supplied_events=INTEGER,
        )),
        day_count=INTEGER, event_bearing_days=INTEGER, zero_event_days=INTEGER,
        known_coverage_gaps=coverage_schema(snapshot_schema)["properties"]["declared_coverage"]["properties"]["known_gaps"],
        gaps=array(obj(left_record_id=STRING, right_record_id=STRING, microseconds=INTEGER, seconds=NUMBER)),
        gap_summary=summary,
        simultaneous_timestamp_groups=array(obj(created_utc=TIMESTAMP, record_ids=IDS)),
        maximum_sliding_windows=array(obj(
            duration_seconds=INTEGER, inclusive_endpoints={"const": True}, maximum_events=INTEGER,
            record_ids=IDS, first_utc=nullable(TIMESTAMP), last_utc=nullable(TIMESTAMP),
        )),
        burst_method={"const": "greedy_nonoverlapping_fixed_window_bursts"},
        burst_duration_seconds=INTEGER, burst_minimum_events=INTEGER,
        greedy_bursts=array(obj(
            record_ids=IDS, first_utc=TIMESTAMP, last_utc=TIMESTAMP, observed_duration_seconds=NUMBER,
        )),
        limitations=STRINGS,
    )


def records_features_schema() -> Schema:
    """Contract for one complete record_features.jsonl row, including titles."""
    pooled = pooled_text_schema()["properties"]
    counts = deepcopy(pooled["counts"])
    for key, value in counts["properties"].items():
        if key == "punctuation":
            counts["properties"][key] = obj(**{name: nullable(INTEGER) for name in PUNCTUATION_KEYS})
        else:
            counts["properties"][key] = nullable(value)
    line_range = nullable({"type": "array", "items": {"type": "integer", "minimum": 1}, "minItems": 2, "maxItems": 2})
    source_field = {"enum": ["text", "title"]}
    core = dict(
        usable={"type": "boolean"}, transformations=array({"enum": [
            "line_endings_lf_v1", "unicode_nfc_v1", "commonmark_parse_v1", "plain_paragraphs_v1",
            "retained_span_exclusion_v1", "horizontal_whitespace_v1", "lexical_regex_v1", "function_mask_v1",
        ]}, unique=True), source_sha256=nullable({"type": "string", "pattern": "^[0-9a-f]{64}$"}),
        segments=array(obj(
            text=STRING, source_record_id=STRING, source_field=source_field,
            source_line_range=line_range, normalized_start=INTEGER, normalized_end=INTEGER,
        )),
        masked_segments=STRINGS, tokens=array(STRINGS), word_tokens=array(STRINGS),
        token_offsets=array(array(obj(
            text=STRING, normalized=STRING, start=INTEGER, end=INTEGER, kind={"enum": ["word", "number"]},
        ))),
        structure=obj(**{key: INTEGER for key in (
            "removed_quote_spans", "removed_code_spans", "removed_url_spans", "headings",
            "list_items", "links", "mentions", "paragraphs",
        )}),
        links=array(obj(
            url=nullable(STRING), hostname=nullable(STRING), status={"enum": ["ok", "malformed", "unsafe_scheme"]},
            source_field=source_field, source_line_range=line_range,
        )),
        warnings=STRINGS, id=STRING, kind={"enum": ["comment", "submission"]},
        subreddit=nullable(STRING), created_utc=nullable(TIMESTAMP),
        edit_state={"enum": ["unknown", "not_edited", "edited"]}, language=STRING,
        counts=counts, rates=pooled["rates"], rate_reason_codes=STRINGS,
        function_counts=pooled["function_counts"], function_rates=pooled["function_rates"], contractions=pooled["contractions"],
    )
    result = obj(**core, title=nullable(obj(**core, source_field={"const": "title"})))
    result.update({"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "AHAS V1 per-record retained-text measurements"})
    return result


def evidence_schema() -> Schema:
    """One evidence.jsonl row with explicitly named source-offset semantics."""
    result = obj(
        evidence_id=STRING, source_record_id=STRING, source_field={"enum": ["text", "title"]},
        representation={"enum": ["raw_source", "retained_prose"]},
        segment_index=nullable(INTEGER), offset_basis={"enum": ["raw_source", "normalized_segment"]},
        start=INTEGER, end=INTEGER, text=STRING, role=STRING, feature_id=nullable(STRING),
        side={"enum": [None, "left", "right"]},
        source_line_range=nullable({"type": "array", "items": {"type": "integer", "minimum": 1}, "minItems": 2, "maxItems": 2}),
    )
    result.update({
        "$schema": "https://json-schema.org/draft/2020-12/schema", "title": "AHAS V1 source-linked evidence",
        "allOf": [{
            "if": {"properties": {"representation": {"const": "raw_source"}}},
            "then": {"properties": {"offset_basis": {"const": "raw_source"}, "segment_index": {"type": "null"}}},
            "else": {"properties": {"offset_basis": {"const": "normalized_segment"}, "segment_index": INTEGER}},
        }],
    })
    return result


def windows_schema() -> Schema:
    """One whole-record chronological window exported to windows.jsonl."""
    schema = obj(
        window_id=STRING, stream_id=STRING, record_ids=IDS,
        word_count=INTEGER, record_count=INTEGER, qualified={"type": "boolean"},
        remainder={"type": "boolean"}, reason_codes=STRINGS,
        largest_record_share={"type": "number", "minimum": 0, "maximum": 1},
        first_utc=TIMESTAMP, last_utc=TIMESTAMP, first_record_id=STRING, last_record_id=STRING,
        first_record_position=INTEGER, last_record_position=INTEGER,
        features=pooled_text_schema(),
    )
    schema.update({"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "AHAS V1 chronological writing window"})
    return schema


def style_stream_schema() -> Schema:
    """Metadata and references only; full feature windows have one artifact home."""
    return obj(
        stream_id=STRING, scope_type={"enum": ["pooled", "community"]},
        kind={"enum": ["comment", "submission"]}, subreddit=nullable(STRING),
        eligible_record_ids=IDS, eligible_words=INTEGER, target_words=INTEGER,
        minimum_records=INTEGER, record_count=INTEGER, qualified_window_count=INTEGER,
        remainder_word_count=INTEGER, window_ids=IDS,
    )


def style_comparison_schema() -> Schema:
    samples = obj(
        record_count=INTEGER, word_count=INTEGER, eligible_record_count=INTEGER,
        eligible_word_count=INTEGER, usable_record_count=INTEGER, missing_timestamps=INTEGER,
        kinds=array({"enum": ["comment", "submission"]}, unique=True), languages=IDS,
        community_distribution=array(obj(subreddit=nullable(STRING), record_count=INTEGER, word_count=INTEGER)),
        edit_state_counts=obj(edited=INTEGER, not_edited=INTEGER, unknown=INTEGER),
        length=pooled_text_schema()["properties"]["words_per_record"],
        largest_record_share=nullable({"type": "number", "minimum": 0, "maximum": 1}),
    )
    contribution = obj(
        feature_id=STRING, left_rate=NUMBER, right_rate=NUMBER, absolute_rate_change=NUMBER,
        contribution=nullable(NUMBER), contribution_kind=STRING,
        left_count=nullable(INTEGER), right_count=nullable(INTEGER),
    )
    distance = obj(
        method_id={"enum": ["cosine_distance_v1", "function_word_js_v1", "classic_delta_v1"]},
        method_version={"const": "1.0.0"}, view={"enum": ["retained_prose", "function_mask_v1", "lexical_tokens"]},
        n={"enum": [None, 3, 4, 5]}, status={"enum": ["ok", "not_computable", "not_run"]},
        reason=nullable(STRING), value=nullable(NUMBER), unit=STRING, rate_unit=STRING,
        left_denominator=INTEGER, right_denominator=INTEGER, denominator_unit=STRING,
        reference_id=nullable(STRING), reference_kind={"enum": [None, "toy", "research"]},
        excluded_coordinates=IDS, contributions=array(contribution),
    )
    distance["allOf"] = [{
        "if": {"properties": {"status": {"const": "ok"}}},
        "then": {"properties": {"value": NUMBER, "reason": {"type": "null"}}},
        "else": {"properties": {"value": {"type": "null"}, "reason": STRING}},
    }]
    return obj(
        comparison_id=STRING, left_window_id=nullable(STRING), right_window_id=nullable(STRING),
        status={"enum": ["ok", "insufficient_data"]}, reason_codes=STRINGS,
        samples=obj(left=samples, right=samples), distances=array(distance),
        surface_changes=array(obj(
            feature_id=STRING, left_value=nullable(NUMBER), right_value=nullable(NUMBER),
            absolute_change=nullable(NUMBER), unit=STRING,
        )),
        limitations=STRINGS,
    )


def style_schema() -> Schema:
    selection = json.loads(files("account_history_analyzer").joinpath("contracts", "comparison.schema.json").read_text(encoding="utf-8"))
    selection["required"] = list(selection["properties"])
    for side in ("left", "right"):
        selector = selection["properties"][side]
        selector["required"] = list(selector["properties"])
    return obj(
        streams=array(style_stream_schema()),
        omitted_communities=array(obj(subreddit=nullable(STRING), eligible_words=INTEGER)),
        comparisons=array(style_comparison_schema()), manual_selection=nullable(selection),
        changes=array(change_schema()), sensitivity=sensitivity_schema(),
    )


def boundary_schema() -> Schema:
    """Candidate boundary interval between whole observed writing windows."""
    return obj(
        boundary_id=STRING, window_index={"type": "integer", "minimum": 1},
        left_window_id=STRING, right_window_id=STRING,
        left_record_id=STRING, right_record_id=STRING,
        left_utc=TIMESTAMP, right_utc=TIMESTAMP,
        left_window_first_utc=TIMESTAMP, left_window_last_utc=TIMESTAMP,
        right_window_first_utc=TIMESTAMP, right_window_last_utc=TIMESTAMP,
        record_interval={"type": "array", "items": INTEGER, "minItems": 2, "maxItems": 2},
        left_window_record_ids=IDS, right_window_record_ids=IDS,
    )


def scaling_schema() -> Schema:
    family = {"enum": ["surface", "function"]}
    return obj(
        feature_order=IDS, feature_families=array(family), means=array(NUMBER),
        standard_deviations=array({"type": "number", "exclusiveMinimum": 0}),
        family_counts=obj(surface=INTEGER, function=INTEGER), nonempty_family_count=INTEGER,
        family_weight_divisors=obj(surface=nullable(NUMBER), function=nullable(NUMBER)),
        ddof={"const": 0}, epsilon={"type": "number", "minimum": 0},
        excluded_features=array(obj(
            feature_id=STRING, family=family,
            reason={"enum": ["missing_in_some_windows", "no_windows", "standard_deviation_at_or_below_epsilon"]},
            mean=nullable(NUMBER), standard_deviation=nullable(NUMBER),
        )),
        standardized_rows=array(array(NUMBER)),
    )


def change_schema() -> Schema:
    schema = obj(
        stream_id=STRING, window_ids=IDS,
        status={"enum": ["ok", "insufficient_data", "no_measurable_variation"]},
        reason_codes=STRINGS, scaling=nullable(scaling_schema()),
        penalty_lambda={"type": "number", "exclusiveMinimum": 0},
        penalty_beta=nullable(NUMBER), objective=nullable(NUMBER), sse=nullable(NUMBER),
        internal_boundaries=array({"type": "integer", "minimum": 1}, unique=True),
        boundaries=array(boundary_schema()), optimizer={"enum": ["pelt_l2_min_size_safe_pruning_v1", "ruptures_pelt_pr383_a28574d_v1"]},
        min_size={"type": "integer", "minimum": 1}, jump={"const": 1},
        objective_definition={"const": "sum_segment_within_segment_squared_euclidean_residuals_plus_beta_times_internal_change_count"},
    )
    schema["allOf"] = [{
        "if": {"properties": {"status": {"const": "ok"}}},
        "then": {"properties": {"objective": NUMBER, "sse": NUMBER, "penalty_beta": NUMBER, "scaling": scaling_schema()}},
        "else": {"properties": {"objective": {"type": "null"}, "sse": {"type": "null"},
                                 "internal_boundaries": {"maxItems": 0}, "boundaries": {"maxItems": 0}}},
    }, {
        "if": {"properties": {"status": {"const": "insufficient_data"}}},
        "then": {"properties": {"scaling": {"type": "null"}, "penalty_beta": {"type": "null"}}},
        "else": {"properties": {"scaling": scaling_schema(), "penalty_beta": NUMBER}},
    }]
    return schema


def sensitivity_schema() -> Schema:
    """Predefined reruns, explicit execution denominators and interval relations."""
    positions = {"type": "array", "items": INTEGER, "minItems": 2, "maxItems": 2}
    change_status = {"enum": ["ok", "insufficient_data", "no_measurable_variation"]}
    match = obj(
        primary_window_index=INTEGER, matched_in_k_of_m_executed_settings=INTEGER,
        executed_setting_count=INTEGER, matched_setting_ids=IDS,
    )
    interval = obj(
        primary_boundary_id=STRING, primary_record_interval=positions,
        overlapping_boundary_ids=IDS, touching_boundary_ids=IDS,
        nearest_boundary_id=nullable(STRING), nearest_record_interval=nullable(positions),
        relation={"enum": ["overlap", "touching", "separated", "no_setting_boundaries"]},
        record_position_gap=nullable(INTEGER),
    )
    return obj(
        method_id={"const": "boundary_sensitivity_v1"}, method_version={"const": "1.0.0"},
        interpretation={"const": "parameter_stability_not_confidence"},
        same_window_boundary_tolerance=INTEGER,
        penalty_settings=array(obj(
            setting_id=STRING, penalty_lambda=NUMBER, is_primary={"type": "boolean"}, results=array(change_schema()),
        )),
        same_window_stability=array(obj(
            stream_id=STRING, executed_setting_count=INTEGER, skipped_setting_count=INTEGER,
            settings=array(obj(
                setting_id=STRING, penalty_lambda=NUMBER, status=change_status, reason_codes=STRINGS,
                matched_pairs=array(positions), unmatched_primary_boundaries=array(INTEGER),
                unmatched_setting_boundaries=array(INTEGER),
            )),
            boundaries=array(match),
        )),
        construction_settings=array(obj(
            setting_id=STRING,
            setting_type={"enum": ["window_target", "exclude_known_edited", "repeat_reduced_exact", "repeat_reduced_near"]},
            target_words=INTEGER,
            status={"enum": ["executed", "insufficient_data", "not_run", "resource_limit"]},
            reason_codes=STRINGS, excluded_record_ids=IDS,
            exclusion_relationships=array(obj(
                excluded_record_id=STRING, representative_record_id=nullable(STRING), reason=STRING,
                source_reference_id=nullable(STRING),
            )),
            streams=array(style_stream_schema()), results=array(change_schema()),
            interval_comparisons=array(obj(
                stream_id=STRING, status={"enum": ["ok", "not_comparable"]},
                primary_status=change_status, setting_status=change_status,
                primary_boundary_count=INTEGER, setting_boundary_count=INTEGER,
                comparisons=array(interval), setting_boundaries_without_overlap=IDS,
            )),
        )),
        within_community=obj(
            enabled={"type": "boolean"}, status={"enum": ["executed", "insufficient_data", "not_run"]},
            reason_codes=STRINGS, primary_stream_ids=IDS,
        ),
        limitations=STRINGS,
    )


def tighten_config(config_schema: Schema) -> Schema:
    """Constrain optional overrides to the implemented V1 method vocabulary.

    Cross-field relationships (for example rational numerator <= denominator)
    remain semantic validation. Schema annotations never expand defaults.
    """
    result = deepcopy(config_schema)
    result["properties"]["activity"]["properties"]["max_calendar_days"] = {"type": "integer", "exclusiveMinimum": 0}
    result["properties"]["artifacts"] = {
        "type": "object", "additionalProperties": False,
        "properties": {key: {"type": "integer", "minimum": 1, "maximum": ceiling}
                       for key, ceiling in (("max_file_bytes", 268435456), ("max_total_bytes", 536870912), ("max_files", 32))},
    }
    for key in ("max_index_postings", "max_work_units", "max_evidence_tokens", "max_evidence_codepoints"):
        result["properties"]["reuse"]["properties"][key] = {"type": "integer", "minimum": 0}
    fixed = {
        "schema_version": "1.0.0", "input.strict": True,
        "text.normalization": "NFC", "text.parser_profile": "commonmark_v1",
        "text.tokenizer": "lexical_regex_v1", "text.function_words_resource": "function_words_en_v1.txt",
        "text.contraction_pairs_resource": "contraction_pairs.json", "style.language": "en",
        "windows.separate_kinds": True, "changes.method": "pelt_l2_v1",
        "changes.scale_ddof": 0, "changes.jump": 1, "activity.timezone": "UTC",
        "report.remote_assets": False, "ai_text_detection.enabled": False,
        "ai_text_detection.status_reason": "not_implemented_in_v1",
    }
    allowed_zero = {
        "changes.scale_ddof", "changes.same_window_boundary_tolerance", "reuse.max_candidate_pairs",
        "reuse.max_index_postings", "reuse.max_work_units", "reuse.max_evidence_tokens", "reuse.max_evidence_codepoints",
        "reuse.near_threshold_numerator", "reuse.containment_threshold_numerator",
    }

    def walk(schema: Schema, path: str = "") -> None:
        for name, child in schema.get("properties", {}).items():
            dotted = f"{path}.{name}".lstrip(".")
            if child.get("type") == "object":
                walk(child, dotted)
            elif child.get("type") in {"integer", "number"} and dotted not in allowed_zero:
                child.pop("minimum", None)
                child["exclusiveMinimum"] = 0
            elif child.get("type") == "array" and child.get("items", {}).get("type") in {"integer", "number"}:
                child["items"].pop("minimum", None)
                child["items"]["exclusiveMinimum"] = 0
            if dotted in fixed:
                child["const"] = fixed[dotted]
    walk(result)
    properties = result["properties"]
    properties["changes"]["properties"]["minimum_windows"]["minimum"] = 8
    properties["style"]["properties"]["ngram_lengths"]["enum"] = [[3], [4], [5], [3, 4], [3, 5], [4, 5], [3, 4, 5]]
    properties["style"]["properties"]["views"]["items"]["enum"] = ["retained_prose", "function_mask_v1"]
    properties["report"]["properties"]["formats"]["items"]["enum"] = ["json", "markdown", "html"]
    properties["report"]["properties"]["formats"]["const"] = ["json", "markdown", "html"]
    properties["report"]["properties"]["excerpts"]["enum"] = ["included", "none"]
    for section, key, maximum in (
        ("windows", "single_record_dominance_fraction", 1),
        ("windows", "max_community_streams", 10),
        ("style", "max_all_pairs_windows", 100),
        ("report", "examples_per_side_per_feature", 2),
        ("report", "maximum_feature_explanations", 10),
    ):
        properties[section]["properties"][key]["maximum"] = maximum
    return result


def reuse_schema(*, legacy: bool = False) -> Schema:
    """Exact groups, complete qualifying edges and deterministic deweighting."""
    match_types = {"enum": ["raw_text_identical", "normalized_prose_identical", "token_sequence_identical"]}
    boolean = {"type": "boolean"}
    fraction = {"type": "number", "minimum": 0, "maximum": 1}
    passage_source = obj(segment_index=INTEGER, normalized_start=INTEGER, normalized_end=INTEGER, text=STRING)
    pair = obj(
        pair_id=STRING, left_record_id=STRING, right_record_id=STRING,
        left_word_count=INTEGER, right_word_count=INTEGER, left_token_count=INTEGER, right_token_count=INTEGER,
        status={"const": "ok"}, left_shingles=INTEGER, right_shingles=INTEGER, intersection=INTEGER, union=INTEGER,
        jaccard=fraction, left_in_right=fraction, right_in_left=fraction,
        near_duplicate=boolean, left_contained_in_right=boolean, right_contained_in_left=boolean,
        matching_passages=array(obj(
            match_type={"const": "contiguous_normalized_lexical_tokens"}, token_count=INTEGER, tokens=STRINGS,
            left=passage_source, right=passage_source,
        )),
    )
    schema = obj(
        scope={"const": "body_text"}, shingle_tokens={"type": "integer", "minimum": 1},
        eligible_records=INTEGER, nonempty_shingle_records=INTEGER,
        exact_groups=array(obj(
            group_id=STRING, match_type=match_types, record_ids=IDS, representative_id=STRING,
            retained_word_counts=array(obj(record_id=STRING, word_count=INTEGER)),
            substantial=boolean, reason_codes=STRINGS,
            match_sha256={"type": "string", "pattern": "^[0-9a-f]{64}$"},
        )),
        near_status={"enum": ["ok", "resource_limit"]}, candidate_pair_count=INTEGER,
        candidate_count_is_lower_bound=boolean, max_candidate_pairs=INTEGER, budget_complete=boolean,
        pairs=array(pair), connected_groups=array(obj(
            group_id=STRING, record_ids=IDS, pair_ids=IDS,
            relationship={"const": "connected_edges_not_pairwise_equivalence"},
        )),
        exact_reductions=array(obj(
            excluded_record_id=STRING, representative_record_id=STRING,
            reason={"const": "normalized_prose_identical"}, match_group_id=STRING,
        )),
        near_reductions=array(obj(
            excluded_record_id=STRING, representative_record_id=STRING,
            reason={"const": "greedy_retained_representative_near_match"}, pair_id=STRING,
            intersection=INTEGER, union=INTEGER, jaccard=fraction,
        )),
        repeat_reduced_retained_ids=IDS,
        near_reduction_status={"enum": ["not_run_disabled", "ok", "not_run_resource_limit"]},
        matching_passage_method={"const": "one_longest_contiguous_lexical_match_per_pair_v1"},
    )
    if not legacy:
        fields = {
            "resource_usage": obj(method={"const": "reuse_work_units_v1"}, work_units=INTEGER,
                                  index_postings=INTEGER, evidence_tokens=INTEGER, evidence_codepoints=INTEGER),
            "resource_limits": obj(max_work_units=INTEGER, max_index_postings=INTEGER,
                                   max_evidence_tokens=INTEGER, max_evidence_codepoints=INTEGER),
            "resource_limit_reason": {"enum": [None, "max_candidate_pairs", "max_work_units",
                                              "max_index_postings", "max_evidence_tokens", "max_evidence_codepoints"]},
        }
        schema["properties"].update(fields)
        schema["required"].extend(fields)
    schema["allOf"] = [{
        "if": {"properties": {"budget_complete": {"const": False}}},
        "then": {"properties": {
            "near_status": {"const": "resource_limit"},
            "pairs": {"maxItems": 0}, "connected_groups": {"maxItems": 0}, "near_reductions": {"maxItems": 0},
        }},
        "else": {"properties": {"near_status": {"const": "ok"}, "candidate_count_is_lower_bound": {"const": False}}},
    }]
    if legacy:
        schema["allOf"][0]["then"]["properties"]["candidate_count_is_lower_bound"] = {"const": True}
    else:
        schema["allOf"][0]["then"]["properties"]["resource_limit_reason"] = {"type": "string"}
        schema["allOf"][0]["else"]["properties"]["resource_limit_reason"] = {"type": "null"}
        schema["allOf"].extend([
            {"if": {"properties": {"resource_limit_reason": {"enum": ["max_candidate_pairs", "max_index_postings"]}}},
             "then": {"properties": {"candidate_count_is_lower_bound": {"const": True}}}},
            {"if": {"properties": {"resource_limit_reason": {"enum": ["max_evidence_tokens", "max_evidence_codepoints"]}}},
             "then": {"properties": {"candidate_count_is_lower_bound": {"const": False}}}},
        ])
    return schema


def links_schema() -> Schema:
    fraction = nullable({"type": "number", "minimum": 0, "maximum": 1})
    summary = obj(
        record_count=INTEGER, total_link_occurrences=INTEGER, valid_http_occurrences=INTEGER,
        malformed_occurrences=INTEGER, unsafe_scheme_occurrences=INTEGER, distinct_hosts=INTEGER,
        records_with_any_links=INTEGER, records_with_valid_links=INTEGER, share_records_with_valid_links=fraction,
        hosts=array(obj(
            hostname=STRING, occurrences=INTEGER, record_count=INTEGER, share_of_records=fraction,
            share_of_valid_http_links=fraction, source_record_ids=IDS, body_occurrences=INTEGER, title_occurrences=INTEGER,
        )),
    )
    return obj(
        scope={"const": "supplied_body_and_separate_submission_titles"}, summary=summary,
        by_field=array(obj(source_field={"enum": ["text", "title"]}, summary=summary)),
        by_community=array(obj(subreddit=nullable(STRING), summary=summary)),
        by_window=array(obj(window_id=STRING, summary=summary)),
        occurrences=array(obj(
            record_id=STRING, source_field={"enum": ["text", "title"]},
            source_line_range=nullable({"type": "array", "items": {"type": "integer", "minimum": 1}, "minItems": 2, "maxItems": 2}),
            hostname=nullable(STRING), url=nullable(STRING), status={"enum": ["ok", "malformed", "unsafe_scheme"]},
        )), limitations=STRINGS,
    )


def interactions_schema() -> Schema:
    boolean = {"type": "boolean"}
    parent_difference = obj(
        record_id=STRING, parent_id=nullable(STRING), created_utc=nullable(TIMESTAMP),
        parent_created_utc=nullable(TIMESTAMP), creation_to_parent_creation_seconds=nullable(NUMBER),
        parent_time_source={"enum": ["internal_record", "supplied_parent_metadata", "unavailable"]},
        status={"enum": ["ok", "negative_unverified_metadata", "missing_timestamps"]}, reason_codes=STRINGS,
    )
    parent_difference["allOf"] = [{
        "if": {"properties": {"status": {"const": "missing_timestamps"}}},
        "then": {"properties": {"creation_to_parent_creation_seconds": {"type": "null"}}},
        "else": {"properties": {"creation_to_parent_creation_seconds": NUMBER}},
    }]
    return obj(
        scope={"const": "distinct_supplied_target_account_records"}, record_count=INTEGER,
        supplied_reply_records=INTEGER, internal_parent_links=INTEGER, unresolved_parent_links=INTEGER,
        records_without_parent_id=INTEGER, records_without_thread_id=INTEGER,
        threads=array(obj(
            thread_id=STRING, record_count=INTEGER, reply_count=INTEGER, repeat_participation=boolean,
            source_record_ids=IDS, reply_record_ids=IDS,
        )), repeat_participation_thread_count=INTEGER, parent_differences=array(parent_difference),
        parent_difference_available_count=INTEGER, negative_unverified_difference_count=INTEGER,
        parent_cycles=array(obj(source_record_ids=IDS)),
        community_sequence=obj(
            timestamped_record_count=INTEGER, adjacent_pairs=INTEGER, changed_label_count=INTEGER,
            transition_counts=array(obj(
                from_subreddit=nullable(STRING), to_subreddit=nullable(STRING), count=INTEGER, includes_unknown_label=boolean,
            )),
            transitions=array(obj(
                left_record_id=STRING, right_record_id=STRING, left_utc=TIMESTAMP, right_utc=TIMESTAMP,
                from_subreddit=nullable(STRING), to_subreddit=nullable(STRING), changed_label=boolean,
            )),
        ), limitations=STRINGS,
    )


def module_payloads(snapshot_schema: Schema) -> dict[str, Schema]:
    """Return complete payload contracts, detached from caller-owned schemas."""
    return deepcopy({
        "coverage": coverage_schema(snapshot_schema),
        "text": obj(body=pooled_text_schema(), titles=pooled_text_schema()),
        "activity": activity_schema(snapshot_schema),
        "reuse": reuse_schema(),
        "style": style_schema(),
        "links": links_schema(),
        "interactions": interactions_schema(),
        "ai_text_detection": obj(capability={"const": "not_implemented_in_v1"}),
    })


def tighten_results(results_schema: Schema, snapshot_schema: Schema) -> Schema:
    """Replace only module extension slots; preserve the supplied envelope."""
    result = deepcopy(results_schema)
    for module, payload in module_payloads(snapshot_schema).items():
        module_schema = result["properties"]["modules"]["properties"][module]
        module_schema["properties"]["payload"] = {"anyOf": [payload, reuse_schema(legacy=True)]} if module == "reuse" else payload
        module_schema["$comment"] = "Payload contract is generated by payload_schemas.py; all fields are explicit."
    # Old data stays readable. Current-version outputs must include the new
    # complete resource accounting, not silently masquerade as legacy payloads.
    result["allOf"] = [{
        "if": {"properties": {"analysis": {"properties": {"suite_version": {"enum": ["1.0.2", "1.0.3", "1.0.4"]}}}}},
        "then": {"properties": {"modules": {"properties": {"reuse": {"properties": {"payload": reuse_schema()}}}}}},
    }]
    return result
