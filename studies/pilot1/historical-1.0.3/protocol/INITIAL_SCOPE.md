# Local real-world review, 2026-09-14

This is a new local evaluation of frozen AHAS 1.0.3. It is not a re-execution of historical release receipts. Source/package/config/thresholds/method definitions remain unchanged. This directory is outside the source repository and release packaging tree. It contains private user data and must not be published as a release.

Checklist:
- [ ] Inspect and hash the two sources; document conversion and missingness.
- [ ] Freeze a concrete public cohort and protocol before calculating comparison or change scores.
- [ ] Run personal history with user-declared primarily English and an unknown-language control.
- [ ] Evaluate public same-account and different-account paired texts using development/evaluation separation, temporal variation and fixed missingness transformations.
- [ ] Exercise the account-stream interface with explicitly constructed splice labels and account-consistency proxy controls, separately from unlabelled real-history interpretation.
- [ ] Audit source-to-feature/evidence links, numerical summaries, abstention, report safety/readability and sensitivity.
- [ ] Repeat in separate offline processes, test relevant existing contracts, measure resources, check frozen fingerprint.
- [ ] Produce local HTML/Markdown/JSON review, receipts, reproducible scripts and specific limitations.

Source acquisition may use the network only to obtain the public corpus. Analyses run with the supplied seccomp offline runner. Read only comments/posts and their header tables in the personal archive; ignore IP fields and unrelated archive members. Preserve source strings/timestamps without making up edits, language detections, thread relations or authorship facts. The user declared the export primarily English on this turn; this is a source-level assumption, not a per-record language annotation.

Primary public corpus is Cornell from the user-linked ConvoKit collection, chosen before outcome inspection because it is the documented manageable example. It is a convenience corpus, not representative of Reddit or the user. Corpus language is an explicit operational English assumption, separately audited, not a detector output. No user-vs-public authorship test: different eras, subjects and sampling frames would confound it.

No threshold will be trained or optimized. Existing paired-text evaluator receives null frozen_threshold; report rankings, overlap and guard coverage, not classification accuracy or probabilities. Distance families are retained_prose cosine n=4 (primary), function_mask_v1 cosine n=4 and function-word Jensen-Shannon (secondary); no method chosen by held-out score. All use the unmodified default config. No Delta reference is supplied.

Empty truth arrays in stream controls will mean only stable corpus account-ID provenance. They do not establish unchanged person, unchanged style or absence of genuine temporal changes. Constructed splice boundaries will be recorded as construction facts only; source text and real UTC times remain intact. The private history has unknown transition truth and will not receive invented stream labels.

Later cohort specification is allowed to use corpus counts, metadata, text-size qualification and leakage checks before scores; all such selection is documented, and exclusions/abstentions remain visible. Report lack of broader validation regardless of engineering success.
