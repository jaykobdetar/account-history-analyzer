"""Verify a Pilot6 export and preserve every existing repository file except its three indexes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser()
    for name in ('source', 'export', 'repo', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--baseline', required=True)
    a = p.parse_args()
    manifest = json.loads((a.export/'PUBLIC_EXPORT_MANIFEST.json').read_bytes())
    rows = {r['path']: r for r in manifest['files']}
    assert len(rows) == len(manifest['files']) == manifest['file_count_excluding_this_manifest']
    originals = {str(f.relative_to(a.source)): f for f in a.source.rglob('*')
                 if f.is_file() and '__pycache__' not in f.parts and f.suffix != '.pyc'}
    exports = {str(f.relative_to(a.export)): f for f in a.export.rglob('*') if f.is_file()}
    assert set(originals) == set(rows)
    assert set(exports) == set(rows) | {'PUBLIC_EXPORT_MANIFEST.json'}
    code = 0
    for name, row in rows.items():
        original, published = originals[name], exports[name]
        assert not original.is_symlink() and not published.is_symlink()
        before, after = original.read_bytes(), published.read_bytes()
        assert (len(before), sha(before)) == (row['original_bytes'], row['original_sha256'])
        assert (len(after), sha(after)) == (row['published_bytes'], row['published_sha256'])
        if original.suffix == '.py':
            assert before == after and row['executable_source_unchanged'] is True
            code += 1
    allowed = {'README.md', 'studies/README.md', 'docs/DOCUMENTATION_INDEX.md'}
    tree = subprocess.check_output(['git', 'ls-tree', '-rz', a.baseline], cwd=a.repo)
    unchanged, changed, prefix_counts, baseline_names = 0, [], {}, set()
    for entry in tree.split(b'\0'):
        if not entry:
            continue
        head, raw_name = entry.split(b'\t', 1)
        mode, kind, expected = head.decode().split()
        name = raw_name.decode()
        baseline_names.add(name)
        assert kind == 'blob', 'Unexpected Git object kind'
        f = a.repo/name
        assert f.exists() or f.is_symlink(), 'A baseline file is missing'
        data = str(f.readlink()).encode() if mode == '120000' else f.read_bytes()
        actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if actual != expected:
            assert name in allowed, 'Unexpected modification of existing repository evidence'
            changed.append(name)
        else:
            unchanged += 1
        for prefix in ('src/account_history_analyzer/', 'studies/pilot1/', 'studies/pilot2/',
                       'studies/pilot3_cross_context/', 'studies/pilot4_chronological_controls/',
                       'studies/pilot5_shared_anchor/'):
            if name.startswith(prefix):
                assert actual == expected
                prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
    listed = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=a.repo)
    added = {n.decode() for n in listed.split(b'\0') if n} - baseline_names
    assert all(n.startswith(('studies/pilot6_shared_anchor_replication/', 'provenance/pilot6-publication/')) for n in added)
    missing = []
    docs = list(a.export.rglob('*.md')) + [a.repo/n for n in sorted(allowed)]
    checked_links = 0
    for doc in docs:
        for match in re.finditer(r'\[[^\]\n]*\]\(([^)\n]+)\)', doc.read_text()):
            target = match.group(1).strip().strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
                continue
            target = unquote(target.split('#', 1)[0])
            if not target:
                continue
            checked_links += 1
            if not (doc.parent/target).resolve().exists():
                missing.append({'document': str(doc.relative_to(a.repo)), 'target': target})
    assert not missing, json.dumps(missing)
    report = {'status': 'passed', 'baseline_commit': a.baseline,
              'existing_files_byte_identical': unchanged, 'changed_navigation_files': sorted(changed),
              'new_files_in_permitted_study_and_publication_directories': len(added),
              'preserved_prefix_file_counts': prefix_counts,
              'export_files_excluding_manifest': len(rows), 'executable_sources_byte_identical': code,
              'public_export_manifest_sha256': sha((a.export/'PUBLIC_EXPORT_MANIFEST.json').read_bytes()),
              'local_file_links_checked': checked_links, 'missing_local_file_links': 0,
              'checker_sha256': sha(Path(__file__).read_bytes()), 'analyzer_calls': 0,
              'scope': 'Every exported byte against its source/export manifest; every pre-existing tracked file against the baseline Git object, except three navigation documents. Markdown file targets checked; heading anchors and remote links are outside this check.'}
    with a.out.open('x') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
