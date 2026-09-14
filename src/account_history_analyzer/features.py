"""Direct, pooled, inspectable measurements of retained text; no identity labels."""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any
import re

import numpy as np

from .config import AnalysisConfig
from .io import Snapshot, freeze
from .registry import PUNCTUATION
from .text import contraction_pairs, function_words, preprocess

_COUNT_KEYS = ("retained_words", "number_tokens", "retained_codepoints", "cased_letters",
               "uppercase_letters", "lowercase_letters", "segments", "paragraphs",
               "word_character_total", "standalone_i_lower", "standalone_i_upper",
               "removed_quote_spans", "removed_code_spans", "removed_url_spans", "headings",
               "list_items", "links", "mentions")
_PUNCTUATION_KEYS = tuple(sorted((*PUNCTUATION, "ascii_period_runs")))


def _zero_counts() -> dict[str, Any]:
    return {**dict.fromkeys(_COUNT_KEYS, 0), "punctuation": dict.fromkeys(_PUNCTUATION_KEYS, 0)}


def _rates(counts: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    def divide(numerator: int | None, denominator: int | None, scale: int = 1) -> float | None:
        return scale * numerator / denominator if denominator and numerator is not None else None
    rates = {"uppercase_fraction": divide(counts["uppercase_letters"], counts["cased_letters"]),
             "average_word_length": divide(counts["word_character_total"], counts["retained_words"]),
             "punctuation_per_1000_words": {key: divide(value, counts["retained_words"], 1000) for key, value in counts["punctuation"].items()},
             "punctuation_per_1000_codepoints": {key: divide(value, counts["retained_codepoints"], 1000) for key, value in counts["punctuation"].items()}}
    reasons = []
    for key in ("retained_words", "retained_codepoints", "cased_letters"):
        if not counts[key]:
            reasons.append(f"zero_{key}_denominator" if counts[key] == 0 else "unavailable_text")
    return rates, sorted(set(reasons))


def _contraction_result(contracted: int | None, expanded: int | None, minimum: int) -> dict[str, Any]:
    opportunities = contracted + expanded if contracted is not None and expanded is not None else None
    raw = contracted / opportunities if opportunities else None
    status = "not_run" if opportunities is None else "ok" if opportunities >= minimum else "insufficient_opportunities"
    return {"contracted": contracted, "expanded": expanded, "opportunities": opportunities,
            "raw_fraction": raw, "fraction": raw if status == "ok" else None, "status": status}


def _count_sequence(segments: Sequence[Sequence[str]], sequence: Sequence[str]) -> int:
    target = tuple(sequence)
    return sum(tuple(segment[index:index + len(target)]) == target
               for segment in segments for index in range(len(segment) - len(target) + 1))


def measure(view: Mapping[str, Any], config: AnalysisConfig, *, language: str | None = None) -> Mapping[str, Any]:
    """Attach direct counts to a derived view without modifying it.

    Unavailable text has null counts; usable empty text has zero literal counts
    with undefined/null rates. English resources run only on declared English.
    """
    language = language or view.get("language", "und")
    counts = _zero_counts()
    if view["usable"]:
        flat = [token for group in view["token_offsets"] for token in group]
        words = [token["text"] for token in flat if token["kind"] == "word"]
        strings = [segment["text"] for segment in view["segments"]]
        counts.update(retained_words=len(words), number_tokens=sum(token["kind"] == "number" for token in flat),
                      retained_codepoints=sum(map(len, strings)),
                      uppercase_letters=sum(char.isupper() for value in strings for char in value),
                      lowercase_letters=sum(char.islower() for value in strings for char in value),
                      segments=len(strings), word_character_total=sum(char.isalpha() for word in words for char in word),
                      standalone_i_lower=words.count("i"), standalone_i_upper=words.count("I"))
        counts["cased_letters"] = counts["uppercase_letters"] + counts["lowercase_letters"]
        for key in view["structure"]:
            counts[key] = view["structure"][key]
        counts["punctuation"] = {key: sum(value.count(char) for value in strings) for key, char in sorted(PUNCTUATION.items())}
        counts["punctuation"]["ascii_period_runs"] = sum(len(re.findall(r"\.{3,}", value)) for value in strings)
    else:
        counts = {**dict.fromkeys(_COUNT_KEYS, None), "punctuation": dict.fromkeys(_PUNCTUATION_KEYS, None)}
    english = view["usable"] and language == "en"
    words_normalized = Counter(word for segment in view["word_tokens"] for word in segment)
    functions = {word: words_normalized[word] if english else None for word in sorted(function_words())}
    function_rates = {word: 1000 * count / counts["retained_words"] if count is not None and counts["retained_words"] else None
                      for word, count in functions.items()}
    contractions = {pair["id"]: _contraction_result(
        _count_sequence(view["tokens"], pair["contracted"]) if english else None,
        _count_sequence(view["tokens"], pair["expanded"]) if english else None,
        config["style"]["contraction_minimum_opportunities"]) for pair in contraction_pairs()}
    rates, reasons = _rates(counts)
    return freeze({**dict(view), "counts": counts, "rates": rates, "rate_reason_codes": reasons,
                   "function_counts": functions, "function_rates": function_rates, "contractions": contractions})


def extract_records(snapshot: Snapshot, config: AnalysisConfig) -> list[Mapping[str, Any]]:
    """Extract immutable body feature records in the snapshot's canonical order.

    Submission titles receive the same separate measurement structure under
    ``title``. They are never concatenated into body segments or word budgets.
    """
    records = []
    for record in snapshot.records:
        view = dict(preprocess(record, snapshot.manifest, config))
        if view["title"] is not None:
            title = {**dict(view["title"]), "id": view["id"], "language": view["language"],
                     "source_field": "title", "kind": view["kind"], "subreddit": view["subreddit"],
                     "created_utc": view["created_utc"], "edit_state": view["edit_state"]}
            view["title"] = measure(title, config)
        records.append(measure(view, config))
    return records


def pooled(records: Sequence[Mapping[str, Any]], config: AnalysisConfig) -> dict[str, Any]:
    """Pool observed literal counts before dividing; never average record rates.

    Unavailable records are counted in ``record_count`` but excluded from text
    denominators and the length sample. With no usable English records the
    English-specific counts are null. Empty scopes have zero observed counts
    and null rates, accompanied by sample sizes and denominator reason codes.
    """
    observed = [record for record in records if record["usable"]]
    english = [record for record in observed if record["language"] == "en"]
    counts = _zero_counts()
    for record in observed:
        for key in _COUNT_KEYS:
            counts[key] += record["counts"][key]
        for key in _PUNCTUATION_KEYS:
            counts["punctuation"][key] += record["counts"]["punctuation"][key]
    rates, reasons = _rates(counts)
    word_count = sum(record["counts"]["retained_words"] for record in english)
    functions = {word: sum(record["function_counts"][word] for record in english) if english else None
                 for word in sorted(function_words())}
    function_rates = {word: 1000 * count / word_count if count is not None and word_count else None
                      for word, count in functions.items()}
    contractions = {pair["id"]: _contraction_result(
        sum(record["contractions"][pair["id"]]["contracted"] for record in english) if english else None,
        sum(record["contractions"][pair["id"]]["expanded"] for record in english) if english else None,
        config["style"]["contraction_minimum_opportunities"]) for pair in contraction_pairs()}
    lengths = [record["counts"]["retained_words"] for record in observed]
    distribution = {"count": len(lengths), "min": min(lengths) if lengths else None,
                    "max": max(lengths) if lengths else None,
                    **{label: float(np.quantile(lengths, q, method="linear")) if lengths else None
                       for label, q in (("q25", 0.25), ("median", 0.5), ("q75", 0.75))}}
    return {"record_count": len(records), "usable_record_count": len(observed), "english_record_count": len(english), "english_word_count": word_count,
            "counts": counts, "rates": rates, "rate_reason_codes": reasons,
            "function_counts": functions, "function_rates": function_rates,
            "contractions": contractions, "words_per_record": distribution}
