"""Executable 0.1.1 contract review, using fictional evidence only."""
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import validate_bundle as v


class ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=v.ROOT/'examples/minimal'
        cls.man=v.strict_loads((cls.bundle/'manifest.json').read_bytes())
        cls.source=cls.man['sources'][0]
        cls.sources={cls.source['source_id']:cls.source}
        cls.base=v.strict_loads((cls.bundle/'records.jsonl').read_bytes())

    def check(self,row,kind='record',sources=None):
        row['observation_id']=v.bound_id(kind,row)
        return v.row_checks(kind,row,self.sources if sources is None else sources)

    @contextmanager
    def bundle_copy(self,name='minimal'):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'bundle'
            shutil.copytree(v.ROOT/'examples'/name,out)
            yield out

    def refresh(self,root,manifest=None):
        man=manifest or v.strict_loads((root/'manifest.json').read_bytes())
        for f in man['files']:
            data=(root/f['path']).read_bytes()
            f.update(sha256=hashlib.sha256(data).hexdigest(),byte_length=len(data))
        (root/'manifest.json').write_bytes(v.canonical(man)+b'\n')

    def test_negative_fixtures_rehash_before_semantic_rejection(self):
        cases=v.strict_loads((v.ROOT/'fixtures/negative-cases.json').read_bytes())
        for case in cases:
            with self.subTest(case=case['name']):
                row=deepcopy(self.base);target=row
                for key in case['path'][:-1]: target=target[key]
                target[case['path'][-1]]=case['value']
                with self.assertRaisesRegex(ValueError,case['error']): self.check(row)

    def test_all_six_canonical_bundles(self):
        bundles=[p for p in (v.ROOT/'examples').iterdir() if p.is_dir()]
        self.assertEqual(len(bundles),6)
        for root in bundles:
            with self.subTest(bundle=root.name):
                self.assertTrue(v.validate_bundle(root,require_canonical=True)['canonical_export'])

    def test_repeats_conflicts_equal_text_and_totals(self):
        root=v.ROOT/'examples/review-cases'
        result=v.validate_bundle(root)
        self.assertEqual((result['record_observations'],result['distinct_record_keys']),(14,11))
        rows=[v.strict_loads(line) for line in (root/'records.jsonl').read_bytes().split(b'\n') if line]
        repeated=[r for r in rows if r['record_key']['id']=='repeated']
        self.assertEqual(len(repeated),4)
        self.assertEqual(len({r['source_id'] for r in repeated}),2)
        twins=[r for r in rows if r['record_key']['id'].startswith('same_text_')]
        self.assertEqual(len(twins),2)
        self.assertEqual(twins[0]['content'],twins[1]['content'])
        self.assertNotEqual(v.key_string(twins[0]['record_key']),v.key_string(twins[1]['record_key']))
        self.assertEqual(result['completeness_status'],'not_established')
        self.assertNotIn('completeness_percent',result)

    def test_extensions_and_transform_parameters_are_opaque(self):
        row=deepcopy(self.base)
        opaque={'status':'date_only','value':'not a time','other':[1,True,None]}
        row['extensions']={'org.example:data':opaque}
        row['provenance']['transformations']=[{'operation':'fictional','version':'1','parameters':opaque}]
        self.check(row)
        self.assertEqual(row['extensions']['org.example:data'],opaque)

    def test_local_keys_on_all_typed_surfaces(self):
        row=deepcopy(self.base)
        local={**row['actor'],'id_type':'source_local','id':row['source_id']+'#/actor'}
        row['actor']=local;self.check(row)
        row['actor']['id']=row['source_id']+'#'
        with self.assertRaisesRegex(v.Invalid,'nonempty locator'): self.check(row)
        for surface in ('actor','attribution','context','relation'):
            with self.subTest(surface=surface):
                row=deepcopy(self.base)
                bad={**local,'id':'sha256:'+'0'*64+'#/missing'}
                if surface=='actor': row['actor']=bad
                if surface=='attribution': row['content']['parts'][0]['attribution']={'relation':'other','account_key':bad}
                if surface=='context': row['contexts']=[{'kind':'thread','key':bad,'basis':'source'}]
                if surface=='relation': row['relations']=[{'type':'reply_to','target_type':'record','target_key':bad,'target_url':None,'resolution':'known_identity'}]
                with self.assertRaisesRegex(v.Invalid,'declared source_id'): self.check(row)

    def test_local_subjects_do_not_migrate_between_sources(self):
        source=deepcopy(self.source);source['description']='A second fictional capture'
        source['source_id']=v.bound_id('source',source)
        sources={**self.sources,source['source_id']:source}
        for field in ('record_key','actor'):
            row=deepcopy(self.base)
            row[field].update(id_type='source_local',id=source['source_id']+'#/item')
            with self.assertRaisesRegex(v.Invalid,'observation source_id'): self.check(row,sources=sources)
        row=deepcopy(self.base)
        target={**row['record_key'],'id_type':'source_local','id':source['source_id']+'#/parent'}
        row['relations']=[{'type':'reply_to','target_type':'record','target_key':target,'target_url':None,'resolution':'known_identity'}]
        self.check(row,sources=sources)  # Cross-source reference, not a subject identity.

    def test_account_profile_subject_and_unique_parts(self):
        row={'format_version':v.VERSION,'account_key':deepcopy(self.base['actor']),
             'source_id':self.base['source_id'],'observed_at':{'status':'unknown','reason':'not_supplied'},
             'aliases':[],'provenance':deepcopy(self.base['provenance']),
             'profile_parts':deepcopy(self.base['content']['parts'])}
        self.check(row,'account')  # record_actor means this profile's account_key.
        row['profile_parts']*=2
        with self.assertRaisesRegex(v.Invalid,'Repeated content part ID'): self.check(row,'account')

    def test_unknown_and_optional_source_metadata(self):
        self.assertNotIn('origin',self.source)
        row=deepcopy(self.base);row['content']['parts'][0]['language']={'tag':'und','basis':'source'}
        self.check(row)
        row['content']['parts'][0]['language']={'tag':'en','basis':'model_annotation','method':'fictional-test/1'}
        self.check(row)

    def test_list_coverage_cannot_claim_an_unsupplied_list(self):
        row=deepcopy(self.base);row['field_coverage']={'links':'complete'}
        with self.assertRaisesRegex(v.Invalid,'Schema error'): self.check(row)
        row['links']=[];self.check(row)
        row['field_coverage']['links']='unknown';row.pop('links');self.check(row)
        row['field_coverage']['links']='not_applicable'
        row['links']=[{'link_id':'x','role':'native_destination','url_as_supplied':'https://example.test',
                       'resolved_url':None,'resolution_basis':'not_attempted'}]
        with self.assertRaisesRegex(v.Invalid,'Schema error'): self.check(row)

    def test_uri_syntax_without_optional_format_dependencies(self):
        for uri in ('urn:ahif:service:x','https://forum.example/a%20b?q=1#f','https://[::1]/','urn:example:α'):
            with self.subTest(uri=uri): self.assertEqual(v.absolute_uri(uri),'α' not in uri)
        for uri in ('relative','https://bad host','https://x/%xx','https://x/\n','https://[bad]/','https://x:port/','https://a@b@c','https://x/#a#b'):
            with self.subTest(uri=uri): self.assertFalse(v.absolute_uri(uri))

    def test_schema_tokens_require_ascii_digits_and_exact_end(self):
        row=deepcopy(self.base)
        row['content']['parts'][0]['language']={'tag':'en\n','basis':'source'}
        with self.assertRaisesRegex(v.Invalid,'Schema error'): self.check(row)
        man=deepcopy(self.man)
        man['sources'][0]['artifacts']=[{'sha256':'0'*64+'\n','byte_length':None,'included_path':None,
                                       'media_type':'application/octet-stream','label':'Omitted'}]
        with self.assertRaisesRegex(v.Invalid,'Schema error'): v.structural('manifest',man)
        row=deepcopy(self.base)
        row['metrics']=[{'name':'fictional','value':'1٢','unit':'count','precision':'exact','as_of':row['observed_at'],
                        'source_field':'count','scope':'fictional supplied total'}]
        with self.assertRaisesRegex(v.Invalid,'Schema error'): self.check(row)

    def test_each_key_field_and_literal_spelling_participates(self):
        original=deepcopy(self.base['record_key'])
        for field,value in (('namespace','https://elsewhere.example'),('collection','comments'),
                            ('id_type','source_local'),('id',' 812'),('id','812 '),('id','0812')):
            self.assertNotEqual(v.key_string(original),v.key_string({**original,field:value}))

    def test_canonical_known_answer_and_domain_separation(self):
        value={'z':9007199254740991,'a':'\x00\b\t\n\f\r"\\/é😀','list':[True,False,None,-9007199254740991]}
        expected=b'{"a":"\\u0000\\b\\t\\n\\f\\r\\"\\\\/'+ 'é😀'.encode()+b'","list":[true,false,null,-9007199254740991],"z":9007199254740991}'
        self.assertEqual(v.canonical(value),expected)
        for kind in ('source','record','account'):
            self.assertEqual(v.bound_id(kind,{}),'sha256:'+hashlib.sha256(f'AHIF:{kind}:0.1.1\n{{}}'.encode()).hexdigest())
        self.assertEqual(len({v.bound_id(k,{}) for k in ('source','record','account')}),3)
        self.assertNotEqual(v.bound_id('record',{}),'sha256:'+hashlib.sha256(b'AHIF:record:0.1.0\n{}').hexdigest())
        self.assertEqual(v.canonical(v.strict_loads('-0')),b'0')
        for token in ('1e0','1.0','NaN','9007199254740992','-9007199254740992','{"":1}','{"é":1}'):
            with self.subTest(token=token),self.assertRaises(v.Invalid): v.strict_loads(token)
        with self.assertRaises(v.Invalid): v.strict_loads(b'"\xff"')

    def test_canonical_profile_distinct_from_ordinary_validation(self):
        for mode in ('no_final_lf','crlf','spacing','row_order','manifest_order'):
            with self.subTest(mode=mode),self.bundle_copy('review-cases') as root:
                p=root/'records.jsonl';data=p.read_bytes()
                if mode=='no_final_lf': p.write_bytes(data[:-1])
                if mode=='crlf': p.write_bytes(data.replace(b'\n',b'\r\n'))
                if mode=='spacing': p.write_bytes(b' '+data)
                if mode=='row_order': p.write_bytes(b'\n'.join(reversed(data.rstrip(b'\n').split(b'\n')))+b'\n')
                man=v.strict_loads((root/'manifest.json').read_bytes())
                if mode=='manifest_order': man['sources'].reverse()
                self.refresh(root,man)
                self.assertFalse(v.validate_bundle(root)['canonical_export'])
                with self.assertRaisesRegex(v.Invalid,'Noncanonical export'): v.validate_bundle(root,require_canonical=True)

    def test_blank_line_and_duplicate_observation_even_across_shards(self):
        with self.bundle_copy() as root:
            p=root/'records.jsonl';p.write_bytes(p.read_bytes()+b'\n');self.refresh(root)
            with self.assertRaisesRegex(v.Invalid,'Blank JSONL line'): v.validate_bundle(root)
        with self.bundle_copy() as root:
            man=deepcopy(self.man);shutil.copyfile(root/'records.jsonl',root/'records-2.jsonl')
            man['files'].append({**man['files'][0],'path':'records-2.jsonl'});self.refresh(root,man)
            with self.assertRaisesRegex(v.Invalid,'Duplicate observation'): v.validate_bundle(root)

    def test_manifest_integrity_and_source_coverage(self):
        for issue in ('row_count','missing_coverage','missing_records','raw_row_count','artifact_null_digest'):
            with self.subTest(issue=issue),self.bundle_copy('mixed-platform') as root:
                man=v.strict_loads((root/'manifest.json').read_bytes())
                if issue=='row_count': next(f for f in man['files'] if f['role']=='records')['row_count']+=1
                if issue=='missing_coverage': man['coverage']=[]
                if issue=='missing_records': man['files']=[f for f in man['files'] if f['role']!='records']
                if issue=='raw_row_count': next(f for f in man['files'] if f['role']=='raw')['row_count']=0
                if issue=='artifact_null_digest': man['sources'][0]['artifacts'][0]['sha256']=None
                self.refresh(root,man)
                with self.assertRaises(v.Invalid): v.validate_bundle(root)
        with self.bundle_copy('review-cases') as root:
            man=v.strict_loads((root/'manifest.json').read_bytes());man['coverage'].pop();self.refresh(root,man)
            with self.assertRaisesRegex(v.Invalid,'Every source requires'): v.validate_bundle(root)

    def test_path_inventory_and_optional_raw(self):
        for path in ('../manifest.json','/tmp/a','raw//a','./a','a/../b','a\\b','C:/a','raw/a:b','raw/\x01a'):
            with self.subTest(path=path),self.assertRaises(v.Invalid): v.safe_path(self.bundle,path)
        with self.bundle_copy() as root:
            (root/'unlisted.txt').write_text('Fictional unlisted member')
            with self.assertRaisesRegex(v.Invalid,'inventory'): v.validate_bundle(root)
        with self.bundle_copy() as root:
            (root/'alias').symlink_to('records.jsonl')
            with self.assertRaisesRegex(v.Invalid,'Symlink'): v.validate_bundle(root)
        with self.bundle_copy() as root:
            p=root/'records.jsonl';data=p.read_bytes();p.unlink()
            (root/'target').write_bytes(data);p.symlink_to('target')
            with self.assertRaises(v.Invalid): v.validate_bundle(root)
        with self.bundle_copy() as root:
            man=deepcopy(self.man);s=man['sources'][0]
            s['artifacts']=[{'sha256':None,'byte_length':None,'included_path':None,'media_type':'application/octet-stream','label':'Not retained'}]
            old=s['source_id'];s['source_id']=v.bound_id('source',s)
            man['coverage'][0]['source_id']=s['source_id']
            row=deepcopy(self.base);row['source_id']=s['source_id'];row['observation_id']=v.bound_id('record',row)
            (root/'records.jsonl').write_bytes(v.canonical(row)+b'\n');self.refresh(root,man)
            self.assertTrue(v.validate_bundle(root)['canonical_export'])

    def test_included_raw_and_locator_digests_are_bound(self):
        with self.bundle_copy('mixed-platform') as root:
            p=root/'raw/source.json';p.write_bytes(p.read_bytes()+b' ')
            with self.assertRaisesRegex(v.Invalid,'checksum mismatch'): v.validate_bundle(root)
            self.refresh(root)
            with self.assertRaisesRegex(v.Invalid,'artifact descriptor mismatch'): v.validate_bundle(root)

    def test_limits_refuse_without_sampling(self):
        for limit in ('MAX_MANIFEST','MAX_LINE','MAX_FILE','MAX_BUNDLE','MAX_ROWS'):
            with self.subTest(limit=limit),patch.object(v,limit,0),self.assertRaisesRegex(v.Invalid,'limit exceeded'):
                v.validate_bundle(self.bundle)

    def test_inconsistent_supplied_dates_are_retained_with_warning(self):
        row=deepcopy(self.base)
        row['created_at']={'status':'known','value':'2026-09-02T00:00:00Z','precision':'second','basis':'source'}
        row['updated_at']={**row['created_at'],'value':'2026-09-01T00:00:00Z'}
        row['lifecycle']['edit_state']='edited'
        self.assertIn('source_updated_time_before_created_time',self.check(row))
        self.assertEqual(row['updated_at']['value'],'2026-09-01T00:00:00Z')

    def test_actual_ahas_schema_rejects_direct_ahif(self):
        repo=v.ROOT.parents[2]
        # Use installed API for genuine offline record/snapshot validation only.
        from account_history_analyzer.schemas import validate, load_schema
        from account_history_analyzer.errors import InputError
        for name in ('record','snapshot'):
            self.assertEqual(load_schema(name),json.loads((repo/f'schemas/{name}.schema.json').read_text()))
        with self.assertRaises(InputError): validate(self.base,'record')
        with self.assertRaises(InputError): validate(self.man,'snapshot')
        validate({'schema_version':'1.0.0','id':'fictional','account_id':'fictional','kind':'submission','status':'present','text':''},'record')
        with self.assertRaises(InputError):
            validate({'schema_version':'1.0.0','id':'fictional','account_id':'fictional','kind':'submission','status':'removed','text':'retained'},'record')

if __name__=='__main__': unittest.main(verbosity=2)
