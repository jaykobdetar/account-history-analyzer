#!/usr/bin/env python3
"""Generate isolated PR383 fixture reports, recompute, and compare prior measurements.

Run with the reference environment's scripts/offline_exec.py. Historical
output/{fixture} directories are read only. Initial-report versus rerender byte
identity is outside this audit; no such claim is made here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

FIXTURES = ('arithmetic','constructed_style_shift','constructed_topic_shift','edge_cases','empty','stable_constructed_style')
EXPORTS = ('records_features.jsonl','windows.jsonl','evidence.jsonl')
OLD_OPTIMIZER = 'pelt_l2_min_size_safe_pruning_v1'
NEW_OPTIMIZER = 'ruptures_pelt_pr383_a28574d_v1'


def canonical(value: Any) -> bytes:
    return (json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))+'\n').encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]


def module_differences(before: Any, after: Any, path: str = 'modules') -> tuple[list[dict],list[dict]]:
    """Permit only the exact old-to-new optimizer identifier at optimizer keys."""
    if before == after:
        return [],[]
    if path.rsplit('.',1)[-1]=='optimizer' and before==OLD_OPTIMIZER and after==NEW_OPTIMIZER:
        return [],[{'path':path,'before':before,'after':after}]
    differences,allowed = [],[]
    if isinstance(before,dict) and isinstance(after,dict):
        for key in sorted(before.keys()|after.keys()):
            if key not in before or key not in after:
                differences.append({'path':path+'.'+key,'reason':'key_added_or_removed'})
            else:
                changed,accepted = module_differences(before[key],after[key],path+'.'+key)
                differences.extend(changed); allowed.extend(accepted)
    elif isinstance(before,list) and isinstance(after,list) and len(before)==len(after):
        for index,(left,right) in enumerate(zip(before,after,strict=True)):
            changed,accepted = module_differences(left,right,path+f'[{index}]')
            differences.extend(changed); allowed.extend(accepted)
    else:
        differences.append({'path':path,'reason':'value_changed','before':before,'after':after})
    return differences,allowed


def source_checks(directory: Path, records: Path, result: dict) -> dict:
    supplied = {row['id']:row for row in jsonl(records)}
    features = {row['id']:row for row in jsonl(directory/'records_features.jsonl')}
    windows = {row['window_id']:row for row in jsonl(directory/'windows.jsonl')}
    evidence_rows = jsonl(directory/'evidence.jsonl')
    evidence = {row['evidence_id']:row for row in evidence_rows}
    findings = {row['finding_id']:row for row in result['findings']}
    if len(evidence)!=len(evidence_rows) or len(findings)!=len(result['findings']):
        raise ValueError('Duplicate evidence/finding identifiers')
    for item in evidence.values():
        identifier,field = item['source_record_id'],item['source_field']
        if identifier not in supplied or identifier not in features:
            raise ValueError('Evidence source is absent from supplied records')
        if item['offset_basis']=='raw_source':
            text = supplied[identifier][field]
        elif item['offset_basis']=='normalized_segment':
            feature = features[identifier] if field=='text' else features[identifier]['title']
            text = feature['segments'][item['segment_index']]['text']
        else:
            raise ValueError('Unknown evidence offset basis')
        if text[item['start']:item['end']] != item['text']:
            raise ValueError('Evidence text does not match its declared source slice')
    boundary_count = 0
    for finding in findings.values():
        if not set(finding['source_record_ids'])<=supplied.keys():
            raise ValueError('Finding refers to an absent supplied record')
        if not set(finding['evidence_refs'])<=evidence.keys() or not set(finding['window_ids'])<=windows.keys():
            raise ValueError('Finding evidence/window reference is unresolved')
        if not set(finding['related_finding_ids'])<=findings.keys():
            raise ValueError('Related finding reference is unresolved')
        if finding['finding_type']=='style_boundary_candidate':
            boundary_count += 1
            if finding['method_id']!='pelt_l2_v1' or finding['method_version']!='1.0.1':
                raise ValueError('Boundary finding does not identify PELT method1.0.1')
    registry = json.loads((directory/'method_registry.json').read_bytes())
    methods = [row for row in registry['methods'] if row['method_id']=='pelt_l2_v1']
    if len(methods)!=1 or methods[0]['version']!='1.0.1':
        raise ValueError('Registry does not identify PELT method1.0.1')
    return {'status':'passed','source_record_count':len(supplied),'evidence_slice_count':len(evidence),
            'boundary_finding_count':boundary_count,'boundary_method_version':'1.0.1',
            'registry_pelt_method_version':methods[0]['version'],'all_source_evidence_window_and_finding_references_resolve':True}


def run_process(argv: list[str], repo: Path, timeout: float) -> dict:
    started = time.perf_counter()
    receipt = {'argv':argv,'cwd':str(repo)}
    try:
        completed = subprocess.run(argv,cwd=repo,check=False,capture_output=True,text=True,timeout=timeout)
        receipt.update(exit_code=completed.returncode,stdout=completed.stdout,stderr=completed.stderr)
    except (OSError,subprocess.TimeoutExpired) as exc:
        receipt.update(exit_code=None,error_type=type(exc).__name__,error=str(exc))
    receipt['elapsed_seconds'] = time.perf_counter()-started
    return receipt


def run(repo: Path, outroot: Path, qa: Path, *, overwrite: bool, timeout: float,
        expected_fingerprint: str | None = None) -> bool:
    summary = {'schema_version':'1.0.0','audit':'pr383_fixture_report_comparison','status':'pending',
               'network_isolation':os.environ.get('AHAS_NETWORK_ISOLATION','not_asserted'),
               'module_comparison':'Exact recursive values, permitting only the registered optimizer identifier replacement',
               'jsonl_comparison':'Exact bytes for records_features.jsonl, windows.jsonl, evidence.jsonl',
               'historical_outputs_modified':False,'truth_sidecars_read':False,
               'initial_report_rerender_identity':'not_checked_outside_this_audit',
               'expected_implementation_fingerprint':expected_fingerprint,'fixtures':[]}
    receipts = {'schema_version':'1.0.0','audit':'pr383_fixture_report_comparison','processes':[]}
    started = time.perf_counter()
    success = True
    qa.mkdir(parents=True,exist_ok=True)
    for fixture in FIXTURES:
        print('Generating and verifying '+fixture,flush=True)
        historical = repo/'output'/fixture
        directory = outroot/fixture
        records = repo/'fixtures'/f'{fixture}.jsonl'
        manifest = repo/'fixtures'/f'{fixture}.snapshot.json'
        prior_bytes = (historical/'results.json').read_bytes()
        historical_hashes = {name:digest((historical/name).read_bytes()) for name in ['results.json',*EXPORTS]}
        row = {'fixture':fixture,'status':'failed','historical_results_sha256':digest(prior_bytes),
               'input_sha256':digest(records.read_bytes()),'manifest_sha256':digest(manifest.read_bytes()),
               'analyze_exit_code':None,'verify_recompute_exit_code':None,'module_differences':[],
               'allowed_optimizer_replacements':[],'exports':{},'source_checks':None,'error':None}
        args = [sys.executable,'-m','account_history_analyzer','analyze','--input',str(records),
                '--manifest',str(manifest),'--out',str(directory)]
        if overwrite:
            args.append('--overwrite')
        generated = run_process(args,repo,timeout)
        receipts['processes'].append({'fixture':fixture,'operation':'analyze',**generated})
        row['analyze_exit_code'] = generated['exit_code']
        try:
            if generated['exit_code']!=0 or json.loads(generated['stdout']).get('status')!='complete':
                raise ValueError('Analyzer did not finish successfully')
            verified = run_process([sys.executable,'-m','account_history_analyzer','verify','--input',str(records),
                '--manifest',str(manifest),'--analysis-dir',str(directory),'--recompute'],repo,timeout)
            receipts['processes'].append({'fixture':fixture,'operation':'verify_recompute',**verified})
            row['verify_recompute_exit_code'] = verified['exit_code']
            if verified['exit_code']!=0 or json.loads(verified['stdout']).get('status')!='reproduced':
                raise ValueError('CLI verify --recompute did not reproduce the analysis')
            after_bytes = (directory/'results.json').read_bytes()
            prior,after = json.loads(prior_bytes),json.loads(after_bytes)
            row['current_results_sha256'] = digest(after_bytes)
            row['implementation_fingerprint'] = after['analysis']['implementation_fingerprint']
            if expected_fingerprint and row['implementation_fingerprint']!=expected_fingerprint:
                raise ValueError('Frozen implementation fingerprint changed')
            differences,accepted = module_differences(prior['modules'],after['modules'])
            row['module_differences'],row['allowed_optimizer_replacements'] = differences,accepted
            for name in EXPORTS:
                before_data,after_data = (historical/name).read_bytes(),(directory/name).read_bytes()
                row['exports'][name] = {'byte_identical':before_data==after_data,
                    'historical_sha256':digest(before_data),'current_sha256':digest(after_data)}
            row['source_checks'] = source_checks(directory,records,after)
            operational = {name:json.loads((directory/name).read_bytes()) for name in ['ingest_receipt.json','run_receipt.json']}
            receipts['processes'][-2]['analyzer_receipts'] = operational
            if operational['run_receipt.json']['network_isolation']!='linux_seccomp_socket_denial':
                raise ValueError('Analyzer receipt does not confirm networking was disabled')
            if any(digest((historical/name).read_bytes())!=value for name,value in historical_hashes.items()):
                raise ValueError('Historical output changed during this audit')
            if differences or not all(item['byte_identical'] for item in row['exports'].values()):
                raise ValueError('Numerical modules or source export bytes differ from the historical release')
            row['status'] = 'passed'
        except (OSError,ValueError,KeyError,TypeError,IndexError) as exc:
            row['error'] = {'type':type(exc).__name__,'message':str(exc)}
            success = False
        summary['fixtures'].append(row)
        summary['status'] = 'passed' if success and len(summary['fixtures'])==len(FIXTURES) else 'running' if success else 'failed'
        receipts['elapsed_seconds'] = time.perf_counter()-started
        (qa/'fixture-receipts.json').write_bytes(canonical(receipts))
        (qa/'fixture-comparison.json').write_bytes(canonical(summary))
        print(f'{fixture}: {row["status"]}',flush=True)
    return success


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--outroot',type=Path,help='New outputs root; default REPO/output/pr383')
    parser.add_argument('--qa',type=Path,help='New audit directory; default REPO/qa/pr383')
    parser.add_argument('--timeout',type=float,default=600,help='Per-process timeout in seconds')
    parser.add_argument('--overwrite',action='store_true',help='Replace this audit/new fixture outputs only')
    parser.add_argument('--expected-fingerprint',help='Require the frozen implementation fingerprint')
    args = parser.parse_args()
    repo = args.repo.resolve()
    outroot = (args.outroot or repo/'output/pr383').resolve()
    qa = (args.qa or repo/'qa/pr383').resolve()
    if args.timeout<=0:
        parser.error('--timeout must be positive')
    if os.environ.get('AHAS_NETWORK_ISOLATION')!='linux_seccomp_socket_denial':
        parser.error('Run this script through scripts/offline_exec.py')
    for name in FIXTURES:
        historical = (repo/'output'/name).resolve()
        for label,candidate in [('--outroot',outroot),('--qa',qa)]:
            if candidate==historical or candidate in historical.parents or historical in candidate.parents:
                parser.error(label+' must not overlap a historical fixture output')
    if not args.overwrite and (outroot.exists() or any((qa/name).exists() for name in ['fixture-receipts.json','fixture-comparison.json'])):
        parser.error('New output/audit already exists; use --overwrite explicitly')
    return 0 if run(repo,outroot,qa,overwrite=args.overwrite,timeout=args.timeout,
                    expected_fingerprint=args.expected_fingerprint) else 1


if __name__=='__main__':
    raise SystemExit(main())
