"""Build the draft's checked-in schemas. Not a data collector or converter."""
from pathlib import Path
import json
ROOT = Path(__file__).resolve().parents[1]
BASE = 'urn:ahif:schema:0.1.1'

def obj(props, required=(), **kw):
    return {'type':'object','additionalProperties':False,'properties':props,'required':list(required),**kw}
def text(n=4096, minimum=0): return {'type':'string','minLength':minimum,'maxLength':n}
def enum(*values): return {'enum':list(values)}
def arr(items, n=1024): return {'type':'array','items':items,'maxItems':n}
def ref(name): return {'$ref':f'#/$defs/{name}'}
def nullable(s): return {'anyOf':[s,{'type':'null'}]}
def req_if(prop,value,then):
    return {'if':{'properties':{prop:{'const':value}},'required':[prop]},'then':then}
D={}
D['digest']={'type':'string','pattern':'^[0-9a-f]{64}$'}
D['hash_id']={'type':'string','pattern':'^sha256:[0-9a-f]{64}$'}
D['uri']={**text(8192,1),'format':'uri'}
D['key']=obj({
 'namespace':{**text(4096,1),'format':'uri','description':'Identity authority, not the collection endpoint. Stable across observations.'},
 'collection':text(128,1), 'id_type':enum('native','uri','handle','source_local'),
 'id':text(8192,1)},['namespace','collection','id_type','id'],description='Compound source identity. Compare all four fields exactly; no cross-platform identity inference.')
D['utc']={'type':'string','pattern':r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:[0-5]\d(?:\.\d{1,9})?Z$','format':'date-time'}
D['time']={'oneOf':[
 obj({'status':{'const':'known'},'value':ref('utc'),'precision':enum('second','millisecond','microsecond','nanosecond'),
      'basis':enum('source','source_documented_conversion','derived','supplier_declared'),'raw':nullable(text(1024))},['status','value','precision','basis']),
 obj({'status':{'const':'date_only'},'value':{'type':'string','format':'date','pattern':r'^\d{4}-\d{2}-\d{2}$'},
      'utc_offset':nullable({'type':'string','pattern':r'^(?:Z|[+-](?:0\d|1[0-4]):[0-5]\d)$'}),
      'basis':enum('source','derived','supplier_declared'),'raw':nullable(text(1024))},['status','value','utc_offset','basis']),
 obj({'status':{'const':'interval'},'start':ref('utc'),'end':ref('utc'),
      'bounds':enum('closed','closed_open'),'basis':enum('source','derived','supplier_declared'),
      'raw':nullable(text(1024))},['status','start','end','bounds','basis']),
 obj({'status':{'const':'unknown'},'reason':text(256,1),'raw':nullable(text(1024))},['status','reason'])
]}
D['json_value']={'anyOf':[{'type':'null'},{'type':'boolean'},text(2000000),
 {'type':'integer','minimum':-9007199254740991,'maximum':9007199254740991},
 arr(ref('json_value'),10000),{'type':'object','propertyNames':{'pattern':r'^[\x20-\x7e]+$'},'additionalProperties':ref('json_value'),'maxProperties':10000}]}
D['extensions']={'type':'object','maxProperties':100,'propertyNames':{'pattern':r'^[A-Za-z0-9][A-Za-z0-9._-]*:[A-Za-z0-9][A-Za-z0-9._/-]*$'},'additionalProperties':ref('json_value')}
D['locator']=obj({'kind':enum('json_pointer','jsonl_line','csv_row','dom_selector','archive_member','source_id','manual','other'),
 'value':text(8192,1),'artifact_sha256':nullable(ref('digest'))},['kind','value'])
D['transform']=obj({'operation':text(256,1),'version':text(128,1),'parameters':ref('json_value'),
 'input_locator':nullable(ref('locator')),'notes':text(4096)},['operation','version'])
D['provenance']=obj({'locator':ref('locator'),'normalizer':obj({'name':text(256,1),'version':text(128,1),
 'configuration_sha256':nullable(ref('digest'))},['name','version']),
 'transformations':arr(ref('transform'),128),'notes':text(8192)},['locator','normalizer','transformations'])
D['language']=obj({'tag':text(128,1),'basis':enum('source','owner_declared','dataset_assumption','model_annotation','unknown'),
 'method':nullable(text(512))},['tag','basis'],allOf=[req_if('basis','unknown',{'properties':{'tag':{'const':'und'}}})])
D['attribution']=obj({'relation':enum('record_actor','other','system','unknown'),'account_key':nullable(ref('key'))},['relation','account_key'],
 allOf=[req_if('relation','record_actor',{'properties':{'account_key':{'type':'null'}}}),req_if('relation','system',{'properties':{'account_key':{'type':'null'}}}),req_if('relation','unknown',{'properties':{'account_key':{'type':'null'}}})])
D['text_part']=obj({'part_id':text(128,1),'role':enum('body','title','quote','signature','code','caption','link_preview','interface','unknown'),
 'attribution':ref('attribution'),'format':enum('plain','commonmark','html','bbcode','other','unknown'),
 'format_variant':nullable(text(128)),'text':text(2000000),
 'fidelity':enum('source_field','rendered_text','transcription','transformed','unknown'),
 'language':ref('language'),'locator':nullable(ref('locator'))},['part_id','role','attribution','format','text','fidelity','language'])
D['content']=obj({'availability':enum('present','empty','unavailable','redacted'),
 'completeness':enum('complete','partial','truncated','unknown','not_applicable'),
 'reason':nullable(text(512)),'parts':arr(ref('text_part'),1024)},['availability','completeness','reason','parts'],allOf=[
 req_if('availability','present',{'properties':{'parts':{'minItems':1},'completeness':enum('complete','partial','truncated','unknown')}}),
 req_if('availability','empty',{'properties':{'parts':{'maxItems':0},'completeness':{'const':'complete'}}}),
 req_if('availability','unavailable',{'properties':{'parts':{'maxItems':0},'reason':text(512,1),'completeness':{'const':'not_applicable'}}}),
 req_if('availability','redacted',{'properties':{'reason':text(512,1),'completeness':enum('partial','not_applicable')}})
])
D['relation']=obj({'type':enum('reply_to','quotes','reposts','crossposts','mentions','other'),
 'target_type':enum('record','account'),'target_key':nullable(ref('key')),'target_url':nullable(text(8192)),
 'resolution':enum('known_identity','locator_only','unknown'),'source_field':nullable(text(1024))},['type','target_type','target_key','target_url','resolution'],allOf=[
 req_if('resolution','known_identity',{'properties':{'target_key':ref('key')}}),
 req_if('resolution','locator_only',{'properties':{'target_key':{'type':'null'},'target_url':text(8192,1)}}),
 req_if('resolution','unknown',{'properties':{'target_key':{'type':'null'},'target_url':{'type':'null'}}})
])
D['context']=obj({'kind':enum('community','forum_section','thread','channel','group','other'),
 'key':ref('key'),'label':nullable(text(4096)),'basis':enum('source','derived','supplier_declared')},['kind','key','basis'])
D['span']=obj({'part_id':text(128,1),'start':{'type':'integer','minimum':0},'end':{'type':'integer','minimum':0},
 'unit':{'const':'unicode_code_points'},'coordinate_space':{'const':'part.text'}},['part_id','start','end','unit','coordinate_space'])
D['link']=obj({'link_id':text(128,1),'role':enum('inline','native_destination','attachment','profile','other'),
 'url_as_supplied':text(8192,1),'resolved_url':nullable(text(8192)),
 'resolution_basis':enum('source_metadata','separately_observed','unknown','not_attempted'),
 'span':nullable(ref('span')),'source_field':nullable(text(1024))},['link_id','role','url_as_supplied','resolved_url','resolution_basis'],allOf=[
 req_if('resolution_basis','not_attempted',{'properties':{'resolved_url':{'type':'null'}}}),
 req_if('resolution_basis','unknown',{'properties':{'resolved_url':{'type':'null'}}})])
D['metric']=obj({'name':text(256,1),'value':{'type':'string','pattern':r'^-?(?:0|[1-9]\d*)(?:\.\d+)?$'},
 'unit':text(128,1),'precision':enum('exact','rounded','lower_bound','upper_bound','unknown'),
 'as_of':ref('time'),'source_field':text(1024,1),'scope':text(4096,1)},['name','value','unit','precision','as_of','source_field','scope'])
D['artifact']=obj({'sha256':nullable(ref('digest')),'byte_length':nullable({'type':'integer','minimum':0}),
 'media_type':text(256,1),'label':text(512,1),'included_path':nullable(text(1024))},['sha256','byte_length','media_type','label','included_path'])
D['source']=obj({'source_id':ref('hash_id'),'mode':enum('account_export','api_response','web_capture','research_corpus','manual_entry','synthetic','other','unknown'),
 'description':text(8192,1),'acquired_at':ref('time'),'content_as_of':ref('time'),
 'origin':nullable(text(8192)),'artifacts':arr(ref('artifact'),1024),
 'access':enum('public','restricted','private','unknown'),
 'redistribution':obj({'status':enum('allowed_by_supplier','prohibited_by_supplier','unknown'), 'basis':text(8192)},['status','basis']),
 'extensions':ref('extensions')},['source_id','mode','description','acquired_at','content_as_of','origin','artifacts','access','redistribution'])
D['gap']=obj({'start':ref('time'),'end':ref('time'),'reason':text(4096,1)},['start','end','reason'])
D['coverage']=obj({'source_id':ref('hash_id'),'account_key':nullable(ref('key')),'scope_description':text(8192,1),
 'status':enum('unknown','partial','complete_for_declared_scope'),
 'basis':text(8192,1),'selection_description':text(8192,1),
 'start':ref('time'),'end':ref('time'),'known_gaps':arr(ref('gap'),10000),
 'context_keys':nullable(arr(ref('key'))),'kinds':nullable(arr(enum('post','reply','repost','quote_post','article','review','other','unknown'),16)),
 'reported_totals':arr(ref('metric'),256)},['source_id','account_key','scope_description','status','basis','selection_description','start','end','known_gaps','reported_totals'])
D['file']=obj({'path':text(1024,1),'role':enum('records','accounts','raw'),'sha256':ref('digest'),
 'byte_length':{'type':'integer','minimum':0},'row_count':nullable({'type':'integer','minimum':0})},['path','role','sha256','byte_length','row_count'])
D['manifest']=obj({'format':{'const':'AHIF'},'format_version':{'const':'0.1.1'},'dataset_id':text(256,1),
 'description':text(8192),'sources':arr(ref('source'),1024),'coverage':arr(ref('coverage'),10000),
 'files':arr(ref('file'),10000),'extensions':ref('extensions')},['format','format_version','dataset_id','sources','coverage','files'],
 description='Dataset manifest. Row lists are observations, not automatically deduplicated account events.')
D['record']=obj({'format_version':{'const':'0.1.1'},'observation_id':ref('hash_id'),'record_key':ref('key'),
 'source_id':ref('hash_id'),'observed_at':ref('time'),'actor':nullable(ref('key')),
 'kind':enum('post','reply','repost','quote_post','article','review','other','unknown'),'native_kind':nullable(text(256)),
 'created_at':ref('time'),'updated_at':ref('time'),
 'lifecycle':obj({'state':enum('visible','deleted','removed','restricted','unknown'),'edit_state':enum('edited','not_edited','unknown'),
 'native_revision_id':nullable(text(8192))},['state','edit_state','native_revision_id']),
 'visibility':enum('public','restricted','private','unknown'),
 'content':ref('content'),'provenance':ref('provenance'),
 'permalink':nullable(text(8192)),'contexts':arr(ref('context')),'relations':arr(ref('relation')),
 'links':arr(ref('link')),'metrics':arr(ref('metric'),256),
 'field_coverage':obj({name:enum('complete','partial','unknown','not_applicable') for name in ['contexts','relations','links','metrics']}),
 'extensions':ref('extensions')},
 ['format_version','observation_id','record_key','source_id','observed_at','actor','kind','created_at','updated_at','lifecycle','visibility','content','provenance'])
D['alias']=obj({'kind':enum('username','display_name','profile_url','other'),'value':text(8192,1)},['kind','value'])
D['account']=obj({'format_version':{'const':'0.1.1'},'observation_id':ref('hash_id'),'account_key':ref('key'),
 'source_id':ref('hash_id'),'observed_at':ref('time'),'aliases':arr(ref('alias'),128),
 'created_at':ref('time'),'state':enum('active','deleted','suspended','restricted','unknown'),
 'profile_parts':arr(ref('text_part'),128),'metrics':arr(ref('metric'),256),
 'provenance':ref('provenance'),'extensions':ref('extensions')},['format_version','observation_id','account_key','source_id','observed_at','aliases','provenance'])
# Reviewed 0.1.1 constraints; see ../CHANGES.md. No 0.1.0 files are rewritten.
D['key']['allOf'] = [req_if('id_type','uri',{'properties':{'id':{'format':'uri'}}})]
D['record_key'] = {'allOf':[ref('key'), {'properties':{'id_type':enum('native','uri','source_local')}}]}
D['record']['properties']['record_key'] = ref('record_key')
D['relation']['allOf'].append(req_if('target_type','record',{'properties':{'target_key':nullable(ref('record_key'))}}))
D['source']['required'].remove('origin')
D['language']['properties']['tag']['pattern'] = r'^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$'
D['language']['allOf'].append(req_if('basis','model_annotation',{'required':['method'],'properties':{'method':text(512,1)}}))
D['content']['allOf'][0]['then']['properties']['parts']['contains'] = {'properties':{'text':{'minLength':1}}}
D['content']['allOf'].append(req_if('availability','redacted',{
 'if':{'properties':{'parts':{'minItems':1}}},
 'then':{'properties':{'completeness':{'const':'partial'}}},
 'else':{'properties':{'completeness':{'const':'not_applicable'}}}}))
D['record']['allOf'] = [{
 'if':{'properties':{'updated_at':{'not':{'properties':{'status':{'const':'unknown'}}}}}},
 'then':{'properties':{'lifecycle':{'properties':{'edit_state':{'const':'edited'}}}}}}]
for name in ('contexts','relations','links','metrics'):
 D['record']['allOf'].extend([
  {'if':{'required':['field_coverage'],'properties':{'field_coverage':{'required':[name],'properties':{name:enum('complete','partial')}}}},
   'then':{'required':[name]}},
  {'if':{'required':['field_coverage'],'properties':{'field_coverage':{'required':[name],'properties':{name:{'const':'not_applicable'}}}}},
   'then':{'properties':{name:{'maxItems':0}}}}])
D['path'] = {**text(1024,1), 'pattern':r'^(?!/)(?!.*[\\\x00-\x1f\x7f:])(?!.*(?:^|/)\.{1,2}(?:/|$))[^/]+(?:/[^/]+)*$'}
D['file']['properties']['path'] = ref('path')
D['artifact']['properties']['included_path'] = nullable(ref('path'))
D['file']['allOf'] = [req_if('role','raw',{'properties':{'row_count':{'type':'null'}}}),
 {'if':{'properties':{'role':enum('records','accounts')}},'then':{'properties':{'row_count':{'type':'integer','minimum':0}}}}]
D['artifact']['allOf'] = [{'if':{'properties':{'included_path':{'type':'string'}}},
 'then':{'properties':{'sha256':ref('digest'),'byte_length':{'type':'integer','minimum':0}}}}]
for name in ('sources','coverage','files'):
 D['manifest']['properties'][name]['minItems'] = 1
D['manifest']['properties']['files']['contains'] = {'properties':{'role':{'const':'records'}}}
# Regex digits are ASCII, not Python's broader Unicode digit class.
def ascii_digits(value):
 if isinstance(value,dict):
  for name,item in value.items():
   if name=='pattern':
    item=item.replace(r'\d', '[0-9]')
    # JS/Python `$` also matches before a final newline; IDs/tags are exact.
    value[name]=item[:-1]+r'(?![\s\S])' if item.endswith('$') else item
   else: ascii_digits(item)
 elif isinstance(value,list):
  for item in value: ascii_digits(item)
ascii_digits(D)
root={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':BASE,
 '$comment':'Draft design. Semantic checks in SPEC.md are normative in addition to this schema. Local refs only; never retrieve schemas over the network.',
 '$defs':D}
(ROOT/'schemas'/'ahif.schema.json').write_text(json.dumps(root,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
for kind in ['manifest','record','account']:
 schema={'$schema':root['$schema'],'$id':BASE+':'+kind,'$ref':BASE+'#/$defs/'+kind}
 (ROOT/'schemas'/f'{kind}.schema.json').write_text(json.dumps(schema,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':print('Wrote 4 draft schema documents.')
