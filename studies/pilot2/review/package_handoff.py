"""Package an explicitly staged review; source datasets are never traversed.

The directory manifest is verified before packaging. ZIP timestamps, order,
permissions and compression parameters are explicit. Rebuilding in this process
must reproduce the archive bytes; this is not a cross-platform identity claim.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile
import zlib


def digest(value):
    return hashlib.sha256(value).hexdigest()


def build(files, destination):
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9, strict_timestamps=True) as archive:
        for relative, content in sorted(files.items()):
            entry = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, content, compresslevel=9)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', type=Path)
    parser.add_argument('archive', type=Path)
    parser.add_argument('verification', type=Path)
    args = parser.parse_args()
    assert not args.archive.exists() and not args.verification.exists(), 'Preserve prior packages'
    files = {}
    for path in sorted(args.stage.rglob('*')):
        assert not path.is_symlink(), 'Symlink in staged handoff'
        if path.is_file():
            files[path.relative_to(args.stage).as_posix()] = path.read_bytes()
    manifest = json.loads(files['HANDOFF_FILES.json'])
    assert set(files) == set(manifest) | {'HANDOFF_FILES.json'}
    for name, row in manifest.items():
        assert row == {'bytes': len(files[name]), 'sha256': digest(files[name])}, name
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    build(files, args.archive)
    second = io.BytesIO()
    build(files, second)
    actual = args.archive.read_bytes()
    assert actual == second.getvalue(), 'Same-runtime archive reconstruction differs'
    with zipfile.ZipFile(args.archive) as archive:
        assert archive.namelist() == sorted(files)
        assert archive.testzip() is None
        assert {name: archive.read(name) for name in archive.namelist()} == files
    receipt = {
        'archive': args.archive.name, 'bytes': len(actual), 'sha256': digest(actual),
        'files': len(files), 'uncompressed_bytes': sum(map(len, files.values())),
        'staged_manifest_sha256': digest(files['HANDOFF_FILES.json']),
        'every_member_equals_staged_bytes': True, 'duplicate_or_extra_members': False,
        'same_runtime_second_build_byte_identical': True,
        'cross_platform_byte_identity_claimed': False,
        'python': sys.version, 'zlib_runtime': zlib.ZLIB_RUNTIME_VERSION,
        'privacy_scope': 'Raw corpus/private prose, source maps and native source-containing outputs omitted; separately checked by final handoff audit.'
    }
    args.verification.write_text(json.dumps(receipt, indent=2) + '\n')
    args.archive.with_suffix('.zip.sha256').write_text(digest(actual) + '  ' + args.archive.name + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
