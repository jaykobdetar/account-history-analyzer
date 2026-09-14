"""Small adversarial oracles for the new review checker; no scoring or inputs."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_final_handoff import html_check, strings, unique


@pytest.mark.parametrize('markup', [
    '<script>fetch("https://example.test")</script>',
    '<iframe src="https://example.test"></iframe>',
    '<svg:script>bad()</svg:script>',
    '<img src="https://example.test/image.png">',
    '<img src="//example.test/image.png">',
    '<svg onload="bad()"></svg>',
    '<meta http-equiv="refresh" content="0;url=https://example.test">',
    '<a href="java\nscript:bad()">open</a>',
    '<a href="data:text/html,bad">open</a>',
    '<style>@import "https://example.test/font.css";</style>',
    '<style>p{background:url(https://example.test/a)}</style>',
])
def test_active_markup_or_remote_resource_fails(markup):
    with pytest.raises(AssertionError):
        html_check(markup)


def test_static_table_and_passive_citation_remain_allowed():
    text = html_check('<style>body{font-family:system-ui}</style>'
                      '<table><tr><th>Score</th></tr><tr><td>unavailable</td></tr></table>'
                      '<a href="https://example.test/paper">reference</a>', 2)
    assert 'unavailable' in text


@pytest.mark.parametrize('field', ['account_key', 'account_keys', 'text', 'source_text', 'record_ids'])
def test_private_fields_fail_at_any_json_depth(field):
    with pytest.raises(AssertionError):
        list(strings({'outcomes': [{field: 'synthetic secret'}]}))


def test_duplicate_outcome_identity_is_rejected():
    with pytest.raises(AssertionError):
        unique([{'id': 'same'}, {'id': 'same'}], lambda r: r['id'])


def test_explicit_known_configuration_mapping_does_not_allow_source_text():
    assert list(strings({'text': {'format': 'markdown'}}, allowed_text_mapping=True)) == ['markdown']
    with pytest.raises(AssertionError):
        list(strings({'text': 'actual source prose'}, allowed_text_mapping=True))
    with pytest.raises(AssertionError):
        list(strings({'text': {'format': 'markdown'}}))
