"""Deterministic static SVG charts drawn only from exported measurements.

No plotting backend, network asset, font file, current time, random identifier or
feature recalculation enters these charts. SVG metadata retains plotted values;
missing values break trajectories instead of being filled or interpolated.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
import json
from typing import Any

CHART_VERSION = "1.0.0"
CHART_NAMES = ("activity_daily.svg", "activity_hourly.svg", "eligible_word_volume.svg",
               "surface_features.svg", "adjacent_distances.svg")


def _fmt(value: float) -> str:
    return f"{value:.6g}"


def _panel(title: str, unit: str, labels: Sequence[str], values: Sequence[float | int | None], *,
           top: int, bars: bool = False, x_values: Sequence[float] | None = None,
           boundaries: Sequence[int] = (), colors: Sequence[str] | None = None,
           x_max: float | None = None) -> list[str]:
    # Keep the plot's upper tick below the title/unit block, including its font
    # height. A shared y coordinate previously made the top tick overlap units.
    left, width, height, baseline = 76.0, 850.0, 120.0, top + 174.0
    result = [f'<text x="20" y="{top+18}" font-size="16" font-weight="600">{escape(title)}</text>',
              f'<text x="20" y="{top+36}" font-size="11" fill="#526274">{escape(unit)}</text>']
    data = {"title": title, "unit": unit, "labels": list(labels), "values": list(values), "boundaries": list(boundaries)}
    result.append('<metadata>'+escape(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',',':')))+'</metadata>')
    present = [float(value) for value in values if value is not None]
    if not present:
        result.append(f'<text x="{left}" y="{top+94}" font-size="13" fill="#526274">No computable observations in this scope.</text>')
        return result
    positions = list(x_values) if x_values is not None else [float(index) for index in range(len(values))]
    domain = max(x_max if x_max is not None else max(positions, default=0), 1.0)
    maximum = max(max(present), 0.0)
    maximum = maximum * 1.08 if maximum else 1.0
    def x(value: float) -> float:
        return left + width * (value + 0.5) / (domain + 1.0)
    def y(value: float) -> float:
        return baseline - height * value / maximum
    for fraction in (0,0.5,1):
        at = baseline - height*fraction
        result.append(f'<line x1="{left}" y1="{_fmt(at)}" x2="{left+width}" y2="{_fmt(at)}" stroke="#dbe2ea"/>')
        result.append(f'<text x="{left-8}" y="{_fmt(at+4)}" text-anchor="end" font-size="11">{_fmt(maximum*fraction)}</text>')
    for boundary in boundaries:
        position = x(boundary - 0.5)
        result.append(f'<line x1="{_fmt(position)}" y1="{baseline-height}" x2="{_fmt(position)}" y2="{baseline}" stroke="#a83242" stroke-dasharray="4 4"><title>Descriptive candidate between windows {boundary} and {boundary+1}</title></line>')
    if bars:
        bar_width = width / max(len(values),2) * 0.72
        for index,value in enumerate(values):
            if value is None:
                continue
            color = colors[index] if colors else '#296589'
            result.append(f'<rect x="{_fmt(x(positions[index])-bar_width/2)}" y="{_fmt(y(value))}" width="{_fmt(bar_width)}" height="{_fmt(height*value/maximum)}" fill="{color}" data-value="{escape(str(value),quote=True)}"><title>{escape(labels[index])}: {_fmt(value)} {escape(unit)}</title></rect>')
    else:
        runs: list[list[tuple[float,float]]] = [[]]
        for position,value in zip(positions,values,strict=True):
            if value is None:
                if runs[-1]:
                    runs.append([])
                continue
            runs[-1].append((x(position),y(value)))
        for run in runs:
            if len(run)>=2:
                result.append('<polyline fill="none" stroke="#296589" stroke-width="2" points="'+' '.join(f'{_fmt(a)},{_fmt(b)}' for a,b in run)+'"/>')
        for index,value in enumerate(values):
            if value is not None:
                result.append(f'<circle cx="{_fmt(x(positions[index]))}" cy="{_fmt(y(value))}" r="3" fill="#296589" data-value="{escape(str(value),quote=True)}"><title>{escape(labels[index])}: {_fmt(value)} {escape(unit)}</title></circle>')
    tick_indices = sorted({round(index*(len(labels)-1)/min(5,len(labels)-1)) for index in range(min(5,len(labels)-1)+1)}) if len(labels)>1 else [0]
    for index in tick_indices:
        if labels:
            result.append(f'<text x="{_fmt(x(positions[index]))}" y="{baseline+20}" text-anchor="middle" font-size="10">{escape(labels[index])}</text>')
    return result


def _svg(name: str, title: str, panels: list[dict[str,Any]], notes: Sequence[str]) -> bytes:
    panel_height = 225
    height = 60 + max(1,len(panels))*panel_height + 20*len(notes)
    identifier = name.removesuffix('.svg').replace('_','-')
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 {height}" role="img" aria-labelledby="{identifier}-title">',
           f'<title id="{identifier}-title">{escape(title)}</title>',
           '<rect width="100%" height="100%" fill="#ffffff"/>',
           '<g font-family="system-ui, sans-serif" fill="#253347">',
           f'<text x="20" y="30" font-size="21" font-weight="600">{escape(title)}</text>']
    if not panels:
        panels=[{"title":"Supplied history","unit":"No eligible observations","labels":[],"values":[]}]
    for index,panel in enumerate(panels):
        parts.extend(_panel(**panel,top=48+panel_height*index))
    for index,note in enumerate(notes):
        parts.append(f'<text x="20" y="{55+len(panels)*panel_height+20*index}" font-size="11" fill="#526274">{escape(note)}</text>')
    parts.extend(['</g>','</svg>\n'])
    return '\n'.join(parts).encode('utf-8')


def render_charts(results: Mapping[str,Any], windows: Sequence[Mapping[str,Any]] | None = None) -> dict[str,bytes]:
    """Return five fixed-basename SVG artifacts from result/window exports only."""
    modules=results['modules']
    activity=modules['activity']['payload']
    daily=activity.get('events_per_day',[])
    charts={
        'activity_daily.svg':_svg('activity_daily.svg','Observed supplied events by UTC date',[
            {'title':'All distinct timed supplied events','unit':'events per UTC calendar date',
             'labels':[row['date'] for row in daily],'values':[row['event_count'] for row in daily], 'bars':True,
             'colors':['#b27b20' if row['known_gap'] else '#748594' if row['edge_day'] else '#296589' for row in daily]}],
            ['Amber: declared collection gap; gray: incomplete edge day. Zero bars mean no supplied events.',
             'Every exported daily bin is plotted; coverage is a supplier declaration.']),
        'activity_hourly.svg':_svg('activity_hourly.svg','UTC hour histogram across supplied dates',[
            {'title':'Distinct timed supplied events','unit':'events aggregated across all dates in each UTC hour',
             'labels':[f'{hour:02d}:00' for hour in range(24)],
             'values':activity.get('hour_histogram',[]) if activity.get('event_count',0) else [None]*24,'bars':True}],
            ['Hour bins aggregate dates. Activity in all bins does not establish uninterrupted use.']),
    }
    style=modules['style']['payload']
    by_window={window['window_id']:window for window in windows or []}
    stream_windows=[]
    for stream in style.get('streams',[]):
        if stream['scope_type']=='pooled':
            swindows=[by_window[identifier] for identifier in stream['window_ids'] if identifier in by_window]
            stream_windows.append((stream,swindows))
    volume=[]
    surfaces=[]
    distances=[]
    changes={change['stream_id']:change for change in style.get('changes',[])}
    comparisons={(comparison['left_window_id'],comparison['right_window_id']):comparison for comparison in style.get('comparisons',[])
                 if comparison['left_window_id'] is not None and comparison['right_window_id'] is not None}
    selected_features=[('Comma rate','per_1000_word_tokens',lambda window:window['features']['rates']['punctuation_per_1000_words']['comma']),
                       ('Semicolon rate','per_1000_word_tokens',lambda window:window['features']['rates']['punctuation_per_1000_words']['semicolon']),
                       ('Uppercase fraction','uppercase / cased code points',lambda window:window['features']['rates']['uppercase_fraction']),
                       ('Mean word length','alphabetic code points / retained word token',lambda window:window['features']['rates']['average_word_length'])]
    for stream,swindows in stream_windows:
        scope='Pooled '+('comments' if stream['kind']=='comment' else 'submission bodies')
        labels=[str(index+1) for index in range(len(swindows))]
        boundaries=changes.get(stream['stream_id'],{}).get('internal_boundaries',[])
        volume.append({'title':scope,'unit':'retained word tokens per whole-record window; x = window ordinal',
                       'labels':labels,'values':[window['word_count'] for window in swindows],'bars':True,
                       'colors':['#748594' if window['remainder'] else '#296589' for window in swindows],
                       'boundaries':boundaries})
        for label,unit,extract in selected_features:
            surfaces.append({'title':scope+' — '+label,'unit':unit+'; x = window ordinal',
                             'labels':labels,'values':[extract(window) for window in swindows],'boundaries':boundaries})
        for method,view,n,label in [('cosine_distance_v1','retained_prose',4,'Raw 4-gram cosine'),
                                    ('cosine_distance_v1','function_mask_v1',4,'Masked 4-gram cosine'),
                                    ('function_word_js_v1','lexical_tokens',None,'Function-word base-2 JS')]:
            values=[]
            qualified=[window for window in swindows if window['qualified']]
            for left,right in zip(qualified,qualified[1:]):
                comparison=comparisons.get((left['window_id'],right['window_id']))
                distance=next((item for item in comparison['distances'] if item['method_id']==method and item['view']==view and item['n']==n),None) if comparison else None
                values.append(distance['value'] if distance is not None and distance['status']=='ok' else None)
            distances.append({'title':scope+' — '+label,'unit':'distance in the named representation; x = adjacent window pair',
                              'labels':[f'{index+1}–{index+2}' for index in range(len(values))],
                              'values':values,'x_values':[index+0.5 for index in range(len(values))],
                              'x_max':float(max(len(qualified)-1,1)),'boundaries':boundaries})
    charts['eligible_word_volume.svg']=_svg('eligible_word_volume.svg','Eligible writing volume in primary windows',volume,
        ['Blue: qualified window; gray: visible short remainder. Dashed red: descriptive candidate boundary.',
         'Pooled scopes only. Separate community streams have overlapping membership; counts are not added.'])
    charts['surface_features.svg']=_svg('surface_features.svg','Selected observed feature trajectories',surfaces,
        ['Lines connect observed windows in order; horizontal spacing is not elapsed time. Missing values break lines.',
         'Dashed red marks a descriptive candidate. Measurements do not establish cause or a change of author.'])
    charts['adjacent_distances.svg']=_svg('adjacent_distances.svg','Adjacent primary-window representation distances',distances,
        ['Representations have different distance distributions and are not interchangeable probability scales.',
         'Missing comparisons break lines. Dashed red marks descriptive candidates; no author probability is implied.'])
    return {name:charts[name] for name in CHART_NAMES}
