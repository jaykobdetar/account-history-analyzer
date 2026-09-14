# Frozen CPython 3.12.3 Linux base. Analysis runs with --network none.
FROM python:3.12.3-slim-bookworm@sha256:afc139a0a640942491ec481ad8dda10f2c5b753f5c969393b12480155fe15a63
ENV PYTHONHASHSEED=0 TZ=UTC OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /opt/ahas
COPY requirements.lock.txt /tmp/requirements.lock.txt
COPY containers/build-requirements.lock /tmp/build-requirements.lock
# Setup is networked; every accepted dependency artifact must match a frozen hash.
RUN python -m pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock.txt -r /tmp/build-requirements.lock
COPY pyproject.toml README.md LICENSE uv.lock ./
COPY src ./src
COPY schemas ./schemas
COPY config ./config
COPY tests ./tests
COPY fixtures ./fixtures
COPY design_examples ./design_examples
COPY scripts ./scripts
RUN python -m pip install --no-deps --no-build-isolation .
ENTRYPOINT ["ahas"]
CMD ["--help"]
