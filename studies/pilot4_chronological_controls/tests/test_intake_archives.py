import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile
import pytest

spec=importlib.util.spec_from_file_location('p4_intake',Path(__file__).resolve().parents[1]/'scripts/intake_archives.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
CONFIG={'input':{'max_text_codepoints':1000},'style':{'minimum_record_words':20}}


def raw(account='new',words=20,**kwargs):
    return {'id':'c1','root':'thread','reply_to':'parent','user':account,'timestamp':1451606400,
            'text':' '.join(['word']*words),'meta':{'subreddit':'one'},**kwargs}


class NoBody(dict):
    def get(self,key,default=None):
        if key=='text':raise AssertionError('Excluded text accessed')
        return super().get(key,default)
    def __getitem__(self,key):
        if key=='text':raise AssertionError('Excluded text accessed')
        return super().__getitem__(key)


def test_excluded_casefolded_identity_precedes_body_access():
    r=NoBody(raw(account='Protected'))
    assert m.present_comment(r,{'protected'})==(None,None,'excluded_account')
    assert m.preprocess_comment(r,'one',{'protected'},CONFIG,lambda *a:pytest.fail('called'))==(None,'excluded_account',0)


@pytest.mark.parametrize('value',[None,True,'1451606400',float('inf')])
def test_noninteger_timestamp_not_eligible(value):
    assert m.present_comment(NoBody(raw(timestamp=value)),set())[2]=='invalid_timestamp'


def test_pair_specific_prefilter_and_exact80_boundary():
    frame={'cross':{'a':80,'c':80},'good':{'a':80,'b':80},'short':{'c':80,'d':79}}
    memberships,pairs=m.candidate_memberships(frame,[['a','b'],['c','d']],80)
    assert memberships=={('good','a'),('good','b')}
    assert pairs=={'a / b':{'good'},'c / d':set()}


def test_conversion_matches_frozen_contract_and_emits_no_body():
    seen=[]
    def preprocess(record,manifest,config):
        seen.append((record,manifest,config))
        return {'usable':True,'word_tokens':[['x']*11,['y']*10]}
    item,reason,calls=m.preprocess_comment(raw(account='NEW'),'one',set(),CONFIG,preprocess)
    assert calls==1 and reason is None and item['retained_words']==21 and item['account_key']=='new'
    assert seen[0][0]=={'id':'c1','kind':'comment','text':raw()['text'],'status':'present',
                       'created_utc':'2016-01-01T00:00:00Z','language':None,'subreddit':'one','edit_state':'unknown'}
    assert seen[0][1]=={'default_language':'en','text_format':'markdown'}
    assert not ({'text','body','word_tokens','features'}&set(item))
    assert item['thread_id']=='thread' and item['parent_id']=='parent'


@pytest.mark.parametrize('change,reason',[({'root':'c1'},'submission'),({'text':'[removed]'},'unavailable_text'),
                                         ({'text':'x'*1001},'source_record_text_codepoint_limit')])
def test_nonprocessable_records_have_no_metadata_rows_or_calls(change,reason):
    assert m.preprocess_comment(raw(**change),'one',set(),CONFIG,lambda *a:pytest.fail('called'))==(None,reason,0)


def test_frozen_guard_and_above500_metadata_are_not_silently_redefined():
    def response(n):return lambda *a:{'usable':True,'word_tokens':[['x']*n]}
    item,reason,calls=m.preprocess_comment(raw(),'one',set(),CONFIG,response(19))
    assert calls==1 and reason=='below_frozen_record_word_guard'
    item,reason,calls=m.preprocess_comment(raw(),'one',set(),CONFIG,response(501))
    assert calls==1 and reason is None and item['retained_words']==501


def fixture(tmp_path,monkeypatch,cap=1000,duplicate=False):
    monkeypatch.setenv('AHAS_NETWORK_ISOLATION','linux_seccomp_socket_denial')
    monkeypatch.setattr(m.resource,'setrlimit',lambda *a:None)
    calls=[]
    def preprocessing(record,manifest,config):
        calls.append(record['id']);return {'usable':True,'word_tokens':[['x']*20]}
    monkeypatch.setattr(m,'load_engine',lambda plan:(CONFIG,preprocessing,{'implementation_fingerprint':'synthetic'}))
    source=tmp_path/'source';source.mkdir()
    sources=[]
    for community in ('one','two'):
        rows=[]
        for i in range(80):
            rows.append(raw(id=('duplicate' if duplicate and i<2 else f'{community}-{i}'),meta={'subreddit':community}))
        rows.append(raw(id=community+'-unavailable',text='[removed]',meta={'subreddit':community}))
        rows.append(raw(id=community+'-excluded',account='EXCLUDED-0',meta={'subreddit':community}))
        data=b''.join(m.canonical(r) for r in rows)
        path=source/(community+'.zip')
        with zipfile.ZipFile(path,'w') as z:z.writestr('utterances.jsonl',data)
        sources.append({'archive':path.name,'community':community,'bytes':path.stat().st_size,'sha256':m.sha(path),'utterances_bytes':len(data)})
    flags={'accounts':[{'account_key':f'excluded-{i}','pilot1_or_pilot2_or_private_mandatory_exclusion':i<57,
                       'pilot3_selected_scored_exposure':i>=57,'prior_capacity_only_exposure':False} for i in range(117)]}
    fp=tmp_path/'flags.json';fp.write_text(json.dumps(flags))
    plan={'exposure_flags_sha256':m.sha(fp),'sources':sources,'community_pairs':[['one','two']],
          'raw_present_comments_per_community_min':80,'record_word_min':20,'record_word_max':500,
          'limits':{'max_address_space_bytes':4*1024**3,'max_wall_seconds':20,'max_source_rows_per_pass':1000,
                    'max_source_uncompressed_bytes_per_pass':1024**2,'max_preprocessed_records':cap,
                    'max_eligibility_output_bytes':1024**2,'max_private_output_bytes':2*1024**2}}
    pp=tmp_path/'plan.json';pp.write_text(json.dumps(plan))
    registration={'plan_sha256':m.sha(pp),'implementation_sha256':m.sha(m.__file__),'exposure_flags_sha256':m.sha(fp),'test_files':[]}
    rp=tmp_path/'registration.json';rp.write_text(json.dumps(registration))
    return (pp,fp,rp,source,tmp_path/'public',tmp_path/'private'),calls


def test_two_pass_synthetic_metadata_intake_counts_and_bindings(tmp_path,monkeypatch):
    args,calls=fixture(tmp_path,monkeypatch)
    assert m.run(*args)==0
    summary=json.loads((args[4]/'intake-summary.json').read_bytes())
    assert summary['counts']['first_pass_rows']==summary['counts']['second_pass_rows']==164
    assert summary['preprocessing_calls']==summary['counts']['eligibility_metadata_rows']==len(calls)==160
    assert summary['rejections']['unavailable_text']==2
    assert summary['style_distance_calls']==0 and summary['calendar_capacity_evaluated'] is False
    rows=[json.loads(x) for x in (args[5]/'record-eligibility.jsonl').read_text().splitlines()]
    assert len(rows)==160 and all(r['account_key']=='new' for r in rows)
    assert all(not {'text','body','word_tokens'}&set(r) for r in rows)
    assert (args[5]/'record-eligibility.jsonl').stat().st_mode&0o777==0o600


def test_call_cap_fails_before_next_dispatch_and_preserves_partial(tmp_path,monkeypatch):
    args,calls=fixture(tmp_path,monkeypatch,cap=1)
    assert m.run(*args)==1 and len(calls)==1
    report=json.loads((args[4]/'incomplete-intake.json').read_bytes())
    assert report['status']=='incomplete_not_zero_capacity' and report['preprocessing_calls']==1
    assert not (args[4]/'intake-summary.json').exists()


def test_duplicate_id_blocks_preprocessing(tmp_path,monkeypatch):
    args,calls=fixture(tmp_path,monkeypatch,duplicate=True)
    assert m.run(*args)==1 and not calls
    report=json.loads((args[4]/'incomplete-intake.json').read_bytes())
    assert report['error_type']=='ValueError'
