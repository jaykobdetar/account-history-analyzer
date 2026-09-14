"""Synthetic paired-adapter contracts; no real held-out data or style scoring."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import zipfile
import pytest
import prepare_pairs as p


def item(identifier,day,words=150,community='Cornell'):
    instant=(datetime(2017,5,16,tzinfo=timezone.utc)+timedelta(days=day)).isoformat().replace('+00:00','Z')
    return {'record':{'id':identifier,'created_utc':instant,'subreddit':community,'text':'unaltered '+identifier},'retained_words':words}


def test_centered_whole_records_guard_overshoot_and_no_refill():
    rows=[item(str(i),i-5) for i in range(10)]
    chosen=p.select_centered(rows,1000,8,'2017-05-16T00:00:00Z')
    assert len(chosen)==8 and sum(row['retained_words'] for row in chosen)==1200
    assert chosen==p.canonical_order(chosen)
    assert p.unit_stats(chosen,1000,8)['overshoot_words']==200
    short=p.select_centered([item('long',0,5000)],1000,8,'2017-05-16T00:00:00Z')
    assert len(short)==1 and not p.unit_stats(short,1000,8)['qualified_for_production_comparison']
    assert p.shared_budget([[],rows,rows,rows])==1000
    assert p.shared_budget([rows]*4)==1500


def test_exact_three_matchings_and_missing_median_fallback():
    accounts=[{'account_key':str(i),'author_rank_hash':str(i)} for i in range(4)]
    offsets=[0,100,10,90]
    cells={(str(i),cell):[item(str(i),offsets[i])] for i in range(4) for cell in ['early','late']}
    blocks,summary=p.pair_blocks(accounts,cells)
    assert [[a['account_key'],b['account_key']] for a,b in blocks]==[['0','2'],['1','3']]
    assert summary['summed_cell_median_gap_seconds']==40*86400
    cells['0','early']=[]
    blocks,summary=p.pair_blocks(accounts,cells)
    assert [[a['account_key'],b['account_key']] for a,b in blocks]==[['0','1'],['2','3']]
    assert summary['summed_cell_median_gap_seconds'] is None


def test_all_omissions_preserve_survivors_and_exact_middle_rule():
    rows=[item(str(i),i,community='Cornell' if i==2 else 'college') for i in range(5)]
    before=deepcopy(rows)
    assert [row['record']['id'] for row in p.omit(rows,'middle50','s')]==['0','3','4']
    assert [row['record']['id'] for row in p.omit(rows,'drop_Cornell','s')]==['0','1','3','4']
    for arm in ['full','middle50','hash50','drop_Cornell']:
        assert all(row in rows for row in p.omit(rows,arm,'s'))
    assert rows==before


def test_global_home_and_split_casefold_before_shortlist():
    plan={'communities':['Cornell','college'],'splits':['development','evaluation','confirmation'],
          'salts':{'author_rank':'rank','author_split':'split'},'paired':{'pre_shortlist_per_home_community_per_split':20}}
    frame=[{'source_account':name,'community':community,'years':{'2017':{'present_raw_codepoints':volume},'2018':{'present_raw_codepoints':volume}}}
           for name,community,volume in [('Person','Cornell',100),('PERSON','college',200),('old','Cornell',900),('AutoModerator','Cornell',900)]]
    shortlist,_,_=p.choose_shortlist(frame,plan,{'old'})
    assert len(shortlist)==1 and shortlist[0]['account_key']=='person' and shortlist[0]['home_community']=='college'
    assert p.choose_shortlist(list(reversed(frame)),plan,{'old'})[0]==shortlist


@pytest.fixture
def prepared_candidates(tmp_path,monkeypatch):
    root=tmp_path/'study';old=tmp_path/'old';root.mkdir();(old/'inputs/public').mkdir(parents=True)
    (old/'inputs/public/source-map.json').write_text('{"accounts":[]}')
    monkeypatch.setattr(p,'ROOT',root);monkeypatch.setattr(p,'OLD',old);monkeypatch.setattr(p,'binding',lambda plan:None)
    plan=json.loads((Path(__file__).parents[1]/'protocol/plan.json').read_bytes())
    plan['communities']=['Cornell'];plan['paired']['pre_shortlist_per_home_community_per_split']=4
    authors={split:[] for split in plan['splits']};index=0
    while any(len(values)<4 for values in authors.values()):
        name='synthetic_author_'+str(index);index+=1
        split=plan['splits'][int(p.hashed(plan['salts']['author_split'],name),16)%3]
        if len(authors[split])<4:authors[split].append(name)
    frame=[];source=[]
    for split,names in authors.items():
        for name in names:
            frame.append({'source_account':name,'community':'Cornell','years':{'2017':{'present_raw_codepoints':9000},'2018':{'present_raw_codepoints':9000}}})
            for year in [2017,2018]:
                for i in range(8):
                    identifier=f'{name}-{year}-{i}';instant=datetime(year,5,12+i,tzinfo=timezone.utc)
                    source.append({'id':identifier,'user':name,'root':'thread-'+identifier,'reply_to':'parent-'+identifier,
                        'timestamp':int(instant.timestamp()),'text':('the word '+chr(97+i)+' ')*60,
                        'meta':{'subreddit':'Cornell','permalink':'https://example.invalid/comments/'+identifier}})
    path=root/'data/Cornell.zip';path.parent.mkdir()
    with zipfile.ZipFile(path,'w') as archive:archive.writestr('utterances.jsonl',b''.join(p.canonical_bytes(row) for row in source))
    plan['source_archives']={'Cornell':{'path':'data/Cornell.zip','sha256':p.file_sha(path)}}
    frame_path=root/'inventory/private/source-frame.jsonl';p.write(frame_path,frame,jsonl=True)
    p.write(root/'inventory/source-frame-summary.json',{'restricted_frame_sha256':p.file_sha(frame_path)})
    plan_path=root/'plan.json';p.write(plan_path,plan)
    out=root/'prepared/paired';p.candidates(plan,plan_path,out)
    return plan,plan_path,out,source


def test_candidate_source_fidelity_schemas_and_confirmation_exclusion(prepared_candidates):
    plan,plan_path,out,source=prepared_candidates
    originals={row['id']:row for row in source};pool=p.read_rows(out/'private/candidate-pool.jsonl')
    assert len(pool)==len(originals)==192
    for row in pool:
        actual=row['record'];original=originals[actual['id']]
        p.validate(actual,'record')
        assert actual['text']==original['text'] and actual['created_utc']==p.utc(original['timestamp'])
        assert actual['thread_id']==original['root'] and actual['parent_id']==original['reply_to']
        assert not {'split','label','account_key','retained_words'}&set(actual)
    audit={'status':'audited','candidate_pool_sha256':p.file_sha(out/'private/candidate-pool.jsonl'),
        'purge_record_ids':[],'near_duplicate_clusters':[{'cluster_id':'cluster-'+row['record']['id'],'record_ids':[row['record']['id']]} for row in pool],
        'limitations':['synthetic_adapter_contract_fixture_only_not_a_real_leakage_audit']}
    audit_path=out/'audit.json';p.write(audit_path,audit)
    p.finalize(plan,plan_path,out,audit_path)
    units=json.loads((out/'private/units.json').read_bytes())
    confirmation={unit['text_id'] for unit in units if unit['split']=='confirmation'}
    assert confirmation and all(unit['input'].startswith('confirmation/') for unit in units if unit['split']=='confirmation')
    for path in (out/'scored/datasets').glob('*.json'):
        document=json.loads(path.read_bytes());p.validate(document,'evaluation_paired_text')
        assert not ({unit['text_id'] for unit in document['texts']}&confirmation)
        assert {pair['split'] for pair in document['pairs']}=={'development','evaluation'}
        for unit in document['texts']:
            assert 'confirmation' not in unit['input']
            p.load_snapshot((path.parent/unit['input']).resolve(),(path.parent/unit['manifest']).resolve())
    empty=[unit for unit in units if unit['arm']=='drop_Cornell']
    assert empty and all(unit['stats']['actual_eligible_words']==0 and unit['stats']['largest_record_share'] is None for unit in empty)
    assert all('thread' not in unit['groups'] and 'near_duplicate_cluster' not in unit['groups'] for unit in empty)


def test_incomplete_audit_blocks_finalization(prepared_candidates):
    plan,plan_path,out,_=prepared_candidates
    path=out/'audit-not-complete.json';p.write(path,{'status':'not_auditable','candidate_pool_sha256':p.file_sha(out/'private/candidate-pool.jsonl')})
    with pytest.raises(ValueError,match='complete'):p.finalize(plan,plan_path,out,path)
    assert not (out/'scored').exists()


def test_thread_purge_is_symmetric_and_includes_confirmation():
    pool=[{'record':{'id':identifier,'thread_id':thread},'split':split}
          for identifier,thread,split in [('a','shared','development'),('b','shared','evaluation'),
                                          ('c','shared','confirmation'),('d','onlydev','development')]]
    threads,ids=p.thread_exclusions(pool)
    assert threads=={'shared'} and ids=={'a','b','c'}

