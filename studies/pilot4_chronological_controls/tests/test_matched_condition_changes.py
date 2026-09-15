import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from chronology_math import factorial_cases,reconstruct_windows,score_case
from matched_condition_changes import matched_changes


def make_rows():
    windows=reconstruct_windows([{'retained_words':125,'style_eligible':True} for _ in range(64)])
    rows=[]
    for descriptor in factorial_cases('synthetic-block'):
        occurrence=descriptor['source_switch'] or descriptor['community_change']
        result=score_case(candidate_intervals=[[32,32]] if occurrence else [],status='ok',reason_codes=[],
            truth_k=32 if descriptor['source_switch'] else None,
            control_junction_k=None if descriptor['source_switch'] else 32,
            windows=windows,record_timestamps=[None]*64)
        rows.append({**descriptor,'score':result})
    return rows


class MatchedChangesTests(unittest.TestCase):
    def test_known_parallel_contrasts_and_interaction(self):
        result=matched_changes(make_rows());values={r['contrast']:r['complete_block_equal_mean'] for r in result['contrasts']}
        self.assertEqual(values['switch_occurrence_same_community'],1)
        self.assertEqual(values['switch_occurrence_changed_community'],0)
        self.assertEqual(values['community_change_occurrence_continuity'],1)
        self.assertEqual(values['community_change_occurrence_switch'],0)
        self.assertEqual(values['community_change_switch_localization'],0)
        self.assertEqual(result['occurrence_interaction']['complete_block_equal_mean'],-1)

    def test_one_abstention_keeps_planned_denominator_and_paired_intersection(self):
        rows=make_rows();target=rows[0]['score']
        target['executed']=False;target['status']='abstained';target['candidate_count']=None;target['candidate_occurrence']=None
        target['control_junction_diagnostic']['matched_within_tolerance']=None
        result=matched_changes(rows);contrast=result['contrasts'][0]
        self.assertEqual(contrast['planned_anchors'],4)
        self.assertEqual(contrast['common_available_anchors'],3)
        self.assertEqual(contrast['complete_blocks'],0)
        self.assertIsNone(contrast['complete_block_equal_mean'])
        self.assertEqual(contrast['available_block_equal_mean'],1)
        self.assertEqual(result['occurrence_interaction']['common_available_anchors'],3)

    def test_missing_case_is_not_a_reduced_denominator(self):
        with self.assertRaises(ValueError):matched_changes(make_rows()[:-1])


if __name__=='__main__':unittest.main()
