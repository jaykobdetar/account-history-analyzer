#!/usr/bin/env python3
"""Audit the report-only 1.0.4 source against the immutable public 1.0.3 release.

This reads public source/configuration/resource files only. It neither analyzes a
history nor asserts numerical output equivalence from an unrun analysis. The
reporting.py change is an explicit presentation exception whose behavior must be
covered separately by renderer and canonical-replay tests.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile
import tomllib


ROOT = Path(__file__).resolve().parents[1]
BASELINE_SHA256 = '273356fe8b9b492c1826814c0e1f7c2afb22454279ed978d5e1d3180bed83488'
PREFIX = 'account_history_analyzer_v1/'
SCOPED_DIRECTORIES = ('src/account_history_analyzer/', 'schemas/', 'config/',
                      'resources/', 'fixtures/', 'design_examples/')
SCOPED_FILES = ('pyproject.toml', 'uv.lock', 'requirements.lock.txt',
                'containers/build-requirements.in', 'containers/build-requirements.lock',
                'containers/Dockerfile')
ADDED_FIXTURES = {'fixtures/reporting/rw001_report_cases.json'}
ALLOWED = {
    'src/account_history_analyzer/reporting.py': 'RW-001 presentation/template change; separately tested',
    'src/account_history_analyzer/__init__.py': 'exact suite version 1.0.3 to 1.0.4',
    'pyproject.toml': 'exact project version 1.0.3 to 1.0.4',
    'uv.lock': 'exact local project version 1.0.3 to 1.0.4; all dependency entries frozen',
    'src/account_history_analyzer/payload_schemas.py': 'add only 1.0.4 to strict reuse-accounting version gate',
    'schemas/results.schema.json': 'add only 1.0.4 to strict reuse-accounting version gate',
    'src/account_history_analyzer/contracts/results.schema.json': 'same generated result contract',
}


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(',', ':')) + '\n').encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def scoped(name):
    path = PurePosixPath(name)
    return ('__pycache__' not in path.parts and path.suffix != '.pyc'
            and (name in SCOPED_FILES or name.startswith(SCOPED_DIRECTORIES)))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def replace_once(data, old, new):
    require(data.count(old) == 1, 'Expected exactly one documented metadata replacement')
    return data.replace(old, new, 1)


def expected_schema(old):
    schema = deepcopy(json.loads(old))
    replacements = 0

    def visit(value):
        nonlocal replacements
        if isinstance(value, dict):
            version = value.get('suite_version')
            if isinstance(version, dict) and version.get('enum') == ['1.0.2', '1.0.3']:
                version['enum'].append('1.0.4')
                replacements += 1
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    require(replacements == 1, 'Expected one result-schema release accounting gate')
    return (json.dumps(schema, indent=2, ensure_ascii=False) + '\n').encode('utf-8')


def check_allowed(name, old, new):
    if name == 'src/account_history_analyzer/reporting.py':
        require(b"TEMPLATE_VERSION = '1.0.4'" in new, 'Presentation version must be 1.0.4')
        return
    if name.endswith('results.schema.json'):
        expected = expected_schema(old)
    elif name.endswith('payload_schemas.py'):
        expected = replace_once(old, b'"enum": ["1.0.2", "1.0.3"]',
                                b'"enum": ["1.0.2", "1.0.3", "1.0.4"]')
    elif name == 'uv.lock':
        expected = replace_once(old, b'name = "account-history-analyzer"\nversion = "1.0.3"',
                                b'name = "account-history-analyzer"\nversion = "1.0.4"')
    elif name.endswith('__init__.py'):
        expected = replace_once(old, b'__version__ = "1.0.3"', b'__version__ = "1.0.4"')
    else:
        expected = replace_once(old, b'version = "1.0.3"', b'version = "1.0.4"')
    require(new == expected, name + ': change exceeds the documented metadata exception')


def audit(baseline):
    require(file_sha(baseline) == BASELINE_SHA256, 'Baseline archive checksum differs from frozen 1.0.3')
    old_files = {}
    with tarfile.open(baseline, 'r:gz') as archive:
        for member in archive:
            if not member.isfile() or not member.name.startswith(PREFIX):
                continue
            name = member.name[len(PREFIX):]
            if scoped(name) or name == 'qa/report005/source-identity.json':
                require(name not in old_files, 'Duplicate scoped archive member: ' + name)
                stream = archive.extractfile(member)
                require(stream is not None, 'Unreadable archive member: ' + name)
                old_files[name] = stream.read()
    old_identity = json.loads(old_files.pop('qa/report005/source-identity.json'))
    current_paths = {str(path.relative_to(ROOT)): path for path in ROOT.rglob('*')
                     if path.is_file() and not path.is_symlink() and scoped(str(path.relative_to(ROOT)))}
    require(set(current_paths) - set(old_files) == ADDED_FIXTURES
            and not set(old_files) - set(current_paths), 'Unexpected scoped inventory change: ' + repr({
        'added': sorted(set(current_paths) - set(old_files)),
        'removed': sorted(set(old_files) - set(current_paths))}))
    comparisons = []
    for name in sorted(old_files):
        old, new = old_files[name], current_paths[name].read_bytes()
        equal = old == new
        if name in ALLOWED:
            check_allowed(name, old, new)
        else:
            require(equal, 'Unapproved production/configuration/resource change: ' + name)
        comparisons.append({'path': name, 'old_sha256': sha(old), 'new_sha256': sha(new),
                            'byte_identical': equal, 'allowed_change': ALLOWED.get(name)})
    changed = [row['path'] for row in comparisons if not row['byte_identical']]
    require(set(changed) == set(ALLOWED), 'Expected exactly the seven documented changed production files')
    # These metadata calls hash current package source/resources; no histories or
    # fixture truth labels enter a feature calculation.
    from account_history_analyzer import __version__
    from account_history_analyzer.pipeline import implementation_identity
    current_fp, environment, resources = implementation_identity()
    require(__version__ == '1.0.4', 'This release-specific audit requires AHAS 1.0.4')
    require(environment == old_identity['reference_environment'], 'Reference environment changed')
    for key, previous in old_identity['resource_sha256'].items():
        if key != 'report_templates':
            require(resources.get(key) == previous, 'Analytical resource identity changed: ' + key)
    require(set(resources) == set(old_identity['resource_sha256']), 'Resource inventory changed')
    require(resources['report_templates'] != old_identity['resource_sha256']['report_templates'],
            'Expected a changed report template identity')
    require(current_fp != old_identity['implementation_fingerprint'], 'Expected a new implementation identity')
    project = tomllib.loads(current_paths['pyproject.toml'].read_text(encoding='utf-8'))
    require(project['project']['version'] == __version__, 'Project/package version disagreement')
    return {'schema_version': '1.0.0', 'status': 'passed',
            'scope': 'RW-001 production-source, configuration, dependency, vendor and resource preservation',
            'baseline_archive': str(baseline.relative_to(ROOT)) if baseline.is_relative_to(ROOT) else baseline.name,
            'baseline_archive_sha256': BASELINE_SHA256,
            'baseline_suite_version': '1.0.3', 'current_suite_version': __version__,
            'baseline_implementation_fingerprint': old_identity['implementation_fingerprint'],
            'current_implementation_fingerprint': current_fp, 'reference_environment': environment,
            'baseline_resource_sha256': old_identity['resource_sha256'], 'current_resource_sha256': resources,
            'allowed_changed_paths': ALLOWED, 'actual_changed_paths': changed,
            'added_synthetic_renderer_fixtures': [
                {'path': name, 'sha256': file_sha(current_paths[name]), 'bytes': current_paths[name].stat().st_size}
                for name in sorted(ADDED_FIXTURES)],
            'scoped_file_count': len(comparisons),
            'byte_identical_file_count': sum(row['byte_identical'] for row in comparisons),
            'file_comparisons': comparisons,
            'numerical_code_config_vendor_and_resources_byte_identical': True,
            'dependency_pins_byte_identical': True, 'unapproved_changes': [],
            'history_analysis_executed_by_this_audit': False,
            'numerical_output_equivalence': 'not_tested_by_this_source_audit; see separately executed regression/replay receipts',
            'private_inputs_or_maps_read': False,
            'renderer_behavior': 'presentation exception; validated by separate tests',
            'audit_script_sha256': file_sha(Path(__file__))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=ROOT / 'release/1.0.3/account-history-analyzer-1.0.3-source-and-reports.tar.gz')
    parser.add_argument('--out', type=Path, default=ROOT / 'qa/rw001/analytical-freeze.json')
    args = parser.parse_args()
    require(not args.out.exists(), 'Refusing to overwrite an existing preservation receipt')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = audit(args.baseline.resolve())
    except Exception as exc:
        result = {'schema_version': '1.0.0', 'status': 'failed',
                  'error': {'type': type(exc).__name__, 'message': str(exc)},
                  'audit_script_sha256': file_sha(Path(__file__))}
        args.out.write_bytes(canonical(result))
        print(json.dumps(result, sort_keys=True), flush=True)
        return 1
    args.out.write_bytes(canonical(result))
    print(json.dumps({key: result[key] for key in ('status', 'scoped_file_count', 'byte_identical_file_count',
                                                 'actual_changed_paths', 'current_implementation_fingerprint')},
                     sort_keys=True), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
