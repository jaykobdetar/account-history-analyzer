"""Independent synthetic-only feasibility oracles; no real metadata access.

The small graph oracle enumerates unrestricted matchings, including unmatched
vertices, to check cardinality before exact rational cost. Adapter tests are
added once the production-independent feasibility API is fixed.
"""
from fractions import Fraction
from itertools import combinations
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import random
from pathlib import Path

import pytest


# Import this exact pilot4 file without depending on another study's sys.path.
SOURCE = Path(__file__).resolve().parents[1]/'scripts/metadata_feasibility.py'
SPEC = importlib.util.spec_from_file_location('pilot4_feasibility_independent_target',SOURCE)
feasibility = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(feasibility)
DAY=86400
PLAN={'half_band_days':180,'record_word_min':20,'record_word_max':500,
      'half_target_words':5000,'half_min_records':40,'half_max_words':5500,'half_max_records':200,
      'all_eight_cell_word_ratio_max':'11/10','all_eight_cell_record_ratio_max':'5/4',
      'within_period_four_cell_median_span_days_max':30}


def exhaustive_matching(vertices, edges):
    """Return the full optimal objective and canonical edge witness for <=8 nodes."""
    vertices = tuple(sorted(vertices))
    assert len(vertices) <= 8
    costs = {tuple(sorted(edge)): Fraction(cost) for edge,cost in edges.items()}

    def enumerate_matchings(remaining):
        if not remaining:
            yield ()
            return
        first, rest = remaining[0], remaining[1:]
        yield from enumerate_matchings(rest)
        for second in rest:
            pair = tuple(sorted((first,second)))
            if pair in costs:
                after = tuple(v for v in rest if v != second)
                for matching in enumerate_matchings(after):
                    yield tuple(sorted((pair,)+matching))

    candidates = ((-len(pairs),sum((costs[p] for p in pairs),Fraction(0)),pairs)
                  for pairs in enumerate_matchings(vertices))
    return min(candidates)


def independent_cell_cost(left, right):
    """Approved four-corresponding-cell rational cost, with seconds as input."""
    return sum((abs(Fraction(a['median'])-Fraction(b['median'])) / (180*86400)
                + Fraction(abs(a['words']-b['words']),5000)
                + Fraction(abs(a['records']-b['records']),40)
                for a,b in zip(left,right,strict=True)),Fraction())


def independent_block_gate(cells):
    """All-eight volume extremes, and all-four medians within each period."""
    assert len(cells)==8
    words=[c['words'] for c in cells]; records=[c['records'] for c in cells]
    if min(words)<=0 or min(records)<=0:
        return False
    return (max(words)*10<=min(words)*11 and max(records)*4<=min(records)*5 and
            all(max(Fraction(c['median']) for c in cells if c['period']==period)
                - min(Fraction(c['median']) for c in cells if c['period']==period)<=30*86400
                for period in ('early','late')))


def rows(lengths,*,start=0,step=1):
    return [{'record_id':f'synthetic-{i:04d}','timestamp':start+i*step,'retained_words':w}
            for i,w in enumerate(lengths)]


def cell_stats(*,words=5000,records=40,median=0):
    return {'retained_words':words,'records':records,'median_timestamp':Fraction(median)}


def account():
    return {k:cell_stats(median=-DAY if k.endswith('early') else DAY) for k in feasibility.CELL_KEYS}


def oracle_cells(left,right):
    return [{'words':c['retained_words'],'records':c['records'],'median':c['median_timestamp'],
             'period':key.split('/')[1]} for side in (left,right) for key,c in side.items()]


@pytest.mark.parametrize('period,stamp,accepted',[
    ('early',-180*DAY-1,False),('early',-180*DAY,True),('early',-1,True),('early',0,False),
    ('late',-1,False),('late',0,True),('late',180*DAY-1,True),('late',180*DAY,False),
])
def test_halfopen_outer_and_cut_endpoints_exact_seconds(period,stamp,accepted):
    selected=feasibility.select_prefix(rows([125]*40,start=stamp,step=0),0,period,PLAN)
    assert (selected is not None)==accepted
    if accepted:
        assert selected['median_timestamp']==stamp


def test_prefix_nearest_cut_timestamp_id_ties_and_input_object_preservation():
    original=rows([125]*45,start=-45)
    before=deepcopy(original)
    selected=feasibility.select_prefix(list(reversed(original)),0,'early',PLAN)
    assert [r['record_id'] for r in selected['rows']]==[r['record_id'] for r in original[5:]]
    assert selected['median_timestamp']==Fraction(-41,2)
    assert original==before
    assert all(any(r is e for e in original) for r in selected['rows'])
    same_time=rows([125]*45,start=0,step=0)
    answer=feasibility.select_prefix(list(reversed(same_time)),0,'late',PLAN)
    assert answer['rows']==same_time[:40]


def test_exact_record_word_minimum_maximum_filter_before_prefix():
    original=rows([19,501,20,500]+[125]*38)
    answer=feasibility.select_prefix(original,0,'late',PLAN)
    assert answer['records']==40 and answer['retained_words']==5270
    assert answer['rows']==original[2:]
    assert answer['rows'][0]['retained_words']==20 and answer['rows'][1]['retained_words']==500


def test_both_word_and_comment_thresholds_stop_first_feasible_whole_prefix():
    # Target met after ten large comments; it still needs forty comments.
    too_wordy=rows([500]*10+[20]*30)
    assert feasibility.select_prefix(too_wordy,0,'late',PLAN) is None
    # Forty comments precede the word target, requiring the forty-first.
    original=rows([124]*40+[40,500])
    answer=feasibility.select_prefix(original,0,'late',PLAN)
    assert answer['rows']==original[:41]
    assert answer['records']==41 and answer['retained_words']==5000
    assert answer['median_timestamp']==20
    # These require forty records although 5000 words are reached at record39.
    original=rows([125]*38+[250,20,500])
    answer=feasibility.select_prefix(original,0,'late',PLAN)
    assert answer['records']==40 and answer['retained_words']==5020


@pytest.mark.parametrize('lengths,expected_records,expected_words',[
    ([138]*20+[137]*20,40,5500),
    ([138]*21+[137]*19,None,None),
    ([25]*200,200,5000),
    ([25]*199+[24,20],None,None),
])
def test_whole_prefix_5500_word_and200_record_ceilings(lengths,expected_records,expected_words):
    answer=feasibility.select_prefix(rows(lengths),0,'late',PLAN)
    if expected_records is None:
        assert answer is None
    else:
        assert answer['records']==expected_records and answer['retained_words']==expected_words


def test_maximum_comment_ceiling_never_skips_short_nearer_records_to_refill():
    assert feasibility.select_prefix(rows([20]*200+[500]*50),0,'late',PLAN) is None


@pytest.mark.parametrize('field,at_limit,over_limit',[
    ('retained_words',5500,5501),('records',50,51),
])
def test_all_eight_ratios_exact_inclusive_limits(field,at_limit,over_limit):
    left,right=account(),account()
    right['Y/late'][field]=at_limit
    assert feasibility.compatible(left,right,PLAN)
    assert independent_block_gate(oracle_cells(left,right))
    right['Y/late'][field]=over_limit
    assert not feasibility.compatible(left,right,PLAN)
    assert not independent_block_gate(oracle_cells(left,right))


def test_date_gate_uses_all_four_medians_not_just_corresponding_pairs():
    left,right=account(),account()
    for side in (left,right):
        side['X/early']['median_timestamp']=Fraction(-60*DAY)
        side['Y/early']['median_timestamp']=Fraction(-30*DAY)
    assert feasibility.compatible(left,right,PLAN)
    assert independent_block_gate(oracle_cells(left,right))
    # Each corresponding left/right median is identical, but within-period
    # all-four spread is now thirty days plus one half second.
    for side in (left,right):
        side['Y/early']['median_timestamp']+=Fraction(1,2)
    assert not feasibility.compatible(left,right,PLAN)
    assert not independent_block_gate(oracle_cells(left,right))


def test_date_span_is_evaluated_separately_in_early_and_late_periods():
    left,right=account(),account()
    for side in (left,right):
        for key,cell in side.items():
            cell['median_timestamp']=Fraction(-170*DAY if key.endswith('early') else 170*DAY)
    assert feasibility.compatible(left,right,PLAN)


def test_exact_cost_all_four_cells_and_approved_denominators():
    left,right=account(),account()
    for i,key in enumerate(feasibility.CELL_KEYS,1):
        right[key]['retained_words']+=i*25
        right[key]['records']+=i
        right[key]['median_timestamp']+=Fraction(i,2)+i*DAY
    a=[{'words':left[k]['retained_words'],'records':left[k]['records'],'median':left[k]['median_timestamp']} for k in feasibility.CELL_KEYS]
    b=[{'words':right[k]['retained_words'],'records':right[k]['records'],'median':right[k]['median_timestamp']} for k in feasibility.CELL_KEYS]
    expected=independent_cell_cost(a,b)
    answer=feasibility.edge_cost(left,right,PLAN)
    assert isinstance(answer,Fraction) and answer==expected
    assert answer==Fraction(10*DAY+5,180*DAY)+Fraction(250,5000)+Fraction(10,40)


def test_general_matching_avoids_greedy_cardinality_trap_and_odd_cycle():
    nodes=list('abcd')
    edges={('a','b'):Fraction(0),('a','c'):Fraction(2),('b','d'):Fraction(2)}
    answer=feasibility.exact_matching(nodes,edges)
    assert answer['cardinality']==2 and answer['cost']==4
    assert answer['pairs']==[('a','c'),('b','d')]
    # Triangle plus tail requires general rather than bipartite assumptions.
    edges={('a','b'):Fraction(0),('b','c'):Fraction(0),('a','c'):Fraction(0),('c','d'):Fraction(7)}
    answer=feasibility.exact_matching(nodes,edges)
    assert answer['cardinality']==2 and answer['pairs']==[('a','b'),('c','d')]


def test_exact_fraction_cost_breaks_matching_ties_below_float_precision():
    epsilon=Fraction(1,10**40)
    edges={('a','b'):Fraction(1)+epsilon,('c','d'):Fraction(1),
           ('a','c'):Fraction(1),('b','d'):Fraction(1)}
    answer=feasibility.exact_matching(list('abcd'),edges)
    assert answer['pairs']==[('a','c'),('b','d')] and answer['cost']==2


def test_disconnected_components_and_equal_cost_ties_respect_node_order():
    nodes=list('dcba')+['isolated','x','y']
    edges={(a,b):Fraction(0) for a,b in combinations('abcd',2)}
    edges['x','y']=Fraction(3,7)
    answer=feasibility.exact_matching(nodes,edges)
    assert answer['pairs']==[('d','c'),('b','a'),('x','y')]
    assert answer['cardinality']==3 and answer['cost']==Fraction(3,7)


def test_160_tiny_unrestricted_graphs_match_independent_exhaustive_oracle():
    rng=random.Random(409)
    for n in range(1,9):
        for _ in range(20):
            nodes=list(range(n)); rng.shuffle(nodes)
            edges={(a,b):Fraction(rng.randrange(7),rng.choice((1,2,3,11)))
                   for a,b in combinations(nodes,2) if rng.random()<.45}
            by_index={(nodes.index(a),nodes.index(b)):cost for (a,b),cost in edges.items()}
            expected=exhaustive_matching(range(n),by_index)
            answer=feasibility.exact_matching(nodes,edges)
            pairs=tuple(tuple(sorted((nodes.index(a),nodes.index(b)))) for a,b in answer['pairs'])
            assert (-answer['cardinality'],answer['cost'],pairs)==expected


def test_global_witness_backtracks_across_strata_without_account_reuse():
    # Locally first edges conflict with a later stratum; a feasible solution
    # requires returning to the earlier stratum instead of dropping subjects.
    edges={'s1':[('a','b'),('c','d')], 's2':[('a','e')], 's3':[('f','g')]}
    answer=feasibility.disjoint_strata_witness(edges,1)
    assert answer=={'s1':[('c','d')],'s2':[('a','e')],'s3':[('f','g')]}
    assert len({a for pairs in answer.values() for pair in pairs for a in pair})==6
    assert feasibility.disjoint_strata_witness({'s1':[('a','b')],'s2':[('a','c')]},1) is None


def test_global_two_block_witness_uses_all_compatible_edges_not_only_local_optimum():
    edges={'s1':[('a','b'),('c','d'),('e','f')],
           's2':[('a','g'),('h','i')], 's3':[('j','k'),('l','m')]}
    answer=feasibility.disjoint_strata_witness(edges,2)
    assert answer['s1']==[('c','d'),('e','f')]
    assert all(len(v)==2 for v in answer.values())
    assert len({a for pairs in answer.values() for pair in pairs for a in pair})==12


def test_metadata_arithmetic_code_imports_no_analysis_or_source_reader():
    text=SOURCE.read_text()
    for forbidden in ('account_history_analyzer','import zipfile','import tarfile','preprocess(', 'analyze(', 'evaluate('):
        assert forbidden not in text


def synthetic_registration(tmp_path):
    """Complete metadata-only input: three strata,117 excluded and12 allowed."""
    (tmp_path/'protocol').mkdir()
    (tmp_path/'tests').mkdir()
    declared_test=tmp_path/'tests/synthetic-binding-marker.py'
    declared_test.write_text('# Synthetic immutable registration fixture.\n')
    flags=[]
    for i in range(117):
        flags.append({'account_key':f'protected-{i:03d}',
                      'pilot1_or_pilot2_or_private_mandatory_exclusion':i<57,
                      'pilot3_selected_scored_exposure':i>=57,'prior_capacity_only_exposure':False})
    flags.append({'account_key':'allowed-0-0','pilot1_or_pilot2_or_private_mandatory_exclusion':False,
                  'pilot3_selected_scored_exposure':False,'prior_capacity_only_exposure':True})
    flag_path=tmp_path/'flags.json';flag_path.write_text(json.dumps({'accounts':flags}))
    metadata=[]
    for i in range(117):
        # Mixed source case must still match canonical exclusion identity.
        metadata.append({'record_id':f'forbidden-row-{i:03d}','account_key':f'PROTECTED-{i:03d}',
                         'community':'synthetic-x-0','created_utc':'1970-01-01T00:00:00Z',
                         'retained_words':125,'reason':None})
    pairs=[[f'synthetic-x-{s}',f'synthetic-y-{s}'] for s in range(3)]
    for s,pair in enumerate(pairs):
        for a in range(4):
            for community in pair:
                for part,base in [('early',-10*DAY),('late',10*DAY)]:
                    for r in range(40):
                        metadata.append({'record_id':f'allowed-{s}-{a}-{community}-{part}-{r}',
                            'account_key':f'allowed-{s}-{a}','community':community,
                            'created_utc':datetime.fromtimestamp(base+r,tz=timezone.utc).isoformat().replace('+00:00','Z'),
                            'retained_words':125,'reason':None})
    source=tmp_path/'metadata.jsonl'
    source.write_text(''.join(json.dumps(row)+'\n' for row in metadata))
    plan={**PLAN,'cuts':['1970-01-02T00:00:00Z','1970-01-01T00:00:00Z'],
          'community_pairs':pairs,'exposure_flags_sha256':feasibility.sha(flag_path),
          'address_space_bytes':4*1024**3,'census_wall_seconds':600,
          'metadata_record_cap':10000,'metadata_bytes_cap':256*1024**2,
          'intended_maximum_blocks_per_stratum':2,
          'source_metadata':[{'path':str(source),'bytes':source.stat().st_size,'sha256':feasibility.sha(source)}]}
    plan_path=tmp_path/'protocol/plan.json';plan_path.write_text(json.dumps(plan))
    registration={'plan_sha256':feasibility.sha(plan_path),'implementation_sha256':feasibility.sha(SOURCE),
                  'exposure_flags_sha256':feasibility.sha(flag_path),'cost_rule':feasibility.COST_RULE,
                  'band_rule':feasibility.BAND_RULE,'tie_rule':feasibility.TIE_RULE,
                  'test_files':[{'path':'tests/synthetic-binding-marker.py','sha256':feasibility.sha(declared_test)}]}
    registration_path=tmp_path/'protocol/registration.json';registration_path.write_text(json.dumps(registration))
    return plan_path,flag_path,registration_path


def test_synthetic_full_run_excludes117_and_binds_earliest_tied_cut_global_witness(tmp_path):
    paths=synthetic_registration(tmp_path)
    out,private=tmp_path/'public',tmp_path/'private'
    assert feasibility.run(*paths,out,private)==0
    summary=json.loads((out/'feasibility-summary.json').read_text())
    assert summary['status']=='feasible_before_contamination_audit'
    assert summary['counts']['excluded_rows']==117
    assert summary['counts']['eligible_registered_metadata_rows']==1920
    assert summary['evaluated_pair_cuts']==6
    assert all(r['cut']=='1970-01-01T00:00:00Z' and r['maximum_disjoint_blocks']==2
               for r in summary['selected_calendar_witnesses'])
    result=json.loads((private/'candidates-and-witness.json').read_text())
    witness=result['globally_disjoint_intended_block_witness']
    assert len(witness)==3 and all(len(edges)==2 for edges in witness.values())
    accounts={a for edges in witness.values() for edge in edges for a in edge}
    assert len(accounts)==12 and all(a.startswith('allowed-') for a in accounts)
    for sid,stratum in result['strata'].items():
        ordered=sorted(stratum['candidate_cells'],key=feasibility.identity_order)
        assert stratum['maximum_matching']['pairs']==[ordered[i:i+2] for i in (0,2)]
        assert stratum['maximum_matching']['cost']=={'numerator':0,'denominator':1}
    assert summary['capacity_only_exposed_candidate_counts_at_chosen_cuts']['stratum-01']==1
    assert summary['new_preprocessing_calls']==summary['new_style_distance_calls']==0
    assert summary['source_prose_fields_accessed'] is False


@pytest.mark.parametrize('change',('registered_test','cost_rule','plan_hash'))
def test_pre_run_registration_rejects_changed_binding_before_metadata_search(tmp_path,change):
    paths=synthetic_registration(tmp_path)
    if change=='registered_test':
        (tmp_path/'tests/synthetic-binding-marker.py').write_text('# Altered marker.\n')
    elif change=='cost_rule':
        registration=json.loads(paths[2].read_text());registration['cost_rule']='unregistered rule'
        paths[2].write_text(json.dumps(registration))
    else:
        plan=json.loads(paths[0].read_text());plan['half_band_days']=181
        paths[0].write_text(json.dumps(plan))
    with pytest.raises(ValueError,match='registration|Registered test'):
        feasibility.run(*paths,tmp_path/'public',tmp_path/'private')
    assert not (tmp_path/'public').exists()


def test_metadata_row_cap_failure_remains_incomplete_never_zero_capacity(tmp_path):
    plan_path,flags_path,registration_path=synthetic_registration(tmp_path)
    plan=json.loads(plan_path.read_text());plan['metadata_record_cap']=1
    plan_path.write_text(json.dumps(plan))
    registration=json.loads(registration_path.read_text());registration['plan_sha256']=feasibility.sha(plan_path)
    registration_path.write_text(json.dumps(registration))
    out=tmp_path/'public'
    assert feasibility.run(plan_path,flags_path,registration_path,out,tmp_path/'private')==1
    result=json.loads((out/'incomplete-search.json').read_text())
    assert result['status']=='incomplete_not_zero_capacity' and result['completed_cuts']==[]
    assert not (out/'feasibility-summary.json').exists()
