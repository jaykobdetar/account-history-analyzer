"""Evidence-backed finding envelopes. Every excerpt is an actual source slice."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any
from .io import Snapshot, digest, thaw
from .registry import method_version


def evidence_object(record_id: str, text: str, *, source_field: str = 'text',
                    representation: str = 'retained_prose', segment_index: int | None = None,
                    start: int = 0, end: int | None = None, role: str = 'source_context',
                    feature_id: str | None = None, side: str | None = None,
                    source_line_range: Sequence[int] | None = None) -> dict[str, Any]:
    """Construct evidence from the exact view passed by a caller, with named offsets."""
    end = len(text) if end is None else end
    if not 0 <= start <= end <= len(text):
        raise ValueError('Evidence slice is outside supplied view')
    result = {'source_record_id': record_id, 'source_field': source_field,
              'representation': representation, 'segment_index': segment_index,
              'offset_basis': 'raw_source' if representation == 'raw_source' else 'normalized_segment',
              'start': start, 'end': end, 'text': text[start:end], 'role': role,
              'feature_id': feature_id, 'side': side,
              'source_line_range': list(source_line_range) if source_line_range is not None else None}
    return {'evidence_id': 'e-'+digest(result)[:24], **result}


def finding(kind: str, *, method: str, scope: dict, values: dict,
            records: Sequence[str] = (), windows: Sequence[str] = (), evidence: Sequence[str] = (),
            status: str = 'observed', limitations: Sequence[str] = (), parameters: dict | None = None,
            level: str = 'measurement') -> dict[str, Any]:
    result = {'finding_type': kind, 'epistemic_level': level, 'status': status, 'scope': scope,
              'method_id': method, 'method_version': method_version(method), 'parameters': parameters or {},
              'values': values, 'source_record_ids': list(dict.fromkeys(records)),
              'window_ids': list(dict.fromkeys(windows)), 'evidence_refs': list(dict.fromkeys(evidence)),
              'limitations': sorted(set(limitations)), 'related_finding_ids': []}
    return {'finding_id': 'f-'+digest(result)[:24], **result}


def context_evidence(record: Mapping, *, role: str = 'ordinary_context', side: str | None = None,
                     feature_id: str | None = None) -> dict | None:
    """An actual normalized source segment, labeled context, never an invented example."""
    if not record['segments']:
        return None
    index, anchor = 0, 0
    if feature_id:
        from .registry import PUNCTUATION
        import re
        punctuation = feature_id.split('.')[1] if feature_id.startswith('punctuation.') else None
        word = feature_id.split('.')[1] if feature_id.startswith('function_word.') else None
        for i, seg in enumerate(record['segments']):
            position = -1
            if punctuation in PUNCTUATION:
                position = seg['text'].find(PUNCTUATION[punctuation])
            elif punctuation == 'ascii_period_runs':
                match = re.search(r'\.{3,}', seg['text'])
                position = match.start() if match else -1
            elif word:
                position = next((t['start'] for t in record['token_offsets'][i] if t['normalized'] == word), -1)
            elif feature_id == 'uppercase_fraction':
                position = next((j for j,c in enumerate(seg['text']) if c.isupper()), -1)
            if position >= 0:
                index, anchor = i, position
                break
    segment = record['segments'][index]
    start = max(0, anchor - 100)
    return evidence_object(record['id'], segment['text'], source_field=segment['source_field'],
                           segment_index=index, start=start, end=min(start+400, len(segment['text'])), role=role, side=side,
                           feature_id=feature_id, source_line_range=segment['source_line_range'])


def validate_references(findings: Sequence[Mapping], evidence: Sequence[Mapping],
                        features: Sequence[Mapping], windows: Sequence[Mapping], snapshot: Snapshot) -> None:
    """Validate all identifiers and exact source slices before artifact publication."""
    records = {r['id']: r for r in snapshot.records}
    by_feature = {r['id']: r for r in features}
    window_ids = {w['window_id'] for w in windows}
    by_evidence = {e['evidence_id']: e for e in evidence}
    finding_ids = {f['finding_id'] for f in findings}
    if len(by_evidence) != len(evidence) or len(finding_ids) != len(findings):
        raise ValueError('Duplicate finding/evidence identifier')
    for e in evidence:
        if e['source_record_id'] not in records:
            raise ValueError('Evidence references absent source record')
        if e['representation'] == 'raw_source':
            source = records[e['source_record_id']][e['source_field']]
        else:
            view = by_feature[e['source_record_id']]
            if e['source_field'] == 'title':
                view = view['title']
            source = view['segments'][e['segment_index']]['text']
        if source[e['start']:e['end']] != e['text']:
            raise ValueError('Evidence is not an actual source slice')
    for f in findings:
        if not set(f['source_record_ids']) <= records.keys() or not set(f['window_ids']) <= window_ids:
            raise ValueError('Finding references absent source/window')
        if not set(f['evidence_refs']) <= by_evidence.keys() or not set(f['related_finding_ids']) <= finding_ids:
            raise ValueError('Finding references absent evidence/finding')


def reuse_findings(payload: Mapping, features: Sequence[Mapping], snapshot: Snapshot,
                   config: Any) -> tuple[list[dict], list[dict]]:
    """Link substantial exact/pair matches to actual source contexts and passages."""
    by_id = {r['id']: r for r in features}
    raw = {r['id']: r for r in snapshot.records}
    findings: list[dict] = []
    evidence: dict[str, dict] = {}
    for group in payload['exact_groups']:
        if not group['substantial']:
            continue
        refs = []
        for rid in group['record_ids'][:2]:
            if group['match_type'] == 'raw_text_identical':
                e = evidence_object(rid, raw[rid]['text'], representation='raw_source',
                                    end=min(400, len(raw[rid]['text'])), role='exact_match_context')
            else:
                e = context_evidence(by_id[rid], role='exact_match_context')
            if e:
                evidence[e['evidence_id']] = e
                refs.append(e['evidence_id'])
        findings.append(finding(group['match_type'], method='exact_reuse_v1',
                                scope={'kind': 'supplied_body_text', 'group_id': group['group_id']},
                                values={'record_count': len(group['record_ids']), 'retained_word_counts': thaw(group['retained_word_counts']),
                                        'match_sha256': group['match_sha256']},
                                records=group['record_ids'], evidence=refs, limitations=['match_does_not_establish_intent'] + list(group['reason_codes'])))
    for pair in payload['pairs']:
        refs = []
        for passage in pair['matching_passages']:
            for side in ('left', 'right'):
                rid = pair[side+'_record_id']
                loc = passage[side]
                segment = by_id[rid]['segments'][loc['segment_index']]
                e = evidence_object(rid, segment['text'], segment_index=loc['segment_index'],
                                    start=loc['normalized_start'], end=loc['normalized_end'],
                                    role='contiguous_lexical_match', side=side,
                                    source_line_range=segment['source_line_range'])
                evidence[e['evidence_id']] = e
                refs.append(e['evidence_id'])
        values = {k: thaw(v) for k, v in pair.items() if k not in {'matching_passages', 'left_record_id', 'right_record_id'}}
        findings.append(finding('shared_token_shingles', method='shingle_reuse_v1',
                                scope={'kind': 'supplied_body_text'}, values=values,
                                records=[pair['left_record_id'], pair['right_record_id']], evidence=refs,
                                limitations=['match_does_not_establish_intent', 'shared_shingles_are_not_one_contiguous_passage',
                                             'normalized_lexical_match_may_differ_in_case_and_punctuation'],
                                parameters=thaw(config['reuse'])))
    return findings, list(evidence.values())


def comparison_findings(payload: Mapping, features: Sequence[Mapping], windows: Sequence[Mapping],
                        config: Any) -> tuple[list[dict], list[dict]]:
    """Select changing and stable measured features, with deterministic source context."""
    from .style import feature_values
    by_id = {r['id']: r for r in features}
    by_window = {w['window_id']: w for w in windows}
    evidence: dict[str, dict] = {}
    findings = []
    for comp in payload['comparisons']:
        if comp['status'] != 'ok':
            continue
        # Comparison helper includes exact side record IDs; adjacent membership
        # can also be resolved from exported windows without inferring selection.
        if comp['left_window_id'] is not None:
            sides = {side: [by_id[i] for i in by_window[comp[side+'_window_id']]['record_ids']] for side in ('left','right')}
        else:
            from .windows import select_comparison
            l, r, _ = select_comparison(features, payload['manual_selection'])
            sides = {'left': l, 'right': r}
        changes = [c for c in comp['surface_changes'] if c['absolute_change'] is not None]
        maximum = config['report']['maximum_feature_explanations']
        changing = sorted(changes, key=lambda c: (-c['absolute_change'], c['feature_id']))[:(maximum+1)//2]
        used = {c['feature_id'] for c in changing}
        stable = sorted((c for c in changes if c['feature_id'] not in used), key=lambda c: (c['absolute_change'], c['feature_id']))[:maximum-len(changing)]
        refs = []
        for side, records in sides.items():
            qualifying = [r for r in records if r['usable'] and r['counts']['retained_words'] >= config['style']['minimum_record_words']]
            for change in changing + stable:
                fid = change['feature_id']
                candidates = [(feature_values(r).get(fid), pos, r) for pos,r in enumerate(qualifying)]
                candidates = [item for item in candidates if item[0] is not None]
                candidates.sort(key=lambda item: (-item[0], item[1]))
                for _, _, record in candidates[:config['report']['examples_per_side_per_feature']]:
                    e = context_evidence(record, role='feature_rate_context', feature_id=fid, side=side)
                    if e:
                        evidence[e['evidence_id']] = e
                        refs.append(e['evidence_id'])
            if qualifying:
                lengths = sorted(r['counts']['retained_words'] for r in qualifying)
                n = len(lengths)
                median = (lengths[(n-1)//2] + lengths[n//2])/2
                ordinary = min(enumerate(qualifying), key=lambda item: (abs(item[1]['counts']['retained_words']-median),item[0]))[1]
                e = context_evidence(ordinary, side=side)
                if e:
                    evidence[e['evidence_id']] = e
                    refs.append(e['evidence_id'])
        record_ids = list(dict.fromkeys(r['id'] for records in sides.values() for r in records))
        finding_values = {'comparison_id': comp['comparison_id'], 'samples': thaw(comp['samples']),
                          'changing_features': thaw(changing), 'stable_features': thaw(stable)}
        findings.append(finding('style_comparison', method='feature_evidence_v1', scope={'observed_text': True},
                                values=finding_values, records=record_ids,
                                windows=[comp[x] for x in ('left_window_id','right_window_id') if comp[x] is not None],
                                evidence=refs, level='derived_comparison', limitations=comp['limitations'],
                                parameters={'config_reference': 'resolved_config.json'}))
    return findings, list(evidence.values())


def change_findings(changes: Sequence[Mapping], style: Mapping, features: Sequence[Mapping],
                    windows: Sequence[Mapping], config: Any,
                    comparison_objects: Sequence[Mapping]) -> tuple[list[dict], list[dict]]:
    """Describe optimizer boundaries and cross-reference their local comparisons."""
    comps = {(c['left_window_id'], c['right_window_id']): c for c in style['comparisons']}
    contexts = {f['values']['comparison_id']: f for f in comparison_objects}
    stream_by_id = {s['stream_id']: s for s in style['streams']}
    by_feature = {r['id']: r for r in features}
    findings, evidence = [], {}
    for analysis in changes:
        for boundary in analysis['boundaries']:
            comp = comps.get((boundary['left_window_id'], boundary['right_window_id']))
            context = contexts.get(comp['comparison_id']) if comp else None
            refs = list(context['evidence_refs']) if context else []
            if not refs:
                for side in ('left', 'right'):
                    ids = boundary[side+'_window_record_ids']
                    if ids:
                        e = context_evidence(by_feature[ids[len(ids)//2]], side=side)
                        if e:
                            evidence[e['evidence_id']] = e
                            refs.append(e['evidence_id'])
            stream = stream_by_id[analysis['stream_id']]
            values = {'boundary': thaw(boundary), 'penalty_beta': analysis['penalty_beta'],
                      'objective': analysis['objective'], 'penalty_lambda': analysis['penalty_lambda'],
                      'samples': thaw(comp['samples']) if comp else {},
                      'changing_features': thaw(context['values']['changing_features']) if context else [],
                      'stable_features': thaw(context['values']['stable_features']) if context else [],
                      'adjacent_distances': [{k: thaw(d[k]) for k in ('method_id','view','n','value','status','reason')}
                                             for d in comp['distances']] if comp else []}
            f = finding('style_boundary_candidate', method='pelt_l2_v1',
                        scope={'stream_id': analysis['stream_id'], 'kind': stream['kind'],
                               'scope_type': stream['scope_type'], 'subreddit': stream['subreddit']},
                        values=values, records=boundary['left_window_record_ids']+boundary['right_window_record_ids'],
                        windows=[boundary['left_window_id'],boundary['right_window_id']], evidence=refs,
                        status='candidate', level='derived_comparison', parameters=thaw(config['changes']),
                        limitations=['descriptive_optimizer_boundary_not_cause_or_author_change',
                                     'observed_text_ordered_by_creation_time', 'parameter_defaults_uncalibrated',
                                     'context_controls_incomplete'])
            if context:
                f['related_finding_ids'] = [context['finding_id']]
            findings.append(f)
    return findings, list(evidence.values())
