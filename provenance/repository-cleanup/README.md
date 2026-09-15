# Repository cleanup — 2026-09-15

This cleanup starts from commit `298137399c962fb1ce03de024013c61bc3881e6f`. It separates current instructions from the original handoff and removes packaged artifacts already available in the frozen release. It changes no analyzer source, defaults, numerical resources, lockfiles, synthetic data or individual study record.

The [file map](file-map.json) records every relocation and removal with its original path, size and SHA-256:

- Five root handoff documents moved byte-for-byte into [docs/archive/original-handoff/](../../docs/archive/original-handoff/README.md).
- Eleven wheel/source archives and eight one-byte build-directory ignore files were removed: **4,802,292 bytes** in total. All 19 files were compared byte-for-byte with members of a freshly downloaded published source-and-reports archive. The two current distributions also matched their standalone release downloads.
- Current navigation now covers all five studies. Fixture instructions describe the implemented CLI; container examples use the current version tag. A packaging include for the relocated root checksum file was removed; the archived files remain included through `docs/`.

QA scripts and receipts, evaluation results, benchmarks, sample reports and all five study directories retain their original evidence paths. Historical manifests are not rewritten. This is a working-tree cleanup; earlier Git history and released assets remain available, so it does not reduce an existing clone's Git object storage.

## Recover removed build files

Download the [frozen source-and-reports archive](https://github.com/jaykobdetar/account-history-analyzer/releases/download/v1.0.4/account-history-analyzer-1.0.4-source-and-reports.tar.gz). Its SHA-256 is:

```text
c1f4985fb484698e055a8ee045b42b5ecfb7377b7958bfa2778a7b6e639564cb
```

Extract into a separate directory to inspect the original layout. Each removed file's exact member name is in `file-map.json`; copy the required members back to their recorded paths when replaying historical packaging checks. For example, `qa/rw001/verify_release.py` and `wheel_container_probe.py` expect the original files under `dist/`. They remain historical procedures and may require other original local artifacts specified in their receipts.

The [production wheel](https://github.com/jaykobdetar/account-history-analyzer/releases/download/v1.0.4/account_history_analyzer-1.0.4-py3-none-any.whl), [source distribution](https://github.com/jaykobdetar/account-history-analyzer/releases/download/v1.0.4/account_history_analyzer-1.0.4.tar.gz), and [release checksums](https://github.com/jaykobdetar/account-history-analyzer/releases/download/v1.0.4/SHA256SUMS.release.txt) are also available separately. Restored files remain ignored as generated artifacts. The published frozen release assets were not replaced. A temporary source distribution of the reorganized checkout was built only to inspect its contents; it is not a replacement release.

## Cleanup verification

- Compared all 54 analyzer files and all 1,214 individual study files with the base commit: unchanged. Retained QA, release/import provenance, saved outputs, evaluations and tests also retained their bytes.
- Independently checked all five relocations and all 19 removed files against the recorded hashes and downloaded archive members.
- Ran 62 existing fixture-integrity, schema, configuration and initial pipeline checks under the offline wrapper: all passed. Schema synchronization check passed.
- Built a temporary source distribution and compared its 54 package files and five archived handoff documents with the checkout: all 59 matched.
- Ran a fresh arithmetic analysis and full recomputation under the offline wrapper: all 14 canonical artifacts reproduced.
- Checked 183 local documentation links, nine linked anchors and nine shell examples in the 14 updated/new guides: passed. Archived historical documents were excluded from this current-navigation check.

These checks verify this organization change. The full software suite, browser/container audits and real-text studies were not rerun for this cleanup.
