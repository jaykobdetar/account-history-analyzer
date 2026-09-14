"""Independent small preparation checks; no optimizer or history scoring."""
import copy
from datetime import datetime,timedelta,timezone
import hashlib
import unittest
import tempfile
import json
from pathlib import Path

import prepare_streams as p


class PreparationChecks(unittest.TestCase):
    def record(self,i,*,side='a',community='Cornell',time=None,status='present'):
        instant=(datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(seconds=i)).isoformat().replace('+00:00','Z') if time is None else time
        return {'id':side+str(i),'account_id':side,'created_utc':instant,'subreddit':community,'text':'Actual source text '+str(i) if status=='present' else None,'status':status}
    def test_union_median_cut_uses_all_supplied_timestamps(self):
        a=[self.record(i) for i in range(0,20,2)]
        b=[self.record(i,side='b') for i in range(1,20,2)]
        originals=copy.deepcopy(a+b)
        result=p.construct(a,b,'constructed')
        self.assertEqual(result['cut_utc'],'2020-01-01T00:00:10Z')
        self.assertEqual([r['id'] for r in result['records']],['a0','a2','a4','a6','a8','b11','b13','b15','b17','b19'])
        self.assertEqual(a+b,originals)
        self.assertEqual(p.surviving_truth(result['records'],result['source_sides'])['truth_boundaries'],[5])
    def test_timestamp_ties_go_to_right_source_only(self):
        a=[self.record(i) for i in range(4)]
        b=[self.record(i,side='b') for i in range(4)]
        result=p.construct(a,b,'c')
        self.assertEqual([r['id'] for r in result['records']],['a0','a1','b2','b3'])
    def test_missing_timestamp_abstains_without_discarding_record(self):
        a=[self.record(0)];a[0]['created_utc']=None
        result=p.construct(a,[self.record(1,side='b')],'c')
        self.assertEqual(result['status'],'not_constructible');self.assertEqual(result['records'],[])
        self.assertIsNone(a[0]['created_utc'])
    def test_hash50_matches_frozen_modulo_rule_and_preserves_survivors(self):
        rows=[self.record(i) for i in range(17)];before=copy.deepcopy(rows)
        expect=[r for r in rows if int(hashlib.sha256(('ahas-pilot2-omission-v1:'+r['id']).encode()).hexdigest(),16)%2==0]
        self.assertEqual(p.arm_records(rows,'hash50'),expect);self.assertEqual(rows,before)
    def test_middle50_uses_registered_floor_indices_for_odd_lengths(self):
        rows=[self.record(i) for i in range(7)]
        self.assertEqual([r['id'] for r in p.arm_records(rows,'middle50')],['a0','a5','a6'])
    def test_community_omission_is_exact_label_and_preserves_nonpresent(self):
        rows=[self.record(0,status='removed'),self.record(1,community='college',status='deleted'),self.record(2,community='cornell')]
        self.assertEqual([r['id'] for r in p.arm_records(rows,'drop_Cornell')],['a1','a2'])
        self.assertEqual(p.arm_records(rows,'full'),rows)
    def test_disappearing_source_side_is_not_unchanged_truth(self):
        rows=[self.record(0),self.record(1)]
        result=p.surviving_truth(rows,{'a0':'left','a1':'left'})
        self.assertEqual(result['status'],'not_labeled_construction');self.assertIsNone(result['truth_boundaries'])
    def test_truth_maps_to_surviving_full_snapshot_ordinals(self):
        rows=[self.record(i) for i in range(8)]
        source_sides={r['id']:'left' if i<4 else 'right' for i,r in enumerate(rows)}
        remaining=[rows[i] for i in (0,2,5,7)]
        self.assertEqual(p.surviving_truth(remaining,source_sides)['truth_boundaries'],[2])
    def test_metadata_combines_cross_corpus_casefolded_authors(self):
        rows=[{'source_account':name,'comment_count':150,'present_raw_codepoints':25000,'source_community':community,'excluded_from_new_sampling':None} for name,community in [('AccountA','Cornell'),('accounta','college')]]
        candidates,_=p.metadata_candidates(rows,set())
        self.assertEqual(len(candidates),1);self.assertEqual(candidates[0]['comment_count'],300)
        self.assertEqual(candidates[0]['home_community'],'Cornell')
        self.assertEqual(p.metadata_candidates(rows,{'accounta'})[0],[])
    def test_registered_candidate_order_salt(self):
        row={'source_account':'AccountA','comment_count':250,'present_raw_codepoints':50000,'source_community':'college','excluded_from_new_sampling':None}
        candidate=p.metadata_candidates([row],set())[0][0]
        self.assertEqual(candidate['rank_hash'],hashlib.sha256(b'ahas-pilot2-chronology-v1:accounta').hexdigest())
    def test_pairing_uses_medians_and_never_reuses_author(self):
        accounts=[{'account_key':str(i),'median_utc_us':m} for i,m in enumerate([0,1,20,21])]
        pairs,leftover=p.pair_closest(accounts)
        self.assertEqual({frozenset(a['account_key'] for a in pair) for pair in pairs},{frozenset(('0','1')),frozenset(('2','3'))})
        self.assertEqual(leftover,[])
    def test_null_nonpresent_and_timestamp_conversion_preserved(self):
        row={'id':'source','text':' [removed] ','timestamp':0,'reply_to':'parent','root':'thread','meta':{'subreddit':'Cornell'}}
        record=p.convert(row,'account')
        self.assertEqual((record['status'],record['text']),('removed',None));self.assertEqual(record['created_utc'],'1970-01-01T00:00:00Z')
        self.assertEqual(row['text'],' [removed] ')
        self.assertEqual(record['parent_created_utc'],None)

    def test_eligibility_uses_actual_feature_contract_and_source_statuses(self):
        from account_history_analyzer.features import extract_records
        from account_history_analyzer import AnalysisConfig,load_snapshot
        records=[p.convert({'id':'present','text':' '.join(['word']*30),'timestamp':1,'root':'thread','reply_to':'parent','meta':{}},'source'),
                 p.convert({'id':'removed','text':'[removed]','timestamp':2,'root':'thread','reply_to':'parent','meta':{}},'source')]
        with tempfile.TemporaryDirectory() as tmp:
            ip,mp=p.write_snapshot(Path(tmp),'sample',records)
            config=AnalysisConfig.from_toml();snapshot=load_snapshot(ip,mp,config)
            features=extract_records(snapshot,config)
            self.assertNotIn('status',features[0])
            counts=p.word_eligibility(features,snapshot.records)
            self.assertEqual(counts['eligible_words'],30)
            self.assertEqual(counts['status_counts'],{'present':1,'removed':1})

    def test_confirmation_component_rejects_whole_author_not_development_peer(self):
        chosen=[{'account_key':'a'},{'account_key':'b'}]
        ids={'a':['a1','a2'],'b':['b1','b2']}
        audit={'status':'audited','components':[
            {'record_ids':['a2','confirm'],'split_memberships':['development','confirmation']},
            {'record_ids':['b2','paired-development'],'split_memberships':['development']}]}
        rejected=p.reject_confirmation_components(chosen,ids,audit,[{'id':'confirm','split':'confirmation'}])
        self.assertEqual(set(rejected),{'a'})
        self.assertEqual(ids['a'],['a1','a2'])
    def test_incomplete_related_audit_rejects_all_provisional_authors(self):
        chosen=[{'account_key':'a'},{'account_key':'b'}]
        self.assertEqual(set(p.reject_confirmation_components(chosen,{}, {'status':'not_auditable'},[])),{'a','b'})
    def test_freeze_is_explicit_and_fails_before_scoring_or_plan_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);freeze=root/'freeze.json'
            for value in ({},{'status':'frozen'},{'status':'frozen','scoring_authorized':False},{'status':'draft','scoring_authorized':True}):
                freeze.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError,'authorization is absent'):
                    p.verify_scoring_freeze(root,freeze)
    def test_prepared_path_escape_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=root/'prepared';base.mkdir();external=root/'source';external.write_text('source')
            with self.assertRaises(ValueError):p.guarded_path(base,'../source')
            (base/'link').symlink_to(external)
            with self.assertRaises(ValueError):p.guarded_path(base,'link')
    def test_full_protection_pool_hash_rejects_truncation_and_missing_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool=Path(tmp)/'pool.jsonl';pool.write_bytes(b'first record\nsecond record\n')
            selection={'candidate_pool_sha256':p.sha_file(pool)}
            p.verify_paired_pool(selection,pool)
            pool.write_bytes(b'first record\n')
            with self.assertRaisesRegex(ValueError,'complete selected-cohort hash'):p.verify_paired_pool(selection,pool)
            with self.assertRaises(ValueError):p.verify_paired_pool({},pool)
    def test_full_freeze_file_map_rejects_changed_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);script=root/'script.py';script.write_text('original source')
            frozen={'script.py':p.sha_file(script)}
            p.verify_frozen_files(root,frozen)
            script.write_text('changed source')
            with self.assertRaisesRegex(ValueError,'file changed'):p.verify_frozen_files(root,frozen)
            with self.assertRaises(ValueError):p.verify_frozen_files(root,{})

    def test_shared_audit_import_resolves_normal_neighbor_module(self):
        import leakage_audit
        self.assertEqual(Path(leakage_audit.__file__).resolve().parent,Path(p.__file__).resolve().parent)
        self.assertTrue(callable(leakage_audit.audit_records))

    def test_empty_omission_manifest_preserves_source_account_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,manifest=p.write_snapshot(Path(tmp),'arm-empty',[],account_alias='original-account-alias')
            self.assertEqual(json.loads(manifest.read_bytes())['account_id'],'original-account-alias')


if __name__=='__main__':unittest.main(verbosity=2)
