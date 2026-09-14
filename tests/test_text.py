"""Independent arithmetic and preprocessing contract regressions (TXT-*)."""
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.features import extract_records, measure, pooled
from account_history_analyzer.io import load_snapshot
from account_history_analyzer.text import function_mask, preprocess, safe_link, tokenize

ROOT = Path(__file__).resolve().parents[1]
CONFIG = AnalysisConfig.from_mapping()


def make(text, *, language='en', fmt='markdown', status='present', kind='comment', title=None):
    record = {'id': 'supplied', 'kind': kind, 'subreddit': None, 'created_utc': '2025-01-01T00:00:00Z',
              'edit_state': 'unknown', 'language': language, 'text': text, 'status': status, 'title': title}
    return measure(preprocess(record, {'text_format': fmt, 'default_language': 'und'}, CONFIG), CONFIG)


def texts(record):
    return [segment['text'] for segment in record['segments']]


def test_TXT_01_arithmetic():
    snapshot = load_snapshot(ROOT/'fixtures/arithmetic.jsonl', ROOT/'fixtures/arithmetic.snapshot.json')
    records = extract_records(snapshot, CONFIG)
    assert [record['counts']['retained_words'] for record in records] == [8, 8, 9, 4, 4, 3]
    summary = pooled(records, CONFIG)
    assert summary['counts']['retained_words'] == 36
    assert texts(records[3]) == ['I think it works.']
    pair = summary['contractions']['dont_do_not']
    assert (pair['contracted'], pair['expanded'], pair['opportunities']) == (2, 1, 3)
    assert pair['raw_fraction'] == 2/3 and pair['fraction'] is None
    assert pair['status'] == 'insufficient_opportunities'
    assert [link['hostname'] for link in records[4]['links']] == ['example.test', 'example.test']


def test_TXT_02_plain_mode_and_paragraphs():
    source = '> quote\n\n`code` and prose'
    plain, markdown = make(source, fmt='plain'), make(source)
    assert plain['counts']['retained_words'] == 4
    assert markdown['counts']['retained_words'] == 2
    assert plain['counts']['removed_quote_spans'] == plain['counts']['removed_code_spans'] == 0
    assert texts(make('alpha\nbeta\n\ngamma', fmt='plain')) == ['alpha\nbeta', 'gamma']


def test_TXT_03_descriptive_link_and_autolink_once():
    result = make('alpha [the notes](https://example.test/a) omega <https://example.test/b> end')
    assert texts(result) == ['alpha the notes omega', 'end']
    assert result['counts']['links'] == 2
    assert result['counts']['retained_words'] == 5
    assert texts(make('pre [https://example.test](https://example.test) post')) == ['pre', 'post']


def test_TXT_04_url_boundaries_keep_punctuation():
    result = make('alpha https://example.test/a. beta https://example.test/b(x)). gamma')
    assert texts(result) == ['alpha', '. beta', '). gamma']
    assert [link['url'] for link in result['links']] == ['https://example.test/a', 'https://example.test/b(x)']


def test_TXT_05_06_formatting_does_not_split_but_code_does():
    assert texts(make('al**ph**a _be_**ta**')) == ['alpha beta']
    result = make('alpha `hidden code` beta')
    assert texts(result) == ['alpha', 'beta']
    assert result['tokens'] == (('alpha',), ('beta',))
    assert result['counts']['removed_code_spans'] == 1
    assert texts(make('alpha\n\n    invisible code\n\nbeta')) == ['alpha', 'beta']


def test_TXT_08_unicode_normalization_source_hash_distinct():
    left, right = make('caf\u00e9'), make('cafe\u0301')
    assert texts(left) == texts(right) == ['café']
    assert left['source_sha256'] != right['source_sha256']
    assert left['counts'] == right['counts']


def test_TXT_09_10_surface_categories_and_contractions():
    result = make("don't don’t—-–….......\"“”")
    punctuation = result['counts']['punctuation']
    assert punctuation['ascii_apostrophe'] == punctuation['curly_apostrophe'] == 1
    assert punctuation['period'] == 7 and punctuation['ascii_period_runs'] == 1
    assert all(punctuation[key] == 1 for key in ('ascii_hyphen','en_dash','em_dash','ellipsis','ascii_double_quote','left_curly_double_quote','right_curly_double_quote'))
    assert result['contractions']['dont_do_not']['contracted'] == 2


@pytest.mark.parametrize('source', ['`code`', '> quoted', 'https://example.test', ' \n\t '])
def test_TXT_11_17_empty_denominators(source):
    record = make(source)
    assert record['counts']['retained_words'] == 0
    assert record['rates']['average_word_length'] is None
    assert record['rates']['uppercase_fraction'] is None
    assert 'zero_retained_words_denominator' in record['rate_reason_codes']


@pytest.mark.parametrize('language', ['es', 'und', None, 'en-US'])
def test_TXT_12_english_methods_abstain(language):
    record = make('I think the words remain measurable.', language=language)
    assert record['counts']['retained_words'] == 6
    assert not record['masked_segments']
    assert all(value is None for value in record['function_counts'].values())
    assert all(pair['status'] == 'not_run' for pair in record['contractions'].values())


def test_TXT_13_14_quotes_handles_metadata():
    result = make('"ordinary quotes" u/name alpha /r/place beta')
    assert texts(result) == ['"ordinary quotes"', 'alpha', 'beta']
    assert result['counts']['mentions'] == 2
    assert result['counts']['retained_words'] == 4
    assert texts(make('occupyfoo/r/name /u/name word')) == ['occupyfoo/r/name', 'word']


def test_TXT_15_pooled_counts_not_mean_of_rates():
    one, nine = make('word,'), make(' '.join(['word']*9))
    summary = pooled([one,nine], CONFIG)
    assert summary['rates']['punctuation_per_1000_words']['comma'] == 100
    assert summary['words_per_record'] == {'count': 2, 'min':1, 'max':9, 'q25':3.0, 'median':5.0, 'q75':7.0}


def test_TXT_16_contraction_guard_and_cross_boundary():
    nine, ten = make("don't "*9), make("don't "*10)
    assert nine['contractions']['dont_do_not']['fraction'] is None
    assert ten['contractions']['dont_do_not']['fraction'] == 1
    assert make('do `code` not')['contractions']['dont_do_not']['expanded'] == 0
    assert make('do\n\nnot')['contractions']['dont_do_not']['expanded'] == 0


def test_TXT_18_offsets_and_original_block():
    result = make('alpha `code` beta\n\ngamma')
    assert result['segments'][0]['source_line_range'] == (1,1)
    assert result['segments'][2]['source_line_range'] == (3,3)
    for segment, tokens in zip(result['segments'], result['token_offsets']):
        assert segment['text'][segment['normalized_start']:segment['normalized_end']] == segment['text']
        for token in tokens:
            assert segment['text'][token['start']:token['end']] == token['text']


def test_operational_unicode_tokenizer_and_mask():
    tokens = tokenize("I don't don’t cafe\u0301 naïve A_B 123 ٣ ² 🦊 re-use")
    assert [token['text'] for token in tokens] == ['I', "don't", 'don’t', 'cafe', 'naïve','A','B','123','٣','²','re','use']
    assert [token['text'] for token in tokens if token['kind'] == 'number'] == ['123','٣','²']
    assert function_mask("I don't know 12, naïve!") == "I ***'* **** ##, *****!"


def test_unavailable_sentinel_and_titles_separate():
    unavailable = make(None, status='removed')
    assert unavailable['counts']['retained_words'] is None
    assert pooled([unavailable], CONFIG)['counts']['retained_words'] == 0
    assert pooled([unavailable], CONFIG)['usable_record_count'] == 0
    assert make('[deleted]')['counts']['retained_words'] is None
    titled = make('body one', kind='submission', title='Title has four words')
    assert titled['counts']['retained_words'] == 2
    assert [segment['text'] for segment in titled['title']['segments']] == ['Title has four words']
    assert titled['title']['segments'][0]['source_field'] == 'title'


def test_link_security_html_quote_and_code():
    record = make('> [quote](https://example.test/q)\n\n`https://example.test/code` <b>safe</b> ![image](https://example.test/i)')
    assert texts(record) == ['safe']
    assert record['counts']['links'] == 3
    assert 'html_present' in record['warnings']
    assert safe_link('https://user:password@EXAMPLE.TEST.:443/path','text',None)['url'] == 'https://example.test:443/path'
    assert safe_link('javascript:alert(1)','text',None)['url'] is None
    assert safe_link('https://example.test:invalid/path','text',None)['status'] == 'malformed'


@given(st.text(alphabet=st.characters(blacklist_categories=('Cs',)), max_size=100))
def test_property_token_offsets_and_measurement_finiteness(source):
    record = make(source, fmt='plain')
    assert record['counts']['retained_words'] >= 0
    assert record['counts']['uppercase_letters'] <= record['counts']['cased_letters']
    for segment, tokens in zip(record['segments'],record['token_offsets']):
        for token in tokens:
            assert segment['text'][token['start']:token['end']] == token['text']


def test_regression_url_markdown_delimiters_do_not_leak_into_prose():
    for source in ('alpha https://example.test/a*b*c omega',
                   'alpha https://example.test/a_b_c omega'):
        result = make(source)
        assert texts(result) == ['alpha','omega']
        assert len(result['links']) == 1
    result = make('alpha [notes](https://example.test/a*b*c) omega')
    assert texts(result) == ['alpha notes omega']
    assert result['links'][0]['url'] == 'https://example.test/a*b*c'
    result = make('alpha <https://example.test/a*b*c> omega')
    assert texts(result) == ['alpha','omega']
    assert result['links'][0]['url'] == 'https://example.test/a*b*c'
    assert 'html_present' not in result['warnings']
    assert texts(make('AHASURLTOKEN0END https://example.test/z end')) == ['AHASURLTOKEN0END','end']


def test_regression_english_pooled_denominator_explicit():
    english, other = make('the word'), make('la palabra extra',language='es')
    result = pooled([english,other],CONFIG)
    assert result['counts']['retained_words'] == 5
    assert result['english_word_count'] == 2
    assert result['function_rates']['the'] == 500


@pytest.mark.parametrize('source', ['`https://example.test/a*b*c` beta',
                                    '> https://example.test/a*b*c\n\nbeta',
                                    '<span href="https://example.test/a*b*c">beta</span>'])
def test_regression_protected_urls_in_excluded_source_contexts(source):
    record = make(source)
    assert texts(record) == ['beta']
    assert [link['url'] for link in record['links']] == ['https://example.test/a*b*c']


@pytest.mark.parametrize('wrapper', ['*','**','_','__','***','_*'])
def test_regression_emphasized_url_has_no_retained_delimiters(wrapper):
    source=f'before {wrapper}https://example.test/a*b*c{wrapper[::-1]} after'
    result=make(source)
    assert texts(result) == ['before','after']
    assert [link['url'] for link in result['links']] == ['https://example.test/a*b*c']


def test_regression_long_unmatched_url_brackets_remain_prose():
    trailing = ')' * 5000
    result = make('https://example.test/path' + trailing,fmt='plain')
    assert texts(result) == [trailing]
    assert [link['url'] for link in result['links']] == ['https://example.test/path']


def test_preprocessing_transformation_sequence_is_explicit():
    record=make('The text.')
    assert record['transformations'] == ('line_endings_lf_v1','unicode_nfc_v1','commonmark_parse_v1',
                                         'retained_span_exclusion_v1','horizontal_whitespace_v1',
                                         'lexical_regex_v1','function_mask_v1')
    assert make(None,status='unavailable')['transformations'] == ()
    assert 'function_mask_v1' not in make('el texto',language='es')['transformations']
