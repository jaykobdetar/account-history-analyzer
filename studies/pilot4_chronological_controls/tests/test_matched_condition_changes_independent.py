"""Independent synthetic paired-coverage and block-weighting checks."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from chronology_math import factorial_cases,reconstruct_windows,score_case
from matched_condition_changes import matched_changes


def rows():
    windows=reconstruct_windows([{'retained_words':125,'style_eligible':True} for _ in range(64)])
    output=[]
    for block in ('complete','partial'):
        for descriptor in factorial_cases(block):
            missing=(block=='partial' and descriptor['condition']=='continuity_same_community' and descriptor['anchor_id']!='AX')
            occurs=(block=='complete' and descriptor['source_switch'])
            score=score_case(candidate_intervals=[[32,32]] if occurs else [],status='unavailable' if missing else 'ok',
                reason_codes=['synthetic_failure'] if missing else [],truth_k=32 if descriptor['source_switch'] else None,
                control_junction_k=None if descriptor['source_switch'] else 32,windows=windows,record_timestamps=[None]*64)
            output.append({**descriptor,'score':score})
    return output


def test_common_anchor_intersection_then_equal_block_weighting():
    result=matched_changes(rows());contrast=result['contrasts'][0]
    assert contrast['planned_anchors']==8 and contrast['common_available_anchors']==5
    assert contrast['complete_blocks']==1 and contrast['complete_block_equal_mean']==1
    # Available blocks get equal weight; five pooled anchors would instead give0.8.
    assert contrast['available_block_equal_mean']==.5
    assert sorted(b['common_available_anchors'] for b in contrast['blocks'])==[1,4]


def test_all_four_conditions_required_for_interaction_and_all_missing_stays_null():
    result=matched_changes(rows())['occurrence_interaction']
    assert result['planned_anchors']==8 and result['common_available_anchors']==5 and result['complete_blocks']==1
    assert result['complete_block_equal_mean']==0
    data=rows()
    for row in data:
        row['score']['candidate_occurrence']=None
        row['score']['executed']=False
        for field in ('switch_localization','control_junction_diagnostic'):
            if row['score'][field] is not None:row['score'][field]['matched_within_tolerance']=None
    result=matched_changes(data)
    assert all(c['complete_block_equal_mean'] is None and c['available_block_equal_mean'] is None and c['common_available_anchors']==0 for c in result['contrasts'])
    assert result['occurrence_interaction']['complete_block_equal_mean'] is None
