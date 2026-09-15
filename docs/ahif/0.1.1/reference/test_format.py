"""Draft-format examples and adverse-input checks, not analyzer validation."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import validate_bundle as v

class FormatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=v.ROOT/'examples'/'mixed-platform'
        cls.man=v.strict_loads((cls.root/'manifest.json').read_bytes())
        cls.sources={s['source_id']:s for s in cls.man['sources']}
        cls.rows=[v.strict_loads(line) for line in (cls.root/'records.jsonl').read_bytes().split(b'\n') if line]
        cls.base=next(r for r in cls.rows if r['record_key']['id']=='18446744073709551615')
    def record(self):return copy.deepcopy(self.base)
    def check(self,r):
        r['observation_id']=v.bound_id('record',r)
        return v.row_checks('record',r,self.sources)
    def reject(self,r):
        with self.assertRaises((v.Invalid,ValueError)): self.check(r)
    def test_01_all_four_bundles(self):
        for name in ['minimal','mixed-platform','uncertain-time','hostile-and-identity']:
            with self.subTest(name=name):self.assertEqual(v.validate_bundle(v.ROOT/'examples'/name)['status'],'passed')
    def test_02_schema_metaschemas(self):self.assertEqual(set(v.validators()),{'record','account','manifest'})
    def test_03_key_order_invariant(self):
        r=self.record(); rev=dict(reversed(list(r.items())))
        self.assertEqual(v.canonical(r),v.canonical(rev))
    def test_04_unicode_preserved_not_normalized(self):
        self.assertNotEqual(v.canonical('é'),v.canonical('e\u0301'))
    def test_05_duplicate_json_keys_rejected(self):
        with self.assertRaises(v.Invalid):v.strict_loads('{"x":1,"x":2}')
    def test_06_nonfinite_rejected(self):
        for value in ['NaN','Infinity','-Infinity']:
            with self.assertRaises(v.Invalid):v.strict_loads(value)
    def test_07_float_rejected(self):
        with self.assertRaises(v.Invalid):v.strict_loads('1.0')
    def test_08_large_number_rejected_but_string_allowed(self):
        with self.assertRaises(v.Invalid):v.strict_loads('9007199254740993')
        self.assertEqual(v.strict_loads('"9007199254740993"'),'9007199254740993')
    def test_09_surrogate_rejected(self):
        with self.assertRaises(v.Invalid):v.strict_loads('"\\ud800"')
    def test_10_unknown_extra_core_field(self):
        r=self.record();r['bot_score']=99;self.reject(r)
    def test_11_unknown_actor_cannot_own_text(self):
        r=self.record();r['actor']=None;self.reject(r)
    def test_12_anonymous_text_can_be_retained(self):
        r=self.record();r['actor']=None;r['content']['parts'][0]['attribution']['relation']='unknown';self.check(r)
    def test_13_repost_cannot_own_commentary(self):
        r=self.record();r['kind']='repost';self.reject(r)
    def test_14_unavailable_text_cannot_contain_parts(self):
        r=self.record();r['content'].update(availability='unavailable',completeness='not_applicable',reason='not_supplied');self.reject(r)
    def test_15_bad_calendar_date(self):
        r=self.record();r['created_at']['value']='2026-02-30T00:00:00Z';self.reject(r)
    def test_16_date_only_valid(self):
        r=self.record();r['created_at']={'status':'date_only','value':'2026-08-20','utc_offset':None,'basis':'source'};self.check(r)
    def test_17_interval_reversal_rejected(self):
        r=self.record();r['created_at']={'status':'interval','start':'2026-08-20T01:00:00Z','end':'2026-08-20T00:00:00Z','bounds':'closed','basis':'source'};self.reject(r)
    def test_18_precision_not_invented(self):
        r=self.record();r['created_at']['value']='2026-08-20T00:00:00.123Z';self.reject(r)
    def test_19_nanoseconds_preserved(self):
        self.assertEqual(v.utc_ns('2026-08-20T00:00:00.123456789Z')-v.utc_ns('2026-08-20T00:00:00Z'),123456789)
    def test_20_unknown_edit_not_false(self):
        r=self.record();r['updated_at']=r['created_at'];self.reject(r)
    def test_21_same_object_multiple_observations(self):
        result=v.validate_bundle(self.root)
        self.assertEqual((result['record_observations'],result['distinct_record_keys']),(12,11))
    def test_22_different_namespace_not_same_identity(self):
        k=self.base['record_key'];other={**k,'namespace':'https://different.example'}
        self.assertNotEqual(v.key_string(k),v.key_string(other))
    def test_23_exact_string_edit_changes_observation(self):
        r=self.record();before=v.bound_id('record',r);r['content']['parts'][0]['text']+=' '
        self.assertNotEqual(before,v.bound_id('record',r))
    def test_24_span_counts_codepoints(self):
        self.check(self.record())
        r=self.record();r['links'][0]['span']['end']+=1;self.reject(r)
    def test_25_repeated_part_ids(self):
        r=self.record();r['content']['parts'].append(copy.deepcopy(r['content']['parts'][0]));self.reject(r)
    def test_26_empty_link_list_not_complete_without_declaration(self):
        r=self.record();r['links']=[];self.check(r)
        self.assertNotIn('field_coverage',r)
    def test_27_bom_rejected(self):
        with self.assertRaises(v.Invalid):v.strict_loads(b'\xef\xbb\xbf{}')
    def test_28_local_key_scope(self):
        r=self.record();r['record_key'].update(id_type='source_local',id=r['source_id']+'#/records/0');self.check(r)
        r['record_key']['id']='unscoped';self.reject(r)
    def test_29_handle_identifier_allowed_not_native(self):
        r=self.record();r['actor']['id_type']='handle';r['actor']['id']='SampleUser';self.check(r)
    def test_30_depth_bounded(self):
        value=0
        for _ in range(70):value=[value]
        with self.assertRaises(v.Invalid):v.check_values(value)
    def test_31_path_traversal(self):
        with self.assertRaises(v.Invalid):v.safe_path(self.root,'../manifest.json')
    def test_32_checksum_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            dst=Path(d)/'bundle';shutil.copytree(self.root,dst)
            with (dst/'records.jsonl').open('ab') as out:out.write(b' ')
            with self.assertRaises(v.Invalid):v.validate_bundle(dst)
    def test_33_unresolved_parent_is_valid_not_fake_record(self):
        r=self.record();r['relations']=[{'type':'reply_to','target_type':'record','target_key':None,'target_url':None,'resolution':'unknown'}];self.check(r)
    def test_34_body_string_not_rewritten(self):
        r=self.record();s=' \r\n café e\u0301 🔧  '
        r['content']['parts'][0]['text']=s;r.pop('links',None);self.check(r)
        self.assertEqual(v.strict_loads(v.canonical(r))['content']['parts'][0]['text'],s)
    def test_35_no_implicit_english(self):
        r=self.record();r['content']['parts'][0]['language']={'tag':'en','basis':'unknown'};self.reject(r)
    def test_36_unknown_future_version(self):
        for version in ('0.1.0','0.2.0'):
            r=self.record();r['format_version']=version;self.reject(r)
    def test_37_unknown_source(self):
        r=self.record();r['source_id']='sha256:'+'0'*64;self.reject(r)
    def test_38_false_timestamp_warns_not_erased(self):
        r=self.record();r['created_at']['value']='2027-01-01T00:00:00Z'
        self.assertIn('source_created_time_after_observed_time',self.check(r))
    def test_39_ascii_keys_profile(self):
        with self.assertRaises(v.Invalid):v.canonical({'é':'value'})
    def test_40_identity_hash_not_claimed_authenticity(self):
        self.assertEqual(v.validate_bundle(self.root)['authenticity_status'],'not_established')

if __name__=='__main__':unittest.main(verbosity=2)
