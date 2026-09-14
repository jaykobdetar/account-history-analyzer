"""Versioned, machine-readable method and feature descriptions.

Registry membership describes the method contract; it is not evidence that a
method ran. Module status in each result records execution and missingness.
No supplied identifiers, labels, timestamps, or fixture facts enter this registry.
"""
from __future__ import annotations

from copy import deepcopy
from importlib.resources import files
import json
from typing import Any, Iterable, Mapping

REGISTRY_VERSION = "1.0.2"
METHOD_VERSION = "1.0.0"

PUNCTUATION: dict[str, str] = {
    "comma": ",", "period": ".", "question_mark": "?", "exclamation_mark": "!",
    "semicolon": ";", "colon": ":", "ascii_apostrophe": "'", "curly_apostrophe": "’",
    "ascii_double_quote": '"', "left_curly_double_quote": "“", "right_curly_double_quote": "”",
    "ascii_hyphen": "-", "en_dash": "–", "em_dash": "—", "ellipsis": "…",
}

FEATURE_EVIDENCE_RULE = (
    "Select at most configured examples_per_side_per_feature records per side by "
    "descending qualifying per-record rate, requiring the configured denominator "
    "minimum; ties use chronological/ID order. Cite actual normalized segment "
    "slices, or the original block when exact raw mapping is unavailable. Include "
    "record nearest median retained word count as ordinary context, tie by "
    "chronological/ID order. Never present normalized offsets as raw offsets."
)


def method_version(method_id: str) -> str:
    """Keep unaffected methods frozen while versioning the optimizer backport."""
    if method_id == "pelt_l2_v1":
        return "1.0.1"
    if method_id in {"retained_prose_v1", "link_hosts_v1", "shingle_reuse_v1", "bounded_artifact_envelope_v1", "reuse_work_units_v1"}:
        return "1.0.2"
    return METHOD_VERSION


def _method(method_id: str, origin: str, description: str, formula: str,
            parameters: Mapping[str, Any], references: Iterable[str] = (),
            limitations: Iterable[str] = ()) -> dict[str, Any]:
    return {
        "method_id": method_id, "version": method_version(method_id), "origin": origin,
        "description": description, "formula": formula,
        "parameters": dict(parameters), "references": list(references),
        "limitations": list(limitations),
    }


_METHODS = [
    _method("bounded_artifact_envelope_v1", "engineering_default", "Complete bounded artifact publication and replay.",
            "Stream canonical JSON and checksums; reject file, total, count or metadata overflow before atomic publication",
            {"max_file_bytes": 268435456, "max_total_bytes": 536870912, "max_files": 32,
             "metadata_max_bytes": 1048576, "metadata_files": ["checksums.json", "resolved_config.json"],
             "input_budget_separate": True, "overrides": "may tighten release ceilings",
             "recompute_scope": "all canonical artifacts including reports and charts; receipts excluded"},
            limitations=["byte_envelope_not_universal_ram_or_runtime_guarantee", "hashes_not_authenticity"]),
    _method("reuse_work_units_v1", "engineering_default", "Deterministic exact reuse work and evidence budgets.",
            "Count shingle construction, posting visits, exact membership scans, suffix-automaton operations and evidence emission",
            {"max_work_units": 250000000, "max_index_postings": 2000000,
             "max_evidence_tokens": 2000000, "max_evidence_codepoints": 8000000,
             "exhaustion": "all near pairs/groups/reductions withheld; complete exact groups retained",
             "matcher": "segmented exact suffix automaton; length then left/right segment and token-offset ties"},
            limitations=["work_units_not_seconds_or_confidence", "exhausted_search_is_incomplete"]),
    _method("canonical_snapshot_v1", "engineering_default", "Strict expanded, deduplicated supplied snapshot.",
            "SHA256(canonical JSON(expanded manifest, unique sorted records))",
            {"sort": ["timestamp_missing", "created_epoch_microseconds", "id"],
             "json": "UTF-8; sorted keys; compact separators; finite numbers; positive zero; final newline"},
            ["S12", "S13"], ["hashes_do_not_establish_authenticity", "reference_environment_identity_only"]),
    _method("retained_prose_v1", "engineering_default", "Segmented visible prose under explicit plain/CommonMark input mode.",
            "NFC and LF normalization; remove defined excluded spans; normalize horizontal whitespace",
            {"normalization": "NFC", "parser_profile": "commonmark_v1", "typographer": False,
             "hard_boundaries": ["record", "paragraph", "excluded_span"], "hyperlink_label_urls": "exclude spans; count destination only"}, ["S14"],
            ["commonmark_is_not_all_reddit_dialects", "semantic_quotation_not_detected"]),
    _method("lexical_regex_v1", "engineering_default", "Operational Unicode lexical tokenization.",
            r"(?u)[^\W\d_]+(?:['’][^\W\d_]+)*|\d+",
            {"case_insensitive": "casefold; internal curly apostrophe mapped to straight apostrophe",
             "number_rule": "all-digit matches", "style_denominator": "word tokens only"},
            limitations=["operational_tokenizer_not_linguistic_segmentation"]),
    _method("surface_counts_v1", "engineering_default", "Direct retained-prose counts and pooled rates.",
            "pooled rate = sum(numerator) / sum(denominator)",
            {"word_rate_scale": 1000, "codepoint_rate_scale": 1000,
             "uppercase": "str.isupper / (str.isupper + str.islower)",
             "word_length": "alphabetic code points excluding apostrophes"},
            limitations=["surface_patterns_do_not_establish_cause"]),
    _method("function_words_v1", "project_adaptation", "Fixed curated English function-word counts.",
            "1000 * literal normalized word count / retained word tokens",
            {"resource": "function_words_en_v1.txt", "required_declared_language": "en"}, ["S3"],
            ["curated_resource_uncalibrated", "language_is_supplier_declared"]),
    _method("contraction_pairs_v1", "engineering_default", "Literal contracted versus expanded token alternatives.",
            "contracted / (contracted + expanded)",
            {"resource": "contraction_pairs.json", "minimum_opportunities": 10,
             "expanded_match": "exact adjacent normalized tokens within segment"}, ["S3"],
            ["literal_alternatives_not_verified_paraphrases"]),
    _method("function_mask_v1", "project_adaptation", "Function-word-preserving text distortion adaptation.",
            "Keep fixed-list tokens and case; replace other word letters by * and number digits by #; keep separators/apostrophes",
            {"resource": "function_words_en_v1.txt", "required_declared_language": "en"}, ["S2"],
            ["not_original_paper_configuration", "mask_not_provably_topic_free"]),
    _method("character_ngrams_v1", "project_adaptation", "Overlapping exact character n-gram profiles.",
            "Count every length-n code-point substring wholly within one segment",
            {"n": [3, 4, 5], "case_sensitive": True, "padding": False,
             "views": ["retained_prose", "function_mask_v1"]}, ["S1"],
            ["correlated_representations", "published_classification_accuracy_does_not_transfer"]),
    _method("cosine_distance_v1", "established_primitive", "Cosine distance over aligned count vectors.",
            "1 - dot(x,y)/(norm(x)*norm(y))",
            {"coordinate_order": "sorted union", "zero_norm": "not_computable",
             "excursion_tolerance": 1e-12}, ["S7"],
            ["distance_is_not_authorship_probability", "ngram_rate_differences_not_cosine_decomposition"]),
    _method("function_word_js_v1", "project_adaptation", "Base-2 Jensen-Shannon distance including residual words.",
            "sqrt(0.5*sum(p*log2(p/m)) + 0.5*sum(q*log2(q/m))); m=(p+q)/2",
            {"base": 2, "other_category": "OTHER_WORD", "smoothing": 0,
             "zero_term": 0, "denominator": "all retained word tokens"}, ["S8", "S3"],
            ["distance_is_not_authorship_probability", "empty_samples_not_computable"]),
    _method("classic_delta_v1", "established_primitive", "Mean absolute standardized-frequency difference with frozen reference.",
            "mean_j(abs((f_Aj-mu_j)/sigma_j - (f_Bj-mu_j)/sigma_j))",
            {"frequency_unit": "per_1000_word_tokens", "excluded_sigma_at_most": 1e-12,
             "reference_fit": "external frozen only", "toy_reference_requires_override": True}, ["S4"],
            ["missing_reference_not_run", "toy_reference_not_validated", "distance_is_not_authorship_probability"]),
    _method("whole_record_windows_v1", "engineering_default", "Nonoverlapping chronological whole-record windows.",
            "Accumulate whole eligible records until word and record-count guards both hold",
            {"target_words": 1000, "minimum_records": 8, "minimum_record_words": 20,
             "separate_kinds": True, "language": "en", "dominance_threshold": 0.5},
            limitations=["window_guards_are_engineering_defaults", "observed_text_ordered_by_creation_time"]),
    _method("family_standardization_v1", "project_adaptation", "Account-local population scaling and equal-family weighting.",
            "(x-mean)/sd / sqrt(retained features in family) / sqrt(nonempty families)",
            {"ddof": 0, "exclude_sd_at_most": 1e-12, "missing_rule": "exclude feature missing in any window",
             "families": ["surface", "function"]}, ["S5", "S6"],
            ["account_local_scaling_changes_with_history", "family_weights_uncalibrated"]),
    _method("pelt_l2_v1", "project_adaptation", "PELT L2 segmentation using the pinned ruptures PR #383 backport, registered family vector and penalty defaults.",
            "sum(segment squared deviations from segment mean) + beta * number of internal boundaries",
            {"model": "l2", "minimum_windows": 8, "min_size": 3, "jump": 1,
             "beta": "lambda*ln(N)", "primary_lambda": 1.0, "sensitivity_lambdas": [0.5, 2.0, 4.0],
             "optimizer": "ruptures_pelt_pr383_a28574d_v1",
             "source_commit": "a28574d9e63b0c2a966e176a1d049d3c9deaaaaf",
             "source_url": "https://github.com/deepcharles/ruptures/pull/383",
             "integration": "verbatim _seg override on locked ruptures 1.1.10",
             "pruning_comparison": "strict upstream >; no local slack",
             "tie_order": "first eligible start in increasing endpoint order",
             "pruning_rule": "Retain a dominated candidate until its witness split can precede a legal min_size segment",
             "segment_cost": "Pinned ruptures CostL2; penalized objective unchanged"},
            ["S5", "S6", "S16"], ["descriptive_candidate_not_significance", "penalties_uncalibrated"]),
    _method("boundary_sensitivity_v1", "engineering_default", "Deterministic descriptive comparison of predefined reruns.",
            "Maximum one-to-one boundary matching; minimize total displacement; lexicographic pair tie order",
            {"same_window_tolerance": 1, "different_windows": "open record-order interval interiors overlap; touching endpoints are reported separately",
             "word_targets": [500, 2000], "exclusions": ["known_edited", "normalized_prose_exact_repeats"],
             "executed_no_variation": True, "alternate_constructions_scope": "pooled kinds; primary community results provide separate controls"},
            limitations=["parameter_stability_is_not_confidence", "skipped_settings_excluded_from_denominator"]),
    _method("exact_reuse_v1", "engineering_default", "Three distinct exact-text equivalence relations.",
            "Compare original strings, retained segment sequences, or normalized token sequences with boundaries",
            {"types": ["raw_text_identical", "normalized_prose_identical", "token_sequence_identical"],
             "headline_minimum_words": 20, "empty_matches": False},
            limitations=["content_match_does_not_establish_intent", "short_common_text"]),
    _method("shingle_reuse_v1", "project_adaptation", "Exact shingle-set resemblance and directed containment.",
            "J=|A intersection B|/|A union B|; C(A in B)=|A intersection B|/|A|",
            {"tokens_per_shingle": 5, "multiplicity": "set", "near_threshold": [80, 100],
             "containment_threshold": [90, 100], "threshold_comparison": "integer cross-multiplication",
             "minimum_near_words": 20, "minimum_contained_words": 50, "candidate_pair_limit": 2000000}, ["S9"],
            ["connected_groups_not_pairwise_equivalence", "shared_shingles_not_necessarily_contiguous",
             "content_match_does_not_establish_intent"]),
    _method("repeat_reduced_v1", "engineering_default", "Deterministic content deweighting sensitivity.",
            "Keep earliest exact-prose representative; optional greedy near matches against already retained representatives",
            {"default": "normalized_prose_identical", "near_representative_tie": "highest Jaccard then earliest"},
            limitations=["deweighting_not_authorship_or_originality", "primary_activity_unchanged"]),
    _method("activity_v1", "engineering_default", "Observed supplied event counts and UTC interval summaries.",
            "Adjacent integer-microsecond differences; inclusive sliding windows; population interval SD/mean",
            {"timezone": "UTC", "sliding_window_seconds": [30, 120, 3600],
             "quantiles": "linear interpolation at (n-1)*q", "variation_minimum_intervals": 2}, ["S12"],
            ["gaps_not_sleep_or_verified_inactivity", "supplier_coverage_unverified"]),
    _method("greedy_nonoverlapping_fixed_window_bursts", "engineering_default", "Greedy disjoint bursts with a fixed first-event anchor.",
            "At i choose greatest j with t[j]-t[i]<=duration; emit and advance past j if count>=minimum, otherwise advance i",
            {"duration_seconds": 30, "minimum_events": 3},
            limitations=["one_operational_burst_definition", "timing_does_not_establish_cause"]),
    _method("link_hosts_v1", "engineering_default", "Offline explicit HTTP(S) link-host occurrence and record summaries.",
            "URL hostname; lowercase; IDNA; remove final DNS dot; count occurrences and distinct records separately",
            {"schemes": ["http", "https"], "registrable_domain_grouping": False, "fetch": False,
             "occurrence": "one hyperlink destination; label URLs are not independent bare occurrences"},
            limitations=["hostname_not_registrable_domain", "links_do_not_establish_payment_or_intent"]),
    _method("interaction_structure_v1", "engineering_default", "Local supplied parent/thread structure and timestamp differences.",
            "creation_to_parent_creation_seconds = child_created - supplied_parent_created",
            {"parent_resolution": "supplied records only", "cycle_detection": True},
            limitations=["creation_delay_not_typing_or_read_to_reply_time", "missing_context_not_evasion"]),
    _method("feature_evidence_v1", "engineering_default", "Source-linked feature examples and ordinary context.",
            FEATURE_EVIDENCE_RULE,
            {"examples_per_side_per_feature": 2, "maximum_feature_explanations": 10,
             "explanation_sort": "descending unrounded value, then feature ID"},
            limitations=["selected_examples_not_representative_sample"]),
]


def method_registry() -> list[dict[str, Any]]:
    """Return independent JSON-compatible method entries in stable ID order."""
    return deepcopy(sorted(_METHODS, key=lambda value: value["method_id"]))


def _feature(feature_id: str, description: str, view: str, formula: str,
             unit: str, numerator: str, denominator: str | None = None,
             missingness: str = "Zero is a valid count when eligible text exists; unavailable text is null.",
             evidence: str = FEATURE_EVIDENCE_RULE,
             level: str = "measurement") -> dict[str, Any]:
    return {"feature_id": feature_id, "description": description, "view": view,
            "formula": formula, "unit": unit, "numerator": numerator,
            "denominator": denominator, "missingness_rule": missingness,
            "evidence_rule": evidence, "version": METHOD_VERSION,
            "epistemic_level": level}


def feature_registry(function_words: Iterable[str] | None = None,
                     contraction_pairs: Iterable[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Return concrete feature descriptions, optionally using explicit resources.

    When omitted, resources are read from the installed package, never the cwd or
    network. Missing resources raise their ordinary file error; they are not
    silently replaced with empty lists.
    """
    resource_root = files("account_history_analyzer").joinpath("resources")
    if function_words is None:
        function_words = resource_root.joinpath("function_words_en_v1.txt").read_text(encoding="utf-8").splitlines()
    if contraction_pairs is None:
        contraction_pairs = json.loads(resource_root.joinpath("contraction_pairs.json").read_text(encoding="utf-8"))["pairs"]
    result = []
    counts = {
        "retained_words": ("Operational word tokens, excluding number tokens", "word tokens"),
        "number_tokens": ("All-digit lexical matches", "number tokens"),
        "retained_codepoints": ("Unicode code points in retained segments", "code points"),
        "cased_letters": ("Code points satisfying isupper or islower", "cased code points"),
        "uppercase_letters": ("Code points satisfying str.isupper", "uppercase code points"),
        "lowercase_letters": ("Code points satisfying str.islower", "lowercase code points"),
        "segments": ("Retained hard-boundary prose segments", "segments"),
        "paragraphs": ("Retained paragraphs before excluded-span segmentation", "paragraphs"),
        "word_character_total": ("Alphabetic code points in word tokens; excludes apostrophes", "alphabetic code points"),
        "standalone_i_lower": ("Exact standalone i word tokens; not verified pronouns", "tokens"),
        "standalone_i_upper": ("Exact standalone I word tokens; not verified pronouns", "tokens"),
    }
    for key, (description, unit) in counts.items():
        result.append(_feature(key, description, "retained_prose", f"count({description})", unit, key))
    for key in ("removed_quote_spans", "removed_code_spans", "removed_url_spans", "headings", "list_items", "links", "mentions"):
        result.append(_feature(key, key.replace("_", " ").capitalize(), "raw_source", f"count(recognized {key})", "occurrences", key))
    for name, literal in sorted(PUNCTUATION.items()):
        fid = f"punctuation.{name}"
        result.append(_feature(fid, f"Literal {name.replace('_', ' ')} ({literal})", "retained_prose", f"count({literal!r})", "characters", fid))
        for denominator, unit in (("retained_words", "per_1000_word_tokens"), ("retained_codepoints", "per_1000_retained_codepoints")):
            result.append(_feature(f"{fid}.{unit}", f"Literal {name.replace('_', ' ')} rate", "retained_prose",
                                   f"1000 * {fid} / {denominator}", unit, fid, denominator,
                                   "Null with zero_denominator when denominator is zero; unavailable text is null."))
    result.append(_feature("punctuation.ascii_period_runs", "Runs of at least three ASCII periods, overlapping literal-period count", "retained_prose", r"count(nonoverlapping matches of \.{3,})", "runs", "punctuation.ascii_period_runs"))
    for denominator, unit in (("retained_words", "per_1000_word_tokens"), ("retained_codepoints", "per_1000_retained_codepoints")):
        result.append(_feature(f"punctuation.ascii_period_runs.{unit}", "Rate of ASCII period runs; overlaps literal periods", "retained_prose",
                               f"1000 * punctuation.ascii_period_runs / {denominator}", unit, "punctuation.ascii_period_runs", denominator,
                               "Null with zero_denominator when denominator is zero; unavailable text is null."))
    for fid, description, numerator, denominator, unit in (
        ("uppercase_fraction", "Fraction of cased code points that are uppercase", "uppercase_letters", "cased_letters", "fraction"),
        ("average_word_length", "Mean alphabetic code points per retained word token", "word_character_total", "retained_words", "alphabetic_codepoints_per_word"),
    ):
        result.append(_feature(fid, description, "retained_prose", f"{numerator}/{denominator}", unit, numerator, denominator,
                               "Null with zero_denominator when denominator is zero; unavailable text is null."))
    result.append(_feature("words_per_record_quantiles", "Distribution of retained word counts across included records", "retained_prose",
                           "Linear interpolation at sorted sample index (n-1)*q", "word_tokens_per_record", "retained_words", "included records",
                           "Null with empty_sample if there are no included records.", "Export sample count and quantile definition."))
    for word in sorted(set(function_words)):
        if not word:
            continue
        fid = f"function_word.{word}"
        result.append(_feature(fid, f"Literal normalized function word {word!r}", "lexical_tokens", f"count(token == {word!r})", "occurrences", fid,
                               missingness="Not run unless declared English; eligible text permits a zero count."))
        result.append(_feature(f"{fid}.per_1000_word_tokens", f"Pooled frequency of {word!r}", "lexical_tokens",
                               f"1000*{fid}/retained_words", "per_1000_word_tokens", fid, "retained_words",
                               "Not run unless declared English; null with zero_denominator."))
    for pair in sorted(contraction_pairs, key=lambda value: value["id"]):
        pid = f"contraction.{pair['id']}"
        for form in ("contracted", "expanded"):
            result.append(_feature(f"{pid}.{form}", f"Literal {form} alternative {pair[form]!r}", "lexical_tokens",
                                   "Count exact adjacent token sequence within each segment", "occurrences", f"{pid}.{form}",
                                   missingness="Not run unless declared English; zero is a valid count."))
        result.append(_feature(f"{pid}.fraction", "Literal contracted preference among matched alternatives", "lexical_tokens",
                               "contracted/(contracted+expanded)", "fraction", f"{pid}.contracted", f"{pid}.contracted+{pid}.expanded",
                               "No opportunities: null. Below configured guard: insufficient_opportunities; preserve nonempty raw fraction in evidence."))
    for view in ("retained_prose", "function_mask_v1"):
        for n in (3, 4, 5):
            result.append(_feature(f"chargram.{view}.{n}.cosine_distance", f"{n}-gram cosine distance between pooled profiles", view,
                                   "1-dot(x,y)/(norm(x)*norm(y))", "cosine_distance", "dot(x,y)", "norm(x)*norm(y)",
                                   "Not computable for either zero norm; masked view requires declared English.",
                                   "All normalized-frequency differences exported; largest absolute differences are feature differences, not exact cosine contributions.", "derived_comparison"))
    result.append(_feature("function_word.js_distance", "Function-word plus OTHER_WORD base-2 Jensen-Shannon distance", "lexical_tokens",
                           "sqrt(sum(nonnegative per-category Jensen-Shannon divergence contributions))", "base_2_js_distance", "Jensen-Shannon divergence", "all retained words per side",
                           "Not computable for empty side; English declaration required.", "Export category divergence contributions before square root and absolute pooled rate changes.", "derived_comparison"))
    result.append(_feature("classic_delta.distance", "Classic Delta using a frozen reference", "lexical_tokens",
                           "mean(abs(z_Aj-z_Bj)) over valid reference coordinates", "mean_absolute_standardized_frequency_difference", "sum(abs(z_Aj-z_Bj))", "valid reference coordinates",
                           "Missing reference: not_run_missing_reference. Exclude sigma <= 1e-12. No valid coordinates: not_computable.", "Export absolute standardized-frequency difference for each valid coordinate.", "derived_comparison"))
    return sorted(result, key=lambda value: value["feature_id"])


def registry_document(function_words: Iterable[str] | None = None,
                      contraction_pairs: Iterable[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Return the complete canonicalizable registry document."""
    return {"registry_version": REGISTRY_VERSION, "methods": method_registry(),
            "features": feature_registry(function_words, contraction_pairs)}
