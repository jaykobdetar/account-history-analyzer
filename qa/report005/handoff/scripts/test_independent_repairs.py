"""Reviewer-authored focused checks; no optimizer substitute or application edits."""
from pathlib import Path
from itertools import product
from random import Random
import hashlib,json
import pytest
from account_history_analyzer.artifact_io import ArtifactLimits,MAX_FILE_BYTES,read_artifact_bytes,load_artifact_json,file_digest,iter_artifact_jsonl
from account_history_analyzer.artifacts import publish_files
from account_history_analyzer.errors import InputError,LimitError
from account_history_analyzer.io import canonical_bytes,canonical_chunks,freeze
from account_history_analyzer.reuse_matching import TokenMatcher,TokenMatch

@pytest.mark.parametrize('chunk_size',[1,2,3,7,64,65536])
def test_streaming_serialization_matches_standard_bytes(chunk_size):
 rng=Random(90210)
 samples=[{'z':-0.0,'a':['x  y','é😀\n\t','<script>',None,True,False,1e-200,1e200]},'x'*200007,{},[]]
 for _ in range(30):
  samples.append({'nested':[{'v':rng.random(),'i':rng.randrange(-10000,10000),'text':''.join(rng.choice('a é😀\\\n\t') for _ in range(20))} for _ in range(5)],'negative_zero':-0.0})
 for value in samples:
  chunks=list(canonical_chunks(freeze(value),chunk_bytes=chunk_size))
  assert all(0<len(c)<=chunk_size for c in chunks)
  assert b''.join(chunks)==canonical_bytes(value)

@pytest.mark.parametrize('reader',[read_artifact_bytes,load_artifact_json,file_digest,iter_artifact_jsonl])
def test_real_oversize_file_refused_before_open(tmp_path,monkeypatch,reader):
 p=tmp_path/'oversize.json'
 with p.open('wb') as f:f.truncate(MAX_FILE_BYTES+1)
 original=Path.open
 def guarded(self,*a,**kw):
  if self==p:raise AssertionError('The oversized file was opened')
  return original(self,*a,**kw)
 monkeypatch.setattr(Path,'open',guarded)
 with pytest.raises(LimitError):
  value=reader(p)
  if reader is iter_artifact_jsonl:list(value)

@pytest.mark.parametrize('reader',[read_artifact_bytes,load_artifact_json,file_digest,iter_artifact_jsonl])
def test_reader_exact_byte_boundary(tmp_path,reader):
 p=tmp_path/'data.json';p.write_bytes(b'{}\n')
 v=reader(p,max_bytes=3)
 if reader is iter_artifact_jsonl:list(v)
 with pytest.raises(LimitError):
  v=reader(p,max_bytes=2)
  if reader is iter_artifact_jsonl:list(v)

@pytest.mark.parametrize('mode',['file','total','count'])
def test_failed_publication_keeps_previous_directory(tmp_path,mode):
 out=tmp_path/'out';out.mkdir();(out/'keep').write_bytes(b'unchanged')
 limits={'file':ArtifactLimits(max_file_bytes=3),'total':ArtifactLimits(max_total_bytes=7),'count':ArtifactLimits(max_files=1)}[mode]
 with pytest.raises(LimitError):
  publish_files({'a.bin':lambda:iter([b'aa',b'bb']),'b.bin':b'1234'},out,overwrite=True,limits=limits)
 assert {p.name:p.read_bytes() for p in out.iterdir()}=={'keep':b'unchanged'}
 assert not list(tmp_path.glob('.ahas-*'))

@pytest.mark.parametrize('bad',[b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}',b'"\\ud800"',b'\xff'])
def test_artifact_reader_still_rejects_invalid_json(tmp_path,bad):
 p=tmp_path/'data.json';p.write_bytes(bad)
 with pytest.raises(InputError):load_artifact_json(p)

def oracle(left,right,minimum):
 # Explicit substring enumeration, not an automaton or suffix-link recurrence.
 occurrences={}
 for li,a in enumerate(left):
  for start in range(len(a)):
   for length in range(minimum,len(a)-start+1):
    key=tuple(a[start:start+length]);occurrences.setdefault(key,(li,start))
 best=None
 for ri,b in enumerate(right):
  for start in range(len(b)):
   for length in range(minimum,len(b)-start+1):
    found=occurrences.get(tuple(b[start:start+length]))
    if found is not None:
     li,ls=found;k=(-length,li,ri,ls,start)
     if best is None or k<best:best=k
 return None if best is None else TokenMatch(-best[0],*best[1:])

def test_reused_matcher_against_3000_new_substring_enumerations():
 rng=Random(2026091402)
 for _ in range(1000):
  left=[[rng.choice('abcde') for _ in range(rng.randrange(19))] for _ in range(rng.randrange(1,5))]
  minimum=rng.randrange(1,7);matcher=TokenMatcher(left,minimum)
  rights=[[[rng.choice('abcde') for _ in range(rng.randrange(19))] for _ in range(rng.randrange(1,5))],left,[list(reversed(a)) for a in reversed(left)]]
  for right in rights:assert matcher.find(right)==oracle(left,right,minimum)
