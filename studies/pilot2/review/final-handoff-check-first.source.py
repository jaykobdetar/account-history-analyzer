"""Review saved final outcomes and an allowlisted static handoff, without scoring.

Run only after root declares reporting/package assembly complete. Frozen study
files are read-only. Findings expose hashes and paths, never source prose or
actual account-key values. This is not a generative or forensic authorship check.
"""
import argparse
from collections import Counter
import hashlib
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import unicodedata
from urllib.parse import unquote, urlsplit
import zipfile

from postfreeze_checks import ROOT, FREEZE_SHA, frozen_check, read, sha


def key(item):
    return tuple(item[k] for k in ('home_community', 'condition', 'arm', 'method'))


def unique(items, key_function):
    result = {key_function(item): item for item in items}
    assert len(result) == len(items), 'Duplicate outcome identity'
    return result


def check_outcomes():
    freeze = read(ROOT / 'protocol/scoring-freeze.json')
    prepared = ROOT / freeze['paired_prepared_directory']
    declared = unique(read(prepared / 'preparation-summary.json')['datasets'], key)
    index = read(ROOT / 'outputs/paired/execution-index.json')
    assert index['freeze_sha256'] == FREEZE_SHA
    runs = unique(index['runs'], key)
    published = unique(read(ROOT / 'review/paired-outcomes.json'), key)
    assert set(declared) == set(runs) == set(published) and len(runs) == 72
    observations = read(ROOT / 'review/pair-observations.json')
    visible = unique(observations, lambda row: (key(row), row['partition'], row['pair_id']))
    seen = set()
    native_counts = Counter()
    all_abstention_partitions = 0
    for identity, run in runs.items():
        output = ROOT / run['output'] / 'evaluation.json'
        assert output.exists(), 'Completed batch is missing saved evaluation output'
        native = read(output)
        assert native['implementation_fingerprint'] == freeze['implementation_fingerprint']
        assert native['analysis_config_sha256'] == freeze['analysis_config_sha256']
        assert native['frozen_threshold'] is None
        exported = published[identity]
        assert exported['exit_code'] == run['driver_exit_code']
        assert exported['status'] == native['status']
        assert exported['source_output_sha256'] == sha(output)
        doc = read(prepared / declared[identity]['path'])
        expected_pairs = {(r['split'], r['pair_id']): r for r in doc['pairs']}
        actual_pairs = set()
        for partition, value in native['partitions'].items():
            rows, metrics = value['rows'], value['metrics']
            assert partition in {'development', 'evaluation'}
            actual = {(partition, row['pair_id']) for row in rows}
            assert len(actual) == len(rows)
            actual_pairs |= actual
            assert exported['partitions'][partition]['metrics'] == metrics
            scored = [r for r in rows if r['score'] is not None]
            assert metrics['total_pair_count'] == len(rows)
            assert metrics['scored_pair_count'] == len(scored)
            assert metrics['abstained_pair_count'] == len(rows) - len(scored)
            if not scored:
                all_abstention_partitions += 1
                assert metrics['ranking']['roc_auc']['value'] is None
                assert metrics['ranking']['average_precision']['value'] is None
            for label in ('same_author', 'different_author'):
                distribution = sorted(r['score'] for r in scored if r['label'] == label)
                assert exported['partitions'][partition]['complete_score_distributions'][label] == distribution
            for row in rows:
                row_key = (identity, partition, row['pair_id'])
                assert row_key in visible and row_key not in seen
                seen.add(row_key)
                public = visible[row_key]
                source = expected_pairs[partition, row['pair_id']]
                assert public['label'] == row['label'] == source['label']
                assert public['score'] == row['score']
                assert public['status'] == row['status']
                assert public['reason_codes'] == row['reason_codes']
                assert public['raw_distance_below_guard_is_not_qualified'] == row['raw_distance']
                if row['status'] == 'ok':
                    assert row['score'] is not None
                    native_counts['scored'] += 1
                    native_counts['measured_zero_scores'] += row['score'] == 0
                else:
                    assert row['score'] is None and row['reason_codes']
                    native_counts['abstained'] += 1
        assert actual_pairs == set(expected_pairs)
    assert seen == set(visible) and len(seen) == 1152

    plan = read(ROOT / 'prepared/streams/stream-plan.json')
    # The adapter stores a scalar count, not a list. A review builder previously
    # called len() on this integer; check the eight-source-account claim directly.
    assert type(plan['final_source_accounts']) is int and plan['final_source_accounts'] == 8
    assert len(list((ROOT / 'prepared/streams/accounts').glob('*.jsonl'))) == 8
    declared_cases = unique(plan['cases'] + plan['operational_availability_views'], lambda r: r['case_id'])
    stream_index = read(ROOT / 'outputs/streams/execution-index.json')
    stream_runs = unique(stream_index['runs'], lambda r: r['case_id'])
    public_streams = unique(read(ROOT / 'review/stream-outcomes.json'), lambda r: r['case_id'])
    assert set(declared_cases) == set(stream_runs) == set(public_streams) and len(declared_cases) == 60
    stream_counts = Counter()
    expected_availability = []
    for identifier, case in declared_cases.items():
        run, public = stream_runs[identifier], public_streams[identifier]
        output = ROOT / run['output']
        operation = output.parent / (output.name + '.operation')
        receipt = read(operation / 'run.json')
        assert public['driver_exit_code'] == run['driver_exit_code']
        assert public['execution_status'] == receipt['status']
        assert public['preparation_status'] == case['preparation_status']
        assert public['preparation_reasons'] == case.get('reason_codes', [])
        if case['execution_mode'] is None:
            assert receipt['status'] == 'not_executed'
            assert public['grid_diagnostic'] is None and public['native_observation'] is None
            stream_counts['planned_unexecuted_slots'] += 1
            continue
        stream_counts['invoked_slots'] += 1
        grid_path = operation / 'grid-diagnostic.json'
        if grid_path.exists():
            grid = read(grid_path)
            assert public['grid_diagnostic'] == grid
            if not grid['candidate_measurement_available']:
                assert grid['candidate_intervals'] is None and grid['has_candidate'] is None
            if grid['best_legal_grid_error'] is None:
                assert grid['tolerance_attainable'] is None
            if grid.get('grid_unattainable') is True:
                assert grid['tolerance_attainable'] is False
                assert grid['registered_tolerance_records'] == 10
        else:
            assert public['grid_diagnostic'] is None
        if (output / 'evaluation.json').exists():
            native = read(output / 'evaluation.json')
            rows = [r for p in native['partitions'].values() for r in p['rows']]
            assert public['native_observation'] == rows
            for row in rows:
                if row['status'] != 'ok':
                    assert row['metrics'] is None
            stream_counts['saved_account_stream_outputs'] += 1
        else:
            assert public['native_observation'] is None
        if (output / 'results.json').exists():
            native = read(output / 'results.json')
            for module, value in native['modules'].items():
                expected_availability.append({'case_id': identifier, 'module': module, 'status': value['status'],
                    'reason_codes': value.get('reason_codes', []), 'truth_status': 'unknown; operational availability only'})
            stream_counts['saved_ordinary_analysis_outputs'] += 1
    order = lambda r: (r['case_id'], r['module'])
    assert sorted(read(ROOT / 'review/module-availability.json'), key=order) == sorted(expected_availability, key=order)
    return {'paired_batches': 72, 'paired_partition_count': 144, 'individual_pair_observations': len(seen),
        'pair_outcome_counts': dict(native_counts), 'all_abstention_partitions': all_abstention_partitions,
        'stream_and_operational_planned_slots': 60, 'stream_execution_counts': dict(stream_counts),
        'module_availability_rows': len(expected_availability), 'chronological_source_accounts': 8,
        'every_score_null_status_and_metric_matches_saved_outputs': True}


class StaticHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.resources = []
        self.table_rows = []
        self.depth = 0

    def handle_starttag(self, tag, attrs):
        assert tag.rsplit(':', 1)[-1] not in {'script', 'iframe', 'object', 'embed', 'form', 'base', 'audio', 'video'}, tag
        attrs = dict(attrs)
        assert not any(k.lower().rsplit(':', 1)[-1].startswith('on') for k in attrs), 'Event handler'
        assert not ('http-equiv' in attrs and attrs['http-equiv'].casefold() == 'refresh'), 'Meta refresh'
        for name, value in attrs.items():
            if name in {'href', 'src', 'xlink:href', 'action', 'poster', 'data', 'srcset'} and value:
                target = unescape(value).strip()
                assert not re.match(r'(?i)(javascript|vbscript):', target)
                if tag == 'a' and name == 'href':
                    assert urlsplit(target).scheme in {'', 'http', 'https'}, 'Unsafe navigation scheme'
                    continue  # Passive, explicit research links may leave the bundle.
                self.resources.append(target)
        if tag == 'table':
            self.depth += 1
            if self.depth == 1:
                self.table_rows.append(0)
        elif tag == 'tr' and self.depth:
            self.table_rows[-1] += 1

    def handle_endtag(self, tag):
        if tag == 'table':
            self.depth -= 1

    def handle_data(self, value):
        self.text.append(value)


def html_check(text, expected_first_rows=None):
    parser = StaticHTML()
    parser.feed(text)
    assert parser.depth == 0
    if expected_first_rows is not None:
        assert parser.table_rows[0] == expected_first_rows
    assert not re.search(r'(?i)@import|@font-face', text)
    for target in parser.resources:
        assert not urlsplit(target).scheme and not target.startswith('//'), 'Remote/embedded active resource'
    for target in re.findall(r'(?is)url\s*\(\s*[\'"]?(.*?)[\'"]?\s*\)', text):
        assert not urlsplit(target).scheme and not target.startswith('//'), 'Remote CSS resource'
    return ' '.join(parser.text)


def strings(value):
    if isinstance(value, dict):
        forbidden = {'account_key', 'account_keys', 'source_account', 'source_spellings',
                     'text', 'body', 'source_excerpt', 'source_text', 'record_ids', 'record_id'}
        assert not set(value) & forbidden, 'Private source field in sanitized JSON'
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield value


def handoff_files(path):
    if path.is_dir():
        for entry in sorted(path.rglob('*')):
            assert not entry.is_symlink(), 'Symlink in public handoff'
            if entry.is_file():
                yield entry.relative_to(path).as_posix(), entry.read_bytes()
    else:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            assert len(names) == len(set(names)), 'Duplicate ZIP member'
            for entry in archive.infolist():
                if entry.is_dir():
                    continue
                assert (entry.external_attr >> 16) & 0o170000 != 0o120000, 'ZIP symlink'
                yield entry.filename, archive.read(entry)


def safety_check(path):
    prepared = ROOT / read(ROOT / 'protocol/scoring-freeze.json')['paired_prepared_directory']
    selection = read(prepared / 'private/selection.json')
    accounts = {row['account_key'].casefold() for row in selection['accounts'] + selection['shortlist']}
    # This existing restricted frame supplies account names for chronological
    # identities too; no frame text/name is copied into the public receipt.
    frame = ROOT / 'inventory/private/source-frame.jsonl'
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location('stream_alias_only', ROOT / 'scripts/prepare_streams.py')
    module = module_from_spec(spec); spec.loader.exec_module(module)
    aliases = {p.stem for p in (ROOT / 'prepared/streams/accounts').glob('*.jsonl')}
    for line in frame.read_text().splitlines():
        row = json.loads(line)
        source = row['source_account'].casefold()
        if module.author_alias(source) in aliases:
            accounts.add(source)
    # Source privacy checks use exact sufficiently long word sequences rather
    # than fuzzy similarity; a short generic phrase is not identifiable prose.
    visible_texts = []
    inventory = {}
    for relative, data in handoff_files(path):
        name = PurePosixPath(relative)
        assert not name.is_absolute() and '..' not in name.parts
        assert not any(part.lower() in {'private', 'confirmation', 'raw', '__pycache__'} for part in name.parts)
        assert name.suffix.lower() != '.jsonl', 'Raw record stream in public handoff'
        inventory[relative] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        if name.suffix.lower() not in {'.md', '.html', '.htm', '.json', '.csv', '.txt', '.svg', '.css', '.py', '.log', '.toml'}:
            continue
        value = data.decode('utf-8')
        if name.suffix.lower() == '.json':
            visible_texts.extend(strings(json.loads(value)))
        elif name.suffix.lower() in {'.html', '.htm', '.svg'}:
            visible_texts.append(html_check(value))
        else:
            if name.suffix.lower() == '.md':
                assert not re.search(r'(?i)<\s*(script|iframe|object|embed)\b', value)
            visible_texts.append(value)
        for account in accounts:
            if len(account) >= 4:
                assert not re.search(r'(?<![\w-])' + re.escape(account) + r'(?![\w-])', value.casefold()), (
                    'Possible source account-key leak: ' + relative + ' key_sha256=' + hashlib.sha256(account.encode()).hexdigest())
    word = re.compile(r'[^\W_]+', re.UNICODE)
    public_phrases = set()
    for text in visible_texts:
        words = word.findall(unicodedata.normalize('NFC', text).casefold())
        public_phrases.update(tuple(words[i:i+12]) for i in range(len(words)-11))
        assert text.casefold() not in accounts, 'Exact account key in public text'
    sources = [prepared / 'private/candidate-pool.jsonl'] + sorted((ROOT / 'prepared/streams/accounts').glob('*.jsonl'))
    checked_records = 0
    for source in sources:
        for line in source.read_text().splitlines():
            record = json.loads(line)
            record = record.get('record', record)
            if not isinstance(record.get('text'), str):
                continue
            checked_records += 1
            words = word.findall(unicodedata.normalize('NFC', record['text']).casefold())
            for i in range(len(words)-11):
                assert tuple(words[i:i+12]) not in public_phrases, (
                    'Possible twelve-word source-prose leak; record_id_sha256=' + hashlib.sha256(record['id'].encode()).hexdigest())
    return {'handoff_file_count': len(inventory), 'files': inventory,
        'source_records_checked_for_twelve_word_excerpt_leaks': checked_records,
        'known_source_account_keys_checked': len(accounts), 'public_private_field_leaks': 0,
        'active_markup_or_remote_resource_references': 0,
        'privacy_check_limit': 'Exact account-key and twelve-word source-sequence checks plus private-field/path exclusion; short generic phrases and unseen corpus text are not identifiable by this mechanical check.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--handoff', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists(), 'Preserve earlier review receipts'
    frozen = frozen_check()
    outcomes = check_outcomes()
    for name, rows in [('PAIRED_OUTCOMES', 145), ('STREAM_OUTCOMES', 61), ('REVIEW', None)]:
        assert (ROOT / 'review' / (name + '.md')).exists()
        html_check((ROOT / 'review' / (name + '.html')).read_text(), rows)
    safety = safety_check(args.handoff)
    result = {'status': 'passed', 'frozen_manifest': frozen, 'outcomes': outcomes, 'handoff': safety,
              'checker_sha256': sha(Path(__file__)), 'scoring_or_replays_performed': False}
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'handoff'}, sort_keys=True))


if __name__ == '__main__':
    main()
