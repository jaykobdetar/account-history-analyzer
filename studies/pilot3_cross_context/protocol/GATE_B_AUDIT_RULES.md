# Gate B candidate-pool protection audit

**Registered rules, frozen before the first real candidate audit. No real audit has run at this registration.** This is an evaluation-only
adapter to the existing leakage audit. It does not calculate style distances,
select final participants, or authorize a smaller design. The target remains
60 accounts in three strata. Register these rules and exact implementation/input
hashes before any real candidate audit.

## Inputs and immutable bindings

`scripts/audit_candidates.py` accepts a private candidate JSONL file, the frozen
private historical-source inventory, the pinned leakage-engine path, these rules,
an audit freeze JSON, a new private output directory, and a new public result file.
Its required flags are `--candidate-pool`, `--historical-inventory`, `--engine-path`,
`--rules`, `--freeze`, `--out-private`, and `--out-public`.

The freeze JSON must have `state: "frozen_before_audit"` and exact SHA256 fields
`candidate_pool_sha256`, `historical_inventory_sha256`, `engine_sha256`,
`wrapper_sha256`, and `rules_sha256`. The wrapper verifies each before reading
source records. It also checks the installed AHAS implementation fingerprint and
default analytical configuration against the baseline in the scoring protocol.
The leakage-engine SHA256 is
`f080682bc5beac251f9fb07404d0c9a9093aab04deff8d53997708d05dd01e92`.
No engine, preprocessor, vocabulary, distance, threshold, or cap is changed.

Each candidate JSONL row has this schema:

```json
{
  "record": {"id": "original ID", "kind": "comment", "status": "present", "text": "original text", "language": null, "subreddit": "community", "created_utc": "original UTC timestamp", "thread_id": "original thread ID"},
  "account_key": "casefolded source account",
  "stratum_id": "registered stratum ID",
  "community": "community",
  "period": "early",
  "retained_words": 20
}
```

`record` is the unchanged full source record; the example lists only fields
needed by this adapter. `period` is `early` or `late`; `community` must exactly
match the original record. Upstream preparation must verify source membership,
original bytes, actual timestamp/window membership, and source-account binding.
The audit independently verifies the declared retained word count using the
frozen preprocessor. Cell identity is `(account_key, community, period)`.
One source account can belong to only one registered stratum. Each original
record ID appears once in the pool. Every new record requires a thread ID and
timestamp, English/default-English declaration, at least 20 retained words, and
an original body no longer than 200,000 codepoints. Submissions are ineligible as
new candidates. No record is split, shortened, or rewritten here.

The candidate pool is frozen before this audit, before final membership. The
planned preparation bound is at most 40 candidate accounts per stratum with
four cells and a 3,000-word whole-record stopping target per cell. This gives
1.44 million target words before whole-record overshoot. Independent hard audit
input ceilings are 100,000 candidate records, 2,000,000 retained candidate words,
and 256 MiB of candidate JSONL. Exceeding a ceiling fails; it does not trim records
or silently enlarge a bound. Final units must still independently satisfy
2,000 words and eight whole eligible records after purges. The preparation
freeze must specify stopping and tie rules; the wrapper does not invent them.

## Historical protection and title handling

The current metadata-only inventory binds 22 files with 38,884 original records:
3,362 pilot 1 selected public comments; 33,190 pilot 2 paired candidate-pool
comments, including the protected confirmation reserve; 2,085 prepared pilot 2
chronological comments; and 247 authorized private-export records. The latter
include 53 submissions. The private inventory records source paths, SHA256,
bytes, row counts, account/split/record identifiers and source kinds. The public
inventory contains aggregate coverage only. Capacity-only accounts' unselected
prose is outside these protection inputs, as disclosed in the inventory.

The loader verifies every listed file's bytes/hash, record count and original
IDs, and wrapped source account/split metadata. The supplied inventory must
declare complete coverage of the requested known protection sources. This is
not a claim that all historical Internet content was supplied. No recursive
discovery or unrelated personal-data search occurs during the audit.

Historical scored or exposed material maps to the audit's `development` split;
protected reserve material remains `confirmation`; new candidates map to
`evaluation`. Account keys are casefolded source identities. Identical repeated
historical records are collapsed by original ID, retaining source references.
Different text or metadata for the same historical ID is fatal. Historical/new
original-ID or source-account overlap is fatal, rather than silently relabeled.

Every original historical body remains a protection node with its status and
language preserved. A nonempty historical submission title creates a separate
title-only protection node. Its ID is the reserved prefix
`__ahas_pilot3_historical_title_v1__:` plus SHA256 of the original ID; source IDs
using this prefix are rejected. Title text is preserved exactly and tagged
privately with its original submission ID, source kind, and `title` component.
Titles receive no minimum-word exclusion: even short nonempty normalized titles
remain eligible for the engine's exact relation. A missing/removed body does not
erase a supplied title. Title nodes share the source submission's thread and
account/split metadata. They are never eligible new samples.

Historical text is processed automatically for protection only. The model must
not inspect protected prose, feature vectors, or relation exemplars to choose
participants or change these rules. Historical-to-historical relations are
reported as protection coverage, not a basis for preferring new participants.

## Frozen relation definitions and two cap checks

Call the unchanged `audit_records(rows, max_candidate_pairs=2000000)` once, after
the separate broad candidate-pair count passes. Use every supplied protection
body/title node and every new candidate node in both counts.

- Exact: equal nonempty normalized lexical-token segment sequences, retaining
  numbers and boundaries.
- Near: five-token shingles; each record has at least 20 retained words; at least
  five unique shared shingles; Jaccard at least 0.80 or containment in either
  direction at least 0.90.
- Template: a 15-word phrase shared by at least three distinct source accounts.
- Quotation: 15-word matches from recognized CommonMark blockquote paragraphs
  to retained text, using the frozen parser and line mapping.

No shingles or phrases cross segment boundaries. The engine unions all four
content relation types into connected components, including honest singletons.
Its existing split-only `excluded_ids` are insufficient for the new/new cell
rule, so the adapter uses the complete components and its separate metadata.

The independent count builds an inverted five-shingle index and enumerates
unique record pairs in each bucket. It shares only the frozen preprocessor with
the engine; it does not reuse the engine's incremental overlap-counting helper
or near-match test. Both records must satisfy the frozen 20-word guard. The
broad counter includes records with fewer than five distinct shingles: a pair
sharing only one shingle counts toward its ceiling even if it is never a near
relation. Independently tally the subset of those pairs where both records also
have at least five distinct shingles. Only this engine-eligible subset count
must equal the frozen engine's candidate-pair count. Report the two counts
separately; a legitimate broad/engine-eligible difference is not a failure. The
broad count itself has the 2,000,000 ceiling, separately from the engine's cap.
A cap excess is recorded as a broad lower bound of 2,000,001; no cap override is
exposed by this wrapper's CLI.

## Purges, grouping and unavailable scope

For each completed content component, purge all its new candidate records if
the component contains any historical protection node or more than one distinct
candidate cell. Independently, group all records by original nonempty source
thread ID and apply the same rule. Purges are symmetric across affected new
cells. Reasons separately identify content/thread and historical-boundary/
cross-candidate-cell relations. Thread groups and content components are not
joined into a new transitive relation beyond the frozen content definition.

Content shared only within one candidate cell is logged by the engine and is
not a cross-cell purge. The audit contains each original record once. Deliberate
reuse of an early anchor in the later comparison schedule is distinct from
duplicating its audit input; comparison-level record disjointness and clustered
analysis remain required by the scoring protocol. The wrapper never schedules
comparisons or declares repeated anchors independent.

Missing new thread metadata is fatal. Missing historical thread metadata is
counted separately for original records and audit nodes; available content
purges may be retained privately, but `gate_b_ready` is false. Unknown removed
or unavailable historical content is disclosed with the frozen engine's flags,
counts and limitations. A completed available-content/grouping audit does not
establish independence from unobserved material. `independence_scope_complete`
is false whenever the engine reports unknown content or old thread metadata is
missing. Even without such flags, the explicitly limited relation definitions
cannot rule out unmarked quotations, short phrases, paraphrases or unsupplied
content. Final reporting must retain these scope limits.

An engine failure, cap excess, count disagreement, invalid metadata, resource
exhaustion or hash mismatch produces a non-success result. No incomplete content
audit supplies actionable survivor/purge IDs. Audit success is only permission
to assess surviving capacity under the already frozen candidate-pool rules.
No adaptive refills, source expansion, new candidate ordering, or replacement
of the pool may follow its audit results. If 60 accounts across all three quotas
cannot be selected, report the deficit; no reduced design is implicitly approved.

## Resources, outputs and checks

Run in the existing socket-denial offline runner, with
`AHAS_NETWORK_ISOLATION=linux_seccomp_socket_denial`. The environment marker alone
is not an operating-system isolation mechanism; the execution receipt must bind
the actual offline runner. The process sets a 4 GiB address-space hard limit and
a 30-minute wall alarm, including input loading, both counts, audit and writes.
Capture the command's exit code, stderr, timing and peak memory with the existing
logged runner. Do not retry with raised caps or replace a failed receipt.

The private output directory is new and mode 0700; `audit.json` is mode 0600.
It contains record IDs, source metadata, relation hashes, component membership,
thread groups, purge reasons and survivors. It contains no copied source prose.
Public output and stdout contain aggregate counts, safe failure codes, known
scope limitations, hashes and resource telemetry only. No public account keys,
record/thread IDs, source paths, relation exemplar text or private row mappings.
Existing output paths are never overwritten. Exit zero requires a completed
available-content/grouping audit; all non-ready outcomes return exit four.

Synthetic tests cover symmetric cross-cell content/thread purges, same-cell
handling, protected reserve and historical thread boundaries, unchanged title
protection, missing grouping, duplicate conflicts, both cap-failure paths,
independent broad-pair accounting, frozen word-count binding, exact/template/
quotation relations, historical unknown-content disclosure, public redaction,
and source-inventory hash binding. They do not establish real-data sufficiency
or replace independent verification of an eventual real audit.
