"""Synthetic single-pair intake never represents the three-stratum study gate."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import zipfile

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import census_pair


def pair_plan():
    plan = json.loads((SCRIPTS.parent / 'protocol/gate_a_plan.json').read_bytes())
    plan['target'].update(accounts=20, blocks=10, strata=1)
    plan['community_pairs'] = [['X', 'Y']]
    plan['sources'] = [{'community': 'X'}, {'community': 'Y'}]
    return plan


@pytest.fixture
def run_synthetic_pair(tmp_path, monkeypatch, capsys):
    def run(account_count):
        plan = pair_plan()
        source = tmp_path / 'sources'
        private = tmp_path / 'private'
        out = tmp_path / 'pair-intake'
        source.mkdir()
        private.mkdir()
        plan['sources'] = []
        for community in ['X', 'Y']:
            rows = []
            for account in [f'account{i:02}' for i in range(account_count)] + ['protected', 'below_guard']:
                for index in range(16):
                    year = 2017 if index < 8 else 2018
                    text = 'word ' * 250 if account != 'below_guard' else 'word ' * 19 + '`' + 'excluded ' * 400 + '`'
                    rows.append({'id': f'{community}-{account}-{index}', 'user': account,
                        'root': 'synthetic-thread', 'reply_to': 'synthetic-parent', 'text': text,
                        'timestamp': int(datetime(year, 6, 1, tzinfo=timezone.utc).timestamp()),
                        'meta': {'subreddit': community}})
            archive = source / (community + '.zip')
            with zipfile.ZipFile(archive, 'w') as handle:
                handle.writestr('utterances.jsonl', b''.join(census_pair.canonical(row) for row in rows))
            plan['sources'].append({'community': community, 'archive': archive.name,
                'bytes': archive.stat().st_size, 'sha256': census_pair.sha(archive)})
        plan['limits'].update(max_preprocessed_records=500000, max_source_rows_per_pass=2000000,
            max_source_uncompressed_bytes_per_pass=2000000000, max_wall_seconds=1800,
            max_address_space_bytes=4 * 1024**3, max_private_output_bytes=500 * 1024**2)
        exclusion = {'complete_for_known_pilot_sources': True,
            'accounts': [{'account_key': 'protected', 'reasons': ['protected_reserve']}],
            'reason_counts': {'protected_reserve': 1}, 'prior_capacity_only_accounts': []}
        (private / 'exclusions-mandatory.json').write_text(json.dumps(exclusion))
        plan_path = tmp_path / 'plan.json'
        plan_path.write_text(json.dumps(plan))
        monkeypatch.setenv('AHAS_NETWORK_ISOLATION', 'linux_seccomp_socket_denial')
        monkeypatch.setattr(census_pair.resource, 'setrlimit', lambda *args: None)
        monkeypatch.setattr(sys, 'argv', ['census_pair.py', '--plan', str(plan_path),
            '--source-root', str(source), '--private-root', str(private), '--out', str(out)])
        census_pair.main()
        stdout = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
        result = json.loads((out / 'capacity.json').read_bytes())
        return plan, result, out, private, stdout
    return run


def test_twenty_account_pair_pass_is_explicitly_not_full_study_gate(run_synthetic_pair):
    plan, result, out, private, stdout = run_synthetic_pair(20)
    assert result['gate_a_status'] == 'pair_capacity_pass'
    assert result['study_scope'] == 'single_pair_intake_only'
    assert result['full_study_gate_status'] == 'not_evaluated_by_single_pair_intake'
    assert result['scoring_permitted'] is False
    assert result['scores_computed'] is result['final_cohort_selected'] is False
    assert (result['planned_accounts'], result['planned_blocks']) == (20, 10)
    assert result['disjoint_capacity']['quota_counts'] == {'X / Y': 20}
    assert result['disjoint_capacity']['total_blocks'] == 10
    assert result['words_per_cell'] == 2000 and result['records_per_cell'] == 8
    assert result['preprocessed_records'] == 21 * 32
    assert result['eligible_records'] == 20 * 32
    assert result['eligible_words'] == 20 * 32 * 250
    assert result['record_rejections']['below_frozen_record_word_guard'] == 32
    assert stdout[-1] == result
    assert len(result['period_capacity_table']) == 4
    assert result['proposed_period_schemes']['X / Y']['id'] == 'matched2017_2018'
    rows = [json.loads(line) for line in (private / out.name / 'record-eligibility.jsonl').read_text().splitlines()]
    assert 'protected' not in {row['account_key'] for row in rows}
    assert all(row['retained_words'] == 19 for row in rows if row['account_key'] == 'below_guard')
    assert all('text' not in row for row in rows)
    binding = json.loads((out / 'start-binding.json').read_bytes())
    assert binding['script_sha256'] == census_pair.sha(SCRIPTS / 'census_pair.py')
    resources = json.loads((out / 'resources.json').read_bytes())
    assert resources['limits'] == plan['limits']
    assert resources['source_passes'] == 2
    assert resources['source_rows_per_pass'] == 22 * 32


def test_inadequate_pair_does_not_quietly_reduce_twenty_account_denominator(run_synthetic_pair):
    _, result, out, private, _ = run_synthetic_pair(18)
    assert result['gate_a_status'] == 'pair_capacity_failed'
    assert result['disjoint_capacity']['total_accounts'] == 18
    assert result['disjoint_capacity']['total_blocks'] == 9
    assert (result['planned_accounts'], result['planned_blocks']) == (20, 10)
    assert result['scoring_permitted'] is False
    witness = json.loads((private / out.name / 'capacity-witness.json').read_bytes())
    assert len(witness['allocation']['assigned']['X / Y']) == 18
    assert len(set(witness['allocation']['assigned']['X / Y'])) == 18


def test_pair_plan_accepts_only_the_registered_twenty_account_single_pair():
    plan = pair_plan()
    assert census_pair.validate_pair_intake_plan(plan) == plan['target']
    plan['target'].update(accounts=60, blocks=30, strata=3)
    with pytest.raises(ValueError, match='20-account'):
        census_pair.validate_pair_intake_plan(plan)


@pytest.mark.parametrize('field,value', [('accounts', 18), ('blocks', 9), ('strata', 2),
    ('accounts_per_stratum', 18), ('blocks_per_stratum', 9),
    ('words_per_cell', 1000), ('eligible_records_per_cell', 7), ('strata', True)])
def test_pair_intake_cannot_silently_lower_cell_guards_or_target(field, value):
    plan = pair_plan()
    plan['target'][field] = value
    with pytest.raises(ValueError):
        census_pair.validate_pair_intake_plan(plan)


@pytest.mark.parametrize('sources,pairs', [
    (['X', 'Y'], [['X', 'Z']]), (['X', 'Y', 'Z'], [['X', 'Y']]),
    (['X', 'X'], [['X', 'X']]), (['X', 'Y'], [['X', 'Y'], ['Y', 'X']]),
])
def test_pair_intake_rejects_unplanned_or_multiple_source_pairs(sources, pairs):
    plan = pair_plan()
    plan['sources'] = [{'community': community} for community in sources]
    plan['community_pairs'] = pairs
    with pytest.raises(ValueError, match='exactly two'):
        census_pair.validate_pair_intake_plan(plan)
