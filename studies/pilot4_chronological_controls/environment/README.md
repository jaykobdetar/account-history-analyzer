# Pilot 4: fresh frozen-baseline verification

The fresh offline verification on 2026-09-15 at 01:12:52 UTC passed all 17 identity checks. This is a new pilot 4 execution receipt, not a reused pilot 3 test result. No corpus was opened, no preprocessing or analysis ran, no dependency was installed, and no production tests were rerun.

The imported module and installed distribution both report AHAS 1.0.4. The import resolves to the existing noneditable target `<INSTALLED_BASELINE>/account_history_analyzer/__init__.py`. All 54 package and resource files match both the immutable git tree at reviewed commit `ea41d82ecc3f6585a7dc2bca92ede34740f0b62d` and the prior installed-byte receipt. The archived wheel also remains byte-identical.

| Identity | Verified value |
|---|---|
| Implementation fingerprint | `bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179` |
| Analytical configuration SHA-256 | `8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925` |
| Wheel SHA-256 | `a0fe943f4d5e3c367ada9fb468499b2b64c2d6f924c828479cdf21fe766d0f6a` |
| Python | 3.12.3 |
| Runtime dependency versions | NumPy 2.4.2; SciPy 1.17.1; ruptures 1.1.10; markdown-it-py 3.0.0; jsonschema 4.26.0 |

Expanded analytical configuration, bundled resource hashes, reference environment, Python identity, and runtime/test dependency versions also agree with the prior probe. Dependency identity here means the recorded versions and reference environment; this check does not claim a prior complete byte manifest for all third-party dependency files.

The verification uses the unchanged prior provenance probe and adds a direct installed-file/git-blob comparison against the immutable reviewed tree. `baseline-start-binding.json` binds the new checker and prior evidence before the fresh probes. `baseline-verification.json` records every check; `installed-package-fresh.json` and `reviewed-source-fresh.json` retain the detailed fresh observations. `baseline-fresh-01.receipt.json` records the actual offline command, timing, status, and logs. The command completed successfully in 0.322 seconds with 26.30 MiB peak child memory.

The prior editable installation's stale 1.0.0 distribution metadata is not used for pilot 4 execution. Continue to use the explicitly selected noneditable installed target. No source/configuration changes are needed.

[Synthetic boundary review](SYNTHETIC_BOUNDARY_REVIEW.md) identifies focused existing tests and proposed independent grid fixtures. It is a code-review recommendation, not a claim that those tests have been freshly executed for pilot 4.
