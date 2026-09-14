"""Whole-output reproduction in independent interpreters and relocated inputs."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def run_analysis(records, manifest, destination, cwd, hash_seed, timezone, config=None):
    args = [sys.executable, '-m', 'account_history_analyzer', 'analyze', '--input', str(records),
            '--manifest', str(manifest), '--out', str(destination)]
    if config is not None:
        args += ['--config', str(config), '--allow-toy-reference']
    env = dict(os.environ, PYTHONHASHSEED=str(hash_seed), TZ=timezone)
    run = subprocess.run(args, cwd=cwd, env=env, capture_output=True)
    assert run.returncode == 0, run.stderr.decode()
    assert json.loads(run.stdout)['status'] == 'complete'
    return {p.name:p.read_bytes() for p in destination.iterdir() if p.name not in {'ingest_receipt.json','run_receipt.json'}}


def test_OUT_09_10_11_process_identity_across_environment_and_row_order(tmp_path):
    rows = [json.loads(line) for line in (ROOT/'fixtures/arithmetic.jsonl').read_text().splitlines()]
    shuffled = tmp_path/'innocuous-renamed-input.jsonl'
    shuffled.write_text('\n'.join(json.dumps(dict(reversed(list(row.items()))), separators=(', ', ': ')) for row in reversed(rows))+'\n')
    other_cwd = tmp_path/'different-cwd'
    other_cwd.mkdir()
    manifest = ROOT/'fixtures/arithmetic.snapshot.json'
    first = run_analysis(ROOT/'fixtures/arithmetic.jsonl',manifest,tmp_path/'first',ROOT,1,'UTC')
    second = run_analysis(shuffled,manifest,tmp_path/'second',other_cwd,9123,'Pacific/Honolulu')
    assert first == second
    one = json.loads((tmp_path/'first/ingest_receipt.json').read_bytes())
    two = json.loads((tmp_path/'second/ingest_receipt.json').read_bytes())
    assert one != two


def test_IN_16_process_reference_relocation_preserves_analytical_bytes(tmp_path):
    folders = [tmp_path/'left',tmp_path/'right']
    for folder in folders:
        folder.mkdir()
        (folder/'ref.json').write_bytes((ROOT/'design_examples/delta_reference_toy.json').read_bytes())
        (folder/'settings.toml').write_text('[delta]\nreference_path="ref.json"\n')
    inputs = ROOT/'fixtures/arithmetic.jsonl', ROOT/'fixtures/arithmetic.snapshot.json'
    first = run_analysis(*inputs,folders[0]/'report',folders[0],19,'UTC',folders[0]/'settings.toml')
    second = run_analysis(*inputs,folders[1]/'report',folders[1],283,'Asia/Tokyo',folders[1]/'settings.toml')
    assert first == second
