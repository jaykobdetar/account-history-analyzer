#!/usr/bin/env python3
"""Measure the complete default benchmark lifecycle in separate offline processes.

Timing and host details are operational receipts, never analytical results.
Run through scripts/offline_exec.py after freezing package code/resources.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

PRESENTATIONS = ('report.md', 'report.html', 'activity_daily.svg', 'activity_hourly.svg',
                 'eligible_word_volume.svg', 'surface_features.svg', 'adjacent_distances.svg')


def equal_files(left: Path, right: Path) -> bool:
    with left.open('rb') as a, right.open('rb') as b:
        while True:
            x, y = a.read(65536), b.read(65536)
            if x != y:
                return False
            if not x:
                return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--receipts', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('AHAS_NETWORK_ISOLATION') != 'linux_seccomp_socket_denial':
        parser.error('Run under scripts/offline_exec.py')
    root = Path(__file__).resolve().parents[1]
    destination, receipts = args.out.resolve(), args.receipts.resolve()
    receipts.mkdir(parents=True, exist_ok=True)
    source, manifest = root/'benchmarks/input/records.jsonl', root/'benchmarks/input/snapshot.json'
    shared = ['--input', str(source), '--manifest', str(manifest)]
    stages = [
        ('analyze', ['analyze', *shared, '--out', str(destination)]),
        ('verify', ['verify', *shared, '--analysis-dir', str(destination)]),
        ('recompute', ['verify', *shared, '--analysis-dir', str(destination), '--recompute']),
        ('render', ['render', '--results', str(destination/'results.json'), '--artifacts', str(destination),
                    '--format', 'both', '--excerpts', 'included', '--out', str(receipts/'rerender')]),
    ]
    report = {'scope': 'Complete supplied 1,000-record workload, all default analysis modules and sensitivity views',
              'network_isolation': os.environ['AHAS_NETWORK_ISOLATION'], 'truth_sidecars_read': False,
              'host_platform': platform.platform(), 'driver_python': platform.python_version(),
              'input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
              'stages': [], 'presentation_exact_bytes': {}, 'status': 'failed'}
    for name, arguments in stages:
        command = [args.python, '-m', 'account_history_analyzer', *arguments]
        timing = receipts/f'benchmark-{name}-time.json'
        argv = ['/usr/bin/time', '-f', '{"elapsed_seconds":%e,"peak_rss_kib":%M,"user_seconds":%U,"system_seconds":%S,"exit_code":%x}',
                '-o', str(timing), *command]
        start = time.perf_counter()
        process = subprocess.run(argv, capture_output=True, text=True, timeout=900)
        (receipts/f'benchmark-{name}.stdout').write_text(process.stdout)
        (receipts/f'benchmark-{name}.stderr').write_text(process.stderr)
        measure = json.loads(timing.read_text().splitlines()[-1])
        report['stages'].append({'stage': name, 'argv': argv, 'exit_code': process.returncode,
                                 'driver_elapsed_seconds': time.perf_counter()-start, **measure})
        print(json.dumps(report['stages'][-1], sort_keys=True), flush=True)
        (receipts/'benchmark-lifecycle-receipt.json').write_text(json.dumps(report, sort_keys=True, indent=2)+'\n')
        if process.returncode:
            return 1
    checks = json.loads((destination/'checksums.json').read_bytes())
    report['artifact_bytes'] = {p.name: p.stat().st_size for p in sorted(destination.iterdir())}
    report['total_artifact_bytes'] = sum(report['artifact_bytes'].values())
    report['canonical_checksums'] = checks
    # Parsing is bounded by the already successful verifier, after child peak RSS is measured.
    result = json.loads((destination/'results.json').read_bytes())
    report['implementation_fingerprint'] = result['analysis']['implementation_fingerprint']
    report['reuse_resource_usage'] = result['modules']['reuse']['payload']['resource_usage']
    report['reuse_budget_complete'] = result['modules']['reuse']['payload']['budget_complete']
    report['presentation_exact_bytes'] = {name: equal_files(destination/name, receipts/'rerender'/name) for name in PRESENTATIONS}
    recomputation = json.loads((receipts/'benchmark-recompute.stdout').read_text())
    report['recompute_scope'] = recomputation['verification_scope']
    report['reproduced_artifacts'] = recomputation['reproduced_artifacts']
    report['status'] = 'passed' if all(report['presentation_exact_bytes'].values()) and report['reuse_budget_complete'] else 'failed'
    (receipts/'benchmark-lifecycle-receipt.json').write_text(json.dumps(report, sort_keys=True, indent=2)+'\n')
    return int(report['status'] != 'passed')


if __name__ == '__main__':
    raise SystemExit(main())
