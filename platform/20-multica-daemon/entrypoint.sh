#!/usr/bin/env bash
# Entrypoint for the in-cluster Multica daemon.
#
# Boot order:
#   1. Materialise ~/.codex/config.toml from the image template (the
#      workspace volume hides anything under ~ on the image layer).
#   2. Point the multica CLI at the in-cluster server.
#   3. Log in with the bootstrap Personal Access Token (PAT) — first
#      boot only; subsequent boots reuse ~/.multica/auth.json on the PVC.
#   4. exec `multica daemon start` in the foreground.

set -euo pipefail

# --- 1. Sanity-check the credentials codex inherits from this process. ---
if [[ -z "${AZURE_OPENAI_API_KEY:-}" ]]; then
  echo "FATAL: AZURE_OPENAI_API_KEY is unset. Codex cannot call Foundry." >&2
  exit 1
fi

# --- 1a. Codex config on the writable volume ------------------------------
# Always re-copy the template so a fresh image (with config tweaks like
# sandbox_mode or new providers) takes effect on the next rollout. The
# PVC still holds per-task scratch under ~/.codex/.tmp, so we only
# overwrite the single config.toml file — nothing under it.
mkdir -p "$HOME/.codex"
cp /etc/codex/config.toml.template "$HOME/.codex/config.toml"

# --- 2. Point CLI at the Multica server ------------------------------------
: "${MULTICA_SERVER_URL:?MULTICA_SERVER_URL must be set (e.g. http://multica-backend.odap-platform:80)}"
: "${MULTICA_APP_URL:?MULTICA_APP_URL must be set (used in OAuth callbacks)}"

multica config set server_url "$MULTICA_SERVER_URL"
multica config set app_url    "$MULTICA_APP_URL"

# --- 3. Authenticate, if we haven't already --------------------------------
# The CLI stores its token under ~/.multica/. We only run `login` the
# first time — subsequent restarts reuse the stored token, even if the
# Secret is rotated.
if multica auth status 2>/dev/null | grep -q 'Logged in'; then
  echo "multica: already authenticated, skipping login"
elif [[ -n "${MULTICA_API_TOKEN:-}" ]]; then
  echo "multica: authenticating with bootstrap PAT"
  multica login --token "$MULTICA_API_TOKEN"
else
  echo "FATAL: not authenticated and MULTICA_API_TOKEN is empty." >&2
  echo "       Create a PAT in Multica's UI (Settings → Personal Access Tokens)" >&2
  echo "       and provision Secret 'multica-daemon-auth' with key MULTICA_API_TOKEN." >&2
  exit 2
fi

# --- 4. Daemon -------------------------------------------------------------
# `multica daemon start` daemonizes (forks + returns) by default — that
# would kill PID 1 and crash-loop the container. `--foreground` keeps
# it attached so tini can supervise it and container stdout captures
# every poll / claim / codex spawn.
echo "multica daemon starting (foreground mode)"
echo "  server:        $MULTICA_SERVER_URL"
echo "  codex model:   ${MULTICA_CODEX_MODEL:-<default in config.toml>}"
echo "  workspace:     $HOME"
exec multica daemon start --foreground
