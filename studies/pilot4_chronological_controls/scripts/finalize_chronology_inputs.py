"""Post-audit deterministic cohort and full factorial snapshots; never analyze."""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
from fractions import Fraction
from itertools import combinations
import json
import hashlib
import os
from pathlib import Path
import resource
import time
from chronology_math import factorial_cases, reconstruct_windows, legal_grid
from metadata_feasibility import select_prefix, compatible, edge_cost, identity_order, seconds, jsonable
from run_full_chronology import sha, write
from prepare_chronology_pool import validate_plan


def original_comment_record(source):
    """Independent source-field projection; submissions cannot become comments."""
    if source.get('root') == source['id']:
        raise ValueError('A source submission cannot enter a whole-comment construction')
    return {'schema_version': '1.0.0', 'id': source['id'], 'account_id': source['user'],
        'kind': 'comment', 'text': source['text'], 'status': 'present',
        'created_utc': datetime.fromtimestamp(source['timestamp'], timezone.utc).isoformat().replace('+00:00', 'Z'),
        'subreddit': source['meta']['subreddit'], 'language': None, 'edit_state': 'unknown',
        'edited_utc': None, 'title': None, 'parent_id': source.get('reply_to'),
        'thread_id': source.get('root'), 'parent_created_utc': None,
        'permalink': source['meta'].get('permalink')}


def bind_audit(plan, plan_path, pool_path, audit_path, freeze_path, public_path):
    """Bind the completed audit to exactly the prepared pool and all provenance.

    Private audit content alone has no input hash. Its public receipt and frozen
    input manifest must agree, including the protected-history inventory, engine,
    wrapper and rules. Unknown unavailable historical content remains disclosed;
    available content and grouping must have completed before selecting a cohort.
    """
    pool_path = Path(pool_path)
    root = pool_path.parent
    preparation = json.loads((root/'preparation.json').read_bytes())
    preparation_binding = json.loads((root/'start-binding.json').read_bytes())
    if (preparation['status'] != 'candidate_pool_prepared_not_audited_or_scored'
            or preparation['plan_sha256'] != sha(plan_path)
            or preparation_binding['plan_sha256'] != sha(plan_path)
            or preparation_binding['script_sha256'] != plan['script_sha256']
            or preparation['style_scores_computed'] != 0):
        raise ValueError('Candidate preparation does not match the frozen construction plan')
    for key, path in [('candidate_pool', pool_path), ('selection', root/'selection.json'),
                      ('original_source_lines', root/'original-source-lines.jsonl'),
                      ('original_source_index', root/'original-source-index.json'),
                      ('start_binding', root/'start-binding.json')]:
        if preparation[key+'_sha256'] != sha(path):
            raise ValueError('Candidate preparation artifact changed')
    freeze = json.loads(Path(freeze_path).read_bytes())
    public = json.loads(Path(public_path).read_bytes())
    audit = json.loads(Path(audit_path).read_bytes())
    if freeze['state'] != 'frozen_before_audit':
        raise ValueError('Pre-audit input freeze required')
    dependencies = {'candidate_pool': pool_path, 'historical_inventory': plan['historical_inventory'],
                    'engine': plan['audit_engine'], 'wrapper': plan['audit_wrapper'], 'rules': plan['audit_rules']}
    for key, path in dependencies.items():
        if freeze[key+'_sha256'] != sha(path):
            raise ValueError('Audit freeze does not match the current registered input')
    if (public['private_audit_sha256'] != sha(audit_path) or public['freeze_sha256'] != sha(freeze_path)
            or any(public[key+'_sha256'] != freeze[key+'_sha256'] for key in ('engine', 'wrapper', 'rules'))):
        raise ValueError('Audit public/private/input hash chain disagrees')
    summary = audit['summary']
    if (audit.get('actionable') is not True or summary.get('status') != 'audited'
            or summary.get('gate_b_ready') is not True
            or summary.get('available_content_and_grouping_audit_complete') is not True
            or summary.get('scores_computed') is not False or audit['engine_audit']['status'] != 'audited'
            or any(public.get(key) != value for key, value in summary.items())):
        raise ValueError('Complete available-content and grouping audit required')
    if pool_path.stat().st_size > 268435456:
        raise ValueError('Candidate pool byte ceiling exceeded')
    entries = {}
    assignments = {a: spec for spec in plan['strata'] for a in spec['accounts']}
    with pool_path.open() as handle:
        for line in handle:
            row = json.loads(line)
            record = row['record']; rid = record['id']; account = row['account_key']
            if rid in entries or len(entries) >= 100000:
                raise ValueError('Duplicate source ID or candidate record ceiling exceeded')
            if account not in assignments or account != record['account_id'].casefold():
                raise ValueError('Pool source account differs from registered assignment')
            spec = assignments[account]
            if (row['stratum_id'] != spec['stratum_id'] or row['community'] not in spec['communities']
                    or row['community'] != record['subreddit'] or row['period'] not in ('early', 'late')
                    or record['kind'] != 'comment' or record['status'] != 'present'
                    or not isinstance(record['text'], str) or len(record['text']) > 200000
                    or record['language'] not in (None, 'en')
                    or not isinstance(record['thread_id'], str) or not record['thread_id']
                    or type(row['retained_words']) is not int or not 20 <= row['retained_words'] <= 500):
                raise ValueError('Candidate pool identity, metadata or whole-comment rule differs')
            cut = seconds(spec['cut']); stamp = seconds(record['created_utc'])
            lo, hi = (cut-180*86400, cut) if row['period'] == 'early' else (cut, cut+180*86400)
            if not lo <= stamp < hi:
                raise ValueError('Candidate record lies outside the registered half')
            entries[rid] = row
    total_words = sum(row['retained_words'] for row in entries.values())
    if (not entries or total_words > 2000000 or preparation['records'] != len(entries)
            or preparation['retained_words'] != total_words or preparation['accounts'] != len(assignments)):
        raise ValueError('Prepared pool counts differ from content')
    selection = json.loads((root/'selection.json').read_bytes())['selected_metadata']
    offsets = json.loads((root/'original-source-index.json').read_bytes())
    if set(selection) != set(entries) or set(offsets) != set(entries):
        raise ValueError('Prepared source-selection coverage differs from pool')
    cursor = 0
    with (root/'original-source-lines.jsonl').open('rb') as originals:
        for rid in sorted(offsets, key=lambda rid: offsets[rid]['offset']):
            offset = offsets[rid]; row = entries[rid]; record = row['record']; expected = selection[rid]
            if offset['offset'] != cursor or type(offset['bytes']) is not int or offset['bytes'] < 1:
                raise ValueError('Original-source byte spans must form a complete nonoverlapping sequence')
            raw = originals.read(offset['bytes']); cursor += len(raw)
            digest = hashlib.sha256(raw).hexdigest()
            if digest != offset['sha256'] or digest != expected['source_line_sha256']:
                raise ValueError('Original source line hash differs from census')
            source = json.loads(raw)
            if (expected['record_id'] != rid or expected['created_utc'] != record['created_utc']
                    or any(expected[k] != row[k] for k in ('account_key', 'community', 'stratum_id', 'period', 'retained_words'))):
                raise ValueError('Candidate metadata differs from registered source selection')
            converted = original_comment_record(source)
            if converted != record:
                raise ValueError('Whole original comment text or source metadata changed during conversion')
        if originals.read(1):
            raise ValueError('Unindexed original source bytes remain')
    purged, survivors = audit['purge_record_ids'], audit['surviving_candidate_ids']
    if (len(set(purged)) != len(purged) or len(set(survivors)) != len(survivors)
            or set(purged) & set(survivors) or set(purged) | set(survivors) != set(entries)):
        raise ValueError('Audit survivors and purges must exactly partition the prepared pool')
    provenance = audit['record_provenance']
    if any(type(row['historical']) is not bool for row in provenance.values()) or {
            rid for rid, row in provenance.items() if not row['historical']} != set(entries):
        raise ValueError('Audit candidate provenance coverage differs from pool')
    for rid, row in entries.items():
        expected = {'source_record_id': rid, 'source_kind': 'comment', 'text_component': 'body',
                    'historical': False, 'account_key': row['account_key'], 'stratum_id': row['stratum_id'],
                    'cell': [row['account_key'], row['community'], row['period']],
                    'thread_id': row['record']['thread_id'], 'declared_retained_words': row['retained_words']}
        if any(provenance[rid].get(key) != value for key, value in expected.items()):
            raise ValueError('Audit record provenance differs from prepared metadata')
    memberships = [rid for component in audit['engine_audit']['components'] for rid in component['record_ids']]
    if len(memberships) != len(set(memberships)) or set(memberships) != set(provenance):
        raise ValueError('Audit components must partition all provenance nodes')
    expected_purged = set()
    def purge_crossing(ids):
        candidate_ids = {rid for rid in ids if rid in entries}
        if any(provenance[rid]['historical'] for rid in ids) or len({tuple(provenance[rid]['cell']) for rid in candidate_ids}) > 1:
            expected_purged.update(candidate_ids)
    for component in audit['engine_audit']['components']:
        purge_crossing(component['record_ids'])
    threads = defaultdict(list)
    for rid, row in provenance.items():
        if row['thread_id']:
            threads[row['thread_id']].append(rid)
    for ids in threads.values():
        purge_crossing(ids)
    if (expected_purged != set(purged) or set(audit['purge_reasons']) != set(purged)
            or any(not reasons for reasons in audit['purge_reasons'].values())
            or summary['candidate_records'] != len(entries)
            or summary['candidate_retained_words'] != total_words
            or summary['purged_candidate_records'] != len(purged)
            or summary['surviving_candidate_records'] != len(survivors)):
        raise ValueError('Audit purge graph or summary counts disagree with candidate records')
    return entries, set(survivors), audit


def capped_matching(nodes, edges, cap):
    """Maximize up to cap<=2 disjoint blocks, then exact cost and identity order."""
    if type(cap) is not int or cap not in (1,2):
        raise ValueError('Registered block cap must be one or two')
    if len(nodes) != len(set(nodes)):
        raise ValueError('Repeated matching account')
    nodes = sorted(nodes, key=identity_order)
    order={n:i for i,n in enumerate(nodes)}
    normalized = {}
    for (a,b), cost in edges.items():
        if a == b or a not in order or b not in order or type(cost) not in (int, Fraction) or cost < 0:
            raise ValueError('Invalid matching edge or inexact cost')
        pair = tuple(sorted((a,b), key=order.__getitem__))
        if pair in normalized:
            raise ValueError('Repeated undirected matching edge')
        normalized[pair] = Fraction(cost)
    edges = normalized
    candidates=sorted(edges,key=lambda e:(order[e[0]],order[e[1]]))
    for count in range(cap,0,-1):
        best=None
        for pairs in combinations(candidates,count):
            if len({n for pair in pairs for n in pair})!=2*count:
                continue
            key=(sum((edges[e] for e in pairs),Fraction()),
                 tuple((order[a],order[b]) for a,b in pairs))
            if best is None or key<best[0]:
                best=(key,pairs)
        if best is not None:
            return list(best[1]),best[0][0]
    return [],Fraction()


def quantile(values,p):
    values=sorted(values); index=(len(values)-1)*p; lo=index.numerator//index.denominator
    return float(values[lo]+(values[min(lo+1,len(values)-1)]-values[lo])*(index-lo))


def summarize_cell(cell):
    words=[r['retained_words'] for r in cell['rows']]
    return {'records':len(words),'retained_words':sum(words),'word_overshoot':sum(words)-5000,
        'largest_record_words':max(words),'largest_record_share':max(words)/sum(words),
        'comment_length_quantiles':{str(p):quantile(words,p) for p in (Fraction(0),Fraction(1,4),Fraction(1,2),Fraction(3,4),Fraction(1))},
        'first_utc':datetime.fromtimestamp(cell['first_timestamp'],timezone.utc).isoformat().replace('+00:00','Z'),
        'last_utc':datetime.fromtimestamp(cell['last_timestamp'],timezone.utc).isoformat().replace('+00:00','Z'),
        'median_utc':datetime.fromtimestamp(float(cell['median_timestamp']),timezone.utc).isoformat().replace('+00:00','Z')}


def finalize(plan_path,pool_path,audit_path,out,public_out,*,audit_freeze,audit_public):
    if os.environ.get('AHAS_NETWORK_ISOLATION') != 'linux_seccomp_socket_denial':
        raise RuntimeError('Offline wrapper required')
    started = time.monotonic()
    resource.setrlimit(resource.RLIMIT_AS, (4294967296,)*2)
    plan, design = validate_plan(plan_path)
    capacity_exposed = {row['account_key'] for row in json.loads(Path(plan['exposure_flags']).read_bytes())['accounts']
                        if row['prior_capacity_only_exposure']}
    entries, surviving, audit = bind_audit(plan, plan_path, pool_path, audit_path, audit_freeze, audit_public)
    cells=defaultdict(list)
    for rid in surviving:
        row=entries[rid]
        cells[row['stratum_id'],row['account_key'],row['community'],row['period']].append({
            'record_id':rid,'timestamp':seconds(row['record']['created_utc']),
            'retained_words':row['retained_words']})
    out=Path(out);out.mkdir(mode=0o700,exist_ok=False)
    public_out=Path(public_out);public_out.mkdir(parents=True,exist_ok=False)
    produced = 0
    def reserve(size):
        nonlocal produced
        if produced + size > 268435456:
            raise RuntimeError('Final construction output byte ceiling exceeded')
        produced += size
    def bounded_write(path, value):
        reserve(len((json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()))
        write(path,value)
    bounded_write(out/'start-binding.json', {'plan_sha256':sha(plan_path), 'pool_sha256':sha(pool_path),
          'audit_sha256':sha(audit_path), 'audit_freeze_sha256':sha(audit_freeze),
          'audit_public_sha256':sha(audit_public), 'script_sha256':sha(__file__),
          'style_scores_computed':0, 'started_utc':datetime.now(timezone.utc).isoformat()})
    blocks=[];summaries=[];public_cells=[];all_case_rows=[];bound=[];used=set();cohort_accounts=set()
    for spec in plan['strata']:
        prepared={};sid=spec['stratum_id'];cut=seconds(spec['cut'])
        for account in spec['accounts']:
            selected={}
            for letter,community in zip(('X','Y'),spec['communities'],strict=True):
                for period in ('early','late'):
                    selected[letter+'/'+period]=select_prefix(cells[sid,account,community,period],cut,period,design)
            if all(selected.values()) and compatible(selected,selected,design):prepared[account]=selected
        nodes=sorted(prepared,key=identity_order)
        edges={(a,b):edge_cost(prepared[a],prepared[b],design) for i,a in enumerate(nodes)
               for b in nodes[i+1:] if compatible(prepared[a],prepared[b],design)}
        pairs,cost=capped_matching(nodes,edges,spec['block_cap'])
        summaries.append({'stratum_id':sid,'communities':spec['communities'],'cut':spec['cut'],
            'pool_accounts':len(spec['accounts']),'post_audit_qualified_accounts':len(nodes),
            'compatible_edges':len(edges),'planned_block_cap':spec['block_cap'],'selected_blocks':len(pairs),
            'block_deficit':spec['block_cap']-len(pairs),'selected_matching_cost':jsonable(cost)})
        for number,(a,b) in enumerate(pairs,1):
            if {a,b}&cohort_accounts:raise ValueError('Account reused across blocks/strata')
            cohort_accounts.update((a,b));block_id=sid+'-block-'+str(number).zfill(2)
            unit_cells={}
            for letter,account in [('A',a),('B',b)]:
                for cell_name,cell in prepared[account].items():
                    community,period=cell_name.split('/');cell_id=f'{block_id}:{letter}:{community}:{period}'
                    ids=[r['record_id'] for r in cell['rows']]
                    if set(ids)&used:raise ValueError('Source record reused in separate cells')
                    used.update(ids);unit_cells[cell_id]=ids
                    public_cells.append({'cell_id':cell_id,'block_id':block_id,'stratum_id':sid,
                        'account_role':letter,'community_role':community,'period':period,**summarize_cell(cell)})
            blocks.append({'block_id':block_id,'stratum_id':sid,'account_keys':[a,b],
                           'communities':spec['communities'],'cut':spec['cut'],'cells':unit_cells})
            for descriptor in factorial_cases(block_id):
                if time.monotonic()-started > 1800:
                    raise RuntimeError('Final construction time ceiling exceeded')
                case_id=descriptor['case_id'];left=unit_cells[descriptor['left_cell_id']];right=unit_cells[descriptor['right_cell_id']]
                ids=sorted(left+right,key=lambda rid:(seconds(entries[rid]['record']['created_utc']),rid))
                if ids[:len(left)]!=left or ids[len(left):]!=right:
                    raise ValueError('Canonical history crosses registered early/late ordering')
                case_dir=out/case_id;case_dir.mkdir(mode=0o700)
                input_path=case_dir/'records.jsonl';manifest_path=case_dir/'snapshot.json';metadata_path=case_dir/'metadata.json'
                records=[{**entries[rid]['record'],'account_id':case_id} for rid in ids]
                if any({k:v for k,v in record.items() if k != 'account_id'} !=
                       {k:v for k,v in entries[rid]['record'].items() if k != 'account_id'}
                       for rid,record in zip(ids,records,strict=True)):
                    raise ValueError('Construction changed fields beyond uniform account alias')
                with input_path.open('xb') as f:
                    for record in records:
                        raw=(json.dumps(record,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()
                        reserve(len(raw));f.write(raw)
                bounded_write(manifest_path,{'schema_version':'1.0.0','snapshot_id':case_id,'account_id':case_id,
                    'source_category':'research_corpus','text_format':'markdown','default_language':'en',
                    'source_notes':'Registered constructed source-account continuity/switch study; original timestamps and writing preserved. English is a corpus-level assumption.',
                    'coverage':{'status':'sampled','start_utc':records[0]['created_utc'],'end_utc':records[-1]['created_utc'],
                                'notes':'Whole-comment sample from two registered adjacent date bands; not a complete source-account history.'}})
                metadata=[{'record_id':rid,'retained_words':entries[rid]['retained_words'],
                           'created_utc':entries[rid]['record']['created_utc'],'style_eligible':True,'kind':'comment'} for rid in ids]
                bounded_write(metadata_path,{'records':metadata})
                windows=reconstruct_windows(metadata)
                row={**descriptor,'stratum_id':sid,'input':str(input_path.resolve()),'manifest':str(manifest_path.resolve()),
                     'metadata':str(metadata_path.resolve()),'truth_k':len(left) if descriptor['source_switch'] else None,
                     'control_junction_k':None if descriptor['source_switch'] else len(left),
                     'prescore_qualified_windows':sum(w['qualified'] for w in windows),'prescore_legal_grid':legal_grid(windows)}
                all_case_rows.append(row)
                bound.extend({'path':str(p.resolve()),'sha256':sha(p)} for p in (input_path,manifest_path,metadata_path))
    if sum(path.stat().st_size for path in out.rglob('*') if path.is_file()) > 268435456 or time.monotonic()-started > 1800:
        raise RuntimeError('Final construction output/time ceiling exceeded')
    bounded_write(out/'cohort.json',{'blocks':blocks,'selected_record_ids':sorted(used),'plan_sha256':sha(plan_path),
                            'audit_sha256':sha(audit_path),'pool_sha256':sha(pool_path),
                            'audit_freeze_sha256':sha(audit_freeze),'audit_public_sha256':sha(audit_public)})
    bound.append({'path':str((out/'cohort.json').resolve()),'sha256':sha(out/'cohort.json')})
    bounded_write(out/'index.json',{'cases':all_case_rows,'bound_files':bound,'prepared_block_count':len(blocks)})
    bounded_write(public_out/'selection-summary.json',{'strata':summaries,'blocks':len(blocks),'accounts':len(cohort_accounts),
        'selected_prior_capacity_only_exposure_accounts':len(cohort_accounts & capacity_exposed),
        'source_records':len(used),'planned_cases':len(all_case_rows),'independent_source_account_blocks':len(blocks),
        'candidate_pool_sha256':sha(pool_path),'audit_sha256':sha(audit_path),'index_sha256':sha(out/'index.json'),
        'source_words':sum(entries[r]['retained_words'] for r in used),'style_scores_computed':0})
    bounded_write(public_out/'cells.json',public_cells)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('plan','pool','audit','out','public-out','audit-freeze','audit-public'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();finalize(a.plan,a.pool,a.audit,a.out,a.public_out,audit_freeze=a.audit_freeze,audit_public=a.audit_public)
