"""Prepare a registered bounded content-audit pool; no style scores or features."""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import sys
import time
import zipfile
from metadata_feasibility import seconds
from run_full_chronology import sha, write

PAIR_CAPS = {frozenset(('AskPhysics', 'Physics')): (1, 2),
             frozenset(('linux', 'linuxquestions')): (2, 12),
             frozenset(('programming', 'learnprogramming')): (2, 12)}
DESIGN = {'half_band_days': 180, 'half_target_words': 5000, 'half_min_records': 40,
          'half_max_words': 5500, 'half_max_records': 200, 'record_word_min': 20,
          'record_word_max': 500, 'all_eight_cell_word_ratio_max': '11/10',
          'all_eight_cell_record_ratio_max': '5/4', 'within_period_four_cell_median_span_days_max': 30}


def validate_plan(plan_path):
    """Bind every consumed file and the unchanged design before touching sources."""
    plan = json.loads(Path(plan_path).read_bytes())
    scripts = Path(__file__).resolve().parent
    if (plan['phase'] != 'frozen_before_candidate_pool'
            or plan['script_sha256'] != sha(scripts/'prepare_chronology_pool.py')
            or plan['finalizer_sha256'] != sha(scripts/'finalize_chronology_inputs.py')):
        raise ValueError('Registered preparation and finalization scripts required')
    required = {str((scripts/name).resolve()) for name in (
        'prepare_chronology_pool.py', 'finalize_chronology_inputs.py', 'metadata_feasibility.py',
        'chronology_math.py', 'run_full_chronology.py')}
    required.update(str(Path(plan[key]).resolve()) for key in (
        'converter', 'feasibility_rules', 'exposure_flags', 'audit_wrapper', 'audit_engine',
        'audit_rules', 'historical_inventory'))
    required.add(str((Path(plan['converter']).resolve().parent/'cohort_selection.py').resolve()))
    required.update(str(Path(path).resolve()) for path in plan['metadata_files'])
    required.update(str(Path(source['archive']).resolve()) for source in plan['sources'])
    bindings = [str(Path(row['path']).resolve()) for row in plan['bound_artifacts']]
    if len(bindings) != len(set(bindings)) or not required.issubset(bindings):
        raise ValueError('Every consumed input and construction helper must be uniquely hash-bound')
    for row in plan['bound_artifacts']:
        if sha(row['path']) != row['sha256']:
            raise ValueError('Registered preparation dependency changed')
    design = json.loads(Path(plan['feasibility_rules']).read_bytes())
    if any(design[key] != value for key, value in DESIGN.items()):
        raise ValueError('Final date and volume gates differ from the original design')
    strata = plan['strata']
    if len(strata) != 3 or len({row['stratum_id'] for row in strata}) != 3:
        raise ValueError('Exactly three distinct registered strata required')
    if {frozenset(row['communities']) for row in strata} != set(PAIR_CAPS):
        raise ValueError('Unexpected amended community-pair set')
    accounts = []
    for spec in strata:
        sid = spec['stratum_id']
        if not isinstance(sid, str) or not sid or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in sid):
            raise ValueError('Unsafe opaque stratum identifier')
        if len(spec['communities']) != 2 or len(set(spec['communities'])) != 2:
            raise ValueError('Two distinct communities per stratum required')
        cap, account_cap = PAIR_CAPS[frozenset(spec['communities'])]
        count = len(spec['accounts'])
        allowed_count = (count == 0 and cap == 2) or 2 <= count <= account_cap
        if type(spec['block_cap']) is not int or spec['block_cap'] != cap or not allowed_count:
            raise ValueError('Amended stratum block or candidate-account cap changed')
        seconds(spec['cut'])
        if any(not isinstance(account, str) or not account or account != account.casefold() for account in spec['accounts']):
            raise ValueError('Candidate source identities must be canonical')
        accounts.extend(spec['accounts'])
    if len(accounts) != len(set(accounts)) or len(accounts) > 26:
        raise ValueError('Candidate account repeated across cells or strata')
    flags = json.loads(Path(plan['exposure_flags']).read_bytes())['accounts']
    flag_keys = [row['account_key'] for row in flags]
    if len(flag_keys) != len(set(flag_keys)) or any(not isinstance(a, str) or not a or a != a.casefold() for a in flag_keys):
        raise ValueError('Exposure identities must be unique and canonical')
    fields = ('pilot1_or_pilot2_or_private_mandatory_exclusion', 'pilot3_selected_scored_exposure', 'prior_capacity_only_exposure')
    if any(type(row[key]) is not bool for row in flags for key in fields):
        raise ValueError('Exposure flags must be boolean')
    mandatory = {row['account_key'] for row in flags if row[fields[0]]}
    scored = {row['account_key'] for row in flags if row[fields[1]]}
    if len(mandatory) != 57 or len(scored) != 60 or mandatory & scored or set(accounts) & (mandatory | scored):
        raise ValueError('The fixed 117 previously protected/scored exclusions must remain absent')
    communities = [source['community'] for source in plan['sources']]
    expected_communities = {community for spec in strata for community in spec['communities']}
    if len(communities) != len(set(communities)) or set(communities) != expected_communities:
        raise ValueError('Exactly one source archive per planned community required')
    hashes = {str(Path(row['path']).resolve()): row['sha256'] for row in plan['bound_artifacts']}
    if any(hashes[str(Path(source['archive']).resolve())] != source['sha256'] for source in plan['sources']):
        raise ValueError('Source archive binding disagrees with source declaration')
    if len(plan['metadata_files']) != len(set(str(Path(path).resolve()) for path in plan['metadata_files'])):
        raise ValueError('Repeated metadata input file')
    return plan, design


def buffer_prefix(rows, cut, period):
    if period not in ('early', 'late'):
        raise ValueError('Unknown candidate period')
    if any(type(row['retained_words']) is not int or row['retained_words'] < 0 for row in rows):
        raise ValueError('Candidate word counts must be nonnegative integers')
    start,end=(cut-180*86400,cut) if period=='early' else (cut,cut+180*86400)
    rows=sorted((r for r in rows if start<=seconds(r['created_utc'])<end and
                 20<=r['retained_words']<=500),key=lambda r:(abs(seconds(r['created_utc'])-cut),
                                                          seconds(r['created_utc']),r['record_id']))
    selected=[]; words=0
    for row in rows:
        if words+row['retained_words']>8500 or len(selected)==300:
            break
        selected.append(row); words+=row['retained_words']
        if words>=8000 and len(selected)>=64:
            break
    return selected


def prepare(plan_path, out):
    import os
    if os.environ.get('AHAS_NETWORK_ISOLATION')!='linux_seccomp_socket_denial':
        raise RuntimeError('Offline wrapper required')
    plan, _ = validate_plan(plan_path)
    resource.setrlimit(resource.RLIMIT_AS,(4294967296,)*2)
    start=time.monotonic()
    out=Path(out); out.mkdir(mode=0o700,exist_ok=False)
    output_bytes = 0
    def bounded_write(path, value):
        nonlocal output_bytes
        size = len((json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode())
        if output_bytes + size > 268435456:
            raise RuntimeError('Candidate output byte cap exceeded')
        write(path,value); output_bytes += size
    bounded_write(out/'start-binding.json',{'plan_sha256':sha(plan_path),'script_sha256':sha(__file__),
          'utc':datetime.now(timezone.utc).isoformat(),'style_scores_computed':0})
    # Reuse byte-preserving corpus conversion already exercised in pilot 3.
    sys.path.insert(0,str(Path(plan['converter']).resolve().parent))
    module_spec = importlib.util.spec_from_file_location('_pilot4_bound_corpus_converter', plan['converter'])
    converter = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(converter)
    convert_source = converter.convert_source
    assignments={a:s for s in plan['strata'] for a in s['accounts']}
    if len(assignments)!=sum(len(s['accounts']) for s in plan['strata']) or len(assignments)>26:
        raise ValueError('Duplicate/cross-stratum identity or account cap exceeded')
    cells=defaultdict(list); visited=set(); metadata_count=0
    for source in plan['metadata_files']:
        with Path(source).open() as f:
            for line in f:
                metadata_count+=1
                if metadata_count>3000000 or time.monotonic()-start>1800:
                    raise RuntimeError('Metadata preparation bound exhausted')
                row=json.loads(line)
                if row['account_key'] not in assignments or row['reason'] is not None:
                    continue
                spec=assignments[row['account_key']]
                if row['community'] not in spec['communities']:
                    continue
                if row['record_id'] in visited:
                    raise ValueError('Duplicate candidate source metadata')
                visited.add(row['record_id'])
                cells[row['account_key'],row['community']].append(row)
    selected={}; cell_counts=[]
    for spec in plan['strata']:
        for account in spec['accounts']:
            for community in spec['communities']:
                for period in ('early','late'):
                    rows=buffer_prefix(cells[account,community],seconds(spec['cut']),period)
                    for row in rows:
                        if row['record_id'] in selected:
                            raise ValueError('Candidate source record appears in two cells')
                        selected[row['record_id']]={**row,'stratum_id':spec['stratum_id'],'period':period}
                    cell_counts.append({'stratum_id':spec['stratum_id'],'account_key':account,
                        'community':community,'period':period,'records':len(rows),
                        'retained_words':sum(r['retained_words'] for r in rows)})
    if len(selected)>100000 or sum(r['retained_words'] for r in selected.values())>2000000:
        raise RuntimeError('Candidate audit pool cap exceeded')
    bounded_write(out/'selection.json',{'cells':cell_counts,'selected_metadata':selected})
    if not selected:
        raise ValueError('No whole-comment candidates available')
    source_rows=0; source_bytes=0; found=set(); receipts=[]; original_offsets={}
    with (out/'candidate-pool.jsonl').open('xb') as pool,(out/'original-source-lines.jsonl').open('xb') as originals:
        for source in plan['sources']:
            if sha(source['archive'])!=source['sha256']:
                raise ValueError('Source archive changed')
            count=0; member_sha=hashlib.sha256()
            with zipfile.ZipFile(source['archive']) as z:
                member=z.getinfo('utterances.jsonl'); source_bytes+=member.file_size
                if source_bytes>10000000000:
                    raise RuntimeError('Source decompression bound exceeded')
                with z.open(member) as f:
                    for line in f:
                        source_rows+=1; count+=1; member_sha.update(line)
                        if source_rows>15000000 or time.monotonic()-start>1800:
                            raise RuntimeError('Source rows/time bound exceeded')
                        source_row=json.loads(line)
                        # Reddit submissions and comments have separate bare-ID namespaces.
                        # Only original comments enter this registered study or ID lookup.
                        if source_row.get('root') == source_row['id']:
                            continue
                        identifier=source_row['id']
                        if identifier not in selected:
                            continue
                        expected=selected[identifier]
                        if source['community'] != expected['community']:
                            raise ValueError('Source archive community differs from candidate metadata')
                        if identifier in found or hashlib.sha256(line).hexdigest()!=expected['source_line_sha256']:
                            raise ValueError('Source record repeated or changed from census')
                        found.add(identifier)
                        converted=convert_source(source_row,expected)
                        entry={k:expected[k] for k in ('account_key','community','stratum_id','period','retained_words')}
                        entry['record']=converted
                        raw=(json.dumps(entry,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()
                        output_bytes+=len(raw)+len(line)
                        if output_bytes>268435456:
                            raise RuntimeError('Candidate output byte cap exceeded')
                        original_offsets[identifier] = {'offset': originals.tell(), 'bytes': len(line),
                                                        'sha256': hashlib.sha256(line).hexdigest()}
                        pool.write(raw); originals.write(line)
            receipts.append({'community':source['community'],'source_rows':count,
                             'utterances_sha256':member_sha.hexdigest(),'archive_sha256':source['sha256']})
    if found!=set(selected):
        raise ValueError('Selected source records were not all found')
    bounded_write(out/'original-source-index.json', original_offsets)
    if sum(path.stat().st_size for path in out.iterdir() if path.is_file()) > 268435456 or time.monotonic()-start > 1800:
        raise RuntimeError('Preparation final output/time bound exhausted')
    bounded_write(out/'preparation.json',{'status':'candidate_pool_prepared_not_audited_or_scored',
        'plan_sha256':sha(plan_path),'records':len(selected),
        'retained_words':sum(r['retained_words'] for r in selected.values()),'accounts':len(assignments),
        'source_rows':source_rows,'source_uncompressed_bytes':source_bytes,'sources':receipts,
        'candidate_pool_sha256':sha(out/'candidate-pool.jsonl'),
        'selection_sha256':sha(out/'selection.json'),
        'original_source_lines_sha256':sha(out/'original-source-lines.jsonl'),
        'original_source_index_sha256':sha(out/'original-source-index.json'),
        'start_binding_sha256':sha(out/'start-binding.json'),'wall_seconds':time.monotonic()-start,
        'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,'style_scores_computed':0})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();prepare(a.plan,a.out)
