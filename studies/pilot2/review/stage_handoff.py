"""Assemble an explicit source-free review handoff; never copy dataset trees."""
from pathlib import Path
import hashlib,json,shutil

ROOT=Path(__file__).resolve().parents[1]
REPO=Path('/home/jaykob/Downloads/Account_History_Analyzer_V1_Agent_Handoff/account_history_analyzer_v1')

def main():
    output=ROOT/'public-handoff'
    if output.exists():raise ValueError('Preserve the previous staged handoff')
    selected={}
    def add(path,relative=None):
        assert path.is_file() and not path.is_symlink()
        target=relative or str(path.relative_to(ROOT))
        assert target not in selected
        selected[target]=path
    add(ROOT/'README.md')
    for directory in ('protocol','scripts','tests','logs','review'):
        for path in sorted((ROOT/directory).iterdir()):
            if path.is_file() and path.suffix in {'.md','.html','.json','.csv','.txt','.log','.py','.patch','.png'}:
                add(path)
    for path in sorted((ROOT/'inventory').iterdir()):
        if path.is_file() and path.suffix in {'.json','.log'}:add(path)
    for name in ('RESOURCE_REVIEW.md','profile-summary.json'):add(ROOT/'resources'/name)
    for name in ('GRID_DIAGNOSTICS.md','validation-summary.json','command-receipts.json','source-identity.json'):
        add(ROOT/'diagnostics'/name)
    for path in sorted((ROOT/'diagnostics/logs').iterdir()):
        if path.is_file():add(path)
    for name in ('PREPARATION_SUMMARY.md','preparation-verification.json'):
        add(ROOT/'prepared/streams'/name)
    add(ROOT/'prepared/paired-registered/preparation-summary.json')
    for source,target in [
        ('docs/RW001.md','repair/RW001.md'),('qa/rw001/source.patch','repair/source.patch'),
        ('qa/rw001/changed-files.json','repair/changed-files.json'),
        ('qa/rw001/private-aggregate.json','repair/private-aggregate.json'),
        ('qa/rw001/analytical-freeze.json','repair/analytical-freeze.json'),
        ('release/1.0.4/archive-verification.json','repair/source-release-verification.json')]:add(REPO/source,target)
    for relative,source in sorted(selected.items()):
        target=output/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    manifest={relative:{'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for relative,path in sorted(selected.items())}
    (output/'HANDOFF_FILES.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'staged_files':len(selected)+1,'bytes':sum(row['bytes'] for row in manifest.values()),'raw_datasets_or_source_maps_copied':False}))

if __name__=='__main__':main()
