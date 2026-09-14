#!/usr/bin/env python3
"""Generate and check all six fixture reports after the audit repairs.

Run through scripts/offline_exec.py in the pinned reference environment. This
driver leaves historical releases and their receipts untouched. Each fixture is
analyzed, fully recomputed, and rerendered from its saved artifacts in separate
processes. Timing and operational receipts are separate from deterministic checks.
The safety check parses markup; it is not a substitute for the browser audit.
"""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any

FIXTURES = ('arithmetic', 'constructed_style_shift', 'constructed_topic_shift',
            'edge_cases', 'empty', 'stable_constructed_style')
PRESENTATION = ('report.md', 'report.html', 'activity_daily.svg',
                'activity_hourly.svg', 'eligible_word_volume.svg',
                'surface_features.svg', 'adjacent_distances.svg')
CANONICAL_ARTIFACTS = frozenset((*PRESENTATION, 'results.json',
    'resolved_config.json', 'method_registry.json', 'records_features.jsonl',
    'windows.jsonl', 'evidence.jsonl', 'checksums.json'))
AUDIT_ID = 'audit_repair_fixture_reports_v1'
SUMMARY_NAME = 'fixture-validation.json'
RECEIPT_NAME = 'fixture-receipts.json'


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(',', ':')) + '\n').encode('utf-8')


def file_digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            value.update(chunk)
    return value.hexdigest()


def jsonl(path: Path) -> list[dict]:
    with path.open(encoding='utf-8') as handle:
        return [json.loads(line) for line in handle if line.strip()]


def indexed(rows: list[dict], key: str) -> dict[str, dict]:
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError('Duplicate exported ' + key)
    return result


def source_checks(directory: Path, records: Path, result: dict) -> dict:
    from account_history_analyzer.reporting import SOURCES

    # The analyzer has already validated duplicate supplied IDs. Arithmetic
    # intentionally contains identical duplicate rows, so index its unique IDs.
    supplied = {row['id']: row for row in jsonl(records)}
    features = indexed(jsonl(directory / 'records_features.jsonl'), 'id')
    windows = indexed(jsonl(directory / 'windows.jsonl'), 'window_id')
    evidence = indexed(jsonl(directory / 'evidence.jsonl'), 'evidence_id')
    findings = indexed(result['findings'], 'finding_id')
    if features.keys() != supplied.keys():
        raise ValueError('Exported features do not cover exactly the supplied IDs')
    for window in windows.values():
        if not set(window['record_ids']) <= supplied.keys():
            raise ValueError('Window refers to an absent supplied record')
        if window['record_count'] != len(window['record_ids']):
            raise ValueError('Window record count disagrees with its source IDs')
    for item in evidence.values():
        identifier, field = item['source_record_id'], item['source_field']
        if identifier not in supplied or field not in {'text', 'title'}:
            raise ValueError('Evidence source record or field is invalid')
        if item['offset_basis'] == 'raw_source':
            text = supplied[identifier][field]
        elif item['offset_basis'] == 'normalized_segment':
            feature = features[identifier] if field == 'text' else features[identifier]['title']
            text = feature['segments'][item['segment_index']]['text']
        else:
            raise ValueError('Unknown evidence offset basis')
        if not 0 <= item['start'] <= item['end'] <= len(text):
            raise ValueError('Evidence offsets exceed their declared source')
        if text[item['start']:item['end']] != item['text']:
            raise ValueError('Evidence text differs from its declared source slice')

    registry = json.loads((directory / 'method_registry.json').read_bytes())
    methods = indexed(registry['methods'], 'method_id')
    source_ids = {identifier for identifier, _, _ in SOURCES}
    for method in methods.values():
        if not set(method['references']) <= source_ids:
            raise ValueError('Registered research reference is absent from report bibliography')
    for finding in findings.values():
        if not set(finding['source_record_ids']) <= supplied.keys():
            raise ValueError('Finding refers to an absent supplied record')
        if not set(finding['evidence_refs']) <= evidence.keys():
            raise ValueError('Finding evidence reference is unresolved')
        if not set(finding['window_ids']) <= windows.keys():
            raise ValueError('Finding window reference is unresolved')
        if not set(finding['related_finding_ids']) <= findings.keys():
            raise ValueError('Related finding reference is unresolved')
        if finding['method_id'] not in methods:
            raise ValueError('Finding method is absent from the frozen registry')
        if finding['method_version'] != methods[finding['method_id']]['version']:
            raise ValueError('Finding method version differs from the frozen registry')

    style = result['modules']['style']['payload']
    for stream in style['streams']:
        if not set(stream['window_ids']) <= windows.keys():
            raise ValueError('Stream window reference is unresolved')
    for comparison in style['comparisons']:
        for key in ('left_window_id', 'right_window_id'):
            if comparison[key] is not None and comparison[key] not in windows:
                raise ValueError('Comparison window reference is unresolved')
    for entry in result['modules']['links']['payload']['by_window']:
        if entry['window_id'] not in windows:
            raise ValueError('Link summary window reference is unresolved')
    return {'status': 'passed', 'unique_source_record_count': len(supplied),
            'window_count': len(windows), 'evidence_slice_count': len(evidence),
            'finding_count': len(findings),
            'boundary_finding_count': sum(item['finding_type'] == 'style_boundary_candidate'
                                          for item in findings.values()),
            'registry_method_versions': {key: value['version'] for key, value in sorted(methods.items())},
            'all_checked_source_evidence_window_finding_and_method_references_resolve': True}


class MarkupAudit(HTMLParser):
    """Inspect actual parsed markup, leaving literal escaped source text inert."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.violations: list[str] = []
        self.ids: set[str] = set()
        self.fragments: set[str] = set()
        self.style_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'iframe', 'object', 'embed', 'base', 'form',
                   'foreignobject', 'animate', 'set'}:
            self.violations.append('active element: ' + tag)
        if tag == 'style':
            self.style_depth += 1
        attributes = dict(attrs)
        for key, raw in attrs:
            value = raw or ''
            if key == 'id':
                if value in self.ids:
                    self.violations.append('duplicate element ID: ' + value)
                self.ids.add(value)
            if key.startswith('on') or key == 'srcdoc':
                self.violations.append('active attribute: ' + key)
            if key in {'href', 'xlink:href', 'src', 'action', 'formaction'}:
                if re.match(r'\s*(?:javascript:|vbscript:|data:text/html)', value, re.I):
                    self.violations.append('unsafe URL scheme')
                if value.startswith('#'):
                    self.fragments.add(value[1:])
            if key in {'src', 'srcset', 'poster', 'background'} or (
                    tag in {'link', 'image', 'use'} and key in {'href', 'xlink:href'}):
                if re.search(r'(?:https?:|//)', value, re.I):
                    self.violations.append('remote automatic asset')
            if key == 'style':
                self._css(value)
        if tag == 'meta' and attributes.get('http-equiv', '').lower() == 'refresh':
            self.violations.append('meta refresh')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == 'style':
            self.style_depth = max(0, self.style_depth - 1)

    def handle_data(self, data):
        if self.style_depth:
            self._css(data)

    def _css(self, source):
        if re.search(r'@import|url\s*\(\s*[\'\"]?(?:https?:|//)|expression\s*\(', source, re.I):
            self.violations.append('remote or active CSS')


def safety_checks(directory: Path) -> dict:
    from markdown_it import MarkdownIt
    from account_history_analyzer.reporting import LIMITATIONS, SOURCES

    markdown = (directory / 'report.md').read_text(encoding='utf-8')
    documents = {'report.html': (directory / 'report.html').read_text(encoding='utf-8'),
                 'report.md_as_commonmark': MarkdownIt('commonmark', {'html': True}).enable('table').render(markdown)}
    checks = {}
    for name, document in documents.items():
        audit = MarkupAudit()
        audit.feed(document)
        audit.close()
        unresolved = sorted(audit.fragments - audit.ids)
        if audit.violations or unresolved:
            raise ValueError('Unsafe markup or unresolved report anchors: ' +
                             json.dumps({'document': name, 'violations': audit.violations,
                                         'unresolved_fragments': unresolved}, sort_keys=True))
        checks[name] = {'status': 'passed', 'element_ids': len(audit.ids),
                        'internal_link_targets': len(audit.fragments)}
    if not all(value in markdown for value in LIMITATIONS):
        raise ValueError('Report omits a required scientific limitation template')
    if not all(f'[{identifier}: {title}]({url})' in markdown for identifier, title, url in SOURCES):
        raise ValueError('Report bibliography differs from registered source templates')
    return {'status': 'passed', 'scope': 'parsed_html_and_commonmark_static_safety_and_anchors',
            'browser_execution': 'not_run_by_this_driver', 'documents': checks,
            'scientific_limitation_templates_present': True,
            'bibliography_template_present': True}


def run_process(argv: list[str], repo: Path, timeout: float) -> dict:
    started = time.perf_counter()
    receipt = {'argv': argv, 'cwd': str(repo)}
    try:
        completed = subprocess.run(argv, cwd=repo, check=False, capture_output=True,
                                   text=True, timeout=timeout)
        receipt.update(exit_code=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
    except (OSError, subprocess.TimeoutExpired) as exc:
        receipt.update(exit_code=None, error_type=type(exc).__name__, error=str(exc))
    receipt['elapsed_seconds'] = time.perf_counter() - started
    return receipt


def run(repo: Path, outroot: Path, qa: Path, *, overwrite: bool, timeout: float,
        expected_fingerprint: str | None = None) -> bool:
    from account_history_analyzer import __version__
    from account_history_analyzer.pipeline import implementation_identity

    fingerprint, environment, _ = implementation_identity()
    if expected_fingerprint is not None and expected_fingerprint != fingerprint:
        raise ValueError('Current implementation differs from the requested frozen fingerprint')
    summary = {'schema_version': '1.0.0', 'audit': AUDIT_ID, 'status': 'pending',
               'suite_version': __version__, 'implementation_fingerprint': fingerprint,
               'reference_environment': environment,
               'network_isolation': os.environ.get('AHAS_NETWORK_ISOLATION', 'not_asserted'),
               'verification_scope': 'all_canonical_artifacts',
               'expected_canonical_artifacts': sorted(CANONICAL_ARTIFACTS),
               'rerender_scope': 'saved_artifacts_to_markdown_html_and_five_charts_excerpts_included',
               'historical_outputs_are_write_targets': False, 'truth_sidecars_read': False,
               'real_world_validation': 'not_established', 'fixtures': []}
    receipts = {'schema_version': '1.0.0', 'audit': AUDIT_ID, 'processes': []}
    started = time.perf_counter()
    success = True
    qa.mkdir(parents=True, exist_ok=True)
    for fixture in FIXTURES:
        print('Generating, recomputing, and rerendering ' + fixture, flush=True)
        directory = outroot / fixture
        records = repo / 'fixtures' / f'{fixture}.jsonl'
        manifest = repo / 'fixtures' / f'{fixture}.snapshot.json'
        row = {'fixture': fixture, 'status': 'failed', 'input_sha256': file_digest(records),
               'manifest_sha256': file_digest(manifest), 'operations': {}, 'error': None}
        args = [sys.executable, '-m', 'account_history_analyzer', 'analyze', '--input', str(records),
                '--manifest', str(manifest), '--out', str(directory)]
        if overwrite:
            args.append('--overwrite')
        try:
            generated = run_process(args, repo, timeout)
            receipts['processes'].append({'fixture': fixture, 'operation': 'analyze', **generated})
            row['operations']['analyze_exit_code'] = generated['exit_code']
            if generated['exit_code'] != 0 or json.loads(generated['stdout']).get('status') != 'complete':
                raise ValueError('Analyzer did not finish with complete status')
            operational = {name: json.loads((directory / name).read_bytes())
                           for name in ('ingest_receipt.json', 'run_receipt.json')}
            receipts['processes'][-1]['analyzer_receipts'] = operational
            if operational['run_receipt.json']['network_isolation'] != 'linux_seccomp_socket_denial':
                raise ValueError('Analyzer receipt does not confirm networking was disabled')
            result = json.loads((directory / 'results.json').read_bytes())
            if result['analysis']['implementation_fingerprint'] != fingerprint:
                raise ValueError('Implementation fingerprint changed during the audit')
            if result['analysis']['suite_version'] != __version__:
                raise ValueError('Suite version changed during the audit')
            row['module_statuses'] = {key: value['status'] for key, value in sorted(result['modules'].items())}
            if not set(row['module_statuses'].values()) <= {'ok', 'insufficient_data', 'not_run'}:
                raise ValueError('A fixture module failed or exhausted a resource budget')
            if result['modules']['ai_text_detection']['payload']['capability'] != 'not_implemented_in_v1':
                raise ValueError('V1 excluded capability state changed')
            if not result['modules']['reuse']['payload']['budget_complete']:
                raise ValueError('Original fixture near-reuse analysis was incomplete')
            row['canonical_artifact_sha256'] = {name: file_digest(directory / name)
                                                for name in sorted(CANONICAL_ARTIFACTS)}
            row['source_checks'] = source_checks(directory, records, result)
            row['report_safety'] = safety_checks(directory)

            verified = run_process([sys.executable, '-m', 'account_history_analyzer', 'verify',
                '--input', str(records), '--manifest', str(manifest), '--analysis-dir', str(directory),
                '--recompute'], repo, timeout)
            receipts['processes'].append({'fixture': fixture, 'operation': 'verify_recompute', **verified})
            row['operations']['verify_recompute_exit_code'] = verified['exit_code']
            verification = json.loads(verified['stdout']) if verified['exit_code'] == 0 else {}
            if (verification.get('status') != 'reproduced' or
                    verification.get('verification_scope') != 'all_canonical_artifacts' or
                    verification.get('reproduced_artifacts') != sorted(CANONICAL_ARTIFACTS) or
                    verification.get('checked_artifacts') != len(CANONICAL_ARTIFACTS) - 1):
                raise ValueError('CLI verify --recompute did not reproduce all 14 canonical artifacts')
            row['full_recompute'] = verification

            with tempfile.TemporaryDirectory(prefix='ahas-audit-rerender-') as temporary:
                rerender = Path(temporary) / 'rendered'
                rendered = run_process([sys.executable, '-m', 'account_history_analyzer', 'render',
                    '--results', str(directory / 'results.json'), '--artifacts', str(directory),
                    '--format', 'both', '--excerpts', 'included', '--out', str(rerender)], repo, timeout)
                receipts['processes'].append({'fixture': fixture, 'operation': 'rerender_included', **rendered})
                row['operations']['rerender_included_exit_code'] = rendered['exit_code']
                if rendered['exit_code'] != 0 or json.loads(rendered['stdout']).get('status') != 'rendered':
                    raise ValueError('Saved artifact rerender did not complete')
                row['rerender'] = {name: {'byte_identical': (directory / name).read_bytes() == (rerender / name).read_bytes(),
                                         'sha256': file_digest(rerender / name)} for name in PRESENTATION}
                if not all(item['byte_identical'] for item in row['rerender'].values()):
                    raise ValueError('Published report/chart bytes differ from saved artifact rerender')
                row['rerender_safety'] = safety_checks(rerender)
            if any(file_digest(directory / name) != value for name, value in row['canonical_artifact_sha256'].items()):
                raise ValueError('Verification or rendering modified the published canonical artifacts')
            row['status'] = 'passed'
        except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
            row['error'] = {'type': type(exc).__name__, 'message': str(exc)}
            success = False
        summary['fixtures'].append(row)
        summary['status'] = ('passed' if success and len(summary['fixtures']) == len(FIXTURES)
                             else 'running' if success else 'failed')
        receipts['elapsed_seconds'] = time.perf_counter() - started
        (qa / RECEIPT_NAME).write_bytes(canonical(receipts))
        (qa / SUMMARY_NAME).write_bytes(canonical(summary))
        print(f'{fixture}: {row["status"]}', flush=True)
    return success


def overlaps(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--outroot', type=Path, help='Fresh reports root; default REPO/output/audit-repair')
    parser.add_argument('--qa', type=Path, help='New receipts directory; default REPO/qa/audit-repair')
    parser.add_argument('--timeout', type=float, default=600, help='Per-process timeout in seconds')
    parser.add_argument('--overwrite', action='store_true', help='Replace this audit outputs and these two receipts only')
    parser.add_argument('--expected-fingerprint', help='Require the requested frozen implementation fingerprint')
    args = parser.parse_args()
    repo = args.repo.resolve()
    outroot = (args.outroot or repo / 'output/audit-repair').resolve()
    qa = (args.qa or repo / 'qa/audit-repair').resolve()
    if args.timeout <= 0:
        parser.error('--timeout must be positive')
    if os.environ.get('AHAS_NETWORK_ISOLATION') != 'linux_seccomp_socket_denial':
        parser.error('Run this script through scripts/offline_exec.py')
    protected = [repo / 'output' / name for name in FIXTURES]
    protected.extend(repo / name for name in ('output/pr383', 'qa/pr383', 'fixtures', 'release', 'src'))
    for candidate in (outroot, qa):
        if any(overlaps(candidate, path.resolve()) for path in protected):
            parser.error('New output and receipt directories must not overlap preserved inputs or releases')
    if overlaps(outroot, qa):
        parser.error('Report outputs and operational receipts must use separate directories')
    if not args.overwrite and (outroot.exists() or any((qa / name).exists() for name in (RECEIPT_NAME, SUMMARY_NAME))):
        parser.error('New output or these audit receipts already exist; use --overwrite explicitly')
    return 0 if run(repo, outroot, qa, overwrite=args.overwrite, timeout=args.timeout,
                    expected_fingerprint=args.expected_fingerprint) else 1


if __name__ == '__main__':
    raise SystemExit(main())
