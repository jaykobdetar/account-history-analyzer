"""Synthetic metadata only: fixed prior dates, hash chains and global quotas."""
import json
from pathlib import Path
import shutil
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import run_pair_calendar as runner


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


@pytest.fixture
def metadata_fixture(tmp_path, monkeypatch):
    def prepare(new_count=20, overlap=False, resource_amendment=False):
        public = tmp_path / 'inventory'
        private = tmp_path / 'private'
        prior = public / 'calendar-03'
        prior_census = public / 'census-02'
        census = public / 'census-04b'
        out = public / 'calendar-05'
        for path in [public, private, prior, prior_census, census]:
            path.mkdir(parents=True, exist_ok=True)
        exclusions = private / 'exclusions-mandatory.json'
        dump(exclusions, {'complete_for_known_pilot_sources': True,
            'accounts': [{'account_key': 'protected', 'reasons': ['protected_reserve']}],
            'prior_capacity_only_accounts': [{'account_key': 'academic00'}]})
        exclusion_sha = runner.fingerprint(exclusions)['sha256']
        prior_pairs = {}
        for pair, cut in runner.FIXED_PRIOR_CUTS.items():
            prefix = 'academic' if pair.startswith('AskAcademia') else 'physics'
            accounts = [f'{prefix}{i:02}' for i in range(20)]
            prior_pairs[pair] = {'scheme': runner.scheme(cut), 'accounts': accounts, 'maximum_accounts': 20,
                'account_cut_intervals_private': [{'account_key': account, 'first_cut': cut, 'last_cut': cut}
                                                 for account in accounts]}
        prior_private = private / prior.name
        dump(prior_private / 'calendar-capacities.json', {'start': runner.START, 'end': runner.END, 'pairs': prior_pairs})
        dump(prior_private / 'capacity-witness.json', {'synthetic_fixture': True})
        dump(prior / 'private-artifact-hashes.json', {p.name: runner.fingerprint(p) for p in prior_private.iterdir()})
        dump(prior / 'capacity.json', {'style_scores_computed': 0, 'final_cohort_selected': False,
            'pair_capacities': {pair: {'chosen_calendar_scheme': item['scheme'], 'maximum_four_cell_accounts': 20}
                                for pair, item in prior_pairs.items()}})
        dump(prior / 'resources.json', {'resource_outcome': 'completed_within_predeclared_limits'})
        dump(prior_census / 'source-inventory.json', {'synthetic_prior_inventory': True})
        prior_records = private / prior_census.name / 'record-eligibility.jsonl'
        dump(prior_records, {'synthetic_bytes_only_prior_metadata': True})
        dump(prior_census / 'private-artifact-hashes.json', {'record-eligibility.jsonl': runner.fingerprint(prior_records)})
        dump(prior_census / 'start-binding.json', {'plan_sha256': 'prior-plan', 'exclusions_sha256': exclusion_sha,
            'implementation_fingerprint': runner.EXPECTED_IMPLEMENTATION, 'analysis_config_sha256': runner.EXPECTED_CONFIG})
        dump(prior / 'start-binding.json', {'source_census': prior_census.name, 'plan_sha256': 'prior-plan',
            'source_inventory_sha256': runner.fingerprint(prior_census / 'source-inventory.json')['sha256'],
            'eligibility_metadata_sha256': runner.fingerprint(prior_records)['sha256']})
        monkeypatch.setattr(runner, 'FROZEN_PRIOR_PUBLIC_HASHES',
            {name: runner.fingerprint(prior / name)['sha256'] for name in runner.FROZEN_PRIOR_PUBLIC_HASHES})
        protocol = tmp_path / 'protocol'
        protocol.mkdir()
        amendment03 = protocol / 'AMENDMENT_03_FINAL_MATH_PAIR.md'
        shutil.copyfile(SCRIPTS.parent / 'protocol' / amendment03.name, amendment03)
        amendment = amendment03
        if resource_amendment:
            amendment = protocol / 'AMENDMENT_04_METADATA_LIMIT_CORRECTION.md'
            shutil.copyfile(SCRIPTS.parent / 'protocol' / amendment.name, amendment)
        plan = {'target': {'accounts': 20, 'blocks': 10, 'strata': 1, 'accounts_per_stratum': 20,
                'blocks_per_stratum': 10, 'words_per_cell': 2000, 'eligible_records_per_cell': 8},
            'sources': [{'community': name, 'archive': name + '.zip', 'sha256': name + '-synthetic-hash', 'bytes': 1}
                        for name in ['math', 'learnmath']],
            'community_pairs': [['math', 'learnmath']], 'amendment': amendment.name,
            'implementation_fingerprint': runner.EXPECTED_IMPLEMENTATION, 'analysis_config_sha256': runner.EXPECTED_CONFIG}
        plan_path = protocol / 'plan.json'
        dump(plan_path, plan)
        dump(census / 'start-binding.json', {'plan_sha256': runner.fingerprint(plan_path)['sha256'],
            'script_sha256': runner.fingerprint(SCRIPTS / 'census_pair.py')['sha256'],
            'exclusions_sha256': exclusion_sha, 'implementation_fingerprint': runner.EXPECTED_IMPLEMENTATION,
            'analysis_config_sha256': runner.EXPECTED_CONFIG, 'scores_computed': False})
        dump(census / 'source-inventory.json', {'scores_computed': False, 'sources': plan['sources']})
        dump(census / 'capacity.json', {'gate_a_status': 'pair_capacity_pass' if new_count >= 20 else 'pair_capacity_failed',
            'scoring_permitted': False, 'final_cohort_selected': False})
        dump(census / 'resources.json', {'resource_outcome': 'completed_within_predeclared_limits'})
        rows = []
        for number in range(new_count):
            account = f'academic{number:02}' if overlap else f'new{number:02}'
            for community in ['math', 'learnmath']:
                for year in [2010, 2017]:
                    for _ in range(8):
                        rows.append({'account_key': account, 'community': community,
                            'created_utc': f'{year}-06-01T00:00:00Z', 'retained_words': 250, 'reason': None})
        records = private / census.name / 'record-eligibility.jsonl'
        records.parent.mkdir()
        records.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        dump(census / 'private-artifact-hashes.json', {'record-eligibility.jsonl': runner.fingerprint(records)})
        monkeypatch.setattr(runner.resource, 'setrlimit', lambda *args: None)
        return (plan_path, amendment, census, prior, private, out)
    return prepare


def test_three_fixed_strata_pass_exact_sixty_accounts_but_do_not_permit_scoring(metadata_fixture):
    args = metadata_fixture()
    result = runner.run(*args)
    assert result['gate_a_status'] == 'capacity_pass_requires_contamination_audit'
    assert (result['planned_accounts'], result['planned_blocks']) == (60, 30)
    assert result['disjoint_capacity']['total_accounts'] == 60
    assert result['disjoint_capacity']['total_blocks'] == 30
    assert result['scoring_permitted'] is False
    assert result['final_cohort_selected'] is False
    assert result['preprocessing_calls'] == result['source_prose_reads'] == result['style_scores_computed'] == 0
    assert set(result['pair_capacities']) == {*runner.FIXED_PRIOR_CUTS, runner.NEW_PAIR}
    for pair, cut in runner.FIXED_PRIOR_CUTS.items():
        assert result['proposed_period_schemes'][pair] == runner.scheme(cut)
        assert result['pair_capacities'][pair]['fixed_from_prior_calendar'] is True
    private_out = args[4] / args[5].name
    witness = runner.read(private_out / 'capacity-witness.json')
    assigned = [a for values in witness['capacity']['assigned'].values() for a in values]
    assert len(assigned) == len(set(assigned)) == 60
    assert runner.read(private_out / 'calendar-capacities.json')['pairs'][runner.NEW_PAIR]['maximum_accounts'] == 20
    manifest = runner.read(args[5] / 'private-artifact-hashes.json')
    assert set(manifest) == {'calendar-capacities.json', 'capacity-witness.json'}
    assert all(runner.fingerprint(private_out / name) == value for name, value in manifest.items())
    public = json.dumps(result)
    assert 'academic00' not in public and 'new00' not in public and 'physics00' not in public


def test_nineteen_new_accounts_keep_full_target_and_only_eighteen_assignable(metadata_fixture):
    result = runner.run(*metadata_fixture(new_count=19))
    assert result['gate_a_status'] == 'failed_capacity'
    assert result['disjoint_capacity']['total_accounts'] == 58
    assert result['disjoint_capacity']['total_blocks'] == 29
    assert result['pair_capacities'][runner.NEW_PAIR]['maximum_four_cell_accounts'] == 19
    assert result['planned_accounts'] == 60 and result['planned_blocks'] == 30


def test_shared_account_identities_cannot_fill_two_strata(metadata_fixture):
    result = runner.run(*metadata_fixture(overlap=True))
    assert result['gate_a_status'] == 'failed_capacity'
    assert result['disjoint_capacity']['total_accounts'] == 40
    assert result['disjoint_capacity']['total_blocks'] == 20


def test_resource_amendment04_is_accepted_with_unchanged_underlying03(metadata_fixture):
    args = metadata_fixture(resource_amendment=True)
    result = runner.run(*args)
    assert result['gate_a_status'] == 'capacity_pass_requires_contamination_audit'
    binding = runner.read(args[5] / 'start-binding.json')
    assert binding['source_census'] == 'census-04b'
    assert binding['amendment']['sha256'] == runner.EXPECTED_RESOURCE_AMENDMENT_SHA256


def test_prior_public_or_private_changes_are_rejected(metadata_fixture):
    args = metadata_fixture()
    path = args[3] / 'capacity.json'
    prior = runner.read(path)
    prior['pair_capacities']['AskAcademia / GradSchool']['maximum_four_cell_accounts'] = 21
    dump(path, prior)
    with pytest.raises(ValueError, match='Frozen prior calendar public artifact changed'):
        runner.run(*args)


def test_prior_private_drift_rejected_even_if_public_capacity_unchanged(metadata_fixture):
    args = metadata_fixture()
    path = args[4] / args[3].name / 'calendar-capacities.json'
    item = runner.read(path)
    item['pairs']['AskAcademia / GradSchool']['accounts'][0] = 'invented'
    dump(path, item)
    with pytest.raises(ValueError, match='Prior private calendar bytes changed'):
        runner.run(*args)


def test_fixed_prior_dates_cannot_be_reoptimized_even_when_local_hashes_updated(metadata_fixture, monkeypatch):
    args = metadata_fixture()
    public_path = args[3] / 'capacity.json'
    private_path = args[4] / args[3].name / 'calendar-capacities.json'
    public, private = runner.read(public_path), runner.read(private_path)
    wrong = runner.scheme('2015-10-07')
    public['pair_capacities']['AskAcademia / GradSchool']['chosen_calendar_scheme'] = wrong
    private['pairs']['AskAcademia / GradSchool']['scheme'] = wrong
    dump(public_path, public)
    dump(private_path, private)
    manifest_path = args[3] / 'private-artifact-hashes.json'
    manifest = runner.read(manifest_path)
    manifest[private_path.name] = runner.fingerprint(private_path)
    dump(manifest_path, manifest)
    monkeypatch.setattr(runner, 'FROZEN_PRIOR_PUBLIC_HASHES', {name: runner.fingerprint(args[3] / name)['sha256']
                                                            for name in runner.FROZEN_PRIOR_PUBLIC_HASHES})
    with pytest.raises(ValueError, match='Frozen prior pair dates changed'):
        runner.run(*args)


def test_new_metadata_and_prior_metadata_hash_drift_are_not_accepted(metadata_fixture):
    args = metadata_fixture()
    path = args[4] / args[2].name / 'record-eligibility.jsonl'
    path.write_text(path.read_text() + '\n')
    with pytest.raises(ValueError, match='New eligibility metadata bytes changed'):
        runner.run(*args)


def test_prior_eligibility_hash_is_reverified_without_parsing_rows(metadata_fixture):
    args = metadata_fixture()
    path = args[4] / 'census-02' / 'record-eligibility.jsonl'
    path.write_text('altered metadata')
    with pytest.raises(ValueError, match='Prior eligibility metadata binding changed'):
        runner.run(*args)


def test_resource_limited_input_does_not_become_completed_feasibility(metadata_fixture):
    args = metadata_fixture()
    dump(args[2] / 'resources.json', {'resource_outcome': 'limit_exhausted'})
    with pytest.raises(ValueError, match='resource gate did not complete'):
        runner.run(*args)


def test_explicit_row_bound_blocks_before_public_capacity_publication(metadata_fixture, monkeypatch):
    args = metadata_fixture()
    monkeypatch.setattr(runner, 'LIMITS', {**runner.LIMITS, 'metadata_rows': 5})
    with pytest.raises(RuntimeError, match='metadata-row or wall-time budget'):
        runner.run(*args)
    assert not (args[5] / 'capacity.json').exists()


def test_protected_new_identity_is_rejected_even_when_metadata_digest_updated(metadata_fixture):
    args = metadata_fixture()
    path = args[4] / args[2].name / 'record-eligibility.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]['account_key'] = 'protected'
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    dump(args[2] / 'private-artifact-hashes.json', {'record-eligibility.jsonl': runner.fingerprint(path)})
    with pytest.raises(ValueError, match='Excluded account reached new calendar'):
        runner.run(*args)


def test_nonmatching_amendment_or_script_bindings_cannot_relabel_old_census(metadata_fixture):
    args = metadata_fixture()
    path = args[2] / 'start-binding.json'
    binding = runner.read(path)
    binding['script_sha256'] = runner.fingerprint(SCRIPTS / 'census.py')['sha256']
    dump(path, binding)
    with pytest.raises(ValueError, match='single-pair intake implementation'):
        runner.run(*args)
