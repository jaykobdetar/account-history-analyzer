# Publication copy and original evidence

This directory is a publication export of the completed local pilot3 study. It was prepared after execution and reporting, in response to the user's request to upload the results. Publication did not rerun scoring, revise cohort selection, change the protocol, or alter scientific results.

## Two distinct sets of hashes

`ARTIFACT_MANIFEST.json` is preserved byte for byte as the **original local artifact manifest**. Its hashes, all preregistration hashes, embedded input/output hashes, script hashes, and prior privacy/integrity snapshot hashes refer to the original local artifacts. These original hashes remain historical evidence; they are not silently reassigned to sanitized copies.

`PUBLICATION_MANIFEST.json` is the **published-copy manifest**. It maps every original file to its original and published SHA-256, sizes, identity status, transformations, and path-redaction counts. Use its `published_sha256` values to verify this directory. `PUBLICATION_CHECKS.json` records the publication checks and binds the publication manifest. The two publication manifests/check reports necessarily do not contain their own checksum; the checks report contains the publication manifest checksum.

The copied README has this directory's publication notice prepended. Its original body is preserved. All Python scripts and tests, CSV tables, and files under `results/` are byte-identical to the completed local artifacts. Prior drafts, failed attempts, and their available operational receipts are retained.

## Operational path policy

Only recorded operational JSON, Markdown, and log files receive path substitutions. Actual local home/workspace, private-study, prior-study, package cache, temporary runtime and test-root paths are replaced with declared logical-root placeholders. Paths inside Python code are preserved: the remaining absolute examples are generic AHAS `/tmp` runtime defaults, a privacy-scanner expression, and explicit synthetic `/home/secret-person` test fixtures. They are not source account identities or user-specific private locations.

A redacted `argv`, working-directory, file-path, or traceback is a sanitized representation of a recorded operation. It is not the byte-exact original command and cannot be reused without reconstructing appropriate local paths. System executable paths such as `/usr/bin/timeout` are retained. Existing `<PRIMARY_PREPARED>`, `<REPLAY_PREPARED>` and related placeholders in sanitized execution resource reports are unchanged. Their embedded exact-original command hashes still refer to the originals.

The placeholders describe roles, without publishing the private original-root map:

- `<WORKSPACE>`: original study repository checkout.
- `<PRIVATE_STUDY>`: protected local inputs, prepared data and original evaluation artifacts.
- `<STUDY_ARTIFACT_ROOT>` and `<PRIOR_STUDY_ARTIFACT_ROOT>`: local current/prior study work areas.
- `<LOCAL_HOME>`: remaining local home locations.
- `<PINNED_SOURCE>` and `<PINNED_INSTALL>`: reviewed source checkout and installed package used for execution.
- `<WHEEL_BUILD>`, `<PACKAGE_CACHE>`, `<TEST_TMP_ROOT>`, and `<TEMP_ROOT>`: operational build, cache, test and temporary locations.

## Source data and reproduction

This export contains study code, protocols, aggregate metadata, sanitized comparison cases, scientific results, reviews, and operational evidence. It does not contain source archives, source writing, candidate/cohort record files, account exclusion lists, source-account maps, snapshots, or unsanitized evaluator outputs. Public archive URLs and archive hashes identify approved acquisitions; they do not grant redistribution rights or imply that archive data is bundled here. The labels A/B denote accounts within anonymous matched blocks, and X/Y denote the registered public community pair; no mapping from source-account handles to those labels is published.

Arithmetic from the sanitized public cases can be reproduced from this directory. Source-level preparation and scoring require authorized source access, the protected original source/cohort data, and reconstruction of the recorded environment and paths. A public copy of a redacted freeze file cannot satisfy an original-input hash check until the original authorized private artifacts are supplied. Unknown historical content and other scientific limitations remain as reported in the protocol and final review.

The checks are bounded: they compare known source-account/record/thread identifiers and exact twenty-alphabetic-word phrases from the new candidate pool, plus selected credential syntax and JSON fields. They do not prove the absence of arbitrary personal data or shorter/paraphrased writing. No historical or protected reserve writing is read for publication review. Publication packaging never changes the local originals.
