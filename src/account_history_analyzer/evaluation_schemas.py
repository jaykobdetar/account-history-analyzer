"""Build-time schemas for evaluator output; no defaults or inferred contracts."""
from .payload_schemas import INTEGER, NUMBER, STRING, STRINGS, array, nullable, obj


def synthetic_evaluation_schema() -> dict:
    sha = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
    boolean = {"type": "boolean"}
    interval = {"type": "array", "items": INTEGER, "minItems": 2, "maxItems": 2}
    value = {"$ref": "#/$defs/json_value"}
    check = obj(check_id=STRING, status={"enum": ["passed", "failed", "not_evaluated"]},
        evidence_level={"enum": ["numerical_correctness", "synthetic_signal", "fixture_integrity"]},
        expected=value, observed=value, tolerance=nullable({"type": "number", "minimum": 0}), reason=nullable(STRING))
    candidate = obj(boundary_id=STRING, record_interval=interval,
        relation={"enum": ["overlap", "touching", "separated"]}, record_position_gap=INTEGER,
        neighboring_window=boolean, left_record_id=STRING, right_record_id=STRING)
    boundary = obj(position={"type": "integer", "minimum": 1}, record_interval=interval,
        definition={"const": "operation_begins_at_zero_based_record_position"},
        neighbor_definition={"const": "construction_adjacent_record_inside_either_candidate_adjacent_window"},
        streams=array(obj(stream_id=STRING, status={"enum": ["ok", "insufficient_data", "no_measurable_variation"]}, candidates=array(candidate))))
    fixture = obj(case=STRING, canonical_snapshot_sha256=sha, results_sha256=sha,
        analysis_exit_code={"enum": [0, 4]},
        module_statuses=obj(**{key: {"enum": ["ok", "insufficient_data", "not_run", "resource_limit"]}
            for key in ("coverage", "text", "activity", "reuse", "style", "links", "interactions", "ai_text_detection")}),
        checks=array(check),
        summary=obj(**{key: INTEGER for key in ("record_count", "retained_words", "event_count", "eligible_style_records",
                    "exact_reuse_groups", "near_reuse_pairs", "qualified_primary_windows", "primary_candidates", "findings")}),
        construction_boundary=nullable(boundary))
    schema = obj(schema_version={"const": "1.0.0"}, suite={"const": "synthetic"},
        method_id={"const": "synthetic_construction_evaluation_v1"}, method_version={"const": "1.0.0"},
        status={"enum": ["passed", "failed"]}, real_world_validation={"const": "not_established"},
        external_data={"const": "not_evaluated"}, label_definition={"const": "construction_operations_only"},
        config_sha256=sha, implementation_fingerprint=sha, reference_environment=STRING,
        dataset=obj(fixture_version=STRING, index_sha256=sha, content_sha256=sha,
            files=array(obj(file=STRING, bytes=INTEGER, sha256=sha, index_matches=boolean)),
            shipped_scenarios_complete=boolean, missing_shipped_scenarios=STRINGS),
        numerical_checks=array(check), fixtures=array(fixture), cross_fixture_checks=array(check),
        check_counts=obj(passed=INTEGER, failed=INTEGER, not_evaluated=INTEGER), limitations=STRINGS)
    schema.update({"$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "AHAS V1 synthetic construction evaluation",
        "$defs": {"json_value": {"anyOf": [{"type": "null"}, boolean, NUMBER, STRING,
            array(value), {"type": "object", "additionalProperties": value}]}}})
    return schema
