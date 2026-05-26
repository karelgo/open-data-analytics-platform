# 17 — Multica

Deploys [Multica](https://github.com/multica-ai/multica) — a coordination
server for **coding** agents (Claude Code, Codex, Copilot CLI, Cursor,
Gemini, Kimi, Kiro CLI, …) — alongside the platform.

> **Status: exploratory** (branch `feat/multica-explore`). Not wired into
> `make deploy-platform` yet. Verified by running the upstream
> `docker-compose.selfhost.yml` locally; this directory is the
> Kubernetes adaptation.

---

## How this differs from `19-nanitics-observatory`

Both are agent-flavoured, but they sit in different lanes — so they
coexist cleanly rather than compete.

|                | **16 — Nanitics Observatory**                       | **17 — Multica**                                   |
|----------------|------------------------------------------------------|----------------------------------------------------|
| Lane           | Runtime / inside-the-platform                        | Dev-loop / build-time                              |
| What runs      | One pod: FastAPI + Nanitics SDK                      | Three pods: Postgres (pgvector), Go backend, Next.js frontend |
| Where agents run | In-cluster (the SDK *is* the agent runtime)        | **On developer laptops** — server only coordinates |
| LLM            | Azure AI Foundry endpoint                            | None server-side; laptop daemons call their own model |
| Use-case       | "Build a `query_trino` tool, watch the span tree"    | "Assign a dbt-PR task to Claude Code, track progress" |

The natural workflow ties them together: assign a Multica task to a
coding agent → it edits `platform/19-nanitics-observatory/app/app.py` →
new agent runs are visible in the Nanitics UI. **One builds, the other
observes.** See `docs/explorations/multica-vs-nanitics.md` (this branch)
for the full design memo.

---

## Layout

```
platform/17-multica/
├── README.md                       ← this file
├── kustomization.yaml              ← excludes secrets.template.yaml on purpose
├── uploads-pvc.yaml                ← PVC for backend attachment uploads
├── postgres.yaml                   ← StatefulSet + headless Service (pgvector/pgvector:pg17)
├── backend-config.yaml             ← non-sensitive env (PORT, METRICS_ADDR, CORS, …)
├── backend.yaml                    ← Deployment + ClusterIP Service + metrics Service
├── frontend.yaml                   ← Deployment + ClusterIP Service (Next.js 16)
├── configmap-oauth2-proxy.yaml     ← oauth2-proxy config — front-door SSO via Keycloak
├── secret-oauth2-proxy.yaml        ← dev-only client-secret + cookie-secret (committed; Mirror of 15-portal)
├── oauth2-proxy.yaml               ← oauth2-proxy Deployment + Service (separate, multi-upstream)
├── ingress.yaml                    ← multica.odap.local — alles via oauth2-proxy
└── secrets.template.yaml           ← TEMPLATE — postgres + backend secrets, apply out-of-band
```

---

## Architecture decisions (and their motivation)

### Dedicated Postgres, not shared with the platform's operators

Multica's migrations expect `pgvector/pgvector:pg17` — the extension
isn't enabled by default but the upstream client checks for its
availability at boot. The cluster's existing Postgres images (Hive
Metastore, OpenMetadata, Keycloak, Airflow, Superset) don't bundle
pgvector. Cleanest path: run a single-replica StatefulSet of the
upstream image in the same `odap-platform` namespace. Production
upgrade path: CloudNativePG with a pgvector-enabled image, plus
replicas.

Side benefit: agent / issue / chat data stays its own data domain.
Easier compliance scoping (AVG art. 35, AI Act lineage).

### Single ingress, path-based routing

Upstream docs offer two reverse-proxy patterns:

1. **Two hosts** — `app.example.com` for frontend, `api.example.com` for backend.
2. **Single host with `/ws` location to backend** — exact Nginx example in `SELF_HOSTING_ADVANCED.md`.

We picked (2). Better UX (one bookmark), fewer cert-manager certs,
fewer `/etc/hosts` entries. The browser hits
`multica.odap.local:8443`; the ingress routes `/api`,
`/auth`, `/uploads`, `/ws`, `/health`, `/readyz` to the backend; `/`
to the frontend.

### oauth2-proxy in front of Multica — front-door SSO only

Multica has no native OIDC. We use the same oauth2-proxy + Keycloak
pattern as [15-portal](../15-portal/), but **only gate the Next.js
bundle** (path `/`). All API + auth + WebSocket paths bypass
oauth2-proxy:

```
skip_auth_routes = ["^/api/", "^/auth/", "^/ws", "^/uploads/", "^/health", "^/readyz"]
```

Why: Multica's daemon path (`/api/daemon/*`, `/ws`) authenticates with
its own JWT. The browser-side API calls (`/api/*`) use Multica's own
session cookie. Multica's email-code login (`/auth/*`) must keep
working for users to actually log in *into* Multica. Putting
oauth2-proxy in front of all of those would either break the daemon or
require a Keycloak-cookie ↔ Multica-JWT bridge.

**Effect**: random network users can't even *see* the Multica UI —
they hit Keycloak first. Once authenticated, they still need a
one-time email-code login for Multica's own user model (codes printed
to backend logs since `RESEND_API_KEY` is empty). This is "front-door
SSO," not full SSO.

**Full SSO (future)** requires either upstream Multica adding OIDC, or
a custom user-provisioning bridge that consumes the
`X-Forwarded-Email` header oauth2-proxy sets and auto-creates the
Multica user. Out of scope for now — see
[`docs/explorations/multica-vs-nanitics.md`](../../docs/explorations/multica-vs-nanitics.md).

### Storage: PVC for uploads in v1, MinIO bucket in v2

`backend-uploads` is a PVC (5 GiB). Switching to MinIO is a one-line
change (`S3_BUCKET=multica` in `backend-config.yaml` + bucket
provisioning) — done in v2 after the rest of the deployment shakes
out.

### Metrics enabled but not exposed externally

`METRICS_ADDR=0.0.0.0:9090` is on. Upstream docs say literally "do not
expose this endpoint through the public app/API ingress" — so the
metrics port has its own ClusterIP-only Service `multica-backend-metrics`
with `prometheus.io/scrape` annotations, not in `ingress.yaml`.

### Known limitation: WebSocket needs a custom-built web image

`NEXT_PUBLIC_WS_URL` is a build-time variable, baked at image build into
the Next.js bundle. The official `ghcr.io/multica-ai/multica-web:latest`
image bakes in `ws://localhost:8080/ws`, which won't work from a browser
hitting `multica.odap.local:8443`.

**Effect on v1**: HTTP works (Next.js rewrites `/api`, `/auth`, `/uploads`
at request time inside the frontend container). Real-time features
(chat streaming, live issue updates, daemon status) **fail to connect**.

**v2 fix**: mirror `19-nanitics-observatory/build-and-load.sh` — clone
multica, run `docker compose -f docker-compose.selfhost.build.yml build`
with `NEXT_PUBLIC_WS_URL=wss://multica.odap.local:8443/ws`, push
to the local k3d registry, swap the `image:` field in `frontend.yaml`.

---

## One-time setup

### 1. Add the hostname to `/etc/hosts`

```sh
echo "127.0.0.1 multica.odap.local" | sudo tee -a /etc/hosts
```

(Same `:8443` quirk as the rest of the platform — k3d serverlb maps
`host:8443 → cluster:443`.)

### 2. Create the secrets out-of-band

```sh
PG_PW=$(openssl rand -hex 24)

kubectl -n odap-platform create secret generic multica-postgres \
  --from-literal=POSTGRES_PASSWORD="$PG_PW" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n odap-platform create secret generic multica-backend \
  --from-literal=JWT_SECRET=$(openssl rand -hex 32) \
  --from-literal=DATABASE_URL="postgres://multica:${PG_PW}@multica-postgres:5432/multica?sslmode=disable" \
  --dry-run=client -o yaml | kubectl apply -f -
```

These secrets are **not** managed by kustomize (`*-secret.yaml` files
are templates only) — same anti-clobber pattern as
`19-nanitics-observatory/secret.yaml`.

### 3. Apply the manifests

```sh
cd platform/17-multica
kubectl apply -k .
kubectl -n odap-platform get pods -l app.kubernetes.io/component=multica -w
```

Open <https://multica.odap.local:8443/>.

### 4. Log in

Without `RESEND_API_KEY`, verification codes print to the backend log:

```sh
kubectl -n odap-platform logs -f deploy/multica-backend | grep -i 'verification code'
```

Enter your email at the login page — copy the code from the log.
This is fine for a dev cluster; for any shared environment, set
`RESEND_API_KEY` in the backend Secret or move to oauth2-proxy (v2).

### 5. (Per developer) Install the CLI + start the daemon

The Multica server only coordinates — agents run on the developer's
laptop. Each user installs the CLI and points it at the cluster:

```sh
brew install multica-ai/tap/multica
multica config set server_url https://multica.odap.local:8443
multica config set app_url https://multica.odap.local:8443
multica login
multica daemon start
```

(See upstream `SELF_HOSTING.md` step 3 for the full agent-CLI list.)

### 5a. (Optional) Point `codex` at Azure AI Foundry

Multica's server doesn't speak LLM — each agent CLI talks to its own
provider. To run codex against your Foundry deployment instead of
OpenAI's hosted API:

```sh
export AZURE_OPENAI_API_KEY="<your-foundry-key>"
export MULTICA_CODEX_MODEL=gpt-4o     # or whatever you deployed
multica daemon start
```

Codex picks the provider up from your existing `~/.codex/config.toml`
(`model_provider = "azure"`); `MULTICA_CODEX_MODEL` overrides the
per-task model. Verified end-to-end against `gpt-4o` —
[full memo in `docs/explorations/multica-foundry.md`](../../docs/explorations/multica-foundry.md).
Same trick won't work for Claude / Gemini / Cursor — those CLIs don't
have a swap-base_url hook.

---

## Day-2 ops

| Action | Command |
|---|---|
| Tail backend logs | `kubectl -n odap-platform logs -f deploy/multica-backend` |
| Restart after config change | `kubectl -n odap-platform rollout restart deploy/multica-backend deploy/multica-frontend` |
| Port-forward (if ingress is broken) | `kubectl -n odap-platform port-forward svc/multica-frontend 3000:80` |
| Health check | `curl -k https://multica.odap.local:8443/readyz` |
| Postgres shell | `kubectl -n odap-platform exec -it multica-postgres-0 -- psql -U multica -d multica` |
| Tear down | `kubectl delete -k .` (does not delete the PVCs — `kubectl delete pvc -l app.kubernetes.io/component=multica`) |

---

## Open work (v2 candidates)

1. **Custom-built web image** with `NEXT_PUBLIC_WS_URL` baked in → enables real-time features. Add `build-and-load.sh` mirroring the nanitics script.
2. **MinIO-backed S3 uploads** — `S3_BUCKET=multica`, bucket provisioning in `infrastructure/`, drop the PVC.
3. **oauth2-proxy + Keycloak** — only after deciding whether the dual-auth weight is worth it vs. pushing for upstream OIDC support.
4. **Vector logging** — wire backend stdout to the cluster's Vector → OpenSearch pipeline (audit trail of agent task assignments).
5. **Portal card** — add Multica next to Nanitics in `portal/src/data/components.ts` under a new `agents` stage. (Done in this branch.)
6. **Compliance memo** — extend `docs/compliance-mapping.md` with both Multica and Nanitics under AI Act art. 50 / Annex III scoping.
