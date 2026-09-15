"""Extend immutable prior protection inventory with pilot3's scored source rows.

This mechanical source-row copy performs no style calculation or manual prose
inspection; prior reserve sources remain unchanged and only enter the audit.
"""
import argparse
import json
from pathlib import Path
from run_full_chronology import sha,write


def extend(old_inventory,cohort,pool,out,public_receipt):
    original=json.loads(Path(old_inventory).read_bytes())
    selected=json.loads(Path(cohort).read_bytes())
    ids=set(selected['selected_record_ids'])
    if len(ids)!=5773:raise ValueError('Unexpected frozen pilot3 selected membership')
    out=Path(out);out.mkdir(mode=0o700,exist_ok=False)
    path=out/'pilot3-scored-original-records.jsonl'
    found=set();metadata=[];accounts=set()
    with Path(pool).open() as source,path.open('x') as target:
        for line in source:
            row=json.loads(line);rid=row['record']['id']
            if rid not in ids:continue
            if rid in found:raise ValueError('Duplicate original identity')
            found.add(rid);accounts.add(row['account_key'])
            item={'record':row['record'],'account_key':row['account_key'],'split':'evaluation'}
            target.write(json.dumps(item,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n')
            metadata.append({'record_id':rid,'account_key':row['account_key'],'original_split':'evaluation'})
    if found!=ids or len(accounts)!=60:raise ValueError('Incomplete pilot3 scored protection source')
    source={'path':str(path.resolve()),'bytes':path.stat().st_size,'sha256':sha(path),
            'source_id':'pilot3_scored_full_cohort','collection':'pilot3_scored_full_cohort',
            'format':'wrapped_record_jsonl','record_count':len(found),'records_metadata':metadata,
            'account_keys':sorted(accounts),'distinct_source_accounts':len(accounts),
            'prose_inspected_by_model':False,'feature_vectors_read':False}
    extended={**original,'files':original['files']+[source],
        'total_source_files':original['total_source_files']+1,
        'total_source_record_rows':original['total_source_record_rows']+len(found),
        'total_source_file_bytes':original['total_source_file_bytes']+path.stat().st_size,
        'pilot4_extension':{'original_inventory_sha256':sha(old_inventory),'pilot3_cohort_sha256':sha(cohort),
                            'pilot3_candidate_pool_sha256':sha(pool),'script_sha256':sha(__file__),
                            'purpose':'Automatic thread/content exclusion only; no design based on prior protected prose or features.'}}
    inventory=out/'historical-audit-source-inventory.json';write(inventory,extended)
    write(public_receipt,{'prior_inventory_sha256':sha(old_inventory),'extended_inventory_sha256':sha(inventory),
        'added_records':len(found),'added_source_accounts':len(accounts),'source_file_count':len(extended['files']),
        'added_source_sha256':sha(path),'script_sha256':sha(__file__),'style_scores_computed':0,
        'prior_missing_content_limitations_preserved':True,'prior_sources_modified':False})


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('old-inventory','cohort','pool','out','public-receipt'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();extend(a.old_inventory,a.cohort,a.pool,a.out,a.public_receipt)
