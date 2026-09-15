"""Synthetic-only checks for the independent frozen-binding reviewer."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_preparation_bindings_v2 import bindings, lines, sha, stratum_summary, nested_binding_count


def strata():
    return [
        {'stratum_id':'stratum-02','communities':['AskPhysics','Physics'],
         'block_cap':1,'accounts':['a','b'],'cut':'2017-11-01T00:00:00Z'},
        {'stratum_id':'stratum-04','communities':['linux','linuxquestions'],
         'block_cap':2,'accounts':['c','d','e'],'cut':'2015-03-01T00:00:00Z'},
        {'stratum_id':'stratum-05','communities':['programming','learnprogramming'],
         'block_cap':2,'accounts':[],'cut':'2012-03-01T00:00:00Z'},
    ]


class BindingChecks(unittest.TestCase):
    def test_nested_evidence_need_not_be_redundantly_listed(self):
        self.assertEqual(nested_binding_count({'a':'hash-a'}, {'a':'hash-a','b':'hash-b'}),1)
        with self.assertRaisesRegex(ValueError, 'nested_binding_hash_disagrees'):
            nested_binding_count({'a':'hash-a'}, {'a':'changed'})

    def test_actual_hash_not_supplied_assertion_and_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'input';path.write_bytes(b'fixed\n')
            row={'path':str(path),'sha256':sha(path)}
            self.assertEqual(bindings([row]),{str(path):row['sha256']})
            with self.assertRaisesRegex(ValueError,'duplicate_binding'):bindings([row,row])
            path.write_bytes(b'changed\n')
            with self.assertRaisesRegex(ValueError,'bound_file_hash_changed'):bindings([row])

    def test_lines_counts_unterminated_tail_and_chunk_boundary(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'rows'
            for raw,expected in [(b'',0),(b'a',1),(b'a\nb\n',2),
                                 (b'x'*(1024*1024)+b'\ny',2)]:
                path.write_bytes(raw);self.assertEqual(lines(path),expected)

    def test_deficit_and_odd_reserve_pool_are_preserved(self):
        public,accounts=stratum_summary(strata())
        self.assertEqual([r['candidate_accounts'] for r in public],[2,3,0])
        self.assertEqual(accounts,set('abcde'))
        self.assertTrue(all('accounts' not in row for row in public))

    def test_shared_identity_singleton_changed_cap_and_non_utc_fail(self):
        variants=[]
        shared=strata();shared[1]['accounts'][0]='a';variants.append(shared)
        single=strata();single[1]['accounts']=['c'];variants.append(single)
        cap=strata();cap[0]['block_cap']=2;variants.append(cap)
        timezone=strata();timezone[0]['cut']='2017-11-01T00:00:00-04:00';variants.append(timezone)
        for rows in variants:
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):stratum_summary(rows)


if __name__=='__main__':unittest.main()
