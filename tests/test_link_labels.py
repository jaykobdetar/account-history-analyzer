"""AUD-004: hyperlink destinations and URL-shaped label text have distinct roles."""
from types import SimpleNamespace

import pytest

from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.features import measure
from account_history_analyzer.links import analyze_links
from account_history_analyzer.reuse import shingle_set
from account_history_analyzer.style import chargrams
from account_history_analyzer.text import preprocess

CONFIG = AnalysisConfig.from_mapping()


def make(source, *, fmt='markdown', title=None):
    record = {'id': 'supplied', 'kind': 'submission' if title is not None else 'comment',
              'subreddit': None, 'created_utc': None, 'edit_state': 'unknown', 'language': 'en',
              'text': source, 'status': 'present', 'title': title}
    return measure(preprocess(record, {'text_format': fmt, 'default_language': 'en'}, CONFIG), CONFIG)


def texts(result):
    return [segment['text'] for segment in result['segments']]


@pytest.mark.parametrize('label', [
    'Read https://label.test for details',
    '**Read** https://label.test for _details_',
    'Read **https://label.test** for details',
    'Read _https://label.test/a*b*c_ for details',
    'R**ea**d https://label.test for det**ai**ls',
    'Read https://label.test/a_b_c for details',
])
def test_URL_LABEL_01_mixed_and_formatted_labels_count_only_destination(label):
    result = make(f'before [{label}](https://destination.test) after')
    assert texts(result) == ['before Read', 'for details after']
    assert result['counts']['links'] == 1
    assert result['counts']['removed_url_spans'] == 1
    assert [link['hostname'] for link in result['links']] == ['destination.test']
    assert [link['url'] for link in result['links']] == ['https://destination.test']
    assert result['counts']['retained_words'] == 5


@pytest.mark.parametrize('label', ['https://label.test', '**https://label.test**',
                                   'https://label.test **https://another.test**'])
def test_URL_LABEL_02_url_only_label_creates_hard_boundary(label):
    result = make(f'alpha beta gamma [{label}](https://destination.test) delta epsilon zeta')
    assert texts(result) == ['alpha beta gamma', 'delta epsilon zeta']
    assert result['counts']['links'] == 1
    assert not shingle_set(result['tokens'])
    assert 'gamma delta' not in chargrams(texts(result), len('gamma delta'))


def test_URL_LABEL_03_mixed_label_exclusions_preserve_prose_boundaries_and_offsets():
    result = make('alpha beta gamma [delta https://label.test epsilon zeta eta](https://destination.test) theta')
    assert texts(result) == ['alpha beta gamma delta', 'epsilon zeta eta theta']
    assert not shingle_set(result['tokens'])
    assert 'delta epsilon' not in chargrams(texts(result), len('delta epsilon'))
    for segment in result['segments']:
        assert segment['text'][segment['normalized_start']:segment['normalized_end']] == segment['text']
        assert tuple(segment['source_line_range']) == (1, 1)


@pytest.mark.parametrize('label', ['Read `https://label.test` for details',
                                   'Read <span data-src="https://label.test">for</span> details'])
def test_URL_LABEL_04_excluded_code_html_inside_label_does_not_add_an_occurrence(label):
    result = make(f'before [{label}](https://destination.test) after')
    assert [link['hostname'] for link in result['links']] == ['destination.test']
    assert result['counts']['links'] == 1
    assert all('https' not in segment for segment in texts(result))
    assert texts(result)[0] == 'before Read'
    assert 'details after' in texts(result)[-1]


@pytest.mark.parametrize('label', ['Read https://label.test for details',
                                   '**Read** https://label.test for _details_',
                                   'Read `https://label.test` for details'])
def test_URL_LABEL_05_quote_context_agrees_on_destination_count(label):
    result = make(f'> [{label}](https://destination.test)')
    assert texts(result) == []
    assert result['counts']['links'] == 1
    assert [link['hostname'] for link in result['links']] == ['destination.test']
    assert result['counts']['removed_quote_spans'] == 1


def test_URL_LABEL_06_separate_hyperlinks_and_bare_urls_are_not_globally_deduplicated():
    result = make('[Read https://same.test details](https://same.test) '
                  '[More **https://same.test** details](https://same.test) '
                  'https://same.test')
    assert result['counts']['links'] == 3
    assert [link['hostname'] for link in result['links']] == ['same.test']*3
    snapshot = SimpleNamespace(records=({'id': 'supplied', 'subreddit': None},))
    summary = analyze_links(snapshot, [result], [], CONFIG)['summary']
    assert summary['total_link_occurrences'] == 3
    assert summary['hosts'][0]['occurrences'] == 3
    assert summary['hosts'][0]['record_count'] == 1


def test_URL_LABEL_07_plain_mode_keeps_each_literal_url_occurrence():
    source = '[Read https://label.test for details](https://destination.test)'
    result = make(source, fmt='plain')
    assert [link['hostname'] for link in result['links']] == ['label.test', 'destination.test']
    assert result['counts']['links'] == result['counts']['removed_url_spans'] == 2
    assert '[' in texts(result)[0]
    raw = make('Read https://label.test for details https://destination.test')
    assert [link['hostname'] for link in raw['links']] == ['label.test', 'destination.test']


@pytest.mark.parametrize('source,hosts', [
    ('[Read https://label.test](https://destination.test', ['label.test', 'destination.test']),
    ('[Read https://label.test](javascript:alert(1))', ['label.test']),
    ('[Read https://label.test](https://destination.test" onmouseover="alert(1))',
     ['label.test', 'destination.test']),
])
def test_URL_LABEL_08_malformed_markdown_does_not_invent_hyperlink_context(source, hosts):
    result = make(source)
    assert [link['hostname'] for link in result['links']] == hosts
    assert all(link['url'].startswith('https://') for link in result['links'])
    assert 'Read' in ' '.join(texts(result))
    assert not any('AHASURLTOKEN' in segment for segment in texts(result))


def test_URL_LABEL_09_separate_title_uses_same_counting_contract():
    result = make('Body words stay available.', title='[Read https://label.test details](https://destination.test)')
    assert result['counts']['links'] == 0
    assert result['title']['structure']['links'] == 1
    assert [link['hostname'] for link in result['title']['links']] == ['destination.test']
    assert texts(result['title']) == ['Read', 'details']


def test_URL_LABEL_10_standalone_code_url_remains_an_observable_occurrence():
    result = make('before `https://outside.test` after '
                  '[Read `https://label.test` details](https://destination.test)')
    assert result['counts']['removed_code_spans'] == 2
    assert [link['hostname'] for link in result['links']] == ['outside.test', 'destination.test']
