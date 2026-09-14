"""Public evaluation command, clean exit contracts and actual generated artifacts."""
import json
from pathlib import Path
import subprocess
import sys

from account_history_analyzer.io import sha256_bytes

ROOT=Path(__file__).resolve().parents[1]


def subset(tmp_path):
    folder=tmp_path/'fixtures';folder.mkdir()
    names=['arithmetic.jsonl','arithmetic.snapshot.json','arithmetic.truth.json','numerical_oracles.json']
    entries=[]
    for name in names:
        data=(ROOT/'fixtures'/name).read_bytes()
        (folder/name).write_bytes(data)
        entries.append({'file':name,'bytes':len(data),'sha256':sha256_bytes(data)})
    (folder/'fixture_index.json').write_text(json.dumps({'fixture_version':'1.0.0','files':entries}))
    return folder


def command(*args):
    return subprocess.run([sys.executable,'-m','account_history_analyzer','evaluate',*map(str,args)],capture_output=True)


def test_evaluate_synthetic_cli_actual_reports_and_failed_check_exit(tmp_path):
    fixtures=subset(tmp_path)
    out=tmp_path/'evaluation'
    proc=command('--suite','synthetic','--fixtures',fixtures,'--out',out)
    assert proc.returncode==0,proc.stderr
    assert json.loads(proc.stdout)['status']=='passed'
    value=json.loads((out/'evaluation.json').read_bytes())
    assert value['fixtures'][0]['summary']['retained_words']==36
    assert value['dataset']['shipped_scenarios_complete'] is False
    assert 'not_established' in (out/'report.md').read_text()
    checks=json.loads((out/'checksums.json').read_bytes())
    assert all(sha256_bytes((out/name).read_bytes())==expected for name,expected in checks.items())
    truth=fixtures/'arithmetic.truth.json';data=json.loads(truth.read_bytes())
    data['retained_word_count_total']=999
    truth.write_text(json.dumps(data))
    failed=command('--suite','synthetic','--fixtures',fixtures,'--out',tmp_path/'failed')
    assert failed.returncode==3,failed.stderr
    assert json.loads(failed.stdout)['status']=='failed'
    assert (tmp_path/'failed/evaluation.json').exists()


def test_external_missing_dataset_and_ambiguous_arguments_are_input_errors(tmp_path):
    for args in [('--suite','paired_text','--dataset',tmp_path/'missing.json'),
                 ('--suite','synthetic'),
                 ('--suite','account_stream','--fixtures','fixtures')]:
        proc=command(*args,'--out',tmp_path/'unwritten')
        assert proc.returncode==2,proc.stderr
        assert not proc.stdout
        assert not (tmp_path/'unwritten').exists()
