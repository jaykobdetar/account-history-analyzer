"""Adversarial source regressions for bounded URL placeholder construction."""
import subprocess
import sys

import pytest

from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.text import preprocess


def analyze(source):
    record = {'id': 'source', 'kind': 'comment', 'status': 'present', 'text': source,
              'created_utc': None, 'subreddit': None, 'language': 'en',
              'edit_state': 'unknown', 'title': None}
    return preprocess(record, {'text_format': 'markdown', 'default_language': 'en'},
                      AnalysisConfig.from_mapping())


def test_long_marker_source_finishes_with_and_without_urls():
    # The old repeated prefix search took about 15 seconds for this valid
    # 200,000-codepoint source even when there were no URLs to protect. A broad
    # subprocess deadline bounds the regression without a tight timing claim.
    script = '''
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.text import preprocess
config = AnalysisConfig.from_mapping()
for suffix in ('', ' https://example.test/a*b*c'):
    body = 'AHASURLTOKEN' + 'X' * (200000 - len('AHASURLTOKEN') - len(suffix))
    record = {'id': 'source', 'kind': 'comment', 'status': 'present', 'text': body + suffix,
              'created_utc': None, 'subreddit': None, 'language': 'en',
              'edit_state': 'unknown', 'title': None}
    result = preprocess(record, {'text_format': 'markdown', 'default_language': 'en'}, config)
    assert [segment['text'] for segment in result['segments']] == [body]
    assert [link['url'] for link in result['links']] == (['https://example.test/a*b*c'] if suffix else [])
'''
    completed = subprocess.run([sys.executable, '-c', script], capture_output=True,
                               text=True, timeout=8, check=False)
    assert completed.returncode == 0, completed.stderr


def test_dense_literal_markers_survive_url_protection():
    markers = ' '.join(f'AHASURLTOKEN{i}END0END' for i in range(250))
    result = analyze(markers + ' https://example.test/a*b*c tail')
    assert [segment['text'] for segment in result['segments']] == [markers, 'tail']
    assert [link['url'] for link in result['links']] == ['https://example.test/a*b*c']


@pytest.mark.parametrize('marker', ['AHASURLTOKEN&#48;END0END',
                                   'AHASURLTOKE&#78;0END0END'])
def test_entity_decoded_literal_marker_survives_url_protection(marker):
    result = analyze(marker + ' https://example.test/a*b*c tail')
    assert [segment['text'] for segment in result['segments']] == ['AHASURLTOKEN0END0END', 'tail']
    assert [link['url'] for link in result['links']] == ['https://example.test/a*b*c']
