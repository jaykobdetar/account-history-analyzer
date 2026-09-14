"""REPORT005: presentation releases preserve current and historical reuse contracts."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from account_history_analyzer.errors import InputError
from account_history_analyzer.io import load_snapshot, thaw
from account_history_analyzer.pipeline import analyze
from account_history_analyzer.schemas import validate


ROOT = Path(__file__).resolve().parents[1]
RESOURCE_FIELDS = ('resource_usage', 'resource_limits', 'resource_limit_reason')


@pytest.fixture(scope='module')
def arithmetic_result():
    snapshot = load_snapshot(ROOT / 'fixtures/arithmetic.jsonl',
                             ROOT / 'fixtures/arithmetic.snapshot.json')
    return thaw(analyze(snapshot).results)


@pytest.mark.parametrize('version', ['1.0.2', '1.0.3'])
def test_REPORT005_META_01_complete_resource_payload_accepted(arithmetic_result, version):
    candidate = deepcopy(arithmetic_result)
    candidate['analysis']['suite_version'] = version
    assert set(RESOURCE_FIELDS) <= candidate['modules']['reuse']['payload'].keys()
    validate(candidate, 'results')


@pytest.mark.parametrize('version', ['1.0.2', '1.0.3'])
@pytest.mark.parametrize('removed', [(name,) for name in RESOURCE_FIELDS] + [RESOURCE_FIELDS])
def test_REPORT005_META_02_resource_accounting_cannot_fall_back_to_legacy(arithmetic_result, version, removed):
    candidate = deepcopy(arithmetic_result)
    candidate['analysis']['suite_version'] = version
    for name in removed:
        del candidate['modules']['reuse']['payload'][name]
    with pytest.raises(InputError):
        validate(candidate, 'results')


def test_REPORT005_META_03_historical_101_payload_remains_readable(arithmetic_result):
    candidate = deepcopy(arithmetic_result)
    candidate['analysis']['suite_version'] = '1.0.1'
    for name in RESOURCE_FIELDS:
        del candidate['modules']['reuse']['payload'][name]
    validate(candidate, 'results')
    # Compatibility remains a typed legacy contract, not an arbitrary object.
    candidate['modules']['reuse']['payload']['unregistered_measurement'] = 0
    with pytest.raises(InputError):
        validate(candidate, 'results')
