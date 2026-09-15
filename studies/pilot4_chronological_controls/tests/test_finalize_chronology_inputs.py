"""Independent synthetic construction/audit-binding/matching integration checks."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from finalize_chronology_inputs import bind_audit, capped_matching, finalize, original_comment_record
from metadata_feasibility import identity_order, seconds
from run_full_chronology import sha
from test_prepare_chronology_pool import SyntheticPool, put


def fake_audit(fixture, *, purge_account=None, purge_threads=False):
    """Fabricated complete graph metadata, never a content-engine invocation."""
    entries = {row['record']['id']:row for row in
               (json.loads(line) for line in (fixture.pool/'candidate-pool.jsonl').read_text().splitlines())}
    provenance = {rid:{'source_record_id':rid,'source_kind':'comment','text_component':'body',
        'historical':False,'account_key':row['account_key'],'stratum_id':row['stratum_id'],
        'cell':[row['account_key'],row['community'],row['period']],
        'thread_id':row['record']['thread_id'],'declared_retained_words':row['retained_words']}
        for rid,row in entries.items()}
    purged = sorted(rid for rid,row in entries.items() if row['account_key'] == purge_account
                    or (purge_threads and row['record']['thread_id']=='shared-thread'))
    components = [{'record_ids':[rid]} for rid in entries if purge_threads or rid not in set(purged)]
    if purged and not purge_threads:
        provenance['synthetic-historical'] = {'historical':True,'thread_id':'old-thread',
                                            'account_key':'old-account','text_component':'body'}
        components.append({'record_ids':purged+['synthetic-historical']})
    summary = {'status':'audited','scores_computed':False,'gate_b_ready':True,
        'available_content_and_grouping_audit_complete':True,
        'independence_scope_complete':True,'unknown_scope_flags':[],
        'candidate_records':len(entries),
        'candidate_retained_words':sum(row['retained_words'] for row in entries.values()),
        'purged_candidate_records':len(purged),'surviving_candidate_records':len(entries)-len(purged)}
    audit = {'actionable':True,'summary':summary,'record_provenance':provenance,
             'purge_record_ids':purged,'surviving_candidate_ids':sorted(set(entries)-set(purged)),
             'purge_reasons':{rid:['content_component_historical_boundary'] for rid in purged},
             'engine_audit':{'status':'audited','components':components}}
    audit_path = fixture.root/'audit.json'
    freeze_path = fixture.root/'audit-freeze.json'
    public_path = fixture.root/'audit-public.json'
    freeze = {'state':'frozen_before_audit',
        'candidate_pool_sha256':sha(fixture.pool/'candidate-pool.jsonl'),
        'historical_inventory_sha256':sha(fixture.plan['historical_inventory']),
        'engine_sha256':sha(fixture.plan['audit_engine']),
        'wrapper_sha256':sha(fixture.plan['audit_wrapper']),
        'rules_sha256':sha(fixture.plan['audit_rules'])}
    put(audit_path,audit);put(freeze_path,freeze)
    public = {**summary,'private_audit_sha256':sha(audit_path),'freeze_sha256':sha(freeze_path),
              **{key:freeze[key] for key in ('engine_sha256','wrapper_sha256','rules_sha256')}}
    put(public_path,public)
    return audit_path,freeze_path,public_path


def rebind_audit(audit_path,freeze_path,public_path):
    audit = json.loads(audit_path.read_bytes())
    public = json.loads(public_path.read_bytes())
    public.update(audit['summary'],private_audit_sha256=sha(audit_path),freeze_sha256=sha(freeze_path))
    put(public_path,public)


class CappedMatching(unittest.TestCase):
    def test_cardinality_precedes_cost_but_cap_one_stops_at_one(self):
        nodes=['a','b','c','d']
        edges={('a','b'):Fraction(0),('a','c'):Fraction(5),('b','d'):Fraction(5)}
        pairs,cost=capped_matching(nodes,edges,2)
        self.assertEqual({frozenset(pair) for pair in pairs},{frozenset(('a','c')),frozenset(('b','d'))})
        self.assertEqual(cost,10)
        pairs,cost=capped_matching(nodes,edges,1)
        self.assertEqual({frozenset(pair) for pair in pairs},{frozenset(('a','b'))})
        self.assertEqual(cost,0)

    def test_exact_fraction_costs_and_hash_ties_ignore_input_order(self):
        ordered=sorted(['a','b','c','d','e','f'],key=identity_order)
        a,b,c,d,e,f=ordered
        pairs,cost=capped_matching(list(reversed(ordered)),{(a,b):Fraction(2**60+1,2**60),(c,d):Fraction(1)},1)
        self.assertEqual(pairs,[(c,d)])
        edges={(x,y):Fraction(1) for i,x in enumerate(ordered) for y in ordered[i+1:]}
        pairs,cost=capped_matching(list(reversed(ordered)),dict(reversed(list(edges.items()))),2)
        self.assertEqual(pairs,[(a,b),(c,d)])
        self.assertEqual(cost,2)

    def test_invalid_graphs_and_empty_capacity(self):
        self.assertEqual(capped_matching(['a','b'],{},2),([],Fraction()))
        for nodes,edges,cap in [(['a','a'],{},1),(['a','b'],{('a','a'):0},1),
                               (['a','b'],{('a','b'):0,('b','a'):0},1),
                               (['a','b'],{('a','b'):0.1},1),(['a','b'],{},True)]:
            with self.subTest(nodes=nodes,edges=edges,cap=cap),self.assertRaises(ValueError):
                capped_matching(nodes,edges,cap)


class AuditBindings(unittest.TestCase):
    def test_independent_original_projection_rejects_submission_kind(self):
        with self.assertRaisesRegex(ValueError,'submission'):
            original_comment_record({'id':'same-bare-id','root':'same-bare-id'})

    def test_cross_cell_threads_require_all_affected_candidates_purged(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture=SyntheticPool(temp,shared_threads=True)
            paths=fake_audit(fixture)
            with self.assertRaisesRegex(ValueError,'purge graph'):
                bind_audit(fixture.plan,fixture.plan_path,fixture.pool/'candidate-pool.jsonl',*paths)
            paths=fake_audit(fixture,purge_threads=True)
            entries,survivors,audit=bind_audit(fixture.plan,fixture.plan_path,fixture.pool/'candidate-pool.jsonl',*paths)
            self.assertEqual(len(entries)-len(survivors),12)
            self.assertEqual(set(entries)-survivors,set(audit['purge_record_ids']))

    def test_complete_pool_receipts_provenance_and_original_bytes_bind(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture=SyntheticPool(temp)
            paths=fake_audit(fixture)
            entries,survivors,audit=bind_audit(fixture.plan,fixture.plan_path,fixture.pool/'candidate-pool.jsonl',*paths)
            self.assertEqual(len(entries),2560)
            self.assertEqual(survivors,set(entries))
            self.assertTrue(audit['actionable'])

    def test_actionable_flag_alone_insufficient_and_hash_chain_checked(self):
        for change in ('gate','public_hash','freeze_pool','provenance','partition','false_purge'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temp:
                fixture=SyntheticPool(temp)
                audit_path,freeze_path,public_path=fake_audit(fixture)
                audit=json.loads(audit_path.read_bytes())
                first=audit['surviving_candidate_ids'][0]
                if change=='gate':audit['summary']['gate_b_ready']=False
                elif change=='provenance':audit['record_provenance'][first]['declared_retained_words']=126
                elif change=='partition':audit['surviving_candidate_ids'].remove(first)
                elif change=='false_purge':
                    audit['surviving_candidate_ids'].remove(first)
                    audit['purge_record_ids']=[first]
                    audit['purge_reasons']={first:['invented']}
                    audit['summary']['purged_candidate_records']=1
                    audit['summary']['surviving_candidate_records']-=1
                elif change=='freeze_pool':
                    freeze=json.loads(freeze_path.read_bytes());freeze['candidate_pool_sha256']='wrong';put(freeze_path,freeze)
                put(audit_path,audit)
                rebind_audit(audit_path,freeze_path,public_path)
                if change=='public_hash':
                    public=json.loads(public_path.read_bytes());public['private_audit_sha256']='wrong';put(public_path,public)
                with self.assertRaises(ValueError):
                    bind_audit(fixture.plan,fixture.plan_path,fixture.pool/'candidate-pool.jsonl',audit_path,freeze_path,public_path)

    def test_pool_text_tampering_rejected_even_after_rebinding_pool_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture=SyntheticPool(temp)
            pool_path=fixture.pool/'candidate-pool.jsonl'
            entries=[json.loads(line) for line in pool_path.read_text().splitlines()]
            entries[0]['record']['text']='altered whole comment'
            pool_path.write_text(''.join(json.dumps(row)+'\n' for row in entries))
            preparation=json.loads((fixture.pool/'preparation.json').read_bytes())
            preparation['candidate_pool_sha256']=sha(pool_path)
            put(fixture.pool/'preparation.json',preparation)
            paths=fake_audit(fixture)
            with self.assertRaisesRegex(ValueError,'Whole original comment'):
                bind_audit(fixture.plan,fixture.plan_path,pool_path,*paths)


class FinalConstruction(unittest.TestCase):
    def run_final(self,fixture,paths):
        out,public=fixture.root/'final',fixture.root/'public'
        with patch.dict('os.environ',{'AHAS_NETWORK_ISOLATION':'linux_seccomp_socket_denial'}), \
             patch('finalize_chronology_inputs.resource.setrlimit'):
            finalize(fixture.plan_path,fixture.pool/'candidate-pool.jsonl',paths[0],out,public,
                     audit_freeze=paths[1],audit_public=paths[2])
        return out,public

    def test_five_blocks_eighty_full_factorial_histories_preserve_all_nonalias_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture=SyntheticPool(temp)
            out,public=self.run_final(fixture,fake_audit(fixture))
            index=json.loads((out/'index.json').read_bytes())
            cohort=json.loads((out/'cohort.json').read_bytes())
            summary=json.loads((public/'selection-summary.json').read_bytes())
            self.assertEqual((summary['blocks'],summary['accounts'],summary['planned_cases']),(5,10,80))
            self.assertEqual((summary['source_records'],summary['source_words']),(1600,200000))
            self.assertEqual(len(index['cases']),80)
            self.assertEqual(len({a for block in cohort['blocks'] for a in block['account_keys']}),10)
            pool={row['record']['id']:row['record'] for row in
                  (json.loads(line) for line in (fixture.pool/'candidate-pool.jsonl').read_text().splitlines())}
            for case in index['cases']:
                records=[json.loads(line) for line in Path(case['input']).read_text().splitlines()]
                meta=json.loads(Path(case['metadata']).read_bytes())['records']
                self.assertEqual(len(records),80)
                self.assertEqual([row['id'] for row in records],[row['record_id'] for row in meta])
                self.assertEqual({row['account_id'] for row in records},{case['case_id']})
                self.assertEqual(case['truth_k'],40 if case['source_switch'] else None)
                self.assertEqual(case['control_junction_k'],None if case['source_switch'] else 40)
                for number,record in enumerate(records):
                    self.assertEqual({k:v for k,v in record.items() if k!='account_id'},
                                     {k:v for k,v in pool[record['id']].items() if k!='account_id'})
                    self.assertEqual(record['text'].encode(),fixture.originals[record['id']]['text'].encode())
                    self.assertEqual(seconds(record['created_utc'])<fixture.cut,number<40)
                source_accounts=[pool[row['id']]['account_id'] for row in records]
                self.assertEqual(source_accounts[0]!=source_accounts[-1],case['source_switch'])
                self.assertEqual(records[0]['subreddit']!=records[-1]['subreddit'],case['community_change'])
                self.assertEqual(case['prescore_qualified_windows'],10)
            for binding in index['bound_files']:
                self.assertEqual(binding['sha256'],sha(binding['path']))
            cells=json.loads((public/'cells.json').read_bytes())
            self.assertTrue(all((row['records'],row['retained_words'],row['word_overshoot'])==(40,5000,0) for row in cells))
            self.assertTrue(all(row['largest_record_share']==0.025 for row in cells))
            self.assertNotIn('Ω', (public/'cells.json').read_text())

    def test_audit_deficit_preserved_without_replacement_or_relaxation(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture=SyntheticPool(temp)
            paths=fake_audit(fixture,purge_account='physics-a')
            out,public=self.run_final(fixture,paths)
            summary=json.loads((public/'selection-summary.json').read_bytes())
            self.assertEqual((summary['blocks'],summary['accounts'],summary['planned_cases']),(4,8,64))
            physics=next(row for row in summary['strata'] if row['stratum_id']=='physics')
            self.assertEqual((physics['selected_blocks'],physics['block_deficit']),(0,1))
            cohort=json.loads((out/'cohort.json').read_bytes())
            self.assertTrue(all('physics-a' not in block['account_keys'] for block in cohort['blocks']))
            self.assertEqual(sum(row['block_deficit'] for row in summary['strata']),1)

    def test_empty_technical_pool_remains_explicit_two_block_deficit(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture=SyntheticPool(temp,prepare_now=False)
            fixture.plan['strata'][1]['accounts']=[]
            put(fixture.plan_path,fixture.plan)
            fixture.prepare()
            out,public=self.run_final(fixture,fake_audit(fixture))
            summary=json.loads((public/'selection-summary.json').read_bytes())
            self.assertEqual((summary['blocks'],summary['accounts'],summary['planned_cases']),(3,6,48))
            linux=next(row for row in summary['strata'] if row['stratum_id']=='linux')
            self.assertEqual((linux['pool_accounts'],linux['selected_blocks'],linux['block_deficit']),(0,0,2))


if __name__=='__main__':
    unittest.main()
