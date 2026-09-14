"""Fail-closed execution-gate tests; no analytical comparisons are invoked."""
import importlib.util,json,sys
from pathlib import Path
import pytest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/run_pairs.py'
spec=importlib.util.spec_from_file_location('pilot2_pair_runner',SCRIPT)
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

def fixture(root):
    (root/'protocol').mkdir()
    prepared=root/'prepared/paired';(prepared/'scored/datasets').mkdir(parents=True)
    doc=prepared/'scored/datasets/case.json'
    doc.write_text(json.dumps({'pairs':[{'split':'development'}],'texts':[]}))
    (prepared/'preparation-summary.json').write_text(json.dumps({'datasets':[{'path':'scored/datasets/case.json','sha256':runner.sha(doc)}]}))
    frozen={'status':'frozen','scoring_authorized':True,'files':{},'paired_prepared_directory':'prepared/paired',
            'implementation_fingerprint':runner.implementation_identity()[0],
            'analysis_config_sha256':runner.digest(runner.AnalysisConfig.from_toml().analytical())}
    path=root/'protocol/scoring-freeze.json';path.write_text(json.dumps(frozen))
    return path,frozen,doc

def test_missing_gate_cannot_score(tmp_path):
    with pytest.raises(FileNotFoundError):runner.validate_freeze(tmp_path)

def test_registered_but_unauthorized_gate_cannot_score(tmp_path):
    path,frozen,_=fixture(tmp_path);frozen['scoring_authorized']=False;path.write_text(json.dumps(frozen))
    with pytest.raises(ValueError,match='not authorized'):runner.validate_freeze(tmp_path)

def test_changed_frozen_file_cannot_score(tmp_path):
    path,frozen,doc=fixture(tmp_path);frozen['files']={str(doc.relative_to(tmp_path)):runner.sha(doc)}
    path.write_text(json.dumps(frozen));doc.write_text('{}')
    with pytest.raises(ValueError,match='file mismatch'):runner.validate_freeze(tmp_path)

def test_different_implementation_cannot_score(tmp_path):
    path,frozen,_=fixture(tmp_path);frozen['implementation_fingerprint']='0'*64;path.write_text(json.dumps(frozen))
    with pytest.raises(ValueError,match='source mismatch'):runner.validate_freeze(tmp_path)

def test_confirmation_reference_cannot_score(tmp_path):
    _,_,doc=fixture(tmp_path)
    doc.write_text(json.dumps({'pairs':[{'split':'development'}],'texts':[{'input':'../../confirmation/secret.jsonl','manifest':'../../confirmation/secret.json'}]}))
    summary=doc.parents[2]/'preparation-summary.json'
    summary.write_text(json.dumps({'datasets':[{'path':'scored/datasets/case.json','sha256':runner.sha(doc)}]}))
    with pytest.raises(ValueError,match='Confirmation'):runner.validate_freeze(tmp_path)
