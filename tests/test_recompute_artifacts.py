"""Full replay compares presentation bytes; checksum integrity alone does not."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from account_history_analyzer import AnalysisConfig, analyze, load_snapshot, write_artifacts
from account_history_analyzer.artifacts import verify_artifacts
from account_history_analyzer.errors import IntegrityError
from account_history_analyzer.io import canonical_bytes, sha256_bytes
from account_history_analyzer.verification import verify

ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / 'fixtures/arithmetic.jsonl'
MANIFEST = ROOT / 'fixtures/arithmetic.snapshot.json'
CANONICAL_ARTIFACTS = {
    'results.json', 'resolved_config.json', 'method_registry.json',
    'records_features.jsonl', 'windows.jsonl', 'evidence.jsonl',
    'report.md', 'report.html', 'activity_daily.svg', 'activity_hourly.svg',
    'eligible_word_volume.svg', 'surface_features.svg', 'adjacent_distances.svg',
    'checksums.json',
}


@pytest.fixture(scope='module')
def genuine_reports(tmp_path_factory):
    root = tmp_path_factory.mktemp('recompute-artifacts')
    outputs = {}
    for excerpts in ('included', 'none'):
        config = AnalysisConfig.from_mapping({'report': {'excerpts': excerpts}})
        output = root / excerpts
        write_artifacts(analyze(load_snapshot(RECORDS, MANIFEST, config), config), output)
        outputs[excerpts] = output
    return outputs


def copied_report(genuine_reports, tmp_path, *, excerpts='included'):
    output = tmp_path / 'analysis'
    shutil.copytree(genuine_reports[excerpts], output)
    return output


def cli_verify(output, *, recompute):
    command = [sys.executable, '-m', 'account_history_analyzer', 'verify',
               '--input', str(RECORDS), '--manifest', str(MANIFEST), '--analysis-dir', str(output)]
    if recompute:
        command.append('--recompute')
    return subprocess.run(command, check=False, capture_output=True)


def assert_full_scope(result):
    assert result['status'] == 'reproduced'
    assert result['verification_scope'] == 'all_canonical_artifacts'
    assert result['reproduced_artifacts'] == sorted(CANONICAL_ARTIFACTS)
    assert len(result['reproduced_artifacts']) == 14
    assert result['checked_artifacts'] == 13  # The manifest does not hash itself.
    assert 'run_receipt.json' not in result['reproduced_artifacts']
    assert 'ingest_receipt.json' not in result['reproduced_artifacts']


@pytest.mark.parametrize('name', ['report.md', 'report.html', 'activity_daily.svg'])
def test_forged_presentation_and_matching_checksums_need_full_recompute(genuine_reports, tmp_path, name):
    output = copied_report(genuine_reports, tmp_path)
    results_before = (output / 'results.json').read_bytes()
    original = (output / name).read_bytes()
    if name == 'report.md':
        forged = original.replace(b'| Retained word tokens | 36 |', b'| Retained word tokens | 999 |', 1)
    elif name == 'report.html':
        forged = original.replace(b'<title>Supplied account-history measurements</title>',
                                  b'<title>Changed report title</title>', 1)
    else:
        forged = original.replace(b'data-value="6"', b'data-value="999"', 1)
    assert forged != original, 'The adversarial replacement must alter a real artifact'
    (output / name).write_bytes(forged)
    checks = json.loads((output / 'checksums.json').read_bytes())
    checks[name] = sha256_bytes(forged)
    (output / 'checksums.json').write_bytes(canonical_bytes(checks))
    assert (output / 'results.json').read_bytes() == results_before

    # These checksums faithfully describe the altered bundle. Integrity checks
    # make no claim that the supplied source recreates the altered presentation.
    assert verify_artifacts(output)['status'] == 'integrity_only'
    integrity = verify(RECORDS, MANIFEST, output)
    assert integrity['status'] == 'integrity_only'
    assert integrity['verification_scope'] == 'artifact_checksums_and_supplied_identities'
    assert 'reproduced_artifacts' not in integrity
    with pytest.raises(IntegrityError) as caught:
        verify(RECORDS, MANIFEST, output, recompute=True)
    assert caught.value.code == 'reproduction_mismatch'
    assert caught.value.exit_code == 5
    command = cli_verify(output, recompute=True)
    assert command.returncode == 5
    assert command.stdout == b''
    assert b'reproduction_mismatch' in command.stderr


@pytest.mark.parametrize('excerpts', ['included', 'none'])
def test_genuine_configured_excerpt_mode_reproduces_all_fourteen_artifacts(genuine_reports, excerpts):
    output = genuine_reports[excerpts]
    resolved = json.loads((output / 'resolved_config.json').read_bytes())
    assert resolved['report']['excerpts'] == excerpts
    if excerpts == 'none':
        assert 'Source excerpts omitted' in (output / 'report.md').read_text()
        assert 'source-excerpt' not in (output / 'report.html').read_text()
    assert_full_scope(verify(RECORDS, MANIFEST, output, recompute=True))
    command = cli_verify(output, recompute=True)
    assert command.returncode == 0, command.stderr.decode()
    assert_full_scope(json.loads(command.stdout))


@pytest.mark.parametrize('excerpts', ['included', 'none'])
def test_untrusted_receipt_rendering_flags_cannot_select_replay_mode(genuine_reports, tmp_path, excerpts):
    output = copied_report(genuine_reports, tmp_path, excerpts=excerpts)
    before_checksums = (output / 'checksums.json').read_bytes()
    before_result = (output / 'results.json').read_bytes()
    receipt_path = output / 'run_receipt.json'
    receipt = json.loads(receipt_path.read_bytes())
    opposite = 'none' if excerpts == 'included' else 'included'
    receipt['render_excerpts'] = opposite
    receipt['original_config']['report']['excerpts'] = opposite
    receipt_path.write_bytes(canonical_bytes(receipt))
    assert verify_artifacts(output)['status'] == 'integrity_only'
    assert_full_scope(verify(RECORDS, MANIFEST, output, recompute=True))
    assert (output / 'checksums.json').read_bytes() == before_checksums
    assert (output / 'results.json').read_bytes() == before_result


def test_receipts_are_optional_to_full_canonical_reproduction(genuine_reports, tmp_path):
    output = copied_report(genuine_reports, tmp_path)
    for name in ('run_receipt.json', 'ingest_receipt.json'):
        (output / name).unlink()
    assert_full_scope(verify(RECORDS, MANIFEST, output, recompute=True))


def test_checksum_manifest_bytes_are_part_of_canonical_reproduction(genuine_reports, tmp_path):
    output = copied_report(genuine_reports, tmp_path)
    path = output / 'checksums.json'
    before = path.read_bytes()
    checks = json.loads(before)
    # The same checksum mapping in a different JSON serialization remains an
    # internally consistent manifest, but it is not the canonical manifest byte
    # artifact advertised in the complete replay scope.
    path.write_text(json.dumps(dict(reversed(list(checks.items()))), indent=2) + '\n')
    assert path.read_bytes() != before
    assert json.loads(path.read_bytes()) == checks
    assert verify_artifacts(output)['status'] == 'integrity_only'
    with pytest.raises(IntegrityError) as caught:
        verify(RECORDS, MANIFEST, output, recompute=True)
    assert caught.value.code == 'reproduction_mismatch'
