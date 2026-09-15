"""Independent synthetic protocol checks; no real metadata or corpus access."""
from copy import deepcopy
from fractions import Fraction
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import pytest

SPEC=importlib.util.spec_from_file_location('pilot6_metadata_independent',Path(__file__).parents[1]/'scripts/metadata_replication.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True)+'\n')


def flags():
    rows=[]
    for i in range(117):
        rows.append({'account_key':f'excluded-{i:03}',
            'pilot1_or_pilot2_or_private_mandatory_exclusion':i<57,
            'pilot3_selected_scored_exposure':i>=57,'prior_capacity_only_exposure':False})
    return {'accounts':rows}


def selection():
    return {'selected':{'account_a':'pilot5-a','account_b':'pilot5-b'}}


def candidate(a='a',b='b',cost=Fraction(),**kw):
    return dict(account_a=a,account_b=b,cost=cost,valid=True,stratum_id='stratum-01',
                cut='2017-01-01T00:00:00Z',community_x='X',community_y='Y',**kw)


def exact_small(nodes,edges,check=lambda:None):
    """Independent exhaustive first-vertex recurrence for small synthetic graphs."""
    nodes=tuple(nodes);position={a:i for i,a in enumerate(nodes)}
    costs={tuple(sorted((position[a],position[b]))):cost for (a,b),cost in edges.items()}
    @lru_cache(None)
    def visit(vertices):
        if not vertices:return (0,Fraction(),())
        a,*rest=vertices;best=visit(tuple(rest))
        for b in rest:
            if (a,b) in costs:
                n,c,pairs=visit(tuple(x for x in rest if x!=b))
                best=min(best,(n-1,c+costs[a,b],((a,b),)+pairs))
        return best
    n,cost,pairs=visit(tuple(range(len(nodes))))
    return {'cardinality':-n,'cost':cost,'pairs':[(nodes[a],nodes[b]) for a,b in pairs],'dp_states':visit.cache_info().currsize}


def registered_fixture(tmp_path,monkeypatch,extra_rows=()):
    rows=[];cut=m.seconds('2017-01-01T00:00:00Z')
    from datetime import datetime,timezone
    # Three strata produce edges ab, ac, bd. Cardinality must defeat cheap ab.
    for sid,(a,b) in enumerate([('a','b'),('a','c'),('b','d')]):
        x,y=m.PAIRS[sid]
        for account,community,period in [(a,x,'early'),(a,x,'late'),(b,x,'late'),(a,y,'late'),(b,y,'late')]:
            for i in range(40):
                rows.append({'record_id':f's{sid}-{account}-{community}-{period}-{i:03}',
                    'account_key':account,'community':community,'reason':None,'retained_words':125,
                    'created_utc':datetime.fromtimestamp(cut+(-3600+i if period=='early' else 3600+i),timezone.utc).isoformat().replace('+00:00','Z')})
    rows.extend(extra_rows)
    source=tmp_path/'metadata.jsonl';source.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    f=tmp_path/'flags.json';s=tmp_path/'selection.json';protocol=tmp_path/'protocol.md'
    put(f,flags());put(s,selection());protocol.write_text('Synthetic protocol binding\n')
    helpers=[m.P4/n for n in ('metadata_feasibility.py','metadata_feasibility_v2.py','chronology_math.py','run_full_chronology.py')]+[m.P5/'prepare_shared_anchor.py']
    bound=[Path(m.__file__),source,f,s,protocol,*helpers]
    plan={'phase':'frozen_before_replication_metadata','script_sha256':m.sha(m.__file__),
          'community_pairs':m.PAIRS,'design':m.DESIGN,'limits':m.LIMITS,
          'cuts':[f'{year}-{month:02d}-01T00:00:00Z' for year in range(2010,2019) for month in range(1,13) if (year,month)<=(2018,5)],
          'exposure_flags':str(f),'pilot5_selection':str(s),'protocol':str(protocol),
          'source_metadata':[{'path':str(source),'bytes':source.stat().st_size,'sha256':m.sha(source)}],
          'bindings':[{'path':str(p),'sha256':m.sha(p)} for p in bound],'matching_backend':{}}
    plan_path=tmp_path/'plan.json';put(plan_path,plan)
    calls=[]
    def matcher(nodes,edges,check):
        calls.append((list(nodes),dict(edges)));return exact_small(nodes,edges,check)
    monkeypatch.setattr(m,'verify_matching_backend',lambda config,check:matcher)
    monkeypatch.setenv('AHAS_NETWORK_ISOLATION','linux_seccomp_socket_denial')
    monkeypatch.setattr(m.resource,'setrlimit',lambda *args:None)
    return plan_path,source,rows,calls


def test_stratum_order_precedes_cut_at_equal_cost():
    first=candidate();later_stratum=candidate();later_stratum.update(stratum_id='stratum-02',cut='2010-01-01T00:00:00Z')
    assert list(m.choose_edges([later_stratum,first]).values())==[first]


def test_exact_cost_and_direction_hash_tie_are_order_independent():
    a=candidate(cost=Fraction(2**150+1,2**150));b=candidate(a='b',b='a',cost=Fraction(1))
    assert list(m.choose_edges([a,b]).values())==[b]
    a['cost']=Fraction(1)
    expected=min([a,b],key=lambda r:(m.identity(r['account_a']),m.identity(r['account_b']),r['community_x'],r['community_y']))
    assert list(m.choose_edges([a,b]).values())==[expected]
    assert m.choose_edges([a,b])==m.choose_edges([b,a])


def test_account_hash_salt_is_exact_utf8_and_casefolded():
    expected=hashlib.sha256(('pilot6-anchor-order-v1\0'+'example').encode('utf-8')).hexdigest()
    assert m.identity('ExAmPlE')==expected


def test_exclusion_union_is_exact_119_and_capacity_exposure_is_separate():
    f=flags();f['accounts'].append({'account_key':'available-capacity',
        'pilot1_or_pilot2_or_private_mandatory_exclusion':False,'pilot3_selected_scored_exposure':False,'prior_capacity_only_exposure':True})
    excluded,capacity=m.flags_excluded(f,selection())
    assert len(excluded)==119 and capacity=={'available-capacity'} and not capacity&excluded


@pytest.mark.parametrize('field',['pilot1_or_pilot2_or_private_mandatory_exclusion','pilot3_selected_scored_exposure','prior_capacity_only_exposure'])
def test_flag_values_must_be_literal_boolean(field):
    f=flags();f['accounts'][0][field]=int(f['accounts'][0][field])
    with pytest.raises(ValueError):m.flags_excluded(f,selection())


@pytest.mark.parametrize('value',['PILOT5-A',''])
def test_pilot5_excluded_accounts_must_be_nonempty_canonical(value):
    s=selection();s['selected']['account_a']=value
    with pytest.raises(ValueError):m.flags_excluded(flags(),s)


def test_full_505_cut_enumeration_global_matching_and_late_only_roles(tmp_path,monkeypatch):
    plan,source,original,calls=registered_fixture(tmp_path,monkeypatch)
    # P5 evaluate imports legal_grid but must never call it during selection.
    module=sys.modules[m.evaluate.__module__]
    monkeypatch.setattr(module,'legal_grid',lambda *_:(_ for _ in ()).throw(AssertionError('grid must not select')))
    digest=m.sha(source)
    assert m.run(plan,tmp_path/'public',tmp_path/'private')==0
    assert m.sha(source)==digest
    saved=json.loads((tmp_path/'private/provisional-pairs.json').read_bytes())
    assert len(calls)==1 and len(calls[0][1])==3
    assert {frozenset((r['account_a'],r['account_b'])) for r in saved['pairs']}=={frozenset(('a','c')),frozenset(('b','d'))}
    assert len({a for r in saved['pairs'] for a in (r['account_a'],r['account_b'])})==4
    cuts=json.loads((tmp_path/'public/all-calendar-cuts.json').read_bytes())
    assert len(cuts)==505 and all(sum(x['accounts_with_two_late_prefixes'] for x in cuts if x['stratum_id']==f'stratum-{i:02}')>0 for i in (1,2,3))
    assert all(c['all_possible_ordered_directions']==c['directions_without_two_late_accounts']+c['directions_without_anchor']+c['evaluated_directions'] for c in cuts)
    assert all(c['evaluated_directions']==c['valid_directions']+c['invalid_evaluated_directions'] for c in cuts)
    summary=json.loads((tmp_path/'public/feasibility-summary.json').read_bytes())
    assert summary['global_maximum_matching_pairs']==2 and summary['provisional_pairs']==2
    assert summary['style_calls']==0 and summary['grid_localization_evaluated'] is False
    assert summary['verified_source_metadata']==[{'source_index':1,'bytes':source.stat().st_size,'rows':len(original),'sha256':digest}]
    assert 'account_a' not in json.dumps(summary) and 'account_b' not in json.dumps(summary)


def test_duplicate_original_id_detected_even_when_excluded_and_outside_scope(tmp_path,monkeypatch):
    extra={'record_id':'same-original','account_key':'excluded-000','community':'outside','reason':'guard',
           'retained_words':0,'created_utc':None}
    plan,source,_,calls=registered_fixture(tmp_path,monkeypatch,[extra,extra])
    with pytest.raises(ValueError,match='ID repeated'):m.run(plan,tmp_path/'public',tmp_path/'private')
    incomplete=json.loads((tmp_path/'public/incomplete-metadata.json').read_bytes())
    assert incomplete['status']=='incomplete_not_zero_capacity' and not calls


def test_source_metadata_declared_hash_must_match_binding(tmp_path,monkeypatch):
    plan,source,_,calls=registered_fixture(tmp_path,monkeypatch)
    document=json.loads(plan.read_bytes());document['source_metadata'][0]['sha256']='0'*64;put(plan,document)
    with pytest.raises(ValueError):m.run(plan,tmp_path/'public',tmp_path/'private')
    assert not calls


def test_same_length_source_mutation_after_preflight_hash_is_detected(tmp_path,monkeypatch):
    plan,source,_,calls=registered_fixture(tmp_path,monkeypatch)
    def mutate_then_backend(config,check):
        before=source.read_bytes();after=before.replace(b'"retained_words": 125',b'"retained_words": 124',1)
        assert len(before)==len(after) and before!=after
        source.write_bytes(after)
        return exact_small
    monkeypatch.setattr(m,'verify_matching_backend',mutate_then_backend)
    with pytest.raises(ValueError,match='changed during streaming'):
        m.run(plan,tmp_path/'public',tmp_path/'private')
    incomplete=json.loads((tmp_path/'public/incomplete-metadata.json').read_bytes())
    assert incomplete['status']=='incomplete_not_zero_capacity'
    assert incomplete['completed_pair_cuts']==0 and not calls


@pytest.mark.parametrize('mutation',[{'account_key':'Excluded-000'},{'retained_words':125.0}])
def test_noncanonical_input_metadata_refused_before_direction_enumeration(tmp_path,monkeypatch,mutation):
    extra={'record_id':'bad-metadata','account_key':'new','community':'AskAcademia','reason':None,
           'retained_words':125,'created_utc':'2017-01-01T01:00:00Z',**mutation}
    plan,source,_,calls=registered_fixture(tmp_path,monkeypatch,[extra])
    with pytest.raises(ValueError):m.run(plan,tmp_path/'public',tmp_path/'private')
    assert not calls


@pytest.mark.parametrize('reason',['unavailable',None])
def test_legacy_null_word_metadata_is_allowed_only_with_explicit_ineligible_reason(tmp_path,monkeypatch,reason):
    extra={'record_id':'legacy-unavailable','account_key':'legacy-account','community':'AskAcademia',
           'reason':reason,'retained_words':None,'created_utc':None}
    plan,source,_,calls=registered_fixture(tmp_path,monkeypatch,[extra])
    if reason is None:
        with pytest.raises(ValueError,match='null retained words'):
            m.run(plan,tmp_path/'public',tmp_path/'private')
        assert not calls
    else:
        assert m.run(plan,tmp_path/'public',tmp_path/'private')==0
        summary=json.loads((tmp_path/'public/feasibility-summary.json').read_bytes())
        assert summary['counts']['ineligible_rows']==1
        assert summary['global_maximum_matching_pairs']==2
