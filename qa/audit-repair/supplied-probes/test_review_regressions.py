"""Additional acceptance tests for the independent AHAS review.

Run from the repository with PYTHONPATH=src and AHAS_REPO set to its root.
The first two tests deliberately fail against the reviewed 1.0.0 source.
The full analysis round-trip test is opt-in and requires ALL pinned dependencies.
Do not mark these xfail to close the findings. This is test code, not a patch.
"""
import json
import os
from pathlib import Path
import pytest

ROOT = Path(os.environ.get('AHAS_REPO', '.')).resolve()


def _reverse_mapping_order(value):
    if isinstance(value, dict):
        return {key: _reverse_mapping_order(item) for key, item in reversed(list(value.items()))}
    if isinstance(value, list):
        return [_reverse_mapping_order(item) for item in value]
    return value


def test_render_does_not_depend_on_mapping_insertion_order():
    from account_history_analyzer.reporting import render_markdown, render_html
    from account_history_analyzer.io import canonical_bytes
    directory = ROOT / 'output/arithmetic'
    result = json.loads((directory/'results.json').read_bytes())
    evidence = [json.loads(line) for line in (directory/'evidence.jsonl').read_text().splitlines()]
    windows = [json.loads(line) for line in (directory/'windows.jsonl').read_text().splitlines()]
    reordered = _reverse_mapping_order(result)
    assert canonical_bytes(result) == canonical_bytes(reordered)
    assert render_markdown(result, evidence, windows=windows) == render_markdown(reordered, evidence, windows=windows)
    assert render_html(result, evidence, windows=windows) == render_html(reordered, evidence, windows=windows)


def test_one_hyperlink_with_a_mixed_url_label_counts_once():
    from account_history_analyzer.config import AnalysisConfig
    from account_history_analyzer.text import preprocess
    record = {'id': 'review-link', 'kind': 'comment', 'status': 'present',
              'text': '[Read https://example.org for details](https://example.org)'}
    manifest = {'text_format': 'markdown', 'default_language': 'en'}
    result = preprocess(record, manifest, AnalysisConfig.from_toml())
    assert len(result['links']) == 1
    assert result['links'][0]['hostname'] == 'example.org'


@pytest.mark.skipif(os.environ.get('AHAS_RUN_LARGE_ROUNDTRIP') != '1',
                    reason='Opt-in full-pipeline benchmark; requires the pinned Python 3.12 environment')
def test_supplied_benchmark_full_artifact_round_trip(tmp_path):
    from account_history_analyzer.config import AnalysisConfig
    from account_history_analyzer.io import load_snapshot
    from account_history_analyzer.pipeline import analyze
    from account_history_analyzer.artifacts import write_artifacts
    from account_history_analyzer.verification import verify
    import subprocess
    import sys
    config = AnalysisConfig.from_toml(ROOT/'config/default.toml')
    source = ROOT/'benchmarks/input/records.jsonl'
    manifest = ROOT/'benchmarks/input/snapshot.json'
    snapshot = load_snapshot(source, manifest, config)
    result = analyze(snapshot, config)
    assert result.exit_code == 0
    directory = tmp_path/'analysis'
    write_artifacts(result, directory)
    # Explicit recomputation must accept the complete generated artifacts.
    assert verify(source, manifest, directory, recompute=True)['status'] == 'reproduced'
    rerender = tmp_path/'rerender'
    command = [sys.executable, '-m', 'account_history_analyzer', 'render',
               '--results', str(directory/'results.json'), '--artifacts', str(directory),
               '--format', 'both', '--excerpts', 'included', '--out', str(rerender)]
    execution = subprocess.run(command, capture_output=True, text=True, timeout=300)
    assert execution.returncode == 0, execution.stderr
    for name in ['report.md', 'report.html', 'activity_daily.svg', 'activity_hourly.svg',
                 'eligible_word_volume.svg', 'surface_features.svg', 'adjacent_distances.svg']:
        assert (directory/name).read_bytes() == (rerender/name).read_bytes(), name
