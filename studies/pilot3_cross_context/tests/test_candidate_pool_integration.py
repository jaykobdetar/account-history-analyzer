"""Independent synthetic candidate assembly and source-preservation checks."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import prepare_candidate_pool as prepare


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def fresh_binding(plan, path):
    absolute = str(path.resolve())
    for item in plan['bound_artifacts']:
        if str(Path(item['path']).resolve()) == absolute:
            item['sha256'] = prepare.sha(path)
            return
    plan['bound_artifacts'].append({'path': absolute, 'sha256': prepare.sha(path)})


@pytest.fixture
def synthetic_pool(tmp_path, monkeypatch, capsys):
    private = tmp_path / 'private'
    private.mkdir()
    out = tmp_path / 'candidate-pool'
    source_root = tmp_path / 'sources'
    source_root.mkdir()
    metadata_path = private / 'eligibility.jsonl'
    exclusion_path = private / 'exclusions.json'
    dump(exclusion_path, {'complete_for_known_pilot_sources': True,
                         'accounts': [{'account_key': 'protected'}]})
    plan = {'phase': 'registered_score_free_candidate_pool',
        'full_target': {'accounts': 60, 'blocks': 30, 'strata': 3},
        'limits': {'candidate_account_cap_per_stratum': 40, 'candidate_records': 100000,
            'candidate_retained_words': 2000000, 'candidate_bytes': 268435456,
            'source_rows': 6000000, 'source_uncompressed_bytes': 3000000000,
            'wall_seconds': 1800, 'address_space_bytes': 4294967296},
        'strata': [], 'eligibility_metadata': [str(metadata_path)],
        'exclusion_manifest': str(exclusion_path), 'sources': [], 'bound_artifacts': []}
    metadata, original_rows, original_lines, expected_provenance = [], {}, {}, []
    for group in range(3):
        communities = [f'X{group}', f'Y{group}']
        name = ' / '.join(communities)
        accounts = [f'synthetic{group}account{i:02}' for i in range(20)]
        scheme = {'id': 'synthetic-cut2018', 'early': ['2017-01-01', '2018-01-01'],
                  'late': ['2018-01-01', '2019-01-01']}
        capacity_file = private / f'capacities-{group}.json'
        dump(capacity_file, {'pairs': {name: {'scheme': scheme, 'accounts': accounts}}})
        plan['strata'].append({'id': name, 'communities': communities,
                               'scheme': scheme, 'capacity_file': str(capacity_file)})
        for community in communities:
            lines = []
            for account in accounts:
                for year in [2017, 2018]:
                    for number in range(8):
                        timestamp = int(datetime(year, 6, 1 + number, tzinfo=timezone.utc).timestamp())
                        identifier = f'{community}-{account}-{year}-{number}'
                        row = {'id': identifier, 'user': account.upper(),
                            'root': f'thread-{community}-{account}-{year}', 'reply_to': 'original-parent',
                            'text': '  ' + 'word ' * 250 + '\n', 'timestamp': timestamp,
                            'meta': {'subreddit': community, 'permalink': '/synthetic/' + identifier}}
                        # Deliberately noncanonical spaces, field order, case and CRLF.
                        line = ('  ' + json.dumps(row, ensure_ascii=False) + '\r\n').encode()
                        lines.append(line)
                        original_rows[identifier], original_lines[identifier] = row, line
                        metadata.append({'account_key': account, 'community': community,
                            'record_id': identifier, 'created_utc': datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace('+00:00', 'Z'),
                            'retained_words': 250, 'reason': None,
                            'source_line_sha256': hashlib.sha256(line).hexdigest()})
            expected_provenance.extend(lines)
            archive = source_root / (community + '.zip')
            raw = b''.join(lines)
            with zipfile.ZipFile(archive, 'w') as handle:
                handle.writestr('utterances.jsonl', raw)
            plan['sources'].append({'community': community, 'archive': str(archive),
                'sha256': prepare.sha(archive), 'source_records': len(lines),
                'utterances_sha256': hashlib.sha256(raw).hexdigest()})
    metadata_path.write_text(''.join(json.dumps(row) + '\n' for row in metadata))
    gate = tmp_path / 'passed-gate-a.json'
    dump(gate, {'gate_a_status': 'capacity_pass_requires_contamination_audit',
        'disjoint_capacity': {'total_accounts': 60, 'total_blocks': 30,
                              'quota_counts': {s['id']: 20 for s in plan['strata']}},
        'selected_pair_strata': [s['id'] for s in plan['strata']],
        'proposed_period_schemes': {s['id']: s['scheme'] for s in plan['strata']},
        'pair_capacities': {s['id']: {'chosen_calendar_scheme': s['scheme'], 'maximum_four_cell_accounts': 20}
                            for s in plan['strata']}})
    plan['gate_a_report'] = str(gate)
    for path in [exclusion_path, gate, metadata_path, SCRIPTS / 'prepare_candidate_pool.py',
                 SCRIPTS / 'cohort_selection.py', SCRIPTS / 'study_math.py',
                 *(Path(s['capacity_file']) for s in plan['strata'])]:
        fresh_binding(plan, path)
    plan_path = tmp_path / 'plan.json'
    monkeypatch.setenv('AHAS_NETWORK_ISOLATION', 'linux_seccomp_socket_denial')
    monkeypatch.setattr(prepare.resource, 'setrlimit', lambda *args: None)

    def run():
        dump(plan_path, plan)
        monkeypatch.setattr(sys, 'argv', ['prepare_candidate_pool.py', '--plan', str(plan_path),
            '--private-root', str(private), '--out', str(out)])
        prepare.main()
        return json.loads((out / 'preparation.json').read_bytes()), capsys.readouterr().out
    return {'plan': plan, 'run': run, 'out': out, 'private': private, 'metadata': metadata_path,
            'gate': gate, 'original_rows': original_rows, 'original_lines': original_lines,
            'expected_provenance': b''.join(expected_provenance)}


def test_three_stratum_twenty_account_pool_preserves_all_original_sources_privately(synthetic_pool):
    fixture = synthetic_pool
    result, stdout = fixture['run']()
    assert result['status'] == 'candidate_pool_prepared_not_audited_or_scored'
    assert result['candidate_account_quotas'] == {s['id']: 20 for s in fixture['plan']['strata']}
    assert result['candidate_records'] == result['metadata_rows_read'] == result['source_rows'] == 1920
    assert result['candidate_cells'] == 240
    assert result['candidate_retained_words'] == 480000
    assert result['new_preprocessing_calls'] == result['style_scores_computed'] == 0
    assert result['final_cohort_frozen'] is False
    private_out = fixture['private'] / fixture['out'].name
    rows = [json.loads(line) for line in (private_out / 'candidate-pool.jsonl').read_text().splitlines()]
    assert len(rows) == len({row['record']['id'] for row in rows}) == 1920
    for wrapper in rows:
        record = wrapper['record']
        original = fixture['original_rows'][record['id']]
        assert record['text'] == original['text']
        assert record['account_id'] == original['user']
        assert record['thread_id'] == original['root']
        assert record['parent_id'] == original['reply_to']
        assert record['permalink'] == original['meta']['permalink']
        assert record['subreddit'] == original['meta']['subreddit']
        assert record['created_utc'] == datetime.fromtimestamp(original['timestamp'], timezone.utc).isoformat().replace('+00:00', 'Z')
        assert record['edit_state'] == 'unknown' and record['parent_created_utc'] is None
        assert wrapper['account_key'] == original['user'].casefold()
    assert (private_out / 'original-source-lines.jsonl').read_bytes() == fixture['expected_provenance']
    selection = json.loads((private_out / 'candidate-selection.json').read_bytes())
    assigned = [a for values in selection['allocation']['assigned'].values() for a in values]
    assert len(assigned) == len(set(assigned)) == 60
    assert all(cell['records'] == 8 and cell['retained_words'] == 2000 for cell in selection['cells'])
    manifest = json.loads((fixture['out'] / 'private-artifact-hashes.json').read_bytes())
    for name, entry in manifest.items():
        assert entry == {'sha256': prepare.sha(private_out / name), 'bytes': (private_out / name).stat().st_size}
        assert (private_out / name).stat().st_mode & 0o777 == 0o600
    public_text = json.dumps(result) + stdout
    assert 'synthetic0account00' not in public_text and 'word word' not in public_text


def test_three_duplicate_stratum_entries_cannot_masquerade_as_full_target(synthetic_pool):
    fixture = synthetic_pool
    fixture['plan']['strata'] = [fixture['plan']['strata'][0]] * 3
    with pytest.raises(ValueError, match='distinct fixed strata'):
        fixture['run']()


@pytest.mark.parametrize('omitted', ['metadata', 'capacity', 'gate', 'helper', 'exclusion'])
def test_every_consumed_dependency_requires_a_unique_hash_binding(synthetic_pool, omitted):
    fixture = synthetic_pool
    plan = fixture['plan']
    paths = {'metadata': str(fixture['metadata']), 'capacity': plan['strata'][0]['capacity_file'],
             'gate': str(fixture['gate']), 'helper': str(SCRIPTS / 'cohort_selection.py'),
             'exclusion': plan['exclusion_manifest']}
    plan['bound_artifacts'] = [item for item in plan['bound_artifacts'] if item['path'] != paths[omitted]]
    with pytest.raises(ValueError, match='uniquely hash-bound'):
        fixture['run']()


def test_no_candidate_assembly_after_failed_gate_a(synthetic_pool):
    fixture = synthetic_pool
    gate = json.loads(fixture['gate'].read_bytes())
    gate['gate_a_status'] = 'failed_capacity'
    dump(fixture['gate'], gate)
    fresh_binding(fixture['plan'], fixture['gate'])
    with pytest.raises(ValueError, match='Gate A capacity passage'):
        fixture['run']()


def test_rebound_different_dates_cannot_borrow_previous_gate_a_pass(synthetic_pool):
    fixture = synthetic_pool
    stratum = fixture['plan']['strata'][0]
    replacement = {'id': 'different-cut', 'early': ['2017-01-01', '2018-02-01'],
                   'late': ['2018-02-01', '2019-01-01']}
    stratum['scheme'] = replacement
    path = Path(stratum['capacity_file'])
    capacity = json.loads(path.read_bytes())
    capacity['pairs'][stratum['id']]['scheme'] = replacement
    dump(path, capacity)
    fresh_binding(fixture['plan'], path)
    with pytest.raises(ValueError, match='exactly match the passed Gate A'):
        fixture['run']()


def test_bound_metadata_drift_stops_before_assembly(synthetic_pool):
    fixture = synthetic_pool
    fixture['metadata'].write_text(fixture['metadata'].read_text() + '\n')
    with pytest.raises(ValueError, match='dependency changed'):
        fixture['run']()


def test_original_source_line_digest_detects_wrong_record_provenance(synthetic_pool):
    fixture = synthetic_pool
    rows = [json.loads(line) for line in fixture['metadata'].read_text().splitlines()]
    rows[0]['source_line_sha256'] = '0' * 64
    fixture['metadata'].write_text(''.join(json.dumps(row) + '\n' for row in rows))
    fresh_binding(fixture['plan'], fixture['metadata'])
    with pytest.raises(ValueError, match='changed original source record'):
        fixture['run']()
    assert not (fixture['out'] / 'preparation.json').exists()


def test_duplicate_original_metadata_id_is_rejected_before_source_selection(synthetic_pool):
    fixture = synthetic_pool
    with fixture['metadata'].open('a') as handle:
        handle.write(fixture['metadata'].read_text().splitlines(keepends=True)[0])
    fresh_binding(fixture['plan'], fixture['metadata'])
    with pytest.raises(ValueError, match='Duplicated candidate source identity'):
        fixture['run']()
