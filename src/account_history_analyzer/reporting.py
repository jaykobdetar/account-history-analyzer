"""Deterministic, source-linked local reports; no measurement is recomputed here."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from html import escape
import hashlib
import json
from typing import Any

TEMPLATE_VERSION = '1.0.4'
# Presentation order is a contract, independent of input mapping insertion.
TEXT_STATUS_ORDER = ('present', 'deleted', 'removed', 'unavailable')
LIMITATIONS = (
    'These are measurements of supplied records. Coverage and language are supplier declarations.',
    'A measured pattern does not establish its cause. Style distance is not an authorship probability.',
    'A content match does not establish deceptive intent. A timestamp gap does not establish sleep or inactivity.',
    'Observed text is ordered by record creation time; edited wording may differ from wording at creation.',
    'AI text detection: not_implemented_in_v1. Real-world validation: not_established.',
)
SOURCES = (
    ('S1','Character n-gram research','https://aclanthology.org/N15-1010/'),
    ('S2','Text distortion research','https://aclanthology.org/E17-1107/'),
    ('S3','Function-word research','https://aclanthology.org/W14-0908/'),
    ('S4','Classic Delta implementations','https://journal.r-project.org/articles/RJ-2016-007/'),
    ('S5','PELT optimization','https://arxiv.org/abs/1101.1438'),
    ('S6','ruptures PELT documentation','https://centre-borelli.github.io/ruptures-docs/user-guide/detection/pelt/'),
    ('S7','SciPy cosine distance','https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.cosine.html'),
    ('S8','SciPy Jensen–Shannon distance','https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.jensenshannon.html'),
    ('S9','Shingle resemblance and containment','https://www.cs.princeton.edu/courses/archive/spr05/cos598E/bib/broder97resemblance.pdf'),
    ('S10','Evaluation leakage guidance','https://scikit-learn.org/stable/common_pitfalls.html'),
    ('S11','RAID detector evaluation cautions','https://aclanthology.org/2024.acl-long.674/'),
    ('S12','Python 3.12 UTC datetime','https://docs.python.org/3.12/library/datetime.html'),
    ('S13','Python 3.12 JSON serialization','https://docs.python.org/3.12/library/json.html'),
    ('S14','CommonMark parsing','https://spec.commonmark.org/0.31.2/'),
    ('S15','PAN writing-style task scope','https://pan.webis.de/clef25/pan25-web/style-change-detection.html'),
    ('S16','ruptures PR #383 pinned optimizer fix','https://github.com/deepcharles/ruptures/commit/a28574d9e63b0c2a966e176a1d049d3c9deaaaaf'),
)


def json_text(value: Any, *, indent: int | None = None) -> str:
    """Render structured values with sorted map keys and unchanged list order.

    JSON's encoder already handles tuples as arrays. The fallback converts only
    the current immutable mapping to a shallow dict when encountered; callers
    need not thaw or copy the complete analysis to render selected subtrees.
    """
    def mapping(value: Any) -> dict:
        if isinstance(value, Mapping):
            return dict(value)
        raise TypeError(f'Unsupported report JSON value: {type(value).__name__}')
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=indent,
                      allow_nan=False, default=mapping)


def md_text(value: Any) -> str:
    """Make untrusted strings inert in Markdown, HTML text and template summaries.

    These numeric entities are emitted only into text contexts. Attribute/anchor
    values are fixed or digest-derived. Newlines cannot create new Markdown blocks.
    """
    text = json_text(value) if isinstance(value, (Mapping, list, tuple)) else str(value)
    return ''.join(f'&#{ord(char)};' if char in '&<>[]()!*_`\\#|\r\n' else char for char in text)


def ngram_label(value: str) -> str:
    """Reversible display notation; never replace the analytical feature ID.

    ASCII JSON string notation escapes controls, invisible Unicode characters,
    quotes and literal backslashes. Escape ordinary spaces too: Markdown tables
    trim boundary spaces and browsers collapse repeated spaces. Decoding the
    displayed cell with json.loads recovers the original code-point sequence.
    Pass this notation through md_text before placing it in a report.
    """
    return json.dumps(value, ensure_ascii=True).replace(' ', r'\u0020')


def number(value: Any) -> str:
    """Round presentation only; a missing measurement stays explicitly missing."""
    if value is None:
        return 'not computable'
    if isinstance(value,float):
        return f'{value:.6g}'
    return str(value)


def _anchor(kind: str, value: str) -> str:
    return kind+'-'+hashlib.sha256(value.encode('utf-8')).hexdigest()[:24]


def _utc(value: str | None) -> str:
    return md_text(value.replace('T',' ').removesuffix('Z')+' UTC') if value else 'not supplied'


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    return ['| '+' | '.join(headers)+' |','| '+' | '.join('---' for _ in headers)+' |']+['| '+' | '.join(row)+' |' for row in rows]+['']


def render_markdown(results: Mapping[str,Any], evidence: Sequence[Mapping[str,Any]] | None = None, *,
                    excerpts: str = 'included', windows: Sequence[Mapping[str,Any]] | None = None) -> str:
    """Render fixed templates with source references and optional prose excerpts.

    Controlled HTML anchors/details/pre blocks are part of the template. All
    supplied content is escaped before insertion; source Markdown is never
    rendered as formatting. ``excerpts=none`` omits all evidence text and n-gram
    example strings while retaining measurements and identifier references.
    Status maps use TEXT_STATUS_ORDER; other rendered maps sort their keys.
    Ordered arrays retain their supplied chronology, ranking and example order.
    """
    if excerpts not in {'included','none'}:
        raise ValueError('excerpts must be included or none')
    modules=results['modules']
    evidence=list(evidence or [])
    windows=list(windows or [])
    by_evidence={item['evidence_id']:item for item in evidence}
    by_window={item['window_id']:item for item in windows}
    findings=results['findings']
    source_ids:set[str]=set()
    def source(identifier: str) -> str:
        source_ids.add(identifier)
        return f'[{md_text(identifier)}](#{_anchor("source",identifier)})'
    def source_list(identifiers: Sequence[str], limit: int | None = None) -> str:
        shown=identifiers if limit is None else identifiers[:limit]
        content=', '.join(source(identifier) for identifier in shown)
        if limit is not None and len(identifiers)>limit:
            content+=f'; {len(identifiers)-limit} further source IDs in the complete export'
        return content or 'none supplied'
    def refs(identifiers: Sequence[str]) -> str:
        return ', '.join(f'[{index+1}](#{_anchor("evidence",identifier)})' for index,identifier in enumerate(identifiers) if identifier in by_evidence) or 'no excerpt evidence attached'
    def section(title: str, name: str) -> None:
        lines.extend([f'<a id="{name}"></a>','',f'## {title}',''])
    def status(name: str) -> None:
        mod=modules[name]
        lines.extend([f"Module status: **{md_text(mod['status'])}**. Reasons: {', '.join(md_text(reason) for reason in mod['reason_codes']) or 'none'}.",''])
    def figure(name: str, caption: str) -> None:
        # Fixed paths only; HTML replaces these trusted local chart placeholders
        # with controlled inline SVG, so opening HTML needs no resource requests.
        lines.extend([f'<!-- AHAS_CHART:{name} -->',f'![{caption}]({name})',''])
    def feature_table(selected: Mapping[str,Any] | None) -> None:
        if not selected:
            return
        for title,key in [('Largest measured feature differences','changing_features'),('Selected stable features','stable_features')]:
            lines.extend([f'**{title}**',''])
            rows=[[md_text(item['feature_id']),number(item['left_value']),number(item['right_value']),
                   number(item['absolute_change']),md_text(item['unit'])] for item in selected['values'].get(key,[])]
            lines.extend(_table(['Feature','Left','Right','Absolute change','Unit'],rows))
        lines.extend(['Selected high-rate examples and ordinary context: '+refs(selected['evidence_refs'])+'.',
                      'Examples are selected by the registered rule and are not a representative sample of an entire window.',''])
    lines=['# Supplied account-history measurements','',
           '**Privacy:** This report contains source text and identifiers.' if excerpts=='included' else
           '**Privacy:** Source excerpts omitted. Remaining identifiers and measurements may still identify an account.','',
           f"Snapshot: {md_text(results['snapshot']['snapshot_id'])}. Source category: {md_text(results['snapshot']['source_category'])}. All temporal labels use UTC.",'',
           '[Coverage](#coverage) · [Text](#text) · [Activity](#activity) · [Reuse](#reuse) · [Comparisons](#style) · [Candidates](#changes) · [Links](#links) · [Evidence](#evidence) · [Methods](#methods)','']
    if 'toy_reference' in results.get('limitations',[]) or any(distance.get('reference_kind')=='toy' for comparison in modules['style']['payload'].get('comparisons',[]) for distance in comparison['distances']):
        lines.extend(['**Toy reference in use:** Delta values use an arithmetic-only reference. This is not a validated research baseline.',''])
    section('Coverage and limitations','coverage')
    status('coverage')
    lines.extend('- '+value for value in LIMITATIONS)
    coverage=modules['coverage']['payload']
    declared=coverage.get('declared_coverage',{})
    lines.extend(['',f"Unique supplied records: **{coverage.get('unique_records',0)}**. Usable body texts: {coverage.get('usable_body_records',0)}. Missing creation times: {coverage.get('missing_timestamps',0)}.",
                  f"Coverage declaration: **{md_text(declared.get('status','unknown'))}**; not independently verified. Declared range: {_utc(declared.get('start_utc'))} to {_utc(declared.get('end_utc'))}.",''])
    status_counts = coverage.get('status_counts', {})
    status_keys = [key for key in TEXT_STATUS_ORDER if key in status_counts]
    status_keys.extend(sorted(set(status_counts) - set(TEXT_STATUS_ORDER)))
    lines.extend(_table(['Supplied text status','Distinct records'],[[md_text(key),number(status_counts[key])] for key in status_keys]))
    lines.extend(_table(['Declared language','Records'],[[md_text(row['language']),str(row['records'])] for row in coverage.get('languages',[])]))
    for gap in declared.get('known_gaps',[]):
        lines.append(f"- Declared collection gap: {_utc(gap['start_utc'])} to {_utc(gap['end_utc'])}. This is collection metadata.")
    for warning in coverage.get('warnings',[]):
        lines.append(f"- {md_text(warning['code'])}: {source_list(warning['source_record_ids'],12)}.")
    lines.append('')
    section('Direct text measurements','text')
    status('text')
    text_payload=modules['text']['payload']
    for name,summary in [('Retained body prose',text_payload.get('body',text_payload)),('Submission titles (separate scope)',text_payload.get('titles',{}))]:
        if not summary:
            continue
        lines.extend([f'### {name}','',
                      f"Included records: {summary.get('record_count',0)}; usable text observations: {summary.get('usable_record_count',0)}. Rates pool counts before dividing.",''])
        counts,rates=summary.get('counts',{}),summary.get('rates',{})
        labels=[('retained_words','Retained word tokens'),('number_tokens','Number tokens'),('retained_codepoints','Retained Unicode code points'),
                ('cased_letters','Cased code points'),('uppercase_letters','Uppercase code points'),('segments','Retained boundary-separated segments'),
                ('paragraphs','Retained prose blocks'),('word_character_total','Alphabetic code points inside word tokens'),
                ('removed_quote_spans','Removed explicit quote spans'),('removed_code_spans','Removed code spans'),('removed_url_spans','Removed visible URL spans'),
                ('headings','Source headings'),('list_items','Source list items'),('links','Detected source link occurrences'),('mentions','Excluded mentions')]
        lines.extend(_table(['Measurement','Count'],[[label,number(counts.get(key))] for key,label in labels]))
        lines.extend([f"Uppercase fraction = uppercase / cased code points: **{number(rates.get('uppercase_fraction'))}**. Average word length = alphabetic code points / retained word tokens: **{number(rates.get('average_word_length'))}**.",
                      'Undefined rates: '+(', '.join(md_text(reason) for reason in summary.get('rate_reason_codes',[])) or 'none')+'.',''])
        lengths=summary.get('words_per_record',{})
        lines.extend([f"Retained words per usable record (n={lengths.get('count',0)}): min {number(lengths.get('min'))}, Q1 {number(lengths.get('q25'))}, median {number(lengths.get('median'))}, Q3 {number(lengths.get('q75'))}, max {number(lengths.get('max'))}. Quantiles use linear interpolation at (n−1)q.",''])
        if name.startswith('Submission') and not summary.get('usable_record_count'):
            continue
        lines.extend(['<details><summary>Literal punctuation and lexical descriptors</summary>',''])
        rows=[[md_text(key.replace('_',' ')),number(value),number(rates.get('punctuation_per_1000_words',{}).get(key)),
               number(rates.get('punctuation_per_1000_codepoints',{}).get(key))] for key,value in sorted(counts.get('punctuation',{}).items())]
        lines.extend(_table(['Literal punctuation','Count','Per 1,000 word tokens','Per 1,000 retained code points'],rows))
        lines.extend(['ASCII period runs overlap literal period counts; these are not disjoint quantities.',
                      f"Standalone literal i/I token counts: {number(counts.get('standalone_i_lower'))}/{number(counts.get('standalone_i_upper'))}. These are not verified pronoun labels.",
                      f"English-specific denominator: {summary.get('english_word_count',0)} retained words in {summary.get('english_record_count',0)} declared-English usable records.",''])
        lines.extend(_table(['Literal alternative','Contracted','Expanded','Opportunities','Qualified fraction','Status'],[
            [md_text(key),number(value['contracted']),number(value['expanded']),number(value['opportunities']),number(value['fraction']),md_text(value['status'])]
            for key,value in sorted(summary.get('contractions',{}).items())]))
        lines.extend(['Raw fractions below the opportunity guard remain in the numerical export; they are not displayed as qualified preferences.','',
                      '</details>',''])
    section('Observed supplied activity','activity')
    status('activity')
    activity=modules['activity']['payload']
    lines.extend([f"Distinct timed supplied events: **{activity.get('event_count',0)}**, including records whose text is deleted, removed or unusable. Range: {_utc(activity.get('earliest_utc'))} to {_utc(activity.get('latest_utc'))}.",
                  f"Observed span: {number(activity.get('observed_span_seconds'))} seconds. Event-bearing UTC dates: {activity.get('event_bearing_days',0)} of {activity.get('day_count',0)} calendar dates; dates with no supplied events: {activity.get('zero_event_days',0)}.",
                  'Zero-event dates and long gaps do not establish inactivity or sleep. Hour bins aggregate across dates.',''])
    figure('activity_daily.svg','Observed events per UTC calendar date')
    figure('activity_hourly.svg','Observed events in UTC hour bins across all dates')
    gaps=activity.get('gap_summary',{})
    lines.extend(_table(['Adjacent-event gap summary','Value'],[
        ['Interval count',str(gaps.get('count',0))],['Mean / median (seconds)',number(gaps.get('mean'))+' / '+number(gaps.get('median'))],
        ['Q1 / Q3 (seconds)',number(gaps.get('q25'))+' / '+number(gaps.get('q75'))],
        ['Population variance (seconds squared)',number(gaps.get('population_variance_seconds_squared'))],
        ['Population SD / mean (dimensionless)',number(gaps.get('coefficient_of_variation'))],
        ['Variability missingness reason',md_text(gaps.get('coefficient_of_variation_reason') or 'none')]]))
    lines.extend(_table(['Inclusive sliding duration (seconds)','Maximum supplied events','Witness source records'],[
        [str(row['duration_seconds']),str(row['maximum_events']),source_list(row['record_ids'],12)] for row in activity.get('maximum_sliding_windows',[])]))
    bursts=activity.get('greedy_bursts',[])
    lines.extend([f"Greedy nonoverlapping fixed-window bursts: {len(bursts)}; duration {activity.get('burst_duration_seconds',30)} seconds, minimum {activity.get('burst_minimum_events',3)} events. This differs from gap-connected sessions or overlapping sliding counts.",''])
    for burst in bursts[:20]:
        lines.append(f"- {_utc(burst['first_utc'])} to {_utc(burst['last_utc'])}: {source_list(burst['record_ids'])}.")
    if len(bursts)>20:
        lines.append(f'{len(bursts)-20} further bursts are available in results.json; this preview shows 20 of {len(bursts)}.')
    lines.extend(['','<details><summary>Weekday exposure and simultaneous supplied timestamps</summary>',''])
    lines.extend(_table(['UTC weekday','Calendar dates in supplied range','Supplied events'],[
        [md_text(row['weekday']),str(row['days_in_supplied_range']),str(row['supplied_events'])] for row in activity.get('weekdays',[])]))
    for group in activity.get('simultaneous_timestamp_groups',[]):
        lines.append(f"- {_utc(group['created_utc'])}: {source_list(group['record_ids'])}. Sub-resolution event order is unknown.")
    lines.extend(['','</details>',''])
    section('Content reuse and source evidence','reuse')
    status('reuse')
    reuse=modules['reuse']['payload']
    if reuse:
        groups,pairs=reuse.get('exact_groups',[]),reuse.get('pairs',[])
        complete = reuse.get('budget_complete', False)
        pair_count = str(len(pairs)) if complete else 'not available (incomplete near-reuse search)'
        lines.extend([f"Exact equivalence groups: {len(groups)}. Qualifying shingle pairs: {pair_count}. Distinct candidate pairs generated{' (lower bound)' if reuse.get('candidate_count_is_lower_bound') else ''}: {reuse.get('candidate_pair_count',0)}; budget {reuse.get('max_candidate_pairs',0)}; complete near-reuse search: {str(complete).lower()}.",
                      'Raw strings, normalized prose and lexical token sequences are different match types. Empty/sentinel text is excluded. Short common text is excluded from substantial-reuse findings.',
                      'Shingles are sets of consecutive tokens within segments. Jaccard divides shared shingles by their union; directed containment divides by the source side’s shingle count. Exact rational thresholds are recorded in resolved_config.json.',''])
        if 'resource_usage' in reuse and 'resource_limits' in reuse:
            usage, limits = reuse['resource_usage'], reuse['resource_limits']
            lines.extend([f"Deterministic near-reuse resource accounting: {md_text(usage['method'])}. Exhaustion reason: {md_text(reuse.get('resource_limit_reason') or 'none')}.", ''])
            lines.extend(_table(['Resource counter','Consumed','Configured limit'],[
                [md_text(key), number(usage[key]), number(limits.get('max_' + key))]
                for key in sorted(usage) if key != 'method']))
        if not complete:
            lines.extend(['No complete near-reuse pair set is available because a resource limit was reached. Exact equivalence groups remain available. This state does not establish an absence of near matches.', ''])
        lines.extend(_table(['Exact match type','Source records','Scope qualification'],[
            [md_text(group['match_type']),source_list(group['record_ids'],8),'substantial under configured word guard' if group['substantial'] else 'short common text'] for group in groups[:20]]))
        lines.extend([f'Showing {min(20,len(groups))} of {len(groups)} exact groups; {max(0,len(groups)-20)} omitted from this preview. All groups are in results.json.',''])
        lines.extend(_table(['Source pair','Words left/right','Shared / union shingles','Jaccard','Left in right','Right in left'],[
            [source(pair['left_record_id'])+' / '+source(pair['right_record_id']),f"{pair['left_word_count']} / {pair['right_word_count']}",
             f"{pair['intersection']} / {pair['union']}",number(pair['jaccard']),number(pair['left_in_right']),number(pair['right_in_left'])] for pair in pairs[:20]]))
        if complete:
            lines.extend([f'Showing {min(20,len(pairs))} of {len(pairs)} pairs; {max(0,len(pairs)-20)} omitted from this preview. Complete computed pairs and passages are in results.json.',
                          f"Connected reuse groups: {len(reuse.get('connected_groups',[]))}. Connected edges do not assert pairwise equivalence among every group member."])
        else:
            lines.append('Near-reuse pair and connected-group tables are unavailable for this incomplete search.')
        lines.extend(['A shared shingle set is not necessarily one contiguous passage. Lexically matched source passages may retain different case and punctuation.',''])
        reuse_findings=[finding for finding in findings if finding['finding_type'] in {'raw_text_identical','normalized_prose_identical','token_sequence_identical','shared_token_shingles'}]
        for finding in reuse_findings[:20]:
            lines.append(f"- {md_text(finding['finding_type'])}: {source_list(finding['source_record_ids'],8)}. Actual evidence: {refs(finding['evidence_refs'])}.")
        lines.append('')
    section('Writing windows and descriptive comparisons','style')
    status('style')
    style=modules['style']['payload']
    lines.extend(['Windows contain whole records, with separate comment and submission-body streams. A visible final remainder is excluded from segmentation. Community streams share records with pooled streams and are not independent samples.',''])
    streams=style.get('streams',[])
    stream_names={stream['stream_id']:stream['scope_type']+' '+stream['kind']+((': '+str(stream['subreddit'])) if stream['scope_type']=='community' else '') for stream in streams}
    lines.extend(_table(['Stream scope','Target words / min records','Eligible words','Qualified windows','Remainder words'],[
        [md_text(stream_names[stream['stream_id']]),f"{stream['target_words']} / {stream['minimum_records']}",str(stream['eligible_words']),
         str(stream['qualified_window_count']),str(stream['remainder_word_count'])] for stream in streams]))
    if style.get('omitted_communities'):
        lines.append('Community stream limit omitted: '+', '.join(f"{md_text(item['subreddit'])} ({item['eligible_words']} eligible words)" for item in style['omitted_communities'])+'.')
    figure('eligible_word_volume.svg','Retained words in primary pooled writing windows')
    comparisons=style.get('comparisons',[])
    comp_findings={finding['values']['comparison_id']:finding for finding in findings if finding['finding_type']=='style_comparison'}
    lines.extend([f'Showing {min(20,len(comparisons))} of {len(comparisons)} comparisons; {max(0,len(comparisons)-20)} omitted from this preview. Complete comparisons/contributions are in results.json and all memberships in windows.jsonl.',
                  'Raw measurements may be computable below the qualified sample guard. A distance is not a percentage of different authorship, and raw/masked distance scales are not interchangeable.',''])
    boundary_pairs={(boundary['left_window_id'],boundary['right_window_id']) for change in style.get('changes',[]) for boundary in change['boundaries']}
    preview=sorted(enumerate(comparisons),key=lambda pair:(0 if pair[1]['left_window_id'] is None else 1 if (pair[1]['left_window_id'],pair[1]['right_window_id']) in boundary_pairs else 2,pair[0]))[:20]
    lines.extend(['The preview prioritizes manual selections, then candidate-adjacent comparisons, then other comparisons in export order.',''])
    if excerpts == 'included' and any(distance['method_id'] == 'cosine_distance_v1' and distance['contributions']
                                      for _, comparison in preview for distance in comparison['distances']):
        lines.extend(['Character n-gram labels use quoted ASCII JSON string notation. Ordinary spaces appear as '+
                      md_text(r'\u0020')+'; controls, non-ASCII characters, quotes and literal backslashes are escaped. '+
                      'JSON-decoding a displayed label recovers its exact feature string. Analytical IDs and rates are unchanged.',''])
    for _,comparison in preview:
        identifier=comparison['comparison_id']
        left,right=comparison['samples']['left'],comparison['samples']['right']
        lines.extend([f'<a id="{_anchor("comparison",identifier)}"></a>',
                      f'<details><summary>Comparison {md_text(identifier)} — {md_text(comparison["status"])}</summary>','',
                      f"Left: {left['record_count']} records / {left['word_count']} words; right: {right['record_count']} records / {right['word_count']} words. Eligible sizes: {left['eligible_record_count']} records / {left['eligible_word_count']} words versus {right['eligible_record_count']} records / {right['eligible_word_count']} words.",
                      f"Kinds: {md_text(', '.join(left['kinds']))} versus {md_text(', '.join(right['kinds']))}; languages: {md_text(', '.join(left['languages']))} versus {md_text(', '.join(right['languages']))}. Missing times: {left['missing_timestamps']} / {right['missing_timestamps']}.",
                      f"Largest single-record word shares: {number(left['largest_record_share'])} / {number(right['largest_record_share'])}. Median retained words per usable record: {number(left['length']['median'])} / {number(right['length']['median'])}.",
                      'Reasons: '+(', '.join(md_text(reason) for reason in comparison['reason_codes']) or 'none')+'.',
                      'Limitations: '+', '.join(md_text(reason) for reason in comparison['limitations'])+'.',''])
        for side,sample in [('Left',left),('Right',right)]:
            lines.append(side+' community composition: '+('; '.join(f"{md_text(item['subreddit'])}: {item['record_count']} records, {item['word_count']} words" for item in sample['community_distribution']) or 'no observations')+'.')
        lines.append('')
        rows=[]
        for distance in comparison['distances']:
            label=distance['method_id']+' / '+distance['view']+(f" / n={distance['n']}" if distance['n'] is not None else '')
            rows.append([md_text(label),number(distance['value']),md_text(distance['unit']),
                         f"{distance['left_denominator']} / {distance['right_denominator']} {md_text(distance['denominator_unit'])}",
                         md_text(distance['status']+' / '+str(distance['reason'] or 'none'))])
        lines.extend(_table(['Method / representation','Distance','Unit','Left/right denominators','Status / reason'],rows))
        feature_table(comp_findings.get(identifier))
        lines.extend(['<details><summary>Largest representation differences and contributions</summary>',''])
        for distance in comparison['distances']:
            if not distance['contributions'] or excerpts=='none' and distance['method_id']=='cosine_distance_v1':
                continue
            lines.extend([f"{md_text(distance['method_id'])}, {md_text(distance['view'])}"+(f", n={distance['n']}" if distance['n'] is not None else '')+f": {len(distance['contributions'])} exported feature coordinates. Preview: {min(10,len(distance['contributions']))}.",
                          'Character n-gram rate differences are not an exact decomposition of cosine distance. JS contributions are divergence terms before square root; Delta contributions are absolute standardized-frequency differences.',''])
            lines.extend(_table(['Feature','Left rate','Right rate','Absolute rate change','Contribution','Rate unit'],[
                [md_text(ngram_label(item['feature_id']) if distance['method_id']=='cosine_distance_v1' else item['feature_id']),number(item['left_rate']),number(item['right_rate']),number(item['absolute_rate_change']),
                 number(item['contribution']),md_text(distance['rate_unit'])] for item in distance['contributions'][:10]]))
        lines.extend(['</details>','','</details>',''])
    section('Descriptive change candidates and sensitivity','changes')
    lines.extend(['Timeline: observed text ordered by record creation time. A candidate locates a boundary between measured windows, not an exact event date, a cause, or a change of author.',''])
    for analysis in style.get('changes',[]):
        lines.extend([f"**{md_text(stream_names.get(analysis['stream_id'],analysis['stream_id']))}: {md_text(analysis['status'])}.** {len(analysis['window_ids'])} qualified windows; λ={number(analysis['penalty_lambda'])}, β={number(analysis['penalty_beta'])}; segment SSE={number(analysis['sse'])}; total penalized objective={number(analysis['objective'])}.",
                      f"Optimizer: {md_text(analysis['optimizer'])}; min segment {analysis['min_size']} windows; jump {analysis['jump']}. Reasons: {', '.join(md_text(reason) for reason in analysis['reason_codes']) or 'none'}.",''])
        if analysis.get('scaling'):
            scaling=analysis['scaling']
            lines.append(f"Scaling retains {len(scaling['feature_order'])} registered coordinates; all exclusions and population scaling parameters are in results.json.")
        for boundary in analysis['boundaries']:
            selected=next((finding for finding in findings if finding['finding_type']=='style_boundary_candidate' and finding['values']['boundary']['boundary_id']==boundary['boundary_id']),None)
            lines.extend([f'<a id="{_anchor("boundary",boundary["boundary_id"])}"></a>',
                          f"### Candidate between windows {boundary['window_index']} and {boundary['window_index']+1}",'',
                          f"Last eligible left record: {source(boundary['left_record_id'])}, {_utc(boundary['left_utc'])}. First eligible right record: {source(boundary['right_record_id'])}, {_utc(boundary['right_utc'])}.",
                          f"Full left window: {_utc(boundary['left_window_first_utc'])}–{_utc(boundary['left_window_last_utc'])}; full right window: {_utc(boundary['right_window_first_utc'])}–{_utc(boundary['right_window_last_utc'])}.",
                          f"Original zero-based record-order boundary interval: {md_text(boundary['record_interval'])}. Missing collection intervals limit the timing interpretation.",''])
            if selected:
                lines.extend(_table(['Adjacent representation','Distance','Status'],[
                    [md_text(item['method_id']+' / '+item['view']+(f" / n={item['n']}" if item['n'] else '')),number(item['value']),md_text(item['status']+' / '+str(item['reason'] or 'none'))]
                    for item in selected['values'].get('adjacent_distances',[])]))
            feature_table(selected)
    figure('surface_features.svg','Selected pooled surface feature trajectories and descriptive candidates')
    figure('adjacent_distances.svg','Adjacent primary-window raw masked and function-word distances')
    sensitivity=style.get('sensitivity',{})
    if sensitivity:
        lines.extend(['### Predefined sensitivity settings','',
                      'Stability across settings is not confidence. Constant no-variation measurements count as executed settings; insufficient settings are excluded from the denominator. Different window constructions use original record-order intervals. Endpoint touching is distinguished from interior overlap.',''])
        # Render the stored setting results independently of primary candidates.
        # Lists define presentation order; identifiers join the stored matching
        # facts. Counting exported objects is presentation, not a new matching run.
        executed_statuses={'ok','no_measurable_variation'}
        primary_by_stream={item['stream_id']:item for item in style.get('changes',[])}
        matches={(row['stream_id'],setting['setting_id']):setting
                 for row in sensitivity['same_window_stability'] for setting in row['settings']}
        setting_results={(setting['setting_id'],item['stream_id']):item
                         for setting in sensitivity['penalty_settings'] for item in setting['results']}
        overview=[]
        candidate_details=[]
        for stream in streams:
            stream_id=stream['stream_id']
            for setting in sensitivity['penalty_settings']:
                analysis=setting_results[(setting['setting_id'],stream_id)]
                matching=matches[(stream_id,setting['setting_id'])]
                executed=analysis['status'] in executed_statuses
                comparable=executed and primary_by_stream[stream_id]['status'] in executed_statuses
                overview.append([md_text(stream_names[stream_id]),number(setting['penalty_lambda']),
                                 md_text(analysis['status']),str(len(analysis['boundaries'])) if executed else 'unavailable',
                                 str(len(matching['matched_pairs'])) if comparable else 'not comparable' if executed else 'unavailable',
                                 str(len(matching['unmatched_setting_boundaries'])) if comparable else 'not comparable' if executed else 'unavailable'])
                if analysis['boundaries']:
                    candidate_details.append((setting,analysis,matching))
        lines.extend(['#### Penalty-setting overview','',
                      'Every predefined penalty setting is listed for each pooled and community stream. Counts use stored candidate and one-to-one matching results. Zero means an executed setting produced no candidates; unavailable means it did not execute. Matching is not comparable when the primary result is unavailable.','',
                      'Primary setting: '+', '.join('λ='+number(setting['penalty_lambda']) for setting in sensitivity['penalty_settings'] if setting['is_primary'])+'.',''])
        lines.extend(_table(['Stream','Setting λ','Status','Candidate count','Primary-matched count','Unmatched-setting candidate count'],overview))
        for setting,analysis,matching in candidate_details:
            stream_id=analysis['stream_id']
            lines.extend([f'<details><summary>Stored candidates: {md_text(stream_names[stream_id])}, λ={number(setting["penalty_lambda"])}'+(' (primary)' if setting['is_primary'] else ' (alternative)')+'</summary>','',
                          f"This setting has {len(analysis['boundaries'])} "+('candidate.' if len(analysis['boundaries'])==1 else 'candidates.'),
                          'These are stored descriptive boundary intervals. They do not identify an exact event date, a change of author, statistical significance or confidence.',''])
            for boundary in analysis['boundaries']:
                identity=json_text([setting['setting_id'],stream_id,boundary['boundary_id']])
                relation=('not comparable' if primary_by_stream[stream_id]['status'] not in executed_statuses else
                          'unmatched setting candidate' if boundary['window_index'] in matching['unmatched_setting_boundaries'] else 'primary-matched candidate')
                lines.extend([f'<a id="{_anchor("setting-boundary",identity)}"></a>',
                              f"Candidate between windows {boundary['window_index']} and {boundary['window_index']+1}: {relation}.",
                              f"Original zero-based record-order boundary interval: {md_text(boundary['record_interval'])}.",
                              f"Last eligible left record: {source(boundary['left_record_id'])}, {_utc(boundary['left_utc'])}. First eligible right record: {source(boundary['right_record_id'])}, {_utc(boundary['right_utc'])}.",
                              f"Full left window: {_utc(boundary['left_window_first_utc'])}–{_utc(boundary['left_window_last_utc'])}; full right window: {_utc(boundary['right_window_first_utc'])}–{_utc(boundary['right_window_last_utc'])}.",
                              'Missing collection intervals limit the timing interpretation.',''])
            lines.extend(['</details>',''])
        for row in sensitivity['same_window_stability']:
            lines.append(f"- {md_text(stream_names.get(row['stream_id'],row['stream_id']))}: {row['executed_setting_count']} settings executed, {row['skipped_setting_count']} skipped.")
            for boundary in row['boundaries']:
                lines.append(f"  Boundary {boundary['primary_window_index']} matched in {boundary['matched_in_k_of_m_executed_settings']} of {boundary['executed_setting_count']} executed settings, within ±{sensitivity['same_window_boundary_tolerance']} window.")
        lines.extend(['','<details><summary>Alternative constructions, exclusions and interval relationships</summary>',''])
        for setting in sensitivity['construction_settings']:
            lines.extend([f"**{md_text(setting['setting_type'])}**, target {setting['target_words']} words: {md_text(setting['status'])}. Excluded records: {source_list(setting['excluded_record_ids'],12)}. Reasons: {', '.join(md_text(reason) for reason in setting['reason_codes']) or 'none'}.",''])
            for comparison in setting['interval_comparisons']:
                lines.append(f"Stream {md_text(stream_names.get(comparison['stream_id'],comparison['stream_id']))}: {md_text(comparison['status'])}; {comparison['primary_boundary_count']} primary and {comparison['setting_boundary_count']} setting boundaries.")
                for row in comparison['comparisons']:
                    lines.append(f"- Primary record interval {md_text(row['primary_record_interval'])}; nearest setting interval {md_text(row['nearest_record_interval'])}: {md_text(row['relation'])}; record-position gap {number(row['record_position_gap'])}. Overlapping setting boundaries: {len(row['overlapping_boundary_ids'])}; touching: {len(row['touching_boundary_ids'])}.")
            lines.append('')
        within=sensitivity['within_community']
        lines.extend([f"Within-community control: {md_text(within['status'])}. Reasons: {', '.join(md_text(reason) for reason in within['reason_codes']) or 'none'}.",
                      'Alternative target/exclusion runs use pooled streams; community controls use primary community streams. Known edits are excluded only in that sensitivity view; unknown edits remain unknown. Repeat reduction does not change primary text or activity.','', '</details>',''])
    section('Linked-host observations','links')
    status('links')
    links=modules['links']['payload']
    summary=links.get('summary',{})
    if summary:
        lines.extend([f"Detected link occurrences: {summary['total_link_occurrences']}; valid HTTP(S): {summary['valid_http_occurrences']}; malformed: {summary['malformed_occurrences']}; unsafe schemes: {summary['unsafe_scheme_occurrences']}.",
                      f"Records with a valid link: {summary['records_with_valid_links']} of {summary['record_count']} ({number(summary['share_records_with_valid_links'])} fraction). Distinct normalized hosts: {summary['distinct_hosts']}.",
                      'Hostnames are parsed locally, with no fetching or DNS. They are not registrable domains. Link repetition does not establish advertising, payment or intent.',
                      'Unsafe schemes is the parser category for unsupported destinations, including scheme-less targets; it does not establish maliciousness. This module measures supplied body/title text. Native post destination fields outside the input contract are not included.',''])
        lines.extend(_table(['Hostname','Occurrences','Records with host / supplied records','Fraction of records','Fraction of valid HTTP(S) links','Sources'],[
            [md_text(row['hostname']),str(row['occurrences']),f"{row['record_count']} / {summary['record_count']}",number(row['share_of_records']),
             number(row['share_of_valid_http_links']),source_list(row['source_record_ids'],8)] for row in summary['hosts']]))
        lines.extend(['<details><summary>Host distributions by community and writing windows, including sensitivity</summary>',''])
        for grouping in ('by_community','by_window'):
            for row in links.get(grouping,[]):
                scope=row.get('subreddit') if grouping=='by_community' else row.get('window_id')
                scoped=row['summary']
                lines.append(f"- {md_text(grouping)} {md_text(scope)}: {scoped['valid_http_occurrences']} valid HTTP(S) occurrences in {scoped['records_with_valid_links']} of {scoped['record_count']} records. Hosts: "+', '.join(f"{md_text(host['hostname'])} ({host['occurrences']} occurrences / {host['record_count']} records)" for host in scoped['hosts'])+'.')
        lines.extend(['','</details>',''])
    section('Supplied interaction structure','interactions')
    status('interactions')
    interactions=modules['interactions']['payload']
    if interactions:
        lines.extend(['Parent/thread context is limited to supplied metadata. Creation-to-parent-creation delay is **not typing time or read-to-reply time**. Missing parents do not establish evasion.',''])
        threads=interactions.get('threads',[])
        lines.extend(_table(['Supplied thread','Records','Replies','Repeat participation','Source records'],[
            [md_text(row['thread_id']),str(row['record_count']),str(row['reply_count']),str(row['repeat_participation']).lower(),source_list(row['source_record_ids'],8)] for row in threads[:30]]))
        if len(threads)>30:
            lines.append(f'Showing 30 of {len(threads)} threads; {len(threads)-30} further rows are in results.json.')
        rows=interactions.get('parent_differences',[])
        lines.extend(_table(['Reply record','Supplied parent','Creation-to-parent-creation seconds','Timestamp source','Status / reason'],[
            [source(row['record_id']),md_text(row['parent_id']),number(row['creation_to_parent_creation_seconds']),md_text(row['parent_time_source']),
             md_text(row['status']+' / '+(', '.join(row['reason_codes']) or 'none'))] for row in rows[:30]]))
        lines.extend([f'Showing {min(30,len(rows))} of {len(rows)} parent-difference rows; {max(0,len(rows)-30)} omitted from this preview. Complete supplied-context observations remain in results.json.',''])
        sequence=interactions.get('community_sequence',{})
        if sequence:
            lines.extend(['<details><summary>Transitions across supplied community labels</summary>','',
                          'Transitions describe consecutive supplied timed records; intervening uncollected events are unknown.','',
                          '<pre>'+escape(json_text(sequence,indent=2))+'</pre>','','</details>',''])
    section('Evidence catalogue','evidence')
    lines.extend([f'{len(evidence)} evidence objects. Each example is an actual supplied raw-source or stored normalized-segment slice. Offsets labeled normalized_segment are not raw-source offsets.',
                  'Feature-rate examples show selected high-rate records; ordinary_context is background context, not feature proof.',''])
    groups:dict[str,list[Mapping[str,Any]]]=defaultdict(list)
    for item in evidence:
        source_ids.add(item['source_record_id'])
        groups[item['source_record_id']].append(item)
    for record_id in sorted(groups):
        items=groups[record_id]
        lines.extend([f'<details><summary>Source {md_text(record_id)} — {len(items)} evidence objects</summary>',''])
        for item in items:
            lines.extend([f'<a id="{_anchor("evidence",item["evidence_id"])}"></a>',
                          f"**{md_text(item['evidence_id'])}** — {source(record_id)}, field {md_text(item['source_field'])}, role {md_text(item['role'])}, side {md_text(item['side'] or 'not sided')}.",
                          f"Feature: {md_text(item['feature_id'] or 'ordinary context')}; {md_text(item['offset_basis'])} offsets {item['start']}–{item['end']}; original source lines {md_text(item['source_line_range'])}.",''])
            if excerpts=='included':
                lines.extend(['<pre class="source-excerpt">'+escape(item['text'])+'</pre>',''])
            else:
                lines.extend(['Source prose excerpt omitted at render time.',''])
        lines.extend(['</details>',''])
    section('Source reference index','sources')
    lines.extend(['Only actual supplied record IDs referenced in this report appear here. Full records/features are in the input snapshot and records_features.jsonl; this index does not claim complete context.',''])
    for identifier in sorted(source_ids):
        lines.extend([f'<a id="{_anchor("source",identifier)}"></a>',f'- {md_text(identifier)}',''])
    section('Methods, parameters and reproducibility','methods')
    lines.extend(['All narrative sentences are fixed templates. Measurements come from results.json and windows.jsonl. Full expanded parameters are in [resolved_config.json](resolved_config.json), feature formulas and evidence rules in [method_registry.json](method_registry.json), and complete source evidence in evidence.jsonl from the analysis directory.',
                  'Established primitives are separated from project adaptations. Published classification accuracy from the research below does not transfer to this descriptive pipeline.',''])
    rows=[['Character profiles / cosine','Configured within-segment case-sensitive character n-grams; cosine abstains on a zero norm.','S1, S7'],
          ['Fixed English profiles / JS','Project vocabulary plus OTHER_WORD; square-root Jensen–Shannon with base 2 and no smoothing.','S3, S8'],
          ['function_mask_v1','Project adaptation retaining fixed-list function words; length/punctuation information remains.','S2'],
          ['Classic Delta','Frozen reference; compatible per-1,000-word units; SD ≤ 1e-12 excluded. Missing reference means not run.','S4'],
          ['Exact reuse / configured token shingles','Separate equivalence relations; exact set Jaccard and directed containment; integer threshold decisions.','S9'],
          ['Temporal candidates','Account-local population scaling and family weights; L2 plus β per internal boundary.','S5, S6'],
          ['Production PELT adaptation','The optimizer identifier records the selected implementation. ruptures_pelt_pr383_a28574d_v1 uses the exact PR #383 delayed-pruning method; legacy pelt_l2_min_size_safe_pruning_v1 used the AHAS correction.','S5, S6, S16'],
          ['Canonical artifacts','Sorted finite UTF-8 JSON, fixed resources and environment; operational receipts are separate.','S12, S13'],
          ['Evaluation status','Numerical/synthetic engineering checks are distinct from unavailable real-world validation.','S10, S11, S15']]
    lines.extend(_table(['Method','Registered calculation or limitation','Source references'],rows))
    lines.extend(['The corrected PELT control flow addresses a tested early-pruning failure in the pinned upstream implementation when minimum segment length exceeds one. The penalized objective is unchanged; the adaptation is explicitly named and tested against independent small-sequence oracles.',
                  'Same-window sensitivity maximizes one-to-one matches, then minimizes displacement, then resolves lexicographic ties. Different constructions compare boundary intervals. No p-values, significance stars or confidence probabilities are produced.',''])
    for identifier,title,url in SOURCES:
        lines.append(f'- [{identifier}: {title}]({url})')
    lines.extend(['',f"- Suite version: {md_text(results['analysis']['suite_version'])}; report template: {TEMPLATE_VERSION}.",
                  f"- Canonical snapshot SHA-256: `{results['snapshot']['canonical_sha256']}`",
                  f"- Expanded configuration SHA-256: `{results['analysis']['config_sha256']}`",
                  f"- Implementation fingerprint: `{md_text(results['analysis']['implementation_fingerprint'])}`",
                  f"- Numerical environment: {md_text(results['analysis']['reference_environment'])}",'',
                  'Hashes establish correspondence with supplied bytes, not authenticity or authorship. Byte identity is claimed only for environments actually tested. Runtime, host and raw-file receipts are separate from canonical measurements.',''])
    lines.extend(['<details><summary>Frozen resource hashes</summary>',''])
    lines.extend(_table(['Resource','SHA-256'],[[md_text(name),md_text(value)] for name,value in sorted(results['analysis']['resource_sha256'].items())]))
    lines.extend(['</details>',''])
    return '\n'.join(lines).rstrip()+'\n'


def render_html(results: Mapping[str,Any], evidence: Sequence[Mapping[str,Any]] | None = None, *,
                excerpts: str = 'included', windows: Sequence[Mapping[str,Any]] | None = None) -> str:
    """Render static HTML with inert source text and controlled inline SVG charts."""
    from markdown_it import MarkdownIt
    from .charts import render_charts
    markdown=render_markdown(results,evidence,excerpts=excerpts,windows=windows)
    charts=render_charts(results,windows)
    # Only fixed generated image markers are replaced. Source image/link syntax
    # was entity-escaped before template insertion and cannot match these lines.
    import re
    for name,data in sorted(charts.items()):
        pattern=r'^<!-- AHAS_CHART:'+re.escape(name)+r' -->\n!\[([^\n]*)\]\('+re.escape(name)+r'\)$'
        markdown=re.sub(pattern,lambda match:'<figure>'+data.decode('utf-8')+'<figcaption>'+escape(match.group(1))+'</figcaption></figure>',markdown,flags=re.MULTILINE)
    body=MarkdownIt('commonmark',{'html':True,'linkify':False,'typographer':False}).enable('table').render(markdown)
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src \'none\'; base-uri \'none\'; form-action \'none\'">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Supplied account-history measurements</title><style>'
            'body{margin:0;background:#edf1f5;color:#243247;font:16px/1.6 system-ui,sans-serif}'
            'main{max-width:76rem;margin:0 auto;padding:2.6rem 3rem 5rem;background:white}'
            'h1{font-size:2.25rem;line-height:1.17;max-width:24ch;margin:.2rem 0 1.6rem}'
            'h2{font-size:1.55rem;line-height:1.3;border-top:2px solid #d8e3ec;padding-top:1.5rem;margin-top:2.8rem}'
            'h3{font-size:1.12rem;margin-top:1.6rem}a{color:#245c80;overflow-wrap:anywhere}'
            'p,li,td,th{overflow-wrap:anywhere}table{width:100%;border-collapse:collapse;font-size:.9rem;margin:1rem 0 1.4rem}'
            'th{background:#edf3f7;text-align:left}td,th{padding:.55rem .65rem;border-bottom:1px solid #dbe3eb;vertical-align:top}'
            'details{border:1px solid #d7e1eb;border-radius:.35rem;padding:.65rem .9rem;margin:.7rem 0}'
            'summary{cursor:pointer;font-weight:600}details[open]>summary{margin-bottom:1rem}'
            'pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f5f8;border-left:3px solid #66879e;padding:.9rem;font:14px/1.6 ui-monospace,monospace}'
            'code{overflow-wrap:anywhere}figure{margin:1.5rem 0}svg{display:block;width:100%;height:auto}'
            'figcaption{color:#526274;font-size:.85rem;margin-top:.3rem}'
            '@media(max-width:700px){main{padding:1.2rem}h1{font-size:1.8rem}table{font-size:.78rem}td,th{padding:.35rem}}'
            '@media print{body,main{background:white}main{padding:0}details{break-inside:avoid}h2{break-after:avoid}}'
            '</style></head><body><main>'+body+'</main></body></html>\n')
