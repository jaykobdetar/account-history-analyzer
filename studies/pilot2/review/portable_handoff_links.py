#!/usr/bin/env python3
"""Rewrite only links in an explicit staging copy; preserve original artifacts.

The original preparation review used absolute desktop file links. Their public
staging copies can use relative links to the same included files. Historical
commands, JSON receipts, numerical outputs, and original Markdown stay intact.
Run before rebuilding HANDOFF_FILES.json and the final archive.
"""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
import argparse, hashlib, json, os, re
from markdown_it import MarkdownIt

ORIGINAL_ROOT = Path('/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914')


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in {'href', 'src', 'data', 'action'}:
                self.links.append((tag, key, value))
            if key == 'id':
                self.ids.add(value)


def scan(bundle):
    records = []
    files = sorted(path for path in bundle.rglob('*') if path.suffix in {'.md', '.html'})
    for path in files:
        parser = Links()
        content = path.read_text()
        parser.feed(content if path.suffix == '.html' else MarkdownIt('commonmark', {'html': True}).render(content))
        for tag, attribute, value in parser.links:
            url = urlsplit(value)
            if url.scheme or url.netloc:
                status = 'external_not_requested' if url.scheme in {'http', 'https', 'mailto'} else 'unsupported_scheme'
            else:
                target = (path.parent / unquote(url.path)).resolve() if url.path else path
                if not target.is_relative_to(bundle):
                    status = 'outside_bundle'
                elif not target.exists():
                    status = 'missing'
                else:
                    status = 'local_ok'
                    if url.fragment and target.suffix == '.html':
                        target_parser = Links()
                        target_parser.feed(target.read_text())
                        if unquote(url.fragment) not in target_parser.ids:
                            status = 'missing_html_fragment'
            records.append({'document': str(path.relative_to(bundle)), 'tag': tag,
                'attribute': attribute, 'target': value, 'status': status})
    return len(files), records


def transform(stage: Path, *, rewrite: bool = True) -> dict:
    """Transform an explicitly named public staging copy; return a receipt.

    The caller writes HANDOFF_FILES.json after this function. Repeated calls
    are idempotent: already-relative targets and an existing CSV link stay as-is.
    """
    bundle = stage.resolve()
    if bundle == ORIGINAL_ROOT.resolve() or ORIGINAL_ROOT.resolve().is_relative_to(bundle):
        raise ValueError('Refusing to operate on the original study or an ancestor')
    if not bundle.name.startswith('public-handoff') or not (bundle / 'README.md').is_file() or not (bundle / 'review/REVIEW.md').is_file():
        raise ValueError('Explicit public-handoff staging directory with README and review required')
    document_count, before = scan(bundle)
    modifications = []
    protected = {}
    pattern = re.compile(r'(?<=\]\()' + re.escape(str(ORIGINAL_ROOT)) + r'/([^\s)]+)(?=\))')
    if rewrite:
        for path in sorted(bundle.rglob('*.md')):
            if path.is_symlink() or not path.resolve().is_relative_to(bundle):
                raise ValueError('Refusing a staged symlink')
            text = path.read_text()
            replacements = []

            def replace(match):
                relative = Path(match.group(1))
                original = (ORIGINAL_ROOT / relative).resolve()
                target = (bundle / relative).resolve()
                if not original.is_relative_to(ORIGINAL_ROOT) or not target.is_relative_to(bundle) or not target.is_file():
                    raise ValueError('Absolute link does not map to an included staged file')
                protected[str(original)] = sha(original)
                new = Path(os.path.relpath(target, path.parent)).as_posix()
                replacements.append({'old_target': match.group(0), 'new_target': new})
                return new

            revised = pattern.sub(replace, text)
            if replacements:
                source_original = ORIGINAL_ROOT / path.relative_to(bundle)
                if source_original.is_file():
                    protected[str(source_original)] = sha(source_original)
                old_sha = sha(path)
                path.write_text(revised)
                modifications.append({'staged_document': str(path.relative_to(bundle)),
                    'before_sha256': old_sha, 'after_sha256': sha(path), 'replacements': replacements})
        # The main review promises linked JSON/CSV exports. The actual CSV is
        # present, but its original companion report did not expose a link.
        if not (bundle / 'review/paired-metrics.csv').is_file():
            raise ValueError('Promised tabular metric export is absent from staging')
        for suffix, old, new in [
            ('.md', '[paired-outcomes.json](paired-outcomes.json).',
                '[paired-outcomes.json](paired-outcomes.json). Tabular ranking metrics are also available as [paired-metrics.csv](paired-metrics.csv).'),
            ('.html', '<a href="paired-outcomes.json">paired-outcomes.json</a>.',
                '<a href="paired-outcomes.json">paired-outcomes.json</a>. Tabular ranking metrics are also available as <a href="paired-metrics.csv">paired-metrics.csv</a>.')]:
            path = bundle / ('review/PAIRED_OUTCOMES' + suffix)
            if path.is_symlink():
                raise ValueError('Refusing a staged symlink')
            content = path.read_text()
            marker = '](paired-metrics.csv)' if suffix == '.md' else 'href="paired-metrics.csv"'
            if marker in content:
                continue
            if content.count(old) != 1:
                raise ValueError('Expected one exact paired-report insertion anchor')
            source_original = ORIGINAL_ROOT / path.relative_to(bundle)
            protected[str(source_original)] = sha(source_original)
            before_sha = sha(path)
            path.write_text(content.replace(old, new, 1))
            modifications.append({'staged_document': str(path.relative_to(bundle)),
                'before_sha256': before_sha, 'after_sha256': sha(path),
                'replacements': [{'old_text': old, 'new_text': new}],
                'reason': 'Expose existing CSV promised by the main review; data unchanged'})
    _, after = scan(bundle)
    for path, expected in protected.items():
        assert sha(Path(path)) == expected, 'Original artifact changed during staged rewrite'
    failures = [row for row in after if row['status'] not in {'local_ok', 'external_not_requested'}]
    result = {'status': 'passed' if not failures else 'failed', 'bundle': str(bundle),
        'mode': 'staging_only_rewrite' if rewrite else 'read_only_check',
        'documents_checked': document_count, 'before_counts': dict(Counter(row['status'] for row in before)),
        'after_counts': dict(Counter(row['status'] for row in after)),
        'modified_staging_files': modifications, 'originals_unchanged': True,
        'frozen_numerical_or_source_files_edited': False, 'network_used': False,
        'failures': failures, 'checked_links': after,
        'requires_staging_manifest_refresh': bool(modifications), 'helper_sha256': sha(Path(__file__))}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', '--bundle', dest='stage', required=True, type=Path)
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--rewrite-staging-links', action='store_true')
    args = parser.parse_args()
    if args.receipt.exists():
        raise ValueError('Preserve previous receipts; choose a new receipt filename')
    result = transform(args.stage, rewrite=args.rewrite_staging_links)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open('x') as handle:
        json.dump(result, handle, sort_keys=True, indent=2)
        handle.write('\n')
    print(json.dumps({key: result[key] for key in ['status', 'documents_checked', 'before_counts', 'after_counts', 'originals_unchanged', 'requires_staging_manifest_refresh']}))
    raise SystemExit(1 if result['status'] == 'failed' else 0)


if __name__ == '__main__':
    main()
