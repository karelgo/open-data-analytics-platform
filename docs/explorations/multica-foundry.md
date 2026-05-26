# Exploration: Multica + Azure AI Foundry

> **Status: verified end-to-end** on 2026-05-09 against
> `https://devfreshmindsaifoundry…` with `gpt-4o`. This memo captures
> what works, what doesn't, and the exact incantation to wire the
> Multica daemon to Foundry via the `codex` CLI.

---

## TL;DR

**Yes** — Multica can use Azure AI Foundry endpoints, but **not at the
server**. The Multica server is provider-agnostic: no
`OPENAI_*`, `AZURE_*`, or `ANTHROPIC_*` keys in its env, no LLM client
in `server/`. The model call happens on the **developer's laptop**, in
whichever agent CLI the user picked. So "Multica + Foundry" is really
"`codex` (or another OpenAI-compatible CLI) + Foundry", with Multica's
daemon spawning that CLI per task.

For your existing setup, the recipe is two env vars before
`multica daemon start`. Details below.

---

## What I verified

### 1. Multica's server is provider-agnostic (source scan)

```sh
grep -E "OPENAI|AZURE|ANTHROPIC|EMBED|MODEL|LLM" \
  ~/sandbox/multica/.env.example
# → only: MULTICA_CODEX_MODEL=
```

A wider scan turned up references in
`server/internal/daemon/execenv/runtime_config.go` — but that file
*generates* `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` files for the agent
CLIs to read. It doesn't make any LLM calls itself. The provider/model
plumbing is exclusively at the agent-CLI layer.

The daemon registers each detected agent CLI in
`server/internal/daemon/config.go:100-176` and reads a per-CLI model
override from env:

| Agent | Model env var |
|---|---|
| Claude Code | `MULTICA_CLAUDE_MODEL` |
| **Codex** | **`MULTICA_CODEX_MODEL`** |
| OpenCode | `MULTICA_OPENCODE_MODEL` |
| OpenClaw | `MULTICA_OPENCLAW_MODEL` |
| Hermes / Gemini / Pi / Cursor / Copilot / Kimi / Kiro | `MULTICA_<NAME>_MODEL` |

### 2. Your Foundry endpoint accepts the key

Both URL forms work against `gpt-4o`:

| URL form | `/chat/completions` | `/responses` |
|---|---|---|
| `https://devfreshmindsaifoundry.openai.azure.com/openai/v1/…` (codex's `config.toml` form) | 200 | 200 |
| `https://devfreshmindsaifoundry.services.ai.azure.com/api/projects/proj-default/openai/v1/…` (project form, what you shared) | 200 | 200 |

Probed model deployments — only `gpt-4o` answered with 200; `gpt-4o-mini`,
`gpt-4`, `gpt-5`, `gpt-5-mini` returned `404 DeploymentNotFound` in this
project. (When `codex` boots it queries `/models` and the listing
mentioned `Llama-3.3-70B-Instruct` as well — there are more deployments,
just not under the names I guessed.)

### 3. End-to-end via `codex` worked

```sh
AZURE_OPENAI_API_KEY="<your-foundry-key>" \
  codex exec --skip-git-repo-check --model gpt-4o \
  "Reply with exactly the two characters: OK"
# →
# codex
# OK
# provider: azure
# model: gpt-4o
```

Codex picked up the `model_provider = "azure"` from your existing
`~/.codex/config.toml`, the API key from `AZURE_OPENAI_API_KEY`, the
model override from `--model gpt-4o`, hit the Foundry endpoint, got a
clean `OK` back.

---

## Two corrections to your existing setup

While verifying I noticed two mismatches in `~/.codex/config.toml`:

1. **`model = "gpt-5.4"`** — that deployment doesn't exist in your
   Foundry project. `gpt-4o` does. Either:
   - update the config to `model = "gpt-4o"` (your default codex
     everywhere becomes gpt-4o), **or**
   - leave the default and override per-context with `--model gpt-4o`
     (what I did) or `MULTICA_CODEX_MODEL=gpt-4o` (what Multica reads).

2. **`AZURE_OPENAI_API_KEY` not in your shell env** — codex falls back
   to `~/.codex/auth.json` (OAuth login) when the env var is missing.
   For Multica's daemon you'll want the env var set, otherwise the
   sub-shell codex inherits won't have credentials.

---

## Wiring Multica's daemon to Foundry (recipe)

After `kubectl apply -k platform/17-multica/.` brings up the server
side, on each developer laptop that should drive coding agents from
Foundry:

```sh
# 1) Install the Multica CLI + agent daemon (one-time).
brew install multica-ai/tap/multica

# 2) Point the CLI at the in-cluster server.
multica config set server_url https://multica.odap.local:8443
multica config set app_url    https://multica.odap.local:8443
multica login          # opens browser, completes email-code dance

# 3) Tell the codex sub-shell which Foundry deployment to use.
export AZURE_OPENAI_API_KEY="<your-foundry-key>"   # NOT in shell history; use a credential helper
export MULTICA_CODEX_MODEL=gpt-4o                  # override the stale gpt-5.4 default

# 4) Start the daemon. It will detect codex on PATH, register a runtime
#    with the server, and start polling for tasks.
multica daemon start
```

When you assign a Multica issue to a codex agent, the daemon spawns
`codex` with `--model gpt-4o` (because of `MULTICA_CODEX_MODEL`) and
codex calls Foundry via your existing `model_provider = "azure"`
config block. Each task gets its own scratch `CODEX_HOME` (see
`server/internal/daemon/execenv/codex_home.go`), so per-task
isolation is preserved without copying credentials around.

---

## What this does NOT cover

- **Claude Code, Gemini, Cursor.** These CLIs talk to their own SaaS
  providers (Anthropic API, Google AI, Cursor's router). They have no
  "swap base_url" hook today — pointing them at Foundry isn't possible
  via the same recipe.
- **The Multica server.** Even if you wanted "all Multica-driven agents
  must go through Foundry as a single egress point", the answer is
  per-CLI provider configuration, not a single Multica switch. There is
  no single switch.
- **`opencode`.** It IS OpenAI-compatible and could be wired to Foundry
  similarly, but it has its own config dir (`~/.opencode/`) and
  conventions; not tested here.
- **Embeddings.** Multica needs `pgvector` but bootstraps without
  enabling the extension — no embedding-call surface seen during
  first-boot. If autopilot or skill-recommendation features later
  enable embedding calls server-side, that becomes a new integration
  question.

---

## Security caveat

The Foundry key was pasted in chat history during this exploration —
treat it as compromised and rotate it in the Azure portal. For
production:

- Put `AZURE_OPENAI_API_KEY` in macOS Keychain / 1Password /
  age-encrypted dotfiles, sourced lazily into the shell that runs
  `multica daemon start`. Don't put it in `~/.zshrc`.
- Prefer Azure Workload Identity / Managed Identity over long-lived
  keys when the daemon eventually runs on shared infrastructure.
- The codex daemon writes per-task scratch state to
  `~/.codex/.tmp/<task>` — this includes prompts and outputs. If
  Multica tasks ever touch sensitive UWV data, that scratch dir must
  be classified accordingly under AVG / BIO. Same compliance question
  as the runtime-agent path raised in `multica-vs-nanitics.md`.
