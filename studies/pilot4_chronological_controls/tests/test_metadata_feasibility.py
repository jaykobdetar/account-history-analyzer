import importlib.util
from fractions import Fraction
from pathlib import Path

spec = importlib.util.spec_from_file_location('p4_feasibility', Path(__file__).resolve().parents[1]/'scripts/metadata_feasibility.py')
f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)


def plan():
    return {'half_band_days':180,'record_word_min':20,'record_word_max':500,
            'half_max_words':5500,'half_target_words':5000,'half_min_records':40,'half_max_records':200,
            'all_eight_cell_word_ratio_max':'11/10','all_eight_cell_record_ratio_max':'5/4',
            'within_period_four_cell_median_span_days_max':30}


def rows(words=125,n=40,base=0):
    return [{'timestamp':base+i,'record_id':str(i).zfill(3),'retained_words':words} for i in range(n)]


def cells(words=5000,records=40,median=0):
    return {key:{'retained_words':words,'records':records,'median_timestamp':Fraction(median)} for key in f.CELL_KEYS}


def test_prefix_requires_both_gates_and_preserves_whole_records():
    r=rows(words=500,n=10)+[{'timestamp':i+10,'record_id':f'x{i:02}','retained_words':20} for i in range(30)]
    assert f.select_prefix(r,0,'late',plan()) is None  #40 comments would overshoot5500.
    q=rows(words=100,n=55)
    c=f.select_prefix(q,0,'late',plan())
    assert c['records']==50 and c['retained_words']==5000
    assert len(c['rows'])==50 and c['median_timestamp']==Fraction(49,2)


def test_half_open_boundaries_and_early_nearest_tie():
    p=plan();p.update(half_target_words=40,half_min_records=2,half_max_words=500,half_max_records=3)
    cut=200*f.DAY
    q=[{'timestamp':cut,'record_id':'late','retained_words':20},
       {'timestamp':cut-1,'record_id':'b','retained_words':20},
       {'timestamp':cut-1,'record_id':'a','retained_words':20},
       {'timestamp':cut-180*f.DAY,'record_id':'start','retained_words':20},
       {'timestamp':cut-180*f.DAY-1,'record_id':'outside','retained_words':20},
       {'timestamp':cut+180*f.DAY,'record_id':'end','retained_words':20}]
    c=f.select_prefix(q,cut,'early',p)
    assert [r['record_id'] for r in c['rows']]==['a','b']
    assert f.select_prefix(q,cut,'late',p) is None


def test_comment_length_endpoints_and_budget_endpoints():
    p=plan();p.update(half_target_words=520,half_min_records=2,half_max_words=520,half_max_records=2)
    q=[{'timestamp':0,'record_id':'a','retained_words':19},
       {'timestamp':1,'record_id':'b','retained_words':20},
       {'timestamp':2,'record_id':'c','retained_words':501},
       {'timestamp':3,'record_id':'d','retained_words':500}]
    c=f.select_prefix(q,0,'late',p)
    assert c['records']==2 and c['retained_words']==520


def test_block_gate_includes_all_four_medians_and_all_eight_volumes():
    p=plan();a=cells();b=cells()
    a['Y/early']['median_timestamp']=Fraction(-20*f.DAY)
    b['X/early']['median_timestamp']=Fraction(20*f.DAY)
    #Corresponding A/B differences20days each, overall four-cellspan40days.
    assert not f.compatible(a,b,p)
    a=cells();b=cells(words=5500,records=50,median=30*f.DAY)
    assert f.compatible(a,b,p)
    b['Y/late']['records']=51
    assert not f.compatible(a,b,p)


def test_cost_is_exact_and_normalized_by_registered_budget():
    a=cells();b=cells(words=5100,records=41,median=18*f.DAY)
    assert f.edge_cost(a,b,plan())==4*(Fraction(1,10)+Fraction(1,50)+Fraction(1,40))


def test_matching_prefers_cardinality_before_cost_then_minimum_cost():
    edges={('a','b'):Fraction(0),('a','c'):Fraction(4),('b','d'):Fraction(4),('c','d'):Fraction(100)}
    m=f.exact_matching(list('abcd'),edges)
    assert m['cardinality']==2 and m['cost']==8 and m['pairs']==[('a','c'),('b','d')]


def test_matching_handles_odd_cycle_and_isolated_vertex():
    m=f.exact_matching(list('abcd'),{('a','b'):1,('b','c'):2,('a','c'):3})
    assert m['cardinality']==1 and m['cost']==1 and m['pairs']==[('a','b')]


def test_global_witness_rejects_cross_stratum_account_reuse():
    assert f.disjoint_strata_witness({'one':[('a','b')],'two':[('b','c')]},1) is None
    w=f.disjoint_strata_witness({'one':[('a','b'),('c','d')],'two':[('a','e')]},1)
    assert w=={'one':[('c','d')],'two':[('a','e')]}


def test_zero_capacity_graph_is_explicit():
    assert f.exact_matching(['a','b'],{})['cardinality']==0
    assert f.disjoint_strata_witness({'one':[]},2) is None


def test_synthetic_cli_writes_complete_bounded_witness(tmp_path):
    import hashlib
    import json
    import subprocess
    import sys
    p=plan()
    cut='2015-01-01T00:00:00Z';stamp=f.seconds(cut)
    flags={'accounts':[{'account_key':f'excluded-{i}','pilot1_or_pilot2_or_private_mandatory_exclusion':i<57,
                       'pilot3_selected_scored_exposure':i>=57,'prior_capacity_only_exposure':False} for i in range(117)]}
    flags_path=tmp_path/'flags.json';flags_path.write_text(json.dumps(flags))
    metadata=tmp_path/'rows.jsonl'
    with metadata.open('w') as handle:
        for a in range(4):
            for community in ('CX','CY'):
                for period in ('early','late'):
                    for i in range(40):
                        t=stamp-40+i if period=='early' else stamp+i
                        row={'account_key':f'new-{a}','community':community,'record_id':f'{a}-{community}-{period}-{i}',
                             'created_utc':f.datetime.fromtimestamp(t,f.timezone.utc).isoformat().replace('+00:00','Z'),
                             'retained_words':125,'reason':None,'source_line_sha256':'0'*64}
                        handle.write(json.dumps(row)+'\n')
    p.update(address_space_bytes=4*1024**3,census_wall_seconds=20,metadata_bytes_cap=1024**2,
             metadata_record_cap=1000,community_pairs=[['CX','CY']],cuts=[cut],intended_maximum_blocks_per_stratum=2,
             source_metadata=[{'path':str(metadata),'bytes':metadata.stat().st_size,'sha256':f.sha(metadata)}],
             exposure_flags_sha256=f.sha(flags_path))
    plan_path=tmp_path/'plan.json';plan_path.write_text(json.dumps(p))
    registration={'plan_sha256':f.sha(plan_path),'implementation_sha256':f.sha(f.__file__),
                  'exposure_flags_sha256':f.sha(flags_path),'cost_rule':f.COST_RULE,'band_rule':f.BAND_RULE,
                  'tie_rule':f.TIE_RULE,'test_files':[]}
    registration_path=tmp_path/'registration.json';registration_path.write_text(json.dumps(registration))
    out=tmp_path/'public';private=tmp_path/'private'
    result=subprocess.run([sys.executable,f.__file__,'--plan',str(plan_path),'--exposure-flags',str(flags_path),
                           '--registration',str(registration_path),'--out',str(out),'--private-out',str(private)],
                          capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    summary=json.loads((out/'feasibility-summary.json').read_bytes())
    assert summary['status']=='feasible_before_contamination_audit'
    assert summary['globally_disjoint_intended_blocks_exist'] is True
    assert summary['counts']['metadata_rows']==640
    assert summary['selected_calendar_witnesses'][0]['maximum_disjoint_blocks']==2
    assert summary['new_style_distance_calls']==summary['new_preprocessing_calls']==0
    assert len((out/'all-calendar-cuts.csv').read_text().splitlines())==2
    assert (private/'candidates-and-witness.json').stat().st_mode & 0o777==0o600
