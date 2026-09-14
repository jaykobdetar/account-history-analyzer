# Frozen Linux reference recipe

The image pins CPython 3.12.3 using the official Python slim-bookworm image digest in `Dockerfile`. Runtime/test dependencies and build dependencies have exact versions and accepted artifact hashes. Image setup downloads these packages; subsequent analyses and tests use Docker network isolation.

From the repository root:

```bash
docker build -f containers/Dockerfile -t ahas-reference:1.0.3 .
docker run --rm --network none --env AHAS_NETWORK_ISOLATION=docker_network_none \
  --entrypoint python ahas-reference:1.0.3 -m pytest -q
mkdir -p container-output
docker run --rm --network none --user "$(id -u):$(id -g)" \
  --env AHAS_NETWORK_ISOLATION=docker_network_none \
  --mount "type=bind,src=$PWD/container-output,dst=/output" \
  ahas-reference:1.0.3 analyze \
  --input fixtures/arithmetic.jsonl --manifest fixtures/arithmetic.snapshot.json \
  --out /output/arithmetic
```

The environment marker describes the accompanying `--network none`; the marker alone does not block networking. Do not omit the network flag. No daemon/API credentials are used by the analyzer. Container creation requires access to your local Docker daemon. Source input mounts can be read-only.

The generic Chrome test is skipped inside the image because Chrome/Node are not shipped; the release ran it separately with internet sockets denied. Tests and analyses inside the image otherwise use the same public package API/CLI. Actual container test and reproduction outcomes are recorded in `docs/REPORT005.md` (1.0.3), `docs/AUDIT_REPAIR.md` (1.0.2), `docs/PR383.md` (1.0.1) and `docs/EVALUATION.md` (historical 1.0.0); the recipe itself does not claim a result.

The base image is version-frozen for reproducing this release, not a promise of current operating-system security patches. Updating it creates a new reference environment to test. Cross-platform numerical/byte agreement is not implied by the wheel being pure-Python: NumPy/SciPy/ruptures contain pinned native dependencies.
