"""Deterministic retained-prose segments with explicit exclusion boundaries."""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from functools import lru_cache
from html import unescape
import json
import re
import unicodedata
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from markdown_it import MarkdownIt

from .config import AnalysisConfig, resource_bytes
from .io import freeze, sha256_bytes

LEXICAL_RE = re.compile(r"(?u)[^\W\d_]+(?:['’][^\W\d_]+)*|\d+")
# Conservative HTTP(S) scanner: whitespace, angle brackets, quotes and backticks
# stop a URL. Terminal sentence punctuation and unmatched closing brackets stay
# in prose. Unknown protocols/formats remain prose.
_URL_RE = re.compile(r'https?://(?:(?!\]\()[^\s<>"\'`])+', re.IGNORECASE)
_MENTION_RE = re.compile(r"(?<![\w/])/?[ur]/[A-Za-z0-9_-]+")
_HORIZONTAL_RE = re.compile(r"[^\S\n]+")


@lru_cache(maxsize=1)
def function_words() -> frozenset[str]:
    """Load the fixed bundled English word list, without network or cwd lookup."""
    return frozenset(resource_bytes("function_words_en_v1.txt").decode("utf-8").splitlines())


@lru_cache(maxsize=1)
def contraction_pairs() -> tuple[Mapping[str, Any], ...]:
    """Load immutable exact token alternatives from the bundled resource."""
    return freeze(json.loads(resource_bytes("contraction_pairs.json"))["pairs"])


def normalized_token(value: str) -> str:
    """Normalize lexical matching only; surface views preserve case/apostrophe."""
    return value.casefold().replace("’", "'")


def tokenize(value: str) -> tuple[Mapping[str, Any], ...]:
    """Return tokens with offsets in the supplied normalized segment, not raw text."""
    return tuple(freeze({"text": match.group(), "normalized": normalized_token(match.group()),
                         "start": match.start(), "end": match.end(),
                         "kind": "number" if match.group().isdigit() else "word"})
                 for match in LEXICAL_RE.finditer(value))


def function_mask(value: str) -> str:
    """Apply the named fixed-function-word mask adaptation within one segment."""
    words = function_words()
    def replace(match: re.Match[str]) -> str:
        token = match.group()
        if normalized_token(token) in words:
            return token
        if token.isdigit():
            return "".join("#" if char.isdigit() else char for char in token)
        return "".join("*" if char.isalpha() else char for char in token)
    return LEXICAL_RE.sub(replace, value)


def _url_spans(value: str) -> list[tuple[int, int, str]]:
    spans = []
    for match in _URL_RE.finditer(value):
        candidate = match.group().rstrip(".,!?;:")
        bracket_counts = Counter(char for char in candidate if char in "()[]{}")
        stop = len(candidate)
        while stop and candidate[stop - 1] in ")]}":
            right = candidate[stop - 1]
            left = {")": "(", "]": "[", "}": "{"}[right]
            if bracket_counts[right] <= bracket_counts[left]:
                break
            bracket_counts[right] -= 1
            stop -= 1
        candidate = candidate[:stop]
        if candidate:
            spans.append((match.start(), match.start() + len(candidate), candidate))
    return spans


def _unused_url_prefix(source: str) -> str:
    """Choose a collision-free marker with one bounded scan of the source.

    Each candidate prefix present in source occupies a regex match. Therefore
    the first unused canonical decimal suffix is found after at most the
    number of matches plus one probes, without repeatedly scanning the source.
    Include entity-decoded text because CommonMark decodes entities before the
    placeholder restoration pass; raw and decoded literal markers both survive.
    """
    marker = re.compile(r"AHASURLTOKEN([0-9]+)END")
    used = {match.group(1) for value in (source, unescape(source))
            for match in marker.finditer(value)}
    nonce = 0
    while str(nonce) in used:
        nonce += 1
    return f"AHASURLTOKEN{nonce}END"


def safe_link(value: str, source_field: str, line_range: list[int] | None) -> dict[str, Any]:
    """Parse an untrusted URL locally and strip userinfo from any display URL.

    Invalid/non-HTTP(S) targets have no clickable URL. Hostname normalization is
    Python's pinned IDNA codec, without DNS or public-suffix lookup.
    """
    result: dict[str, Any] = {"url": None, "hostname": None, "status": "malformed",
                              "source_field": source_field, "source_line_range": line_range}
    try:
        parsed = urlsplit(value)
        if parsed.scheme.lower() not in {"http", "https"}:
            result["status"] = "unsafe_scheme"
            return result
        host = parsed.hostname
        if not host or any(char.isspace() or ord(char) < 32 for char in value):
            return result
        hostname = host.lower().rstrip(".").encode("idna").decode("ascii")
        if not hostname or any(char in hostname for char in '/\\@<>"'):
            return result
        port = parsed.port  # Validate port even though it does not affect host counts.
        netloc = f"[{hostname}]" if ":" in hostname else hostname
        if port is not None:
            netloc += f":{port}"
        result.update(url=urlunsplit((parsed.scheme.lower(), netloc, parsed.path, parsed.query, parsed.fragment)),
                      hostname=hostname, status="ok")
    except (ValueError, UnicodeError):
        pass
    return result


def _prepare(text: str | None, *, record_id: str, source_field: str,
             text_format: str, language: str, usable: bool) -> Mapping[str, Any]:
    structure = {key: 0 for key in ("removed_quote_spans", "removed_code_spans", "removed_url_spans", "headings", "list_items", "links", "mentions", "paragraphs")}
    segments: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    warnings: set[str] = set()
    source = unicodedata.normalize("NFC", (text or "").replace("\r\n", "\n").replace("\r", "\n"))

    def link(value: str, lines: list[int] | None) -> None:
        links.append(safe_link(value, source_field, lines))
        structure["links"] += 1

    def add_segment(value: str, lines: list[int] | None) -> None:
        normalized = _HORIZONTAL_RE.sub(" ", value).strip()
        if normalized:
            segments.append({"text": normalized, "source_record_id": record_id,
                             "source_field": source_field, "source_line_range": lines,
                             "normalized_start": 0, "normalized_end": len(normalized)})

    def visible(value: str, lines: list[int] | None, buffer: list[str], *, count_url_links: bool = True) -> None:
        excluded = [(start, end, "url", target) for start, end, target in _url_spans(value)]
        excluded.extend((m.start(), m.end(), "mention", "") for m in _MENTION_RE.finditer(value))
        cursor = 0
        for start, end, kind, target in sorted(excluded):
            if start < cursor:
                continue
            buffer.append(value[cursor:start])
            add_segment("".join(buffer), lines)
            buffer.clear()
            if kind == "url":
                if count_url_links:
                    link(target, lines)
                structure["removed_url_spans"] += 1
            else:
                structure["mentions"] += 1
            cursor = end
        buffer.append(value[cursor:])

    def scan_excluded_links(value: str, lines: list[int] | None) -> None:
        for _, _, target in _url_spans(value):
            link(target, lines)

    if usable and text_format == "plain":
        # A blank line separates paragraphs; ordinary single LF is preserved.
        for match in re.finditer(r"(?:[^\n]|\n(?![ \t]*\n))+", source):
            paragraph = match.group()
            start = source.count("\n", 0, match.start())
            lines = [start + 1, start + paragraph.count("\n") + 1]
            before = len(segments)
            buffer: list[str] = []
            visible(paragraph, lines, buffer)
            add_segment("".join(buffer), lines)
            structure["paragraphs"] += int(len(segments) > before)
    elif usable:
        parser = MarkdownIt("commonmark", {"typographer": False, "html": True, "linkify": False})
        # CommonMark may treat '*'/'_' inside a bare URL as formatting. Protect
        # complete scanner spans before parsing so those URL characters cannot
        # leak into prose after emphasis-token splitting. Placeholders contain
        # no Markdown syntax and are checked absent from source. Restoring after
        # parsing preserves the original line maps (URLs contain no newlines).
        url_spans = _url_spans(source)
        prefix = _unused_url_prefix(source) if url_spans else None
        substitutions: dict[str, str] = {}
        protected_parts: list[str] = []
        cursor = 0
        for start, end, target in url_spans:
            # Preserve surrounding emphasis syntax while shielding punctuation
            # inside the address. For nested delimiter runs the closers reverse
            # the opener order. Underscores inside words are not openers.
            opener_start = start
            while opener_start and source[opener_start - 1] in "*_":
                opener_start -= 1
            if opener_start < start:
                markers = source[opener_start:start]
                intraword_underscore = ("_" in markers and opener_start > 0
                                        and source[opener_start - 1].isalnum())
                closing = markers[::-1]
                if not intraword_underscore and target.endswith(closing):
                    target = target[:-len(closing)]
                    end -= len(closing)
            if start > 0 and source[start - 1] == "<" and end < len(source) and source[end] == ">":
                continue  # CommonMark autolinks already protect their contents.
            placeholder = f"{prefix}{len(substitutions)}END"
            protected_parts.extend((source[cursor:start], placeholder))
            substitutions[placeholder] = target
            cursor = end
        protected_parts.append(source[cursor:])
        tokens = parser.parse("".join(protected_parts))
        if substitutions:
            placeholder_re = re.compile(re.escape(prefix) + r"\d+END")
            def restore(value: str) -> str:
                return placeholder_re.sub(lambda match: substitutions.get(match.group(), match.group()), value)
            def restore_token(token: Any) -> None:
                token.content = restore(token.content)
                token.attrs = {key: restore(value) if isinstance(value, str) else value
                               for key, value in token.attrs.items()}
                for child in token.children or []:
                    restore_token(child)
            for token in tokens:
                restore_token(token)
        quote_depth = 0
        for token in tokens:
            lines = [token.map[0] + 1, token.map[1]] if token.map is not None else None
            if token.type == "blockquote_open":
                if quote_depth == 0:
                    structure["removed_quote_spans"] += 1
                quote_depth += 1
                continue
            if token.type == "blockquote_close":
                quote_depth -= 1
                continue
            if token.type == "heading_open":
                structure["headings"] += 1
            elif token.type == "list_item_open":
                structure["list_items"] += 1
            if token.type in {"fence", "code_block"}:
                structure["removed_code_spans"] += 1
                scan_excluded_links(token.content, lines)
                continue
            if token.type == "html_block":
                warnings.add("html_present")
                scan_excluded_links(token.content, lines)
                continue
            if token.type != "inline":
                continue
            children = token.children or []
            if quote_depth:
                # Links remain observable source metadata even inside quotes.
                for child in children:
                    if child.type == "link_open":
                        link(child.attrGet("href") or "", lines)
                    elif child.type == "image":
                        link(child.attrGet("src") or "", lines)
                    elif child.type in {"text", "code_inline"}:
                        # URL autolink labels are handled below by link-depth.
                        pass
                depth = 0
                for child in children:
                    if child.type == "link_open":
                        depth += 1
                    elif child.type == "link_close":
                        depth -= 1
                    elif child.type in {"text", "code_inline"} and not depth:
                        scan_excluded_links(child.content, lines)
                continue
            before = len(segments)
            buffer = []
            link_depth = 0
            for child in children:
                if child.type == "link_open":
                    target = child.attrGet("href") or ""
                    link(target, lines)
                    link_depth += 1
                elif child.type == "link_close":
                    link_depth -= 1
                elif child.type == "text":
                    # A URL printed inside a hyperlink label is excluded prose,
                    # not another destination occurrence. Keep its hard boundary
                    # and descriptive surrounding text, including formatted labels.
                    visible(child.content, lines, buffer, count_url_links=not link_depth)
                elif child.type in {"softbreak", "hardbreak"}:
                    buffer.append("\n")
                elif child.type in {"code_inline", "html_inline", "image"}:
                    add_segment("".join(buffer), lines)
                    buffer.clear()
                    if child.type == "code_inline":
                        structure["removed_code_spans"] += 1
                        if not link_depth:
                            scan_excluded_links(child.content, lines)
                    elif child.type == "html_inline":
                        warnings.add("html_present")
                        if not link_depth:
                            scan_excluded_links(child.content, lines)
                    else:
                        link(child.attrGet("src") or "", lines)
                # Emphasis/strong/link close tokens do not break visible prose.
            add_segment("".join(buffer), lines)
            structure["paragraphs"] += int(len(segments) > before)
    token_offsets = [tokenize(segment["text"]) for segment in segments]
    transformations = (["line_endings_lf_v1", "unicode_nfc_v1",
                        "commonmark_parse_v1" if text_format == "markdown" else "plain_paragraphs_v1",
                        "retained_span_exclusion_v1", "horizontal_whitespace_v1", "lexical_regex_v1"]
                       + (["function_mask_v1"] if language == "en" else [])) if usable else []
    return freeze({"usable": usable, "transformations": transformations, "source_sha256": sha256_bytes(text.encode("utf-8")) if text is not None else None,
                   "segments": segments,
                   "masked_segments": [function_mask(segment["text"]) for segment in segments] if language == "en" else [],
                   "tokens": [[token["normalized"] for token in group] for group in token_offsets],
                   "word_tokens": [[token["normalized"] for token in group if token["kind"] == "word"] for group in token_offsets],
                   "token_offsets": token_offsets, "structure": structure, "links": links,
                   "warnings": sorted(warnings)})


def preprocess(record: Mapping[str, Any], manifest: Mapping[str, Any],
               config: AnalysisConfig) -> Mapping[str, Any]:
    """Return an immutable derived body view with separate optional title view.

    Unavailable/sentinel bodies retain metadata but have no analyzable segments.
    Empty present bodies are usable observations with zero counts downstream.
    """
    language = record.get("language") or manifest.get("default_language") or "und"
    body = record.get("text")
    sentinel = isinstance(body, str) and body.strip() in {"[deleted]", "[removed]"}
    usable = record["status"] == "present" and isinstance(body, str) and not sentinel
    common = {"record_id": record["id"], "text_format": manifest["text_format"], "language": language}
    processed = dict(_prepare(body, source_field="text", usable=usable, **common))
    processed.update({key: record.get(key) for key in ("id", "kind", "subreddit", "created_utc", "edit_state")})
    processed["language"] = language
    processed["warnings"] = sorted(set(processed["warnings"]) | ({"removed_content_sentinel"} if sentinel else set()) |
                                    ({"known_edited_observed_text"} if record.get("edit_state") == "edited" else set()) |
                                    ({"english_specific_methods_not_run"} if language != "en" else set()))
    title = record.get("title")
    processed["title"] = (_prepare(title, source_field="title", usable=True, **common)
                          if record["kind"] == "submission" and title is not None else None)
    return freeze(processed)
