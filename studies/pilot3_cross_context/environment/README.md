# Frozen installed AHAS baseline

Verification passed for commit `ea41d82ecc3f6585a7dc2bca92ede34740f0b62d`.
The evaluation target contains a noneditable AHAS 1.0.4 wheel. Both the imported
module version and installed distribution metadata report 1.0.4. Every packaged
file matches the pinned source byte for byte.

- Implementation fingerprint: `bfc989028bf2b47c506d1ba501287d4e362aadc25ca5c731c41e4b27a336e179`.
- Expanded analytical configuration: `8fd0239fe2f87c9f1506786ac36099fe996e00cc6e021b3ecc67fbb65cd2d925`.
- Environment: CPython 3.12.3, Linux x86_64; numpy 2.4.2, scipy 1.17.1,
  ruptures 1.1.10, markdown-it-py 3.0.0, jsonschema 4.26.0.
- Frozen guards include 20 retained words per record; 1,000 retained words and
  eight eligible records per comparison side; 1,000 words and eight records per
  standard window; one-record dominance above 50%; ten contraction opportunities;
  eight windows and three windows per segment for change analysis.
- The selected existing preprocessing, configuration, comparison qualification,
  and window regressions passed: **59 tests**. Every imported AHAS module came
  from the installed wheel target. Tests used only synthetic repository fixtures.

The preexisting workspace virtual environment has stale 1.0.0 *editable*
distribution metadata. Its editable import points to workspace source, whose
`__version__` is 1.0.4 and whose fingerprint already matches the pinned baseline.
Editable metadata does not automatically refresh when source files change. The
evaluation installation resolves that mismatch without changing the workspace
virtual environment or production source.

The package target is `<PINNED_INSTALL>`; dependencies are reused from
the existing virtual environment and were individually checked against the
project's exact pins. This is an isolated package target, not a newly provisioned
interpreter. All installation actions were offline and used `--no-deps`.

## Reproduction

From the pinned repository at `<PINNED_SOURCE>`, build with the
workspace virtual environment's Python:

```sh
<WORKSPACE>/.venv/bin/python -m hatchling build -t wheel -d <WHEEL_BUILD>
```

Install the wheel into the evaluation target:

```sh
uv --cache-dir <PACKAGE_CACHE> pip install --offline --no-deps --python <WORKSPACE>/.venv/bin/python --target <PINNED_INSTALL> <WHEEL_BUILD>/account_history_analyzer-1.0.4-py3-none-any.whl
```

Run evaluation scripts against the actual wheel:

```sh
PYTHONPATH=<PINNED_INSTALL> <WORKSPACE>/.venv/bin/python path/to/evaluation_script.py
```

From the workspace repository, reproduce this evidence with:

```sh
.venv/bin/python studies/pilot3_cross_context/environment/verify_environment.py
.venv/bin/python studies/pilot3_cross_context/environment/run_installed_guards.py
```

`editable_before.json`, `pinned_source.json`, and `installed_wheel.json` retain
paths, versions, package file hashes, resource hashes, analytical defaults, and
dependency versions. `verification_summary.json` retains the wheel hash and all
14 identity checks. `installed_guard_tests.json` and `installed_guard_tests.log`
retain the exact selected tests, result, and imported module paths. The checks
in this directory neither read nor score the study corpus or reserve.
