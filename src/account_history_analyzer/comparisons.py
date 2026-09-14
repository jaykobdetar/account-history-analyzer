"""Window and manual comparison orchestration, separate from numerical primitives."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any
from .io import digest, thaw


def normalized_selection(selection: Mapping) -> dict:
    defaults = {'start_utc': None, 'end_utc': None, 'ids': None, 'kind': None, 'subreddit': None}
    result = {'schema_version': '1.0.0', 'allow_overlap': selection.get('allow_overlap', False)}
    for side in ('left', 'right'):
        result[side] = {**defaults, **thaw(selection[side])}
        if result[side]['ids'] is not None:
            result[side]['ids'] = sorted(result[side]['ids'])
    return result


def analyze_comparisons(features: Sequence[Mapping], config: Any,
                        selection: Mapping | None = None) -> tuple[dict, list[dict]]:
    """Qualified adjacent windows plus optional supplied manual slices."""
    from .style import compare_features
    from .windows import build_streams, select_comparison
    built = build_streams(features, config)
    by_id = {r['id']: r for r in features}
    windows = []
    streams = []
    comparisons = []
    for stream in built['streams']:
        swindows = stream['windows']
        windows.extend(thaw(swindows))
        streams.append({**{k: thaw(v) for k, v in stream.items() if k != 'windows'},
                        'window_ids': [w['window_id'] for w in swindows]})
        qualified = [w for w in swindows if w['qualified']]
        for left, right in zip(qualified, qualified[1:]):
            comp = compare_features([by_id[i] for i in left['record_ids']], [by_id[i] for i in right['record_ids']], config)
            comp.update(left_window_id=left['window_id'], right_window_id=right['window_id'])
            comp['comparison_id'] = 'cmp-'+digest(comp)[:24]
            comparisons.append(comp)
    manual = None
    if selection is not None:
        left, right, dependent = select_comparison(features, selection)
        manual = normalized_selection(selection)
        comp = compare_features(left, right, config)
        if dependent:
            comp['limitations'] = sorted(set(comp['limitations']) | {'overlapping_selection_dependent'})
        comp.update(left_window_id=None, right_window_id=None)
        comp['comparison_id'] = 'cmp-'+digest(comp)[:24]
        comparisons.append(comp)
    return {'streams': streams, 'omitted_communities': thaw(built['omitted_communities']),
            'comparisons': comparisons, 'manual_selection': manual}, windows
