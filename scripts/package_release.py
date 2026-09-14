#!/usr/bin/env python3
"""Create a deterministic source/report archive, excluding environments and caches."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tomllib

ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'.git','.venv','.uv-cache','.pytest_cache','.hypothesis','__pycache__','release'}


def included(path):
    relative=path.relative_to(ROOT)
    if any(part in EXCLUDED for part in relative.parts) or path.is_symlink() or path.suffix=='.pyc':
        return False
    if relative.parts[0]=='benchmarks' and any(part.endswith('-report') for part in relative.parts):
        return False
    if relative.parts[0]=='qa' and any(part in {'arithmetic-preview','container-output','wheel-output','rerender'} for part in relative.parts):
        return False
    return path.is_file()


def main():
    files=sorted(path for path in ROOT.rglob('*') if included(path))
    checks={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    version=tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
    # Each release gets its own receipts; packaging an update must not replace
    # the original archive's hash inventory or claim those runs used new code.
    destination=ROOT/'release'/version;destination.mkdir(parents=True,exist_ok=True)
    archive=destination/f'account-history-analyzer-{version}-source-and-reports.tar.gz'
    with archive.open('wb') as raw, gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed:
        with tarfile.open(fileobj=compressed,mode='w|',format=tarfile.PAX_FORMAT) as tar:
            for path in files:
                data=path.read_bytes()
                info=tarfile.TarInfo('account_history_analyzer_v1/'+str(path.relative_to(ROOT)))
                info.size=len(data);info.mtime=0;info.mode=0o644;info.uid=info.gid=0
                tar.addfile(info,io.BytesIO(data))
    (destination/'source-file-checksums.json').write_text(json.dumps(checks,sort_keys=True,indent=2)+'\n')
    distributions={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in sorted((ROOT/'dist').glob('*')) if path.is_file() and not path.name.startswith('.')}
    distributions[str(archive.relative_to(ROOT))]=hashlib.sha256(archive.read_bytes()).hexdigest()
    (destination/'SHA256SUMS.txt').write_text(''.join(f'{value}  {name}\n' for name,value in sorted(distributions.items())))
    print(json.dumps({'archive':str(archive),'files':len(files),'bytes':archive.stat().st_size,'sha256':distributions[str(archive.relative_to(ROOT))]},sort_keys=True))


if __name__=='__main__':
    main()
