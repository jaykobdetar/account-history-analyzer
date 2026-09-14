"""Run only inside the pinned reference image with the public repository mounted."""
from pathlib import Path
import hashlib
import json
import os
import resource
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path('/review')
OUT = Path('/receipts')
EXPECTED_FP = 'bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179'
WHEEL = ROOT / 'dist/account_history_analyzer-1.0.4-py3-none-any.whl'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(name, argv, cwd='/tmp'):
    started = time.perf_counter()
    with (OUT / (name + '.stdout.log')).open('xb') as stdout, (OUT / (name + '.stderr.log')).open('xb') as stderr:
        result = subprocess.run(argv, cwd=cwd, stdout=stdout, stderr=stderr)
    receipt = {'command': argv, 'cwd': cwd, 'exit_code': result.returncode,
               'wall_seconds': time.perf_counter() - started,
               'stdout_sha256': sha(OUT / (name + '.stdout.log')),
               'stderr_sha256': sha(OUT / (name + '.stderr.log')),
               'network_isolation': 'docker_network_none'}
    (OUT / (name + '.receipt.json')).write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'step': name, **receipt}), flush=True)
    return result.returncode


def main():
    if (OUT / 'verification.json').exists():
        raise RuntimeError('Refusing to overwrite prior verification')
    assert os.environ.get('AHAS_NETWORK_ISOLATION') == 'docker_network_none'
    assert run('wheel-install', [sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps',
                                '--force-reinstall', str(WHEEL)]) == 0
    import account_history_analyzer as ahas
    from account_history_analyzer.pipeline import implementation_identity
    package_path = Path(ahas.__file__).resolve()
    assert ahas.__version__ == '1.0.4'
    assert package_path.is_relative_to('/usr/local/lib/python3.12/site-packages')
    identity = implementation_identity()
    assert identity[0] == EXPECTED_FP
    tests_code = run('full-tests', [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                                  '--basetemp=/tmp/rw001-pytest', '--junitxml=/receipts/full-tests.xml',
                                  'tests'], cwd=str(ROOT))
    counts = {'tests': 0, 'failures': 0, 'errors': 0, 'skipped': 0}
    suites = ET.parse(OUT / 'full-tests.xml').getroot()
    for suite in suites.iter('testsuite'):
        for name in counts:
            counts[name] += int(suite.attrib.get(name, 0))
    skipped = [{'test': case.attrib.get('name'), 'reason': skip.attrib.get('message')}
               for case in suites.iter('testcase') for skip in case.findall('skipped')]
    analysis = Path('/tmp/rw001-wheel-arithmetic')
    inputs = ['--input', str(ROOT / 'fixtures/arithmetic.jsonl'),
              '--manifest', str(ROOT / 'fixtures/arithmetic.snapshot.json')]
    analyze_code = run('arithmetic-analyze', [sys.executable, '-m', 'account_history_analyzer',
                                            'analyze', *inputs, '--out', str(analysis)])
    verify_code = run('arithmetic-recompute', [sys.executable, '-m', 'account_history_analyzer',
                                             'verify', *inputs, '--analysis-dir', str(analysis), '--recompute'])
    verify = json.loads((OUT / 'arithmetic-recompute.stdout.log').read_text())
    assert verify['status'] == 'reproduced'
    assert verify['verification_scope'] == 'all_canonical_artifacts'
    names = verify['reproduced_artifacts']
    assert len(names) == 14
    source = ROOT / 'output/rw001/arithmetic-source'
    comparisons = [{'name': name, 'source_sha256': sha(source / name), 'wheel_sha256': sha(analysis / name),
                    'byte_identical': (source / name).read_bytes() == (analysis / name).read_bytes()}
                   for name in names]
    assert all(row['byte_identical'] for row in comparisons)
    shutil.copytree(analysis, OUT / 'arithmetic')
    passed = tests_code == analyze_code == verify_code == 0 and counts['failures'] == counts['errors'] == 0
    result = {'status': 'passed' if passed else 'failed', 'suite_version': ahas.__version__,
              'production_wheel_sha256': sha(WHEEL), 'imported_package_path': str(package_path),
              'implementation_fingerprint': identity[0], 'reference_environment': identity[1],
              'resource_sha256': identity[2], 'test_counts': counts,
              'passed_tests': counts['tests'] - counts['failures'] - counts['errors'] - counts['skipped'],
              'skips': skipped, 'analysis_exit_code': analyze_code, 'recompute_exit_code': verify_code,
              'canonical_artifacts_compared': len(comparisons), 'comparisons': comparisons,
              'recompute': verify, 'network_isolation': 'docker_network_none',
              'peak_children_rss_kib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
              'operational_receipts_excluded_from_canonical_comparison': True}
    (OUT / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'test_counts': counts,
                      'canonical_artifacts_compared': len(comparisons)}, sort_keys=True), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
