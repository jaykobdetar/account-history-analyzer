"""Versioned artifact bounds, independent of the supplied-history input budget."""
from __future__ import annotations

from collections.abc import Mapping, Iterator
from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

from .errors import InputError, LimitError
from .io import parse_json

ARTIFACT_POLICY = 'bounded_artifact_envelope_v1'
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_FILES = 32
METADATA_BYTES = 1024 * 1024
CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class ArtifactLimits:
    """Configured limits may tighten, never raise, the supported release envelope."""
    max_file_bytes: int = MAX_FILE_BYTES
    max_total_bytes: int = MAX_TOTAL_BYTES
    max_files: int = MAX_FILES

    def __post_init__(self) -> None:
        for key, ceiling in (('max_file_bytes', MAX_FILE_BYTES), ('max_total_bytes', MAX_TOTAL_BYTES), ('max_files', MAX_FILES)):
            value = getattr(self, key)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise InputError(f'artifacts.{key} must be in [1,{ceiling}]', code='invalid_artifact_limit')

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> ArtifactLimits:
        return cls(**config.get('artifacts', {}))

    def check(self, name: str, size: int, total: int, count: int) -> None:
        if size > self.max_file_bytes:
            raise LimitError(f'{name} exceeds artifact file budget {self.max_file_bytes}', code='artifact_file_byte_limit')
        if total > self.max_total_bytes:
            raise LimitError(f'Artifact directory exceeds byte budget {self.max_total_bytes}', code='artifact_total_byte_limit')
        if count > self.max_files:
            raise LimitError(f'Artifact directory exceeds file budget {self.max_files}', code='artifact_file_count_limit')


def _validate_read_budget(max_bytes: int) -> None:
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_FILE_BYTES:
        raise InputError(f'Artifact reader budget must be in [1,{MAX_FILE_BYTES}]', code='invalid_artifact_limit')


def file_digest(path: str | Path, *, max_bytes: int = MAX_FILE_BYTES) -> str:
    """Hash bounded file chunks rather than materializing another artifact copy."""
    _validate_read_budget(max_bytes)
    if Path(path).stat().st_size > max_bytes:
        raise LimitError(f'{Path(path).name} exceeds artifact file budget {max_bytes}', code='artifact_file_byte_limit')
    digest = hashlib.sha256()
    total = 0
    with Path(path).open('rb') as handle:
        while chunk := handle.read(min(CHUNK_BYTES, max_bytes - total + 1)):
            total += len(chunk)
            if total > max_bytes:
                raise LimitError(f'{Path(path).name} exceeds artifact file budget {max_bytes}', code='artifact_file_byte_limit')
            digest.update(chunk)
    return digest.hexdigest()


def read_artifact_bytes(path: str | Path, *, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    """Bound before allocating; retain a second check if a file grows during read."""
    _validate_read_budget(max_bytes)
    path = Path(path)
    if path.stat().st_size > max_bytes:
        raise LimitError(f'{path.name} exceeds artifact file budget {max_bytes}', code='artifact_file_byte_limit')
    with path.open('rb') as handle:
        data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise LimitError(f'{path.name} exceeds artifact file budget {max_bytes}', code='artifact_file_byte_limit')
    return data


def load_artifact_json(path: str | Path, *, max_bytes: int = MAX_FILE_BYTES) -> Any:
    return parse_json(read_artifact_bytes(path, max_bytes=max_bytes), str(path))


def iter_artifact_jsonl(path: str | Path, *, max_bytes: int = MAX_FILE_BYTES) -> Iterator[Any]:
    """Strict JSONL one row at a time, with a bound on the entire file."""
    _validate_read_budget(max_bytes)
    path = Path(path)
    if path.stat().st_size > max_bytes:
        raise LimitError(f'{path.name} exceeds artifact file budget {max_bytes}', code='artifact_file_byte_limit')
    total = 0
    with path.open('rb') as handle:
        while line := handle.readline(max_bytes - total + 1):
            total += len(line)
            if total > max_bytes:
                raise LimitError(f'{path.name} exceeds artifact file budget {max_bytes}', code='artifact_file_byte_limit')
            yield parse_json(line, str(path))
