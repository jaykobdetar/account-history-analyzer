#!/usr/bin/env python3
"""Fresh pilot4 baseline identity check; no corpus, pipeline, or score execution.

Reuse the pilot3 provenance probe unchanged, with new timestamped receipts. The
package's actual bytes are additionally checked against git's immutable reviewed
tree, independently of the reviewed checkout's current working-tree state.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRIOR = ROOT / 'studies/pilot3_cross_context/environment'
PINNED = Path('/tmp/ahas-pilot3-reviewed-repo')
INSTALLED = Path('/tmp/ahas-pilot3-installed')
COMMIT = 'ea41d82ecc3f6585a7dc2bca92ede34740f0b62d'
FP = 'bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179'
CONFIG = '8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925'
OLD_HELPER_SHA = '40d2aeb1ace80a79a7f8beab2daa5965ab5e8a037139df6a4ab88a3a1f1742d1'


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def save(name, value):
    with (HERE/name).open('x') as handle:
        json.dump(value, handle, sort_keys=True, indent=2)
        handle.write('\n')


def main():
    started = datetime.now(timezone.utc).isoformat()
    clock = time.monotonic()
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    sys.dont_write_bytecode = True
    helper = PRIOR/'verify_environment.py'
    assert sha(helper) == OLD_HELPER_SHA, 'Prior provenance helper changed'
    prior_path = PRIOR/'installed_wheel.json'
    prior_summary_path = PRIOR/'verification_summary.json'
    binding = {'status': 'started_before_fresh_identity_probe', 'started_utc': started,
               'checker_sha256': sha(__file__), 'prior_probe_helper_sha256': sha(helper),
               'prior_installed_probe_sha256': sha(prior_path),
               'prior_verification_summary_sha256': sha(prior_summary_path),
               'expected_reviewed_commit': COMMIT, 'expected_implementation_fingerprint': FP,
               'expected_config_sha256': CONFIG, 'corpus_read': False, 'scores_computed': 0,
               'production_tests_executed': 0}
    save('baseline-start-binding.json', binding)
    spec = importlib.util.spec_from_file_location('prior_ahas_environment_probe', helper)
    probe_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe_module)
    installed = probe_module.probe(INSTALLED)
    pinned = probe_module.probe(PINNED/'src')
    previous = json.loads(prior_path.read_bytes())
    previous_summary = json.loads(prior_summary_path.read_bytes())
    commit = subprocess.check_output(['git','-C',str(PINNED),'rev-parse','HEAD'], text=True).strip()
    tree = subprocess.check_output(['git','-C',str(PINNED),'ls-tree','-r','-z',COMMIT,'--','src/account_history_analyzer'])
    prefix = 'src/account_history_analyzer/'
    git_objects = {}
    for entry in tree.split(b'\0'):
        if not entry:
            continue
        header, name = entry.decode().split('\t', 1)
        mode, kind, object_id = header.split()
        assert name.startswith(prefix) and kind == 'blob', 'Unexpected reviewed package tree entry'
        git_objects[name[len(prefix):]] = object_id
    package = Path(installed['package_file']).parent
    actual_git_objects = {}
    for relative in installed['package_files_sha256']:
        data = (package/relative).read_bytes()
        actual_git_objects[relative] = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    dependencies = previous_summary['runtime_dependency_requirements']
    checks = {
        'reviewed_checkout_commit_unchanged': commit == COMMIT,
        'installed_module_path_isolated': Path(installed['package_file']).is_relative_to(INSTALLED),
        'installed_distribution_path_isolated': Path(installed['distribution_path']).is_relative_to(INSTALLED),
        'installed_distribution_noneditable': not (installed['direct_url'] or {}).get('dir_info',{}).get('editable',False),
        'module_distribution_versions_1_0_4': installed['module_version'] == installed['distribution_version'] == '1.0.4',
        'installed_bytes_match_reviewed_git_tree': actual_git_objects == git_objects,
        'installed_bytes_match_reviewed_working_source': installed['package_files_sha256'] == pinned['package_files_sha256'],
        'installed_bytes_unchanged_since_pilot3': installed['package_files_sha256'] == previous['package_files_sha256'],
        'installed_and_pinned_fingerprints_frozen': installed['implementation_fingerprint'] == pinned['implementation_fingerprint'] == previous['implementation_fingerprint'] == FP,
        'installed_and_pinned_configuration_frozen': installed['config_sha256'] == pinned['config_sha256'] == previous['config_sha256'] == CONFIG,
        'expanded_analytical_configuration_unchanged': installed['expanded_default_config'] == pinned['expanded_default_config'] == previous['expanded_default_config'],
        'resource_hashes_unchanged': installed['resource_hashes'] == pinned['resource_hashes'] == previous['resource_hashes'],
        'runtime_dependencies_match_pinned_versions': all(installed['dependency_versions'][name] == version for name,version in dependencies.items()),
        'runtime_and_test_dependency_versions_unchanged': installed['dependency_versions'] == previous['dependency_versions'],
        'reference_environment_unchanged': installed['reference_environment'] == pinned['reference_environment'] == previous['reference_environment'],
        'python_identity_unchanged': installed['python'] == previous['python'] and installed['python_executable'] == previous['python_executable'],
        'archived_wheel_bytes_unchanged': sha(probe_module.WHEEL) == previous_summary['wheel_sha256'],
    }
    save('installed-package-fresh.json', installed)
    save('reviewed-source-fresh.json', pinned)
    report = {'status': 'passed' if all(checks.values()) else 'failed', 'checks': checks,
              'started_utc': started, 'finished_utc': datetime.now(timezone.utc).isoformat(),
              'wall_seconds': time.monotonic()-clock,
              'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'child_peak_rss_kib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
              'reviewed_commit': commit, 'installed_package_files_verified': len(actual_git_objects),
              'implementation_fingerprint': installed['implementation_fingerprint'],
              'analysis_config_sha256': installed['config_sha256'],
              'module_version': installed['module_version'], 'distribution_version': installed['distribution_version'],
              'installed_import_path': installed['package_file'],
              'runtime_dependency_versions': {name: installed['dependency_versions'][name] for name in dependencies},
              'python_version': installed['python'], 'archived_wheel_sha256': sha(probe_module.WHEEL),
              'prior_probe_helper_sha256': sha(helper), 'checker_sha256': sha(__file__),
              'fresh_probe_sha256': {'installed-package-fresh.json': sha(HERE/'installed-package-fresh.json'),
                                    'reviewed-source-fresh.json': sha(HERE/'reviewed-source-fresh.json')},
              'corpus_read': False, 'preprocessor_calls': 0, 'scores_computed': 0,
              'production_tests_executed': 0, 'production_source_changed': False,
              'dependency_installation_performed': False,
              'scope': 'Fresh installed-package/git-tree/resource/configuration and dependency-version identity only; no corpus or real analysis.'}
    save('baseline-verification.json', report)
    print(json.dumps(report,sort_keys=True))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
