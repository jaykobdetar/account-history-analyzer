#!/usr/bin/env python3
"""Record the draft-read race and verify the registered candidate replay."""
from pathlib import Path
import hashlib, json, os

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def diffs(left, right, prefix=''):
    if isinstance(left, dict) and isinstance(right, dict):
        found = []
        for key in sorted(left.keys() | right.keys()):
            path = prefix + '.' + key if prefix else key
            if key not in left or key not in right:
                found.append({'path': path, 'old_present': key in left, 'new_present': key in right,
                    'old_value': left.get(key), 'new_value': right.get(key)})
            else:
                found.extend(diffs(left[key], right[key], path))
        return found
    return [] if left == right else [{'path': prefix, 'old_value': left, 'new_value': right}]


def main():
    assert os.environ.get('AHAS_NETWORK_ISOLATION') == 'linux_seccomp_socket_denial'
    old = ROOT / 'prepared/paired'
    new = ROOT / 'prepared/paired-registered'
    registration = read(ROOT / 'protocol/registration.json')
    plan = read(ROOT / 'protocol/plan.json')
    assert sha(ROOT / 'protocol/plan.json') == registration['files']['protocol/plan.json']
    original = read(old / 'private/preparation-plan.json')
    replay = read(new / 'private/preparation-plan.json')
    assert replay == plan
    delta = diffs(original, replay)
    assert len(delta) == 1 and delta[0]['path'] == 'leakage.missing_content'
    assert delta[0]['old_present'] is False and delta[0]['new_present'] is True
    assert sha(old / 'private/candidate-pool.jsonl') == sha(new / 'private/candidate-pool.jsonl')
    assert read(old / 'private/selection.json') == read(new / 'private/selection.json')
    assert (old / 'candidate-summary.json').read_bytes() == (new / 'candidate-summary.json').read_bytes()
    assert not (old / 'scored').exists() and not (old / 'confirmation').exists()
    audit = read(old / 'private/leakage-audit.json')
    assert audit['status'] == 'audited' and audit['candidate_pool_sha256'] == sha(new / 'private/candidate-pool.jsonl')
    old_run = read(ROOT / 'inventory/paired-candidates.receipt.json')
    new_run = read(ROOT / 'inventory/paired-registered-candidates-run.receipt.json')
    assert old_run['started_utc'] < registration['registered_utc'] < new_run['started_utc']
    result = {'status': 'passed', 'scores_computed': False,
        'old_directory': 'prepared/paired', 'registered_replay_directory': 'prepared/paired-registered',
        'old_candidate_started_utc': old_run['started_utc'], 'registered_utc': registration['registered_utc'],
        'registered_replay_started_utc': new_run['started_utc'],
        'historical_run_relabelled': False, 'exact_plan_delta': delta,
        'historical_plan_identity_note': 'The original selection plan_sha256 read the path at run completion; private/preparation-plan.json preserves the actual earlier in-memory plan. Only this preserved copy is used to identify that earlier plan.',
        'historical_saved_plan_sha256': sha(old / 'private/preparation-plan.json'),
        'registered_saved_plan_sha256': sha(new / 'private/preparation-plan.json'),
        'registered_plan_file_sha256': sha(ROOT / 'protocol/plan.json'),
        'candidate_pool_sha256': sha(new / 'private/candidate-pool.jsonl'),
        'selected_metadata_and_ranks_exactly_equal': True, 'candidate_summary_byte_identical': True,
        'existing_audit_sha256': sha(old / 'private/leakage-audit.json'),
        'independent_preflight_sha256': sha(ROOT / 'inventory/paired-preflight.json'),
        'failed_finalize_receipt_sha256': sha(ROOT / 'inventory/paired-finalize-run.receipt.json'),
        'reason_for_new_directory': 'Original finalize rejected a plan mismatch before writing units. Fresh replay uses the registered plan and preserves every earlier receipt and candidate file.'}
    path = ROOT / 'inventory/paired-registered-replay.json'
    with path.open('x') as handle:
        json.dump(result, handle, sort_keys=True, indent=2)
        handle.write('\n')
    path.chmod(0o600)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
