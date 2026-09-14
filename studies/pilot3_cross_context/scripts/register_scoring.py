#!/usr/bin/env python3
"""Create the final, non-overwriting input/code/environment freeze before scoring."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--private', type=Path, required=True)
    args = parser.parse_args()
    study = Path(__file__).resolve().parent.parent
    private = args.private.resolve()
    prepared = private / 'prepared-01'
    output = study / 'protocol/scoring-freeze.json'
    if output.exists() or any(private.glob('evaluation-*')):
        raise ValueError('Registration cannot replace a freeze or follow scoring')
    receipt = json.loads((study / 'logs/study-tests-final-prescore-attempt02.receipt.json').read_bytes())
    if receipt['exit_code'] != 0:
        raise ValueError('Complete synthetic suite must pass before registration')
    for name, expected in (('environment/verification_summary.json', 'pass'),
                           ('review/prepared-independent-check-01.json', 'passed')):
        if json.loads((study / name).read_bytes())['status'] != expected:
            raise ValueError('Baseline and independent preparation checks must pass')
    index = json.loads((prepared / 'batch-index.json').read_bytes())
    strata = sorted({item['stratum_id'] for item in index})
    if len(index) != 360 or strata != ['AskAcademia / GradSchool', 'AskPhysics / Physics', 'learnmath / math']:
        raise ValueError('Full registered design is required')
    files = set()
    for folder in ('protocol', 'inventory', 'environment', 'scripts', 'tests', 'review'):
        files.update(p.resolve() for p in (study / folder).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    # Include completed preparation/test receipts, not the currently open registration log.
    files.update(p.resolve() for p in (study / 'logs').rglob('*')
                 if p.is_file() and not p.name.startswith('scoring-registration-'))
    for folder in ('candidates-01', 'audit-01', 'cohort-01', 'prepared-01'):
        files.update(p.resolve() for p in (private / folder).rglob('*') if p.is_file())
    for name in ('exclusions-mandatory.json', 'historical-audit-source-inventory.json'):
        files.add((private / name).resolve())
    files.add((study.parents[1] / 'scripts/offline_exec.py').resolve())
    files.update(p.resolve() for p in Path('/tmp/ahas-pilot3-installed').rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    files.add(Path('/tmp/ahas-pilot3-reviewed-repo/studies/pilot2/scripts/leakage_audit.py'))
    freeze = {
        'status': 'frozen_before_first_style_score', 'scoring_authorized': True,
        'registered_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'reviewed_commit': 'ea41d82ecc3f6585a7dc2bca92ede34740f0b62d',
        'implementation_fingerprint': 'bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179',
        'analysis_config_sha256': '8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925',
        'runner_sha256': sha(study / 'scripts/run_scoring.py'),
        'normalizer_sha256': sha(study / 'scripts/normalize_evaluations.py'),
        'replay_checker_sha256': sha(study / 'scripts/check_replay.py'),
        'registered_protocol_sha256': sha(study / 'protocol/PROTOCOL.md'),
        'analysis_plan_sha256': sha(study / 'protocol/analysis-plan.json'),
        'batch_index_sha256': sha(prepared / 'batch-index.json'),
        'primary_prepared_directory': str(prepared), 'replay_stratum_id': strata[0],
        'public_stratum_map': {name: f'stratum-{i:02d}' for i, name in enumerate(strata, 1)},
        'primary_environment': {'PYTHONHASHSEED': '0', 'TZ': 'UTC', 'LC_ALL': 'C.UTF-8'},
        'replay_environment': {'PYTHONHASHSEED': '73129', 'TZ': 'Pacific/Honolulu', 'LC_ALL': 'C.UTF-8'},
        'execution_limits': {'jobs': 2, 'batch_wall_seconds': 300, 'run_wall_seconds': 7200,
                             'address_space_bytes': 4294967296},
        'bound_artifacts': [{'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                            for p in sorted(files)],
    }
    with output.open('x') as handle:
        json.dump(freeze, handle, indent=2, sort_keys=True)
        handle.write('\n')
    print(json.dumps({'status': freeze['status'], 'registered_utc': freeze['registered_utc'],
                      'bound_artifacts': len(files), 'freeze_sha256': sha(output)}))


if __name__ == '__main__':
    main()
