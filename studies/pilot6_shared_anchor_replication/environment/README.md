# Pilot6 preservation baseline

The [preservation baseline](preservation-baseline.json) was frozen before Pilot6
selection or scoring. It records all 460 local public Pilot3 files, 301 Pilot4
files, and 105 Pilot5 files, excluding Python and test caches. This includes the
unchanged Pilot4 execution, scoring and arithmetic helpers.

The complete private trees are covered without exclusions: 16,365 Pilot3 files,
32 Pilot4 files, and 217 Pilot5 files. Their filenames and exact inventories are
kept only in the private Pilot6 preservation directory. The public manifest
contains aggregate private file counts and byte sizes plus the private manifest
hash. No original writing, private identities or private file paths are published.

The historical protection inventory declares 23 source files: the original 22
sources plus the Pilot3 extension. The extension is already included in the
private tree inventory. The remaining original sources, their supplied snapshot
manifests, and metadata binding documents produce 49 distinct external bindings
(44,757,980 bytes). Their recorded prior hashes were checked; duplicate paths
were counted once. Confirmation material was hashed without preprocessing or
scoring.

All 27 fresh engine identity checks passed. The 54 installed files, 54 reviewed
working-source files, and 54 local workspace package files match the immutable
reviewed Git objects at `ea41d82ecc3f6585a7dc2bca92ede34740f0b62d`.
The installed version remains 1.0.4, its fingerprint remains
`bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179`, and its
configuration hash remains
`8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925`.
Dependency versions, interpreter identity, resources and archived wheel bytes
also remain unchanged. Fresh probes containing operational paths stay private.

The [new preservation helper](preserve_prior_studies.py) extends the unchanged
Pilot5 preservation helpers and unchanged Pilot3 environment probe. Fourteen
synthetic tests passed, including private inventory completeness, cache policy,
missing/added/changed files, symlinks, concurrent changes, read budgets, private
reporting and a complete freeze/recheck cycle. The actual baseline hashed
17,529 files and 3,924,149,717 bytes in 8.38 seconds under the recorded wrapper,
with peak child RSS of 84.15 MiB. No analyzer or preprocessor call ran.

## Final recheck

Run the unchanged helper through `scripts/offline_exec.py`, using a fresh output
directory and filename. Supply the same private parent, the public baseline, and
the original private `preservation-01/private-manifest.json`:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<INSTALLED_BASELINE> \
  .venv/bin/python -B scripts/offline_exec.py .venv/bin/python -B \
  studies/pilot6_shared_anchor_replication/environment/preserve_prior_studies.py verify \
  --private-parent "$PRIVATE_PARENT" \
  --private-out "$PRIVATE_PARENT/pilot6_private/preservation-final-01" \
  --public-out studies/pilot6_shared_anchor_replication/environment/preservation-final-01.json \
  --baseline studies/pilot6_shared_anchor_replication/environment/preservation-baseline.json \
  --private-baseline "$PRIVATE_PARENT/pilot6_private/preservation-01/private-manifest.json"
```

Record that command with the unchanged `run_logged.py` wrapper, placing its logs
under the private Pilot6 directory. The checker enforces a 600-second alarm,
4 GiB address-space limit, 100,000-file and 16 GiB hash budgets, and a 64 MiB
per-output-file limit. It refuses to overwrite a previous attempt. Final reports
publish difference counts only; exact changed private paths remain private.
The [final recheck](preservation-final-01.json) passed after the completed pipeline: all 17,529 files and 3,924,149,717 bytes matched, with no earlier-study or protected-source differences. All 27 engine checks passed. The [safe execution summary](final-preservation-execution-summary.json) records 9.50 seconds and 84.24 MiB peak child RSS; private command arguments remain outside the public report.
