# In-cluster Multica daemon, bundled with the OpenAI Codex CLI wired to
# the Azure AI Foundry endpoint.
#
# History: opencode was briefly installed alongside codex as a fallback
# runtime, but Foundry's gpt-5.4-nano deployment rejects opencode's
# request payload with "Unknown parameter: 'reasoningSummary'" (opencode's
# @ai-sdk/openai-compatible provider auto-attaches a reasoning param it
# can't be told to omit). Removed in commit log; restore that commit and
# the matching opencode.json + entrypoint section if Foundry compatibility
# is resolved upstream.
#
# Build context: this `platform/20-multica-daemon/` directory.
# Build manually:
#
#   ./build-and-load.sh        # from platform/20-multica-daemon/
#
# Or:
#
#   docker build -t odap/multica-daemon:dev .

# Stage 1 — grab the multica CLI binary from the upstream backend image.
# We don't reuse that image as the runtime base because we need Node.js
# for codex, and the upstream image is a slim distroless-ish layout.
FROM ghcr.io/multica-ai/multica-backend:latest AS multica-src

# Stage 2 — runtime. Node 20 + Debian slim gives us npm, apt for git,
# and a real shell for the entrypoint script.
FROM node:20-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# - git: clone repos the coding agent will edit
# - ca-certificates: for HTTPS calls to GitHub, Foundry, Multica
# - jq: handy for the entrypoint script to parse Multica config output
# - openssh-client: future-proof for git+ssh, costs almost nothing
# - tini: PID-1 to reap zombies; the daemon spawns codex sub-shells per task
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
         git ca-certificates jq openssh-client tini \
    && rm -rf /var/lib/apt/lists/*

# Multica CLI — the binary that exposes `multica daemon start`.
COPY --from=multica-src /app/multica /usr/local/bin/multica
RUN chmod +x /usr/local/bin/multica

# OpenAI Codex CLI. Pinned to a known-good major to avoid surprise
# breakage on rebuild; bump deliberately when you re-test.
RUN npm install -g @openai/codex@0.130.0 \
    && npm cache clean --force

# Replace the npm-installed `codex` shim with a wrapper that disables
# codex' bubblewrap sandbox for daemon-spawned per-task runs. The real
# binary moves to /usr/local/bin/codex.real. See codex-wrapper.sh for
# the full rationale (bwrap can't create namespaces in this pod's
# kernel/seccomp/cap profile; the pod itself is the sandbox).
COPY codex-wrapper.sh /usr/local/bin/codex-wrapper.sh
RUN mv /usr/local/bin/codex /usr/local/bin/codex.real \
    && mv /usr/local/bin/codex-wrapper.sh /usr/local/bin/codex \
    && chmod +x /usr/local/bin/codex

# Non-root user. The Debian base ships a `daemon` user, and node:20 ships
# a `node` user at uid 1000, so use `multica` at uid 1001. The daemon
# writes to ~/.multica and codex to ~/.codex — both go on the workspace
# volume mounted at /home/multica.
RUN useradd --system --uid 1001 --create-home --shell /bin/bash --home-dir /home/multica multica

# Codex config template. The entrypoint copies it into ~/.codex/config.toml
# at runtime so the workspace volume holds the live copy (codex writes
# per-task scratch there too, and ~/.codex must be writable).
COPY codex-config.toml /etc/codex/config.toml.template
RUN chown -R multica:multica /etc/codex

# Entrypoint: configure server URL, log in with the bootstrap PAT,
# then exec `multica daemon start` in the foreground.
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER multica
WORKDIR /home/multica

# tini → entrypoint → multica daemon start
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
