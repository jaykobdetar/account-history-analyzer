"""Offline schema validation against the installed external contracts.

Defaults are annotations only. Ingestion and configuration explicitly expand them.
The bundled contracts contain only local references; remote retrieval is forbidden.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import datetime
from functools import lru_cache
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry
from referencing.exceptions import NoSuchResource

from .errors import InputError

_FORMAT_CHECKER = FormatChecker()


@_FORMAT_CHECKER.checks("date-time", raises=(ValueError, TypeError))
def _utc_datetime(value: Any) -> bool:
    # jsonschema's optional date-time dependency is not always installed. Supply
    # the complete V1 date-time check explicitly, independent of that extra.
    if not isinstance(value, str):
        return True
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z", value) is None:
        return False
    datetime.fromisoformat(value[:-1] + "+00:00")
    return True


def _deny_remote(uri: str) -> Any:
    raise NoSuchResource(ref=uri)


@lru_cache(maxsize=32)
def load_schema(name: str) -> dict[str, Any]:
    """Read a named, bundled schema without accessing the network or current cwd."""
    filename = name if name.endswith(".schema.json") else f"{name}.schema.json"
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise InputError("Expected a bundled schema name", code="invalid_schema_name")
    resource = files("account_history_analyzer").joinpath("contracts", filename)
    try:
        schema = json.loads(resource.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InputError(f"Bundled schema unavailable: {filename}", code="missing_schema") from exc
    Draft202012Validator.check_schema(schema)
    return schema


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def validate(instance: Any, schema_name: str, location: str = "input") -> None:
    """Validate a complete supplied object, including date-time format checks.

    Raises :class:`InputError` with the first deterministically ordered violation.
    Immutable internal mappings and tuples are accepted as JSON objects/arrays.
    """
    validator = Draft202012Validator(
        load_schema(schema_name), format_checker=_FORMAT_CHECKER,
        registry=Registry(retrieve=_deny_remote),
    )
    errors = sorted(validator.iter_errors(_plain(instance)), key=lambda e: (str(list(e.absolute_path)), e.message))
    if errors:
        error = errors[0]
        suffix = "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path)
        raise InputError(error.message, code="schema_validation", location=f"{location}{suffix}")
