"""Record frozen installed-package provenance without reading the study corpus."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
PINNED = Path('/tmp/ahas-pilot3-reviewed-repo')
INSTALLED = Path('/tmp/ahas-pilot3-installed')
WHEEL = Path('/tmp/ahas-pilot3-wheel/account_history_analyzer-1.0.4-py3-none-any.whl')
PYTHON = ROOT / '.venv/bin/python'
EXPECTED_COMMIT = 'ea41d82ecc3f6585a7dc2bca92ede34740f0b62d'
EXPECTED_FP = 'bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179'
EXPECTED_CONFIG = '8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925'

PROBE = '''
import hashlib, importlib.metadata as md, json, pathlib, platform, sys
import account_history_analyzer as ahas
from account_history_analyzer.pipeline import implementation_identity
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.io import digest
package_root = pathlib.Path(ahas.__file__).parent
fp, environment, resources = implementation_identity()
print(json.dumps({
  "python": sys.version,
  "python_executable": sys.executable,
  "package_file": ahas.__file__,
  "module_version": ahas.__version__,
  "distribution_version": md.version("account-history-analyzer"),
  "distribution_path": str(md.distribution("account-history-analyzer")._path),
  "direct_url": json.loads(md.distribution("account-history-analyzer").read_text("direct_url.json") or "null"),
  "implementation_fingerprint": fp,
  "reference_environment": environment,
  "resource_hashes": resources,
  "config_sha256": digest(AnalysisConfig.from_mapping().analytical()),
  "expanded_default_config": AnalysisConfig.from_mapping().analytical(),
  "dependency_versions": {name: md.version(name) for name in ("numpy", "scipy", "ruptures", "markdown-it-py", "jsonschema", "pytest", "hypothesis", "hatchling")},
  "package_files_sha256": {str(p.relative_to(package_root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(package_root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}
}, default=lambda value: dict(value)))
'''


def probe(path: Path | None) -> dict:
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    if path is not None:
        env['PYTHONPATH'] = str(path)
    result = subprocess.run([str(PYTHON), '-c', PROBE], cwd='/tmp', env=env,
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def save(name: str, data: object) -> None:
    (OUT / name).write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def main() -> None:
    before = probe(None)
    pinned = probe(PINNED / 'src')
    installed = probe(INSTALLED)
    commit = subprocess.check_output(['git', '-C', str(PINNED), 'rev-parse', 'HEAD'], text=True).strip()
    project = tomllib.loads((PINNED / 'pyproject.toml').read_text())['project']
    requirements = dict(item.split('==') for item in project['dependencies'])
    checks = {
        'pinned_commit_matches': commit == EXPECTED_COMMIT,
        'wheel_import_path_used': Path(installed['package_file']).is_relative_to(INSTALLED),
        'wheel_distribution_path_used': Path(installed['distribution_path']).is_relative_to(INSTALLED),
        'wheel_is_noneditable': not (installed['direct_url'] or {}).get('dir_info', {}).get('editable', False),
        'module_and_distribution_version_agree': installed['module_version'] == installed['distribution_version'] == project['version'] == '1.0.4',
        'installed_package_bytes_match_pinned_source': installed['package_files_sha256'] == pinned['package_files_sha256'],
        'installed_fp_matches_frozen': installed['implementation_fingerprint'] == EXPECTED_FP,
        'pinned_fp_matches_frozen': pinned['implementation_fingerprint'] == EXPECTED_FP,
        'installed_config_matches_frozen': installed['config_sha256'] == EXPECTED_CONFIG,
        'pinned_config_matches_frozen': pinned['config_sha256'] == EXPECTED_CONFIG,
        'resource_hashes_identical': installed['resource_hashes'] == pinned['resource_hashes'],
        'runtime_dependencies_match_pins': all(installed['dependency_versions'][name] == version for name, version in requirements.items()),
        'reference_environment_unchanged': installed['reference_environment'] == pinned['reference_environment'] == before['reference_environment'],
        'editable_source_fp_matches_frozen': before['implementation_fingerprint'] == EXPECTED_FP,
    }
    save('editable_before.json', before)
    save('pinned_source.json', pinned)
    save('installed_wheel.json', installed)
    save('verification_summary.json', {
        'status': 'pass' if all(checks.values()) else 'fail',
        'checks': checks,
        'pinned_commit': commit,
        'wheel_path': str(WHEEL),
        'wheel_sha256': hashlib.sha256(WHEEL.read_bytes()).hexdigest(),
        'runtime_dependency_requirements': requirements,
        'corpus_read': False,
        'production_source_changed': False,
        'runtime_dependency_installation': 'Existing pinned .venv dependencies reused; wheel installed offline with --no-deps into an isolated target.',
        'stale_metadata_explanation': 'The existing .venv contains a 1.0.0 editable distribution pointing to the live checkout. Editable imports load the checkout source (now __version__ 1.0.4); dist-info metadata is a separate snapshot retained from installation. The isolated wheel has matching source and installed distribution versions 1.0.4.',
    })
    print(json.dumps(checks, indent=2))
    assert all(checks.values()), 'Frozen installed environment checks failed'


if __name__ == '__main__':
    main()
