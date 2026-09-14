#!/usr/bin/env python3
"""Render aggregate, prose-free Gate A observations into auditable tables."""
import argparse
import csv
import json
from pathlib import Path

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--census',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    cap=json.loads((args.census/'capacity.json').read_text())
    inv=json.loads((args.census/'source-inventory.json').read_text())
    res=json.loads((args.census/'resources.json').read_text())
    args.out.mkdir(parents=True,exist_ok=False)
    def table(name,rows):
        if not rows:return
        with (args.out/name).open('x',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    table('period-capacity.csv',cap['period_capacity_table'])
    table('source-capacity.csv',[{'community':s['community'],'archive_bytes':s['bytes'],
          'archive_sha256':s['sha256'],'records':s['counts']['source_records'],
          'comments':s['counts']['comments'],'submissions':s['counts']['submissions'],
          'first_nonexcluded_utc':s['nonexcluded_first_utc'],'last_nonexcluded_utc':s['nonexcluded_last_utc'],
          'source_missing_thread':s['counts']['missing_thread'],
          'explicit_language_missing':s['counts']['explicit_language_missing']}
          for s in inv['sources']])
    table('exclusions.csv',[{'reason':k,'unique_mandatory_accounts':v} for k,v in inv['exclusion_manifest_reason_counts'].items()])
    rows=[]
    selected=cap.get('selected_pair_strata',list(cap['disjoint_capacity']['quota_counts']))
    for pair in selected:
        scheme=cap['proposed_period_schemes'][pair]
        item=next(v for v in cap['period_capacity_table'] if v['community_pair']==pair and v['period_scheme']==scheme['id'])
        allocated=cap['disjoint_capacity']['quota_counts'][pair]
        rows.append({'community_pair':pair,'proposed_period_scheme':scheme['id'],
                     'four_cell_accounts':item['four_cell_accounts'],'disjoint_account_slots':allocated,
                     'disjoint_blocks':allocated//2,'planned_blocks':10,
                     'unfilled_account_slots':20-allocated,
                     'all_history_necessary_accounts':cap['all_history_necessary_capacity'][pair]['accounts']})
    table('stratum-capacity.csv',rows)
    lines=['# Score-free feasibility result: '+args.census.name,'',
           '**Gate A status: '+cap['gate_a_status']+'. No new style scores were computed.**','',
           f"The proposed calendar grid supports {cap['disjoint_capacity']['total_blocks']} disjoint two-account blocks "
           f"({cap['disjoint_capacity']['total_accounts']} account slots), against a target of 30 blocks/60 accounts in three strata. "
           'These counts precede shared-thread/content filtering and ordinary method qualification; they are ceilings on usable final study capacity. '
           'No final cohort was selected and no reduced design is approved.','',
           '| Proposed stratum | Calendar scheme | Four-cell accounts | Disjoint blocks / target |',
           '|---|---|---:|---:|']
    lines += [f"| {r['community_pair']} | {r['proposed_period_scheme']} | {r['four_cell_accounts']} | {r['disjoint_blocks']} / 10 |" for r in rows]
    lines += ['', '## Source and exclusion evidence','',
              f"The fresh source scan read {inv['source_records']:,} unique original records in {len(inv['sources'])} archives. "
              f"It found {inv['nonexcluded_comment_accounts']:,} nonexcluded account keys with comments; "
              f"{inv['preprocessing_candidate_accounts']:,} had at least 16 present timestamped comments in each of two communities. "
              'This necessary prefilter cannot exclude an account capable of supplying two eight-record cells in both communities. '
              'Provider speaker totals are not used as complete-history counts.','',
              f"Exactly {inv['exclusion_unique_account_count']} known source-account identities are excluded: 12 pilot 1 accounts, "
              '24 scored pilot 2 paired accounts, 12 protected reserve accounts, eight chronological accounts (including failed attempts), '
              'and the private export account. The last identity comes from the historical export filename; private prose was not reopened. '
              f"A further {inv['prior_capacity_only_exposed_accounts']} previously capacity-inspected but unscored identities are flagged, "
              'not silently treated as scored or excluded to manufacture scarcity. Reserve writing/features were not inspected for this design.','',
              f"The frozen preprocessor ran on {cap['preprocessed_records']:,} comments; {cap['eligible_records']:,} met its record guard "
              f"and contained {cap['eligible_words']:,} retained word tokens. English is an unverified corpus-level assumption. "
              'Raw text length was never substituted for eligible words. All relevant candidate records are accounted for in private metadata, '
              'with source-line hashes, record IDs, times, retained word counts and exclusion reasons. No original prose is exported by the census.','',
              '## Dates and what the bounds mean','']
    for pair in selected:
        s=cap['proposed_period_schemes'][pair]
        lines.append(f"- {pair}: early [{s['early'][0]}, {s['early'][1]}); late [{s['late'][0]}, {s['late'][1]}), UTC.")
    lines += ['', 'All four tested schemes are preserved in `period-capacity.csv`. Every cell uses the same dates within its stratum. '
              'The 2,000-word/eight-record requirement applies independently to all four cells of each account. '
              'The all-history bound instead requires at least 4,000 eligible words and 16 eligible records per community over all observed dates. '
              'It is only a necessary condition for two disjoint periods. Even that bound cannot establish feasible shared calendar cells. '
              'Neither a provider account count nor all-history volume is a substitute for matched-cell capacity.','',
              '## Interpretation and next gate','',
              'This is evidence about input feasibility, not evidence for or against cross-context discrimination. '
              'Cross-community ordering, its within-community difference, method sensitivity, omission coverage, ROC-AUC/AP and uncertainty '
              'are not estimated here. Shared-thread/content audits, final 60-account selection, scored inputs, Gate B registration, '
              'scoring and canonical scoring replay have not run. Missing strata remain missing.','',
              'Production feature extraction, masking, vocabulary, distances, guards, optimizer and resource limits remain frozen. '
              'The census uses installed AHAS 1.0.4 with the required fingerprint/configuration; the stale editable 1.0.0 metadata '
              'was resolved through an isolated noneditable wheel installation. See the environment evidence and command receipts.','',
              'These archives are historical convenience samples with incomplete histories, missing/deleted writing, unknown edits, '
              'unverified language and coarse community contexts. Their known source-account labels do not establish human authorship, '
              'bot/human identity, account takeover or cross-platform accuracy. Corpus redistribution rights were not inferred; '
              'archives, source-account mappings and per-record provenance remain private.','',
              '## Observed resources','',
              f"Two source passes completed in {res['wall_seconds']:.2f} seconds with {res['peak_rss_mib']:.2f} MiB peak RSS. "
              f"Private metadata output occupied {res['private_output_bytes']:,} bytes. "
              'The run completed within its predeclared bounds. Operational receipts retain actual commands, exit codes, wall time '
              'and artifact hashes. These successful receipts are fresh census runs, not scoring reruns.','']
    (args.out/'FEASIBILITY.md').write_text('\n'.join(lines))
    print(json.dumps({'status':'rendered','census':str(args.census),'out':str(args.out),'scores_computed':False}))

if __name__=='__main__':main()
