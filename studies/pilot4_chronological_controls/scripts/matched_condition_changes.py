"""Descriptive within-anchor changes; missing outcomes never become zeros."""
from fractions import Fraction
from chronology_math import aggregate_cases


def mean(values):
    return float(sum((Fraction(v) for v in values),Fraction())/len(values)) if values else None


def matched_changes(rows):
    aggregate_cases(rows)  # Require every exact factorial descriptor, including failures.
    by_key={(r['block_id'],r['anchor_id'],r['condition']):r['score'] for r in rows}
    blocks=sorted({r['block_id'] for r in rows})
    pairs=[
        ('switch_occurrence_same_community','switch_same_community','continuity_same_community',None),
        ('switch_occurrence_changed_community','switch_changed_community','continuity_changed_community',None),
        ('community_change_occurrence_continuity','continuity_changed_community','continuity_same_community',None),
        ('community_change_occurrence_switch','switch_changed_community','switch_same_community',None),
        ('community_change_switch_localization','switch_changed_community','switch_same_community','switch_localization'),
        ('community_change_control_junction_alignment','continuity_changed_community','continuity_same_community','control_junction_diagnostic'),
    ]
    contrasts=[]
    for name,left,right,field in pairs:
        block_rows=[]
        for block in blocks:
            anchors=[]
            for anchor in ('AX','AY','BX','BY'):
                values=[]
                for condition in (left,right):
                    score=by_key[block,anchor,condition]
                    values.append(score[field]['matched_within_tolerance'] if field else score['candidate_occurrence'])
                value=int(values[0])-int(values[1]) if all(v is not None for v in values) else None
                anchors.append({'anchor_id':anchor,'left_value':values[0],'right_value':values[1],'difference':value})
            available=[a['difference'] for a in anchors if a['difference'] is not None]
            block_rows.append({'block_id':block,'anchors':anchors,'common_available_anchors':len(available),
                               'available_anchor_mean':mean(available),
                               'complete_block_mean':mean(available) if len(available)==4 else None})
        contrasts.append({'contrast':name,'direction':left+' minus '+right,'planned_blocks':len(blocks),
            'planned_anchors':4*len(blocks),'common_available_anchors':sum(b['common_available_anchors'] for b in block_rows),
            'complete_blocks':sum(b['complete_block_mean'] is not None for b in block_rows),
            'complete_block_equal_mean':mean([b['complete_block_mean'] for b in block_rows if b['complete_block_mean'] is not None]),
            'available_block_equal_mean':mean([b['available_anchor_mean'] for b in block_rows if b['available_anchor_mean'] is not None]),
            'blocks':block_rows})
    interaction=[]
    for block in blocks:
        anchors=[]
        for anchor in ('AX','AY','BX','BY'):
            values=[by_key[block,anchor,c]['candidate_occurrence'] for c in (
                'switch_changed_community','continuity_changed_community','switch_same_community','continuity_same_community')]
            anchors.append({'anchor_id':anchor,'difference_in_differences':
                            int(values[0])-int(values[1])-int(values[2])+int(values[3])
                            if all(v is not None for v in values) else None})
        available=[a['difference_in_differences'] for a in anchors if a['difference_in_differences'] is not None]
        interaction.append({'block_id':block,'anchors':anchors,'common_available_anchors':len(available),
                            'complete_block_mean':mean(available) if len(available)==4 else None,
                            'available_anchor_mean':mean(available)})
    return {'interpretation':'Descriptive paired changes on common observed outcomes; source-account proxies and sampled histories, not causal effects.',
            'contrasts':contrasts,'occurrence_interaction':{'direction':'(switch minus continuity) with community change minus without community change',
            'blocks':interaction,'planned_anchors':4*len(blocks),
            'common_available_anchors':sum(b['common_available_anchors'] for b in interaction),
            'complete_blocks':sum(b['complete_block_mean'] is not None for b in interaction),
            'complete_block_equal_mean':mean([b['complete_block_mean'] for b in interaction if b['complete_block_mean'] is not None])}}
