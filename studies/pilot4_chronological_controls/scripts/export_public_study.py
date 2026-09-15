"""Create a sanitized publication copy with original-to-published byte mappings."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    source = args.source.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    workspace = source.parents[1]
    visual = Path('/home/jaykob/.codex/visualizations/2026/09/14/01a0a1b3-d799-70b2-9746-932405f84cdf')
    replacements = [(str(visual/'pilot4_private'), '<PRIVATE_PILOT4>'),
                    (str(visual/'pilot3_private'), '<PRIVATE_PILOT3>'),
                    (str(visual), '<PRIVATE_WORK_AREA>'),
                    (str(workspace), '<WORKSPACE>'),
                    ('/tmp/ahas-pilot3-reviewed-repo', '<REVIEWED_REPO>'),
                    ('/tmp/ahas-pilot3-installed', '<INSTALLED_BASELINE>'),
                    ('/tmp/ahas-pilot4-matching-installed', '<ISOLATED_MATCHING_LIBRARY>'),
                    ('/tmp/ahas-pilot4-matching-wheel', '<ISOLATED_MATCHING_WHEEL>')]
    sha = lambda data: hashlib.sha256(data).hexdigest()
    rows = []
    for file in sorted(source.rglob('*')):
        if not file.is_file() or '__pycache__' in file.parts or file.suffix == '.pyc':
            continue
        if file.is_symlink():
            raise ValueError('Refuse to publish symlink')
        relative = file.relative_to(source)
        if relative.as_posix() == 'PUBLIC_EXPORT_MANIFEST.json':
            raise ValueError('Original evidence must not already contain a publication manifest')
        original = file.read_bytes(); transformed = original
        substitutions = []
        if file.suffix != '.py':
            value = original.decode('utf-8')
            for old, placeholder in replacements:
                if old in value:
                    value = value.replace(old, placeholder)
                    substitutions.append(placeholder)
            transformed = value.encode('utf-8')
        target = args.out/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.open('xb').write(transformed)
        rows.append({'path':relative.as_posix(), 'original_bytes':len(original),
                     'original_sha256':sha(original), 'published_bytes':len(transformed),
                     'published_sha256':sha(transformed), 'path_placeholders_applied':substitutions,
                     'executable_source_unchanged':file.suffix=='.py' and transformed==original})
    result = {'created_utc':datetime.now(timezone.utc).isoformat(), 'files':rows,
              'file_count_excluding_this_manifest':len(rows), 'publication_only':True,
              'original_frozen_hashes_preserved_in_receipts':True,
              'private_corpus_artifacts_included':False,
              'excluded_artifact_types':['__pycache__','*.pyc'],
              'explanation':'Original evidence is immutable. Non-code public copies replace host paths; code bytes are unchanged. Use original_sha256 to reconcile original registrations, and published_sha256 to verify this export.'}
    (args.out/'PUBLIC_EXPORT_MANIFEST.json').open('x').write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'exported_files':len(rows),'path_transformed_files':sum(bool(r['path_placeholders_applied']) for r in rows),
                      'source_files_byte_identical':sum(r['executable_source_unchanged'] for r in rows)}))


if __name__ == '__main__':
    main()
