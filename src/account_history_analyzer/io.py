"""Strict local JSON ingestion and deterministic immutable snapshot boundaries."""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .errors import InputError, LimitError
from .schemas import validate

_TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z\Z")
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_INPUT_DEFAULTS = {"max_unique_records": 10000, "max_text_codepoints": 200000, "max_input_bytes": 52428800, "strict": True}
_RECORD_DEFAULTS = {
    "created_utc": None, "subreddit": None, "language": None, "edit_state": "unknown",
    "edited_utc": None, "title": None, "parent_id": None, "thread_id": None,
    "parent_created_utc": None, "permalink": None,
}


def freeze(value: Any) -> Any:
    """Recursively copy JSON data into immutable mappings/tuples."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(freeze(item) for item in value)
    return value


def thaw(value: Any) -> Any:
    """Copy immutable JSON data to ordinary JSON-compatible containers."""
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [thaw(item) for item in value]
    return value


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("Canonical JSON object keys must be strings")
        return {key: _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Canonical JSON cannot contain NaN or Infinity")
        return 0.0 if value == 0.0 else value
    return value


def canonical_bytes(value: Any) -> bytes:
    """UTF-8 sorted compact JSON with finite numbers, positive zero and final LF."""
    return (json.dumps(_canonical_value(value), ensure_ascii=False, allow_nan=False,
                       sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def canonical_chunks(value: Any, *, chunk_bytes: int = 65536):
    """Stream bytes identical to canonical_bytes without copying the JSON tree.

    Used for large artifact publication/replay. Only the current scalar and a
    bounded output buffer are encoded at once; input mappings/arrays are read
    directly, including immutable stage objects. Array order is never changed.
    """
    if type(chunk_bytes) is not int or chunk_bytes < 1:
        raise ValueError("chunk_bytes must be a positive integer")

    def tokens(item):
        if isinstance(item, Mapping):
            if not all(isinstance(key, str) for key in item):
                raise ValueError("Canonical JSON object keys must be strings")
            yield "{"
            for index, key in enumerate(sorted(item)):
                if index:
                    yield ","
                yield json.dumps(key, ensure_ascii=False)
                yield ":"
                yield from tokens(item[key])
            yield "}"
        elif isinstance(item, (tuple, list)):
            yield "["
            for index, child in enumerate(item):
                if index:
                    yield ","
                yield from tokens(child)
            yield "]"
        else:
            if isinstance(item, float) and item == 0:
                item = 0.0
            yield json.dumps(item, ensure_ascii=False, allow_nan=False, separators=(",", ":"))

    buffer = bytearray()
    for token in tokens(value):
        data = token.encode("utf-8")
        for start in range(0, len(data), chunk_bytes):
            part = data[start:start + chunk_bytes]
            room = chunk_bytes - len(buffer)
            buffer.extend(part[:room])
            if len(buffer) == chunk_bytes:
                yield bytes(buffer)
                buffer.clear()
            buffer.extend(part[room:])
    buffer.extend(b"\n")
    if buffer:
        yield bytes(buffer)


def canonical_digest(value: Any) -> str:
    """SHA-256 over streaming canonical bytes, preserving the existing format."""
    result = hashlib.sha256()
    for chunk in canonical_chunks(value):
        result.update(chunk)
    return result.hexdigest()


def sha256_bytes(value: bytes) -> str:
    """Return lowercase SHA-256 for supplied bytes, without normalizing them."""
    return hashlib.sha256(value).hexdigest()


def digest(value: Any) -> str:
    """SHA-256 of :func:`canonical_bytes`."""
    return sha256_bytes(canonical_bytes(value))


def epoch_us(value: str) -> int:
    """Parse specified UTC timestamps to exact signed integer epoch microseconds.

    No local timezone, floating point timestamp, current date, or leap-second guess
    is involved. Missing timestamps are represented as None by callers.
    """
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        raise InputError("Expected RFC3339 UTC ending in Z with at most six fractional digits", code="invalid_timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise InputError("Invalid calendar timestamp", code="invalid_timestamp") from exc
    delta = parsed - _EPOCH
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"Duplicate object key {key!r}", code="duplicate_json_key")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise InputError(f"Nonfinite JSON number {value}", code="nonfinite_json_number")


def _check_json_values(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise InputError("Overflowing/nonfinite JSON number", code="nonfinite_json_number")
    if isinstance(value, str) and any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise InputError("Lone Unicode surrogate is not a Unicode scalar value", code="invalid_unicode")
    if isinstance(value, dict):
        for key, item in value.items():
            _check_json_values(key)
            _check_json_values(item)
    elif isinstance(value, list):
        for item in value:
            _check_json_values(item)


def parse_json(text: str | bytes, location: str = "input") -> Any:
    """Strict JSON decoding: duplicate keys, nonfinite values and invalid UTF-8 fail."""
    try:
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        value = json.loads(text, object_pairs_hook=_unique_keys, parse_constant=_nonfinite)
        _check_json_values(value)
        return value
    except InputError as exc:
        raise InputError(exc.message, code=exc.code, location=location) from exc
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise InputError(str(exc), code="invalid_json", location=location) from exc


def _read_bounded(path: str | Path, max_bytes: int) -> bytes:
    try:
        with Path(path).open("rb") as handle:
            data = handle.read(max_bytes + 1)
    except OSError as exc:
        raise InputError(str(exc), code="input_file_error", location=str(path)) from exc
    if len(data) > max_bytes:
        raise LimitError(f"Input exceeds available byte budget {max_bytes}", code="input_byte_limit", location=str(path))
    return data


def load_json(path: str | Path, max_bytes: int = 52428800) -> Any:
    """Read a bounded strict local JSON document; paths are never interpreted as URLs."""
    return parse_json(_read_bounded(path, max_bytes), str(path))


def _check_interval(value: Mapping[str, Any], location: str) -> None:
    start = epoch_us(value["start_utc"]) if value.get("start_utc") is not None else None
    end = epoch_us(value["end_utc"]) if value.get("end_utc") is not None else None
    if start is not None and end is not None and start > end:
        raise InputError("Interval start must not follow end", code="inverted_interval", location=location)


def _manifest(value: Any) -> dict[str, Any]:
    validate(value, "snapshot", "manifest")
    manifest = {"capture_utc": None, "source_notes": "", "license_notes": None, **value}
    coverage = {"start_utc": None, "end_utc": None, "known_gaps": [], "notes": "", **manifest["coverage"]}
    _check_interval(coverage, "manifest.coverage")
    gaps = []
    for index, gap in enumerate(coverage["known_gaps"]):
        _check_interval(gap, f"manifest.coverage.known_gaps[{index}]")
        gaps.append({"note": "", **gap})
    coverage["known_gaps"] = sorted(gaps, key=lambda g: (epoch_us(g["start_utc"]), epoch_us(g["end_utc"]), g["note"]))
    manifest["coverage"] = coverage
    if manifest["capture_utc"] is not None:
        epoch_us(manifest["capture_utc"])
    return manifest


def record_sort_key(record: Mapping[str, Any]) -> tuple[bool, int, str]:
    """Stable supplied-event order; missing timestamps sort last by opaque ID."""
    created = record["created_utc"]
    return (created is None, 0 if created is None else epoch_us(created), record["id"])


@dataclass(frozen=True)
class Snapshot:
    """Validated immutable records and manifest plus separate operational receipt.

    Warnings contain stable reason codes and existing supplied record IDs. They are
    analytical limitations, whereas duplicate-line counts exist only in receipt.
    """

    records: tuple[Mapping[str, Any], ...]
    manifest: Mapping[str, Any]
    canonical_sha256: str
    receipt: Mapping[str, Any]
    warnings: tuple[Mapping[str, Any], ...]


def _parent_warnings(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {record["id"]: record for record in records}
    warnings = []
    for record in records:
        parent = by_id.get(record["parent_id"])
        supplied_time = record["parent_created_utc"]
        created = record["created_utc"]
        if parent is not None:
            internal_time = parent["created_utc"]
            if internal_time is not None and supplied_time is not None and epoch_us(internal_time) != epoch_us(supplied_time):
                raise InputError("Supplied parent timestamp contradicts internal parent record", code="internal_parent_timestamp_conflict", location=record["id"])
            effective_time = internal_time if internal_time is not None else supplied_time
            if created is not None and effective_time is not None and epoch_us(created) < epoch_us(effective_time):
                raise InputError("Child creation precedes supplied internal parent creation", code="internal_parent_after_child", location=record["id"])
        elif created is not None and supplied_time is not None and epoch_us(created) < epoch_us(supplied_time):
            warnings.append({"code": "unverified_external_parent_after_child", "source_record_ids": [record["id"]]})
    # A functional parent graph permits an iterative linear-time cycle walk.
    done: set[str] = set()
    for start in sorted(by_id):
        path: list[str] = []
        seen: dict[str, int] = {}
        current = start
        while current in by_id and current not in done:
            if current in seen:
                warnings.append({"code": "parent_reference_cycle", "source_record_ids": sorted(path[seen[current]:])})
                break
            seen[current] = len(path)
            path.append(current)
            current = by_id[current]["parent_id"]
        done.update(path)
    return warnings


def load_snapshot(records_path: str | Path, manifest_path: str | Path, config: Any = None) -> Snapshot:
    """Load one complete snapshot, rejecting any invalid row before analysis.

    `config` may be an expanded analysis configuration or a mapping with an `input`
    section. Input byte budget covers JSONL and manifest together. Text limits are
    additionally bounded by the external record schema. No truth sidecar is read.
    """
    limits = dict(_INPUT_DEFAULTS)
    if config is not None:
        limits.update(config["input"])
    if limits["strict"] is not True:
        raise InputError("V1 requires strict ingestion", code="strict_required")
    for name in ("max_unique_records", "max_text_codepoints", "max_input_bytes"):
        if not isinstance(limits[name], int) or isinstance(limits[name], bool) or limits[name] <= 0:
            raise InputError(f"{name} must be a positive integer", code="invalid_input_limit")
    raw_manifest = _read_bounded(manifest_path, limits["max_input_bytes"])
    manifest = _manifest(parse_json(raw_manifest, "manifest"))
    raw_input = _read_bounded(records_path, limits["max_input_bytes"] - len(raw_manifest))
    try:
        text = raw_input.decode("utf-8")
    except UnicodeError as exc:
        raise InputError(str(exc), code="invalid_utf8", location="records") from exc
    by_id: dict[str, dict[str, Any]] = {}
    rows = duplicates = 0
    warnings: list[dict[str, Any]] = []
    capture = epoch_us(manifest["capture_utc"]) if manifest["capture_utc"] is not None else None
    # JSONL is separated by LF (optionally preceded by CR), not by arbitrary
    # Unicode line separators that can legitimately occur inside JSON strings.
    physical_lines = text.split("\n") if text else []
    if physical_lines and physical_lines[-1] == "":
        physical_lines.pop()
    for line_number, line in enumerate(physical_lines, 1):
        if not line.strip():
            continue
        rows += 1
        location = f"records line {line_number}"
        value = parse_json(line, location)
        if isinstance(value, dict):
            body = value.get("text")
            if isinstance(body, str) and len(body) > min(limits["max_text_codepoints"], 200000):
                raise LimitError("Record text exceeds Unicode code-point limit", code="text_size_limit", location=location)
            title = value.get("title")
            if isinstance(title, str) and len(title) > min(limits["max_text_codepoints"], 20000):
                raise LimitError("Record title exceeds Unicode code-point limit", code="text_size_limit", location=location)
        validate(value, "record", location)
        record = {**_RECORD_DEFAULTS, **value}
        if record["account_id"] != manifest["account_id"]:
            raise InputError("Record account_id must equal manifest account_id", code="mixed_accounts", location=location)
        for field in ("created_utc", "edited_utc", "parent_created_utc"):
            if record[field] is not None:
                epoch_us(record[field])
        created = epoch_us(record["created_utc"]) if record["created_utc"] is not None else None
        edited = epoch_us(record["edited_utc"]) if record["edited_utc"] is not None else None
        if created is not None and edited is not None and edited < created:
            raise InputError("Known edit precedes creation", code="edit_before_creation", location=location)
        previous = by_id.get(record["id"])
        if previous is not None:
            if previous != record:
                raise InputError("Conflicting versions of the same record ID", code="conflicting_record", location=location)
            duplicates += 1
            continue
        by_id[record["id"]] = record
        if len(by_id) > limits["max_unique_records"]:
            raise LimitError("Unique-record limit exceeded", code="record_count_limit", location=location)
        if record["status"] == "present" and record["text"].strip() in ("[deleted]", "[removed]"):
            warnings.append({"code": "removed_content_sentinel", "source_record_ids": [record["id"]]})
        if record["edit_state"] == "edited":
            warnings.append({"code": "known_edited_observed_text", "source_record_ids": [record["id"]]})
        if capture is not None:
            for field, value_us in (("created_utc", created), ("edited_utc", edited)):
                if value_us is not None and value_us > capture:
                    warnings.append({"code": field.removesuffix("_utc") + "_after_supplied_capture", "source_record_ids": [record["id"]]})
    records = sorted(by_id.values(), key=record_sort_key)
    warnings.extend(_parent_warnings(records))
    warnings.sort(key=lambda item: (item["code"], item["source_record_ids"]))
    identity = {"manifest": manifest, "records": records}
    receipt = {
        "physical_lines": len(physical_lines), "parsed_rows": rows, "duplicate_rows": duplicates,
        "unique_records": len(records), "raw_input_sha256": sha256_bytes(raw_input),
        "raw_manifest_sha256": sha256_bytes(raw_manifest), "raw_input_bytes": len(raw_input),
        "raw_manifest_bytes": len(raw_manifest), "input_path": str(Path(records_path).resolve()),
        "manifest_path": str(Path(manifest_path).resolve()),
    }
    return Snapshot(tuple(freeze(record) for record in records), freeze(manifest), digest(identity), freeze(receipt), tuple(freeze(warning) for warning in warnings))
