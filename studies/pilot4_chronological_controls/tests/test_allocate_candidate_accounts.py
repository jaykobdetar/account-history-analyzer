from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from allocate_candidate_accounts import joint_witness,allocate

DESIGN={'all_eight_cell_word_ratio_max':'11/10','all_eight_cell_record_ratio_max':'5/4',
        'within_period_four_cell_median_span_days_max':30,'half_band_days':180,
        'half_target_words':5000,'half_min_records':40}


def stratum(accounts):
    return {'candidate_cells':{account:{c+'/'+p:{'records':40,'retained_words':5000,
           'median_timestamp':0 if p=='early' else 86400}
           for c in ('X','Y') for p in ('early','late')} for account in accounts}}


class JointWitnessTests(unittest.TestCase):
    def test_reserves_other_stratum_accounts_with_backtracking(self):
        graphs={'02':[('a','b')],'04':[('c','d'),('e','f'),('g','h')],'05':[('c','d'),('i','j')]}
        result=joint_witness(graphs,{'02':1,'04':2,'05':2})
        self.assertEqual(result['04'],[('e','f'),('g','h')])
        self.assertEqual(len({a for pairs in result.values() for pair in pairs for a in pair}),10)

    def test_reports_unattainable_full_quota(self):
        self.assertIsNone(joint_witness({'04':[('a','b')],'05':[('a','c')]},{'04':1,'05':1}))

    def test_keeps_zero_quota_stratum_explicit(self):
        self.assertEqual(joint_witness({'04':[],'05':[('a','b')]},{'04':0,'05':1}),{'04':[],'05':[('a','b')]})

    def test_full_allocation_preserves_reserved_accounts_and_is_order_invariant(self):
        source={'stratum-02':stratum(['p1','p2']),
                'stratum-04':stratum(['linux'+str(i) for i in range(16)]+['shared1','shared2']),
                'stratum-05':stratum(['program'+str(i) for i in range(16)]+['shared1','shared2'])}
        first=allocate(source,DESIGN)
        for row in source.values():row['candidate_cells']=dict(reversed(list(row['candidate_cells'].items())))
        self.assertEqual(first,allocate(dict(reversed(list(source.items()))),DESIGN))
        accounts=[a for values in first['assigned'].values() for a in values]
        self.assertEqual(len(accounts),26);self.assertEqual(len(set(accounts)),26)
        self.assertEqual(first['attainable_reserved_block_counts'],{'stratum-02':1,'stratum-04':2,'stratum-05':2})
        for name,reserved in first['reserved_witness_accounts'].items():
            self.assertTrue(set(reserved)<=set(first['assigned'][name]))

    def test_empty_technical_stratum_retains_explicit_target_deficit(self):
        result=allocate({'stratum-02':stratum(['p1','p2']),'stratum-04':stratum([]),
                         'stratum-05':stratum(['x1','x2'])},DESIGN)
        self.assertEqual(result['registered_target_deficits'],{'stratum-02':0,'stratum-04':2,'stratum-05':1})
        self.assertEqual(result['assigned']['stratum-04'],[])


if __name__=='__main__':unittest.main()
