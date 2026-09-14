"""RW-001 public presentation regressions; never use private pilot source text.

Source records are independently generated artificial prose. The case sidecar
substitutes explicitly constructed *exported presentation facts* only after the
analysis returns. It is never passed to feature extraction or optimization.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import json
from pathlib import Path

from markdown_it import MarkdownIt
import pytest

from account_history_analyzer.io import canonical_bytes, load_snapshot, thaw
from account_history_analyzer.pipeline import analyze
from account_history_analyzer.reporting import render_html, render_markdown

ROOT = Path(__file__).resolve().parents[1]
HEADERS = ['Stream', 'Setting λ', 'Status', 'Candidate count',
           'Primary-matched count', 'Unmatched-setting candidate count']
EXECUTED = {'ok', 'no_measurable_variation'}


class Parsed(HTMLParser):
    """Inspect the actual final HTML, including native details and table cells."""
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.tables=[]; self.text=[]; self.tags=[]; self.attrs=[]
        self.ids=[]; self.fragments=[]; self.table=None; self.row=None; self.cell=None
        self.feed(source); self.close()

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag); self.attrs.extend((tag,key,value) for key,value in attrs)
        values=dict(attrs)
        if 'id' in values: self.ids.append(values['id'])
        if values.get('href','').startswith('#'): self.fragments.append(values['href'][1:])
        if tag=='table': self.table=[]
        if tag=='tr': self.row=[]
        if tag in {'th','td'}: self.cell=[]

    def handle_data(self, value):
        self.text.append(value)
        if self.cell is not None: self.cell.append(value)

    def handle_endtag(self, tag):
        if tag in {'th','td'} and self.cell is not None:
            self.row.append(''.join(self.cell)); self.cell=None
        if tag=='tr' and self.row is not None:
            if self.table is not None: self.table.append(self.row)
            self.row=None
        if tag=='table' and self.table is not None:
            self.tables.append(self.table); self.table=None


def native(report, *, excerpts='included', output='html'):
    results,evidence,windows=report
    if output=='html':
        return render_html(results,evidence,windows=windows,excerpts=excerpts)
    markdown=render_markdown(results,evidence,windows=windows,excerpts=excerpts)
    return MarkdownIt('commonmark',{'html':True}).enable('table').render(markdown)


def overview(parsed):
    tables=[table for table in parsed.tables if table and table[0]==HEADERS]
    assert len(tables)==1, 'Every penalty setting/stream requires one inspectable sensitivity overview'
    return tables[0][1:]


@pytest.fixture(scope='module')
def exported(tmp_path_factory):
    """Small real pipeline output with legal primary memberships and evidence."""
    return build_exported_report(tmp_path_factory.mktemp('rw001-public'))


def build_exported_report(root):
    """Generate public source data for tests and the review-only sample report."""
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    records=[]
    for i in range(96):
        # Different lexical tokens avoid cross-record reuse while keeping each
        # source record over the fixed eligible-word guard; no case labels enter.
        word='token'+chr(97+i//26)+chr(97+i%26)
        text=' '.join(['the',word,'is',word,'and',word,'to',word]*16)+'.'
        if i>=48: text=text.upper().replace('.', ';')
        records.append({'schema_version':'1.0.0','id':f'r{i:03d}','account_id':'public-fixture',
            'kind':'comment','text':text,'status':'present','title':None,'subreddit':'synthetic_context',
            'created_utc':(datetime(2025,1,1,tzinfo=timezone.utc)+timedelta(hours=i)).isoformat().replace('+00:00','Z')})
    source=root/'records.jsonl'; manifest=root/'snapshot.json'
    source.write_bytes(b''.join(canonical_bytes(row) for row in records))
    metadata=json.loads((ROOT/'fixtures/arithmetic.snapshot.json').read_bytes())
    metadata.update(account_id='public-fixture',snapshot_id='public-report-fixture',text_format='plain')
    metadata['coverage'].update(start_utc=records[0]['created_utc'],end_utc=records[-1]['created_utc'])
    manifest.write_bytes(canonical_bytes(metadata))
    result=analyze(load_snapshot(source,manifest))
    assert result.exit_code==0
    return (thaw(result.results),
            [json.loads(line) for line in result.files['evidence.jsonl'].splitlines()],
            [json.loads(line) for line in result.files['windows.jsonl'].splitlines()])


def constructed(exported, case='alternative_only'):
    """Explicitly replace stored presentation observations, never rerun methods."""
    results,evidence,windows=deepcopy(exported)
    facts=json.loads((ROOT/'fixtures/reporting/rw001_report_cases.json').read_bytes())['cases'][case]
    style=results['modules']['style']['payload']; sensitivity=style['sensitivity']
    streams=[s for s in style['streams'] if s['kind']=='comment']
    assert len(streams)==2 and {s['scope_type'] for s in streams}=={'pooled','community'}
    by_window={w['window_id']:w for w in windows}
    by_change={change['stream_id']:change for change in style['changes']}
    style['streams']=streams
    # Primary findings belong to the genuine pipeline run. They are deliberately
    # omitted from the constructed presentation fixture rather than relabeled.
    results['findings']=[]
    style['changes']=[]; sensitivity['penalty_settings']=[]; sensitivity['same_window_stability']=[]
    parameters=[('primary',1.0,'ok'),('alternative',0.5,'ok'),
                ('constant',2.0,'no_measurable_variation'),('insufficient',4.0,'insufficient_data')]
    for name,value,status in parameters:
        sensitivity['penalty_settings'].append({'setting_id':name,'penalty_lambda':value,
            'is_primary':name=='primary','results':[]})
    for stream in streams:
        identifier=stream['stream_id']; original=by_change[identifier]
        assert len(original['window_ids'])>=10
        def boundary(index,setting):
            left=by_window[original['window_ids'][index-1]];right=by_window[original['window_ids'][index]]
            return {'boundary_id':f'public-{identifier}-{setting}-{index}','window_index':index,
                'left_window_id':left['window_id'],'right_window_id':right['window_id'],
                'left_record_id':left['record_ids'][-1],'right_record_id':right['record_ids'][0],
                'left_utc':left['last_utc'],'right_utc':right['first_utc'],
                'left_window_first_utc':left['first_utc'],'left_window_last_utc':left['last_utc'],
                'right_window_first_utc':right['first_utc'],'right_window_last_utc':right['last_utc'],
                'record_interval':[left['last_record_position'],right['first_record_position']],
                'left_window_record_ids':left['record_ids'],'right_window_record_ids':right['record_ids']}
        setting_rows=[]
        for setting in sensitivity['penalty_settings']:
            name=setting['setting_id'];status=next(status for n,_,status in parameters if n==name)
            indices=facts[name] if name in {'primary','alternative'} else []
            result={**deepcopy(original),'penalty_lambda':setting['penalty_lambda'],'status':status,
                'internal_boundaries':indices,'boundaries':[boundary(i,name) for i in indices],
                'reason_codes':['fewer_than_required_qualified_windows'] if status=='insufficient_data' else []}
            if status=='insufficient_data':
                result.update(window_ids=original['window_ids'][:2],scaling=None,penalty_beta=None,objective=None,sse=None)
            elif status=='no_measurable_variation': result.update(objective=None,sse=None)
            setting['results'].append(result)
            if name=='primary': style['changes'].append(deepcopy(result))
            pairs=([[i,i] for i in facts['primary']] if name=='primary' else facts['matched_pairs'] if name=='alternative' else [])
            unmatched=(facts['unmatched_setting'] if name=='alternative' else [])
            setting_rows.append({'setting_id':name,'penalty_lambda':setting['penalty_lambda'],'status':status,
                'reason_codes':result['reason_codes'],'matched_pairs':pairs,
                'unmatched_primary_boundaries':[i for i in facts['primary'] if i not in {p[0] for p in pairs}],
                'unmatched_setting_boundaries':unmatched})
        sensitivity['same_window_stability'].append({'stream_id':identifier,'executed_setting_count':3,
            'skipped_setting_count':1,'settings':setting_rows,
            'boundaries':[{'primary_window_index':i,'matched_in_k_of_m_executed_settings':2,
                'executed_setting_count':3,'matched_setting_ids':['primary','alternative']} for i in facts['primary']]})
    # The actual supported disabled state is a construction result; penalty
    # change schemas deliberately have no invented disabled enum.
    disabled=next(s for s in sensitivity['construction_settings'] if s['setting_type']=='repeat_reduced_near')
    assert disabled['status']=='not_run' and disabled['reason_codes']==['disabled_by_configuration']
    sensitivity['construction_settings']=[disabled]
    return results,evidence,windows


@pytest.mark.parametrize('output',['html','markdown'])
def test_zero_primary_does_not_erase_alternative_only_candidate(exported,output):
    report=constructed(exported)
    parsed=Parsed(native(report,output=output)); rows=overview(parsed)
    assert len(rows)==8
    for row in rows:
        if row[1]=='0.5': assert row[2:]==['ok','1','0','1']
        if row[1]=='1': assert row[2:]==['ok','0','0','0']
    text=' '.join(parsed.text)
    alternate=report[0]['modules']['style']['payload']['sensitivity']['penalty_settings'][1]
    for result in alternate['results']:
        for boundary in result['boundaries']:
            assert str(boundary['record_interval']) in text
            assert boundary['left_record_id'] in text and boundary['right_record_id'] in text
    assert 'not confidence' in text


def test_primary_matching_details_and_additional_setting_candidate_both_survive(exported):
    report=constructed(exported,'matched_plus_extra'); parsed=Parsed(native(report))
    rows=overview(parsed)
    assert [row[2:] for row in rows if row[1]=='0.5']==[['ok','2','1','1']]*2
    assert [row[2:] for row in rows if row[1]=='1']==[['ok','1','1','0']]*2
    text=' '.join(parsed.text)
    assert 'matched in 2 of 3 executed settings' in text
    for result in report[0]['modules']['style']['payload']['sensitivity']['penalty_settings'][1]['results']:
        assert str(result['boundaries'][1]['record_interval']) in text


def test_executed_zero_insufficient_and_disabled_are_distinct(exported):
    parsed=Parsed(native(constructed(exported))); rows=overview(parsed)
    assert [row[2:] for row in rows if row[1]=='2']==[['no_measurable_variation','0','0','0']]*2
    skipped=[row[2:] for row in rows if row[1]=='4']
    assert len(skipped)==2
    assert all(row[0]=='insufficient_data' and all(cell=='unavailable' for cell in row[1:]) for row in skipped)
    text=' '.join(parsed.text)
    assert 'not_run' in text and 'disabled_by_configuration' in text


def test_unavailable_primary_does_not_turn_matching_into_a_reassuring_zero(exported):
    """Render explicit stored availability; do not infer it from another row."""
    report=constructed(exported);style=report[0]['modules']['style']['payload'];sensitivity=style['sensitivity']
    primary=next(setting for setting in sensitivity['penalty_settings'] if setting['is_primary'])
    for result in [*style['changes'],*primary['results']]:
        result.update(status='insufficient_data',reason_codes=['fewer_than_required_qualified_windows'],
                      scaling=None,penalty_beta=None,objective=None,sse=None,window_ids=result['window_ids'][:2])
    for stream in sensitivity['same_window_stability']:
        stream.update(executed_setting_count=2,skipped_setting_count=2)
        row=next(row for row in stream['settings'] if row['setting_id']=='primary')
        row.update(status='insufficient_data',reason_codes=['fewer_than_required_qualified_windows'])
    rows=overview(Parsed(native(report)))
    assert [row[2:] for row in rows if row[1]=='0.5']==[['ok','1','not comparable','not comparable']]*2
    assert [row[2:] for row in rows if row[1]=='1']==[['insufficient_data','unavailable','unavailable','unavailable']]*2


def reversed_maps(value):
    if isinstance(value,dict):return {key:reversed_maps(item) for key,item in reversed(list(value.items()))}
    if isinstance(value,list):return [reversed_maps(item) for item in value]
    return value


def test_key_permutations_are_inert_and_stream_setting_lists_keep_their_order(exported):
    report=constructed(exported,'matched_plus_extra')
    # Different stream counts make a positional-zip join observably wrong.
    sensitivity=report[0]['modules']['style']['payload']['sensitivity']
    community=report[0]['modules']['style']['payload']['streams'][1]['stream_id']
    alternate=next(setting for setting in sensitivity['penalty_settings'] if setting['setting_id']=='alternative')
    change=next(row for row in alternate['results'] if row['stream_id']==community)
    change['boundaries']=change['boundaries'][1:]; change['internal_boundaries']=[7]
    stability=next(row for row in sensitivity['same_window_stability'] if row['stream_id']==community)
    match=next(row for row in stability['settings'] if row['setting_id']=='alternative')
    match.update(matched_pairs=[],unmatched_primary_boundaries=[3],unmatched_setting_boundaries=[7])
    stability['boundaries'][0].update(matched_in_k_of_m_executed_settings=1,matched_setting_ids=['primary'])
    original=native(report)
    assert native(tuple(reversed_maps(item) for item in report))==original
    baseline=overview(Parsed(original)); assert len(baseline)==8
    # The renderer must join metadata by identifiers. Reordering unrelated join
    # inputs must not change rows or silently associate counts to another stream.
    joined=deepcopy(report); sensitivity=joined[0]['modules']['style']['payload']['sensitivity']
    sensitivity['same_window_stability'].reverse()
    for row in sensitivity['same_window_stability']: row['settings'].reverse()
    for setting in sensitivity['penalty_settings']: setting['results'].reverse()
    assert overview(Parsed(native(joined)))==baseline
    reordered=deepcopy(report); style=reordered[0]['modules']['style']['payload']
    style['streams'].reverse(); style['sensitivity']['penalty_settings'].reverse()
    changed=overview(Parsed(native(reordered)))
    assert changed==list(reversed(baseline))


@pytest.mark.parametrize('excerpts',['included','none'])
@pytest.mark.parametrize('output',['html','markdown'])
def test_source_safety_excerpt_omission_and_lossless_ngram_labels(exported,excerpts,output):
    report=constructed(exported,'matched_plus_extra'); results,evidence,_=report
    hostile='<script>fixture_only()</script><img src="https://invalid.test/x" onerror="x()"> [x](javascript:x)'
    evidence[0]['text']=hostile
    style=results['modules']['style']['payload']
    style['streams'][1]['subreddit']=hostile
    # Source identifiers appear in both new candidate details and the shared
    # source catalogue. They must become inert text with digest-only anchors.
    alternate=style['sensitivity']['penalty_settings'][1]['results'][0]['boundaries'][0]
    alternate['left_record_id']='left-'+hostile
    alternate['right_record_id']='right-'+hostile
    alternate['boundary_id']='boundary-'+hostile
    labels=[' a  b ','\\u0020','\t\n','<tag>','a|b','\u00a0']
    distance=next(d for c in style['comparisons'] for d in c['distances'] if d['method_id']=='cosine_distance_v1' and len(d['contributions'])>=len(labels))
    for row,label in zip(distance['contributions'],labels):row['feature_id']=label
    parsed=Parsed(native(report,excerpts=excerpts,output=output))
    assert not set(parsed.tags)&{'script','iframe','object','embed'}
    assert not any(key.startswith('on') or key in {'srcdoc','srcset'} for _,key,_ in parsed.attrs)
    sources=[value for _,key,value in parsed.attrs if key=='src']
    if output=='html': assert sources==[] and 'img' not in parsed.tags
    else:
        assert sorted(sources)==sorted(['activity_daily.svg','activity_hourly.svg','eligible_word_volume.svg',
                                        'surface_features.svg','adjacent_distances.svg'])
    assert not any((value or '').lower().startswith(('javascript:','data:','vbscript:'))
                   for _,key,value in parsed.attrs if key in {'href','src'})
    assert len(parsed.ids)==len(set(parsed.ids))
    assert set(parsed.fragments)<=set(parsed.ids)
    contribution_labels=[row[0] for table in parsed.tables if table and table[0][:2]==['Feature','Left rate'] for row in table[1:]]
    decoded=[]
    for label in contribution_labels:
        if label.startswith('"'):decoded.append(json.loads(label))
    if excerpts=='included':
        assert all(label in decoded for label in labels)
        assert hostile in ''.join(parsed.text)
    else:
        # Hostile subreddit metadata remains inert, but source excerpt and
        # character-ngram example disclosure is disabled.
        assert decoded==[]
        assert not any(tag=='pre' and key=='class' and 'source-excerpt' in (value or '') for tag,key,value in parsed.attrs)
    assert len(overview(parsed))==8


@pytest.mark.parametrize('excerpts',['included','none'])
def test_saved_json_replay_and_render_do_not_mutate_any_stored_measurements(exported,tmp_path,excerpts):
    report=constructed(exported,'matched_plus_extra')
    before=canonical_bytes(report)
    paths=[]
    for name,value in zip(('results','evidence','windows'),report):
        path=tmp_path/(name+'.json');path.write_bytes(canonical_bytes(value));paths.append(path)
    loaded=tuple(json.loads(path.read_bytes()) for path in paths)
    for renderer in (render_html,render_markdown):
        actual=renderer(report[0],report[1],windows=report[2],excerpts=excerpts)
        replay=renderer(loaded[0],loaded[1],windows=loaded[2],excerpts=excerpts)
        assert actual==replay
    assert canonical_bytes(report)==before


def test_render_uses_stored_candidates_and_matches_without_running_methods(exported,monkeypatch):
    from account_history_analyzer import changepoints,sensitivity,style
    report=constructed(exported,'matched_plus_extra')
    def unexpected(*args,**kwargs):
        raise AssertionError('The renderer must not run an analytical method')
    monkeypatch.setattr(changepoints,'analyze_changes',unexpected)
    monkeypatch.setattr(sensitivity,'maximum_boundary_matching',unexpected)
    monkeypatch.setattr(style,'compare_features',unexpected)
    assert len(overview(Parsed(native(report))))==8
