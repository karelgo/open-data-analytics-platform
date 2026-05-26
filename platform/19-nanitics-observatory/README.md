# 16 — Nanitics Observatory

Deploys the [Nanitics](https://github.com/nanitics/nanitics) Observatory
(an agent-trace viewer) on the UWV reference data platform, wired to an
**Azure AI Foundry** model endpoint as the LLM provider.

The Observatory is a developer-facing UI for inspecting agent runs —
LLM calls, tool invocations, span tree, capability panels (memory,
planning, HITL, evaluation). The Python app shipped here is a thin
glue layer: it serves the Observatory router under `/api/observatory/`
and exposes four agent-type endpoints so each Observatory view (ReAct,
ReWOO plan, Reflexion retry, LATS MCTS tree) has traces to render.

| Endpoint | Purpose | Notes |
|---|---|---|
| `GET /chat` | Browser chat UI — pick an agent, type a task, watch events stream | Single-page; no build step. Talks to the streaming endpoint and the existing Observatory SSE |
| `POST /run/<slug>` | Run an agent **synchronously** — blocks until done | Use for curl / scripts |
| `POST /run/<slug>/stream` | Kick off an agent **asynchronously** — returns `{run_id}` in <50 ms | Pair with `GET /api/observatory/runs/<id>/stream` for live events |
| `POST /run` | Legacy alias for `POST /run/react` | |
| `GET /agents` | JSON index: slug, label, description, default task | Used by the chat UI to populate the agent picker |
| `GET /health` | Liveness probe | |
| `/api/observatory/*` | Embedded trace viewer | SSE stream lives at `/api/observatory/runs/<id>/stream` |

The four demo agents (`react`, `rewoo`, `reflexion`, `lats`) each emit a distinctive event signature that drives the Observatory's agent-specific views — see [Observatory views](#observatory-views) below.

A fifth agent, [`watcher`](#platform-watcher), is the real-work surface: it investigates platform health signals (Alertmanager + Prometheus + OpenSearch logs + K8s events) and files Multica tasks against the `platform-ops` workspace when something needs human attention. Tasks are filed without the `approved` label — explicit human approval is required before any coding agent can claim the work.

> **Status: dev-only.** Per the SDK docs, Observatory v0.1.0 is not a
> production observability platform — no built-in auth, no
> multi-tenancy, no retention, no credential scrubber. We rely on the
> existing nginx-ingress + cert-manager chain for TLS and treat the
> endpoint as trusted-network only. See
> [docs/guides/observatory-integration.md](https://github.com/nanitics/nanitics/blob/main/docs/guides/observatory-integration.md)
> in the SDK repo for production seams.

---

## Layout

```
platform/19-nanitics-observatory/
├── README.md                  ← this file
├── build-and-load.sh          ← build image + k3d import
├── kustomization.yaml         ← kustomize entry point
├── configmap.yaml             ← non-sensitive config (endpoint URL, model, watcher URLs)
├── secret.yaml                ← Azure AI Foundry API key (placeholder!)
├── secret-multica.yaml        ← Multica bearer token (placeholder!)
├── secret-opensearch.yaml     ← OpenSearch basic-auth creds (placeholder, optional)
├── rbac.yaml                  ← SA + ClusterRole (events read-only) for the watcher
├── deployment.yaml            ← single-pod Deployment
├── service.yaml               ← ClusterIP :80 → :8001
├── ingress.yaml               ← nanitics.odap.local
└── app/
    ├── Dockerfile             ← Python 3.11 + nanitics[api] + uvicorn + httpx + kubernetes_asyncio
    ├── app.py                 ← FastAPI + Observatory + agent registry
    ├── watcher.py             ← platform watcher tools (alerts, prom, logs, events, multica)
    ├── .gitignore             ← excludes the synced UI bundle
    └── observatory-ui/        ← (synced at build time, gitignored)
```

---

## One-time setup

### 1. Provision an Azure AI Foundry model

In the Azure portal, create or pick an **Azure AI Foundry** project,
deploy a chat model (e.g., `gpt-4o-mini`), and grab two values:

- **Endpoint URL** — looks like
  `https://<your-resource>.services.ai.azure.com/openai/v1`
  (Foundry's OpenAI-compatible v1 surface).
- **API key** — from the deployment's keys & endpoint page.

> **If you only have an old-style Azure OpenAI deployment**
> (URL contains `/openai/deployments/<name>/...`), Nanitics' OpenAI
> client cannot call it directly. See [Variant: deployment-style Azure
> OpenAI via LiteLLM](#variant-deployment-style-azure-openai-via-litellm)
> below.

### 2. Add the hostname to your hosts file

```sh
echo "127.0.0.1 nanitics.odap.local" | sudo tee -a /etc/hosts
```

> **Note on the port:** the k3d serverlb maps `host:8080 → cluster:80`
> and `host:8443 → cluster:443`. All UWV ingress URLs are reached at
> `:8443`, not `:443`. If you see a connection refused / hanging
> browser, that's why. The portal at `platform.odap.local`
> behaves the same way — same `:8443` quirk.

### 3. Set the endpoint in the ConfigMap and the API key as a Secret

Endpoint goes in `configmap.yaml` (it's an identifier, not a credential):

```sh
$EDITOR configmap.yaml   # set AZURE_AI_FOUNDRY_ENDPOINT and LLM_MODEL
```

The `AZURE_AI_FOUNDRY_ENDPOINT` should end at `/openai/v1` (strip any
`/responses` or `/chat/completions` suffix the portal showed you — the
SDK appends the operation path itself). `LLM_MODEL` must match a
deployment name in your project.

> **Find your deployment name** by probing the endpoint with curl:
> ```sh
> for m in gpt-4o gpt-4o-mini gpt-4 gpt-5 gpt-5-mini; do
>   echo -n "$m: "
>   curl -s -o /dev/null -w "%{http_code}\n" \
>     -X POST "https://<your-resource>.services.ai.azure.com/api/projects/proj-default/openai/v1/chat/completions" \
>     -H "Authorization: Bearer <your-key>" \
>     -H "Content-Type: application/json" \
>     --data "{\"model\":\"$m\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":4}"
> done
> ```
> 200 = deployment exists, 404 `DeploymentNotFound` = it doesn't.

API key goes into a Kubernetes Secret created **out-of-band** — never
written to disk:

```sh
kubectl -n odap-platform create secret generic nanitics-azure-foundry \
  --from-literal=AZURE_AI_FOUNDRY_API_KEY='<paste-your-key>' \
  --dry-run=client -o yaml | kubectl apply -f -
```

> **Why not in `secret.yaml`?** The committed `secret.yaml` exists only
> as a *template* showing the expected shape. It is **deliberately
> excluded from `kustomization.yaml`** — if it were a managed resource,
> every `kubectl apply -k .` would overwrite the real key with the
> placeholder. (We learned that the hard way during initial deploy.)
> For prod, replace `kubectl create secret` with External Secrets /
> Vault / a Workload Identity binding.

### 4. Make sure the dist-embed UI bundle exists

The build script copies `<nanitics-repo>/observatory/dist-embed` into
the build context. If it's stale or missing:

```sh
cd /Users/karelgoense/Documents/programming/sandbox/nanitics
just observatory-build
```

(Requires Node.js. The bundle is already committed in this repo for
convenience — usually you can skip this.)

---

## Deploy

```sh
# From repo root.
cd platform/19-nanitics-observatory

# Build the image and import it into the running k3d cluster.
./build-and-load.sh

# Apply the Kubernetes manifests (does NOT touch the Secret — see step 3 above).
kubectl apply -k .

# Watch the pod come up.
kubectl -n odap-platform get pods -l app.kubernetes.io/component=nanitics-observatory -w
```

Two browser entry points:

- <https://nanitics.odap.local:8443/chat> — chat UI to talk to agents
- <https://nanitics.odap.local:8443/api/observatory/> — trace viewer

The chat UI lets you pick an agent, type a task, and watch each tool
call / LLM call / evaluation event stream in live as the agent works.
Each run is also captured in the Observatory — there's a "open in
Observatory" link on every result.

## Observatory views

The first time you'll see an empty run list. Trigger one run per agent
type from the chat UI, or from curl:

```sh
curl -k -X POST https://nanitics.odap.local:8443/run/react \
  -H 'Content-Type: application/json' \
  -d '{"task":"Greet the UWV team in Dutch and describe the platform."}'

curl -k -X POST https://nanitics.odap.local:8443/run/rewoo \
  -H 'Content-Type: application/json' \
  -d '{"task":"Search for data lakehouse and data warehouse, summarize each, then compare in one sentence."}'

curl -k -X POST https://nanitics.odap.local:8443/run/reflexion \
  -H 'Content-Type: application/json' \
  -d '{"task":"Describe the UWV platform storage layer in at least 80 characters."}'

curl -k -X POST https://nanitics.odap.local:8443/run/lats \
  -H 'Content-Type: application/json' \
  -d '{"task":"Find the best tool to introspect the UWV platform layout. Finish with DONE."}'
```

Each call returns `{"run_id": "...", "agent_type": "...", "result": "..."}`.
Refresh the Observatory UI — the four runs appear in the run list with
distinct event signatures. Click each to compare:

- **ReAct** trace: linear span tree, one LLM call → tool → LLM call → done.
- **ReWOO** trace: plan-creation event, parallel step execution, only 2 LLM calls regardless of step count.
- **Reflexion** trace: at least one `evaluation.result`; if the first attempt fails the substantive-output check, you'll also see a `reflection.generated` event and a second attempt.
- **LATS** trace: a tree of `tree_search.node.created` / `tree_search.node.evaluated` events, `mcts.iteration` and `mcts.backpropagation` events tracking the search, and a final `tree_search.complete` summary.

---

## Platform watcher

The `watcher` agent is the platform's real-work surface. Where the four
demo agents exist to drive Observatory views, the watcher investigates
platform health signals and files Multica tasks for issues a human
should review.

### Tools

| Tool | What it does | Side effect |
|---|---|---|
| `list_firing_alerts(severity?)` | Curated list of active Alertmanager alerts with `fingerprint`, `runbook_url`, `severity` | Read-only |
| `query_prometheus(promql)` | Instant query against in-cluster Prometheus | Read-only |
| `search_opensearch_logs(query, time_range_minutes?, max_hits?)` | Lucene search over `logs-*` | Read-only |
| `recent_k8s_warnings(namespace?, since_minutes?)` | Warning-type K8s events (CrashLoopBackOff, OOMKilled, ImagePullBackOff, …) | Read-only |
| `find_existing_multica_tasks(fingerprint)` | Dedup check before filing | Read-only |
| `file_multica_task(title, body, severity, area, fingerprint)` | Create a Multica task in `platform-ops` | **Write** |

The system prompt enforces the order: **list alerts → pick the most severe →
confirm with Prometheus / logs → dedup using Alertmanager's `fingerprint` →
file at most one task**. Tasks carry the labels `watcher-filed`,
`severity:<info|warning|critical>`, `area:<workload>` and **never** carry
the `approved` label — only humans set that, and Multica's coding-agent
daemon filters on its presence. Two human gates remain in place: Multica
approval gate, and the existing PR review path.

### Trigger a run

```sh
curl -k -X POST https://nanitics.odap.local:8443/run/watcher \
  -H 'Content-Type: application/json' \
  -d '{"task":"Investigate the currently firing PrometheusRule alerts. For the most severe one, dedup against existing Multica tasks and file a new task if needed."}'
```

Or, if you want to scope the run to a specific alert:

```sh
curl -k -X POST https://nanitics.odap.local:8443/run/watcher \
  -H 'Content-Type: application/json' \
  -d '{"task":"Investigate TrinoQueryLatencyP99High. Confirm via PromQL, dedup, then file a Multica task if real."}'
```

The watcher's full trace (every Prometheus query, every dedup check,
the agent's reasoning, the task creation request) is captured by the
Observatory exactly like any other agent run.

### Dry-run vs. live mode

`MULTICA_DRY_RUN=true` (the default in `configmap.yaml`) is the safe
landing mode. In dry-run the watcher logs the Multica payload it would
have posted and returns a synthetic task_id — useful for verifying the
end-to-end loop without spamming Multica during early-life tuning.

To go live:

1. In Multica's UI, create user `platform-watcher@example.com`, add to the
   `platform-ops` workspace, and generate a long-lived API token.
2. Provision the token as a Secret (see `secret-multica.yaml`):

   ```sh
   kubectl -n odap-platform create secret generic nanitics-multica-token \
     --from-literal=MULTICA_API_TOKEN='<paste-token>' \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

3. Flip `MULTICA_DRY_RUN: "false"` in `configmap.yaml` and roll the
   deployment.

### Scheduled runs (CronJob)

`cronjob-watcher.yaml` deploys a CronJob that POSTs to `/run/watcher`
every 30 min. **It ships suspended.** Each tick costs a real Foundry
call, so the operator flips it on once dry-run output looks right:

```sh
# Inspect the dry-run loop manually first.
kubectl -n odap-platform create job --from=cronjob/nanitics-watcher-cron \
  watcher-manual-$(date +%s)
kubectl -n odap-platform logs -l job-name=watcher-manual-... --tail=200

# Once happy, enable the schedule.
kubectl -n odap-platform patch cronjob nanitics-watcher-cron \
  -p '{"spec":{"suspend":false}}'
```

The cron body lives in ConfigMap `nanitics-watcher-cron-body` — tweak
the investigation prompt by editing `body.json` and re-applying. The
CronJob has `concurrencyPolicy: Forbid`, so a long-running ReAct loop
is not overlapped by the next tick; the 30-min cadence is the natural
rate limiter rather than a hard per-day cap.

### Operator runbook — the full approval loop

This is the end-to-end flow once the watcher is live (out of dry-run and
the CronJob un-suspended):

1. **Cron tick** — every 30 min, the CronJob POSTs to `/run/watcher`.
   The agent calls `list_firing_alerts`, picks the most severe, confirms
   with Prometheus / logs / events, dedup-checks against existing
   Multica tasks, and either files a new task or reports "no issue
   found".

2. **Triage** — in Multica, filter the `platform-ops` workspace by
   label `watcher-filed`. New tasks have severity + area labels
   (`severity:critical`, `area:trino`, …) but **no `approved` label**.

3. **Decide** — open the task and read the deterministic *Approval
   checklist* at the bottom of the body (appended by the watcher, not
   the LLM):
     - Is the signal still real?
     - Is the Suggested fix appropriate scope?
     - Is the blast radius acceptable?
     - Is there an active incident that would conflict?

   If any check fails, comment on the task, optionally adjust the body,
   and **do not** add `approved`. If the issue cleared on its own,
   close the task — that information helps the next dedup pass.

4. **Approve** — add the `approved` label and assign the task to the
   coding-agent user (e.g. `claude-code@<email>`). Multica's daemon
   running on a developer laptop will claim the task; the agent runs
   inside this repo's working tree and opens a PR.

5. **Review the PR** — existing CI runs, existing review path applies.
   The watcher has *no role* past step 1 — there is no auto-merge, no
   ChatOps shortcut, no second AI involvement in the merge gate.

6. **Merge** — fix lands. Next cron tick may re-investigate the same
   fingerprint; if the symptom is gone, the agent reports "no issue
   found" and the task lifecycle is complete. If the symptom returns,
   a new task is filed (the previous one is closed and so doesn't
   dedup it away).

Two human gates by construction: the `approved` label flip, and the PR
merge. The watcher cannot bypass either.

### What's deliberately not in this build

- **No autonomous fixes** — the watcher only writes Multica tasks. Every
  change to the platform still goes through `human approves Multica task
  → coding agent opens PR → human merges PR`. Two human gates by design.
- **No K8s write verbs** — the ClusterRole in `rbac.yaml` grants only
  `events: get/list/watch`. The watcher cannot mutate cluster state.
- **No hard per-day task cap** — the cron interval is the rate limiter.
  If a tight budget becomes necessary, have `file_multica_task` consult
  Multica for "tasks filed by me in last 24h" and short-circuit.
- **No distributed traces** — Tempo (slice 3) is intentionally deferred;
  logs + metrics + events get ~80% of the signal.

### Multica API caveat

The exact request shape for Multica's task-create + task-search endpoints
is centralised in `_build_task_payload` and the params dict of
`find_existing_multica_tasks` in [`app/watcher.py`](app/watcher.py). When
the live Multica integration is wired up (transition out of `MULTICA_DRY_RUN`),
those two spots may need adjustment to match the actual API. The
`# NOTE:` comment in `find_existing_multica_tasks` flags the dedup
parameter specifically.

---

## Switching to a real LLM vs. mock

The pod ships configured for `LLM_PROVIDER=azure-foundry`. To smoke-test
without burning Azure credits, override at deploy time:

```sh
kubectl -n odap-platform set env deploy/nanitics-observatory LLM_PROVIDER=mock
```

The mock provider is a scripted two-turn ReAct response — useful for
verifying the trace pipeline works before wiring real keys.

To switch back:

```sh
kubectl -n odap-platform set env deploy/nanitics-observatory LLM_PROVIDER=azure-foundry
```

---

## Day-2 ops

| Action | Command |
|---|---|
| Tail logs | `kubectl -n odap-platform logs -f deploy/nanitics-observatory` |
| Restart after secret change | `kubectl -n odap-platform rollout restart deploy/nanitics-observatory` |
| Port-forward (if ingress is broken) | `kubectl -n odap-platform port-forward svc/nanitics-observatory 8001:80` then visit <http://localhost:8001/api/observatory/> |
| Health check | `curl -k https://nanitics.odap.local:8443/health` |
| Tear down | `kubectl delete -k .` |

---

## How it fits the platform

```
                  Browser                      curl / portal
                     │                              │
                     ▼                              ▼
            ┌──────────────────────────────────────────────┐
            │        nginx-ingress (cert-manager TLS)      │
            └──────────────────────────────────────────────┘
                                  │
                                  ▼
            ┌──────────────────────────────────────────────┐
            │  nanitics-observatory pod (odap-platform ns)  │
            │  ┌────────────────────────────────────────┐  │
            │  │ FastAPI                                │  │
            │  │  ├─ /api/observatory/  (React bundle)  │  │
            │  │  ├─ /api/observatory/runs/...  (REST)  │  │
            │  │  ├─ /api/observatory/runs/{id}/stream  │  │
            │  │  │   (SSE — live trace updates)        │  │
            │  │  ├─ /run     → ReActAgent demo         │  │
            │  │  └─ /health                            │  │
            │  └────────────────────────────────────────┘  │
            │           │                                  │
            │           ▼                                  │
            │     OpenAILLMClient(base_url=<foundry>)      │
            └──────────────────────────────────────────────┘
                          │ HTTPS
                          ▼
            ┌──────────────────────────────────────────────┐
            │   Azure AI Foundry (/openai/v1/...)          │
            └──────────────────────────────────────────────┘
```

The `TracedExecutor` writes events to an in-memory
`PersistentTraceStore`. For durable storage across pod restarts, swap
in `PostgresTraceStore` (a separate Postgres deployment is needed; see
[Adding durable trace storage](#adding-durable-trace-storage) below).

---

## Customising the demo agents

`app/app.py` currently exposes five toy tools (`greet`,
`describe_platform`, `search`, `summarize`, `analyze`) wired into four
agent types. To make this useful for your platform, replace the toy
tools with ones that call the actual services:

```python
@tool("query_trino", "Run a read-only SQL query against the data warehouse.")
async def query_trino(sql: str) -> str:
    # connect to trino-coordinator.odap-data:8080 internally
    ...

@tool("trigger_airflow_dag", "Trigger an Airflow DAG by id.")
async def trigger_airflow_dag(dag_id: str, conf: dict) -> str:
    # call airflow.odap-platform internally
    ...
```

Then add them to the `ReActAgent(tools=[...])` list in `app.py`.

> **Wrap destructive tools with `ApprovalGate`.** See
> [`examples/hitl/approval_gate.py`](https://github.com/nanitics/nanitics/blob/main/examples/hitl/approval_gate.py)
> in the SDK repo. You don't want an agent dropping a Hive table.

---

## Variant: deployment-style Azure OpenAI via LiteLLM

If your endpoint shape is
`https://<resource>.openai.azure.com/openai/deployments/<deployment>/chat/completions?api-version=...`,
the OpenAI Python SDK can't call it directly. Two options:

1. **Migrate to a Foundry "v1" endpoint** (recommended; same models,
   OpenAI-compatible URL).
2. **Use LiteLLM** as a translator. Add `nanitics[litellm]` to the
   Dockerfile and switch `app.py` to:

   ```python
   from nanitics import LiteLLMClient
   client = LiteLLMClient(model="azure/<deployment-name>")
   # set env vars: AZURE_API_KEY, AZURE_API_BASE, AZURE_API_VERSION
   ```

   The ConfigMap/Secret keys change to `AZURE_API_*`. LiteLLM handles
   the deployment-style URL transparently.

---

## Adding durable trace storage

The default `InMemoryPersistentTraceStore` loses everything on pod
restart. To upgrade:

1. Deploy a small Postgres in `odap-platform` (or reuse an existing
   one — check what `05-hive-metastore` already runs).
2. Install the `nanitics[postgres]` extra in the Dockerfile.
3. In `app.py`, replace:
   ```python
   from nanitics import PostgresTraceStore
   store = PostgresTraceStore(dsn=os.environ["TRACE_DB_DSN"])
   await store.bootstrap_schema()
   ```
4. Add the DSN to the ConfigMap (host) and the password to the Secret.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `ERR_CERT_AUTHORITY_INVALID` in browser | cert-manager hasn't issued the cert yet. Check `kubectl -n odap-platform get certificate nanitics-observatory-tls`. |
| `502 Bad Gateway` | Pod not ready. `kubectl logs` it; check the readiness probe at `/health`. |
| `/run` returns 500 with `LLMProviderError: 404 DeploymentNotFound` | `LLM_MODEL` doesn't match a deployment in your Foundry project. Probe with the curl loop in step 3 to find a working name. |
| `/run` returns 500 with `LLMProviderError: 401 invalid subscription key` | Either the secret is missing/wrong, OR somebody re-applied the placeholder via kustomize. Run the `kubectl create secret` from step 3 again. |
| UI shows fallback page instead of React app | `observatory-ui/` wasn't synced. Re-run `./build-and-load.sh`. |
| Run list is empty after `/run` succeeded | Browser cached an old page; hard-refresh. SSE stream and run list both proxy through the same ingress. |

---

## Security notes

- The Observatory UI has **no built-in auth**. The ingress is
  reachable from anything that can resolve `nanitics.odap.local`
  — fine on a developer laptop, not fine in shared environments.
  For a shared cluster, put it behind the same `oauth2-proxy` sidecar
  pattern as `15-portal/`.
- Tool inputs/outputs are recorded verbatim in the trace store. If
  you add tools that touch PII or secrets, implement a `RedactionHook`
  (see SDK observability guide) before exposing the UI.
- The Azure key sits in a vanilla K8s `Secret` — base64, not
  encrypted at rest unless you've configured KMS encryption on the
  k3d datastore. Use Vault/External Secrets for anything beyond local
  dev.
