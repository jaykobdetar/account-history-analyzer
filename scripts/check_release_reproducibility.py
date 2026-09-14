#!/usr/bin/env python3
"""Compare complete release artifacts from independent, network-denied processes.

Usage: .venv/bin/python scripts/check_release_reproducibility.py qa

Run only after freezing package source/resources. No truth sidecars are read.
All analyzer outputs live in temporary directories. The durable reproduction
report contains hashes and comparisons; timings, temporary paths and process
receipts are written separately to reproduction_receipts.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

FIXTURES = ('constructed_style_shift', 'edge_cases')
RECEIPTS = {'ingest_receipt.json', 'run_receipt.json'}
REQUIRED = {
    'results.json', 'resolved_config.json', 'method_registry.json',
    'records_features.jsonl', 'windows.jsonl', 'evidence.jsonl', 'report.md', 'report.html',
    'activity_daily.svg', 'activity_hourly.svg', 'eligible_word_volume.svg',
    'surface_features.svg', 'adjacent_distances.svg',
}
VARIANTS = (
    {'name': 'original', 'hash_seed': '1', 'timezone': 'UTC', 'input_order': 'original', 'cwd': 'repository'},
    {'name': 'renamed', 'hash_seed': '9123', 'timezone': 'Asia/Tokyo', 'input_order': 'original', 'cwd': 'unrelated_temporary_directory'},
    {'name': 'reversed', 'hash_seed': '48219', 'timezone': 'Pacific/Honolulu', 'input_order': 'reverse_rows_and_recursive_object_keys', 'cwd': 'another_temporary_directory'},
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode('utf-8')


def reverse_keys(value: Any) -> Any:
    """Change object serialization order without changing list or string values."""
    if isinstance(value, dict):
        return {key: reverse_keys(item) for key, item in reversed(list(value.items()))}
    if isinstance(value, list):
        return [reverse_keys(item) for item in value]
    return value


def inspect_artifacts(directory: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Verify every checksummed file, reject missing/unaccounted-for outputs."""
    manifest_bytes = (directory/'checksums.json').read_bytes()
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict) or not REQUIRED <= manifest.keys():
        raise ValueError('Checksum manifest omits required canonical/export/report/chart artifacts')
    if RECEIPTS & manifest.keys() or 'checksums.json' in manifest:
        raise ValueError('Operational receipts or checksum self-reference entered canonical artifact identity')
    observed = {path.name for path in directory.iterdir()}
    if observed != set(manifest) | RECEIPTS | {'checksums.json'}:
        raise ValueError('Output directory has missing or unaccounted-for files')
    artifacts = {}
    for name, expected in sorted(manifest.items()):
        if not isinstance(name, str) or Path(name).name != name or '\\' in name or name in {'.', '..'}:
            raise ValueError('Unsafe checksummed artifact basename')
        path = directory/name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Checksummed artifact must be a regular nonsymlink file')
        data = path.read_bytes()
        if sha256(data) != expected:
            raise ValueError('Checksum mismatch: '+name)
        artifacts[name] = data
    # checksums.json itself is compared byte-for-byte in addition to its entries.
    artifacts['checksums.json'] = manifest_bytes
    receipts = {name: json.loads((directory/name).read_bytes()) for name in sorted(RECEIPTS)}
    if receipts['run_receipt.json'].get('network_isolation') != 'linux_seccomp_socket_denial':
        raise ValueError('Analyzer receipt did not confirm inherited seccomp network denial')
    return artifacts, receipts


def run(repo: Path, destination: Path, python: str, timeout: float) -> bool:
    runner = repo/'scripts/offline_exec.py'
    if not runner.is_file():
        raise ValueError('Repository does not contain scripts/offline_exec.py')
    report: dict[str, Any] = {
        'schema_version': '1.0.0', 'audit': 'release_artifact_reproducibility',
        'status': 'pending', 'scope': 'Actual local reference environment only; no cross-platform byte-identity claim',
        'network_isolation': 'linux_seccomp_socket_denial',
        'comparison': 'Exact bytes of every checksummed artifact plus checksums.json',
        'excluded_operational_receipts': sorted(RECEIPTS), 'truth_sidecars_read': False,
        'fixtures': [], 'operational_receipts': 'reproduction_receipts.json',
    }
    receipts: dict[str, Any] = {
        'schema_version': '1.0.0', 'audit': 'release_artifact_reproducibility',
        'python_executable': python, 'driver_python': platform.python_version(),
        'host_platform': platform.platform(), 'runs': [],
    }
    success = True
    fingerprint = None
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='ahas-release-repro-') as temporary:
        work = Path(temporary)
        for fixture in FIXTURES:
            records = repo/'fixtures'/f'{fixture}.jsonl'
            manifest = repo/'fixtures'/f'{fixture}.snapshot.json'
            source_bytes, manifest_bytes = records.read_bytes(), manifest.read_bytes()
            summary: dict[str, Any] = {
                'fixture': fixture, 'status': 'passed',
                'original_input_sha256': sha256(source_bytes), 'original_manifest_sha256': sha256(manifest_bytes),
                'runs': [],
            }
            baseline: dict[str, bytes] | None = None
            for variant in VARIANTS:
                folder = work/fixture/variant['name']
                folder.mkdir(parents=True)
                output = folder/'analysis'
                cwd = repo if variant['cwd'] == 'repository' else folder/'unrelated-cwd'
                cwd.mkdir(parents=True, exist_ok=True)
                if variant['name'] == 'original':
                    input_path, manifest_path = records, manifest
                else:
                    input_path, manifest_path = folder/'neutral-source-17.jsonl', folder/'neutral-metadata-29.json'
                    if variant['name'] == 'renamed':
                        input_path.write_bytes(source_bytes)
                        manifest_path.write_bytes(manifest_bytes)
                    else:
                        rows = [json.loads(line) for line in source_bytes.splitlines() if line.strip()]
                        input_path.write_text(''.join(json.dumps(reverse_keys(row), ensure_ascii=True,
                            separators=(', ', ': '))+'\n' for row in reversed(rows)), encoding='utf-8')
                        manifest_path.write_text(json.dumps(reverse_keys(json.loads(manifest_bytes)),
                            ensure_ascii=True, indent=3)+'\n', encoding='utf-8')
                argv = [python, str(runner), python, '-m', 'account_history_analyzer', 'analyze',
                        '--input', str(input_path), '--manifest', str(manifest_path), '--out', str(output)]
                environment = dict(os.environ, PYTHONHASHSEED=variant['hash_seed'], TZ=variant['timezone'])
                operational = {'fixture': fixture, 'variant': variant['name'], 'argv': argv,
                               'cwd': str(cwd), 'environment_overrides': {
                                   'PYTHONHASHSEED': variant['hash_seed'], 'TZ': variant['timezone']}}
                result = {**variant, 'status': 'failed', 'checksummed_artifact_count': None,
                          'compared_artifact_count': None, 'artifact_sha256': {},
                          'byte_identical_to_original': None, 'mismatched_artifacts': [], 'error': None}
                tick = time.perf_counter()
                print(f'Running {fixture}: {variant["name"]}', flush=True)
                try:
                    completed = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True,
                                               text=True, check=False, timeout=timeout)
                    operational.update(returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
                    if completed.returncode != 0:
                        raise ValueError(f'Analyzer process exited {completed.returncode}')
                    status = json.loads(completed.stdout)
                    if status.get('status') != 'complete':
                        raise ValueError('Analyzer did not report complete output')
                    artifacts, output_receipts = inspect_artifacts(output)
                    operational['analyzer_receipts'] = output_receipts
                    analytical = json.loads(artifacts['results.json'])
                    current = analytical['analysis']['implementation_fingerprint']
                    if fingerprint is not None and fingerprint != current:
                        raise ValueError('Package implementation changed during the release audit')
                    fingerprint = current
                    if variant['name'] == 'original':
                        baseline = artifacts
                        summary['reference_environment'] = analytical['analysis']['reference_environment']
                        summary['implementation_fingerprint'] = current
                        summary['canonical_snapshot_sha256'] = analytical['snapshot']['canonical_sha256']
                        summary['analysis_config_sha256'] = analytical['analysis']['config_sha256']
                    if baseline is None:
                        raise ValueError('No successful original run exists for comparison')
                    mismatches = sorted(name for name in artifacts.keys() | baseline.keys()
                                        if artifacts.get(name) != baseline.get(name))
                    result.update(status='passed' if not mismatches else 'failed',
                                  checksummed_artifact_count=len(artifacts)-1, compared_artifact_count=len(artifacts),
                                  artifact_sha256={name: sha256(data) for name, data in sorted(artifacts.items())},
                                  byte_identical_to_original=not mismatches, mismatched_artifacts=mismatches)
                except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
                    # Detailed paths/errors belong in operational receipts; the
                    # result records a stable failure class rather than success.
                    operational['exception'] = str(exc)
                    result['error'] = type(exc).__name__
                operational['elapsed_seconds'] = time.perf_counter()-tick
                receipts['runs'].append(operational)
                summary['runs'].append(result)
                if result['status'] != 'passed':
                    summary['status'] = 'failed'
                    success = False
                print(f'{fixture} {variant["name"]}: {result["status"]}', flush=True)
            report['fixtures'].append(summary)
    receipts['elapsed_seconds'] = time.perf_counter()-started
    report['status'] = 'passed' if success else 'failed'
    report['analyzer_process_count'] = sum(len(item['runs']) for item in report['fixtures'])
    destination.mkdir(parents=True, exist_ok=True)
    (destination/'reproduction_receipts.json').write_bytes(canonical(receipts))
    (destination/'reproduction.json').write_bytes(canonical(report))
    print(json.dumps({'status': report['status'], 'report': str(destination/'reproduction.json'),
                      'processes': report['analyzer_process_count']}), flush=True)
    return success


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target_dir', type=Path, help='Directory receiving reproduction.json and separate operational receipts')
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--python', default=sys.executable, help='Installed reference Python executable')
    parser.add_argument('--timeout', type=float, default=300, help='Timeout in seconds for each analyzer process')
    parser.add_argument('--overwrite', action='store_true', help='Replace a prior reproduction audit')
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    destination = args.target_dir.absolute()
    if not args.overwrite and any((destination/name).exists() for name in ('reproduction.json','reproduction_receipts.json')):
        parser.error('A prior audit exists; use --overwrite to replace it')
    # Preserve a virtualenv executable symlink: resolving it would accidentally
    # invoke the base interpreter and lose the installed reference environment.
    selected = shutil.which(args.python)
    if selected is None:
        parser.error('--python executable is unavailable')
    python = str(Path(selected).absolute())
    return 0 if run(args.repo.resolve(), destination, python, args.timeout) else 1


if __name__ == '__main__':
    raise SystemExit(main())
