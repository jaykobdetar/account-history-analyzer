#!/usr/bin/env python3
"""Prespecified independent arithmetic check of 72 frozen raw distances.

No evaluator/feature/distance aggregation functions are imported. The frozen
preprocessor supplies segments, masks, and token offsets; this module builds
its own counts, cosine and base-2 Jensen-Shannon arithmetic. Sample selection
uses only frozen pair identities, before reading qualification or outcomes.
This is preparatory code until separately frozen and authorized for execution.
"""
from collections import Counter, defaultdict
from hashlib import sha256
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import time

from account_history_analyzer.config import AnalysisConfig, resource_bytes
from account_history_analyzer.io import digest
from account_history_analyzer.pipeline import implementation_identity
from account_history_analyzer.text import preprocess

SALT = 'ahas-pilot3-raw-distance-check-v1:'
METHODS = (('cosine_distance_v1','retained_prose',4),
           ('cosine_distance_v1','function_mask_v1',4),
           ('function_word_js_v1','lexical_tokens',None))
ARMS = ('full','hash75','hash50','middle50')
FINGERPRINT = 'bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179'
CONFIG = '8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925'
LIMITS = {'comparisons':72, 'requested_unit_sides':144, 'unique_units':48,
          'preprocessor_calls':15000, 'retained_words':300000,
          'wall_seconds':600, 'address_space_bytes':4*1024**3,
          'source_input_bytes':100*1024**2, 'output_bytes':100*1024**2}
TOLERANCE = 1e-12


class CheckFailure(ValueError):
    """Fixed public-safe reason codes only."""


def need(value, code):
    if not value:
        raise CheckFailure(code)


def canonical(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':'))+'\n').encode()


def sha_file(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def safe_child(root, name):
    p = Path(name)
    need(not p.is_absolute() and '..' not in p.parts,'unsafe_frozen_path')
    p = (root/p).resolve()
    need(p.is_relative_to(root.resolve()),'input_outside_registered_root')
    return p


def rank(pair_id):
    return sha256((SALT+pair_id).encode()).digest(), pair_id


def select_cases(index, datasets, *, synthetic=False):
    """Exactly two distinct pair IDs per stratum/method/arm, no outcomes."""
    strata = {row['stratum_id'] for row in index}
    if not synthetic:
        need(len(index)==360 and len(strata)==3,'complete_fixed_batch_index_required')
    cells, seen = defaultdict(list), set()
    for item in index:
        method = tuple(item[k] for k in ('method_id','view','n'))
        need(method in METHODS and item['arm'] in ARMS,'unregistered_method_or_arm')
        key = item['stratum_id'], method, item['arm']
        data = datasets[item['batch_id']]
        need(data['protocol']['distance']==dict(zip(('method_id','view','n'),method)), 'dataset_method_changed')
        need(len(data['pairs'])==16,'incomplete_planned_pair_rows')
        for pair in data['pairs']:
            identifier = key + (pair['pair_id'],)
            need(identifier not in seen and pair['split']=='evaluation','duplicate_or_unplanned_pair')
            seen.add(identifier)
            cells[key].append({'batch':item,'pair':pair})
    need(set(cells)=={(s,m,a) for s in strata for m in METHODS for a in ARMS},'incomplete_sample_design')
    selected = []
    for sid in sorted(strata):
        for method in METHODS:
            for arm in ARMS:
                rows = cells[sid,method,arm]
                need(len(rows)>=2,'sample_population_too_small')
                selected.extend(sorted(rows,key=lambda row:rank(row['pair']['pair_id']))[:2])
    if not synthetic:
        need(len(selected)==72,'fixed_sample_size_changed')
    return selected


def character_counts(segments, n=4):
    need(type(n) is int and n>0,'invalid_ngram_length')
    counts = Counter()
    for segment in segments:
        for start in range(max(0,len(segment)-n+1)):
            counts[segment[start:start+n]] += 1
    return counts


def cosine(left, right):
    """Independent count-domain dot product, without production max scaling."""
    need(all(type(v) is int and v>=0 for c in (left,right) for v in c.values()),'invalid_character_count')
    if not sum(left.values()) or not sum(right.values()):
        return None
    if left==right:
        return 0.0
    dot = sum(v*right.get(k,0) for k,v in left.items())
    norm_left = sum(v*v for v in left.values())
    norm_right = sum(v*v for v in right.values())
    answer = 1.0-dot/math.sqrt(norm_left*norm_right)
    need(-TOLERANCE<=answer<=1+TOLERANCE,'cosine_out_of_range')
    return min(1.0,max(0.0,answer))


def js_distance(left, right, vocabulary):
    """Normalize integer token counts directly, with fixed OTHER_WORD category."""
    need(all(type(v) is int and v>=0 for c in (left,right) for v in c.values()),'invalid_word_count')
    nx,ny = sum(left.values()),sum(right.values())
    if not nx or not ny:
        return None
    vocabulary = sorted(set(vocabulary))
    x = [left.get(w,0) for w in vocabulary]; y = [right.get(w,0) for w in vocabulary]
    x.append(nx-sum(x)); y.append(ny-sum(y))
    terms = []
    for count_x,count_y in zip(x,y):
        p,q = count_x/nx,count_y/ny
        midpoint = (p+q)/2
        if p:
            terms.append(p*math.log2(p/midpoint)/2)
        if q:
            terms.append(q*math.log2(q/midpoint)/2)
    divergence = math.fsum(terms)
    need(-TOLERANCE<=divergence<=1+TOLERANCE,'js_out_of_range')
    return math.sqrt(min(1.0,max(0.0,divergence)))


def representations(records, manifest, config):
    """Frozen parsing only; independent counting from word-kind token offsets."""
    original_ids, retained, masked, words = set(), [], [], Counter()
    kinds,languages = set(),set()
    eligible_records,eligible_words,total_words = 0,0,0
    for record in records:
        need(record['id'] not in original_ids,'duplicate_unit_record')
        original_ids.add(record['id'])
        derived = preprocess(record,manifest,config)
        kinds.add(record['kind']); languages.add(derived['language'])
        count = 0
        if derived['usable']:
            retained.extend(segment['text'] for segment in derived['segments'])
            masked.extend(derived['masked_segments'])
            for group in derived['token_offsets']:
                for token in group:
                    if token['kind']=='word':
                        words[token['normalized']] += 1
                        count += 1
            total_words += count
            if derived['language']=='en' and count>=20:
                eligible_records += 1; eligible_words += count
    return {'retained_prose':character_counts(retained), 'function_mask_v1':character_counts(masked),
            'lexical_tokens':words, 'records':len(records), 'retained_words':total_words,
            'eligible_records':eligible_records, 'eligible_words':eligible_words,
            'kinds':kinds,'languages':languages}


def independent_result(left,right,method,vocabulary):
    need(method in METHODS,'unregistered_distance')
    english = left['languages']==right['languages']=={'en'}
    reasons = set()
    if any(s['eligible_records']<8 or s['eligible_words']<1000 for s in (left,right)):
        reasons.add('insufficient_comparable_text')
    if len(left['kinds'])!=1 or left['kinds']!=right['kinds']:
        reasons.add('incompatible_kind_scope')
    if not english:
        reasons.add('english_not_declared_for_both_scopes')
    if method[1] in ('function_mask_v1','lexical_tokens') and not english:
        value = None; distance_status='not_run'
    else:
        value = (js_distance(left['lexical_tokens'],right['lexical_tokens'],vocabulary)
                 if method[0]=='function_word_js_v1' else cosine(left[method[1]],right[method[1]]))
        distance_status = 'ok' if value is not None else 'not_computable'
        if value is None:
            reasons.add('empty_representation')
    qualified = not reasons and value is not None
    return {'raw_distance':value,'score':value if qualified else None,
            'status':'ok' if qualified else 'abstained','distance_status':distance_status,
            'reason_codes':sorted(reasons)}


def compare_result(expected,actual):
    errors = []
    for field in ('raw_distance','score'):
        a,b = expected[field],actual[field]
        if a is None or b is None:
            need(a is None and b is None,'unavailable_distance_or_score_changed')
        else:
            need(type(b) in (float,int) and math.isfinite(b) and 0<=b<=1,'nonfinite_or_out_of_range_result')
            need(math.isclose(a,b,rel_tol=TOLERANCE,abs_tol=TOLERANCE),'raw_arithmetic_mismatch')
            errors.append(abs(a-b))
    need(expected['status']==actual['status'] and expected['distance_status']==actual['distance_status'] and
         expected['reason_codes']==sorted(actual['reason_codes']),'qualification_or_reasons_mismatch')
    return max(errors,default=0.0)


def run_check(prepared, executions, index, datasets, selected, freeze, config):
    execution = read(executions/'execution-index.json')
    need(execution['status']=='completed' and execution['replay'] is False and execution['executed_batches']==360,
         'complete_primary_execution_required')
    need(execution['freeze_sha256']==freeze['_file_sha256'],'execution_freeze_changed')
    runs = {r['batch_id']:r for r in execution['runs']}
    need(len(runs)==360 and set(runs)=={r['batch_id'] for r in index},'execution_batch_coverage')
    vocabulary = resource_bytes('function_words_en_v1.txt').decode().splitlines()
    cache, evaluation_cache = {}, {}
    calls, words, source_bytes, max_error, abstained, computable = 0,0,0,0.0,0,0
    input_hashes, output_hashes = {},{}
    for case in selected:
        item,pair = case['batch'],case['pair']; name=item['batch_id']
        dataset_path = safe_child(prepared,item['dataset']); data=datasets[name]
        unit_defs = {t['text_id']:t for t in data['texts']}
        representations_pair=[]
        for side in ('left_text_id','right_text_id'):
            cell=pair[side]; unit=unit_defs[cell]
            cache_key=item['stratum_id'],item['block_id'],item['arm'],cell
            source_path=safe_child(dataset_path.parent,unit['input'])
            manifest_path=safe_child(dataset_path.parent,unit['manifest'])
            hashes=(sha_file(source_path),sha_file(manifest_path))
            for path,h in ((source_path,hashes[0]),(manifest_path,hashes[1])):
                relative=str(path.relative_to(prepared))
                need(item['input_hashes'][relative]==h,'sample_input_hash_changed')
                input_hashes[relative]=h
            if cache_key in cache:
                need(cache[cache_key][0]==hashes,'method_units_not_byte_identical')
            else:
                need(len(cache)<LIMITS['unique_units'],'unique_unit_budget_exhausted')
                source_bytes+=source_path.stat().st_size+manifest_path.stat().st_size
                need(source_bytes<=LIMITS['source_input_bytes'],'source_byte_budget_exhausted')
                records=[]
                with source_path.open('rb') as handle:
                    for line in handle:
                        records.append(json.loads(line))
                        need(calls+len(records)<=LIMITS['preprocessor_calls'],'preprocessor_call_budget_exhausted')
                representation=representations(records,read(manifest_path),config)
                calls+=len(records); words+=representation['retained_words']
                need(words<=LIMITS['retained_words'],'retained_word_budget_exhausted')
                cache[cache_key]=hashes,representation
            representations_pair.append(cache[cache_key][1])
        if name not in evaluation_cache:
            output_path=safe_child(executions,name+'/evaluation.json'); h=sha_file(output_path)
            need(runs[name]['exit_code']==0 and runs[name]['output_files']['evaluation.json']['sha256']==h,'sample_evaluation_receipt_changed')
            evaluation=read(output_path)
            need(evaluation['implementation_fingerprint']==FINGERPRINT and evaluation['analysis_config_sha256']==CONFIG and
                 evaluation['distance']=={k:item[k] for k in ('method_id','view','n')},'sample_numerical_baseline_changed')
            rows=evaluation['partitions']['evaluation']['rows']
            need(len(rows)==16 and len({r['pair_id'] for r in rows})==16 and
                 {r['pair_id'] for r in rows}=={r['pair_id'] for r in data['pairs']},'sample_evaluation_incomplete')
            evaluation_cache[name]={r['pair_id']:r for r in rows}
            output_hashes[name]=h
        actual=evaluation_cache[name][pair['pair_id']]
        need(all(actual[k]==pair[k] for k in pair),'evaluated_pair_identity_changed')
        expected=independent_result(*representations_pair,tuple(item[k] for k in ('method_id','view','n')),vocabulary)
        max_error=max(max_error,compare_result(expected,actual))
        abstained+=expected['score'] is None; computable+=expected['raw_distance'] is not None
    return {'status':'passed','sampled_comparisons':len(selected),'requested_unit_sides':len(selected)*2,
            'unique_preprocessed_units':len(cache),'preprocessor_calls':calls,'retained_words_checked':words,
            'raw_distances_computable':computable,'qualified_scores_unavailable':abstained,
            'maximum_absolute_difference':max_error,'absolute_and_relative_tolerance':TOLERANCE,
            'source_input_bytes':source_bytes,'sample_input_hashes_sha256':sha256(canonical(input_hashes)).hexdigest(),
            'sample_evaluation_hashes_sha256':sha256(canonical(output_hashes)).hexdigest(),
            'frozen_evaluator_calls':0,'original_archives_read':0,'private_source_values_published':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('freeze','prepared','executions','out'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS,(LIMITS['address_space_bytes'],)*2)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError()))
    signal.alarm(LIMITS['wall_seconds']); started=time.monotonic()
    try:
        need(not args.out.exists(),'output_already_exists')
        freeze=read(args.freeze)
        need(freeze['status']=='frozen_before_first_style_score' and freeze['scoring_authorized'] is True,'pre_score_registration_required')
        code_hash=sha_file(__file__)
        need(any(Path(r['path']).resolve()==Path(__file__).resolve() and r['sha256']==code_hash for r in freeze['bound_artifacts']),
             'checker_not_bound_before_scoring')
        need(implementation_identity()[0]==FINGERPRINT and freeze['implementation_fingerprint']==FINGERPRINT,'frozen_implementation_changed')
        config=AnalysisConfig.from_toml()
        need(digest(config.analytical())==CONFIG and freeze['analysis_config_sha256']==CONFIG,'frozen_configuration_changed')
        prepared=args.prepared.resolve(); executions=args.executions.resolve()
        need(sha_file(prepared/'batch-index.json')==freeze['batch_index_sha256'],'frozen_batch_index_changed')
        index=read(prepared/'batch-index.json'); datasets={}
        for row in index:
            path=safe_child(prepared,row['dataset'])
            need(sha_file(path)==row['dataset_sha256'],'frozen_dataset_changed')
            datasets[row['batch_id']]=read(path)
        selected=select_cases(index,datasets)
        identifiers=[{**{k:c['batch'][k] for k in ('stratum_id','block_id','method_id','view','n','arm')},
                      'pair_id':c['pair']['pair_id']} for c in selected]
        binding={'status':'sample_frozen_before_reading_evaluator_rows','selection_rule':SALT,
                 'checker_sha256':code_hash,'freeze_sha256':sha_file(args.freeze),'limits':LIMITS,
                 'sample_identity_sha256':sha256(canonical(identifiers)).hexdigest(),
                 'sampled_comparisons':len(selected),'qualification_used_for_selection':False}
        args.out.parent.mkdir(parents=True,exist_ok=True)
        with args.out.with_suffix('.start-binding.json').open('xb') as handle:
            handle.write(canonical(binding))
        freeze['_file_sha256']=sha_file(args.freeze)
        report=run_check(prepared,executions,index,datasets,selected,freeze,config)
        report.update(binding)
        report['status']='passed'
    except Exception as error:
        report={'status':'failed','reason_codes':[str(error) if type(error) is CheckFailure else 'unexpected_'+type(error).__name__],
                'checker_sha256':sha_file(__file__),'private_source_values_published':False,'frozen_evaluator_calls':0}
    report.update(wall_seconds=time.monotonic()-started,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('xb') as handle:
        handle.write(canonical(report))
    signal.alarm(0)
    print(json.dumps(report,sort_keys=True))
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':
    raise SystemExit(main())
