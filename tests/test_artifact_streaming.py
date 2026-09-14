"""AUD-001: canonical streaming, bounded readers and atomic artifact envelopes."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from hypothesis import given, settings, strategies as st
import pytest

from account_history_analyzer import artifact_io, artifacts
from account_history_analyzer.artifact_io import (
    ArtifactLimits, MAX_FILE_BYTES, MAX_TOTAL_BYTES, MAX_FILES,
    file_digest, iter_artifact_jsonl, load_artifact_json, read_artifact_bytes,
)
from account_history_analyzer.artifacts import publish_files
from account_history_analyzer.errors import InputError, LimitError
from account_history_analyzer.io import canonical_bytes, canonical_chunks, canonical_digest, freeze

TEXT = st.text(alphabet=st.characters(blacklist_categories=('Cs',)), max_size=30)
JSON = st.recursive(st.one_of(st.none(), st.booleans(), st.integers(-10**18, 10**18),
                    st.floats(allow_nan=False, allow_infinity=False), TEXT),
                    lambda children: st.one_of(st.lists(children, max_size=5),
                                               st.dictionaries(TEXT, children, max_size=5)), max_leaves=30)


@given(JSON, st.integers(1, 97))
@settings(max_examples=100)
def test_ART_STREAM_01_canonical_equivalence_nested_unicode_and_immutable_values(value, size):
    expected = canonical_bytes(value)
    for supplied in (value, freeze(value)):
        chunks = list(canonical_chunks(supplied, chunk_bytes=size))
        assert b''.join(chunks) == expected
        assert all(0 < len(chunk) <= size for chunk in chunks)
        assert canonical_digest(supplied) == hashlib.sha256(expected).hexdigest()


@pytest.mark.parametrize('value,expected', [
    ({'z': -0.0, 'a': [True, False, None, 1, 1.0]}, b'{"a":[true,false,null,1,1.0],"z":0.0}\n'),
    ('café😀\n\u2028', '"café😀\\n\u2028"\n'.encode('utf-8')),
    ({'b': '\\"', 'a': '\t'}, b'{"a":"\\t","b":"\\\\\\\""}\n'),
])
def test_ART_STREAM_02_hand_checked_bytes_and_final_lf(value, expected):
    for size in (1, 2, 3, 7, 64):
        assert b''.join(canonical_chunks(value, chunk_bytes=size)) == expected
    assert canonical_bytes(value) == expected


@pytest.mark.parametrize('value,error', [
    (float('nan'), ValueError), (float('inf'), ValueError), (float('-inf'), ValueError),
    ({'ok': [1, float('nan')]}, ValueError), ({1: 'bad key'}, ValueError),
    ({'nested': {None: 1}}, ValueError), (b'bytes', TypeError), ({1, 2}, TypeError),
    (object(), TypeError), ('\ud800', UnicodeEncodeError),
])
def test_ART_STREAM_03_invalid_data_is_not_silently_coerced(value, error):
    with pytest.raises(error):
        list(canonical_chunks(value))
    with pytest.raises(error):
        canonical_bytes(value)


@pytest.mark.parametrize('size', [0, -1, True, 1.5, None])
def test_ART_STREAM_04_invalid_chunk_bound_rejected(size):
    with pytest.raises(ValueError):
        list(canonical_chunks({}, chunk_bytes=size))


@pytest.mark.parametrize('field,ceiling', [('max_file_bytes', MAX_FILE_BYTES),
                                          ('max_total_bytes', MAX_TOTAL_BYTES), ('max_files', MAX_FILES)])
def test_ART_LIMIT_01_configuration_may_tighten_but_not_raise_hard_caps(field, ceiling):
    assert getattr(ArtifactLimits(**{field: ceiling}), field) == ceiling
    assert getattr(ArtifactLimits(**{field: 1}), field) == 1
    for value in (ceiling+1, 0, -1, True, 1.5):
        with pytest.raises(InputError, match='invalid_artifact_limit'):
            ArtifactLimits(**{field: value})


def assert_clean_rollback(parent, out, before):
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before
    assert not list(parent.glob('.ahas-staging-*'))
    assert not list(parent.glob('.ahas-previous-*'))


def test_ART_LIMIT_02_file_exact_limit_succeeds_next_byte_rolls_back(tmp_path):
    out = tmp_path/'out'
    publish_files({'value.bin': lambda: iter([b'ab', b'cdef', b'gh'])}, out,
                  limits=ArtifactLimits(max_file_bytes=8))
    assert (out/'value.bin').read_bytes() == b'abcdefgh'
    before = {'value.bin': b'abcdefgh'}
    with pytest.raises(LimitError, match='artifact_file_byte_limit'):
        publish_files({'value.bin': lambda: iter([b'ab', b'cdef', b'ghi'])}, out, overwrite=True,
                      limits=ArtifactLimits(max_file_bytes=8))
    assert_clean_rollback(tmp_path, out, before)


def test_ART_LIMIT_03_total_exact_limit_and_receipts_are_charged(tmp_path):
    files = {'value.bin': b'12345', 'ingest_receipt.json': b'{}', 'run_receipt.json': b'{}'}
    out = tmp_path/'out'
    publish_files(files, out, limits=ArtifactLimits(max_total_bytes=9))
    assert sum(path.stat().st_size for path in out.iterdir()) == 9
    with pytest.raises(LimitError, match='artifact_total_byte_limit'):
        publish_files({**files, 'value.bin': b'123456'}, out, overwrite=True,
                      limits=ArtifactLimits(max_total_bytes=9))
    assert_clean_rollback(tmp_path, out, files)


def test_ART_LIMIT_04_generated_checksums_and_receipts_count_toward_file_limit(tmp_path):
    files = {'value.bin': b'123', 'ingest_receipt.json': b'{}', 'run_receipt.json': b'{}'}
    out = tmp_path/'out'
    publish_files(files, out, limits=ArtifactLimits(max_files=4), _add_checksums=True)
    assert len(list(out.iterdir())) == 4
    before = {path.name: path.read_bytes() for path in out.iterdir()}
    checks = json.loads(before['checksums.json'])
    assert checks == {'value.bin': hashlib.sha256(b'123').hexdigest()}
    with pytest.raises(LimitError, match='artifact_file_count_limit'):
        publish_files(files, out, overwrite=True, limits=ArtifactLimits(max_files=3), _add_checksums=True)
    assert_clean_rollback(tmp_path, out, before)


def test_ART_LIMIT_05_generated_checksum_bytes_count_toward_total(tmp_path):
    checks = json.dumps({'a': hashlib.sha256(b'x').hexdigest()}, sort_keys=True, separators=(',', ':')).encode()+b'\n'
    size = 1 + len(checks)
    out = tmp_path/'out'
    publish_files({'a': b'x'}, out, limits=ArtifactLimits(max_total_bytes=size), _add_checksums=True)
    assert (out/'checksums.json').read_bytes() == checks
    before = {path.name: path.read_bytes() for path in out.iterdir()}
    with pytest.raises(LimitError, match='artifact_total_byte_limit'):
        publish_files({'a': b'x'}, out, overwrite=True, limits=ArtifactLimits(max_total_bytes=size-1), _add_checksums=True)
    assert_clean_rollback(tmp_path, out, before)


@pytest.mark.parametrize('name', ['resolved_config.json', 'checksums.json'])
def test_ART_LIMIT_06_metadata_limit_matches_publication_bound(tmp_path, monkeypatch, name):
    monkeypatch.setattr(artifacts, 'METADATA_BYTES', 16)
    out = tmp_path/'out'
    good = b'"'+b'a'*13+b'"\n'
    assert len(good) == 16
    publish_files({name: good}, out)
    assert load_artifact_json(out/name, max_bytes=16) == 'a'*13
    with pytest.raises(LimitError, match='artifact_metadata_byte_limit'):
        publish_files({name: good+b' '}, out, overwrite=True)
    assert_clean_rollback(tmp_path, out, {name: good})


def test_ART_LIMIT_07_generated_metadata_obeys_its_own_cap(tmp_path, monkeypatch):
    checksum = json.dumps({'a': hashlib.sha256(b'x').hexdigest()}, sort_keys=True, separators=(',', ':')).encode()+b'\n'
    monkeypatch.setattr(artifacts, 'METADATA_BYTES', len(checksum))
    out = tmp_path/'out'
    publish_files({'a': b'x'}, out, _add_checksums=True)
    before = {'a': b'x', 'checksums.json': checksum}
    monkeypatch.setattr(artifacts, 'METADATA_BYTES', len(checksum)-1)
    with pytest.raises(LimitError, match='artifact_metadata_byte_limit'):
        publish_files({'a': b'x'}, out, overwrite=True, _add_checksums=True)
    assert_clean_rollback(tmp_path, out, before)


@pytest.mark.parametrize('bad_chunk', [b'123456789', 'not bytes', None])
def test_ART_LIMIT_08_midstream_failure_leaves_no_complete_new_output(tmp_path, bad_chunk):
    out = tmp_path/'out'
    def chunks():
        yield b'good'
        yield bad_chunk
    with pytest.raises((LimitError, TypeError)):
        publish_files({'a': b'staged', 'results.json': chunks}, out,
                      limits=ArtifactLimits(max_file_bytes=8), _add_checksums=True)
    assert not out.exists()
    assert not list(tmp_path.glob('.ahas-staging-*'))


def test_ART_LIMIT_09_serialization_failure_rolls_back_existing_directory(tmp_path):
    out = tmp_path/'out'
    publish_files({'old': b'preserved'}, out)
    with pytest.raises(ValueError):
        publish_files({'results.json': lambda: canonical_chunks({'a': 1, 'z': float('nan')}, chunk_bytes=2)},
                      out, overwrite=True, _add_checksums=True)
    assert_clean_rollback(tmp_path, out, {'old': b'preserved'})


@pytest.mark.parametrize('reader', [read_artifact_bytes, file_digest])
def test_ART_READ_01_byte_limit_exact_and_next_byte(tmp_path, reader):
    path = tmp_path/'data'
    path.write_bytes(b'12345678')
    expected = b'12345678' if reader is read_artifact_bytes else hashlib.sha256(b'12345678').hexdigest()
    assert reader(path, max_bytes=8) == expected
    path.write_bytes(b'123456789')
    with pytest.raises(LimitError, match='artifact_file_byte_limit'):
        reader(path, max_bytes=8)


def test_ART_READ_02_json_and_jsonl_retain_strict_boundaries(tmp_path):
    path = tmp_path/'data.jsonl'
    raw = '{"text":"café\u2028second"}\n{"other":true}\n'.encode()
    path.write_bytes(raw)
    assert list(iter_artifact_jsonl(path, max_bytes=len(raw))) == [{'text': 'café\u2028second'}, {'other': True}]
    with pytest.raises(LimitError):
        list(iter_artifact_jsonl(path, max_bytes=len(raw)-1))
    one = tmp_path/'one.json'
    one.write_bytes(b'{"one":1}\n')
    assert load_artifact_json(one, max_bytes=10) == {'one': 1}
    with pytest.raises(LimitError):
        load_artifact_json(one, max_bytes=9)


@pytest.mark.parametrize('raw', [b'\n', b'NaN\n', b'{"a":1,"a":2}\n', b'{"unfinished":\n', b'"\xff"\n'])
def test_ART_READ_03_jsonl_rejects_invalid_records(tmp_path, raw):
    path = tmp_path/'bad.jsonl'
    path.write_bytes(raw)
    with pytest.raises(InputError):
        list(iter_artifact_jsonl(path))


@pytest.mark.parametrize('reader', [read_artifact_bytes, load_artifact_json, iter_artifact_jsonl, file_digest])
def test_ART_READ_04_sparse_hard_cap_plus_one_refused_before_open(tmp_path, monkeypatch, reader):
    path = tmp_path/'oversized'
    with path.open('wb') as handle:
        handle.truncate(MAX_FILE_BYTES+1)
    original = Path.open
    def guarded_open(candidate, *args, **kwargs):
        if candidate == path:
            pytest.fail('Oversized artifact was opened despite stat-visible hard-cap violation')
        return original(candidate, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guarded_open)
    with pytest.raises(LimitError, match='artifact_file_byte_limit'):
        value = reader(path)
        if reader is iter_artifact_jsonl:
            list(value)


def test_ART_READ_05_hash_reductions_use_bounded_chunks(tmp_path, monkeypatch):
    path = tmp_path/'large'
    data = b'abc'*(artifact_io.CHUNK_BYTES+7)
    path.write_bytes(data)
    sizes = []
    original = Path.open
    class Recorded(io.BytesIO):
        def read(self, size=-1):
            sizes.append(size)
            return super().read(size)
    def recorded_open(candidate, *args, **kwargs):
        return Recorded(data) if candidate == path else original(candidate, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', recorded_open)
    assert file_digest(path) == hashlib.sha256(data).hexdigest()
    assert len(sizes) > 2
    assert all(0 < size <= artifact_io.CHUNK_BYTES for size in sizes)
