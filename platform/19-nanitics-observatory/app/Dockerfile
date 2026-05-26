# Image for the Nanitics Observatory wired to Azure AI Foundry, deployed
# as part of the UWV reference data platform.
#
# Build context: this `app/` directory itself. The `observatory-ui/`
# directory must be populated *before* build — the helper script
# `../build-and-load.sh` copies it from the nanitics SDK repo.
#
# Build manually:
#
#   ./build-and-load.sh   # from platform/19-nanitics-observatory/
#
# Or:
#
#   cp -R <nanitics-repo>/observatory/dist-embed app/observatory-ui
#   docker build -t odap/nanitics-observatory:dev app/

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# Install Nanitics + FastAPI from PyPI. Pin a known-good version; the
# layer README explains how to bump.
#
# httpx is the watcher's HTTP client for Prometheus + Multica. nanitics
# already depends on it transitively (via the OpenAI SDK), but the
# watcher pins it explicitly so it doesn't disappear under us if nanitics
# swaps client libraries.
RUN pip install \
        "nanitics[api]==0.1.0" \
        "uvicorn[standard]>=0.30" \
        "httpx>=0.27" \
        "kubernetes_asyncio>=29"

# Embedded Observatory UI bundle. Populated from the nanitics repo at
# build-time by the helper script. If absent, the API still works but
# the UI root returns a fallback page (per the SDK's contract for
# static_dir=None — handled in app.py).
COPY observatory-ui /srv/observatory-ui

# Application glue + chat UI static assets.
COPY app.py /srv/app.py
COPY watcher.py /srv/watcher.py
COPY static /srv/static

# Drop privileges.
RUN useradd --system --uid 1000 --create-home --shell /usr/sbin/nologin app \
    && chown -R app:app /srv
USER 1000:1000

EXPOSE 8001
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
