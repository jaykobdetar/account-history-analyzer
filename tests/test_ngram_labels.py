"""AHAS-REPORT-005: rendered n-gram labels preserve exact source strings.

The oracle decodes actual HTML table-cell text as JSON. These formatter tests
never recalculate features or infer analytic meaning from the adversarial labels.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

from hypothesis import given, settings, strategies as st
from markdown_it import MarkdownIt
import pytest

from account_history_analyzer.reporting import _table, md_text, ngram_label, render_html, render_markdown

ROOT = Path(__file__).resolve().parents[1]
SAVED_REPORT = ROOT / 'output/audit-repair/constructed_style_shift'
CASES = (
    '', ' ', '  ', '   ', ' th', 'th ', ' the ', 'a  b', 'a   b',
    '\t', '\n', '\r', '\r\n', '\t \n', 'a\tb\nc',
    '"', "'", '\\', '\\u0020', '\\t', '\\n', '\\"', '\\\\',
    '|', 'a|b', '<tag>', '</td><script>label_only()</script>', '&',
    '&nbsp;', '&#32;', '&quot;', '*emphasis*', '_emphasis_', '`code`',
    '[]()', '[label](javascript:alert(1))',
    '\u00a0', 'a\u00a0b', '\u200b', '\u200c', '\u200d', '\ufeff',
    '\u202e', '\u202aabc\u202c', '\u2066abc\u2069', '\u2028', '\u2029',
    '\u00e9', 'e\u0301', '\U0001f642', '\U0001f469\u200d\U0001f4bb',
    '\\ud83d\\ude42', '\\u00a0', '\\u200b', '\\u202e',
)
CONTRIBUTION_CONTEXT = re.compile(
    r'^(cosine_distance_v1|function_word_js_v1|classic_delta_v1), ([a-zA-Z0-9_]+)(?:, n=(\d+))?:'
)


class ParsedTables(HTMLParser):
    """Keep literal cell text and surrounding comparison/method identifiers."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.text = []
        self.attributes = []
        self.tags = []
        self._paragraph = None
        self._last_paragraph = ''
        self._summary = None
        self._comparison = None
        self._table = None
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend((tag, key, value) for key, value in attrs)
        if tag == 'p':
            self._paragraph = []
        elif tag == 'summary':
            self._summary = []
        elif tag == 'table':
            self._table = {'comparison': self._comparison, 'context': self._last_paragraph, 'rows': []}
        elif tag == 'tr':
            self._row = []
        elif tag == 'td':
            self._cell = []

    def handle_data(self, data):
        self.text.append(data)
        if self._paragraph is not None:
            self._paragraph.append(data)
        if self._summary is not None:
            self._summary.append(data)
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag == 'p' and self._paragraph is not None:
            self._last_paragraph = ''.join(self._paragraph)
            self._paragraph = None
        elif tag == 'summary' and self._summary is not None:
            summary = ''.join(self._summary)
            if summary.startswith('Comparison '):
                self._comparison = summary.removeprefix('Comparison ').split(' — ', 1)[0]
            self._summary = None
        elif tag == 'td' and self._cell is not None:
            if self._row is not None:
                self._row.append(''.join(self._cell))
            self._cell = None
        elif tag == 'tr' and self._row is not None:
            if self._table is not None and self._row:
                self._table['rows'].append(self._row)
            self._row = None
        elif tag == 'table' and self._table is not None:
            self.tables.append(self._table)
            self._table = None


def parse_html(document):
    parsed = ParsedTables()
    parsed.feed(document)
    parsed.close()
    return parsed


def markdown_html(markdown):
    return MarkdownIt('commonmark', {'html': True, 'linkify': False,
                                  'typographer': False}).enable('table').render(markdown)


def structural_digest(value):
    # Independent, within-test mutation detection for already parsed plain JSON.
    # This is not a replacement for the product's canonical serialization.
    data = json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True,
                      separators=(',', ':')).encode('ascii')
    return hashlib.sha256(data).hexdigest()


def displayed_labels(values):
    markdown = '\n'.join(_table(['Feature'], [[md_text(ngram_label(value))] for value in values]))
    parsed = parse_html(markdown_html(markdown))
    assert len(parsed.tables) == 1
    assert all(len(row) == 1 for row in parsed.tables[0]['rows'])
    assert set(parsed.tags) <= {'table', 'thead', 'tbody', 'tr', 'th', 'td'}
    assert parsed.attributes == []
    return [row[0] for row in parsed.tables[0]['rows']]


@pytest.mark.parametrize('original', CASES)
def test_actual_markdown_table_label_decodes_to_exact_original_string(original):
    label, = displayed_labels([original])
    assert json.loads(label) == original
    assert label.startswith('"') and label.endswith('"')
    assert label.isascii()
    assert all(not character.isspace() for character in label)


def test_all_adversarial_labels_are_distinct_after_markdown_and_html_parsing():
    assert len(CASES) == len(set(CASES))
    labels = displayed_labels(CASES)
    assert len(labels) == len(CASES)
    assert len(set(labels)) == len(labels)
    assert [json.loads(label) for label in labels] == list(CASES)


@given(st.lists(st.sampled_from(CASES), min_size=1, max_size=4).map(''.join))
@settings(max_examples=100, deadline=None)
def test_composed_escape_and_unicode_sequences_survive_the_real_table_parser(original):
    label, = displayed_labels([original])
    assert json.loads(label) == original
    assert label.isascii() and not any(character.isspace() for character in label)


@pytest.fixture(scope='module')
def saved_style_report():
    if SAVED_REPORT.exists():
        # Audit checkout: exercise the actual supplied saved measurements.
        with (SAVED_REPORT / 'results.json').open(encoding='utf-8') as handle:
            results = json.load(handle)
        exported = []
        for name in ('evidence.jsonl', 'windows.jsonl'):
            with (SAVED_REPORT / name).open(encoding='utf-8') as handle:
                exported.append([json.loads(line) for line in handle if line.strip()])
        return results, *exported

    # Source distributions and the reference container omit historical reports.
    # Analyze the same shipped input once instead; no evaluator truth is read.
    from account_history_analyzer import analyze, load_snapshot
    from account_history_analyzer.io import thaw
    analysis = analyze(load_snapshot(ROOT / 'fixtures/constructed_style_shift.jsonl',
                                     ROOT / 'fixtures/constructed_style_shift.snapshot.json'))
    assert analysis.exit_code == 0
    return (thaw(analysis.results),
            [json.loads(line) for line in analysis.files['evidence.jsonl'].splitlines()],
            [json.loads(line) for line in analysis.files['windows.jsonl'].splitlines()])


def full_document(report, output, *, excerpts):
    results, evidence, windows = report
    if output == 'markdown':
        source = render_markdown(results, evidence, windows=windows, excerpts=excerpts)
        return source, markdown_html(source)
    source = render_html(results, evidence, windows=windows, excerpts=excerpts)
    return source, source


def contribution_tables(parsed):
    found = {}
    for table in parsed.tables:
        match = CONTRIBUTION_CONTEXT.match(table['context'])
        if match is not None:
            method, view, n = match.groups()
            key = (table['comparison'], method, view, int(n) if n is not None else None)
            assert key not in found
            found[key] = table['rows']
    return found


@contextmanager
def substituted_labels(report, labels):
    """Temporarily change only existing exported cosine feature_id values."""
    results, _, _ = report
    comparison = results['modules']['style']['payload']['comparisons'][0]
    before = deepcopy(comparison)
    originals = []
    expected = {}
    iterator = iter(labels)
    used = 0
    try:
        for distance in comparison['distances']:
            if distance['method_id'] != 'cosine_distance_v1':
                continue
            key = (comparison['comparison_id'], distance['method_id'], distance['view'], distance['n'])
            expected[key] = []
            for contribution in distance['contributions'][:10]:
                replacement = next(iterator, contribution['feature_id'])
                originals.append((contribution, contribution['feature_id']))
                contribution['feature_id'] = replacement
                expected[key].append(replacement)
                used += 1
        assert used >= len(labels), 'The genuine report must expose enough preview slots for the corpus'
        yield expected
    finally:
        for contribution, original in originals:
            contribution['feature_id'] = original
        assert comparison == before


@pytest.mark.parametrize('output', ['markdown', 'html'])
def test_full_saved_report_retains_ngram_labels_and_existing_preview_order(saved_style_report, output):
    results, _, _ = saved_style_report
    before = structural_digest(results)
    _, document = full_document(saved_style_report, output, excerpts='included')
    actual = contribution_tables(parse_html(document))
    comparisons = {item['comparison_id']: item for item in results['modules']['style']['payload']['comparisons']}
    cosine_rows = 0
    non_cosine_rows = 0
    for (comparison_id, method, view, n), rows in actual.items():
        comparison = comparisons[comparison_id]
        distance = next(item for item in comparison['distances']
                        if (item['method_id'], item['view'], item['n']) == (method, view, n))
        source = distance['contributions'][:10]
        assert len(rows) == len(source)
        labels = [row[0] for row in rows]
        if method == 'cosine_distance_v1':
            assert [json.loads(label) for label in labels] == [item['feature_id'] for item in source]
            assert len(set(labels)) == len(labels)
            cosine_rows += len(rows)
        else:
            # The reversible source-label representation applies only to cosine
            # coordinates; registered function/Delta feature labels stay plain.
            assert labels == [item['feature_id'] for item in source]
            non_cosine_rows += len(rows)
    assert cosine_rows > 0 and non_cosine_rows > 0
    assert structural_digest(results) == before


@pytest.mark.parametrize('output', ['markdown', 'html'])
def test_full_report_adversarial_labels_preserve_order_rates_and_inert_text(saved_style_report, output):
    results, _, _ = saved_style_report
    before = structural_digest(results)
    _, initial_document = full_document(saved_style_report, output, excerpts='included')
    initial = parse_html(initial_document)
    initial_tables = contribution_tables(initial)
    with substituted_labels(saved_style_report, CASES) as expected:
        mutated_digest = structural_digest(results)
        _, changed_document = full_document(saved_style_report, output, excerpts='included')
        changed = parse_html(changed_document)
        actual = contribution_tables(changed)
        assert actual.keys() == initial_tables.keys()
        assert changed.attributes == initial.attributes
        assert changed.tags == initial.tags
        for key, labels in expected.items():
            assert [json.loads(row[0]) for row in actual[key]] == labels
            assert [row[1:] for row in actual[key]] == [row[1:] for row in initial_tables[key]]
        assert len(set(label for labels in expected.values() for label in labels)) >= len(CASES)
        assert structural_digest(results) == mutated_digest
    assert structural_digest(results) == before


@pytest.mark.parametrize('output', ['markdown', 'html'])
def test_excerpt_none_omits_ngram_strings_from_text_attributes_and_serialized_output(saved_style_report, output):
    before_source, before_document = full_document(saved_style_report, output, excerpts='none')
    before = parse_html(before_document)
    marker = 'AHAS_PRIVATE_NGRAM_REPORT005_'
    labels = [f'{marker}{index:02d}:{value}' for index, value in enumerate(CASES)]
    with substituted_labels(saved_style_report, labels):
        source, document = full_document(saved_style_report, output, excerpts='none')
        parsed = parse_html(document)
        assert source == before_source
        assert document == before_document
        assert parsed.text == before.text
        assert parsed.attributes == before.attributes
        assert marker not in source and marker not in document
        assert all(marker not in item for item in parsed.text)
        assert all(marker not in (value or '') for _, _, value in parsed.attributes)
        assert not any(key[1] == 'cosine_distance_v1' for key in contribution_tables(parsed))
        assert 'Source excerpts omitted' in ''.join(parsed.text)
