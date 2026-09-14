"""Read-only actual prepared-input checks. No windows, distances or scoring."""
from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
import hashlib,json
from pathlib import Path
import unittest
import zipfile

from account_history_analyzer.io import canonical_digest
from account_history_analyzer.schemas import validate

ROOT=Path(__file__).resolve().parents[1]
PREP=ROOT/'prepared/streams'


def sha_file(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while block:=f.read(65536):h.update(block)
    return h.hexdigest()


def rows(path):
    with path.open() as f:return [json.loads(line) for line in f if line.strip()]


class PreparedChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=json.loads((PREP/'stream-plan.json').read_bytes())
        cls.protocol=json.loads((ROOT/'protocol/plan.json').read_bytes())
        cls.selection=json.loads((PREP/'private/selected-accounts.json').read_bytes())
        cls.paired=json.loads((ROOT/'prepared/paired/private/selection.json').read_bytes())
        cls.accounts={a['account_alias']:a for a in cls.selection['accepted']}
        cls.by_alias={alias:rows(PREP/'accounts'/(alias+'.jsonl')) for alias in cls.accounts}
        cls.group=json.loads((PREP/'group-audit.json').read_bytes())
        cls.joint=json.loads((PREP/'private/joint-related-audit.json').read_bytes())
    def test_complete_pool_and_all_prepared_hash_bindings(self):
        pool=ROOT/'prepared/paired/private/candidate-pool.jsonl'
        self.assertEqual(sha_file(pool),self.paired['candidate_pool_sha256'])
        self.assertEqual(self.plan['paired_pool_sha256'],self.paired['candidate_pool_sha256'])
        self.assertEqual(self.group['paired_pool_sha256'],self.paired['candidate_pool_sha256'])
        for relative,expected in self.plan['inputs_sha256'].items():self.assertEqual(sha_file(PREP/relative),expected)
        self.assertEqual(sha_file(PREP/'group-audit.json'),self.plan['group_audit_sha256'])
        self.assertFalse(self.plan['scoring_executed'])
        self.assertEqual(len(self.plan['cases']),51)
        self.assertEqual(len(self.plan['operational_availability_views']),9)
    def test_author_confirmation_components_and_slots(self):
        accepted={a['account_key'] for a in self.selection['accepted']}
        self.assertFalse(accepted & {a['account_key'] for a in self.paired['accounts']})
        final_ids={r['id'] for records in self.by_alias.values() for r in records}
        for component in self.joint['components']:
            if 'confirmation' in component['split_memberships']:self.assertFalse(final_ids & set(component['record_ids']))
        for slot in self.plan['unfilled_slots']:
            self.assertEqual(slot['selected_authors']+slot['unfilled_author_slots'],slot['planned_authors'])
            home=slot['home_community']
            self.assertEqual(sum(p['home_community']==home for p in self.plan['pairings']),slot['formed_pairs'])
        all_authors=[a for pair in self.plan['pairings'] for a in pair['source_account_aliases']]
        self.assertEqual(len(all_authors),len(set(all_authors)))
    def test_all_arms_survive_unchanged_and_truth_is_not_fabricated(self):
        by_case={c['case_id']:c for c in self.plan['cases']}
        for case in self.plan['cases']:
            if case['execution_mode'] is None:
                self.assertIsNone(case['truth_boundaries']);continue
            supplied=rows(PREP/case['input'])
            for r in supplied:validate(r,'record')
            validate(json.loads((PREP/case['manifest']).read_bytes()),'snapshot')
            if case['case_type']=='unknown_truth_natural':
                self.assertIsNone(case['truth_boundaries']);continue
            base=rows(PREP/by_case[case['pair_id']+'-'+case['case_type']+'-full']['input'])
            n=len(base)
            if case['arm']=='full':expected=base
            elif case['arm']=='hash50':expected=[r for r in base if int(hashlib.sha256(('ahas-pilot2-omission-v1:'+r['id']).encode()).hexdigest(),16)%2==0]
            elif case['arm']=='middle50':expected=base[:n//4]+base[3*n//4:]
            else:expected=[r for r in base if r['subreddit']!='Cornell']
            self.assertEqual(canonical_digest(supplied),canonical_digest(expected))
            mapping=json.loads((PREP/'private'/(case['case_id']+'.ordinal-map.json')).read_bytes())
            self.assertEqual(len(mapping),len(supplied))
            self.assertTrue(all(m['record_id']==r['id'] and m['surviving_ordinal']==i and base[m['full_original_ordinal']]==r for i,(m,r) in enumerate(zip(mapping,supplied))))
            if case['case_type']=='splice':
                sides=[m['source_side'] for m in mapping]
                if 'left' not in sides or 'right' not in sides:
                    self.assertIsNone(case['truth_boundaries']);self.assertEqual(case['execution_mode'],'analyze_unknown_truth')
                else:
                    cut=sides.index('right');self.assertEqual(case['truth_boundaries'],[cut])
                    self.assertEqual(sides,['left']*cut+['right']*(len(sides)-cut))
            else:self.assertEqual(case['truth_boundaries'],[])
            if case['dataset']:validate(json.loads((PREP/case['dataset']).read_bytes()),'evaluation_account_stream')
        for view in self.plan['operational_availability_views']:
            self.assertEqual(view['scientific_sample_count_increment'],0)
            self.assertIsNone(view['truth_boundaries'])
            if view['execution_mode']:
                source=by_case[view['shared_input_with_case']]
                self.assertEqual((view['input'],view['manifest']),(source['input'],source['manifest']))
    def test_splices_use_fixed_actual_union_median_and_complete_halves(self):
        by_case={c['case_id']:c for c in self.plan['cases']}
        for pair in self.plan['pairings']:
            aa,bb=[self.by_alias[a] for a in pair['source_account_aliases']]
            case=by_case[pair['pair_id']+'-splice-full']
            times=sorted(r['created_utc'] for r in aa+bb if r['created_utc'] is not None)
            if len(times)!=len(aa)+len(bb):
                self.assertEqual(case['preparation_status'],'not_constructible');continue
            cut=times[len(times)//2]
            before=[r for r in aa if r['created_utc']<cut];after=[r for r in bb if r['created_utc']>=cut]
            if not before or not after:
                self.assertEqual(case['preparation_status'],'not_constructible');continue
            self.assertEqual(case['cut_utc'],cut)
            expected=sorted(before+after,key=lambda r:(r['created_utc'],r['id']))
            actual=rows(PREP/case['input'])
            # Exactly the intentional constructed account-metadata reassignment.
            for record in expected:record=dict(record)
            self.assertEqual(canonical_digest([{k:v for k,v in r.items() if k!='account_id'} for r in actual]),
                             canonical_digest([{k:v for k,v in r.items() if k!='account_id'} for r in expected]))
    def test_complete_available_source_histories_preserve_text_ids_times_status(self):
        wanted={a['account_key']:a['account_alias'] for a in self.selection['accepted']}
        originals=defaultdict(dict);mismatch_count=0;occurrences=0
        for source,spec in self.protocol['source_archives'].items():
            with zipfile.ZipFile(ROOT/spec['path']) as z:
                with z.open('utterances.jsonl') as f:
                    for line in f:
                        row=json.loads(line);author=row.get('user')
                        if not isinstance(author,str) or author.casefold() not in wanted or row.get('root')==row.get('id'):continue
                        alias=wanted[author.casefold()];identifier=row['id'];occurrences+=1
                        text=row.get('text')
                        status='unavailable' if text is None else 'removed' if text.strip()=='[removed]' else 'deleted' if text.strip()=='[deleted]' else 'present'
                        utc=(datetime(1970,1,1,tzinfo=timezone.utc)+timedelta(seconds=row['timestamp'])).isoformat(timespec='seconds').replace('+00:00','Z') if row.get('timestamp') is not None else None
                        observed={'id':identifier,'text':text if status=='present' else None,'status':status,'created_utc':utc,
                                  'subreddit':(row.get('meta') or {}).get('subreddit'),'parent_id':row.get('reply_to'),'thread_id':row.get('root'),
                                  'permalink':(row.get('meta') or {}).get('permalink')}
                        if identifier in originals[alias]:self.assertEqual(canonical_digest(originals[alias][identifier]),canonical_digest(observed))
                        originals[alias][identifier]=observed
        total=0
        for alias,records in self.by_alias.items():
            self.assertEqual(len(records),len(originals[alias]));total+=len(records)
            for record in records:
                expected=originals[alias].get(record['id'])
                self.assertIsNotNone(expected)
                if canonical_digest(expected)!=canonical_digest({k:record[k] for k in expected}):mismatch_count+=1
        self.assertEqual(mismatch_count,0)
        self.assertGreaterEqual(occurrences,total)

if __name__=='__main__':unittest.main(verbosity=2)
