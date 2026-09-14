"""RW-001 presentation release keeps reuse accounting strict and legacy data readable."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tomllib

import pytest

from account_history_analyzer import __version__
from account_history_analyzer.errors import InputError
from account_history_analyzer.io import load_snapshot, thaw
from account_history_analyzer.pipeline import analyze
from account_history_analyzer.schemas import validate


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_FIELDS = ('resource_usage', 'resource_limits', 'resource_limit_reason')
ACCOUNTING_VERSIONS = ('1.0.2', '1.0.3', '1.0.4')


@pytest.fixture(scope='module')
def arithmetic_result():
    snapshot = load_snapshot(ROOT / 'fixtures/arithmetic.jsonl',
                             ROOT / 'fixtures/arithmetic.snapshot.json')
    return thaw(analyze(snapshot).results)


def test_RW001_META_01_project_and_lock_identify_the_running_package():
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    lock = tomllib.loads((ROOT / 'uv.lock').read_text(encoding='utf-8'))
    local_packages = [package for package in lock['package']
                      if package['name'] == project['project']['name']]
    assert len(local_packages) == 1
    assert project['project']['version'] == local_packages[0]['version'] == __version__


@pytest.mark.parametrize('version', ACCOUNTING_VERSIONS)
def test_RW001_META_02_complete_resource_accounting_accepted(arithmetic_result, version):
    candidate = deepcopy(arithmetic_result)
    candidate['analysis']['suite_version'] = version
    assert set(RESOURCE_FIELDS) <= candidate['modules']['reuse']['payload'].keys()
    validate(candidate, 'results')


@pytest.mark.parametrize('version', ACCOUNTING_VERSIONS)
@pytest.mark.parametrize('removed', [(name,) for name in RESOURCE_FIELDS] + [RESOURCE_FIELDS])
def test_RW001_META_03_current_accounting_cannot_fall_back_to_legacy(arithmetic_result, version, removed):
    candidate = deepcopy(arithmetic_result)
    candidate['analysis']['suite_version'] = version
    for name in removed:
        del candidate['modules']['reuse']['payload'][name]
    with pytest.raises(InputError):
        validate(candidate, 'results')


def test_RW001_META_04_historical_101_payload_remains_typed(arithmetic_result):
    candidate = deepcopy(arithmetic_result)
    candidate['analysis']['suite_version'] = '1.0.1'
    for name in RESOURCE_FIELDS:
        del candidate['modules']['reuse']['payload'][name]
    validate(candidate, 'results')
    candidate['modules']['reuse']['payload']['unregistered_measurement'] = 0
    with pytest.raises(InputError):
        validate(candidate, 'results')


def test_RW001_META_05_source_and_packaged_result_contracts_are_identical():
    assert (ROOT / 'schemas/results.schema.json').read_bytes() == (
        ROOT / 'src/account_history_analyzer/contracts/results.schema.json').read_bytes()
