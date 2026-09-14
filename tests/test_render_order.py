"""AUD-002: presentation depends on values and ordered lists, not map history."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

from account_history_analyzer.artifacts import write_artifacts
from account_history_analyzer.charts import CHART_NAMES, render_charts
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.evaluation_reporting import render_evaluation, write_evaluation
from account_history_analyzer.evaluation_synthetic import evaluate_synthetic
from account_history_analyzer.io import canonical_bytes, freeze, load_snapshot, sha256_bytes, thaw
from account_history_analyzer.pipeline import analyze
from account_history_analyzer.reporting import json_text, md_text, render_html, render_markdown

ROOT = Path(__file__).resolve().parents[1]


def permute_maps(value, seed):
    """Permute every map recursively while leaving every ordered array intact."""
    generator = random.Random(seed)
    def visit(item):
        if isinstance(item, Mapping):
            keys = list(item)
            generator.shuffle(keys)
            return {key: visit(item[key]) for key in keys}
        if isinstance(item, (list, tuple)):
            return [visit(child) for child in item]
        return item
    return visit(value)


def make_writing_analysis(directory, *, excerpts='included'):
    directory.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'fixtures/constructed_style_shift.jsonl'
    rows = source.read_bytes().splitlines()
    # A bounded subset gives eight qualified windows and ranked source examples.
    # No truth file is read or passed to analysis. Reuse word guards isolate the
    # renderer test from expensive pair matching, which has its own regressions.
    selected = rows[:32] + rows[160:192]
    records = directory / 'records.jsonl'
    records.write_bytes(b'\n'.join(selected) + b'\n')
    cfg = AnalysisConfig.from_mapping({
        'windows': {'target_words': 500},
        'style': {'minimum_comparison_words_per_side': 500},
        'reuse': {'minimum_near_duplicate_words': 100000, 'minimum_containment_shorter_words': 100000},
        'report': {'excerpts': excerpts},
    })
    result = analyze(load_snapshot(records, ROOT / 'fixtures/constructed_style_shift.snapshot.json', cfg), cfg)
    assert result.results['modules']['style']['payload']['comparisons']
    assert result.results['modules']['style']['payload']['changes'][0]['boundaries']
    assert result.files['evidence.jsonl'] and result.files['windows.jsonl']
    return result


@pytest.fixture(scope='module')
def writing_analysis(tmp_path_factory):
    return make_writing_analysis(tmp_path_factory.mktemp('render-writing'))


def objects(analysis):
    return (thaw(analysis.results),
            [json.loads(line) for line in analysis.files['evidence.jsonl'].splitlines()],
            [json.loads(line) for line in analysis.files['windows.jsonl'].splitlines()])


@pytest.mark.parametrize('seed', [0, 7, 383])
@pytest.mark.parametrize('excerpts', ['included', 'none'])
def test_AUD002_nested_mapping_permutations_leave_all_reports_identical(writing_analysis, seed, excerpts):
    original = objects(writing_analysis)
    changed = permute_maps(original, seed)
    assert canonical_bytes(original) == canonical_bytes(changed)
    before = canonical_bytes(changed)
    for renderer in (render_markdown, render_html):
        expected = renderer(original[0], original[1], windows=original[2], excerpts=excerpts)
        assert renderer(changed[0], changed[1], windows=changed[2], excerpts=excerpts) == expected
    assert render_charts(changed[0], changed[2]) == render_charts(original[0], original[2])
    assert canonical_bytes(changed) == before


@pytest.mark.parametrize('excerpts', ['included', 'none'])
def test_AUD002_immutable_results_and_sequences_match_loaded_json(writing_analysis, excerpts):
    plain = objects(writing_analysis)
    immutable = freeze(plain)
    for renderer in (render_markdown, render_html):
        assert renderer(immutable[0], immutable[1], windows=immutable[2], excerpts=excerpts) == renderer(
            plain[0], plain[1], windows=plain[2], excerpts=excerpts)
    assert render_charts(immutable[0], immutable[2]) == render_charts(plain[0], plain[2])


@pytest.mark.parametrize('excerpts', ['included', 'none'])
def test_AUD002_initial_publication_saved_results_and_cli_rerender_match(writing_analysis, tmp_path, excerpts):
    # Publication takes the mode from canonical resolved configuration, never
    # from an untrusted operational receipt. Exercise genuine mode-specific runs.
    analysis = writing_analysis if excerpts == 'included' else make_writing_analysis(tmp_path / 'input', excerpts=excerpts)
    original = tmp_path / 'original'
    write_artifacts(analysis, original)
    results = json.loads((original / 'results.json').read_bytes())
    evidence = [json.loads(line) for line in (original / 'evidence.jsonl').read_bytes().splitlines()]
    windows = [json.loads(line) for line in (original / 'windows.jsonl').read_bytes().splitlines()]
    rerendered = {
        'report.md': render_markdown(results, evidence, windows=windows, excerpts=excerpts).encode(),
        'report.html': render_html(results, evidence, windows=windows, excerpts=excerpts).encode(),
        **render_charts(results, windows),
    }
    assert all((original / name).read_bytes() == data for name, data in rerendered.items())
    derivative = tmp_path / 'derivative'
    command = [sys.executable, '-m', 'account_history_analyzer', 'render', '--results', str(original / 'results.json'),
        '--artifacts', str(original), '--format', 'both', '--excerpts', excerpts, '--out', str(derivative)]
    completed = subprocess.run(command, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr.decode()
    assert json.loads(completed.stdout)['analytical_results_unchanged'] is True
    for name in ('report.md', 'report.html', *CHART_NAMES):
        assert (derivative / name).read_bytes() == (original / name).read_bytes(), name


def test_AUD002_semantic_list_order_is_preserved(writing_analysis):
    results, evidence, windows = objects(writing_analysis)
    comparisons = results['modules']['style']['payload']['comparisons'][:2]
    assert len(comparisons) == 2
    results['modules']['style']['payload']['comparisons'] = comparisons[::-1]
    text = render_markdown(results, evidence, windows=windows)
    markers = [f'<details><summary>Comparison {md_text(item["comparison_id"])}' for item in comparisons]
    assert text.index(markers[1]) < text.index(markers[0])
    finding = next(item for item in results['findings'] if len(item.get('values', {}).get('changing_features', [])) >= 2)
    changing = finding['values']['changing_features']
    # Ranking is already supplied by analysis, including ties. The renderer must
    # not sort these rows while making unordered maps deterministic.
    finding['values']['changing_features'] = changing[::-1]
    rendered = render_markdown(results, evidence, windows=windows)
    assert rendered != text
    for feature in changing:
        assert md_text(feature['feature_id']) in rendered
    source_example = {'z': [{'rank': 2}, {'rank': 1}], 'a': {'later': 2, 'earlier': 1}}
    assert json_text(freeze(source_example)) == '{"a": {"earlier": 1, "later": 2}, "z": [{"rank": 2}, {"rank": 1}]}'


@pytest.fixture(scope='module')
def synthetic_evaluation(tmp_path_factory):
    folder = tmp_path_factory.mktemp('render-evaluation')
    entries = []
    for name in ('arithmetic.jsonl', 'arithmetic.snapshot.json', 'arithmetic.truth.json', 'numerical_oracles.json'):
        data = (ROOT / 'fixtures' / name).read_bytes()
        (folder / name).write_bytes(data)
        entries.append({'file': name, 'bytes': len(data), 'sha256': sha256_bytes(data)})
    (folder / 'fixture_index.json').write_bytes(canonical_bytes({'fixture_version': '1.0.0', 'files': entries}))
    actual = evaluate_synthetic(folder)
    # Structured check values are expressly allowed by the evaluator contract.
    # This formatter regression exercises nested maps, arrays, nulls and text.
    value = {'z': [None, {'b': '<script>inert</script>', 'a': 1}], 'a': {'y': 2, 'x': 3}}
    actual['numerical_checks'].append({'check_id': 'structured_value_contract', 'status': 'passed',
        'evidence_level': 'numerical_correctness', 'expected': value, 'observed': deepcopy(value), 'reason': None, 'tolerance': None})
    actual['check_counts']['passed'] += 1
    return actual


@pytest.mark.parametrize('suite', ['synthetic', 'paired_text', 'account_stream'])
def test_AUD002_all_evaluator_paths_preserve_nested_map_identity(synthetic_evaluation, tmp_path, suite):
    if suite == 'synthetic':
        evaluation = deepcopy(synthetic_evaluation)
    else:
        # External formatter paths serialize the complete supplied metric
        # object. These hand-constructed values test formatting, not accuracy.
        evaluation = {'format': suite, 'status': 'evaluated',
            'label_definition': 'Formatter test values only; no external validation.',
            'partitions': {'evaluation': {'rows': [{'id': 'second', 'score': None}, {'id': 'first', 'score': 0.5}],
                'metrics': {'coverage': {'observed': 2, 'abstained': 1}, 'ranking': {'value': None, 'reason': 'not_evaluated'}}}},
            'provenance': '</details>```<script>inert</script>',
            'dataset': {'id': 'local'}, 'identities': {'not_displayed': {}}}
    changed = permute_maps(evaluation, 2025)
    assert canonical_bytes(evaluation) == canonical_bytes(changed)
    expected = render_evaluation(evaluation)
    assert render_evaluation(changed) == expected
    assert render_evaluation(freeze(evaluation)) == expected
    assert render_evaluation(json.loads(canonical_bytes(evaluation))) == expected
    output = tmp_path / 'evaluation'
    write_evaluation(freeze(changed), output, runtime_seconds=0)
    assert (output / 'report.md').read_text() == expected
    assert render_evaluation(json.loads((output / 'evaluation.json').read_bytes())) == expected
    if suite != 'synthetic':
        assert '<script>' not in expected
        assert '\\u003cscript\\u003e' in expected


@pytest.fixture(scope='module')
def arithmetic_analysis():
    return analyze(load_snapshot(ROOT / 'fixtures/arithmetic.jsonl', ROOT / 'fixtures/arithmetic.snapshot.json'))


@pytest.mark.parametrize('reason', [None, 'max_work_units', 'max_index_postings', 'max_evidence_tokens',
                                  'max_evidence_codepoints', 'max_candidate_pairs'])
def test_reuse_resource_counters_and_incomplete_search_are_visible(arithmetic_analysis, reason):
    results, evidence, windows = objects(arithmetic_analysis)
    reuse = results['modules']['reuse']['payload']
    usage = {'method': 'reuse_work_units_v1', 'work_units': 101, 'index_postings': 37,
             'evidence_tokens': 19, 'evidence_codepoints': 73}
    limits = {'max_work_units': 200, 'max_index_postings': 100,
              'max_evidence_tokens': 100, 'max_evidence_codepoints': 300}
    reuse.update(resource_usage=usage, resource_limits=limits, resource_limit_reason=reason,
                 budget_complete=reason is None, candidate_count_is_lower_bound=reason in {'max_candidate_pairs', 'max_index_postings'})
    if reason is not None:
        reuse.update(pairs=[], connected_groups=[], near_status='resource_limit')
        results['modules']['reuse']['status'] = 'resource_limit'
    expected = render_markdown(results, evidence, windows=windows)
    assert 'Deterministic near-reuse resource accounting: '+md_text(usage['method']) in expected
    assert 'Exhaustion reason: '+md_text(reason or 'none') in expected
    for key in sorted(usage):
        if key != 'method':
            assert f'| {md_text(key)} | {usage[key]} | {limits["max_"+key]} |' in expected
    if reason is not None:
        assert 'Qualifying shingle pairs: not available (incomplete near-reuse search)' in expected
        assert 'Exact equivalence groups remain available' in expected
        assert 'Showing 0 of 0 pairs' not in expected
        assert 'Connected reuse groups: 0' not in expected
    changed = permute_maps([results, evidence, windows], 998)
    assert render_markdown(changed[0], changed[1], windows=changed[2]) == expected
    assert render_html(changed[0], changed[1], windows=changed[2]) == render_html(results, evidence, windows=windows)


def test_legacy_reuse_payload_without_work_counters_remains_renderable(arithmetic_analysis):
    results, evidence, windows = objects(arithmetic_analysis)
    for key in ('resource_usage', 'resource_limits', 'resource_limit_reason'):
        results['modules']['reuse']['payload'].pop(key, None)
    for renderer in (render_markdown, render_html):
        rendered = renderer(results, evidence, windows=windows)
        assert 'Deterministic near-reuse resource accounting' not in rendered
        assert 'Exact equivalence groups:' in rendered
