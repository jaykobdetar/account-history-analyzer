import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest
from account_history_analyzer import analyze,load_snapshot,write_artifacts,AnalysisConfig
from account_history_analyzer.artifacts import verify_artifacts
from account_history_analyzer.errors import IntegrityError
from account_history_analyzer.verification import verify


def report(tmp_path,selection=None,config=None):
    r=analyze(load_snapshot('fixtures/arithmetic.jsonl','fixtures/arithmetic.snapshot.json'),config,selection=selection)
    out=tmp_path/'analysis'
    write_artifacts(r,out)
    return out


def test_OUT_13_integrity_vs_reproduction(tmp_path):
    out=report(tmp_path)
    args=('fixtures/arithmetic.jsonl','fixtures/arithmetic.snapshot.json',out)
    assert verify(*args)['status']=='integrity_only'
    assert verify(*args,recompute=True)['status']=='reproduced'


@pytest.mark.parametrize('name',['results.json','records_features.jsonl','windows.jsonl','evidence.jsonl','resolved_config.json','report.html'])
def test_OUT_14_tampered_artifact(tmp_path,name):
    out=report(tmp_path)
    with (out/name).open('ab') as f:f.write(b'corruption')
    with pytest.raises(IntegrityError):
        verify('fixtures/arithmetic.jsonl','fixtures/arithmetic.snapshot.json',out)


def test_OUT_14_source_and_configuration(tmp_path):
    out=report(tmp_path)
    rows=Path('fixtures/arithmetic.jsonl').read_text().replace('THE RESULT WORKS!','AN ALTERED SOURCE!')
    p=tmp_path/'records.jsonl';p.write_text(rows)
    with pytest.raises(IntegrityError,match='snapshot mismatch'):
        verify(p,'fixtures/arithmetic.snapshot.json',out)
    config=tmp_path/'changed.toml';config.write_text('[activity]\nburst_duration_seconds=31\n')
    with pytest.raises(IntegrityError,match='configuration mismatch'):
        verify('fixtures/arithmetic.jsonl','fixtures/arithmetic.snapshot.json',out,config_path=config)


def test_compare_recomputation_and_receipt_path_untrusted(tmp_path):
    selection=json.loads(Path('design_examples/comparison.json').read_text())
    out=report(tmp_path,selection)
    # Verification does not trust this operational data for resource reads.
    (out/'run_receipt.json').write_text('{"original_config":{"delta":{"reference_path":"/unrelated/private/file"}}}')
    assert verify('fixtures/arithmetic.jsonl','fixtures/arithmetic.snapshot.json',out,recompute=True)['status']=='reproduced'


def test_toy_reference_replay_from_export(tmp_path):
    p=tmp_path/'toy.json';p.write_bytes(Path('design_examples/delta_reference_toy.json').read_bytes())
    config=AnalysisConfig.from_mapping({'delta':{'reference_path':str(p)}},allow_toy_reference=True)
    out=report(tmp_path,json.loads(Path('design_examples/comparison.json').read_text()),config)
    p.unlink()
    assert verify('fixtures/arithmetic.jsonl','fixtures/arithmetic.snapshot.json',out,recompute=True)['status']=='reproduced'


def test_OUT_12_render_excerpts_none(tmp_path):
    out=report(tmp_path)
    before=(out/'results.json').read_bytes()
    proc=subprocess.run([sys.executable,'-m','account_history_analyzer','render','--results',str(out/'results.json'),
                         '--artifacts',str(out),'--format','both','--excerpts','none','--out',str(tmp_path/'rendered')],capture_output=True)
    assert proc.returncode==0,proc.stderr
    assert (out/'results.json').read_bytes()==before
    for name in ('report.md','report.html'):
        text=(tmp_path/'rendered'/name).read_text()
        assert 'may still identify' in text
        assert "I don't know" not in text


def test_checksum_symlink_refused(tmp_path):
    out=report(tmp_path)
    checksum=(out/'checksums.json').read_bytes()
    (out/'checksums.json').unlink()
    external=tmp_path/'external.json';external.write_bytes(checksum)
    (out/'checksums.json').symlink_to(external)
    with pytest.raises(IntegrityError):
        verify_artifacts(out)
