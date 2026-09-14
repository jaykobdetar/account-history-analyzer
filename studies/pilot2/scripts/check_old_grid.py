#!/usr/bin/env python3
"""Post-hoc old-pilot window-grid diagnostic using ordinary release imports.

No optimizer is invoked. No old inputs, tolerances, scores or artifacts are
rewritten. Raw record memberships stay in the explicit external output directory.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
import zipfile

from account_history_analyzer import __version__
from account_history_analyzer import features as feature_module
from account_history_analyzer.artifact_io import iter_artifact_jsonl
from account_history_analyzer.config import AnalysisConfig
from account_history_analyzer.features import extract_records
from account_history_analyzer.io import canonical_bytes, canonical_digest, load_snapshot
from account_history_analyzer.pipeline import implementation_identity
from account_history_analyzer.schemas import validate
from account_history_analyzer.windows import build_streams

CASE_ORDER = ('splice-1-full','splice-1-hash50','splice-2-full','splice-2-hash50')
COMPONENTS = ('config.py','io.py','text.py','features.py','windows.py','changepoints.py')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while block:=f.read(65536):h.update(block)
    return h.hexdigest()


def inventory(root):
    result={}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():raise ValueError('Study symlink prevents unambiguous preservation audit')
        if p.is_file():result[str(p.relative_to(root))]=sha(p)
    return result


def independent_windows(features, *, target=1000, minimum_records=8, minimum_words=20,
                        kind='comment', subreddit=None, scope_type='pooled'):
    """Greedy whole-record accumulation, independently of production windows.py.

    Features are in the canonical full-record order returned by extract_records.
    Ordinals remain in that full order even when ineligible records are skipped.
    The final short remainder is exported explicitly and never completes a grid.
    """
    finished=[]; members=[]; words=0
    def close():
        qualified=words>=target and len(members)>=minimum_records
        return {'record_ids':[features[i]['id'] for i in members],
                'record_positions':list(members),'word_count':words,'record_count':len(members),
                'first_record_position':members[0],'last_record_position':members[-1],
                'qualified':qualified,'remainder':not qualified}
    for ordinal,record in enumerate(features):
        if not (record['kind']==kind and record['usable'] and record['language']=='en'
                and record['created_utc'] is not None and record['counts']['retained_words']>=minimum_words
                and (scope_type=='pooled' or record['subreddit']==subreddit)):
            continue
        members.append(ordinal);words+=record['counts']['retained_words']
        if words>=target and len(members)>=minimum_records:
            finished.append(close());members=[];words=0
    if members:finished.append(close())
    return finished


def legal_grid(windows, minimum_segment_windows=3):
    """All one-boundary legal partitions; each side has at least m windows.

    At boundary k (k completed left windows), the split coordinate interval is
    [last left original ordinal + 1, first right original ordinal], inclusive.
    Gaps between eligible records are retained, not compressed away.
    """
    if type(minimum_segment_windows) is not int or minimum_segment_windows<1:
        raise ValueError('Positive integer minimum segment size required')
    qualified=[w for w in windows if w['qualified']]
    return [{'window_index':k,'split_interval':[qualified[k-1]['last_record_position']+1,
                                              qualified[k]['first_record_position']]}
            for k in range(minimum_segment_windows,len(qualified)-minimum_segment_windows+1)]


def interval_error(interval, truth):
    if len(interval)!=2 or any(type(x) is not int for x in (*interval,truth)) or interval[0]>interval[1]:
        raise ValueError('An ordered integer split interval and integer truth are required')
    return max(interval[0]-truth,truth-interval[1],0)


def check_memberships(independent, exported):
    if len(independent)!=len(exported):raise AssertionError('Window count differs')
    for a,b in zip(independent,exported):
        for key in ('record_ids','word_count','record_count','first_record_position','last_record_position','qualified','remainder'):
            if a[key]!=b[key]:raise AssertionError('Window membership/word-count/ordinal mismatch: '+key)


class HandChecks(unittest.TestCase):
    def feature(self,i,words=125,**changes):
        return {'id':str(i),'kind':'comment','usable':True,'language':'en','created_utc':'2020-01-01T00:00:00Z',
                'subreddit':None,'counts':{'retained_words':words},**changes}
    def test_exact_word_and_record_thresholds(self):
        w=independent_windows([self.feature(i) for i in range(9)])
        self.assertEqual([(x['record_count'],x['word_count'],x['qualified']) for x in w],[(8,1000,True),(1,125,False)])
    def test_record_guard_prevents_giant_record_closing(self):
        f=[self.feature(0,2000)]+[self.feature(i,20) for i in range(1,8)]
        self.assertEqual([(w['record_count'],w['word_count']) for w in independent_windows(f)],[(8,2140)])
    def test_word_guard_whole_record_overshoot(self):
        f=[self.feature(i,120) for i in range(9)]
        self.assertEqual([(w['record_count'],w['word_count']) for w in independent_windows(f)],[(9,1080)])
    def test_ineligible_gaps_preserve_original_ordinals(self):
        f=[self.feature(i) for i in range(12)]
        f[1]['usable']=False;f[3]['language']='und';f[5]['created_utc']=None;f[7]['counts']['retained_words']=19
        w=independent_windows(f)[0]
        self.assertEqual(w['record_positions'],[0,2,4,6,8,9,10,11])
        self.assertEqual((w['first_record_position'],w['last_record_position']),(0,11))
    def test_kinds_and_titles_do_not_join_body_budget(self):
        f=[self.feature(i,100,title={'counts':{'retained_words':10000}}) for i in range(9)]
        f[3]['kind']='submission'
        w=independent_windows(f)[0]
        self.assertFalse(w['qualified']);self.assertEqual(w['word_count'],800)
    def test_minimum_segment_edges_and_remainder(self):
        w=[{'qualified':True,'first_record_position':i*10,'last_record_position':i*10+7} for i in range(8)]
        w.append({'qualified':False,'first_record_position':80,'last_record_position':80})
        self.assertEqual(legal_grid(w),[{'window_index':3,'split_interval':[28,30]},
            {'window_index':4,'split_interval':[38,40]},{'window_index':5,'split_interval':[48,50]}])
    def test_min_size_six_has_one_legal_split_five_has_none(self):
        w=[{'qualified':True,'first_record_position':i,'last_record_position':i} for i in range(6)]
        self.assertEqual(legal_grid(w),[{'window_index':3,'split_interval':[3,3]}]);self.assertEqual(legal_grid(w[:5]),[])
    def test_inclusive_interval_errors_and_tolerance(self):
        self.assertEqual([interval_error([28,30],t) for t in (20,28,29,30,41)],[8,0,0,0,11])
        self.assertEqual(interval_error([181,182],170),11)
        self.assertGreater(interval_error([181,182],170),10)
    def test_invalid_interval_rejected(self):
        with self.assertRaises(ValueError):interval_error([5,4],4)
        with self.assertRaises(ValueError):interval_error([1,3],True)


def diagnose(args):
    if os.environ.get('AHAS_NETWORK_ISOLATION')!='linux_seccomp_socket_denial':
        raise ValueError('Run under scripts/offline_exec.py')
    if __version__!='1.0.4':raise ValueError('This registered diagnostic requires AHAS 1.0.4')
    study=args.study.resolve(strict=True);out=args.out.resolve()
    if out.is_relative_to(study) or study.is_relative_to(out):raise ValueError('Diagnostic output must be separate')
    if (out/'grid-diagnostics.json').exists():raise ValueError('Never replace completed diagnostic receipts')
    out.mkdir(parents=True,exist_ok=True);(out/'private-memberships').mkdir(exist_ok=False)
    before=inventory(study)
    config=AnalysisConfig.from_toml()
    defaults={'target_words':config['windows']['target_words'],'minimum_records':config['windows']['minimum_records'],
              'minimum_record_words':config['style']['minimum_record_words'],'minimum_segment_windows':config['changes']['minimum_segment_windows'],
              'minimum_temporal_windows':config['changes']['minimum_windows'],'jump':config['changes']['jump']}
    assert defaults=={'target_words':1000,'minimum_records':8,'minimum_record_words':20,'minimum_segment_windows':3,'minimum_temporal_windows':8,'jump':1}
    dataset=json.loads((study/'inputs/public/streams/dataset.json').read_bytes())
    results=json.loads((study/'results/streams/evaluation.json').read_bytes())
    assert dataset['protocol']['boundary_tolerance_records']==results['boundary_tolerance_records']==10
    assert canonical_digest(config.analytical())==dataset['protocol']['analysis_config_sha256']==results['analysis_config_sha256']
    by_unit={u['stream_id']:u for u in dataset['streams']}
    by_result={r['stream_id']:r for p in results['partitions'].values() for r in p['rows']}
    with zipfile.ZipFile(args.review_zip) as z:
        names=('evidence/window_resolution.json','checks/check_window_resolution.py')
        assert all(z.namelist().count(name)==1 and z.getinfo(name).file_size<=2*1024*1024 for name in names)
        reference=json.loads(z.read(names[0]))
        review_member_hashes={name:hashlib.sha256(z.read(name)).hexdigest() for name in names}
    reference_rows={r['case']:r for r in reference['rows']}
    source=Path(feature_module.__file__).resolve().parent
    frozen=json.loads((study/'protocol/source-freeze.json').read_bytes())
    unchanged={name:sha(source/name)==frozen['files']['src/account_history_analyzer/'+name] for name in COMPONENTS}
    assert all(unchanged.values()),'A supposedly presentation-only release changed an analytical component'
    fingerprint,environment,resources=implementation_identity()
    source_receipt={'suite_version':__version__,'implementation_fingerprint':fingerprint,'reference_environment':environment,
        'resource_sha256':resources,'analysis_config_sha256':canonical_digest(config.analytical()),
        'import_mechanism':'ordinary package imports in the current 1.0.4 environment; no importlib/sys.modules bypass',
        'component_sha256':{name:sha(source/name) for name in COMPONENTS},'components_identical_to_frozen_1_0_3':unchanged,
        'review_zip_sha256':sha(args.review_zip),'read_only_review_members_sha256':review_member_hashes,
        'diagnostic_script_sha256':sha(__file__),'optimizer_invoked':False}
    rows=[]
    for case in CASE_ORDER:
        unit=by_unit[case];old=by_result[case]
        root=study/'inputs/public/streams'
        snapshot=load_snapshot(root/unit['input'],root/unit['manifest'],config)
        assert snapshot.canonical_sha256==old['snapshot_sha256']
        features=extract_records(snapshot,config)
        independent=independent_windows(features)
        built=build_streams(features,config)
        current=next(s for s in built['streams'] if s['scope_type']=='pooled' and s['kind']=='comment')
        export=out/'private-memberships'/(case+'.current-windows.jsonl')
        with export.open('wb') as f:
            for w in current['windows']:
                validate(w,'windows');f.write(canonical_bytes(w))
        exported=list(iter_artifact_jsonl(export))
        check_memberships(independent,exported)
        (out/'private-memberships'/(case+'.independent-memberships.json')).write_bytes(canonical_bytes(independent))
        grid=legal_grid(independent,defaults['minimum_segment_windows'])
        intervals=[r['split_interval'] for r in grid]
        qualified=sum(w['qualified'] for w in independent)
        assert qualified>=defaults['minimum_temporal_windows']
        truth=unit['truth_boundaries'][0]
        assert unit['truth_boundaries']==old['truth_boundaries'] and all(x in intervals for x in old['candidate_intervals'])
        errors=[interval_error(x,truth) for x in intervals]
        best=min(errors) if errors else None
        observed_errors=[interval_error(x,truth) for x in old['candidate_intervals']]
        observed_best=min(observed_errors) if observed_errors else None
        row={'case':case,'record_count':len(features),'eligible_record_count':sum(w['record_count'] for w in independent),
            'eligible_words':sum(w['word_count'] for w in independent),'qualified_windows':qualified,
            'remainder_record_count':sum(w['record_count'] for w in independent if w['remainder']),
            'remainder_words':sum(w['word_count'] for w in independent if w['remainder']),
            'truth_split':truth,'nearest_attainable_boundary_error_records':best,
            'some_grid_boundary_within_registered_tolerance':best is not None and best<=10,
            'reported_candidate_intervals':old['candidate_intervals'],'reported_candidate_errors_records':observed_errors,
            'nearest_reported_error_records':observed_best,
            'nearest_attainable_intervals':[x for x in intervals if interval_error(x,truth)==best],
            'legal_boundary_count':len(grid),'legal_boundaries':grid,'adequate_temporal_input':True,
            'candidate_status':'no_candidate' if not observed_errors else 'within_tolerance' if observed_best<=10 else 'off_target_candidate',
            'grid_status':'tolerance_attainable' if best is not None and best<=10 else 'tolerance_unattainable',
            'excess_over_grid_error_records':observed_best-best if observed_best is not None and best is not None else None,
            'historical_matched_count_unchanged':old['metrics']['matched_count'],
            'independent_vs_current_exported_memberships':'passed','current_window_export_sha256':sha(export)}
        for key,value in reference_rows[case].items():assert row[key]==value,'Review reference diagnostic disagrees: '+case+'/'+key
        row['review_zip_reference_agreement']='passed';rows.append(row)
    # Historical stream evaluation did not retain per-splice windows. Corroborate
    # the independent construction against retained natural-report windows too.
    cohort=json.loads((study/'protocol/cohort.json').read_bytes())
    accounts={a['account_alias']:a for a in cohort['accounts']}
    historical_checks=[]
    for report in sorted((study/'results').glob('public-*')):
        if not (report/'windows.jsonl').is_file():continue
        account=accounts[report.name.removeprefix('public-')]
        snapshot=load_snapshot(study/account['input'],study/account['manifest'],config)
        features=extract_records(snapshot,config)
        independent=independent_windows(features)
        current=next(s for s in build_streams(features,config)['streams'] if s['scope_type']=='pooled' and s['kind']=='comment')
        old_windows={w['window_id']:w for w in iter_artifact_jsonl(report/'windows.jsonl')}
        check_memberships(independent,[old_windows[w['window_id']] for w in current['windows']])
        historical_checks.append({'case_number':len(historical_checks)+1,'record_count':len(features),'primary_windows_checked':len(independent),
                                  'historical_windows_sha256':sha(report/'windows.jsonl'),'status':'passed'})
    assert len(historical_checks)==2
    after=inventory(study);assert before==after,'Historical pilot files changed'
    summary={'status':'passed','diagnostic_type':'Post-hoc historical representation-resolution check, not new evaluation scoring',
        'coordinate_definition':'Split k precedes zero-based canonical record ordinal k. Candidate interval endpoints are inclusive; left endpoint is last left ordinal + 1.',
        'registered_historical_tolerance_records':10,'historical_tolerance_and_scores_unchanged':True,
        'optimizer_invoked':False,'default_parameters':defaults,'rows':rows,'historical_natural_window_checks':historical_checks,
        'historical_splice_window_export_status':'not_retained_by_account_stream_evaluator',
        'splice_membership_validation':'Independent reconstruction matched newly exported current 1.0.4 build_streams memberships; no claim of comparing missing historical splice memberships.',
        'historical_preservation':{'file_count':len(before),'inventory_sha256_before':canonical_digest(before),'inventory_sha256_after':canonical_digest(after),'all_file_bytes_unchanged':before==after},
        'limitations':['This already-inspected pilot is development evidence, not untouched confirmation data.',
                      'A grid limitation remains a failure of the original ten-record end-to-end criterion.',
                      'Constructed source-account boundaries are evaluator construction facts, not verified human-authorship transitions.',
                      'No optimizer, threshold, tolerance, source record, score or production code was changed.']}
    (out/'grid-diagnostics.json').write_bytes(canonical_bytes(summary))
    (out/'source-identity.json').write_bytes(canonical_bytes(source_receipt))
    md=['# Old splice output-grid diagnostic','',
        'Verified with ordinary AHAS 1.0.4 package imports and unchanged analytical components. The current preprocessor supplied word counts; a separate whole-record accumulator reconstructed the windows. No optimizer ran and no historical scores or the ten-record tolerance changed.','',
        '| Existing case | Qualified windows | Reported nearest error | Best legal error | Grid within tolerance 10 | Candidate state |',
        '|---|---:|---:|---:|---|---|']
    for r in rows:
        md.append(f"| {r['case']} | {r['qualified_windows']} | {r['nearest_reported_error_records'] if r['nearest_reported_error_records'] is not None else 'no candidate'} | {r['nearest_attainable_boundary_error_records']} | {'yes' if r['some_grid_boundary_within_registered_tolerance'] else 'no'} | {r['candidate_status']} |")
    md+=['','The hash-half variant of splice 1 cannot satisfy the registered tolerance at any legal output interval. Its reported interval is already the nearest attainable interval. This explains a representation limit; it does not convert that original failure into a pass. The hash-half variant of splice 2 had adequate input and no candidate even though a nine-record-error legal interval was available.','',
         'Legal cuts require at least three qualified windows on each side. Intervals use original full-record ordinals, so skipped short or otherwise ineligible records remain in the coordinate system. A split interval is [last eligible left ordinal + 1, first eligible right ordinal], inclusive. Final unqualified remainders are excluded.','',
         'All four reconstructions match newly exported production window memberships and all independent-review reference values. The old account-stream evaluator did not retain per-splice window exports; this missing artifact is explicit. Two existing natural-report exports independently corroborate the reconstruction against historical memberships.','',
         f"All {len(before)} historical files retain their exact hashes. Private record membership maps and exact operational commands remain outside the public repository.",'',
         'This is post-hoc development evidence. Source-account construction labels do not establish human authorship, and no new held-out evaluation was scored.','']
    (out/'GRID_DIAGNOSTICS.md').write_text('\n'.join(md))
    print(json.dumps({'status':'passed','cases_checked':len(rows),'historical_files_preserved':len(before),'historical_natural_reports_checked':len(historical_checks),
        'reported_and_best_legal_errors':[[r['nearest_reported_error_records'],r['nearest_attainable_boundary_error_records']] for r in rows],
        'source_fingerprint':fingerprint,'optimizer_invoked':False},sort_keys=True))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study',type=Path);p.add_argument('--review-zip',type=Path);p.add_argument('--out',type=Path);p.add_argument('--self-test',action='store_true')
    a=p.parse_args()
    if a.self_test:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(HandChecks)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    if not all((a.study,a.review_zip,a.out)):p.error('--study, --review-zip and --out are required')
    diagnose(a);return 0

if __name__=='__main__':raise SystemExit(main())
