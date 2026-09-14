#!/usr/bin/env python3
"""Rerender an explicitly supplied study into a new private destination.

No private source paths, account names or prose are embedded in this public QA
script. Run under scripts/offline_exec.py after freezing the renderer. The old
study is read-only. Stored numerical results are copied exactly, not recomputed;
new renderer identity and operational evidence live in a separate receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from account_history_analyzer import __version__
from account_history_analyzer.artifact_io import iter_artifact_jsonl, load_artifact_json
from account_history_analyzer.artifacts import inspect_artifacts, publish_files, safe_artifact
from account_history_analyzer.charts import render_charts
from account_history_analyzer.io import canonical_bytes, canonical_digest
from account_history_analyzer.pipeline import implementation_identity
from account_history_analyzer.reporting import TEMPLATE_VERSION, render_html, render_markdown


PRESENTATIONS = ('report.md', 'report.html', 'activity_daily.svg', 'activity_hourly.svg',
                 'eligible_word_volume.svg', 'surface_features.svg', 'adjacent_distances.svg')
RENDER_METADATA = ('resolved_config.json', 'method_registry.json')
PRESENTATION_IDENTITY_FIELDS = ('analysis.suite_version', 'analysis.implementation_fingerprint',
                                'analysis.resource_sha256.report_templates')


def sha_file(path: Path) -> str:
    result = hashlib.sha256()
    with path.open('rb') as source:
        while data := source.read(65536):
            result.update(data)
    return result.hexdigest()


def stream_file(path: Path):
    def source():
        with path.open('rb') as handle:
            while data := handle.read(65536):
                yield data
    return source


def study_inventory(study: Path) -> dict[str, str]:
    inventory = {}
    for path in sorted(study.rglob('*')):
        if path.is_symlink():
            raise ValueError('Study contains a symlink; refusing ambiguous preservation audit')
        if path.is_file():
            inventory[str(path.relative_to(study))] = sha_file(path)
    return inventory


def analytical_digest(result) -> str:
    """Exclude exactly three documented presentation-release identity fields.

    Shallow copies preserve the full analytical payload without another large
    deep copy. Configuration, numerical environment, methods, resource identities,
    arrays, findings, artifact links and selected intervals remain in the digest.
    """
    analysis = dict(result['analysis'])
    resources = dict(analysis['resource_sha256'])
    analysis.pop('suite_version')
    analysis.pop('implementation_fingerprint')
    resources.pop('report_templates')
    analysis['resource_sha256'] = resources
    return canonical_digest({**result, 'analysis': analysis})


def selected_interval_digest(result) -> str:
    style = result['modules']['style']['payload']
    sensitivity = style['sensitivity']
    def selected(rows):
        return [{key: row[key] for key in ('stream_id', 'status', 'internal_boundaries', 'boundaries')}
                for row in rows]
    return canonical_digest({
        'primary': selected(style['changes']),
        'penalties': [{'setting_id': setting['setting_id'], 'results': selected(setting['results'])}
                      for setting in sensitivity['penalty_settings']],
        'constructions': [{'setting_id': setting['setting_id'], 'status': setting['status'],
                           'results': selected(setting['results'])}
                          for setting in sensitivity['construction_settings']],
        'same_window_stability': sensitivity['same_window_stability'],
    })


def require(condition, message):
    if not condition:
        raise ValueError(message)


def contained_file(study: Path, relative: str) -> Path:
    path = study / relative
    require(not path.is_symlink() and path.resolve().is_relative_to(study), 'Unsafe study-relative path')
    require(path.is_file(), 'Required study file missing')
    return path


def run_logged(out: Path, receipt: dict, name: str, argv: list[str], *, env=None):
    started = time.perf_counter()
    process = subprocess.run(argv, cwd=out, env=env, capture_output=True)
    for label, content in (('stdout', process.stdout), ('stderr', process.stderr)):
        (out / 'logs' / f'{name}.{label}.log').write_bytes(content)
    row = {'name': name, 'argv': argv, 'cwd': str(out), 'exit_code': process.returncode,
           'elapsed_seconds': time.perf_counter() - started,
           'stdout_sha256': hashlib.sha256(process.stdout).hexdigest(),
           'stderr_sha256': hashlib.sha256(process.stderr).hexdigest()}
    receipt['commands'].append(row)
    return process


def verify_private_presentations(args):
    require(os.environ.get('AHAS_NETWORK_ISOLATION') == 'linux_seccomp_socket_denial',
            'Run this script under scripts/offline_exec.py')
    study = args.study.resolve(strict=True)
    out = args.out.absolute()
    repo = Path(__file__).resolve().parents[1]
    require(study.is_dir() and not args.study.is_symlink(), 'Study must be a real directory')
    require(not any(path.is_symlink() for path in (out, *out.parents)), 'Output ancestry must not contain symlinks')
    out = out.resolve()
    require(not out.exists(), 'Output must be new; historical runs are never overwritten')
    require(not out.is_relative_to(study) and not study.is_relative_to(out), 'Output must be separate from the old study')
    require(not out.is_relative_to(repo) and not repo.is_relative_to(out), 'Private outputs must remain outside the public repository')
    source = study / args.bundle
    require(source.resolve().is_relative_to(study) and source.is_dir(), 'Source bundle must be inside the supplied study')
    original_test = contained_file(study, args.regression)
    before = study_inventory(study)
    out.mkdir(parents=True)
    (out / 'logs').mkdir()
    (out / 'scripts').mkdir()
    receipt = {
        'status': 'failed', 'scope': 'Rerender copied stored analytical results; no numerical recomputation',
        'private_outputs_do_not_publish': True, 'source_study': str(study), 'output_root': str(out),
        'network_isolation': os.environ['AHAS_NETWORK_ISOLATION'], 'commands': [],
        'analytical_projection_excludes_only': list(PRESENTATION_IDENTITY_FIELDS),
        'historical_inventory_sha256_before': canonical_digest(before),
        'historical_file_count_before': len(before),
    }
    try:
        integrity, result, checks, limits = inspect_artifacts(source)
        receipt['original_integrity'] = integrity
        original_digest = analytical_digest(result)
        original_intervals = selected_interval_digest(result)
        receipt['original_results_sha256'] = checks['results.json']
        receipt['original_analytical_identity'] = result['analysis']
        fp, environment, resources = implementation_identity()
        receipt['renderer_identity'] = {'suite_version': __version__, 'template_version': TEMPLATE_VERSION,
                                        'implementation_fingerprint': fp, 'reference_environment': environment,
                                        'resource_sha256': resources}
        evidence = list(iter_artifact_jsonl(safe_artifact(source, 'evidence.jsonl'), max_bytes=limits.max_file_bytes))
        windows = list(iter_artifact_jsonl(safe_artifact(source, 'windows.jsonl'), max_bytes=limits.max_file_bytes))
        charts = render_charts(result, windows)
        receipt['charts_unchanged'] = {name: hashlib.sha256(data).hexdigest() == checks[name]
                                      for name, data in charts.items()}
        require(all(receipt['charts_unchanged'].values()), 'Report repair unexpectedly changed a chart')
        initial = {}
        for mode in ('included', 'none'):
            initial[mode] = {**charts,
                'report.md': render_markdown(result, evidence, excerpts=mode, windows=windows).encode('utf-8'),
                'report.html': render_html(result, evidence, excerpts=mode, windows=windows).encode('utf-8')}
        require(analytical_digest(result) == original_digest and selected_interval_digest(result) == original_intervals,
                'Rendering mutated stored analytical values')
        # This complete corrected-presentation bundle retains old analytical
        # metadata and copied JSON bytes. Never attach a fabricated analysis run
        # receipt: current renderer identity is recorded only in this QA receipt.
        included = out / 'results' / 'private-en'
        copied = {name: stream_file(safe_artifact(source, name)) for name in checks if name not in PRESENTATIONS}
        publish_files({**copied, **initial['included']}, included, limits=limits, _add_checksums=True)
        omitted = out / 'results' / 'private-none'
        metadata = {name: stream_file(safe_artifact(source, name)) for name in RENDER_METADATA}
        publish_files({**metadata, **initial['none']}, omitted, limits=limits)
        _, reloaded, copied_checks, _ = inspect_artifacts(included)
        require(copied_checks['results.json'] == checks['results.json'], 'Copied results bytes changed')
        require(analytical_digest(reloaded) == original_digest, 'Analytical projection changed after saved-JSON publication')
        require(selected_interval_digest(reloaded) == original_intervals, 'Stored selected intervals changed')
        receipt['analytical_values_sha256'] = original_digest
        receipt['selected_intervals_and_matches_sha256'] = original_intervals
        receipt['results_bytes_preserved_exactly'] = True
        receipt['immutable_artifact_checks'] = {name: copied_checks[name] == expected
            for name, expected in checks.items() if name not in {'report.md', 'report.html'}}
        require(all(receipt['immutable_artifact_checks'].values()), 'A non-report artifact changed')
        if args.fresh_results is not None:
            fresh = load_artifact_json(args.fresh_results)
            require(analytical_digest(fresh) == original_digest, 'Fresh result differs outside the allowed presentation identity fields')
            require(selected_interval_digest(fresh) == original_intervals, 'Fresh selected intervals differ')
            receipt['optional_fresh_results_projection_match'] = True
        env = os.environ.copy()
        env.update(PYTHONHASHSEED='901', TZ='UTC', PYTHONDONTWRITEBYTECODE='1')
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
        receipt['child_environment_overrides'] = {'PYTHONHASHSEED': '901', 'TZ': 'UTC', 'PYTHONDONTWRITEBYTECODE': '1',
                                                 'PYTHONPATH': 'removed', 'PYTHONHOME': 'removed'}
        receipt['saved_json_rerender_agreement'] = {}
        for mode, initial_path in (('included', included), ('none', omitted)):
            rerendered = out / 'rerendered' / mode
            argv = [args.python, '-B', '-m', 'account_history_analyzer', 'render', '--results', str(included/'results.json'),
                    '--artifacts', str(included), '--format', 'both', '--excerpts', mode, '--out', str(rerendered)]
            process = run_logged(out, receipt, 'saved-json-rerender-'+mode, argv, env=env)
            require(process.returncode == 0, 'Saved-JSON rerender command failed')
            agreement = {name: sha_file(initial_path/name) == sha_file(rerendered/name)
                         for name in (*PRESENTATIONS, *RENDER_METADATA)}
            receipt['saved_json_rerender_agreement'][mode] = agreement
            require(all(agreement.values()), 'Initial report and separate-process saved-JSON rerender differ')
        copied_test = out / 'scripts' / 'test_sensitivity_visibility.py'
        shutil.copyfile(original_test, copied_test)
        require(sha_file(original_test) == sha_file(copied_test), 'Original known-failure regression was altered')
        receipt['original_regression_source_sha256'] = sha_file(original_test)
        receipt['regression_source_unchanged'] = True
        process = run_logged(out, receipt, 'original-sensitivity-visibility',
            [args.python, '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', str(copied_test)], env=env)
        receipt['original_regression_exit_code'] = process.returncode
        require(process.returncode == 0, 'Unmodified original report regression still fails; inspect new private logs')
        receipt['status'] = 'passed'
    finally:
        after = study_inventory(study)
        receipt['historical_inventory_sha256_after'] = canonical_digest(after)
        receipt['historical_file_count_after'] = len(after)
        receipt['historical_study_bytes_unchanged'] = before == after
        if before != after:
            receipt['status'] = 'failed'
        (out / 'presentation-receipt.json').write_bytes(canonical_bytes(receipt))
        require(before == after, 'Historical study files changed during the preservation audit')
    print(json.dumps({'status': receipt['status'], 'historical_files_preserved': len(before),
        'saved_json_rerender_files_compared': sum(len(value) for value in receipt['saved_json_rerender_agreement'].values()),
        'original_regression_exit_code': receipt['original_regression_exit_code'],
        'analytical_values_sha256': receipt['analytical_values_sha256'],
        'selected_intervals_and_matches_sha256': receipt['selected_intervals_and_matches_sha256']}, sort_keys=True))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, required=True, help='Existing frozen study directory; read-only')
    parser.add_argument('--out', type=Path, required=True, help='New private directory outside both study and repository')
    parser.add_argument('--bundle', default='results/private-en', help='Study-relative complete stored analysis bundle')
    parser.add_argument('--regression', default='scripts/test_sensitivity_visibility.py', help='Study-relative original regression to copy unchanged')
    parser.add_argument('--python', default=sys.executable, help='Same release environment used by this driver')
    parser.add_argument('--fresh-results', type=Path, help='Optional separately recomputed result to compare with the narrow metadata exclusions')
    args = parser.parse_args()
    try:
        return verify_private_presentations(args)
    except Exception as exc:
        # Private source values must never become public command output.
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
