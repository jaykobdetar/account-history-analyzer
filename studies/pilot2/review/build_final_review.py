#!/usr/bin/env python3
"""Fixed-text interpretation template over the complete saved pilot outcomes."""
import hashlib,importlib.util,json,shlex
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('saved_summary',ROOT/'scripts/summarize_results.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
read=module.read;table=module.table

def main():
    paired=read(ROOT/'review/paired-outcomes.json');streams=read(ROOT/'review/stream-outcomes.json')
    plan=read(ROOT/'prepared/streams/stream-plan.json');freeze=read(ROOT/'protocol/scoring-freeze.json')
    primary=[];all_methods=[]
    for row in paired:
        if row['arm']=='full' and row['condition']=='within_community':
            metric=row['partitions']['evaluation']['metrics']
            observed=[row['home_community'],row['method'],f"{metric['scored_pair_count']} / {metric['total_pair_count']}",
                      metric['ranking']['roc_auc']['value'],metric['ranking']['average_precision']['value']]
            all_methods.append(observed)
            if row['primary_method']:primary.append(observed)
    case_defs={case['case_id']:case for case in plan['cases']+plan['operational_availability_views']}
    full=[]
    for row in streams:
        case=case_defs[row['case_id']]
        if case.get('case_type')=='splice' and case.get('arm')=='full':
            g=row['grid_diagnostic'] or {}
            full.append([row['case_id'],row['preparation_status'],g.get('analysis_scope_status'),g.get('qualified_windows'),
                         len(g['candidate_intervals']) if g.get('candidate_intervals') is not None else None,
                         g.get('nearest_candidate_error_original_ordinals'),g.get('best_legal_grid_error'),g.get('matched_at_original_tolerance')])
    # The source plan is authoritative; tolerate only the registered case type.
    assert len(full)==6,('expected all six full construction slots',len(full))
    observation_counts=Counter(row['execution_status'] for row in streams)
    paired_methods=Counter(row['method'] for row in paired)
    module.write(ROOT/'review/summary.json',{
        'engineering_release':'AHAS 1.0.4 RW-001 complete; original analytical baseline preserved',
        'real_world_validation':'not_established','confirmation_scored':False,
        'paired_batches':len(paired),'paired_batches_by_method':dict(paired_methods),
        'chronological_source_accounts':plan['final_source_accounts'],
        'chronological_formed_pairs':sum(s['formed_pairs'] for s in plan['unfilled_slots']),
        'planned_stream_and_operational_slots':len(streams),'execution_counts':dict(observation_counts),
        'implementation_fingerprint':freeze['implementation_fingerprint'],
        'scoring_freeze_sha256':hashlib.sha256((ROOT/'protocol/scoring-freeze.json').read_bytes()).hexdigest(),
        'scope':'Account-ID comparison proxies, descriptive natural-history measurements and explicitly constructed source-account transitions.'})
    text=f'''# AHAS 1.0.4: repair evidence and second Reddit pilot

AHAS-RW-001 is repaired and the analytical baseline remains frozen. The second pilot executed the preregistered comparisons and available chronological cases, preserving every planned exclusion, insufficient-data result and unfilled slot. Engineering completion does **not** establish real-world authorship validity: `real_world_validation: not_established` remains unchanged.

## Read the results with their coverage

The paired cohort contains 36 additional source accounts: 12 development, 12 evaluation and 12 confirmation. The confirmation reserve was excluded physically from every scored input. The 72 planned method/community/condition/omission batches completed. Across the primary full within-community evaluation condition, 20 of 24 planned pairs qualified. Across communities, only 2 of 24 qualified; these data provide very limited evidence about cross-community performance. These counts describe reused account blocks, not independent people.

The predeclared primary method remains retained-prose cosine distance with character n=4. Its full within-community evaluation results are below. AUC ranks different-account distances above same-account distances in these retained observations; it is not an authorship probability. In particular, 1.00 here describes eight scored pairs from a small selected stratum, not perfect performance on a population.

{table(['Home community','Method','Scored / planned pairs','AUC','AP'],primary)}

All three registered methods are shown below without selecting a replacement primary method. No threshold was fitted. Average precision uses different-account pairs as the positive label and whole tied-score groups. The independent exact-rational/pairwise check reproduced metrics and null/coverage semantics for all 144 partitions. Complete score distributions, all 1,152 method/arm pair observations, and every abstention are in [the paired outcome report](PAIRED_OUTCOMES.html) and its linked JSON/CSV exports.

{table(['Home community','Method','Scored / planned pairs','AUC','AP'],all_methods)}

## Chronological results retain the original tolerance

Four source-account pairs were formed from eight additional accounts. All seven otherwise eligible Cornell candidates shared threads with confirmation records, leaving its four account/two source-pair slots unfilled. No replacement, partial-history deletion or guard relaxation repaired those slots. The resulting chronological study is exploratory, not an independent held-out replication.

Each splice combines A's complete available pre-cut portion with B's complete available post-cut portion at the fixed union-median timestamp. It preserves original source text, IDs and posting times. The construction is not an observed takeover. The full-arm results retain all six planned slots:

{table(['Construction slot','Preparation','Scope status','Qualified windows','Candidates','Nearest error','Best legal grid error','Matched within 10'],full)}

Three of the four executed full constructions matched within ten records; the remaining construction had adequate input but no candidate. The two unfilled Cornell constructions remain in the planned denominator. Three of four full continuity-proxy histories executed the primary change calculation and produced zero candidates; the fourth had only seven qualified windows and abstained. That unavailable result is not counted as another zero.

Candidate error is measured in original-record split coordinates for each supplied surviving snapshot. A legal-grid error above ten would still fail the registered ten-record precision requirement. Sufficient input with no candidate, insufficient input, an off-target candidate and an unattainable tolerance have separate fields. The [complete chronological report](STREAM_OUTCOMES.html) retains all 60 scientific/operational slots and all fixed omission arms. Its module-availability table comes from ordinary analyses of the same two natural accounts and their omissions, not additional subjects.

Account-continuity controls use empty construction-boundary arrays only to denote no source-account-ID reassignment. Their candidates are not established false positives for human authorship. Unknown-truth natural views have no accuracy labels. Across conditions, omitted records are never refilled, timestamps are never regenerated, and missing results remain unavailable rather than zero.

The old four-case grid diagnostic was independently reproduced with the current frozen source: nearest attainable errors remain 5, 11, 9 and 9 records. In particular, the old eleven-record case still fails its original ten-record tolerance. [The diagnostic and actual command receipts](../diagnostics/GRID_DIAGNOSTICS.md) remain separate from the new pilot's results.

## What the sampling and audits establish

The authorized local frame contains 1,997,146 utterances across Cornell, ApplyingToCollege and college. The new archives were acquired from the existing Cornell ConvoKit dataset host and hash-verified; no Reddit collector was built. These are three related education communities from the same historical ConvoKit/Pushshift collection, not independent source replications or representative Reddit sampling. Community membership is a coarse context control, not an exact topic label. The provider documents incomplete historical coverage; actual archive identity and counts are recorded separately. [ConvoKit corpus documentation](https://convokit.cornell.edu/documentation/subreddit.html).

Selection used fixed dates, global casefolded account identities, matched account blocks and whole-record word budgets. It removed the first pilot's 12 inspected accounts. Targets were shared within each block, with actual words, whole-record overshoot, largest-record share and realized time imbalance retained. English was an explicit unverified corpus assumption. The user's English-language confirmation applies to their earlier private export, not to every public account.

The content audit covered 33,190 pre-purge candidate records. It enumerated 358,744 bounded candidate pairs and verified 7,454 exact shingle-set comparisons, detected 57 exact groups and 2,474 near relations, and found no template/quote relations under its specific fifteen-word rules within this pool. That zero does not establish absence of quotations or templates elsewhere. Six cross-split component records and 8,311 cross-split-thread records overlapped in four records: the combined purge removed 8,313 records. Selected accounts stayed fixed. The joint 35,275-record chronology/paired audit exposed no new cross-split bridges.

All 576 prepared units, including 192 protected confirmation units, retain actual provenance. Empty omission units omit unavailable group arrays instead of inventing successful group checks. Their native missing-group statuses remain not auditable even though the earlier candidate pool was audited. Full selection, qualification, time/volume imbalance and grouping limitations are in [the preparation review](PREPARATION_REVIEW.md), [the registered protocol](../protocol/PROTOCOL.md) and [the independent audit review](paired-leakage-review.md).

## Engineering repair, separately verified

The 1.0.4 report renderer now shows every stored penalty setting and stream, including an alternative-only interval when the primary set is empty. It reads stored counts and matching results, preserves semantic list order, and differentiates executed zero from skipped/unavailable. No feature, distance, threshold, selected interval, evidence rule or pinned PR #383 optimizer changed. N-gram labels remain reversible and source strings inert; excerpt omission remains effective.

Fresh release checks passed: 658 repository tests with one separate-browser skip on both the reference host and installed-wheel reference container; eight original audit/adversarial regressions; 24 independent reviewer tests; and the separate browser test. Four synthetic reports were inspected in the browser with no remote requests or active content. Six fresh process analyses reproduced all fourteen canonical artifacts per fixture. The actual private regression passed unchanged, with corrected presentations in new private destinations; old private inputs, scores and failed receipts remain historical. Fresh private numerical output changed only the three documented release/template identity fields.

The separate 1.0.4 source-and-reports archive supplies the working package, production wheel, exact dependency locks, source/test diff, public synthetic reports and raw repair logs. Its SHA-256 is `c1f4985fb484698e055a8ee045b42b5ecfb7377b7958bfa2778a7b6e639564cb`. The wheel SHA-256 is `dd92aa29bfdf8631a8ac2a37948edcd573b31872cf97b49d43fc2930a3b43b51`. No private inputs or maps are in that release.

## Reproducibility and operating cost

The measurement identity is `{freeze['implementation_fingerprint']}`. All 1,448 protocol, driver, test and prepared files were frozen before scores. Preparation passed 68 combined study tests plus five checks against the actual chronological archives. Independent checks verified every reported content match and component, source fidelity, grouping and guard accounting. The exact commands, starts/finishes, raw logs and failures are linked in [COMMANDS.md](COMMANDS.md).

The paired and constructed-splice replays under different hash seeds and timezones reproduced all three canonical evaluator files byte-for-byte. A separate full natural-history verification reproduced all fourteen canonical artifacts, including Markdown, HTML and SVG, in 59.55 seconds. The reference environment is CPython 3.12.3/Linux x86_64 with NumPy 2.4.2, SciPy 1.17.1, ruptures 1.1.10, markdown-it-py 3.0.0 and jsonschema 4.26.0. Runtime analyses and their descendants used socket denial. Acquisition was a separate authorized operation. Receipts are not canonical results; cross-platform byte identity is not claimed. The installed-wheel container test belongs to the repair release, not an independent recomputation of every new corpus case.

Before these full-history jobs, a previously exposed 400-comment natural-text sample was profiled. Its separate unprofiled full verification took 74.46 seconds, used 454.24 MiB peak RSS and reproduced fourteen canonical artifacts. The result JSON was 94.09 MiB. Serialization had substantial cumulative profiled cost; overlapping cumulative times were not summed. No optimization or truncation followed. The 72 paired batches took 48.40 seconds at two workers; the chronological batch took 700.75 seconds at two workers. Its largest reported per-process peak was 1,707,808 KiB (about 1.63 GiB), showing that comment count alone does not bound cost. Complete per-case resource evidence is separate from ranking results. [Detailed cost report](RESOURCE_COST.md), [operating check](../resources/RESOURCE_REVIEW.md).

Two pre-score preparation failures remain visible: a draft/registered-plan mismatch correctly blocked finalization and was resolved by a byte-identical registered replay; a capped launch wrapper failed to import a neighboring script and was corrected without changing data or rules. A protection-pool completeness guard was strengthened before the scoring freeze. These are documented engineering events, not rewritten historical successes.

## Remaining limitations

The labels do not establish who wrote a record, whether an account is shared or automated, or whether two accounts belong to one person. The held confirmation reserve remains unscored; no untouched-confirmation accuracy claim is available. Four constructed source pairs and a small selected paired cohort cannot establish broad change-detection or authorship validity. Sparse cross-community coverage, natural time/topic/style variation and thread-related exclusions materially limit interpretation.

Complete histories mean all comments available in these three archives, not all Reddit activity. Deleted, uncaptured or other-community material and undocumented edits remain unknown. Mechanical reuse checks do not cover semantic paraphrase or all quotation, and a content match does not establish intent. Timestamp gaps are not sleep and reply delays are not typing time. Default guards and hard resource limits remain unchanged.

The sanitized review handoff omits raw corpus prose, source-account maps and the user's private export. Numerical replay therefore requires the separately retained local corpora and protected preparation inputs. The working software source release can independently analyze conforming local JSONL/manifest inputs. Corpus redistribution rights were not inferred from the software's license. Broader platforms, RW-004 optimization and additional usability work remain separate work; no classifier, collector or optimizer investigation was added.
'''
    module.render(ROOT/'review/REVIEW.md',text)
    commands=['# Actual command records','', 'Each block below is an actual recorded invocation. Historical failed attempts stay failed. Complete stdout/stderr are beside the linked receipt; performance receipts are separate from canonical artifacts.','']
    for directory in ('logs','inventory','review'):
        for path in sorted((ROOT/directory).glob('*.receipt.json')):
            receipt=read(path)
            if 'command' not in receipt:continue
            relative=Path('..')/path.relative_to(ROOT)
            commands.extend([f"## {path.stem}",'',f"Exit code: {receipt['exit_code']}. Wall seconds: {receipt.get('wall_seconds','unavailable')}. [Receipt]({relative.as_posix()}).",'', '```bash',shlex.join(receipt['command']),'```',''])
    (ROOT/'review/COMMANDS.md').write_text('\n'.join(commands))
    print(json.dumps({'review':'review/REVIEW.html','summary':'review/summary.json','commands':'review/COMMANDS.md'}))

if __name__=='__main__':main()
