"""Fresh allowlisted final handoff, with completed receipts and portable links.

The initial staging and its receipt remain historical. The current command's
open logs are deliberately excluded; its completed receipt is delivered beside
the final archive. No source/analytical/frozen study file is modified.
"""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
REPO = Path('/home/jaykob/Downloads/Account_History_Analyzer_V1_Agent_Handoff/account_history_analyzer_v1')


def main():
    stage = ROOT / 'public-handoff-final'
    assert not stage.exists(), 'Preserve prior staging destinations'
    selected = {}

    def add(path, relative=None):
        assert path.is_file() and not path.is_symlink()
        relative = relative or path.relative_to(ROOT).as_posix()
        # These commands have not completed at final-staging snapshot time.
        if relative.startswith(('logs/handoff-final-staging.', 'logs/handoff-packaging.')):
            return
        assert relative not in selected
        selected[relative] = path

    add(ROOT / 'README.md')
    for directory in ('protocol', 'scripts', 'tests', 'logs', 'review'):
        for path in sorted((ROOT / directory).iterdir()):
            if path.is_file() and path.suffix in {'.md', '.html', '.json', '.csv', '.txt', '.log', '.py', '.patch', '.png'}:
                add(path)
    for path in sorted((ROOT / 'inventory').iterdir()):
        if path.is_file() and path.suffix in {'.json', '.log'}:
            add(path)
    for name in ('RESOURCE_REVIEW.md', 'profile-summary.json'):
        add(ROOT / 'resources' / name)
    for name in ('GRID_DIAGNOSTICS.md', 'validation-summary.json', 'command-receipts.json', 'source-identity.json'):
        add(ROOT / 'diagnostics' / name)
    for path in sorted((ROOT / 'diagnostics/logs').iterdir()):
        if path.is_file():
            add(path)
    for name in ('PREPARATION_SUMMARY.md', 'preparation-verification.json'):
        add(ROOT / 'prepared/streams' / name)
    add(ROOT / 'prepared/paired-registered/preparation-summary.json')
    for source, target in (
        ('docs/RW001.md', 'repair/RW001.md'),
        ('qa/rw001/source.patch', 'repair/source.patch'),
        ('qa/rw001/changed-files.json', 'repair/changed-files.json'),
        ('qa/rw001/private-aggregate.json', 'repair/private-aggregate.json'),
        ('qa/rw001/analytical-freeze.json', 'repair/analytical-freeze.json'),
        ('release/1.0.4/archive-verification.json', 'repair/source-release-verification.json'),
    ):
        add(REPO / source, target)
    for relative, source in sorted(selected.items()):
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    # This helper edits only navigation in the distributable copy.
    from portable_handoff_links import transform
    edits = transform(stage)
    assert edits['status'] == 'passed', 'Unresolved portable links in staged review'
    (stage / 'review/PORTABLE_LINK_EDITS.json').write_text(json.dumps(edits, indent=2) + '\n')

    # Include every completed command after the original command index snapshot.
    lines = ['# Final packaging and review commands', '',
             'These completed receipts supplement COMMANDS.md. They are review, browser and packaging preparation checks, not new analytical runs.', '',
             'Final staging, ZIP creation and post-ZIP verification occur after this snapshot; their raw receipts are delivered beside the archive.', '']
    for relative in sorted(selected):
        if not relative.endswith('.receipt.json'):
            continue
        receipt = json.loads((stage / relative).read_text())
        if receipt.get('started_utc', '') < '2026-09-14T19:55:00':
            continue
        lines += [f'## {relative}', '', f"Started UTC: {receipt.get('started_utc')}; exit: {receipt.get('exit_code')}; wall seconds: {receipt.get('wall_seconds')}.", '',
                  f'[Actual receipt](../{relative})', '', '```json', json.dumps(receipt.get('command'), indent=2), '```', '']
    (stage / 'review/FINAL_COMMANDS.md').write_text('\n'.join(lines) + '\n')
    with (stage / 'README.md').open('a') as output:
        output.write('\nFinal review commands are indexed in [FINAL_COMMANDS.md](review/FINAL_COMMANDS.md). '
                     'Navigation-only edits in this distributable copy are recorded in '
                     '[PORTABLE_LINK_EDITS.json](review/PORTABLE_LINK_EDITS.json). '
                     'The final ZIP verification and completed packaging receipts are supplied beside the archive.\n')
    manifest = {}
    for path in sorted(stage.rglob('*')):
        if path.is_file():
            content = path.read_bytes()
            manifest[path.relative_to(stage).as_posix()] = {'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
    (stage / 'HANDOFF_FILES.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'staged_files': len(manifest) + 1, 'data_bytes': sum(row['bytes'] for row in manifest.values()),
                      'source_inputs_copied': False, 'link_transform_receipt': 'review/PORTABLE_LINK_EDITS.json',
                      'in_flight_command_logs_copied': False}))


if __name__ == '__main__':
    main()
