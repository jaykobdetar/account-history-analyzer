"""Independent read-only checks after the pilot-2 source/input freeze.

This review-only script is outside frozen study scripts. It never scores or
changes an input. Every receipt uses a new destination instead of overwriting.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from account_history_analyzer import AnalysisConfig, __version__
from account_history_analyzer.io import digest
from account_history_analyzer.pipeline import implementation_identity

ROOT = Path(__file__).resolve().parents[1]
FREEZE_SHA = 'fba67a5a1c8ddc51c66cbe67c0ff02c317a776df382d5cd3c412d858e7de8df5'


def sha(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def safe_path(base, relative):
    target = (base / relative).resolve()
    assert target.is_relative_to(base.resolve()), 'Path leaves its declared scope'
    assert not (base / relative).is_symlink(), 'Symlink is not an immutable input'
    return target


def frozen_check():
    freeze_path = ROOT / 'protocol/scoring-freeze.json'
    assert sha(freeze_path) == FREEZE_SHA
    freeze = read(freeze_path)
    assert freeze['status'] == 'frozen' and freeze['scoring_authorized'] is True
    assert freeze['confirmation_distance_computation_authorized'] is False
    assert len(freeze['files']) == 1448
    for relative, expected in freeze['files'].items():
        assert sha(safe_path(ROOT, relative)) == expected, relative
    fingerprint, environment, resources = implementation_identity()
    baseline = read(ROOT / 'protocol/measurement-baseline.json')
    assert __version__ == '1.0.4'
    assert fingerprint == freeze['implementation_fingerprint'] == baseline['implementation_fingerprint']
    assert environment == freeze['reference_environment'] == baseline['reference_environment']
    assert dict(resources) == baseline['resources']
    assert digest(AnalysisConfig.from_toml().analytical()) == freeze['analysis_config_sha256'] == baseline['configuration_sha256']

    prepared = safe_path(ROOT, freeze['paired_prepared_directory'])
    summary = read(prepared / 'preparation-summary.json')
    units = read(prepared / 'private/units.json')
    by_id = {u['text_id']: u for u in units}
    confirmation = {u['text_id'] for u in units if u['split'] == 'confirmation'}
    confirmation_records = {i for u in units if u['split'] == 'confirmation' for i in u['record_ids']}
    confirmation_groups = defaultdict(set)
    for unit in units:
        if unit['split'] == 'confirmation':
            for key, values in unit['groups'].items():
                confirmation_groups[key].update(values)
    seen = set()
    dataset_keys = set()
    for entry in summary['datasets']:
        path = safe_path(prepared, entry['path'])
        assert sha(path) == entry['sha256']
        document = read(path)
        key = tuple(entry[k] for k in ('home_community', 'condition', 'arm', 'method'))
        assert key not in dataset_keys
        dataset_keys.add(key)
        assert document['protocol']['frozen_threshold'] is None
        assert document['protocol']['analysis_config_sha256'] == freeze['analysis_config_sha256']
        for pair in document['pairs']:
            assert pair['split'] in {'development', 'evaluation'}
            assert pair['left_text_id'] not in confirmation and pair['right_text_id'] not in confirmation
        for unit in document['texts']:
            identifier = unit['text_id']
            assert identifier in by_id and identifier not in confirmation
            assert by_id[identifier]['split'] in {'development', 'evaluation'}
            for field in ('input', 'manifest'):
                target = (path.parent / unit[field]).resolve()
                assert target.is_relative_to(prepared / 'scored/units')
                assert str(target.relative_to(ROOT)) in freeze['files']
            if identifier in seen:
                continue
            seen.add(identifier)
            records = [json.loads(line) for line in (path.parent / unit['input']).read_text().splitlines()]
            assert {r['id'] for r in records} == set(by_id[identifier]['record_ids'])
            assert not {r['id'] for r in records} & confirmation_records
            for key, values in unit['groups'].items():
                assert not set(values) & confirmation_groups[key], key
    assert len(dataset_keys) == 72
    assert len(seen) == 384 and len(confirmation) == 192
    streams = read(ROOT / 'prepared/streams/stream-plan.json')
    cases = streams['cases'] + streams['operational_availability_views']
    assert len(cases) == len({c['case_id'] for c in cases}) == 60
    assert Counter(c['case_type'] for c in streams['cases']) == {
        'splice': 24, 'continuity_proxy': 24, 'unknown_truth_natural': 3}
    return {'status': 'passed', 'scoring_freeze_sha256': FREEZE_SHA,
        'frozen_files_verified': len(freeze['files']), 'source_version': __version__,
        'implementation_fingerprint': fingerprint, 'analysis_config_sha256': freeze['analysis_config_sha256'],
        'reference_environment_and_resources_unchanged': True,
        'scored_dataset_count': len(dataset_keys), 'scored_unit_count': len(seen),
        'confirmation_units_physically_separate': len(confirmation),
        'confirmation_record_and_all_declared_group_overlaps': 0,
        'planned_stream_and_operational_slots': len(cases),
        'scores_or_replays_launched_by_this_check': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['frozen'], required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit('Refusing to overwrite an earlier review check')
    result = frozen_check()
    result['checker_sha256'] = sha(Path(__file__))
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
