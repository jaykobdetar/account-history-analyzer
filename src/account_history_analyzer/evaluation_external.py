"""Strict local external evaluation; labels and grouping never enter analysis.

This adapter evaluates supplier-defined labels, without establishing their
validity. Frozen thresholds bind development data, method and configuration.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
from pathlib import Path
from typing import Any

from .config import AnalysisConfig
from .errors import InputError, LimitError
from .io import _read_bounded, digest, load_snapshot, parse_json, thaw
from .registry import registry_document
from .schemas import validate

GROUP_DIMENSIONS = ('author', 'thread', 'source_document', 'near_duplicate_cluster', 'related_sample')
SELECTOR_DEFAULTS = {'start_utc': None, 'end_utc': None, 'ids': None, 'kind': None, 'subreddit': None}


def _local_path(value: str, base: Path) -> Path:
    if '://' in value or '\x00' in value:
        raise InputError('Evaluation accepts local file paths only', code='invalid_evaluation_path')
    path = Path(value)
    path = path if path.is_absolute() else base / path
    return path.resolve()


def _read_dataset(dataset_path: str | Path, suite: str, config: AnalysisConfig) -> tuple[dict, Path, int]:
    if suite not in {'paired_text', 'account_stream'}:
        raise InputError('External suite must be paired_text or account_stream', code='invalid_evaluation_suite')
    path = _local_path(str(dataset_path), Path.cwd())
    raw = _read_bounded(path, config['input']['max_input_bytes'])
    dataset = parse_json(raw, 'external evaluation dataset')
    validate(dataset, 'evaluation_' + suite, location='external evaluation dataset')
    if dataset['protocol']['analysis_config_sha256'] != digest(config.analytical()):
        raise InputError('Preregistered analysis configuration hash does not match', code='evaluation_config_mismatch')
    return dataset, path.parent, len(raw)


def _unique(items: list[dict], key: str) -> dict[str, dict]:
    result = {}
    for item in items:
        if item[key] in result:
            raise InputError(f'Duplicate {key}: {item[key]}', code='duplicate_evaluation_id')
        result[item[key]] = item
    return result


def _paired_units(dataset: dict) -> tuple[dict[str, dict], dict[str, set[str]]]:
    texts = _unique(dataset['texts'], 'text_id')
    _unique(dataset['pairs'], 'pair_id')
    uses = {split: set() for split in ('development', 'evaluation')}
    for pair in dataset['pairs']:
        if pair['left_text_id'] == pair['right_text_id']:
            raise InputError('A labeled pair must contain two distinct text IDs', code='invalid_evaluation_pair')
        for side in ('left_text_id', 'right_text_id'):
            if pair[side] not in texts:
                raise InputError(f'Unknown text ID: {pair[side]}', code='unknown_evaluation_text')
            uses[pair['split']].add(pair[side])
    return texts, uses


def _group_audit(units: Mapping[str, dict], uses: Mapping[str, set[str]]) -> list[dict]:
    shared = uses['development'] & uses['evaluation']
    if shared:
        raise InputError(f'Samples occur in both splits: {sorted(shared)}', code='evaluation_leakage')
    results = []
    for dimension in GROUP_DIMENSIONS:
        values = {split: set() for split in uses}
        missing = {split: [] for split in uses}
        for split in ('development', 'evaluation'):
            for unit_id in sorted(uses[split]):
                labels = units[unit_id].get('groups', {}).get(dimension, [])
                values[split].update(labels)
                if not labels:
                    missing[split].append(unit_id)
        overlap = values['development'] & values['evaluation']
        if overlap:
            raise InputError(f'Observed {dimension} groups cross development/evaluation: {sorted(overlap)}',
                             code='evaluation_leakage')
        auditable = bool(uses['development'] and uses['evaluation']) and not any(missing.values())
        results.append({'dimension': dimension, 'status': 'audited_disjoint' if auditable else 'not_auditable',
                        'development_group_count': len(values['development']),
                        'evaluation_group_count': len(values['evaluation']),
                        'missing_development_units': missing['development'],
                        'missing_evaluation_units': missing['evaluation'],
                        'reason': None if auditable else 'missing_group_metadata_or_split'})
    return results


class _Sources:
    def __init__(self, base: Path, config: AnalysisConfig, dataset_bytes: int) -> None:
        self.base = base
        self.config = config
        self.bytes = dataset_bytes
        self.paths: set[Path] = set()
        self.snapshots: dict[tuple[Path, Path], Any] = {}
        self.features: dict[str, Any] = {}
        self.canonical_snapshots: set[str] = set()
        self.records = 0

    def snapshot(self, unit: dict) -> Any:
        key = (_local_path(unit['input'], self.base), _local_path(unit['manifest'], self.base))
        if key not in self.snapshots:
            for path in key:
                if path not in self.paths:
                    data = _read_bounded(path, self.config['input']['max_input_bytes'])
                    self.bytes += len(data)
                    if self.bytes > self.config['input']['max_input_bytes']:
                        raise LimitError('External dataset and unique source files exceed max_input_bytes',
                                         code='evaluation_input_limit')
                    self.paths.add(path)
            snapshot = load_snapshot(*key, self.config)
            if snapshot.canonical_sha256 not in self.canonical_snapshots:
                self.records += len(snapshot.records)
                if self.records > self.config['input']['max_unique_records']:
                    raise LimitError('External dataset exceeds max_unique_records across snapshots',
                                     code='evaluation_record_limit')
                self.canonical_snapshots.add(snapshot.canonical_sha256)
            self.snapshots[key] = snapshot
        return self.snapshots[key]

    def text(self, unit: dict) -> tuple[list, dict]:
        from .features import extract_records
        from .windows import select_records
        snapshot = self.snapshot(unit)
        if snapshot.canonical_sha256 not in self.features:
            self.features[snapshot.canonical_sha256] = extract_records(snapshot, self.config)
        selector = {**SELECTOR_DEFAULTS, **unit.get('selector', {})}
        if selector['ids'] is not None:
            selector['ids'] = sorted(selector['ids'])
        selected = select_records(self.features[snapshot.canonical_sha256], selector)
        identity = {'text_id': unit['text_id'], 'snapshot_sha256': snapshot.canonical_sha256,
                    'selector': selector, 'groups': unit.get('groups', {})}
        return selected, identity


def _snapshot_split_audit(identities: Mapping[str, dict], uses: Mapping[str, set[str]]) -> None:
    snapshots = {split: {identities[unit]['snapshot_sha256'] for unit in uses[split]} for split in uses}
    if snapshots['development'] & snapshots['evaluation']:
        raise InputError('The same canonical supplied snapshot occurs in both splits', code='evaluation_leakage')


def _method_sha256() -> str:
    from .pipeline import implementation_identity
    fingerprint, environment, resources = implementation_identity()
    return digest({'registry': registry_document(), 'implementation_fingerprint': fingerprint,
                   'reference_environment': environment, 'resource_sha256': resources})


def _development_identity(dataset: dict, identities: Mapping[str, dict]) -> str:
    pairs = sorted((pair for pair in dataset['pairs'] if pair['split'] == 'development'), key=lambda p: p['pair_id'])
    ids = {pair[side] for pair in pairs for side in ('left_text_id', 'right_text_id')}
    return digest({'label_definition': dataset['label_definition'],
                   'pairs': pairs, 'texts': [identities[key] for key in sorted(ids)]})


def _score_pair(pair: dict, texts: Mapping[str, list], config: AnalysisConfig, method: dict) -> dict:
    from .style import compare_features
    comparison = compare_features(texts[pair['left_text_id']], texts[pair['right_text_id']], config)
    distances = [distance for distance in comparison['distances']
                 if all(distance[key] == method[key] for key in ('method_id', 'view', 'n'))]
    if len(distances) != 1:
        raise InputError('Preregistered distance is unavailable in this configuration', code='invalid_evaluation_method')
    distance = distances[0]
    qualified = comparison['status'] == 'ok' and distance['status'] == 'ok'
    reasons = set(comparison['reason_codes'])
    if distance['reason']:
        reasons.add(distance['reason'])
    return {**pair, 'status': 'ok' if qualified else 'abstained', 'reason_codes': sorted(reasons),
            'score': distance['value'] if qualified else None, 'raw_distance': distance['value'],
            'samples': comparison['samples'], 'distance_status': distance['status']}


def freeze_pair_threshold(dataset_path: str | Path, config: AnalysisConfig | None = None, *,
                          value: float, selection_rule: str, provenance: str) -> dict[str, Any]:
    """Bind a supplied development-selected cutoff without opening held-out text.

    This does not select a threshold automatically or verify a human's claim of
    preregistration. It requires qualified development examples of both labels,
    records their hashes, and reads no evaluation snapshot files or pair scores.
    """
    config = config or AnalysisConfig.from_toml()
    finite = type(value) is int or type(value) is float and math.isfinite(value)
    if not finite or value < 0:
        raise InputError('Threshold must be a finite nonnegative number', code='invalid_evaluation_threshold')
    if any(not isinstance(item, str) or not 1 <= len(item) <= 4096 for item in (selection_rule, provenance)):
        raise InputError('Threshold requires selection rule and provenance', code='invalid_evaluation_threshold')
    dataset, base, size = _read_dataset(dataset_path, 'paired_text', config)
    units, uses = _paired_units(dataset)
    _group_audit(units, uses)
    sources = _Sources(base, config, size)
    texts, identities = {}, {}
    for key in sorted(uses['development']):
        texts[key], identities[key] = sources.text(units[key])
    scores = [_score_pair(pair, texts, config, dataset['protocol']['distance'])
              for pair in sorted(dataset['pairs'], key=lambda p: p['pair_id']) if pair['split'] == 'development']
    if {score['label'] for score in scores if score['status'] == 'ok'} != {'same_author', 'different_author'}:
        raise InputError('Threshold freezing requires qualified development pairs of both labels',
                         code='insufficient_threshold_development')
    return {'value': value, 'positive_label': 'different_author', 'operator': '>=', 'selected_on': 'development',
            'development_pair_ids': [score['pair_id'] for score in scores],
            'development_dataset_sha256': _development_identity(dataset, identities),
            'analysis_config_sha256': digest(config.analytical()), 'method_sha256': _method_sha256(),
            'distance': dataset['protocol']['distance'], 'selection_rule': selection_rule, 'provenance': provenance}


def _paired(dataset: dict, sources: _Sources, config: AnalysisConfig) -> tuple[dict, dict, list[dict]]:
    from .evaluation_metrics import paired_metrics
    units, uses = _paired_units(dataset)
    audit = _group_audit(units, uses)
    texts, identities = {}, {}
    for key in sorted(units):
        texts[key], identities[key] = sources.text(units[key])
    _snapshot_split_audit(identities, uses)
    development_hash = _development_identity(dataset, identities)
    frozen = dataset['protocol']['frozen_threshold']
    if frozen is not None:
        expected = {'development_dataset_sha256': development_hash,
                    'development_pair_ids': sorted(pair['pair_id'] for pair in dataset['pairs'] if pair['split'] == 'development'),
                    'analysis_config_sha256': digest(config.analytical()), 'method_sha256': _method_sha256(),
                    'distance': dataset['protocol']['distance']}
        for key, value in expected.items():
            if frozen[key] != value:
                raise InputError(f'Frozen threshold binding mismatch: {key}', code='frozen_threshold_mismatch')
    partitions = {}
    for split in ('development', 'evaluation'):
        rows = [_score_pair(pair, texts, config, dataset['protocol']['distance'])
                for pair in sorted(dataset['pairs'], key=lambda p: p['pair_id']) if pair['split'] == split]
        if frozen and split == 'development' and {r['label'] for r in rows if r['status'] == 'ok'} != {'same_author', 'different_author'}:
            raise InputError('Frozen threshold development lacks both qualified labels', code='insufficient_threshold_development')
        partitions[split] = {'rows': rows, 'metrics': paired_metrics([r['label'] for r in rows], [r['score'] for r in rows],
                              threshold=frozen['value'] if frozen else None)}
    canonical = {**{k: v for k, v in dataset.items() if k != 'texts'},
                 'texts': [identities[key] for key in sorted(identities)],
                 'pairs': sorted(dataset['pairs'], key=lambda p: p['pair_id'])}
    result = {'partitions': partitions, 'distance': dataset['protocol']['distance'],
              'frozen_threshold': frozen, 'development_dataset_sha256': development_hash,
              'text_count': len(units), 'unreferenced_text_ids': sorted(set(units) - set.union(*uses.values())),
              'exit_code': 0}
    return result, canonical, audit


def _streams(dataset: dict, sources: _Sources, config: AnalysisConfig) -> tuple[dict, dict, list[dict]]:
    from .evaluation_metrics import aggregate_stream_metrics, boundary_metrics
    units = _unique(dataset['streams'], 'stream_id')
    uses = {split: {key for key, unit in units.items() if unit['split'] == split}
            for split in ('development', 'evaluation')}
    audit = _group_audit(units, uses)
    identities, snapshots = {}, {}
    for key, unit in sorted(units.items()):
        snapshots[key] = sources.snapshot(unit)
        scope = unit['scope']
        if scope['scope_type'] == 'pooled' and scope['subreddit'] is not None:
            raise InputError('Pooled scope requires subreddit:null', code='invalid_evaluation_scope')
        if any(boundary >= len(snapshots[key].records) for boundary in unit['truth_boundaries']):
            raise InputError('Truth split must lie between supplied canonical records', code='invalid_evaluation_boundary')
        identities[key] = {k: v for k, v in unit.items() if k not in {'input', 'manifest'}}
        identities[key]['snapshot_sha256'] = snapshots[key].canonical_sha256
    _snapshot_split_audit(identities, uses)
    analyzed = {}
    partitions = {}
    incomplete = False
    for split in ('development', 'evaluation'):
        rows = []
        for key in sorted(uses[split]):
            unit, snapshot = units[key], snapshots[key]
            if snapshot.canonical_sha256 not in analyzed:
                analyzed[snapshot.canonical_sha256] = _stream_analysis(snapshot, config)
            analysis = analyzed[snapshot.canonical_sha256]
            matching = [s for s in analysis['streams'] if all(s[field] == unit['scope'][field]
                        for field in ('scope_type', 'kind', 'subreddit'))]
            change = next((c for c in analysis['changes'] if matching and c['stream_id'] == matching[0]['stream_id']), None)
            reasons = []
            status = 'ok'
            if analysis['exit_code']:
                incomplete = True
                status = 'resource_limit'
                reasons.append('whole_pipeline_incomplete')
            elif change is None:
                status = 'abstained'
                reasons.append('requested_scope_not_selected_or_eligible')
            elif change['status'] not in {'ok', 'no_measurable_variation'}:
                status = 'abstained'
                reasons.extend(change['reason_codes'])
                reasons.append(change['status'])
            candidates = [[b['record_interval'][0] + 1, b['record_interval'][1]] for b in change['boundaries']] if change else []
            metrics = boundary_metrics(candidates, unit['truth_boundaries'], tolerance=dataset['protocol']['boundary_tolerance_records']) if status == 'ok' else None
            rows.append({'stream_id': key, 'split': split, 'status': status, 'reason_codes': sorted(set(reasons)),
                         'snapshot_sha256': snapshot.canonical_sha256, 'analysis_results_sha256': analysis['results_sha256'],
                         'record_count': len(snapshot.records), 'scope': unit['scope'],
                         'declared_coverage': thaw(snapshot.manifest['coverage']),
                         'missing_timestamps': sum(record['created_utc'] is None for record in snapshot.records),
                         'truth_boundaries': sorted(unit['truth_boundaries']), 'candidate_intervals': candidates,
                         'change_status': change['status'] if change else None, 'metrics': metrics})
        executed = [row['metrics'] for row in rows if row['metrics'] is not None]
        partitions[split] = {'rows': rows, 'metrics': aggregate_stream_metrics(executed, abstained_stream_count=len(rows)-len(executed)),
                             'known_unchanged_stream_count': sum(not row['truth_boundaries'] for row in rows),
                             'abstained_unchanged_stream_count': sum(not row['truth_boundaries'] and row['metrics'] is None for row in rows)}
    canonical = {**{key: value for key, value in dataset.items() if key != 'streams'},
                 'streams': [identities[key] for key in sorted(identities)]}
    return {'partitions': partitions, 'boundary_tolerance_records': dataset['protocol']['boundary_tolerance_records'],
            'boundary_coordinate_definition': 'split k is first right-hand record index in the complete canonical snapshot',
            'exit_code': 4 if incomplete else 0}, canonical, audit


def _stream_analysis(snapshot: Any, config: AnalysisConfig) -> dict:
    """Retain only scoring inputs; release full report/artifacts per snapshot."""
    from .pipeline import analyze
    analysis = analyze(snapshot, config)
    style = analysis.results['modules']['style']['payload']
    return {'results_sha256': digest(analysis.results), 'exit_code': analysis.exit_code,
            'streams': thaw(style['streams']), 'changes': thaw(style['changes'])}


def evaluate_external(dataset_path: str | Path, suite: str,
                      config: AnalysisConfig | None = None) -> dict[str, Any]:
    """Evaluate one explicit local dataset deterministically, with abstention.

    No dataset is downloaded and no timestamp, author identity or label is
    invented. Dataset bytes and all distinct source files share configured input
    limits. Expected input/configuration failures raise stable ``InputError``;
    incomplete whole-stream analysis is returned with ``exit_code=4``.
    """
    from .pipeline import implementation_identity
    config = config or AnalysisConfig.from_toml()
    dataset, base, size = _read_dataset(dataset_path, suite, config)
    sources = _Sources(base, config, size)
    payload, canonical, audit = (_paired if suite == 'paired_text' else _streams)(dataset, sources, config)
    fingerprint, environment, resources = implementation_identity()
    return {'schema_version': '1.0.0', 'suite': suite, 'dataset_id': dataset['dataset_id'],
            'status': 'incomplete' if payload['exit_code'] else ('evaluated' if payload['partitions']['evaluation']['rows'] else 'not_evaluated'),
            'dataset_sha256': digest(canonical), 'analysis_config_sha256': digest(config.analytical()),
            'method_sha256': _method_sha256(), 'implementation_fingerprint': fingerprint,
            'reference_environment': environment, 'resource_sha256': resources,
            'label_definition': dataset['label_definition'], 'dataset_provenance': dataset['provenance'],
            'protocol': dataset['protocol'], 'leakage_audit': audit,
            'limitations': ['supplier_labels_and_preregistration_not_independently_verified',
                            'descriptive_metrics_without_independence_confidence_intervals',
                            'distances_are_not_authorship_probabilities',
                            'missing_group_metadata_prevents_complete_leakage_audit',
                            'results_do_not_validate_ai_bot_or_takeover_detection'],
            **payload}
