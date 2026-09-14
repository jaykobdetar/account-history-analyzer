# Dependency versions and license metadata

Read from the actually installed locked distributions. Licenses here summarize package metadata; redistribution must retain the complete notices shipped in wheels. NumPy/SciPy wheels include additional bundled numerical-library licenses. The project owner has not selected a license for AHAS.

| Distribution | Version | License metadata |
| --- | --- | --- |
| attrs | 26.1.0 | MIT |
| hypothesis | 6.131.9 | MPL-2.0 |
| iniconfig | 2.3.0 | MIT |
| jsonschema | 4.26.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| markdown-it-py | 3.0.0 | OSI Approved :: MIT License |
| mdurl | 0.1.2 | OSI Approved :: MIT License |
| numpy | 2.4.2 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pluggy | 1.6.0 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| pytest | 9.0.2 | MIT |
| referencing | 0.37.0 | MIT |
| rpds-py | 2026.6.3 | MIT |
| ruptures | 1.1.10 | BSD-2-Clause |
| scipy | 1.17.1 | Copyright (c) 2001-2002 Enthought, Inc. 2003, SciPy Developers. |
| sortedcontainers | 2.4.0 | Apache 2.0 |
| typing_extensions | 4.16.0 | PSF-2.0 |

`uv.lock` records resolved artifacts and hashes. Analysis uses a single numerical worker through scripts/offline_exec.py. No model, reference corpus, or remote language resources are installed.

## Frozen build backend
- hatchling 1.29.0: MIT.
- pathspec 1.1.1: License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0).
- trove-classifiers 2026.6.1.19: License :: OSI Approved :: Apache Software License.

Exact build artifacts are locked in containers/build-requirements.lock.

## Frozen PELT backport

AHAS 1.0.1 bundles only the verbatim `Pelt._seg` method from ruptures PR #383, commit `a28574d9e63b0c2a966e176a1d049d3c9deaaaaf`, in `src/account_history_analyzer/_vendor/ruptures_pr383.py`. Its private subclass uses the unchanged ruptures 1.1.10 dependency. Original source and complete BSD-2-Clause notice are bundled alongside the method; `ruptures_pr383.json` pins their hashes. The wheel includes these files. The upstream test module is retained under `tests/vendor_pr383` with the import redirected to this private class. This backport is not a released/merged upstream version.
