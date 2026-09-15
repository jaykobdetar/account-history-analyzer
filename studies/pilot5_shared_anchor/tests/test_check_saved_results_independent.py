from datetime import datetime,timedelta,timezone
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_saved_results_independent import error,localization,bracket,reconstruct,grid,native,FP,CONFIG


def result(status='ok',intervals=()):
    return {'analysis':{'implementation_fingerprint':FP,'config_sha256':CONFIG},'modules':{'style':{'payload':{
        'streams':[{'scope_type':'pooled','kind':'comment','subreddit':None,'stream_id':'p','window_ids':[]}],
        'changes':[{'stream_id':'p','status':status,'reason_codes':[],
                    'boundaries':[{'record_interval':v} for v in intervals]}]}}}}


class IndependentArithmetic(unittest.TestCase):
    def setUp(self):self.times=[datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(days=i) for i in range(100)]

    def test_ten_inclusive_eleven_outside_and_exact(self):
        self.assertEqual(error([30,32],42),10)
        self.assertTrue(localization([[30,32]],42,4,self.times)['matched_within_tolerance'])
        self.assertFalse(localization([[30,31]],42,4,self.times)['matched_within_tolerance'])
        self.assertTrue(localization([[40,43]],42,0,self.times)['exact_interval_containment'])

    def test_native_coordinates_convert_exactly_once(self):
        extracted=native(result(intervals=[[37,38]]),0)
        self.assertEqual(extracted['intervals'],[[38,38]])
        self.assertEqual(error(extracted['intervals'][0],42),4)

    def test_zero_candidates_distinct_from_unavailable(self):
        self.assertEqual(native(result('no_measurable_variation'),0)['intervals'],[])
        self.assertIsNone(native(result(intervals=[[37,38]]),4)['intervals'])
        self.assertEqual(native(None,4)['status'],'resource_limit')
        zero=localization([],42,4,self.times);absent=localization(None,42,4,self.times)
        self.assertFalse(zero['matched_within_tolerance']);self.assertIsNone(absent['matched_within_tolerance'])
        self.assertIsNone(zero['nearest_interval_error_records']);self.assertIsNone(absent['unmatched_candidate_count'])

    def test_nearest_tie_is_earlier_and_time_bracket_is_bounding_records(self):
        chosen=localization([[46,46],[38,38]],42,4,self.times)
        self.assertEqual(chosen['nearest_interval']['split_interval'],[38,38])
        self.assertEqual(chosen['excess_error_over_best_grid_records'],0)
        self.assertEqual(chosen['unmatched_candidate_count'],1)
        b=bracket([38,38],self.times)
        self.assertEqual((b['left_record_position'],b['right_record_position']),(37,38))
        self.assertEqual(b['elapsed_seconds'],86400)

    def test_seven_vs_eight_windows_and_original_ordinal_gap(self):
        rows=[{'style_eligible':True,'kind':'comment','retained_words':125} for _ in range(64)]
        self.assertEqual(grid(reconstruct(rows[:56])),[])
        self.assertEqual([g['split_interval'] for g in grid(reconstruct(rows))],[[24,24],[32,32],[40,40]])
        rows.insert(24,{'style_eligible':False,'kind':'comment','retained_words':10})
        self.assertEqual(grid(reconstruct(rows))[0]['split_interval'],[24,25])


if __name__=='__main__':unittest.main()
