"""Pure stage orchestration; no CLI, fetching, model calls or evaluator labels."""
from __future__ import annotations
from collections import Counter
from importlib import metadata
from importlib.resources import files
from pathlib import Path
from typing import Any
import platform
import os
import resource
import time

from . import __version__
from .artifacts import AnalysisResult, jsonl_bytes
from .config import AnalysisConfig
from .io import Snapshot, canonical_bytes, digest, freeze, sha256_bytes, thaw
from .registry import registry_document


def module(payload: dict, status: str = 'ok', reasons: list[str] | None = None) -> dict:
    return {'status': status, 'reason_codes': sorted(set(reasons or [])), 'payload': payload}


def implementation_identity() -> tuple[str, str, dict[str, str]]:
    root = Path(__file__).parent
    source = {str(p.relative_to(root)): sha256_bytes(p.read_bytes()) for p in sorted(root.rglob('*'))
              if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py', '.json', '.toml', '.txt'}}
    env = ';'.join(['CPython-'+platform.python_version(), platform.system(), platform.machine()] +
                   [f'{name}={metadata.version(name)}' for name in ('numpy', 'scipy', 'ruptures', 'markdown-it-py', 'jsonschema')])
    resources = {p.name: sha256_bytes(p.read_bytes()) for p in sorted((root/'resources').iterdir()) if p.is_file()}
    resources['method_registry'] = digest(registry_document())
    resources['report_templates'] = sha256_bytes((root/'reporting.py').read_bytes())
    return digest(source), env, resources


def analyze(snapshot: Snapshot, config: AnalysisConfig | None = None, *, selection: dict | None = None) -> AnalysisResult:
    """Analyze immutable supplied records. Insufficient data is a normal module state."""
    from .features import extract_records, pooled
    from .activity import analyze_activity
    from .links import analyze_links
    from .interactions import analyze_interactions
    from .reuse import analyze_reuse
    from .findings import reuse_findings, comparison_findings, change_findings, validate_references
    from .comparisons import analyze_comparisons
    from .schemas import validate
    started = time.perf_counter()
    config = config or AnalysisConfig.from_toml()
    features = extract_records(snapshot, config)
    counts = Counter(r['status'] for r in snapshot.records)
    languages = Counter(r['language'] for r in features)
    eligible = [r for r in features if r['usable'] and r['created_utc'] is not None and r['language'] == 'en'
                and (r['counts']['retained_words'] or 0) >= config['style']['minimum_record_words']]
    coverage = {'unique_records': len(snapshot.records),
                'status_counts': {k: counts[k] for k in ('present', 'deleted', 'removed', 'unavailable')},
                'missing_timestamps': sum(r['created_utc'] is None for r in snapshot.records),
                'usable_body_records': sum(r['usable'] for r in features),
                'eligible_style_records': len(eligible), 'declared_coverage': thaw(snapshot.manifest['coverage']),
                'warnings': thaw(snapshot.warnings),
                'languages': [{'language': lang, 'records': n} for lang, n in sorted(languages.items())],
                'kinds': {k: sum(r['kind'] == k for r in snapshot.records) for k in ('comment', 'submission')}}
    body = pooled(features, config)
    titles = pooled([r['title'] for r in features if r.get('title') is not None], config)
    activity = analyze_activity(snapshot, config)
    mods = {name: module({}, 'not_run', ['milestone_not_implemented']) for name in ('reuse', 'style', 'links', 'interactions')}
    mods.update(coverage=module(coverage, 'ok' if features else 'insufficient_data', [] if features else ['empty_snapshot']),
                text=module({'body': body, 'titles': titles}, 'ok' if any(r['usable'] for r in features) else 'insufficient_data',
                            [] if any(r['usable'] for r in features) else ['no_usable_text']),
                activity=module(activity, 'ok' if activity['event_count'] else 'insufficient_data',
                                [] if activity['event_count'] else ['no_supplied_timestamps']),
                ai_text_detection=module({'capability': 'not_implemented_in_v1'}, 'not_run', ['not_implemented_in_v1']))
    reuse = analyze_reuse(snapshot, features, config)
    mods['reuse'] = module(reuse, reuse['near_status'], [] if reuse['budget_complete'] else ['near_reuse_resource_limit', reuse['resource_limit_reason']])
    if reuse['budget_complete'] and not reuse['nonempty_shingle_records'] and not reuse['exact_groups']:
        mods['reuse']['status'] = 'insufficient_data'
        mods['reuse']['reason_codes'] = ['no_comparable_reuse_text']
    findings, evidence = reuse_findings(reuse, features, snapshot, config)
    style, windows = analyze_comparisons(features, config, selection)
    from .sensitivity import analyze_temporal
    from .style import compare_features
    temporal = analyze_temporal(features, style, windows, reuse, config)
    style.update(changes=temporal['changes'], sensitivity=temporal['sensitivity'])
    windows = list({w['window_id']: w for w in windows + temporal['extra_windows']}.values())
    links = analyze_links(snapshot, features, windows, config)
    interactions = analyze_interactions(snapshot, config)
    for name, payload in (('links', links), ('interactions', interactions)):
        mods[name] = module(payload, 'ok' if features else 'insufficient_data',
                            [] if features else ['empty_snapshot'])
    by_window = {w['window_id']: w for w in windows}
    by_feature = {r['id']: r for r in features}
    compared_pairs = {(c['left_window_id'], c['right_window_id']) for c in style['comparisons']}
    reruns = [r for setting in temporal['sensitivity']['construction_settings'] for r in setting['results']]
    for rerun in reruns:
        for boundary in rerun['boundaries']:
            pair = (boundary['left_window_id'], boundary['right_window_id'])
            if pair in compared_pairs:
                continue
            left, right = [by_window[wid] for wid in pair]
            comp = compare_features([by_feature[i] for i in left['record_ids']], [by_feature[i] for i in right['record_ids']], config)
            comp.update(left_window_id=pair[0], right_window_id=pair[1])
            comp['comparison_id'] = 'cmp-'+digest(comp)[:24]
            style['comparisons'].append(comp)
            compared_pairs.add(pair)
    qualified_comparisons = sum(c['status'] == 'ok' for c in style['comparisons'])
    mods['style'] = module(style, 'ok' if qualified_comparisons else 'insufficient_data',
                           [] if qualified_comparisons else ['insufficient_comparable_text'])
    cf, ce = comparison_findings(style, features, windows, config)
    findings.extend(cf)
    bf, be = change_findings(style['changes'], style, features, windows, config, cf)
    findings.extend(bf)
    evidence = list({e['evidence_id']: e for e in evidence + ce + be}.values())
    validate_references(findings, evidence, features, windows, snapshot)
    fp, env, resources = implementation_identity()
    if config.reference_sha256:
        resources['delta_reference'] = config.reference_sha256
    resolved = config.analytical()
    if style['manual_selection'] is not None:
        resolved['manual_selection'] = style['manual_selection']
    artifacts = {'records_features.jsonl': jsonl_bytes(features), 'windows.jsonl': jsonl_bytes(windows),
                 'evidence.jsonl': jsonl_bytes(evidence), 'resolved_config.json': canonical_bytes(resolved),
                 'method_registry.json': canonical_bytes(registry_document())}
    if config.reference_bytes is not None:
        artifacts['delta_reference.json'] = config.reference_bytes
    result = {'schema_version': '1.0.0',
              'analysis': {'suite_version': __version__, 'implementation_fingerprint': fp,
                           'reference_environment': env, 'config_sha256': digest(resolved), 'resource_sha256': resources},
              'snapshot': {'snapshot_id': snapshot.manifest['snapshot_id'], 'account_id': snapshot.manifest['account_id'],
                           'canonical_sha256': snapshot.canonical_sha256, 'source_category': snapshot.manifest['source_category']},
              'modules': mods, 'findings': findings,
              'limitations': ['supplier_declared_coverage', 'no_causal_or_authorship_inference', 'real_world_validation_not_established',
                              'observed_text_ordered_by_creation_time', 'parameter_defaults_uncalibrated'],
              'artifacts': {name: {'relative_path': name, 'sha256': sha256_bytes(data)} for name, data in sorted(artifacts.items())}}
    if config.reference is not None and config.reference['reference_kind'] == 'toy':
        result['limitations'].append('toy_reference')
    validate(result, 'results', location='analysis result')
    receipt = {'runtime_seconds': time.perf_counter()-started, 'peak_process_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               'python': platform.python_version(), 'platform': platform.platform(), 'processor': platform.processor(),
               'network_isolation': os.environ.get('AHAS_NETWORK_ISOLATION', 'not_asserted'),
               'original_config': thaw(config.data), 'manual_selection': style['manual_selection'], 'render_excerpts': config['report']['excerpts'],
               'numerical_environment': env}
    return AnalysisResult(freeze(result), freeze(artifacts), snapshot.receipt, freeze(receipt),
                          4 if any(m['status'] == 'resource_limit' for m in mods.values()) else 0)
