"""Independent proposed-label and actual excerpt-omission review; no source edits."""
from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
import random

from markdown_it import MarkdownIt
from account_history_analyzer.artifact_io import load_artifact_json, iter_artifact_jsonl
from account_history_analyzer.reporting import md_text, render_markdown, render_html


def candidate_label(value):
    return json.dumps(value, ensure_ascii=True).replace(' ', r'\u0020')


class Cells(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cells = []
        self.current = None
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, attrs))
        if tag == 'td':
            self.current = []

    def handle_data(self, text):
        if self.current is not None:
            self.current.append(text)

    def handle_endtag(self, tag):
        if tag == 'td':
            self.cells.append(''.join(self.current))
            self.current = None


cases = ['', ' ', '  ', ' th', 'he ', ' the ', '\t\n\r\b\f', r'\u0020', r'\t',
         '"', '\\', '|', '`', '&nbsp;', '&#32;', '&quot;', '&amp;#32;', '<img src=x>',
         '[x](javascript:x)', '\x00\x1f\x7f', '\u00a0\u200b\u202e\u2066\ufeff',
         'é', 'e\u0301', '\U0001f600', '\U0010ffff', '***', '"\\ | &\n\t']
rng = random.Random(502005)
for _ in range(1000):
    points = []
    for _ in range(rng.randrange(13)):
        codepoint = rng.randrange(0x110000)
        while 0xD800 <= codepoint <= 0xDFFF:
            codepoint = rng.randrange(0x110000)
        points.append(chr(codepoint))
    cases.append(''.join(points))
cases = list(dict.fromkeys(cases))
parser = Cells()
markdown = '| Label |\n| --- |\n' + ''.join('| ' + md_text(candidate_label(s)) + ' |\n' for s in cases)
rendered = MarkdownIt('commonmark', {'html':True, 'linkify':False, 'typographer':False}).enable('table').render(markdown)
parser.feed(rendered)
assert len(parser.cells) == len(cases)
assert len(set(parser.cells)) == len(cases)
for original, visible in zip(cases, parser.cells, strict=True):
    assert visible == candidate_label(original)
    assert json.loads(visible) == original
    assert all(0x21 <= ord(c) <= 0x7e for c in visible)
assert all(tag in {'table','thead','tr','th','tbody','td'} and not attrs for tag,attrs in parser.tags)

fixture = Path('output/audit-repair/constructed_style_shift')
results = load_artifact_json(fixture / 'results.json')
evidence = list(iter_artifact_jsonl(fixture / 'evidence.jsonl'))
windows = list(iter_artifact_jsonl(fixture / 'windows.jsonl'))
before_md = render_markdown(results, evidence, excerpts='none', windows=windows)
before_html = render_html(results, evidence, excerpts='none', windows=windows)
changed = 0
for comparison in results['modules']['style']['payload']['comparisons']:
    for distance in comparison['distances']:
        if distance['method_id'] == 'cosine_distance_v1':
            for item in distance['contributions']:
                item['feature_id'] = 'SOURCE_LABEL_REPLACED_FOR_OMISSION_PROBE'
                changed += 1
for item in evidence:
    item['text'] = 'SOURCE_PROSE_REPLACED_FOR_OMISSION_PROBE'
assert render_markdown(results, evidence, excerpts='none', windows=windows) == before_md
assert render_html(results, evidence, excerpts='none', windows=windows) == before_html
assert 'SOURCE_LABEL_REPLACED_FOR_OMISSION_PROBE' not in before_html
assert 'SOURCE_PROSE_REPLACED_FOR_OMISSION_PROBE' not in before_html
print(json.dumps({
    'label_scope':'Proposed candidate formula plus actual md_text and pinned Markdown-to-HTML pipeline',
    'distinct_unicode_scalar_strings_roundtripped':len(cases),
    'label_roundtrip':'passed',
    'only_expected_table_tags_and_no_attributes':True,
    'omission_scope':'Actual full report render from supplied 1.0.2 style-shift measurements; no analysis recomputation',
    'replaced_cosine_feature_labels':changed,
    'replaced_evidence_texts':len(evidence),
    'excerpt_none_markdown_byte_identity':'passed',
    'excerpt_none_html_byte_identity':'passed',
}, indent=2))
