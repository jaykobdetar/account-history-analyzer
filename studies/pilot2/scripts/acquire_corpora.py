"""Approved acquisition only; all subsequent measurements run offline."""
import datetime,hashlib,json,time,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE='https://zissou.infosci.cornell.edu/convokit/datasets/subreddit-corpus/corpus-zipped/'
SOURCES=[('ApplyingToCollege','AnythingGoesPic~-~ApplyingToCollege',155300755),('college','cock4brains~-~coloringpages',133664381)]
(ROOT/'data').mkdir(exist_ok=True)
plan={'authorization':'User explicitly approved downloading whatever dataset is needed on 2026-09-14, before this acquisition.','scope':'Two bounded existing ConvoKit subreddit archives for local evaluation alongside existing Cornell corpus; no live Reddit collection.','planned_bytes':sum(s[2] for s in SOURCES),'sources':[{'community':n,'url':BASE+folder+'/'+n+'.corpus.zip','expected_bytes_from_official_index':size} for n,folder,size in SOURCES],'selection_rationale':'Related education communities with anticipated overlapping accounts; community is context, not exact topic or authorship truth.','provenance_documentation':'https://convokit.cornell.edu/documentation/subreddit.html','license_status':'No corpus-specific redistribution license established from linked documentation; raw corpora kept local, never included in public repair release.'}
(ROOT/'inventory/acquisition-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
for source in plan['sources']:
    name=source['community'];target=ROOT/'data'/(name+'.corpus.zip');partial=target.with_suffix('.part')
    if target.exists() or partial.exists():raise RuntimeError('Refusing existing acquisition output')
    began=datetime.datetime.now(datetime.UTC).isoformat();tick=time.perf_counter();hashing=hashlib.sha256();size=0
    request=urllib.request.Request(source['url'],headers={'User-Agent':'AHAS-local-evaluation/1.0.4'})
    with urllib.request.urlopen(request,timeout=60) as response,partial.open('xb') as output:
        resolved=response.geturl();headers=dict(response.headers)
        assert resolved==source['url']
        while chunk:=response.read(1024*1024):
            size+=len(chunk)
            if size>source['expected_bytes_from_official_index']:raise RuntimeError('Published size exceeded')
            output.write(chunk);hashing.update(chunk)
    assert size==source['expected_bytes_from_official_index']
    partial.rename(target)
    with zipfile.ZipFile(target) as archive:
        members=[{'name':x.filename,'bytes':x.file_size,'compressed_bytes':x.compress_size,'crc32':x.CRC} for x in archive.infolist()]
        assert all(not Path(x['name']).is_absolute() and '..' not in Path(x['name']).parts for x in members)
    receipt={**source,'resolved_url':resolved,'http_headers':headers,'started_utc':began,'finished_utc':datetime.datetime.now(datetime.UTC).isoformat(),'elapsed_seconds':time.perf_counter()-tick,'actual_bytes':size,'sha256':hashing.hexdigest(),'members':members,'status':'acquired','analysis_executed':False}
    (ROOT/'inventory'/(name+'-acquisition.json')).write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'community':name,'status':'acquired','bytes':size,'sha256':hashing.hexdigest(),'elapsed_seconds':receipt['elapsed_seconds']}),flush=True)
