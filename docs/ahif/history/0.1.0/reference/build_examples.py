"""Build fictional format fixtures only; no platform access and no analyzer calls."""
from copy import deepcopy
from pathlib import Path
import hashlib,json
from validate_bundle import ROOT, bound_id, canonical

def unknown(reason='not_supplied',raw=None):
    out={'status':'unknown','reason':reason}
    if raw is not None:out['raw']=raw
    return out

def known(value='2026-09-01T12:00:00Z',precision='second'):
    return {'status':'known','value':value,'precision':precision,'basis':'source'}

def key(ns,collection,id): return {'namespace':ns,'collection':collection,'id_type':'native','id':id}
def part(text,role='body',format='plain',attr='record_actor',actor=None,lang='en',fidelity='source_field'):
    return {'part_id':role,'role':role,'attribution':{'relation':attr,'account_key':actor},
      'format':format,'text':text,'fidelity':fidelity,'language':{'tag':lang,'basis':'unknown' if lang=='und' else 'source'}}

def row(ns,id,actor,text,kind='post',**kw):
    r={'format_version':'0.1.0','record_key':key(ns,'posts',id),'actor':actor,
     'kind':kind,'observed_at':known(),'created_at':known('2026-08-20T08:00:00Z'),
     'updated_at':unknown(),'lifecycle':{'state':'visible','edit_state':'unknown','native_revision_id':None},
     'visibility':'public','content':{'availability':'present','completeness':'complete','reason':None,'parts':[part(text)]},
     'provenance':{'locator':{'kind':'json_pointer','value':'/records/0'},'normalizer':{'name':'fictional_fixture_builder','version':'0.1.0'},'transformations':[]}}
    r.update(kw);return r

REDDIT='urn:ahif:service:reddit'; X='urn:ahif:service:x'; FORUM='https://forum.example.org'
a=key(REDDIT,'accounts','user_001');b=key(X,'accounts','9007199254740993');c=key(FORUM,'members','17')

minimal=[row(FORUM,'812',c,'I tried the new cable. It works now, but the connector still feels loose.')]
minimal[0]['observed_at']=unknown();minimal[0]['created_at']=unknown()
minimal[0]['content']['parts'][0]['language']={'tag':'und','basis':'unknown'}
minimal[0]['kind']='unknown'

mixed=[]
r=row(REDDIT,'c_demo',a,'I tested this twice.\n\n> The old quoted explanation.\n\nThe second result was different.',kind='reply')
r['native_kind']='comment';r['content']['parts'][0]['format']='commonmark'
r['contexts']=[{'kind':'community','key':key(REDDIT,'communities','demo'),'label':'demo','basis':'source'},
 {'kind':'thread','key':key(REDDIT,'threads','p_demo'),'basis':'source'}]
r['relations']=[{'type':'reply_to','target_type':'record','target_key':key(REDDIT,'posts','parent_not_in_bundle'),
 'target_url':None,'resolution':'known_identity'}]
mixed.append(r)
r=row(X,'18446744073709551615',b,'A short original post — with punctuation, an emoji 🔧, and a link https://t.example/a')
r['links']=[{'link_id':'url_1','role':'inline','url_as_supplied':'https://t.example/a',
 'resolved_url':'https://destination.example/page','resolution_basis':'source_metadata',
 'span':{'part_id':'body','start':r['content']['parts'][0]['text'].index('https:'),'end':len(r['content']['parts'][0]['text']),
 'unit':'unicode_code_points','coordinate_space':'part.text'}}]
mixed.append(r)
r=row(X,'quote_1',b,'This disagrees with my measurements.',kind='quote_post')
r['content']['parts'].append(part('The source statement that another account published.',role='quote',attr='other',actor=key(X,'accounts','someone_else')))
r['relations']=[{'type':'quotes','target_type':'record','target_key':key(X,'posts','outside_1'),'target_url':None,'resolution':'known_identity'}]
mixed.append(r)
r=row(X,'repost_action_1',b,'',kind='repost')
r['content']={'availability':'empty','completeness':'complete','reason':'Pure repost action with no added text.','parts':[]}
r['relations']=[{'type':'reposts','target_type':'record','target_key':key(X,'posts','outside_1'),'target_url':None,'resolution':'known_identity'}]
mixed.append(r)
r=row(FORUM,'html_1',c,'<p>I checked the connector; it is loose.</p>')
r['content']['parts'][0]['format']='html'
r['content']['parts'].append(part('My forum signature',role='signature'))
r['content']['parts'].append(part('Replace the entire system.',role='quote',attr='other'))
r['contexts']=[{'kind':'forum_section','key':key(FORUM,'boards','repairs'),'label':'Repairs','basis':'source'}]
mixed.append(r)
r=row(FORUM,'bbcode_1',c,'[b]Update[/b]: fixed the cable.',kind='reply')
r['content']['parts'][0]['format']='bbcode';r['relations']=[{'type':'reply_to','target_type':'record','target_key':None,'target_url':None,'resolution':'unknown'}]
mixed.append(r)
r=row(FORUM,'partial_1',c,'Only the beginning of this record was supplied…')
r['content']['completeness']='truncated';r['content']['reason']='Source supplied a preview, not the full contribution.'
r['content']['parts'][0]['language']={'tag':'und','basis':'unknown'}
mixed.append(r)
r=row(REDDIT,'deleted_1',None,'',kind='reply')
r['lifecycle']['state']='deleted';r['content']={'availability':'unavailable','completeness':'not_applicable','reason':'deleted_in_source','parts':[]}
mixed.append(r)
r=row(FORUM,'media_1',c,'')
r['content']={'availability':'empty','completeness':'complete','reason':'Image-only contribution; no supplied caption.','parts':[]}
r['links']=[{'link_id':'image_1','role':'attachment','url_as_supplied':'https://media.example/image.png',
 'resolved_url':None,'resolution_basis':'not_attempted'}]
mixed.append(r)
r=row(FORUM,'edited_1',c,'The cable is intact.')
r['observed_at']=known('2026-08-21T10:00:00Z');r['lifecycle']['native_revision_id']='v1';mixed.append(r)
r=deepcopy(r);r['content']['parts'][0]['text']='Correction: the cable is damaged.'
r['observed_at']=known('2026-08-23T10:00:00Z');r['updated_at']=known('2026-08-22T09:00:00Z')
r['lifecycle'].update(edit_state='edited',native_revision_id='v2');mixed.append(r)
r=row(FORUM,'redacted_1',c,'[text removed by the supplier]')
r['content']={'availability':'redacted','completeness':'not_applicable','reason':'Supplier withheld the complete body.','parts':[]}
mixed.append(r)

uncertain=[]
r=row(FORUM,'day',c,'A post with a date but no known posting time.')
r['created_at']={'status':'date_only','value':'2026-08-20','utc_offset':None,'basis':'source'};uncertain.append(r)
r=row(FORUM,'interval',c,'The source reports a posting interval, not one instant.')
r['created_at']={'status':'interval','start':'2026-08-20T08:00:00Z','end':'2026-08-20T09:00:00Z','bounds':'closed_open','basis':'derived','raw':'within this hour'};uncertain.append(r)
r=row(FORUM,'relative',c,'The timezone needed to resolve this display is unknown.')
r['created_at']=unknown('relative_label_not_resolved','yesterday');uncertain.append(r)
r=row(FORUM,'nano',c,'The source supplies precision finer than the frozen engine accepts.')
r['created_at']=known('2026-08-20T08:00:00.123456789Z','nanosecond');uncertain.append(r)

hostile=[]
r=row(FORUM,'hostile',c,'<script>alert("sample")</script> & [x](javascript:sample)\n e\u0301 é  \\u0020 🔧')
r['content']['parts'][0]['format']='plain';hostile.append(r)
r=row('https://another-forum.example','812',key('https://another-forum.example','members','17'),'Same numeric ID on another service is a distinct record and account.')
hostile.append(r)
r=row(FORUM,'anon',None,'Guest writing with no established account attribution.')
r['content']['parts'][0]['attribution']={'relation':'unknown','account_key':None};hostile.append(r)


def make_bundle(name,rows,accounts=False,raw=True):
    out=ROOT/'examples'/name;out.mkdir(parents=True,exist_ok=True)
    rows=deepcopy(rows)
    # A synthetic evidence source independent of the normalized record IDs.
    raw_payload={'notice':'Fictional format examples, not scraped data or research samples.',
     'records':[{k:v for k,v in r.items() if k!='provenance'} for r in rows]}
    raw_bytes=canonical(raw_payload)+b'\n';raw_hash=hashlib.sha256(raw_bytes).hexdigest()
    source={'mode':'synthetic','description':'Fictional '+name+' fixture; no live account or network collection.',
     'acquired_at':known(),'content_as_of':unknown('varies_by_record'),'origin':None,
     'artifacts':([{'sha256':raw_hash,'byte_length':len(raw_bytes),'media_type':'application/json','label':'Fictional original source',
      'included_path':'raw/source.json'}] if raw else []),
     'access':'public','redistribution':{'status':'allowed_by_supplier','basis':'Synthetic examples authored for this design package.'}}
    source['source_id']=bound_id('source',source)
    for i,r in enumerate(rows):
        r['source_id']=source['source_id']
        r['provenance']['locator']={'kind':'json_pointer','value':f'/records/{i}',**({'artifact_sha256':raw_hash} if raw else {})}
        r['observation_id']=bound_id('record',r)
    acct=[]
    if accounts:
        keys={canonical(r['actor']):r['actor'] for r in rows if r['actor']}
        for k in keys.values():
            ar={'format_version':'0.1.0','account_key':k,'source_id':source['source_id'],
             'observed_at':known(),'aliases':[{'kind':'username','value':'sample_user'}],
             'provenance':{'locator':{'kind':'manual','value':'Fictional alias for schema testing'},
              'normalizer':{'name':'fictional_fixture_builder','version':'0.1.0'},'transformations':[]}}
            ar['observation_id']=bound_id('account',ar);acct.append(ar)
    files=[]
    for filename,role,values in [('records.jsonl','records',rows),('accounts.jsonl','accounts',acct)]:
        if role=='accounts' and not accounts:continue
        values.sort(key=lambda r:r['observation_id'])
        data=b''.join(canonical(r)+b'\n' for r in values)
        (out/filename).write_bytes(data)
        files.append({'path':filename,'role':role,'sha256':hashlib.sha256(data).hexdigest(),'byte_length':len(data),'row_count':len(values)})
    if raw:
        (out/'raw').mkdir(exist_ok=True);(out/'raw/source.json').write_bytes(raw_bytes)
        files.append({'path':'raw/source.json','role':'raw','sha256':raw_hash,'byte_length':len(raw_bytes),'row_count':None})
    coverage={'source_id':source['source_id'],'account_key':None,'scope_description':'The explicitly constructed examples in this bundle, not complete account histories.',
      'status':'complete_for_declared_scope','basis':'The fixture builder enumerates this finite synthetic sample.',
      'selection_description':'Purpose-built edge cases; no sampling of actual people.',
      'start':unknown(),'end':unknown(),'known_gaps':[],'reported_totals':[]}
    manifest={'format':'AHIF','format_version':'0.1.0','dataset_id':'fictional-'+name,'sources':[source],
     'coverage':[coverage],'files':sorted(files,key=lambda f:f['path'])}
    (out/'manifest.json').write_bytes(canonical(manifest)+b'\n')
    (ROOT/'examples'/f'{name}-record-readable.json').write_text(json.dumps(rows[0],indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return out

if __name__=='__main__':
    for name,rows,accounts,raw in [('minimal',minimal,False,False),('mixed-platform',mixed,True,True),
          ('uncertain-time',uncertain,False,True),('hostile-and-identity',hostile,True,True)]:
        print(make_bundle(name,rows,accounts,raw))
