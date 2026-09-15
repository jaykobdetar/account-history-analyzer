# Engineering evidence

This directory preserves actual test logs, screenshots, resource measurements, validation helpers and failed attempts from software development. It is an evidence archive; routine checks live in [tests/](../tests/) and are described in the [development guide](../docs/DEVELOPMENT.md).

| Location | Record |
| --- | --- |
| Root files | Original 1.0.0 implementation checks |
| [pr383/](pr383/) | 1.0.1 pinned optimizer backport and validation |
| [audit-repair/](audit-repair/) | 1.0.2 audit repairs |
| [report005/](report005/) | 1.0.3 character n-gram display repair |
| [rw001/](rw001/) | 1.0.4 stored sensitivity-candidate presentation repair |

Read the corresponding [engineering reports](../docs/DOCUMENTATION_INDEX.md#release-and-engineering-history) before using individual logs. A failure or retry is part of the record, not an obsolete file to overwrite. Commands retain historical paths and may depend on the original environment or archived artifacts. Duplicate distributions were moved out of the Git working tree; the [recovery map](../provenance/repository-cleanup/README.md) identifies their exact release copies.
