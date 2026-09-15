"""Reporting-only archive hash and ZIP-directory inventory; no prose reads."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import time
import zipfile

OLD=('Physics','AskPhysics')
NEW=('linux','linuxquestions','programming','learnprogramming')
ROW_CAP=15000000
BYTE_CAP=10000000000

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def read(path):return json.loads(path.read_bytes())

def check(args):
    started=time.monotonic();utc=datetime.now(timezone.utc).isoformat()
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    old=read(args.prior_inventory);second=read(args.prior_second_pass);new=read(args.intake_summary)
    if new['status']!='completed_score_free_archive_intake':raise ValueError('Incomplete intake cannot certify limits')
    inputs={k:{'sha256':sha(getattr(args,k)),'bytes':getattr(args,k).stat().st_size}
            for k in ('prior_inventory','prior_second_pass','intake_summary','preparation_rules')}
    rows=[]
    for community in OLD+NEW:
        if time.monotonic()-started>120:raise TimeoutError('Metadata inventory wall budget exceeded')
        if community in OLD:
            source=[s for s in old['sources'] if s['community']==community]
            again=[s for s in second if s['community']==community]
            if len(source)!=1 or len(again)!=1:raise ValueError('Expected unique prior source')
            source=source[0];again=again[0];path=Path(source['archive'])
            expected_bytes=source['bytes'];expected_sha=source['sha256'];count=source['counts']['source_records']
            source_group='pilot3_private/data'
        else:
            source=[s for s in new['source_bindings'] if s['community']==community]
            again=[s for s in new['second_pass_bindings'] if s['community']==community]
            if len(source)!=1 or len(again)!=1:raise ValueError('Expected unique new source')
            source=source[0];again=again[0];path=args.new_archive_root/(community+'.corpus.zip')
            expected_bytes=source['archive_bytes'];expected_sha=source['archive_sha256'];count=source['counts']['rows']
            source_group='pilot4_private/data'
        if count!=again['rows'] or source['utterances_sha256']!=again['utterances_sha256']:
            raise ValueError('Independent prior full pass metadata disagree')
        if path.stat().st_size!=expected_bytes or sha(path)!=expected_sha:
            raise ValueError('Archive bytes differ from previously inventoried source')
        with zipfile.ZipFile(path) as z:
            members=[x for x in z.infolist() if x.filename=='utterances.jsonl']
            if len(members)!=1:raise ValueError('Expected one utterance member')
            member=members[0]
            if member.file_size!=source['utterances_bytes']:
                raise ValueError('ZIP member size differs from full-pass receipt')
        rows.append({'community':community,'archive':source_group+'/'+path.name,
          'archive_bytes':expected_bytes,'archive_sha256':expected_sha,'member':'utterances.jsonl',
          'declared_uncompressed_member_bytes':member.file_size,'member_compressed_bytes':member.compress_size,
          'source_rows':count,'source_rows_basis':'Two previous matching full passes; no new source-content scan.',
          'previous_full_pass_utterances_sha256':source['utterances_sha256']})
    totals={'source_rows':sum(r['source_rows'] for r in rows),
      'declared_uncompressed_member_bytes':sum(r['declared_uncompressed_member_bytes'] for r in rows),
      'archive_bytes':sum(r['archive_bytes'] for r in rows)}
    passed=totals['source_rows']<=ROW_CAP and totals['declared_uncompressed_member_bytes']<=BYTE_CAP
    result={'status':'pass' if passed else 'preparation_limits_exceeded','phase':'post_census_reporting_only_archive_inventory',
      'started_utc':utc,'finished_utc':datetime.now(timezone.utc).isoformat(),
      'wall_seconds':time.monotonic()-started,'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
      'implementation_sha256':sha(Path(__file__)),'inputs':inputs,'archives':rows,'totals':totals,
      'limits':{'source_rows':ROW_CAP,'declared_uncompressed_member_bytes':BYTE_CAP},
      'headroom':{'source_rows':ROW_CAP-totals['source_rows'],
        'declared_uncompressed_member_bytes':BYTE_CAP-totals['declared_uncompressed_member_bytes']},
      'coverage':'All six full archive byte hashes freshly verified. ZIP directories inspected without opening the utterance member. Row counts are inherited from two hash-matching completed passes per archive; no new source prose access.',
      'source_member_decompressions':0,'source_prose_displayed':False,'new_preprocessing_calls':0,'new_style_calls':0,
      'calendar_results_modified':False,'cohort_selected':False}
    with args.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'archives':len(rows),'totals':totals,'headroom':result['headroom']}),flush=True)
    return 0 if passed else 1

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('prior-inventory','prior-second-pass','intake-summary','preparation-rules','new-archive-root','out'):
        p.add_argument('--'+name,type=Path,required=True)
    raise SystemExit(check(p.parse_args()))
