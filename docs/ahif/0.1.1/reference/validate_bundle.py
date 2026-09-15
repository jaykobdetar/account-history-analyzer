#!/usr/bin/env python3
"""Offline draft-format checker. Does not collect, convert, merge or analyze histories.

Requires jsonschema and referencing. All schema resolution is local.
This is a design reference for small fixtures, not a production ingestion service.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource
from ipaddress import IPv6Address

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.1.1'
MAX_FILE = 64 * 1024 * 1024
MAX_BUNDLE = 256 * 1024 * 1024
MAX_ROWS = 100000
MAX_DEPTH = 64
MAX_MANIFEST = 4 * 1024 * 1024
MAX_LINE = 16 * 1024 * 1024

class Invalid(ValueError):
    pass

def fail(msg: str) -> None:
    raise Invalid(msg)

def check_values(value: Any, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        fail('JSON nesting limit exceeded')
    if isinstance(value, str):
        if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            fail('Lone surrogate in a string')
    elif isinstance(value, dict):
        for k,v in value.items():
            if not isinstance(k,str) or not k or any(not 0x20 <= ord(c) <= 0x7e for c in k):
                fail('Object property names must be nonempty printable ASCII')
            check_values(v,depth+1)
    elif isinstance(value, list):
        for v in value: check_values(v,depth+1)
    elif value is None or isinstance(value,bool):
        pass
    elif type(value) is int:
        if abs(value)>9007199254740991: fail('Integer outside exact interoperable range; use string')
    else:
        fail('Floating-point JSON numbers are outside this draft profile; use a decimal string')

def pairs_hook(pairs):
    result={}
    for k,v in pairs:
        if k in result: fail('Duplicate JSON object key')
        result[k]=v
    return result

def strict_loads(raw: bytes | str) -> Any:
    try:
        if isinstance(raw,bytes):
            if raw.startswith(b'\xef\xbb\xbf'): fail('UTF-8 BOM not permitted')
            raw=raw.decode('utf-8',errors='strict')
        value=json.loads(raw,object_pairs_hook=pairs_hook,
            parse_float=lambda _: fail('Floating-point JSON token not permitted'),
            parse_constant=lambda _: fail('Nonfinite JSON token not permitted'))
    except (RecursionError, UnicodeError, json.JSONDecodeError) as e:
        raise Invalid('Invalid JSON or excessive nesting') from e
    check_values(value)
    return value

def canonical(value: Any) -> bytes:
    """JCS-compatible on AHIF's restricted integer/ASCII-key JSON domain.

    This is deliberately NOT a general RFC 8785 implementation.
    """
    check_values(value)
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')

def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()

def bound_id(kind: str, value: dict) -> str:
    if kind not in ('source','record','account'): fail('Unsupported hash domain')
    field='source_id' if kind=='source' else 'observation_id'
    body={k:v for k,v in value.items() if k!=field}
    prefix=f'AHIF:{kind}:{VERSION}\n'.encode('ascii')
    return 'sha256:'+hashlib.sha256(prefix+canonical(body)).hexdigest()

def key_string(key: dict) -> str:
    return canonical(key).decode('utf-8')

def utc_ns(value: str) -> int:
    m=re.fullmatch(r'([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-5][0-9])(?:\.([0-9]{1,9}))?Z',value)
    if not m: fail('Invalid UTC timestamp syntax')
    d=datetime.strptime(m[1],'%Y-%m-%dT%H:%M:%S')
    epoch=datetime(1970,1,1)
    delta=d-epoch
    return (delta.days*86400+delta.seconds)*1000000000+int((m[2] or '').ljust(9,'0') or '0')

def check_time(value: dict) -> None:
        status=value['status']
        if status=='known':
            utc_ns(value['value'])
            fraction=value['value'].split('.')[1][:-1] if '.' in value['value'] else ''
            cap={'second':0,'millisecond':3,'microsecond':6,'nanosecond':9}[value['precision']]
            if len(fraction)>cap: fail('Timestamp has digits finer than declared precision')
        elif status=='date_only':
            date.fromisoformat(value['value'])
            off=value['utc_offset']
            if off and off!='Z' and int(off[1:3])==14 and off[4:]!='00': fail('UTC offset beyond 14 hours')
            if off=='-00:00': fail('Unknown UTC offset must be null, not -00:00')
        elif status=='interval':
            a,b=utc_ns(value['start']),utc_ns(value['end'])
            if b<a or (b==a and value['bounds']=='closed_open'): fail('Invalid time interval')

def declared_times(kind: str, value: dict):
    """Walk only typed time fields. Extension data is opaque."""
    if kind=='manifest':
        for source in value['sources']:
            yield source['acquired_at']; yield source['content_as_of']
        for cov in value['coverage']:
            yield cov['start']; yield cov['end']
            for gap in cov['known_gaps']:
                yield gap['start']; yield gap['end']
            for metric in cov['reported_totals']: yield metric['as_of']
    else:
        for name in ('observed_at','created_at','updated_at'):
            if name in value: yield value[name]
        for metric in value.get('metrics',[]): yield metric['as_of']

def declared_keys(kind: str, value: dict):
    if kind=='manifest':
        for cov in value['coverage']:
            if cov['account_key']: yield cov['account_key']
            yield from cov.get('context_keys') or []
    else:
        yield value['record_key'] if kind=='record' else value['account_key']
        if kind=='record':
            if value['actor']: yield value['actor']
            for ctx in value.get('contexts',[]): yield ctx['key']
            for rel in value.get('relations',[]):
                if rel['target_key']: yield rel['target_key']
        parts=value['content']['parts'] if kind=='record' else value.get('profile_parts',[])
        for part in parts:
            if part['attribution']['account_key']: yield part['attribution']['account_key']

def absolute_uri(value: str) -> bool:
    """RFC 3986 ASCII absolute URI syntax; no lookup or normalization.

    Check components explicitly so optional jsonschema format packages cannot
    silently disable this contract. IRI strings belong in inert URL fields.
    """
    if not re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', value): return False
    atom=r"(?:[A-Za-z0-9._~!$&'()*+,;=-]|%[0-9A-Fa-f]{2})"
    try:
        if any(ord(c)<=32 or ord(c)>=127 for c in value): return False
        rest=value.split(':',1)[1]
        rest,_,fragment=rest.partition('#')
        rest,_,query=rest.partition('?')
        authority=''
        if rest.startswith('//'):
            authority,sep,path=rest[2:].partition('/')
            path=('/'+path) if sep else ''
        else: path=rest
        if not re.fullmatch(rf'(?:{atom}|[:@/])*',path): return False
        if not re.fullmatch(rf'(?:{atom}|[:@/?])*',query): return False
        if not re.fullmatch(rf'(?:{atom}|[:@/?])*',fragment): return False
        if '@' in authority:
            user,authority=authority.split('@',1)
            if not re.fullmatch(rf'(?:{atom}|:)*',user): return False
        if authority.startswith('['):
            close=authority.index(']'); host=authority[1:close]; tail=authority[close+1:]
            if host[:1].lower()=='v':
                if not re.fullmatch(r"[vV][0-9A-Fa-f]+\.[A-Za-z0-9._~!$&'()*+,;=:-]+",host): return False
            else:
                if '%' in host: return False
                IPv6Address(host)
            return not tail or re.fullmatch(r':[0-9]*',tail) is not None
        return re.fullmatch(rf'{atom}*(?::[0-9]*)?',authority) is not None
    except ValueError:
        return False

def deny_remote(uri):
    raise NoSuchResource(ref=uri)

def validators():
    defs=strict_loads((ROOT/'schemas/ahif.schema.json').read_bytes())
    registry=Registry(retrieve=deny_remote).with_resource(defs['$id'],Resource.from_contents(defs))
    result={}
    for name in ('manifest','record','account'):
        schema=strict_loads((ROOT/f'schemas/{name}.schema.json').read_bytes())
        Draft202012Validator.check_schema(schema)
        # All declared core URI/date/time values are explicitly checked below.
        # Optional jsonschema format packages must not change these results.
        result[name]=Draft202012Validator(schema,registry=registry,format_checker=FormatChecker(formats=[]))
    Draft202012Validator.check_schema(defs)
    return result

VALIDATORS=None

def structural(kind:str,value:dict) -> None:
    global VALIDATORS
    if VALIDATORS is None: VALIDATORS=validators()
    check_values(value)
    errors=list(VALIDATORS[kind].iter_errors(value))
    if errors:
        error=sorted(errors,key=lambda e: '/'.join(map(str,e.absolute_path)))[0]
        fail('Schema error '+kind+' at /'+'/'.join(map(str,error.absolute_path))+': '+error.validator)
    for timestamp in declared_times(kind,value): check_time(timestamp)
    for key in declared_keys(kind,value):
        if not absolute_uri(key['namespace']): fail('Invalid absolute namespace URI')
        if key['id_type']=='uri' and not absolute_uri(key['id']): fail('Invalid identity URI')

def safe_path(root:Path,name:str)->Path:
    if not name or '\\' in name or ':' in name or any(ord(c)<32 or ord(c)==127 for c in name): fail('Unsafe bundle path')
    p=PurePosixPath(name)
    if p.is_absolute() or any(x in ('','.','..') for x in name.split('/')): fail('Unsafe bundle path')
    full=root.joinpath(*p.parts)
    # Resolve only after testing every component; never follow an included symlink.
    for part in [full,*list(full.parents)]:
        if part==root.parent: break
        if part.is_symlink(): fail('Symlink in bundle path')
    if not full.is_file(): fail('Missing bundle member')
    if root not in full.resolve().parents: fail('Bundle traversal')
    return full

def local_key(key, sources, owner=None):
    if key is None or key['id_type']!='source_local': return
    source, sep, locator=key['id'].partition('#')
    if not sep or not locator or source not in sources:
        fail('source_local identity requires a declared source_id plus a nonempty locator')
    if owner is not None and source!=owner:
        fail('source_local subject identity must belong to observation source_id')

def locators(row, parts):
    yield row['provenance']['locator']
    for transform in row['provenance']['transformations']:
        if transform.get('input_locator'): yield transform['input_locator']
    for part in parts:
        if part.get('locator'): yield part['locator']

def row_checks(kind:str,row:dict,sources:dict)->list[str]:
    structural(kind,row)
    if row['source_id'] not in sources: fail('Unknown source_id')
    if bound_id(kind,row)!=row['observation_id']: fail('Observation digest mismatch')
    warnings=[]
    key=row['record_key'] if kind=='record' else row['account_key']
    for supplied_key in declared_keys(kind,row): local_key(supplied_key,sources)
    local_key(key,sources,row['source_id'])
    if kind=='record': local_key(row['actor'],sources,row['source_id'])
    parts=row['content']['parts'] if kind=='record' else row.get('profile_parts',[])
    if len({p['part_id'] for p in parts})!=len(parts): fail('Repeated content part ID')
    hashes={a['sha256'] for a in sources[row['source_id']]['artifacts'] if a['sha256']}
    for locator in locators(row,parts):
        if locator.get('artifact_sha256') and locator['artifact_sha256'] not in hashes:
            fail('Locator artifact hash not declared by observation source')
    if kind=='account': return warnings
    if row['observed_at']['status']=='known' and row['created_at']['status']=='known':
        if utc_ns(row['created_at']['value'])>utc_ns(row['observed_at']['value']):
            warnings.append('source_created_time_after_observed_time')
    if row['updated_at']['status']!='unknown' and row['lifecycle']['edit_state']!='edited':
        fail('Known edit time requires edited state')
    if row['updated_at']['status']=='known':
        updated=utc_ns(row['updated_at']['value'])
        if row['created_at']['status']=='known' and updated<utc_ns(row['created_at']['value']):
            warnings.append('source_updated_time_before_created_time')
        if row['observed_at']['status']=='known' and updated>utc_ns(row['observed_at']['value']):
            warnings.append('source_updated_time_after_observed_time')
    content=row['content']; parts=content['parts']; ids=[p['part_id'] for p in parts]
    if len(ids)!=len(set(ids)): fail('Repeated content part ID')
    for part in parts:
        relation=part['attribution']['relation']
        if relation=='record_actor' and row['actor'] is None: fail('Actor attribution without an actor identity')
        if row['kind']=='repost' and relation=='record_actor' and part['role'] in ('body','title') and part['text']:
            fail('A pure repost cannot contain actor-attributed commentary; use quote_post or other')
    for relation in row.get('relations',[]):
        if relation['type'] in ('reply_to','quotes','reposts','crossposts') and relation['target_type']!='record':
            fail('Relationship requires record target')
        if relation['target_key']==row['record_key'] and relation['type']=='reply_to':
            warnings.append('source_self_reply_cycle')
    linkids=[x['link_id'] for x in row.get('links',[])]
    if len(linkids)!=len(set(linkids)): fail('Repeated link ID within observation')
    lookup={p['part_id']:p for p in parts}
    for link in row.get('links',[]):
        span=link.get('span')
        if span:
            if span['part_id'] not in lookup: fail('Unknown link span part')
            if not 0<=span['start']<span['end']<=len(lookup[span['part_id']]['text']):
                fail('Link span outside exact part text')
    if content['availability']=='present' and not any(p['text'] for p in parts):
        fail('Present content must contain at least one character; use empty')
    if content['availability']=='redacted' and parts and content['completeness']!='partial':
        fail('Retained redacted text must be explicitly partial')
    return warnings

def validate_bundle(root:Path, *, require_canonical=False)->dict:
    root=root.absolute()
    manifest_path=safe_path(root,'manifest.json')
    if manifest_path.stat().st_size>MAX_MANIFEST: fail('Manifest size limit exceeded')
    manifest_bytes=manifest_path.read_bytes()
    manifest=strict_loads(manifest_bytes);structural('manifest',manifest)
    canonical_ok=manifest_bytes==canonical(manifest)+b'\n'
    canonical_ok &= manifest['sources']==sorted(manifest['sources'],key=lambda x:x['source_id'])
    canonical_ok &= manifest['coverage']==sorted(manifest['coverage'],key=canonical)
    canonical_ok &= manifest['files']==sorted(manifest['files'],key=lambda x:x['path'])
    sources={}
    for source in manifest['sources']:
        sid=source['source_id']
        if sid in sources: fail('Duplicate source descriptor')
        if bound_id('source',source)!=sid: fail('Source descriptor digest mismatch')
        sources[sid]=source
    if not sources: fail('At least one source descriptor is required')
    for coverage in manifest['coverage']:
        if coverage['source_id'] not in sources:fail('Unknown coverage source')
        local_key(coverage['account_key'],sources,coverage['source_id'])
        for key in coverage.get('context_keys') or []: local_key(key,sources)
    if {c['source_id'] for c in manifest['coverage']}!=set(sources):
        fail('Every source requires an explicit coverage declaration; unknown is valid')
    paths=[f['path'] for f in manifest['files']]
    if len(paths)!=len(set(paths)):fail('Repeated manifest file path')
    if 'manifest.json' in paths:fail('Manifest cannot list itself')
    if not any(f['role']=='records' for f in manifest['files']):fail('At least one records file is required')
    actual=set()
    for member in root.rglob('*'):
        if member.is_symlink(): fail('Symlink in bundle inventory')
        if member.is_dir(): continue
        if not member.is_file(): fail('Nonregular bundle member')
        actual.add(member.relative_to(root).as_posix())
    if actual!=set(paths)|{'manifest.json'}: fail('Bundle inventory differs from manifest')
    total=manifest_path.stat().st_size
    all_ids=set(); records=[]; account_rows=[]; warnings=Counter(); file_results=[]
    for cov in manifest['coverage']:
        for interval in [cov,*cov['known_gaps']]:
            if interval['start']['status']==interval['end']['status']=='known':
                if utc_ns(interval['start']['value'])>utc_ns(interval['end']['value']):
                    warnings['source_coverage_start_after_end']+=1
    for f in manifest['files']:
        path=safe_path(root,f['path']);size=path.stat().st_size
        if size>MAX_FILE:fail('Reference-checker file limit exceeded')
        total+=size
        if total>MAX_BUNDLE:fail('Reference-checker bundle limit exceeded')
        h=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''): h.update(chunk)
        if size!=f['byte_length'] or h.hexdigest()!=f['sha256']:fail('Manifest size or checksum mismatch')
        count=0
        if f['role'] in ('records','accounts'):
            kind='record' if f['role']=='records' else 'account'
            last_id=''
            with path.open('rb') as stream:
                for raw in stream:
                    if not raw.strip():fail('Blank JSONL line')
                    if len(raw)>MAX_LINE:fail('Reference-checker line limit exceeded')
                    row=strict_loads(raw);warnings.update(row_checks(kind,row,sources))
                    canonical_ok &= raw==canonical(row)+b'\n' and row['observation_id']>last_id
                    last_id=row['observation_id']
                    if row['observation_id'] in all_ids:fail('Duplicate observation within snapshot')
                    all_ids.add(row['observation_id'])
                    (records if kind=='record' else account_rows).append(row)
                    count+=1
                    if len(all_ids)>MAX_ROWS:fail('Reference-checker row limit exceeded')
            if count!=f['row_count']:fail('Incorrect JSONL row_count')
        elif f['row_count'] is not None:fail('Raw artifact row_count must be null')
        file_results.append({'path':f['path'],'role':f['role'],'rows':count if f['role']!='raw' else None})
    bypath={f['path']:f for f in manifest['files']}
    included=set()
    for source in sources.values():
        for artifact in source['artifacts']:
            path=artifact['included_path']
            if path:
                included.add(path)
                if path not in bypath or bypath[path]['role']!='raw': fail('Included raw artifact not in manifest')
                f=bypath[path]
                if artifact['sha256']!=f['sha256'] or artifact['byte_length']!=f['byte_length']:
                    fail('Source artifact descriptor mismatch')
    if included!={f['path'] for f in manifest['files'] if f['role']=='raw'}:
        fail('Raw file lacks a source artifact descriptor')
    if require_canonical and not canonical_ok: fail('Noncanonical export')
    groups=Counter(key_string(r['record_key']) for r in records)
    # Multiple observations are legal. The checker deliberately chooses none.
    repeated=sum(n>1 for n in groups.values())
    source_local=sum(r['record_key']['id_type']=='source_local' for r in records)
    return {'status':'passed','format_version':VERSION,'record_observations':len(records),
      'distinct_record_keys':len(groups),'account_observations':len(account_rows),
      'record_keys_with_multiple_observations':repeated,'source_local_record_observations':source_local,
      'projection_status':'not_performed','authenticity_status':'not_established',
      'canonical_export':bool(canonical_ok),'completeness_status':'not_established',
      'count_semantics':'supplied keys only; not verified posting-event totals',
      'warnings':dict(sorted(warnings.items())),'files':file_results}

def main()->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('bundle',type=Path)
    p.add_argument('--canonical',action='store_true',help='Require canonical bytes and export ordering')
    args=p.parse_args()
    try: result=validate_bundle(args.bundle,require_canonical=args.canonical)
    except (Invalid,UnicodeError,OSError,ValueError) as e:
        print(json.dumps({'status':'failed','reason':str(e)}));return 2
    print(json.dumps(result,indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
