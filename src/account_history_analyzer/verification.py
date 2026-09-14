"""Integrity and explicit recomputation, without trusting receipt resource paths."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from .artifacts import safe_artifact, inspect_artifacts, write_artifacts
from .artifact_io import METADATA_BYTES, file_digest, load_artifact_json
import tempfile
from .config import AnalysisConfig, resource_bytes
from .errors import InputError, IntegrityError
from .io import canonical_bytes, digest, load_json, load_snapshot, sha256_bytes, thaw


def config_from_resolved(directory: str | Path) -> tuple[AnalysisConfig, dict | None]:
    """Reconstruct settings using verified bundled identities and local artifact reference.

    Operational receipt paths are never used to read arbitrary resources during
    replay. External references are restored from the verified analysis directory.
    """
    root = Path(directory)
    resolved = load_artifact_json(safe_artifact(root, 'resolved_config.json'), max_bytes=METADATA_BYTES)
    selection = resolved.pop('manual_selection', None)
    for name in ('function_words_resource', 'contraction_pairs_resource'):
        identity = resolved['text'][name]
        if sha256_bytes(resource_bytes(identity['resource_id'])) != identity['sha256']:
            raise IntegrityError('Installed bundled resource differs from analyzed resource', code='resource_mismatch')
        resolved['text'][name] = identity['resource_id']
    reference = resolved['delta']['reference_path']
    if reference is None:
        resolved['delta']['reference_path'] = ''
    else:
        path = safe_artifact(root, 'delta_reference.json')
        if file_digest(path) != reference['sha256']:
            raise IntegrityError('Frozen reference digest mismatch', code='reference_mismatch')
        resolved['delta']['reference_path'] = str(path.resolve())
    return AnalysisConfig.from_mapping(resolved), selection


def verify(input_path: str | Path, manifest_path: str | Path, analysis_dir: str | Path,
           *, recompute: bool = False, config_path: str | Path | None = None) -> dict[str, Any]:
    """Verify artifact and snapshot identities; recompute only when explicitly requested."""
    try:
        checked, expected, checksums, limits = inspect_artifacts(analysis_dir)
        stored_config, selection = config_from_resolved(analysis_dir)
        config = AnalysisConfig.from_toml(config_path) if config_path else stored_config
        analytical = config.analytical()
        if selection is not None:
            analytical['manual_selection'] = selection
        if digest(analytical) != expected['analysis']['config_sha256']:
            raise IntegrityError('Expanded configuration mismatch', code='config_mismatch')
        snapshot = load_snapshot(input_path, manifest_path, config)
        if snapshot.canonical_sha256 != expected['snapshot']['canonical_sha256']:
            raise IntegrityError('Supplied canonical snapshot mismatch', code='snapshot_mismatch')
        if recompute:
            # The stored large result has served its validation purpose. Do not
            # retain a second complete parsed result during the actual analysis.
            del expected
            from .pipeline import analyze
            rerun = analyze(snapshot, config, selection=selection)
            with tempfile.TemporaryDirectory(prefix='ahas-recompute-') as temporary:
                replay = Path(temporary)/'analysis'
                write_artifacts(rerun, replay)
                reproduced = load_artifact_json(replay/'checksums.json', max_bytes=METADATA_BYTES)
                if reproduced != checksums or file_digest(replay/'checksums.json') != file_digest(Path(analysis_dir)/'checksums.json'):
                    raise IntegrityError('Recomputed canonical artifacts differ; inspect implementation/environment/config/template identities', code='reproduction_mismatch')
            checked['status'] = 'reproduced'
            checked['verification_scope'] = 'all_canonical_artifacts'
            checked['reproduced_artifacts'] = sorted([*checksums, 'checksums.json'])
        return checked
    except (InputError, KeyError, TypeError, ValueError, OSError) as exc:
        raise IntegrityError(f'Invalid verification input: {exc}', code='invalid_verification_input') from exc
