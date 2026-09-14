from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
import hashlib, json

R=Path('/home/jaykob/.codex/visualizations/2026/09/13/01a09a32-1ca6-7983-93da-5f7da689ab16/ahas-pilot2-20260914')
P=R/'prepared/paired-registered'
def read(path):return json.loads(path.read_bytes())
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def desc(values):
    good=[v for v in values if v is not None]
    return {'observed_count':len(good),'unavailable_count':len(values)-len(good),
        'min':min(good) if good else None,'median':median(good) if good else None,'max':max(good) if good else None}
def seconds(value):return datetime.fromisoformat(value).timestamp() if value else None
def fmt(value,digits=1):return 'unavailable' if value is None else f'{value:,.{digits}f}'
def triple(summary,digits=1):return ' / '.join(fmt(summary[k],digits) for k in ('min','median','max'))
def link(label,name):return f'[{label}]({R/name})'
plan=read(R/'protocol/plan.json');registration=read(R/'protocol/registration.json')
assert sha(R/'protocol/plan.json')==registration['files']['protocol/plan.json']
summary=read(P/'preparation-summary.json');candidate=read(P/'candidate-summary.json')
units=read(P/'private/units.json');blocks=read(P/'private/blocks.json')
pair_obs=read(P/'private/pair-observations.json');frame=read(R/'inventory/source-frame-summary.json')
verified=read(R/'inventory/paired-prepared-check.json');replay=read(R/'inventory/paired-registered-replay.json')
assert verified['status']=='passed'
assert sha(P/'prepared-sha256.json')==verified['prepared_manifest_sha256']
for name,expected in read(P/'prepared-sha256.json').items():assert sha(P/name)==expected
unitgroups=defaultdict(list)
for unit in units:unitgroups[unit['split'],unit['home_community'],unit['condition'],unit['arm']].append(unit)
pairgroups=defaultdict(list)
for block in blocks:
    for condition in plan['paired']['conditions']:
        for arm in plan['paired']['arms']:
            group=[unit for unit in units if unit['block_id']==block['block_id'] and unit['condition']==condition and unit['arm']==arm]
            bykey={(unit['account_key'],unit['cell']):unit for unit in group}
            a,b=block['account_keys']
            for la,ra,label in [(a,a,'same_author'),(b,b,'same_author'),(a,b,'different_author'),(b,a,'different_author')]:
                left,right=bykey[la,'early'],bykey[ra,'late'];lt,rt=seconds(left['stats']['median_utc']),seconds(right['stats']['median_utc'])
                pairgroups[block['split'],block['home_community'],condition,arm].append({'label':label,
                    'guard_qualified':left['stats']['qualified_for_production_comparison'] and right['stats']['qualified_for_production_comparison'],
                    'time_gap_days':abs(lt-rt)/86400 if lt is not None and rt is not None else None,
                    'word_imbalance':abs(left['stats']['actual_eligible_words']-right['stats']['actual_eligible_words']),
                    'record_imbalance':abs(left['stats']['eligible_records']-right['stats']['eligible_records'])})
coverage=[]
for split in plan['splits']:
    for home in plan['communities']:
        for condition in plan['paired']['conditions']:
            for arm in plan['paired']['arms']:
                key=(split,home,condition,arm);group=unitgroups[key];pairs=pairgroups[key]
                missing={dim:sum(not u['groups'].get(dim) for u in group) for dim in ['author','thread','source_document','near_duplicate_cluster','related_sample']}
                labels={label:{'planned_pairs':sum(p['label']==label for p in pairs),
                    'pre_score_guard_qualified_pairs':sum(p['label']==label and p['guard_qualified'] for p in pairs),
                    'pair_median_time_gap_days':desc([p['time_gap_days'] for p in pairs if p['label']==label]),
                    'absolute_word_imbalance':desc([p['word_imbalance'] for p in pairs if p['label']==label]),
                    'absolute_record_imbalance':desc([p['record_imbalance'] for p in pairs if p['label']==label])}
                    for label in ['same_author','different_author']}
                same,different=(labels[label]['pair_median_time_gap_days']['median'] for label in ['same_author','different_author'])
                coverage.append({'split':split,'home_community':home,'condition':condition,'arm':arm,
                    'selected_accounts':4,'distinct_two_account_blocks':2,'planned_units':len(group),
                    'guard_qualified_units':sum(u['stats']['qualified_for_production_comparison'] for u in group),
                    'empty_units':sum(u['stats']['eligible_records']==0 for u in group),
                    'planned_proxy_pair_slots':len(pairs),'guard_qualified_proxy_pair_slots':sum(p['guard_qualified'] for p in pairs),
                    'pairs_in_scored_dataset_per_method':len(pairs) if split!='confirmation' else 0,
                    'actual_distance_qualified_pairs':None,'distance_qualification_status':'not_examined_in_preparation_review',
                    'missing_group_units':missing,'target_B':desc([u['stats']['target_B'] for u in group]),
                    'actual_eligible_words':desc([u['stats']['actual_eligible_words'] for u in group]),
                    'overshoot_words':desc([u['stats']['overshoot_words'] for u in group]),
                    'eligible_records':desc([u['stats']['eligible_records'] for u in group]),
                    'largest_record_share':desc([u['stats']['largest_record_share'] for u in group]),
                    'target_reached_units':sum(u['stats']['target_reached'] for u in group),
                    'observed_UTC_start':min((u['stats']['first_utc'] for u in group if u['stats']['first_utc']),default=None),
                    'observed_UTC_end':max((u['stats']['last_utc'] for u in group if u['stats']['last_utc']),default=None),
                    'class_preparation_summary':labels,
                    'same_minus_different_median_time_gap_days':same-different if same is not None and different is not None else None})
full_totals=[]
for split in plan['splits']:
    for condition in plan['paired']['conditions']:
        group=[row for row in coverage if row['split']==split and row['condition']==condition and row['arm']=='full']
        full_totals.append({'split':split,'condition':condition,**{key:sum(row[key] for row in group) for key in ['planned_units','guard_qualified_units','empty_units','planned_proxy_pair_slots','guard_qualified_proxy_pair_slots']}})
sources=[{'community':s['community'],'rows':s['counts']['rows'],'comments':s['counts']['comments'],
    'source_archive_sha256':s['archive_sha256'],'present_comments':s['counts']['comment_status_present'],
    'removed_or_deleted_comments':sum(s['counts'].get('comment_status_'+k,0) for k in ['removed','deleted']),
    'excluded_comment_counts':{key:s['counts'].get(key,0) for key in ['excluded_comments_old_pilot_account','excluded_comments_placeholder_account','excluded_comments_automoderator_account']},
    'additional_account_community_keys':s['additional_account_community_keys'],'duplicate_ids':s['duplicated_id_count'],
    'first_utc':s['first_utc'],'last_utc':s['last_utc']} for s in frame['sources']]
receipts=[('Seven synthetic adapter checks','inventory/paired-adapter-final-tests.receipt.json'),
    ('Independent retained-word/ranking preflight','inventory/paired-preflight-run.receipt.json'),
    ('Actual source fidelity','logs/candidate-fidelity.receipt.json'),
    ('Original candidate process','inventory/paired-candidates.receipt.json'),
    ('Preserved failed original finalize','inventory/paired-finalize-run.receipt.json'),
    ('Registered candidate replay','inventory/paired-registered-candidates-run.receipt.json'),
    ('Replay identity verification','inventory/paired-registered-replay-check-run.receipt.json'),
    ('Completed paired leakage audit','logs/paired-leakage-audit.receipt.json'),
    ('Registered finalization','inventory/paired-registered-finalize-run.receipt.json'),
    ('Independent actual prepared-input checks','inventory/paired-prepared-check-run.receipt.json')]
receiptfacts=[]
for label,name in receipts:
    receipt=read(R/name)
    receiptfacts.append({'description':label,'path':name,'sha256':sha(R/name),
        'exit_code':receipt['exit_code'],'wall_seconds':receipt['wall_seconds'],
        'peak_rss_kib':receipt.get('peak_rss_kib'),'started_utc':receipt['started_utc']})
limits=[
    'This is a volume-selected pilot from three educational communities in one historical ConvoKit/Pushshift Reddit collection, not a probability sample of Reddit accounts or independent corpus replications.',
    'Labels denote equality or inequality of casefolded source account keys only. Shared or automated accounts and multiple accounts belonging to one person remain possible.',
    'English is a corpus assumption; original authorship, language, edit history and complete account coverage are not established.',
    'Four pairs share each two-account block; methods, conditions and omission arms reuse sources. Pair counts are not independent people and do not justify IID intervals or broad accuracy claims.',
    'The initial historical pilot was inspected and is development evidence; its 12 accounts were excluded rather than relabeled as held-out.',
    'Missing group arrays in empty units are omitted to satisfy the external schema. The evaluator can therefore report not_auditable for a dimension despite the completed candidate-population audit; no passed labels are fabricated.',
    'Observed group disjointness covers the registered exact/near/template/recognized-quotation audit. Unmarked/indirect quotations, paraphrases and shared outside sources may remain.',
    'Pre-score word/record qualification is necessary but does not certify nondegenerate distance vectors, method availability or scientific validity. Actual distance-qualified counts are unexamined/null here.',
    'Confirmation metadata and preparation budgets are summarized only for capacity inspection. Confirmation records are physically absent from all scored dataset documents; no confirmation representation or distance is examined here.',
    'Cross-community support is sparse and remains as empty or insufficient units; no replacement, refill, changed threshold or post-score selection improves those counts.'
]
inputs=['protocol/plan.json','protocol/registration.json','inventory/source-frame-summary.json',
    'inventory/paired-preflight.json','inventory/paired-prepared-check.json','inventory/paired-registered-replay.json',
    'prepared/paired-registered/preparation-summary.json','prepared/paired-registered/prepared-sha256.json']
result={'review_type':'sanitized_preparation_and_coverage','contains_comparison_results':False,
    'protocol_id':plan['protocol_id'],'source_release':plan['source_release'],
    'protocol_plan_sha256':sha(R/'protocol/plan.json'),'implementation_fingerprint':plan['implementation_fingerprint'],
    'analysis_config_sha256':plan['analysis_config_sha256'],'registered_utc':registration['registered_utc'],
    'source_scope':sources,'sampling':{'available_global_casefolded_accounts':sum(row['available_account_keys'] for row in candidate['metadata_strata']),
        'old_accounts_excluded':12,'metadata_shortlisted_accounts':180,'selected_accounts':36,
        'rejected_after_capacity_ranking':144,'unfilled_selected_account_slots':0,
        'metadata_strata':candidate['metadata_strata'],'preprocessing_scan_counts':candidate['scan_counts'],
        'pre_purge_candidate_records':33190,'pre_purge_candidate_retained_words':3026159,
        'candidate_records_by_split':candidate['candidate_records_by_split'],
        'thread_purge_records':verified['thread_purge_records'],'cross_split_threads':verified['cross_split_threads'],
        'component_purge_records':verified['component_purge_records'],'purge_overlap_records':verified['component_and_thread_purge_overlap_records'],
        'union_purge_records':verified['union_purge_records'],'surviving_candidate_records':summary['surviving_candidate_records'],
        'replacements_after_purge':0},
    'dependence':{'selected_accounts_total':36,'accounts_per_split':12,'two_account_blocks_total':18,'blocks_per_split':6,
        'communities':3,'independent_source_collections':1,'scored_dataset_documents':72,'units_total':576,
        'confirmation_units_reserved':192,'units_in_scored_subtree':384,
        'planned_dev_eval_pair_occurrences_without_method_repetition':384,
        'planned_dev_eval_pair_occurrences_with_three_methods':1152,
        'record_occurrences_all_prepared_units':verified['surviving_record_occurrences_verified'],
        'distinct_source_records_all_prepared_units':verified['distinct_surviving_source_records_in_units']},
    'qualification_rule':{'minimum_retained_words_per_record':20,'minimum_eligible_records_per_unit':8,'minimum_eligible_words_per_unit':1000,
        'shared_block_budget':'max(1000,min(3000,min(Aearly,Alate,Bearly,Blate eligible-word capacities)))',
        'qualification_is_pre_score':True,'omissions_refill':False},
    'full_arm_totals':full_totals,'coverage':coverage,
    'failure_history':{'original_finalize_exit_code':1,'cause':'Original process read the draft just before registration; the saved in-memory plan lacked only the additive leakage.missing_content clarification.',
        'resolution':'Preserved the original run and failure; replayed candidates into prepared/paired-registered using the registered plan, verified byte-identical pool and identical selected observations, then finalized there.',
        'historical_run_relabelled':False,'registered_replay_pool_byte_identical':True,
        'provenance_path':'inventory/paired-registered-replay.json'},
    'existing_execution_receipts':receiptfacts,'input_sha256':{name:sha(R/name) for name in inputs},'limitations':limits}
review=R/'review';review.mkdir(exist_ok=True,mode=0o700)
jsonpath=review/'preparation-coverage.json'
with jsonpath.open('x') as f:json.dump(result,f,sort_keys=True,indent=2);f.write('\n')
lines=['# Paired-study preparation and coverage review','',
    'This review describes frozen prepared inputs and default word/record eligibility. It contains no comparison scores, distance-qualified result counts, or confirmation representations. All counts below precede scoring and are derived from existing preparation artifacts.',
    '',f'The registered plan is {link("hash-bound here","protocol/registration.json")}. The source is AHAS {plan["source_release"]}; configuration and implementation hashes are recorded in the companion '+link('aggregate JSON','review/preparation-coverage.json')+'.',
    '', '## Sampling and exclusions','',
    f'The three local archives contain {sum(s["rows"] for s in sources):,} records and {sum(s["comments"] for s in sources):,} comments. Global casefolded account identity yields {result["sampling"]["available_global_casefolded_accounts"]:,} additional account keys after the original 12 pilot accounts and fixed placeholders/AutoModerator exclusions. Home community is assigned from 2017–2018 present raw character volume. The salted split and volume shortlist select 20 accounts in each of nine community/split strata; retained-word capacity then selects four in each stratum. All 36 slots were filled before purges; 144 shortlisted accounts were not selected.',
    '', '| Community | Source records | Comments | Removed/deleted comments | Additional account/community keys | Duplicate IDs |',
    '|---|---:|---:|---:|---:|---:|']
for s in sources:lines.append(f'| {s["community"]} | {s["rows"]:,} | {s["comments"]:,} | {s["removed_or_deleted_comments"]:,} | {s["additional_account_community_keys"]:,} | {s["duplicate_ids"]} |')
lines += ['', 'Account/community counts overlap across corpora and are not additive counts of people. Source-account metadata, raw prose, individual IDs and maps are excluded from this review.',
    '', 'The fixed January–September cells in 2017 and 2018 required 108,881 shortlisted comments to be preprocessed; 40,339 fell below the 20-word record guard. Another 65,797 shortlisted source records were outside those cells, and 2,818 were submissions. The selected-account candidate pool contained 33,190 records and 3,026,159 retained words.',
    '', 'The completed graph audit examined 358,744 candidate pairs under the registered 2,000,000-pair ceiling. It marked six records for cross-split component removal. Symmetric thread purging removed 8,311 records in 2,433 threads; four records overlapped the component purge. The union removed 8,313 records, leaving 24,877 candidates. No account replacement or record refill followed purging.',
    '', '## Dependence and what “qualified” means','',
    'There are 12 selected accounts and six disjoint two-account blocks in each split: 36 accounts and 18 blocks overall. Each block yields four account-ID proxy pairs per condition and arm; the same records are reused across methods, conditions and omissions. The 72 scored dataset documents contain 384 pair occurrences before the three-method repetition, or 1,152 afterward. These are repeated observations of 24 scored accounts, not 1,152 independent people. The 12 confirmation accounts have 192 reserved units and zero entries in scored dataset documents.',
    '', 'The unchanged default guard requires at least eight eligible records and 1,000 retained words in each unit; every selected record already has at least 20 retained words. Shared B is bounded at 1,000–3,000 words per block/condition, with whole-record overshoot and the eight-record guard retained. Deletion arms use the original base unit and never refill. Word/record qualification is necessary but does not establish that a distance vector is nondegenerate or a method is available. Actual distance-qualified counts are deliberately null in this review.',
    '', '| Split | Condition | Qualified units / planned | Empty units | Qualified proxy pair slots / planned |',
    '|---|---|---:|---:|---:|']
for row in full_totals:lines.append(f'| {row["split"]} | {row["condition"]} | {row["guard_qualified_units"]}/{row["planned_units"]} | {row["empty_units"]} | {row["guard_qualified_proxy_pair_slots"]}/{row["planned_proxy_pair_slots"]} |')
lines += ['', 'This table is the full arm. Confirmation pair slots describe reserved sampling capacity only. Within-community full-arm qualification is 24/24 development and 20/24 evaluation pairs. The four inadequate evaluation pairs occur in Cornell after the registered purges. Cross-community qualification is 2/24 in each scored split; its sparse or empty units remain in the planned denominator.',
    '', '## All planned conditions and omission arms','',
    'Every row has four accounts, two blocks, eight unit slots and eight proxy-pair slots. Confirmation rows have no scored-dataset pairs. “Missing groups” counts units without observed thread/source/near-component metadata; author and related-sample labels remain known. These three missing-group counts coincide because their corresponding units are empty.',
    '', '| Split | Home | Condition | Arm | Qualified units / 8 | Qualified pairs / 8 | Empty units | Missing groups |',
    '|---|---|---|---|---:|---:|---:|---:|']
for row in coverage:
    assert len({row['missing_group_units'][dim] for dim in ['thread','source_document','near_duplicate_cluster']})==1
    lines.append(f'| {row["split"]} | {row["home_community"]} | {row["condition"]} | {row["arm"]} | {row["guard_qualified_units"]}/8 | {row["guard_qualified_proxy_pair_slots"]}/8 | {row["empty_units"]} | {row["missing_group_units"]["thread"]} |')
lines += ['', 'Empty units use valid empty JSONL files. Their group arrays are omitted rather than invented because the external schema requires nonempty arrays when present. The frozen evaluator can consequently label a group dimension `not_auditable` for that dataset despite the completed upstream candidate audit. This caveat is different from a detected cross-split overlap.',
    '', '## Word volume, overshoot and timing','',
    'The following full-arm summaries show minimum / median / maximum across eight units in each community/split/condition. Zero words and records describe known empty units; a largest-record share is unavailable when its denominator is zero. The companion JSON includes these summaries for every arm, observed/unavailable counts, target B, record counts, and UTC bounds.',
    '', '| Split | Home | Condition | Eligible words | Overshoot words | Largest-record share | Unavailable shares |',
    '|---|---|---|---:|---:|---:|---:|']
for row in coverage:
    if row['arm']=='full':lines.append(f'| {row["split"]} | {row["home_community"]} | {row["condition"]} | {triple(row["actual_eligible_words"],0)} | {triple(row["overshoot_words"],0)} | {triple(row["largest_record_share"],3)} | {row["largest_record_share"]["unavailable_count"]} |')
lines += ['', 'Pairing minimized differences in source-account cell-median timestamps among the three possible matchings, using metadata before selecting centered whole records. It cannot make the resulting samples perfectly matched in date or length. Below are the observed full-arm median gaps in days between each pair’s two sample medians, by proxy class. Each class has four planned pairs per row; empty-sided gaps remain unavailable. The difference is same-account minus different-account, not an effect estimate.',
    '', '| Split | Home | Condition | Same-account gap median days (observed / 4) | Different-account gap median days (observed / 4) | Median gap difference days |',
    '|---|---|---|---:|---:|---:|']
for row in coverage:
    if row['arm']=='full':
        a,b=(row['class_preparation_summary'][label]['pair_median_time_gap_days'] for label in ['same_author','different_author'])
        lines.append(f'| {row["split"]} | {row["home_community"]} | {row["condition"]} | {fmt(a["median"])} ({a["observed_count"]}/4) | {fmt(b["median"])} ({b["observed_count"]}/4) | {fmt(row["same_minus_different_median_time_gap_days"])} |')
lines += ['', 'The JSON additionally reports absolute left/right word and record imbalances for both classes in every arm. These preparation comparisons are descriptive, use repeated samples, and do not imply control of topic or verified continuity of a human author.',
    '', '## Failure history and actual verification','',
    f'The first candidate process began at {replay["old_candidate_started_utc"]}; registration occurred at {replay["registered_utc"]}. The in-memory plan copy lacked only the additive missing-content clarification. Finalization exited 1 before writing units because the saved plan differed from the registered plan. The original candidate files and failed receipt remain unchanged. A fresh replay in `prepared/paired-registered` began after registration, reproduced the pool byte-for-byte and all selected metadata/ranks exactly, and then finalized successfully. The original run is not relabeled as registered. '+link('Exact provenance and delta','inventory/paired-registered-replay.json')+'.',
    '', 'Seven synthetic adapter checks passed. Independent checks reconstructed all 180 shortlist capacities and all 33,190 candidate word counts, verified original-source fidelity, and verified all 576 actual prepared units and 72 dataset schemas. All 8,239 exported record occurrences, representing 2,485 distinct source records, preserved their source record values. Observed author, thread, source-document, audited-component and related-sample groups were disjoint across all three splits.',
    '', 'The following links lead to actual recorded argv, exit status and timing. Times are operational measurements during concurrent study work; they are not canonical results or performance guarantees.',
    '', '| Executed check | Exit | Wall seconds | Receipt with actual command |',
    '|---|---:|---:|---|']
for fact in receiptfacts:lines.append(f'| {fact["description"]} | {fact["exit_code"]} | {fact["wall_seconds"]:.3f} | {link("Receipt",fact["path"])} |')
lines += ['', '## Limits of this pilot','']
lines += ['- '+limit for limit in limits]
lines += ['', 'This review covers paired preparation only. Chronological construction, its joint group audit, final scoring authorization, and later numerical results have separate artifacts. Engineering checks and a useful local pilot do not establish real-world authorship validation.', '']
md='\n'.join(lines)
serialized=json.dumps(result,sort_keys=True)
for prohibited in ['"account_key"','"record_ids"','"source_record_ids"','"text_id"','"block_id"','"text"','"groups"']:
    assert prohibited not in serialized
for name in ['PREPARATION_REVIEW.md','preparation-coverage.json']:
    assert not (review/name).exists() if name.endswith('.md') else True
path=review/'PREPARATION_REVIEW.md'
with path.open('x') as f:f.write(md)
path.chmod(0o600);jsonpath.chmod(0o600)
print(json.dumps({'status':'passed','coverage_strata':len(coverage),'markdown_sha256':sha(path),'aggregate_sha256':sha(jsonpath),
    'source_or_prepared_files_modified':False,'comparison_results_read':False,'confirmation_distances_or_representations_read':False},sort_keys=True))
