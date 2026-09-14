"""Explicit default expansion, strict config validation and path-independent identity."""
from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from types import MappingProxyType
from typing import Any
import copy
import math
import tomllib

from .errors import InputError


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def resource_bytes(name: str) -> bytes:
    if name not in {'function_words_en_v1.txt', 'contraction_pairs.json', 'default.toml'}:
        raise InputError(f'Unsupported bundled resource: {name}', code='invalid_resource')
    return files('account_history_analyzer').joinpath('resources', name).read_bytes()


def defaults() -> dict[str, Any]:
    return tomllib.loads(resource_bytes('default.toml').decode('utf-8'))


def _merge(base: dict, supplied: Mapping, prefix: str = '') -> None:
    if not isinstance(supplied, Mapping):
        raise InputError(f'{prefix}: expected table', code='invalid_config')
    for key, value in supplied.items():
        path = f'{prefix}.{key}'.lstrip('.')
        if key not in base:
            raise InputError(f'Unknown config key {path}', code='unknown_config_key')
        original = base[key]
        if isinstance(original, dict):
            _merge(original, value, path)
        else:
            # bool is a subtype of int: exact type checks are intentional.
            accepted = (type(value) is type(original) or
                        type(original) is float and type(value) in (int, float))
            if not accepted:
                raise InputError(f'{path}: incorrect type', code='invalid_config')
            if isinstance(value, list) and (not value or any(type(v) is not type(original[0]) and not (type(original[0]) is float and type(v) in (int, float)) for v in value)):
                raise InputError(f'{path}: invalid list', code='invalid_config')
            base[key] = copy.deepcopy(value)


def _validate(d: dict) -> None:
    fixed = {'schema_version': '1.0.0', 'input.strict': True,
             'text.normalization': 'NFC', 'text.parser_profile': 'commonmark_v1',
             'text.tokenizer': 'lexical_regex_v1', 'text.function_words_resource': 'function_words_en_v1.txt',
             'text.contraction_pairs_resource': 'contraction_pairs.json', 'style.language': 'en',
             'windows.separate_kinds': True, 'changes.method': 'pelt_l2_v1',
             'changes.scale_ddof': 0, 'changes.jump': 1, 'activity.timezone': 'UTC',
             'report.remote_assets': False, 'ai_text_detection.enabled': False,
             'report.formats': ['json', 'markdown', 'html'],
             'ai_text_detection.status_reason': 'not_implemented_in_v1'}
    for path, expected in fixed.items():
        value: Any = d
        for key in path.split('.'):
            value = value[key]
        if value != expected:
            raise InputError(f'{path}: V1 requires {expected!r}', code='unsupported_config')
    def walk(obj: dict, prefix: str = '') -> None:
        for key, value in obj.items():
            path = f'{prefix}.{key}'.lstrip('.')
            if isinstance(value, dict):
                walk(value, path)
            elif type(value) in (int, float):
                if not math.isfinite(value) or value < 0 or (value == 0 and path not in {'changes.scale_ddof', 'changes.same_window_boundary_tolerance', 'reuse.max_candidate_pairs', 'reuse.max_index_postings', 'reuse.max_work_units', 'reuse.max_evidence_tokens', 'reuse.max_evidence_codepoints', 'reuse.near_threshold_numerator', 'reuse.containment_threshold_numerator'}):
                    raise InputError(f'{path}: invalid numeric value', code='invalid_config')
            elif isinstance(value, list) and value and type(value[0]) in (int, float):
                if any(not math.isfinite(v) or v <= 0 for v in value) or len(set(value)) != len(value):
                    raise InputError(f'{path}: positive distinct values required', code='invalid_config')
    walk(d)
    from .artifact_io import ArtifactLimits
    ArtifactLimits.from_config(d)
    if d['changes']['minimum_windows'] < 8:
        raise InputError('changes.minimum_windows must be at least 8 in V1', code='invalid_config')
    if d['style']['ngram_lengths'] != sorted(d['style']['ngram_lengths']) or not set(d['style']['ngram_lengths']) <= {3, 4, 5}:
        raise InputError('style.ngram_lengths must be an ordered subset of 3,4,5', code='invalid_config')
    if len(set(d['style']['views'])) != len(d['style']['views']) or not set(d['style']['views']) <= {'retained_prose', 'function_mask_v1'}:
        raise InputError('Unsupported/repeated style view', code='invalid_config')
    for stem in ('near', 'containment'):
        if d['reuse'][stem+'_threshold_numerator'] > d['reuse'][stem+'_threshold_denominator']:
            raise InputError('Threshold must be in [0,1]', code='invalid_config')
    if d['windows']['single_record_dominance_fraction'] > 1:
        raise InputError('Dominance fraction must be <=1', code='invalid_config')
    if not set(d['report']['formats']) <= {'json', 'markdown', 'html'} or d['report']['excerpts'] not in {'included', 'none'}:
        raise InputError('Unsupported report format/excerpts', code='invalid_config')
    if d['report']['examples_per_side_per_feature'] > 2 or d['report']['maximum_feature_explanations'] > 10:
        raise InputError('Evidence display maxima are 2 per side and 10 features', code='invalid_config')
    if d['windows']['max_community_streams'] > 10 or d['style']['max_all_pairs_windows'] > 100:
        raise InputError('V1 scope limits exceeded', code='invalid_config')


@dataclass(frozen=True)
class AnalysisConfig:
    """Immutable expanded configuration, with an optional validated frozen reference."""
    data: Mapping[str, Any]
    reference: Mapping[str, Any] | None = None
    reference_sha256: str | None = None
    reference_bytes: bytes | None = None

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    @classmethod
    def from_toml(cls, path: str | Path | None = None, *, allow_toy_reference: bool = False) -> AnalysisConfig:
        try:
            supplied = tomllib.loads(Path(path).read_text('utf-8')) if path else {}
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            raise InputError(str(exc), code='invalid_config') from exc
        return cls.from_mapping(supplied, base_dir=Path(path).resolve().parent if path else None,
                                allow_toy_reference=allow_toy_reference)

    @classmethod
    def from_mapping(cls, supplied: Mapping | None = None, *, base_dir: Path | None = None,
                     allow_toy_reference: bool = False) -> AnalysisConfig:
        from .io import _read_bounded, parse_json, sha256_bytes
        from .schemas import validate
        d = defaults()
        validate(supplied or {}, 'config', location='configuration')
        _merge(d, supplied or {})
        if allow_toy_reference:
            d['delta']['allow_toy_reference'] = True
        _validate(d)
        ref = None
        ref_hash = None
        ref_bytes = None
        ref_path = d['delta']['reference_path']
        if ref_path:
            if '://' in ref_path:
                raise InputError('Reference must be a local file', code='invalid_reference')
            p = Path(ref_path)
            if not p.is_absolute():
                if base_dir is None:
                    raise InputError('Relative reference requires explicit base_dir', code='invalid_reference')
                p = base_dir / p
            ref_bytes = _read_bounded(p, 52428800)
            ref = parse_json(ref_bytes, 'delta reference')
            validate(ref, 'delta_reference', location='delta reference')
            if len(ref['vocabulary']) != len(ref['means']) or len(ref['means']) != len(ref['standard_deviations']):
                raise InputError('Reference arrays have different lengths', code='invalid_reference')
            import re
            pattern = re.compile(r"(?u)[^\W\d_]+(?:['’][^\W\d_]+)*|\d+")
            if any(not pattern.fullmatch(w) or w.isdigit() or w != w.casefold().replace('’', "'") for w in ref['vocabulary']):
                raise InputError('Reference vocabulary must contain normalized word tokens', code='invalid_reference')
            if ref['reference_kind'] == 'toy' and not d['delta']['allow_toy_reference']:
                raise InputError('Toy reference requires --allow-toy-reference', code='toy_reference_forbidden')
            ref_hash = sha256_bytes(ref_bytes)
            d['delta']['reference_path'] = str(p.resolve())
        return cls(_freeze(d), _freeze(ref) if ref else None, ref_hash, ref_bytes)

    def analytical(self) -> dict[str, Any]:
        """Export all defaults with resource locations replaced by content identities."""
        from .io import sha256_bytes
        d = _plain(self.data)
        d['delta']['reference_path'] = ({'reference_id': self.reference['reference_id'],
                                       'sha256': self.reference_sha256} if self.reference else None)
        for key in ('function_words_resource', 'contraction_pairs_resource'):
            name = d['text'][key]
            d['text'][key] = {'resource_id': name, 'sha256': sha256_bytes(resource_bytes(name))}
        return d

    def with_overrides(self, overrides: Mapping) -> AnalysisConfig:
        d = _plain(self.data)
        _merge(d, overrides)
        _validate(d)
        if d['delta'] == _plain(self.data['delta']):
            return AnalysisConfig(_freeze(d), self.reference, self.reference_sha256, self.reference_bytes)
        return AnalysisConfig.from_mapping(d)
