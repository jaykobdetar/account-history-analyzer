# Original specification handoff

These five files predate the implemented analyzer. They are preserved byte-for-byte as historical inputs, including instructions to build the then-unimplemented application. Use the [current usage guide](../../USAGE.md) and [documentation index](../../DOCUMENTATION_INDEX.md) for today's software.

| File | Historical purpose |
| --- | --- |
| [BUILD_SPEC.md](BUILD_SPEC.md) | Original implementation and numerical contract |
| [ACCEPTANCE_TESTS.md](ACCEPTANCE_TESTS.md) | Original acceptance requirements; current executable coverage is in the [test map](../../TEST_MAP.md) |
| [AGENT_PROMPT.md](AGENT_PROMPT.md) | Original implementation assignment |
| [PACKAGE_VALIDATION.md](PACKAGE_VALIDATION.md) | Validation of the specification/fixture handoff before the analyzer existed |
| [SHA256SUMS.txt](SHA256SUMS.txt) | Checksums of the original handoff, not the implemented software or current repository |

The documents originally lived at repository root. Their internal paths and checksum entries still describe that original layout; relocating the manifest does not make it a checksum of this directory. The [cleanup map](../../../provenance/repository-cleanup/file-map.json) records old paths, new paths and unchanged SHA-256 values. The frozen release archive retains the original paths.
