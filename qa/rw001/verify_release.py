"""Check every release archive member against its frozen manifest."""
import hashlib
import json
from pathlib import Path
import tarfile
import zipfile

root=Path(__file__).resolve().parents[2]
release=root/'release/1.0.4'
archive=release/'account-history-analyzer-1.0.4-source-and-reports.tar.gz'
manifest=json.loads((release/'source-file-checksums.json').read_bytes())
wheel=root/'dist/account_history_analyzer-1.0.4-py3-none-any.whl'
tested=json.loads((root/'qa/rw001/container-wheel/verification.json').read_bytes())
assert hashlib.sha256(wheel.read_bytes()).hexdigest()==tested['production_wheel_sha256']
observed={}
with tarfile.open(archive) as bundle:
    for item in bundle:
        assert item.isfile() and not item.issym() and not item.islnk()
        relative=Path(item.name).relative_to('account_history_analyzer_v1')
        assert not relative.is_absolute() and '..' not in relative.parts
        name=str(relative)
        assert name not in observed
        observed[name]=hashlib.sha256(bundle.extractfile(item).read()).hexdigest()
assert observed==manifest
for name in ('requirements.lock.txt','containers/build-requirements.lock','src/account_history_analyzer/reporting.py',
             'dist/account_history_analyzer-1.0.4-py3-none-any.whl','docs/RW001.md'):
    assert observed[name]==hashlib.sha256((root/name).read_bytes()).hexdigest()
prohibited=[name for name in observed if any(part in {'ahas-realworld-review','inputs','source-map.json',
             'unmodeled_metadata.jsonl','Cornell.corpus.zip','export_thereal4982_20260914.zip'} for part in Path(name).parts)
             and not name.startswith('benchmarks/input/')]
assert not prohibited
with zipfile.ZipFile(wheel) as package:
    assert package.read('account_history_analyzer/reporting.py')==(root/'src/account_history_analyzer/reporting.py').read_bytes()
result={'status':'passed','archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'archive_bytes':archive.stat().st_size,'members_checked':len(observed),
        'all_members_match_manifest':True,'tested_production_wheel_sha256':tested['production_wheel_sha256'],
        'private_input_or_map_paths_present':prohibited,
        'privacy_scope':'Package member-path and known private-dataset exclusion checks; private QA data resides outside repository',
        'source_identity':tested['implementation_fingerprint']}
(release/'archive-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,sort_keys=True))
