from copy import deepcopy
from datetime import datetime,timezone,timedelta
from fractions import Fraction
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_shared_anchor import evaluate,identity,KEYS


def fixtures():
    entries={};samples={}
    for offset,key in enumerate(KEYS):
        rows=[]
        for i in range(40):
            rid=key+str(i);stamp=datetime(2012 if offset else 2010,1,1,tzinfo=timezone.utc)+timedelta(seconds=i)
            entries[rid]={'record':{'created_utc':stamp.isoformat()}}
            rows.append({'record_id':rid,'retained_words':125})
        samples[key]={'rows':rows,'records':40,'retained_words':5000,'median_timestamp':Fraction(offset*86400)}
    return samples,entries


class PreparationTests(unittest.TestCase):
    def test_anchor_time_absent_from_late_alignment_and_cost(self):
        s,e=fixtures();first=evaluate(s,e);s['anchor']['median_timestamp']=-10**12
        self.assertEqual(first,evaluate(s,e));self.assertTrue(first['valid'])
        self.assertEqual(first['cost'],Fraction(10,180))
        self.assertEqual(first['qualified_window_counts'],[10]*4)

    def test_all_five_volume_pairs_contribute(self):
        s,e=fixtures();base=evaluate(s,e)['cost'];s['anchor']['records']=44;s['anchor']['retained_words']=5100
        self.assertEqual(evaluate(s,e)['cost']-base,4*(Fraction(4,40)+Fraction(100,5000)))

    def test_missing_unused_reciprocal_early_cell_cannot_enter(self):
        s,e=fixtures();self.assertTrue(evaluate(s,e)['valid'])
        s['late_BY']=None;self.assertEqual(evaluate(s,e)['reason_codes'],['unavailable_sample:late_BY'])

    def test_date_boundary_inclusive_and_volume_boundaries(self):
        s,e=fixtures()
        for k in KEYS[1:]:s[k]['median_timestamp']=0
        s['late_BY']['median_timestamp']=30*86400
        self.assertTrue(evaluate(s,e)['valid'])
        s['late_BY']['median_timestamp']+=1
        self.assertIn('four_late_median_span_above_30_days',evaluate(s,e)['reason_codes'])

    def test_identity_is_casefolded_and_delimited(self):
        self.assertEqual(identity('Mixed'),identity('mixed'))
        self.assertNotEqual(identity('ab'),identity('a'))


if __name__=='__main__':unittest.main()
