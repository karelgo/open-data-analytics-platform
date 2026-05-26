# Exploration: Multica naast Nanitics Observatory

> **Status: exploratory memo** in branch `feat/multica-explore`. Not yet
> an ADR. Outcome of running `multica-ai/multica` self-host locally and
> comparing the integration surface against `19-nanitics-observatory`.
>
> Promote to ADR-0008 when:
> - we've run `platform/17-multica/` end-to-end on k3d, confirmed login
>   + a single coding-agent task assignment;
> - the v2 questions below are decided (custom web image, MinIO uploads,
>   oauth2-proxy or push for upstream OIDC);
> - compliance-mapping is extended (AI Act art. 50 / Annex III scoping
>   covers both Nanitics and Multica).

---

## TL;DR

Multica and Nanitics target **different lanes**. They coexist cleanly in
the platform. Nothing about Multica replaces Nanitics; nothing about
Nanitics blocks Multica. The risk is **narrative confusion** — two
"agent" things in one platform — not technical conflict.

The sharp test we should keep applying: *whose laptop runs the agent?*
- **Nanitics**: the cluster runs the agent (FastAPI + Nanitics SDK pod).
- **Multica**: the developer's laptop runs the agent (Claude Code, Codex, …).

That single line resolves most "wait, what does this do" conversations.

---

## Two lanes, one platform

|                                | **Nanitics Observatory** ([platform/19-nanitics-observatory](../../platform/19-nanitics-observatory/README.md)) | **Multica** ([platform/17-multica](../../platform/17-multica/README.md)) |
|--------------------------------|----------------------------------------------------|----------------------------------------------------|
| Lane                           | Runtime / inside-the-platform                      | Dev-loop / build-time                              |
| What runs in-cluster           | One pod: FastAPI + Nanitics SDK                    | Three pods: Postgres (pgvector), Go backend, Next.js frontend |
| Where the agent executes       | The pod (the SDK *is* the agent runtime)           | **Developer's laptop**                             |
| LLM                            | Azure AI Foundry endpoint                          | None server-side; laptop daemons call their own model |
| Auth                           | None (dev-only); recommends oauth2-proxy           | Email-code (RESEND_API_KEY) or Google OAuth; no native OIDC |
| Database                       | In-memory by default; Postgres opt-in              | Postgres 17 + pgvector required                    |
| Trace / progress data          | Span tree, plan, MCTS events                       | Issues, comments, agent runtime registry, chat     |
| Killer use-case                | "Build a `query_trino` tool, watch the trace"      | "Assign a dbt-PR task to Claude Code, track it"    |

The natural workflow ties them: assign a Multica task to a coding agent
→ it edits `platform/19-nanitics-observatory/app/app.py` to add a new
runtime tool → the developer triggers a run and the new agent run shows
up in the Nanitics UI. **One builds, the other observes.**

---

## What I learned by actually running Multica

Run command:

```sh
cd ~/sandbox/multica
JWT=$(openssl rand -hex 32) && sed -i.bak "s/^JWT_SECRET=.*/JWT_SECRET=$JWT/" .env
sed -i.bak2 "s/^PORT=.*/PORT=8090/" .env   # 8080 collided with k3d serverlb
docker compose -f docker-compose.selfhost.yml up -d
```

Findings that shaped the K8s adaptation:

1. **pgvector is required, not optional.** The image
   `pgvector/pgvector:pg17` ships with `vector 0.8.2` available. Multica
   doesn't enable the extension on bootstrap (only `pgcrypto`,
   `plpgsql` show up after first migration), but a code path expects it
   to be installable. Cluster's existing Postgres operators don't bundle
   pgvector → **dedicated Postgres** is the path of least resistance.
2. **Schema is wide and coherent.** First boot creates ~40 tables —
   `agent`, `agent_runtime`, `agent_skill`, `agent_task_queue`,
   `autopilot`, `autopilot_run`, `autopilot_trigger`, `chat_message`,
   `chat_session`, `daemon_connection`, `daemon_token`, `inbox_item`,
   `issue`, `issue_dependency`, `member`, … . This is "an issue tracker
   + agent registry + chat + autopilot", not a thin coordination layer.
   Treat it as its own data domain.
3. **Health endpoints**: `/health` (cheap, dependency-free),
   `/readyz` (db + migrations), `/healthz` (alias of readyz). Maps
   cleanly to K8s liveness/readiness probes.
4. **Auth has no OIDC.** Email-code via Resend, or Google OAuth, or
   `MULTICA_DEV_VERIFICATION_CODE` for testing. Putting it behind
   oauth2-proxy + Keycloak gates *network access* but doesn't replace
   Multica's user model — would create a confusing dual-auth setup.
5. **WebSocket is build-time-baked.** `NEXT_PUBLIC_WS_URL` lives in
   the Next.js bundle. The official `multica-web:latest` image bakes in
   `ws://localhost:8080/ws` — won't work behind any reverse proxy
   without rebuilding the web image. Real-time features (chat
   streaming, live issue updates, daemon status) will fail in v1.
6. **S3 is genuinely optional.** Without `S3_BUCKET`, uploads land on a
   local volume. Trivial to switch to MinIO later.
7. **Metrics endpoint is opt-in and explicitly NOT for public ingress.**
   `METRICS_ADDR=0.0.0.0:9090`, ClusterIP-only Service for Prometheus.

---

## Decisions for `platform/17-multica/`

Each captured in the deployment README, repeated here for reviewers:

| Decision | Choice | Why |
|---|---|---|
| Postgres | Dedicated StatefulSet (`pgvector/pgvector:pg17`) | Existing operators don't bundle pgvector; agent/issue/chat is its own data domain |
| Auth (v1) | Multica's native email-code, codes printed to backend logs | Adding oauth2-proxy creates dual-auth without solving user-model duplication |
| Auth (v2 candidate) | Either oauth2-proxy + Keycloak, or push for upstream OIDC | Decide after v1 + a compliance-mapping pass |
| Ingress | Single host (`multica.odap.local:8443`), path-based: `/api`, `/auth`, `/uploads`, `/ws` → backend; `/` → frontend | Matches upstream Nginx example; one cert, one /etc/hosts entry |
| WebSocket (v1) | Broken in browser (build-time URL mismatch), HTTP works | Acknowledged limitation; v2 builds a custom web image |
| Storage (v1) | PVC for `backend-uploads` | Simplest; defer MinIO until rest stabilises |
| Metrics | `METRICS_ADDR` enabled, ClusterIP-only Service with `prometheus.io/scrape` annotations | Upstream explicitly forbids public ingress for metrics |
| Realtime hub | In-memory (single-replica) | `REDIS_URL` opt-in; not worth a Redis pod yet |
| Compliance | TODO — extend `docs/compliance-mapping.md` | Both Nanitics and Multica need AI Act art. 50 / Annex III scoping |

---

## What did NOT make v1

These are conscious deferrals, not omissions:

- **oauth2-proxy + Keycloak.** Captured above.
- **Custom web image with `NEXT_PUBLIC_WS_URL` baked.** Mirror the
  `19-nanitics-observatory/build-and-load.sh` pattern; touches
  `infrastructure/` for image push, hence postponed.
- **MinIO bucket for uploads.** Provisioning a bucket means touching
  `infrastructure/` (MinIO Helm values + bucket policy). Not needed
  for the smoke-test slice.
- **Vector → OpenSearch** for backend logs. The audit trail of agent
  task assignments belongs in OpenSearch, but the pipeline is not yet
  hooked up.
- **dbt-style platform skills.** "Run a Trino query and review the
  result", "Generate a NiFi flow template", "Author a Rego test" —
  these would be the actual delivered value of Multica for this
  platform. Out of scope until v1 stands up cleanly.

---

## Risks and sharp edges

1. **Two young upstreams.** Nanitics SDK is v0.1.x; Multica is similarly
   early. We're betting on two breaking-change cycles, not one.
2. **Compliance footprint.** Both add LLM-touching surface. Nanitics
   makes outbound calls from inside the cluster (Azure AI Foundry).
   Multica's coding-agent daemons make outbound calls from
   developer laptops to whatever provider those agents use (Anthropic,
   OpenAI, …). Both need explicit scoping in
   `docs/compliance-mapping.md` before either is "deployed for real".
3. **Resource pressure.** k3d cluster already lives near 8 GiB. Multica
   adds three pods (Postgres ≈ 256 MiB, backend ≈ 256 MiB, frontend
   ≈ 256 MiB) → roughly +1 GiB committed. Document this in the top-level
   README's "scaled-down" notes.
4. **Naming ambiguity.** "We have two agent platforms" is bewildering
   without the lane framing. Insist on the *whose-laptop-runs-it* test
   in any onboarding doc.

---

## Success criteria for promoting to ADR-0008

- [ ] `kubectl apply -k platform/17-multica/.` brings up all three
      pods Ready on k3d.
- [ ] `https://multica.odap.local:8443/` loads the frontend.
- [ ] Login via email-code (from backend logs) succeeds.
- [ ] At least one coding agent (e.g. Claude Code) registers a daemon
      against the cluster's backend and accepts a task.
- [ ] WebSocket limitation is either fixed (custom web image) or
      decisively documented as "live updates require manual refresh in
      v1".
- [ ] `docs/compliance-mapping.md` has a section covering both
      Nanitics and Multica's data flows, classified storage, and LLM
      egress.
