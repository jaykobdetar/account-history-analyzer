"""RE acceptance gates and hand-checkable content-reuse evidence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from account_history_analyzer.activity import analyze_activity
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.features import extract_records
from account_history_analyzer.io import canonical_bytes, load_snapshot
from account_history_analyzer.reuse import analyze_reuse, ratio_at_least, shingle_metrics, shingle_set
from account_history_analyzer.text import tokenize

ROOT = Path(__file__).resolve().parents[1]
WORDS = ["term" + chr(97 + index // 26) + chr(97 + index % 26) for index in range(120)]


def run_texts(tmp_path, texts, *, overrides=None, text_format="markdown"):
    records = [{"schema_version": "1.0.0", "id": f"r{index:03}", "account_id": "account", "kind": "comment", "text": text, "status": "present", "created_utc": f"2025-01-01T00:{index // 60:02}:{index % 60:02}Z"} for index, text in enumerate(texts)]
    manifest = {"schema_version": "1.0.0", "snapshot_id": "snapshot", "account_id": "account", "source_category": "synthetic", "text_format": text_format, "default_language": "en", "coverage": {"status": "unknown"}}
    input_path, manifest_path = tmp_path / "records.jsonl", tmp_path / "snapshot.json"
    input_path.write_bytes(b"".join(canonical_bytes(record) for record in records))
    manifest_path.write_bytes(canonical_bytes(manifest))
    snapshot = load_snapshot(input_path, manifest_path)
    config = AnalysisConfig.from_mapping(overrides)
    features = extract_records(snapshot, config)
    return analyze_reuse(snapshot, features, config), snapshot, features, config


def test_RE_01_arithmetic_normalized_not_raw_identical():
    config = AnalysisConfig.from_toml()
    snapshot = load_snapshot(ROOT / "fixtures/arithmetic.jsonl", ROOT / "fixtures/arithmetic.snapshot.json")
    result = analyze_reuse(snapshot, extract_records(snapshot, config), config)
    assert [group["match_type"] for group in result["exact_groups"]] == ["normalized_prose_identical", "token_sequence_identical"]
    assert all(group["record_ids"] == ["arithmetic_001", "arithmetic_002"] for group in result["exact_groups"])
    assert all(group["substantial"] is False for group in result["exact_groups"])
    assert result["exact_reductions"][0]["excluded_record_id"] == "arithmetic_002"


def test_RE_02_token_match_does_not_claim_string_identity(tmp_path):
    result, *_ = run_texts(tmp_path, ["Alpha, beta gamma!", "ALPHA beta; GAMMA."])
    assert [group["match_type"] for group in result["exact_groups"]] == ["token_sequence_identical"]
    assert not result["exact_reductions"]


def test_RE_03_excluded_quote_code_and_paragraph_boundaries(tmp_path):
    shared = " ".join(WORDS[:30])
    result, *_ = run_texts(tmp_path, [f"> {shared}\n\nalpha retained", f"> {shared}\n\nbeta other", f"```\n{shared}\n```\n\ngamma third", f"```\n{shared}\n```\n\ndelta fourth"])
    assert result["exact_groups"] == []
    assert result["pairs"] == []
    assert result["nonempty_shingle_records"] == 0
    separated, *_ = run_texts(tmp_path, ["alpha beta\n\ngamma delta", "alpha beta gamma delta"])
    assert separated["exact_groups"] == []


def test_RE_04_short_empty_sentinel_and_code_only(tmp_path):
    result, *_ = run_texts(tmp_path, ["OK", "OK", "", "", "[deleted]", "[deleted]", "```\ncode\n```", "```\ncode\n```"])
    assert all(group["reason_codes"] == ["short_common_text"] for group in result["exact_groups"])
    assert all(not group["substantial"] for group in result["exact_groups"])
    assert all("r002" not in group["record_ids"] and "r004" not in group["record_ids"] for group in result["exact_groups"])
    code = [group for group in result["exact_groups"] if "r006" in group["record_ids"]]
    assert len(code) == 1 and code[0]["match_type"] == "raw_text_identical"
    assert result["pairs"] == []


def test_RE_06_RE_07_disconnected_shared_shingles_have_actual_contiguous_evidence(tmp_path):
    a = WORDS[:5] + ["leftunique"] + WORDS[10:15]
    b = WORDS[:5] + ["rightunique"] + WORDS[10:15]
    result, _, features, _ = run_texts(tmp_path, [" ".join(a), " ".join(b)], overrides={"reuse": {"minimum_near_duplicate_words": 1, "near_threshold_numerator": 1, "near_threshold_denominator": 100}})
    pair = result["pairs"][0]
    assert pair["intersection"] == 2
    passage = pair["matching_passages"][0]
    assert passage["token_count"] == 5
    assert passage["tokens"] == WORDS[:5]
    for side, feature in zip(("left", "right"), features, strict=True):
        evidence = passage[side]
        segment = feature["segments"][evidence["segment_index"]]["text"]
        assert segment[evidence["normalized_start"]:evidence["normalized_end"]] == evidence["text"]
        assert [token["normalized"] for token in tokenize(evidence["text"])] == passage["tokens"]


def test_RE_07_case_punctuation_differences_retained_in_match_evidence(tmp_path):
    left = " ".join(WORDS[:25])
    right = ", ".join(WORDS[:25]).upper()
    result, *_ = run_texts(tmp_path, [left, right])
    pair = result["pairs"][0]
    assert pair["jaccard"] == 1
    passage = pair["matching_passages"][0]
    assert passage["token_count"] == 25
    assert passage["left"]["text"] != passage["right"]["text"]
    assert passage["match_type"] == "contiguous_normalized_lexical_tokens"


def test_RE_09_pair_budget_retains_exact_and_never_partial_near(tmp_path):
    text = " ".join(WORDS[:30])
    result, *_ = run_texts(tmp_path, [text, text, text], overrides={"reuse": {"max_candidate_pairs": 1, "repeat_reduced_near_sensitivity": True}})
    assert result["near_status"] == "resource_limit"
    assert result["budget_complete"] is False
    assert result["candidate_pair_count"] == 2
    assert result["candidate_count_is_lower_bound"] is True
    assert result["pairs"] == result["connected_groups"] == []
    assert len(result["exact_groups"]) == 3
    assert len(result["exact_reductions"]) == 2
    assert result["near_reductions"] == []
    assert result["near_reduction_status"] == "not_run_resource_limit"


def test_RE_10_repeat_reduced_is_deterministic_and_preserves_primary_activity(tmp_path):
    text = " ".join(WORDS[:30])
    result, snapshot, features, config = run_texts(tmp_path, [text, "  " + text, text.upper()])
    before = canonical_bytes(features)
    assert result["exact_reductions"][0]["representative_record_id"] == "r000"
    assert result["exact_reductions"][0]["excluded_record_id"] == "r001"
    assert result["repeat_reduced_retained_ids"] == ["r000", "r002"]
    assert analyze_activity(snapshot, config)["event_count"] == 3
    assert canonical_bytes(features) == before
    repeated = analyze_reuse(snapshot, features, config)
    assert canonical_bytes(repeated) == canonical_bytes(result)


def test_RE_11_near_reduction_requires_retained_representative(tmp_path):
    a = WORDS[:50]
    b = WORDS[60:65] + WORDS[5:50]
    c = WORDS[60:65] + WORDS[5:45] + WORDS[70:75]
    result, *_ = run_texts(tmp_path, [" ".join(a), " ".join(b), " ".join(c)], overrides={"reuse": {"repeat_reduced_near_sensitivity": True}})
    near_pairs = {(pair["left_record_id"], pair["right_record_id"]) for pair in result["pairs"] if pair["near_duplicate"]}
    assert ("r000", "r001") in near_pairs and ("r001", "r002") in near_pairs and ("r000", "r002") not in near_pairs
    assert len(result["near_reductions"]) == 1
    assert result["near_reductions"][0]["excluded_record_id"] == "r001"
    assert result["near_reductions"][0]["representative_record_id"] == "r000"
    assert result["repeat_reduced_retained_ids"] == ["r000", "r002"]


def test_NUM_REUSE_oracle_and_rational_thresholds():
    oracle = json.loads((ROOT / "fixtures/numerical_oracles.json").read_text())["shingles"]
    a = shingle_set([oracle["tokens_a"]], oracle["n"])
    b = shingle_set([oracle["tokens_b"]], oracle["n"])
    result = shingle_metrics(a, b)
    assert result["left_shingles"] == result["right_shingles"] == 3
    assert result["intersection"] == 2 and result["union"] == 4
    assert result["jaccard"] == .5
    assert result["left_in_right"] == result["right_in_left"] == 2 / 3
    assert ratio_at_least(4, 5, 80, 100)
    assert not ratio_at_least(799, 1000, 80, 100)
    assert not ratio_at_least(0, 0, 80, 100)
    assert shingle_metrics(frozenset(), a)["jaccard"] is None


def test_NUM_REUSE_containment_is_directed_and_respects_shorter_word_guard(tmp_path):
    result, *_ = run_texts(tmp_path, [" ".join(WORDS[:50]), " ".join(WORDS[:100])])
    pair = result["pairs"][0]
    assert pair["left_in_right"] == 1
    assert pair["right_in_left"] < 1
    assert pair["left_contained_in_right"] is True
    assert pair["right_contained_in_left"] is False
    assert pair["near_duplicate"] is False
    under, *_ = run_texts(tmp_path, [" ".join(WORDS[:49]), " ".join(WORDS[:100])])
    assert under["pairs"] == []


def test_regression_zero_threshold_must_consider_disjoint_nonempty_sets(tmp_path):
    result, *_ = run_texts(tmp_path, [" ".join(WORDS[:25]), " ".join(WORDS[50:75])], overrides={"reuse": {"near_threshold_numerator": 0}})
    assert result["candidate_pair_count"] == 1
    pair = result["pairs"][0]
    assert pair["intersection"] == 0
    assert pair["near_duplicate"] is True
    assert pair["matching_passages"] == []


def test_RE_12_persistent_identifiers_are_digest_strings(tmp_path):
    text = " ".join(WORDS[:25])
    result, *_ = run_texts(tmp_path, [text, text])
    assert all(len(group["match_sha256"]) == 64 for group in result["exact_groups"])
    assert result["pairs"][0]["pair_id"].startswith("reuse_pair_")
    assert result["pairs"][0]["intersection"] == 21
