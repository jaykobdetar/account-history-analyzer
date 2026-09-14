"""Report contract checks using exported observations, including visual regressions."""
from __future__ import annotations

from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from account_history_analyzer.charts import CHART_NAMES, _svg, render_charts
from account_history_analyzer.io import canonical_bytes, load_snapshot, thaw
from account_history_analyzer.pipeline import analyze
from account_history_analyzer.reporting import render_html, render_markdown

ROOT = Path(__file__).resolve().parents[1]
SVG = '{http://www.w3.org/2000/svg}'


@pytest.fixture(scope='module')
def arithmetic():
    analysis = analyze(load_snapshot(ROOT/'fixtures/arithmetic.jsonl', ROOT/'fixtures/arithmetic.snapshot.json'))
    return (thaw(analysis.results),
            [json.loads(line) for line in analysis.files['evidence.jsonl'].splitlines()],
            [json.loads(line) for line in analysis.files['windows.jsonl'].splitlines()])


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.ids, self.hrefs, self.tags, self.requests, self.text = [], [], [], [], []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append(tag)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if 'href' in attrs:
            self.hrefs.append(attrs['href'])
        self.requests.extend((tag, key) for key in attrs if key in {'src', 'srcset', 'poster', 'onload', 'onerror'})

    def handle_data(self, text):
        self.text.append(text)


def test_rendered_data_matches_hand_checkable_arithmetic(arithmetic):
    results, evidence, windows = arithmetic
    markdown = render_markdown(results, evidence, windows=windows)
    document = Document(render_html(results, evidence, windows=windows))
    content = ' '.join(document.text)
    assert '| Retained word tokens | 36 |' in markdown
    assert '| Mean / median (seconds) | 36 / 40 |' in markdown
    assert '| Population variance (seconds squared) | 504 |' in markdown
    assert 'timestamp gap does not establish sleep' in content
    assert 'not_established' in content
    assert document.tags.count('svg') == 5
    assert not set(document.tags) & {'script', 'img', 'iframe', 'object', 'form'}
    assert document.requests == []
    assert len(document.ids) == len(set(document.ids))
    assert all(href[1:] in document.ids for href in document.hrefs if href.startswith('#'))
    assert 'evidence.jsonl' not in document.hrefs


def test_chart_metadata_is_exact_exported_data(arithmetic):
    results, _, windows = arithmetic
    charts = render_charts(results, windows)
    assert tuple(charts) == CHART_NAMES
    activity = results['modules']['activity']['payload']
    daily = ET.fromstring(charts['activity_daily.svg'])
    data = json.loads(daily.find('.//'+SVG+'metadata').text)
    assert data['values'] == [row['event_count'] for row in activity['events_per_day']] == [6]
    assert data['labels'] == [row['date'] for row in activity['events_per_day']]
    hourly = ET.fromstring(charts['activity_hourly.svg'])
    data = json.loads(hourly.find('.//'+SVG+'metadata').text)
    assert data['values'] == activity['hour_histogram'] == [6]+[0]*23
    assert data['labels'] == [f'{hour:02d}:00' for hour in range(24)]


def test_chart_plot_header_spacing_regression(arithmetic):
    """A real-browser review found the upper tick overlapping the units line."""
    results, _, windows = arithmetic
    for name in ('activity_daily.svg', 'activity_hourly.svg'):
        root = ET.fromstring(render_charts(results, windows)[name])
        text = root.findall('.//'+SVG+'text')
        unit = next(node for node in text if node.attrib.get('y') == '84')
        ticks = [node for node in text if node.attrib.get('text-anchor') == 'end']
        upper_tick = min(float(node.attrib['y']) for node in ticks)
        assert upper_tick - float(unit.attrib['y']) >= float(unit.attrib['font-size']) + 4
        grid_top = min(float(node.attrib['y1']) for node in root.findall('.//'+SVG+'line'))
        assert grid_top > float(unit.attrib['y']) + float(unit.attrib['font-size'])


def test_missing_chart_values_break_paths_and_remain_null():
    chart = _svg('test.svg', 'Observed trajectory', [{
        'title': 'Actual exported values', 'unit': 'units',
        'labels': ['1','2','3','4','5'], 'values': [1,2,None,3,4],
    }], [])
    root = ET.fromstring(chart)
    paths = root.findall('.//'+SVG+'polyline')
    assert len(paths) == 2
    assert all(len(path.attrib['points'].split()) == 2 for path in paths)
    assert len(root.findall('.//'+SVG+'circle')) == 4
    assert json.loads(root.find('.//'+SVG+'metadata').text)['values'] == [1,2,None,3,4]


def test_source_chart_syntax_does_not_become_template_chart(arithmetic):
    """A source line resembling a report image must stay an actual excerpt."""
    results, _, windows = arithmetic
    prose = '![Actual source syntax](activity_daily.svg)\n<!-- AHAS_CHART:activity_daily.svg -->'
    evidence = [{
        'evidence_id': 'test-source-image', 'source_record_id': 'supplied-record',
        'source_field': 'text', 'role': 'ordinary_context', 'side': None,
        'feature_id': None, 'offset_basis': 'raw_source', 'start': 0,
        'end': len(prose), 'source_line_range': [1,2], 'text': prose,
    }]
    document = Document(render_html(results, evidence, windows=windows))
    assert document.tags.count('svg') == 5
    assert prose in ''.join(document.text)
    assert len(document.ids) == len(set(document.ids))
    assert all(href[1:] in document.ids for href in document.hrefs if href.startswith('#'))
    assert prose not in render_html(results, evidence, windows=windows, excerpts='none')


def test_freeform_implementation_fingerprint_is_inert(arithmetic):
    results, evidence, windows = arithmetic
    results = deepcopy(results)
    value = '`</p><script>window.sourceExecuted=true</script><img src="remote">`'
    results['analysis']['implementation_fingerprint'] = value
    document = Document(render_html(results, evidence, windows=windows))
    assert 'script' not in document.tags
    assert 'img' not in document.tags
    assert not document.requests


def test_rendering_is_deterministic_and_does_not_mutate_measurements(arithmetic):
    results, evidence, windows = arithmetic
    before = canonical_bytes(results)
    for renderer in (render_markdown, render_html):
        assert renderer(results,evidence,windows=windows) == renderer(results,evidence,windows=windows)
        omitted = renderer(results,evidence,windows=windows,excerpts='none')
        assert 'Remaining identifiers' in omitted
    assert render_charts(results,windows) == render_charts(results,windows)
    assert canonical_bytes(results) == before


def test_empty_history_charts_preserve_unavailable_observations():
    analysis = analyze(load_snapshot(ROOT/'fixtures/empty.jsonl', ROOT/'fixtures/empty.snapshot.json'))
    charts = render_charts(analysis.results, [])
    for name in CHART_NAMES:
        root = ET.fromstring(charts[name])
        assert not root.findall('.//'+SVG+'polyline')
        assert not root.findall('.//'+SVG+'circle')
        assert 'No computable observations' in charts[name].decode()
    hourly = ET.fromstring(charts['activity_hourly.svg'])
    assert json.loads(hourly.find('.//'+SVG+'metadata').text)['values'] == [None]*24


def test_invalid_excerpt_setting_is_rejected(arithmetic):
    with pytest.raises(ValueError, match='excerpts'):
        render_markdown(arithmetic[0], excerpts='unexpected')
