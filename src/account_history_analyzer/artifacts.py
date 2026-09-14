"""Atomic artifact publication and independent integrity checking."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Callable, Iterable
import os
import hashlib
import io
import re
import platform
import resource
import shutil
import tempfile
import time

from .errors import InputError, IntegrityError
from .artifact_io import ArtifactLimits, METADATA_BYTES, file_digest, load_artifact_json, read_artifact_bytes
from .io import Snapshot, canonical_bytes, canonical_chunks, digest, parse_json, sha256_bytes


@dataclass(frozen=True)
class AnalysisResult:
    """Immutable complete in-memory analysis and named deterministic artifacts.

    `receipt` is operational and excluded from canonical identity. Normal missing
    data stays in module statuses; resource limits produce a partial result.
    """
    results: Mapping[str, Any]
    files: Mapping[str, bytes]
    ingest_receipt: Mapping[str, Any]
    run_receipt: Mapping[str, Any]
    exit_code: int = 0


def jsonl_bytes(rows: list | tuple) -> bytes:
    return b''.join(canonical_bytes(row) for row in rows)


def publish_files(files: Mapping[str, bytes | Callable[[], Iterable[bytes]]], output_dir: str | Path, *, overwrite: bool = False,
                  limits: ArtifactLimits | None = None, _add_checksums: bool = False) -> None:
    """Stage a complete directory then rename; never publish a success marker early.

    Existing nonempty directories require explicit overwrite. A symlink target is
    rejected. Artifact names must be single fixed basenames, never supplied IDs.
    """
    limits = limits or ArtifactLimits()
    limits.check("", 0, 0, len(files) + int(_add_checksums))
    out = Path(output_dir).absolute()
    if any(p.is_symlink() for p in (out, *out.parents)):
        raise InputError('Output directory and ancestors must not be symlinks', code='unsafe_output_path')
    out = out.resolve()
    current = Path.cwd().resolve()
    if out == Path(out.anchor) or out == current or out in current.parents:
        raise InputError('Output must be a dedicated directory', code='unsafe_output_path')
    if out.exists() and not out.is_dir():
        raise InputError('Output path is not a directory', code='unsafe_output_path')
    if out.exists() and any(out.iterdir()) and not overwrite:
        raise InputError('Output directory is nonempty; use --overwrite', code='output_exists')
    for name in files:
        if Path(name).name != name or name in {'.', '..'} or '\\' in name:
            raise InputError('Artifact name is not a safe basename', code='unsafe_artifact_path')
    out.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.ahas-staging-', dir=out.parent))
    backup: Path | None = None
    try:
        total = 0
        hashes = {}

        def write(name, source):
            nonlocal total
            size = 0
            digest = hashlib.sha256()
            chunks = (source,) if isinstance(source, bytes) else source()
            with (staging / name).open('xb') as handle:
                for chunk in chunks:
                    if not isinstance(chunk, bytes):
                        raise TypeError('Artifact chunks must be bytes')
                    size += len(chunk)
                    total += len(chunk)
                    limits.check(name, size, total, len(files) + int(_add_checksums))
                    if name in {'checksums.json', 'resolved_config.json'} and size > METADATA_BYTES:
                        from .errors import LimitError
                        raise LimitError(f'{name} exceeds metadata budget {METADATA_BYTES}', code='artifact_metadata_byte_limit')
                    handle.write(chunk)
                    digest.update(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            return digest.hexdigest()

        for name, source in sorted(files.items(), key=lambda item: (item[0] == 'checksums.json', item[0])):
            checksum = write(name, source)
            if name not in {'ingest_receipt.json', 'run_receipt.json'}:
                hashes[name] = checksum
        if _add_checksums:
            write('checksums.json', canonical_bytes(hashes))
        if out.exists():
            backup = Path(tempfile.mkdtemp(prefix='.ahas-previous-', dir=out.parent))
            backup.rmdir()
            out.rename(backup)
        staging.rename(out)
    except BaseException:
        if backup is not None and backup.exists() and not out.exists():
            backup.rename(out)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    if backup is not None:
        shutil.rmtree(backup)


def write_artifacts(result: AnalysisResult, output_dir: str | Path, *, overwrite: bool = False) -> None:
    """Publish complete bounded artifacts; stream the large result without copies."""
    from .reporting import render_markdown, render_html
    from .charts import render_charts
    files = dict(result.files)
    resolved = parse_json(files['resolved_config.json'])
    limits = ArtifactLimits.from_config(resolved)
    files['results.json'] = lambda: canonical_chunks(result.results)
    # Byte exports already exist at this immutable stage; parse one line at a
    # time instead of materializing another list of every encoded line.
    evidence = [parse_json(line) for line in io.BytesIO(files['evidence.jsonl'])]
    windows = [parse_json(line) for line in io.BytesIO(files['windows.jsonl'])]
    files.update(render_charts(result.results, windows))
    excerpt_mode = resolved['report']['excerpts']
    files['report.md'] = render_markdown(result.results, evidence, excerpts=excerpt_mode, windows=windows).encode('utf-8')
    files['report.html'] = render_html(result.results, evidence, excerpts=excerpt_mode, windows=windows).encode('utf-8')
    files['ingest_receipt.json'] = canonical_bytes(result.ingest_receipt)
    files['run_receipt.json'] = canonical_bytes(result.run_receipt)
    publish_files(files, output_dir, overwrite=overwrite, limits=limits, _add_checksums=True)


def safe_artifact(directory: Path, name: str) -> Path:
    if not isinstance(name, str) or Path(name).name != name or '\\' in name or name in {'.', '..'}:
        raise IntegrityError('Unsafe artifact path', code='unsafe_artifact_path')
    path = directory / name
    if path.is_symlink() or not path.is_file() or path.resolve().parent != directory.resolve():
        raise IntegrityError(f'Missing/unsafe artifact {name}', code='missing_artifact')
    return path


def inspect_artifacts(directory: str | Path, snapshot: Snapshot | None = None):
    """Verify once and return parsed results for render/replay without reloading.

    Hard release ceilings are applied before trusting the stored tighter policy.
    Receipts are bounded but not trusted as analytical data or resource paths.
    """
    from .schemas import validate
    root = Path(directory)
    checks = load_artifact_json(safe_artifact(root, 'checksums.json'), max_bytes=METADATA_BYTES)
    required = {'results.json', 'resolved_config.json', 'method_registry.json', 'records_features.jsonl',
                'windows.jsonl', 'evidence.jsonl', 'report.md', 'report.html', 'activity_daily.svg',
                'activity_hourly.svg', 'eligible_word_volume.svg', 'surface_features.svg', 'adjacent_distances.svg'}
    if not isinstance(checks, dict) or not required <= checks.keys():
        raise IntegrityError('Incomplete checksum manifest', code='incomplete_artifacts')
    if 'checksums.json' in checks or {'ingest_receipt.json', 'run_receipt.json'} & checks.keys():
        raise IntegrityError('Checksums cannot include themselves or operational receipts', code='invalid_checksum_manifest')
    hard = ArtifactLimits()
    names = [*checks, 'checksums.json'] + [name for name in ('ingest_receipt.json','run_receipt.json') if (root/name).exists() or (root/name).is_symlink()]
    total = 0
    for name in names:
        size = safe_artifact(root, name).stat().st_size
        total += size
        hard.check(name, size, total, len(names))
    resolved = load_artifact_json(safe_artifact(root, 'resolved_config.json'), max_bytes=METADATA_BYTES)
    limits = ArtifactLimits.from_config(resolved)
    total = 0
    for name in names:
        size = safe_artifact(root, name).stat().st_size
        total += size
        limits.check(name, size, total, len(names))
    for name, expected in sorted(checks.items()):
        if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
            raise IntegrityError('Malformed SHA-256 in checksum manifest', code='invalid_checksum_manifest')
        if file_digest(safe_artifact(root, name), max_bytes=limits.max_file_bytes) != expected:
            raise IntegrityError(f'Artifact checksum mismatch: {name}', code='artifact_mismatch')
    result = load_artifact_json(safe_artifact(root, 'results.json'), max_bytes=limits.max_file_bytes)
    validate(result, 'results', location='results')
    for name, meta in sorted(result['artifacts'].items()):
        if checks.get(meta['relative_path']) != meta['sha256']:
            raise IntegrityError(f'Result artifact mismatch: {name}', code='artifact_mismatch')
    if digest(resolved) != result['analysis']['config_sha256']:
        raise IntegrityError('Configuration identity mismatch', code='config_mismatch')
    if snapshot is not None and snapshot.canonical_sha256 != result['snapshot']['canonical_sha256']:
        raise IntegrityError('Supplied snapshot mismatch', code='snapshot_mismatch')
    summary = {'status': 'integrity_only', 'checked_artifacts': len(checks),
               'results_sha256': checks['results.json'], 'verification_scope': 'artifact_checksums_and_supplied_identities'}
    return summary, result, checks, limits


def verify_artifacts(directory: str | Path, snapshot: Snapshot | None = None) -> dict[str, Any]:
    """Check bounded local checksums; no authenticity or reproduction claim."""
    return inspect_artifacts(directory, snapshot)[0]
