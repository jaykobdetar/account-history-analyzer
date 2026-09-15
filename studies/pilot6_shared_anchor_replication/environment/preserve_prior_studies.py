"""Bounded hash-only Pilot6 preservation baseline and final recheck.

Extends the unchanged Pilot5 preservation helpers. It never parses results or
source prose, never calls preprocessing or analysis, and publishes no private
file names. The historical source inventory is read as binding metadata only.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import stat
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COMMIT = 'ea41d82ecc3f6585a7dc2bca92ede34740f0b62d'
FP = 'bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179'
CONFIG = '8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925'
INSTALLED = Path('/tmp/ahas-pilot3-installed')
REVIEWED = Path('/tmp/ahas-pilot3-reviewed-repo')
STUDIES = {'pilot3': 'pilot3_cross_context', 'pilot4': 'pilot4_chronological_controls', 'pilot5': 'pilot5_shared_anchor'}
LIMITS = {'wall_seconds': 600, 'address_space_bytes': 4*1024**3, 'bytes_hashed': 16*1024**3,
          'files_hashed': 100000, 'output_file_bytes': 64*1024**2}
PRIOR_HELPERS = {
    'studies/pilot5_shared_anchor/environment/freeze_prior_artifacts.py': '852a26a4d90f40bcffdd13033bca6d764573d0718cf83a2cc0bcc4274e1c955d',
    'studies/pilot5_shared_anchor/environment/verify_final_preservation.py': '3ab76d5936a7ec8fe1d5964ec3240da522f59565d66e842b2b1442ddf329a974',
    'studies/pilot3_cross_context/environment/verify_environment.py': '40d2aeb1ace80a79a7f8beab2daa5965ab5e8a037139df6a4ab88a3a1f1742d1',
}
CACHE_PARTS = {'__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache'}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def save(path, value):
    with Path(path).open('x') as handle:
        json.dump(value, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write('\n')


def prior_helpers():
    modules = []
    for i, (relative, expected) in enumerate(PRIOR_HELPERS.items()):
        path = ROOT/relative
        require(sha(path) == expected, 'unchanged_prior_helper_hash_mismatch')
        spec = importlib.util.spec_from_file_location('pilot6_frozen_helper_'+str(i), path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    return modules


class Budget:
    def __init__(self, max_bytes=LIMITS['bytes_hashed'], max_files=LIMITS['files_hashed']):
        self.bytes = self.files = 0
        self.max_bytes, self.max_files = max_bytes, max_files

    def reserve(self, size):
        require(self.bytes+size <= self.max_bytes and self.files+1 <= self.max_files, 'preservation_read_budget_exceeded')
        self.bytes += size
        self.files += 1


def files_in(root, exclude_caches):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), 'preserved_root_missing_or_symlink')
    result = []
    for path in root.rglob('*'):
        relative = path.relative_to(root)
        if exclude_caches and (CACHE_PARTS.intersection(relative.parts) or path.suffix in {'.pyc', '.pyo'}):
            continue
        mode = path.lstat().st_mode
        require(not stat.S_ISLNK(mode), 'preserved_symlink_refused')
        if stat.S_ISDIR(mode):
            continue
        require(stat.S_ISREG(mode), 'preserved_nonregular_file_refused')
        result.append(path)
    return sorted(result)


def inventory(root, exclude_caches, budget, describe):
    """Use unchanged Pilot5 byte description; check reads and tree membership."""
    paths = files_in(root, exclude_caches)
    rows = []
    for path in paths:
        before = path.stat()
        budget.reserve(before.st_size)
        row = describe(path, Path(root))
        after = path.stat()
        require((before.st_size, before.st_mtime_ns, before.st_ino) ==
                (after.st_size, after.st_mtime_ns, after.st_ino), 'file_changed_during_preservation_hash')
        rows.append(row)
    require(paths == files_in(root, exclude_caches), 'tree_membership_changed_during_hashing')
    return rows


def compare_rows(expected, actual):
    old = {row['path']: row for row in expected}
    new = {row['path']: row for row in actual}
    require(len(old) == len(expected) and len(new) == len(actual), 'duplicate_preservation_path')
    return {'missing': sorted(old.keys()-new.keys()), 'added': sorted(new.keys()-old.keys()),
            'changed': sorted(path for path in old.keys() & new.keys() if old[path] != new[path])}


def aggregate(rows):
    return {'files': len(rows), 'bytes': sum(row['bytes'] for row in rows)}


def protected_source_bindings(private_parent, private_roots, budget, describe):
    plan_path = private_parent/'pilot4_private/PREPARATION_PLAN_V1.json'
    plan = read(plan_path)
    inventory_path = Path(plan['historical_inventory'])
    metadata = read(inventory_path)
    require(metadata['complete_for_requested_known_protection_sources'] is True and not metadata['missing_sources'],
            'historical_source_inventory_incomplete')
    bindings = [(row, 'historical_source') for row in metadata['files']]
    bindings += [(row['snapshot_manifest'], 'historical_snapshot_manifest') for row in metadata['files'] if row.get('snapshot_manifest')]
    bindings += [(row, 'historical_metadata_binding') for row in metadata['metadata_binding_documents']]
    distinct = {}
    for row, category in bindings:
        path = Path(row['path']).resolve()
        expected = {'bytes': row['bytes'], 'sha256': row['sha256']}
        if str(path) in distinct:
            require(distinct[str(path)]['expected'] == expected, 'conflicting_historical_binding')
            distinct[str(path)]['categories'].append(category)
        else:
            distinct[str(path)] = {'expected': expected, 'categories': [category]}
    external, covered = [], []
    for name, item in sorted(distinct.items()):
        path = Path(name)
        containing = next((key for key, root in private_roots.items() if path.is_relative_to(root)), None)
        if containing:
            covered.append({'private_tree': containing, 'path': str(path.relative_to(private_roots[containing])),
                            **item['expected'], 'categories': sorted(set(item['categories']))})
            continue
        require(path.is_file() and not path.is_symlink(), 'protected_external_source_missing_or_symlink')
        budget.reserve(path.stat().st_size)
        before = path.stat()
        row = describe(path, path.parent)
        after = path.stat()
        require((before.st_size, before.st_mtime_ns, before.st_ino) ==
                (after.st_size, after.st_mtime_ns, after.st_ino), 'protected_file_changed_during_hash')
        require({k: row[k] for k in ('bytes', 'sha256')} == item['expected'], 'protected_original_source_hash_mismatch')
        external.append({'path': name, **item['expected'], 'categories': sorted(set(item['categories']))})
    return {'inventory_path': str(inventory_path), 'inventory_sha256': sha(inventory_path),
            'declared_historical_source_files': len(metadata['files']),
            'external_files': external, 'already_covered_by_private_trees': covered}


def fresh_engine(probe):
    previous_path = ROOT/'studies/pilot5_shared_anchor/environment/final-installed-package-fresh.json'
    previous = read(previous_path)
    installed, reviewed = probe.probe(INSTALLED), probe.probe(REVIEWED/'src')
    fields = ('package_files_sha256', 'module_version', 'distribution_version', 'package_file', 'distribution_path',
              'direct_url', 'implementation_fingerprint', 'config_sha256', 'expanded_default_config', 'resource_hashes',
              'dependency_versions', 'reference_environment', 'python', 'python_executable')
    checks = {'unchanged_since_pilot5_'+field: installed[field] == previous[field] for field in fields}
    tree = subprocess.check_output(['git', '-C', str(REVIEWED), 'ls-tree', '-rz', COMMIT, '--', 'src/account_history_analyzer'], timeout=30)
    git_objects = {}
    for entry in tree.split(b'\0'):
        if entry:
            metadata, name = entry.decode().split('\t', 1)
            mode, kind, oid = metadata.split()
            require(kind == 'blob' and mode == '100644', 'reviewed_git_package_entry')
            git_objects[name.removeprefix('src/account_history_analyzer/')] = oid
    for label, root in [('installed', Path(installed['package_file']).parent), ('reviewed', REVIEWED/'src/account_history_analyzer'),
                        ('workspace', ROOT/'src/account_history_analyzer')]:
        observed = {}
        for path in files_in(root, True):
            data = path.read_bytes()
            observed[str(path.relative_to(root))] = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        checks[label+'_54_files_match_immutable_reviewed_git_tree'] = observed == git_objects and len(observed) == 54
    checks.update({
        'reviewed_checkout_commit': subprocess.check_output(['git', '-C', str(REVIEWED), 'rev-parse', 'HEAD'], text=True, timeout=30).strip() == COMMIT,
        'installed_distribution_noneditable': not (installed['direct_url'] or {}).get('dir_info', {}).get('editable', False),
        'installed_module_and_distribution_1_0_4': installed['module_version'] == installed['distribution_version'] == '1.0.4',
        'actual_isolated_import_path': Path(installed['package_file']).resolve() == INSTALLED/'account_history_analyzer/__init__.py',
        'actual_isolated_distribution_path': Path(installed['distribution_path']).resolve().parent == INSTALLED,
        'frozen_fingerprint': installed['implementation_fingerprint'] == reviewed['implementation_fingerprint'] == FP,
        'frozen_configuration': installed['config_sha256'] == reviewed['config_sha256'] == CONFIG,
        'reviewed_package_hashes_match_installed': reviewed['package_files_sha256'] == installed['package_files_sha256'],
        'reviewed_resource_environment_match': reviewed['resource_hashes'] == installed['resource_hashes'] and reviewed['reference_environment'] == installed['reference_environment'],
        'original_archived_wheel_unchanged': sha(probe.WHEEL) == read(ROOT/'studies/pilot3_cross_context/environment/verification_summary.json')['wheel_sha256'],
    })
    require(all(checks.values()), 'frozen_engine_identity_mismatch')
    return {'checks': checks, 'installed_files': installed['package_files_sha256'],
            'reviewed_git_objects': git_objects, 'reviewed_commit': COMMIT,
            'implementation_fingerprint': FP, 'configuration_sha256': CONFIG,
            'prior_pilot5_installed_probe_sha256': sha(previous_path), 'archived_wheel_sha256': sha(probe.WHEEL)}, installed, reviewed


def public_projection(public_trees, private_trees, historical, private_manifest_hash, engine):
    return {'schema_version': 'pilot6-preservation-v1', 'public_trees': public_trees,
            'private_tree_aggregates': {key: aggregate(value['files']) for key, value in private_trees.items()},
            'protected_source_aggregates': {'declared_historical_source_files': historical['declared_historical_source_files'],
                'external_files': len(historical['external_files']), 'external_bytes': sum(r['bytes'] for r in historical['external_files']),
                'bindings_already_in_private_trees': len(historical['already_covered_by_private_trees'])},
            'private_preservation_manifest_sha256': private_manifest_hash, 'engine': engine,
            'private_paths_or_identifiers_published': False, 'source_content_displayed': False,
            'preprocessor_calls': 0, 'analyzer_calls': 0, 'production_tests_run': 0}


def snapshot(private_parent, describe):
    budget = Budget()
    public = {key: {'relative_root': 'studies/'+name, 'files': inventory(ROOT/'studies'/name, True, budget, describe)}
              for key, name in STUDIES.items()}
    roots = {key: (private_parent/(key+'_private')).resolve() for key in STUDIES}
    private = {key: {'root': str(root), 'files': inventory(root, False, budget, describe)} for key, root in roots.items()}
    historical = protected_source_bindings(private_parent, roots, budget, describe)
    for row in historical['already_covered_by_private_trees']:
        actual = next(r for r in private[row['private_tree']]['files'] if r['path'] == row['path'])
        require(all(actual[k] == row[k] for k in ('bytes', 'sha256')), 'protected_source_inside_private_tree_hash_mismatch')
    return public, private, historical, {'files_hashed': budget.files, 'bytes_hashed': budget.bytes}


def execute(mode, private_parent, private_out, public_out, baseline=None, private_baseline=None):
    require(os.environ.get('AHAS_NETWORK_ISOLATION') == 'linux_seccomp_socket_denial', 'offline_socket_denial_wrapper_required')
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    sys.dont_write_bytecode = True
    os.umask(0o077)
    signal.alarm(LIMITS['wall_seconds'])
    resource.setrlimit(resource.RLIMIT_AS, (LIMITS['address_space_bytes'],)*2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMITS['output_file_bytes'],)*2)
    started = time.monotonic()
    freeze_helper, final_helper, probe = prior_helpers()
    private_out = Path(private_out)
    private_out.mkdir(mode=0o700, parents=True, exist_ok=False)
    binding = {'mode': mode, 'started_utc': datetime.now(timezone.utc).isoformat(),
        'checker_sha256': sha(__file__), 'prior_helper_sha256': PRIOR_HELPERS,
        'limits': LIMITS, 'public_baseline_sha256': sha(baseline) if baseline else None,
        'private_baseline_sha256': final_helper.sha(Path(private_baseline)) if private_baseline else None}
    save(private_out/'start-binding.json', binding)
    public, private, historical, counts = snapshot(Path(private_parent), freeze_helper.describe)
    engine, installed, reviewed = fresh_engine(probe)
    save(private_out/'installed-package-fresh.json', installed)
    save(private_out/'reviewed-source-fresh.json', reviewed)
    private_manifest = {'schema_version': 'pilot6-preservation-private-v1', 'private_trees': private,
                        'historical_original_bindings': historical}
    save(private_out/'private-manifest.json', private_manifest)
    result = public_projection(public, private, historical, sha(private_out/'private-manifest.json'), engine)
    differences = {}
    if mode == 'verify':
        require(baseline is not None and private_baseline is not None, 'both_preservation_baselines_required')
        old_public, old_private = read(baseline), read(private_baseline)
        require(old_public['checker_sha256'] == sha(__file__) and old_public['status'] == 'frozen', 'preservation_checker_or_initial_status_changed')
        require(old_public['private_preservation_manifest_sha256'] == sha(private_baseline), 'private_preservation_manifest_binding_mismatch')
        require(set(old_public['public_trees']) == set(public) and set(old_private['private_trees']) == set(private), 'preserved_tree_scope_changed')
        for category, initial, current in [('public', old_public['public_trees'], public), ('private', old_private['private_trees'], private)]:
            for key in initial:
                change = compare_rows(initial[key]['files'], current[key]['files'])
                if any(change.values()):
                    differences[category+'_'+key] = change
        if old_private['historical_original_bindings'] != historical:
            differences['historical_original_bindings'] = {'changed': True}
        if old_public['engine'] != engine:
            differences['frozen_engine'] = {'changed': True}
        save(private_out/'differences.json', differences)
        result['difference_counts'] = {key: {k: len(v) if isinstance(v, list) else int(v) for k, v in changes.items()}
                                       for key, changes in differences.items()}
        result['public_baseline_sha256'] = sha(baseline)
        result['original_private_baseline_sha256'] = sha(private_baseline)
        result['status'] = 'passed' if not differences else 'failed'
    else:
        result['status'] = 'frozen'
    result.update(checker_sha256=sha(__file__), prior_helper_sha256=PRIOR_HELPERS, limits=LIMITS,
        started_utc=binding['started_utc'], finished_utc=datetime.now(timezone.utc).isoformat(),
        wall_seconds=time.monotonic()-started, peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        hash_budget_use=counts, private_execution_binding_sha256=sha(private_out/'start-binding.json'))
    save(public_out, result)
    print(json.dumps({k: result[k] for k in ('status', 'private_tree_aggregates', 'protected_source_aggregates',
          'wall_seconds', 'peak_rss_mib', 'hash_budget_use', 'analyzer_calls', 'preprocessor_calls')}))
    return 0 if result['status'] in {'frozen', 'passed'} else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('freeze', 'verify'))
    parser.add_argument('--private-parent', type=Path, required=True)
    parser.add_argument('--private-out', type=Path, required=True)
    parser.add_argument('--public-out', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--private-baseline', type=Path)
    args = parser.parse_args()
    raise SystemExit(execute(args.mode, args.private_parent, args.private_out, args.public_out,
                             args.baseline, args.private_baseline))
