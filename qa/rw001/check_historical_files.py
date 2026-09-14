"""Verify baseline archive files without rewriting historical receipts."""
import hashlib
import json
from pathlib import Path
import tarfile

root=Path(__file__).resolve().parents[2]
allowed={'README.md','pyproject.toml','uv.lock','schemas/results.schema.json',
         'src/account_history_analyzer/__init__.py','src/account_history_analyzer/payload_schemas.py',
         'src/account_history_analyzer/contracts/results.schema.json','src/account_history_analyzer/reporting.py'}
old=root/'release/1.0.3/account-history-analyzer-1.0.3-source-and-reports.tar.gz'
assert hashlib.sha256(old.read_bytes()).hexdigest()=='273356fe8b9b492c1826814c0e1f7c2afb22454279ed978d5e1d3180bed83488'
changed=[];same=[];unexpected=[]
with tarfile.open(old) as archive:
    for member in archive.getmembers():
        if not member.isfile():continue
        name=str(Path(member.name).relative_to('account_history_analyzer_v1'))
        path=root/name
        old_sha=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
        new_sha=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if old_sha==new_sha:same.append(name)
        else:
            changed.append({'path':name,'old_sha256':old_sha,'new_sha256':new_sha})
            if name not in allowed:unexpected.append(name)
result={'status':'passed' if not unexpected else 'failed','baseline_archive_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),
        'byte_identical_existing_files':len(same),'identical_original_test_files':sum(p.startswith('tests/') for p in same),
        'identical_historical_qa_files':sum(p.startswith('qa/') for p in same),
        'identical_historical_output_files':sum(p.startswith('output/') for p in same),
        'documented_changes':changed,'unexpected_changes':unexpected,'old_files_rewritten_as_new_runs':False}
(root/'qa/rw001/historical-preservation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,sort_keys=True))
assert not unexpected
