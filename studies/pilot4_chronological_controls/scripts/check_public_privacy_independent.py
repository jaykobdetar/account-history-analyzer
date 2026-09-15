"""Bounded lexical publication check; emits no private values or source excerpts.

Checks source identity tokens from audit metadata and 15-word phrases from the
new candidate pool only. Historical source prose is not read. Negative results
are bounded checks, not an assertion of privacy against every possible attack.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import resource
import signal


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def words(text):
    return re.findall(r'[a-z0-9]+',text.casefold())


def phrase_hashes(text):
    parts=words(text)
    return {hashlib.sha256(' '.join(parts[i:i+15]).encode()).digest()
            for i in range(max(0,len(parts)-14))}


def strings(value):
    if isinstance(value,str):yield value
    elif isinstance(value,list):
        for row in value:yield from strings(row)
    elif isinstance(value,dict):
        for key,row in value.items():
            yield key
            yield from strings(row)


def review(public_root,pool,audit,flags):
    files=sorted(p for p in public_root.rglob('*') if p.is_file()
                 and '__pycache__' not in p.parts and p.suffix!='.pyc')
    if len(files)>1000 or sum(p.stat().st_size for p in files)>20*1024**2:
        raise ValueError('public_scan_limit_exceeded')
    inventory=[{'path':str(p.relative_to(public_root)),'bytes':p.stat().st_size,
                'sha256':sha(p)} for p in files]
    identities={};provenance=json.loads(audit.read_bytes())['record_provenance']
    for row in provenance.values():
        for field in ('account_key','source_record_id','thread_id'):
            value=row.get(field)
            if isinstance(value,str) and value:
                identities.setdefault(value.casefold(),set()).add(field)
    for row in json.loads(flags.read_bytes())['accounts']:
        identities.setdefault(row['account_key'].casefold(),set()).add('account_key')
    phrases=set();pool_rows=0
    with pool.open() as handle:
        for raw in handle:
            row=json.loads(raw);pool_rows+=1
            if pool_rows>100000:raise ValueError('private_pool_scan_limit_exceeded')
            record=row['record']
            phrases.update(phrase_hashes(record['text']))
            for field in ('id','thread_id','parent_id','account_id'):
                value=record.get(field)
                if isinstance(value,str) and value:
                    identities.setdefault(value.casefold(),set()).add(field)
    token_findings=[];phrase_findings=[];json_exact_findings=[]
    for p in files:
        raw=p.read_text();name=str(p.relative_to(public_root))
        tokens=set(re.findall(r'[A-Za-z0-9_:-]+',raw.casefold()))
        matched=tokens&identities.keys()
        if matched:
            kinds=Counter(k for token in matched for k in identities[token])
            token_findings.append({'path':name,'unique_known_token_matches':len(matched),
                                   'categories':dict(sorted(kinds.items()))})
        shared=phrase_hashes(raw)&phrases
        if shared:phrase_findings.append({'path':name,'shared_15_word_phrases':len(shared)})
        if p.suffix=='.json':
            values=set(s.casefold() for s in strings(json.loads(raw)))
            exact=values&identities.keys()
            if exact:json_exact_findings.append({'path':name,'exact_known_identity_values':len(exact)})
            shared=set().union(*(phrase_hashes(s) for s in strings(json.loads(raw))))&phrases
            if shared:phrase_findings.append({'path':name,'decoded_json_shared_15_word_phrases':len(shared)})
    return {'status':'no_matches' if not(token_findings or phrase_findings or json_exact_findings)
            else 'potential_matches_require_review','public_files':inventory,'files_checked':len(files),
            'bytes_checked':sum(r['bytes'] for r in inventory),'private_pool_records':pool_rows,
            'audit_provenance_nodes':len(provenance),'known_identity_tokens':len(identities),
            'private_candidate_15_word_phrase_hashes':len(phrases),
            'identity_token_findings':token_findings,'exact_json_identity_findings':json_exact_findings,
            'candidate_phrase_findings':phrase_findings,
            'cache_files_excluded':True,'historical_prose_read':False,'private_values_emitted':False,
            'style_scores_computed':0,
            'limitations':['Exact known identity tokens and new-candidate 15-word lexical sequences only.',
                'Common words or synthetic fixture tokens can be benign identity matches.',
                'No proof against paraphrases, shorter excerpts, unlisted identities or indirect inference.',
                'Inventory hashes bind only files present at this scan; later changes require another scan.']}


def main():
    p=argparse.ArgumentParser()
    for key in ('public-root','pool','audit','flags','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('privacy_scan_limit')))
    signal.alarm(300)
    start={'started_utc':datetime.now(timezone.utc).isoformat(),'checker_sha256':sha(__file__),
        'input_sha256':{k:sha(getattr(a,k)) for k in ('pool','audit','flags')},'style_scores_computed':0}
    with Path(str(a.out)+'.start-binding.json').open('x') as h:json.dump(start,h,sort_keys=True,indent=2)
    result=review(a.public_root,a.pool,a.audit,a.flags)
    result['checker_sha256']=start['checker_sha256']
    with a.out.open('x') as h:json.dump(result,h,sort_keys=True,indent=2);h.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='public_files'},sort_keys=True))
    raise SystemExit(0 if result['status']=='no_matches' else 2)


if __name__=='__main__':main()
