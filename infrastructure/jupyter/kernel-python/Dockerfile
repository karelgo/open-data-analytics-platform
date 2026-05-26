# ODAP Lab — single-user JupyterLab kernel image.
#
# Base: `quay.io/jupyter/scipy-notebook` brings pandas / numpy / matplotlib /
# scikit-learn / sympy. We layer the lakehouse-specific libraries:
#
#   - trino       — SQL access to bronze/silver/gold/sensitive (honors OPA).
#   - deltalake   — read/write Delta tables directly on MinIO via delta-rs.
#   - duckdb      — local analytics engine for ad-hoc joins on Trino results.
#   - polars      — fast in-process dataframe.
#   - s3fs        — browse and read raw objects in the MinIO buckets.
#   - kafka-python — peek at Kafka topics for streaming demos.
#   - openmetadata-ingestion — query the catalog API from notebooks.
#   - jupyterlab-git — commit / push / pull from inside the lab UI.
#   - ipywidgets   — interactive controls in notebooks.
#
# A small `odap_lab` helper package is baked in alongside the libraries so a
# user can do `from odap_lab import trino, s3, hms` and get pre-configured
# clients that respect the env injected by the JupyterHub spawner.
#
# Build (vanuit repo-root):
#   docker build -t odap/jupyter-kernel:dev -f infrastructure/jupyter/kernel-python/Dockerfile .
#   k3d image import odap/jupyter-kernel:dev -c odap-platform
#
# Of:  make jupyter-image
#
# SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE.
FROM quay.io/jupyter/scipy-notebook:2024-10-21

USER root

# OS-level tooling: git for jupyterlab-git, openssh-client for git@ remotes,
# ca-certificates so we can swap in the Platform CA bundle later, less for `git log`.
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      git \
      openssh-client \
      ca-certificates \
      less \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# Build-time pip cache cleanup keeps the image lean for k3d import.
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

USER ${NB_UID}

# Pinned versions: bump deliberately. trino 0.330+ removes deprecated transport
# code; deltalake 0.21+ supports MinIO endpoint via storage_options.
RUN pip install --no-cache-dir \
      "trino[sqlalchemy]==0.330.0" \
      "deltalake==0.21.0" \
      "duckdb==1.1.3" \
      "polars==1.13.1" \
      "pyarrow==17.0.0" \
      "s3fs==2024.10.0" \
      "boto3==1.35.50" \
      "kafka-python==2.0.2" \
      "ipywidgets==8.1.5" \
      "jupyterlab-git==0.50.2" \
      "openmetadata-ingestion[trino]==1.5.5" \
 && jupyter labextension list 2>/dev/null | grep -q jupyterlab-git \
 || true

# Bake the odap_lab helper into site-packages. The base image ships exactly
# one /opt/conda/lib/python3.*/site-packages directory; we resolve it at
# build-time instead of relying on shell glob expansion (which would error
# if cp interprets multiple expansions as "copy into existing directory").
COPY infrastructure/jupyter/kernel-python/odap_lab /tmp/odap_lab_src
USER root
RUN PYSP="$(ls -d /opt/conda/lib/python3.*/site-packages | head -1)" \
 && cp -r /tmp/odap_lab_src "$PYSP/odap_lab" \
 && rm -rf /tmp/odap_lab_src \
 && chown -R ${NB_UID}:${NB_GID} "$PYSP/odap_lab"
USER ${NB_UID}

# Default working directory for notebooks. Mounted to a PVC at runtime so user
# work persists across pod restarts.
WORKDIR /home/${NB_USER}/work

# JupyterLab settings: enable the git extension surface by default.
COPY --chown=${NB_UID}:${NB_GID} infrastructure/jupyter/kernel-python/overrides.json \
     /opt/conda/share/jupyter/lab/settings/overrides.json

# Smoke check at build time — import everything once, fail the build if not.
RUN python -c "import trino, deltalake, duckdb, polars, s3fs, kafka, odap_lab; print('odap_lab kernel imports OK')"
