"""Verify original source bytes and every selected input field, without scoring."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
P4=Path(__file__).resolve().parents[2]/'pilot4_chronological_controls'
sys.path.insert(0,str(P4/'scripts'))
from finalize_chronology_inputs import original_comment_record
from run_full_chronology import sha,write


def main():
    p=argparse.ArgumentParser()
    for k in ('plan','prepared','out'):p.add_argument('--'+k,required=True,type=Path)
    a=p.parse_args();plan=json.loads(a.plan.read_bytes())
    for binding in plan['bindings']:
        assert sha(binding['path'])==binding['sha256'],'Registered source changed'
    root=Path(plan['pool']).parent
    pool={e['record']['id']:e for e in map(json.loads,Path(plan['pool']).read_text().splitlines())}
    metadata=json.loads((root/'selection.json').read_bytes())['selected_metadata']
    offsets=json.loads((root/'original-source-index.json').read_bytes())
    prepared=json.loads((a.prepared/'selection.json').read_bytes())
    ids={r for records in prepared['source_samples'].values() for r in records}
    audit=json.loads(Path(plan['audit']).read_bytes())
    assert ids<=set(audit['surviving_candidate_ids'])
    byte_count=0
    with (root/'original-source-lines.jsonl').open('rb') as f:
        for rid in ids:
            ref=offsets[rid];f.seek(ref['offset']);raw=f.read(ref['bytes']);byte_count+=len(raw)
            assert hashlib.sha256(raw).hexdigest()==ref['sha256']==metadata[rid]['source_line_sha256']
            assert original_comment_record(json.loads(raw))==pool[rid]['record']
    index=json.loads((a.prepared/'index.json').read_bytes());appearances=0
    for binding in index['bound_files']:
        assert sha(binding['path'])==binding['sha256']
    for case,key in zip(index['cases'],('late_AX','late_BX','late_AY','late_BY'),strict=True):
        expected=prepared['source_samples']['anchor']+prepared['source_samples'][key]
        records=[json.loads(line) for line in Path(case['input']).read_text().splitlines()]
        assert [r['id'] for r in records]==expected
        for r in records:
            assert r==dict(pool[r['id']]['record'],account_id=case['case_id'])
            appearances+=1
    report={'status':'passed','original_source_records_verified':len(ids),'original_source_bytes_verified':byte_count,
            'input_record_appearances_verified':appearances,'histories':len(index['cases']),
            'only_changed_record_field':'uniform account_id alias','selected_records_all_audited_survivors':True,
            'style_calls':0,'new_preprocessor_calls':0,'checker_sha256':sha(__file__),
            'input_index_sha256':sha(a.prepared/'index.json'),'selection_registration_sha256':sha(a.plan),
            'original_source_lines_sha256':sha(root/'original-source-lines.jsonl'),
            'original_source_index_sha256':sha(root/'original-source-index.json')}
    write(a.out,report);print(json.dumps(report))


if __name__=='__main__':main()
