#!/usr/bin/env python3
"""Independent source-record check; never extracts analytical comparison features."""
import hashlib,json,os,sys,zipfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    with path.open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()

def main():
    assert os.environ.get('AHAS_NETWORK_ISOLATION')=='linux_seccomp_socket_denial'
    registration=json.loads((ROOT/'protocol/registration.json').read_bytes())
    for path,expected in registration['files'].items():assert sha(ROOT/path)==expected,path
    plan=json.loads((ROOT/'protocol/plan.json').read_bytes())
    prepared=ROOT/'prepared/paired'
    selection=json.loads((prepared/'private/selection.json').read_bytes())
    rows=[json.loads(line) for line in (prepared/'private/candidate-pool.jsonl').read_bytes().splitlines()]
    assert sha(prepared/'private/candidate-pool.jsonl')==selection['candidate_pool_sha256']
    records={row['record']['id']:row for row in rows}
    assert len(records)==len(rows)
    accounts={row['account_key']:row for row in selection['accounts']}
    assert len(accounts)==36
    assert set(Counter((row['home_community'],row['split']) for row in accounts.values()).values())=={4}
    old=json.loads((ROOT.parent/'ahas-realworld-review/inputs/public/source-map.json').read_bytes())
    assert not set(accounts)&{row['source_account'].casefold() for row in old['accounts']}
    verified=set();counts=Counter()
    for community,item in plan['source_archives'].items():
        archive_path=(ROOT/item['path']).resolve()
        assert sha(archive_path)==item['sha256']
        with zipfile.ZipFile(archive_path) as archive,archive.open('utterances.jsonl') as source:
            for line in source:
                raw=json.loads(line);identifier=raw['id']
                if identifier not in records:continue
                assert identifier not in verified
                row=records[identifier];record=row['record'];account=accounts[raw['user'].casefold()]
                timestamp=datetime.fromtimestamp(raw['timestamp'],timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                assert record['text']==raw['text']
                assert record['created_utc']==timestamp
                assert raw['root']!=identifier and record['kind']=='comment'
                assert record['thread_id']==raw['root'] and record['parent_id']==raw['reply_to']
                assert record['permalink']==raw['meta']['permalink']
                assert record['subreddit']==raw['meta']['subreddit']==community
                assert record['status']=='present' and record['language'] is None
                assert record['edit_state']=='unknown' and record['edited_utc'] is None
                assert record['parent_created_utc'] is None and record['title'] is None
                assert record['account_id']==account['account_alias']
                assert row['account_key']==raw['user'].casefold()
                assert row['split']==account['split'] and row['home_community']==account['home_community']
                assert row['source_line_sha256']==hashlib.sha256(line).hexdigest()
                cell=plan['paired'][row['cell']]
                assert cell['start_utc']<=timestamp<cell['end_utc']
                assert row['retained_words']>=20
                verified.add(identifier);counts[community]+=1
    assert verified==set(records)
    result={'status':'passed','source_record_count':len(verified),'source_records_by_community':dict(counts),
            'selected_account_count':len(accounts),'old_selected_account_overlap':0,
            'source_text_ids_timestamps_links_and_statuses_preserved':True,
            'word_counts_scope':'Existing preparation eligibility counts checked against guard; no independent word-token recomputation in this check.',
            'registered_files_unchanged':True,'candidate_pool_sha256':selection['candidate_pool_sha256'],
            'scores_computed':False}
    with (ROOT/'inventory/candidate-fidelity.json').open('x') as target:json.dump(result,target,indent=2);target.write('\n')
    print(json.dumps(result))

if __name__=='__main__':main()
