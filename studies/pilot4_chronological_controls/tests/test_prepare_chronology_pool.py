"""Synthetic source archives only; no downloaded corpus or scoring calls."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS))
from prepare_chronology_pool import DESIGN, buffer_prefix, prepare, validate_plan
from run_full_chronology import sha
from metadata_feasibility import seconds


def put(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True) + '\n')


class SyntheticPool:
    """Ten entirely fabricated source accounts support the amended five blocks."""
    def __init__(self, root, *, prepare_now=True, shared_threads=False):
        self.root = Path(root)
        self.plan_path = self.root/'plan.json'
        self.pool = self.root/'pool'
        self.cut_text = '2015-01-01T00:00:00Z'
        self.cut = seconds(self.cut_text)
        self.strata = [
            {'stratum_id': 'physics', 'communities': ['AskPhysics', 'Physics'], 'block_cap': 1,
             'accounts': ['physics-a', 'physics-b'], 'cut': self.cut_text},
            {'stratum_id': 'linux', 'communities': ['linux', 'linuxquestions'], 'block_cap': 2,
             'accounts': ['linux-a', 'linux-b', 'linux-c', 'linux-d'], 'cut': self.cut_text},
            {'stratum_id': 'code', 'communities': ['programming', 'learnprogramming'], 'block_cap': 2,
             'accounts': ['code-a', 'code-b', 'code-c', 'code-d'], 'cut': self.cut_text},
        ]
        self.originals = {}
        metadata = []
        sources = []
        for spec in self.strata:
            for community in spec['communities']:
                lines = []
                for account in spec['accounts']:
                    for period in ('early', 'late'):
                        for number in range(64):
                            rid = f'{community}:{account}:{period}:{number}'
                            timestamp = self.cut - (number+1)*60 if period == 'early' else self.cut + number*60
                            row = {'id': rid, 'user': account.upper(), 'timestamp': timestamp,
                                   'text': '\n'.join([('Ω'+rid+' ')*25 for _ in range(5)]),
                                   'root': 'thread:'+rid, 'reply_to': 'parent:'+rid,
                                   'meta': {'subreddit': community, 'permalink': 'https://example.invalid/'+rid,
                                            'extra_source_metadata': ['preserved', number]}}
                            if shared_threads and number == 0 and account == spec['accounts'][0]:
                                row['root'] = 'shared-thread'
                            raw = (json.dumps(row, ensure_ascii=False, separators=(',', ':'))+'\n').encode()
                            lines.append(raw); self.originals[rid] = row
                            metadata.append({'record_id': rid, 'account_key': account, 'community': community,
                                'created_utc': datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace('+00:00','Z'),
                                'reason': None, 'retained_words': 125,
                                'source_line_sha256': hashlib.sha256(raw).hexdigest()})
                archive = self.root/(community+'.zip')
                with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as handle:
                    handle.writestr('utterances.jsonl', b''.join(lines))
                sources.append({'community': community, 'archive': str(archive), 'sha256': sha(archive)})
        metadata_path = self.root/'metadata.jsonl'
        metadata_path.write_text(''.join(json.dumps(row)+'\n' for row in metadata))
        flags = [{'account_key': f'excluded-{i}',
                  'pilot1_or_pilot2_or_private_mandatory_exclusion': i < 57,
                  'pilot3_selected_scored_exposure': i >= 57,
                  'prior_capacity_only_exposure': False} for i in range(117)]
        paths = {}
        for key, content in [('feasibility_rules', DESIGN), ('exposure_flags', {'accounts': flags}),
                             ('audit_engine', {'synthetic': 'engine'}), ('audit_wrapper', {'synthetic': 'wrapper'}),
                             ('audit_rules', {'synthetic': 'rules'}), ('historical_inventory', {'sources': []})]:
            paths[key] = str(self.root/(key+'.json'))
            put(paths[key], content)
        converter = SCRIPTS.parents[1]/'pilot3_cross_context'/'scripts'/'prepare_candidate_pool.py'
        self.plan = {'phase': 'frozen_before_candidate_pool', 'script_sha256': sha(SCRIPTS/'prepare_chronology_pool.py'),
                     'finalizer_sha256': sha(SCRIPTS/'finalize_chronology_inputs.py'),
                     'strata': self.strata, 'metadata_files': [str(metadata_path)],
                     'converter': str(converter), 'sources': sources, **paths}
        required = {SCRIPTS/name for name in ('prepare_chronology_pool.py','finalize_chronology_inputs.py',
                    'metadata_feasibility.py','chronology_math.py','run_full_chronology.py')}
        required.update(Path(path) for path in paths.values())
        required.update((metadata_path, converter, converter.parent/'cohort_selection.py'))
        required.update(Path(source['archive']) for source in sources)
        self.plan['bound_artifacts'] = [{'path': str(path), 'sha256': sha(path)} for path in sorted(required)]
        put(self.plan_path, self.plan)
        if prepare_now:
            self.prepare()

    def prepare(self):
        with patch.dict('os.environ', {'AHAS_NETWORK_ISOLATION': 'linux_seccomp_socket_denial'}), \
             patch('prepare_chronology_pool.resource.setrlimit'):
            prepare(self.plan_path, self.pool)


class BufferRules(unittest.TestCase):
    def rows(self, n, words=125, start=0):
        cut = seconds('2015-01-01T00:00:00Z')
        return [{'record_id': str(i), 'retained_words': words,
                 'created_utc': datetime.fromtimestamp(cut+start+i, timezone.utc).isoformat()}
                for i in range(n)]

    def test_buffer_requires_both_eight_thousand_words_and_sixty_four_records(self):
        cut = seconds('2015-01-01T00:00:00Z')
        self.assertEqual(len(buffer_prefix(self.rows(100), cut, 'late')), 64)
        self.assertEqual(len(buffer_prefix(self.rows(100, 100), cut, 'late')), 80)
        self.assertEqual(len(buffer_prefix(self.rows(100, 500), cut, 'late')), 17)
        self.assertEqual(len(buffer_prefix(self.rows(400, 20), cut, 'late')), 300)

    def test_half_open_dates_nearest_cut_and_whole_record_no_cap_skipping(self):
        cut = seconds('2015-01-01T00:00:00Z')
        rows = self.rows(3, start=-1)
        self.assertEqual([r['record_id'] for r in buffer_prefix(rows,cut,'early')], ['0'])
        self.assertEqual([r['record_id'] for r in buffer_prefix(rows,cut,'late')], ['1','2'])
        rows = self.rows(50, 499)
        rows[17]['retained_words'] = 20
        chosen = buffer_prefix(rows,cut,'late')
        self.assertEqual(len(chosen), 17)
        self.assertNotIn('17', {r['record_id'] for r in chosen})

    def test_invalid_period_and_noninteger_words_rejected(self):
        cut = seconds('2015-01-01T00:00:00Z')
        with self.assertRaises(ValueError):
            buffer_prefix(self.rows(2),cut,'middle')
        rows = self.rows(2); rows[0]['retained_words'] = True
        with self.assertRaises(ValueError):
            buffer_prefix(rows,cut,'late')


class CandidatePreparation(unittest.TestCase):
    def test_submission_namespace_collision_ignored_but_duplicate_comment_rejected(self):
        for is_submission in (True, False):
            with self.subTest(is_submission=is_submission), tempfile.TemporaryDirectory() as temp:
                fixture = SyntheticPool(temp, prepare_now=False)
                rid = next(rid for rid in fixture.originals if rid.startswith('linux:'))
                source = next(row for row in fixture.plan['sources'] if row['community'] == 'programming')
                path = Path(source['archive'])
                with zipfile.ZipFile(path) as handle:
                    old = handle.read('utterances.jsonl')
                collision = {'id':rid, 'root':rid if is_submission else 'different-thread',
                             'timestamp':fixture.cut, 'user':'unrelated', 'text':'not the comment',
                             'meta':{'subreddit':'programming'}}
                with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as handle:
                    handle.writestr('utterances.jsonl',old+json.dumps(collision).encode()+b'\n')
                source['sha256'] = sha(path)
                for binding in fixture.plan['bound_artifacts']:
                    if binding['path'] == str(path):binding['sha256'] = sha(path)
                put(fixture.plan_path,fixture.plan)
                if is_submission:
                    fixture.prepare()
                    rows = [json.loads(line) for line in (fixture.pool/'candidate-pool.jsonl').read_text().splitlines()]
                    saved = next(row for row in rows if row['record']['id'] == rid)
                    self.assertEqual(saved['record']['text'],fixture.originals[rid]['text'])
                    self.assertEqual(len(rows),2560)
                else:
                    with self.assertRaises(ValueError):fixture.prepare()

    def test_source_bytes_metadata_and_exact_buffer_counts_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = SyntheticPool(temp)
            report = json.loads((fixture.pool/'preparation.json').read_bytes())
            self.assertEqual((report['accounts'], report['records'], report['retained_words']), (10, 2560, 320000))
            self.assertEqual(report['style_scores_computed'], 0)
            selection = json.loads((fixture.pool/'selection.json').read_bytes())
            self.assertEqual(len(selection['cells']), 40)
            self.assertTrue(all((row['records'],row['retained_words']) == (64,8000) for row in selection['cells']))
            pool = [json.loads(line) for line in (fixture.pool/'candidate-pool.jsonl').read_text().splitlines()]
            for entry in pool:
                source = fixture.originals[entry['record']['id']]
                self.assertEqual(entry['record']['text'].encode(), source['text'].encode())
                self.assertEqual(entry['record']['account_id'], source['user'])
                self.assertEqual(entry['record']['thread_id'], source['root'])
                self.assertEqual(entry['record']['parent_id'], source['reply_to'])
                self.assertEqual(entry['record']['permalink'], source['meta']['permalink'])
            offsets = json.loads((fixture.pool/'original-source-index.json').read_bytes())
            raw = (fixture.pool/'original-source-lines.jsonl').read_bytes()
            for rid, item in offsets.items():
                line = raw[item['offset']:item['offset']+item['bytes']]
                self.assertEqual(hashlib.sha256(line).hexdigest(), item['sha256'])
                self.assertEqual(json.loads(line), fixture.originals[rid])

    def test_missing_binding_excluded_identity_and_relaxed_gate_rejected(self):
        for change in ('binding', 'excluded', 'gate', 'duplicate_stratum', 'wrong_cap'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temp:
                fixture = SyntheticPool(temp, prepare_now=False)
                if change == 'binding':
                    fixture.plan['bound_artifacts'] = [r for r in fixture.plan['bound_artifacts']
                        if r['path'] != fixture.plan['metadata_files'][0]]
                elif change == 'excluded':
                    fixture.plan['strata'][0]['accounts'][0] = 'excluded-0'
                elif change == 'duplicate_stratum':
                    fixture.plan['strata'][0]['stratum_id'] = fixture.plan['strata'][1]['stratum_id']
                elif change == 'wrong_cap':
                    fixture.plan['strata'][0]['block_cap'] = 2
                else:
                    design = dict(DESIGN, half_band_days=365)
                    put(fixture.plan['feasibility_rules'], design)
                    for artifact in fixture.plan['bound_artifacts']:
                        if artifact['path'] == fixture.plan['feasibility_rules']:
                            artifact['sha256'] = sha(artifact['path'])
                put(fixture.plan_path, fixture.plan)
                with self.assertRaises(ValueError):
                    validate_plan(fixture.plan_path)


if __name__ == '__main__':
    unittest.main()
