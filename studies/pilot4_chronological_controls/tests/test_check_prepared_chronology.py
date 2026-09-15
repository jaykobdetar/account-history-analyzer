"""Entirely synthetic verification of independent prepared-input checks."""
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import json
import sys
from unittest.mock import patch
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import check_prepared_chronology as check
from test_prepare_chronology_pool import SyntheticPool,put
from test_finalize_chronology_inputs import fake_audit
from finalize_chronology_inputs import finalize


@pytest.fixture
def prepared(tmp_path):
    fixture=SyntheticPool(tmp_path)
    audit,freeze,public_audit=fake_audit(fixture)
    out,public=tmp_path/'prepared',tmp_path/'public'
    with patch.dict('os.environ',{'AHAS_NETWORK_ISOLATION':'linux_seccomp_socket_denial'}),patch('finalize_chronology_inputs.resource.setrlimit'):
        finalize(fixture.plan_path,fixture.pool/'candidate-pool.jsonl',audit,out,public,audit_freeze=freeze,audit_public=public_audit)
    return (fixture.plan_path,fixture.pool/'candidate-pool.jsonl',audit,freeze,public_audit,out,public)


def rebind_prepared(args):
    out=args[5];index=check.read(out/'index.json')
    for row in index['bound_files']:row['sha256']=check.sha(row['path'])
    put(out/'index.json',index)
    summary=check.read(args[6]/'selection-summary.json');summary['index_sha256']=check.sha(out/'index.json');put(args[6]/'selection-summary.json',summary)


def test_complete_synthetic_five_blocks_eighty_cases(prepared):
    result=check.verify(*prepared,sample=False)
    assert result['status']=='passed' and result['selected_blocks']==5 and result['selected_accounts']==10
    assert result['prepared_cases']==80 and result['selected_records']==1600 and result['public_cells_checked']==40
    assert result['prepared_record_appearances_verified']==6400 and result['source_archive_reads']==result['style_scores_computed']==0
    assert result['word_sample']['preprocessor_calls']==0


@pytest.mark.parametrize('field,value',[
    ('text','modified source writing'),('id','renamed'),('created_utc','2015-01-01T00:00:01Z'),
    ('subreddit','wrong-community'),('parent_id','wrong-parent'),('thread_id','wrong-thread'),('account_id','wrong-alias'),
])
def test_exported_field_mutations_fail_after_hash_rebinding(prepared,field,value):
    case=check.read(prepared[5]/'index.json')['cases'][0];path=Path(case['input'])
    rows=[json.loads(line) for line in path.read_text().splitlines()];rows[0][field]=value
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows));rebind_prepared(prepared)
    with pytest.raises(ValueError,match='exported_record_changed'):check.verify(*prepared,sample=False)


@pytest.mark.parametrize('field,value',[
    ('truth_k',40),('control_junction_k',39),('prescore_qualified_windows',11),
    ('prescore_legal_grid',[]),('source_switch',True),
])
def test_case_design_truth_and_grid_mutations_fail(prepared,field,value):
    path=prepared[5]/'index.json';index=check.read(path);index['cases'][0][field]=value;put(path,index);rebind_prepared(prepared)
    with pytest.raises(ValueError):check.verify(*prepared,sample=False)


def test_source_copy_fidelity_does_not_depend_on_declared_pool_hash(prepared):
    path=prepared[1];rows=[json.loads(x) for x in path.read_text().splitlines()]
    rows[0]['record']['text']='changed';path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    # Rebind the reported input chain; independent original byte projection must still fail.
    prep_path=path.parent/'preparation.json';prep=check.read(prep_path);prep['candidate_pool_sha256']=check.sha(path);put(prep_path,prep)
    freeze=check.read(prepared[3]);freeze['candidate_pool_sha256']=check.sha(path);put(prepared[3],freeze)
    audit_public=check.read(prepared[4]);audit_public['freeze_sha256']=check.sha(prepared[3]);put(prepared[4],audit_public)
    for name in ('cohort.json','start-binding.json'):
        p=prepared[5]/name;x=check.read(p);x.update(pool_sha256=check.sha(path),audit_freeze_sha256=check.sha(prepared[3]),audit_public_sha256=check.sha(prepared[4]));put(p,x)
    rebind_prepared(prepared)
    with pytest.raises(ValueError,match='source_copy_field_fidelity'):check.verify(*prepared,sample=False)


def test_cohort_cannot_choose_different_equal_cost_matching_after_binding(prepared):
    path=prepared[5]/'cohort.json';cohort=check.read(path)
    cohort['blocks'][0]['account_keys'].reverse();put(path,cohort);rebind_prepared(prepared)
    with pytest.raises(ValueError,match='cohort_prefix_matching'):check.verify(*prepared,sample=False)


def test_public_quantile_or_cost_cannot_be_silently_changed(prepared):
    path=prepared[6]/'cells.json';rows=check.read(path);rows[0]['comment_length_quantiles']['1/2']=124;put(path,rows)
    with pytest.raises(ValueError,match='public_cell_statistics'):check.verify(*prepared,sample=False)


def test_unexpected_private_export_file_rejected(prepared):
    (prepared[5]/'unexpected.json').write_text('{}')
    with pytest.raises(ValueError,match='unexpected_prepared'):check.verify(*prepared,sample=False)


def test_capped_matching_uses_best_capped_matching_not_prefix_of_uncapped():
    nodes=list('abcd');edges={('a','b'):0,('a','c'):5,('b','d'):5}
    one,total=check.capped_matching(nodes,edges,1);two,total2=check.capped_matching(nodes,edges,2)
    assert set(one[0])=={'a','b'} and total==0 and len(two)==2 and total2==10


def test_prefix_guard_half_open_endpoints_and_no_skip_refill():
    rows=[{'timestamp':-180*check.DAY,'record_id':str(i),'retained_words':125} for i in range(40)]
    assert check.prefix(rows,0,'early')['words']==5000
    assert check.prefix([{**r,'timestamp':180*check.DAY} for r in rows],0,'late') is None
    rows=[{'timestamp':i,'record_id':str(i),'retained_words':20} for i in range(200)]
    rows+=[{'timestamp':201,'record_id':'long','retained_words':500}]
    assert check.prefix(rows,0,'late') is None


def test_word_sample_is_deterministic_twenty_and_uses_word_kind_offsets():
    entries={str(i):{'retained_words':20,'record':{'id':str(i),'text':' '.join(['word']*20)}} for i in range(30)}
    calls=[]
    def preprocessing(record,manifest,config):
        calls.append(record['id']);return {'usable':True,'token_offsets':[[{'kind':'word'}]*20+[{'kind':'punctuation'}]],'word_tokens':[['deliberately-wrong']]}
    first=check.word_sample(entries,entries,preprocessing,{})
    order=list(calls);calls.clear()
    second=check.word_sample(entries,list(reversed(entries)),preprocessing,{})
    assert calls==order and first==second and first['sampled_records']==20 and first['sampled_words']==400


def test_word_sample_refuses_changed_counts():
    entry={'a':{'retained_words':20,'record':{'id':'a','text':'synthetic'}}}
    with pytest.raises(ValueError,match='sampled_retained_word'):
        check.word_sample(entry,entry,lambda *a:{'usable':True,'token_offsets':[]},{})


def test_protected_account_cannot_enter_amended_allocation(prepared):
    plan=check.read(prepared[0]);plan['strata'][0]['accounts'][0]='excluded-0';put(prepared[0],plan)
    with pytest.raises(ValueError,match='fixed117_exclusions'):check.verify(*prepared,sample=False)


def test_audit_deficit_retains_zero_stratum_and_does_not_refill(tmp_path):
    fixture=SyntheticPool(tmp_path);audit,freeze,public_audit=fake_audit(fixture,purge_account='physics-a')
    out,public=tmp_path/'prepared',tmp_path/'public'
    with patch.dict('os.environ',{'AHAS_NETWORK_ISOLATION':'linux_seccomp_socket_denial'}),patch('finalize_chronology_inputs.resource.setrlimit'):
        finalize(fixture.plan_path,fixture.pool/'candidate-pool.jsonl',audit,out,public,audit_freeze=freeze,audit_public=public_audit)
    result=check.verify(fixture.plan_path,fixture.pool/'candidate-pool.jsonl',audit,freeze,public_audit,out,public,sample=False)
    assert result['selected_blocks']==4 and result['prepared_cases']==64
    missing=next(r for r in result['strata'] if r['stratum_id']=='physics')
    assert missing['selected_blocks']==0 and missing['block_deficit']==1


def test_upstream_census_source_hash_checked_independently(tmp_path):
    row={'record_id':'synthetic','reason':None,'source_line_sha256':'original','account_key':'synthetic'}
    path=tmp_path/'metadata.jsonl';path.write_text(json.dumps(row)+'\n')
    binding={str(path.resolve()):check.sha(path)}
    expected={'synthetic':{**row,'stratum_id':'synthetic-stratum','period':'early'}}
    assert check.source_metadata_binding([path],binding,expected)['selected_source_hashes_verified']==1
    expected['synthetic']['source_line_sha256']='altered'
    with pytest.raises(ValueError,match='upstream_census_metadata'):check.source_metadata_binding([path],binding,expected)
