# 18 — Multica daemon (in-cluster)

Runs the **Multica agent-runtime daemon** as a Kubernetes Deployment, so
approved Multica tasks get claimed and executed in-cluster instead of
on a developer's laptop. The daemon image bundles the OpenAI **Codex**
CLI configured to drive the existing Azure AI Foundry deployment
(`gpt-5.4-nano` by default).

> **Status: dev-only.** Single replica, single coding-agent CLI
> (Codex), no GitHub credentials wired (cannot push PRs yet). Use this
> layer to verify the claim → run → log loop end-to-end; promote to
> production by adding a GitHub App credential, ResourceQuota, and a
> ServiceMonitor.

---

## How this differs from `17-multica`

| | **17 — Multica server** | **18 — Multica daemon** |
|---|---|---|
| Role | Coordinator (REST API, task store, UI) | Claimant (polls server, runs coding agent per task) |
| Pods | `multica-backend`, `multica-frontend`, `multica-postgres`, `multica-oauth2-proxy` | `multica-daemon` |
| Outbound calls | None to LLM providers | Foundry (via Codex), GitHub (future) |
| Image | Upstream `ghcr.io/multica-ai/*` | Locally built `odap/multica-daemon:dev` |
| Auth to server | n/a (it IS the server) | Bootstrap PAT (`mul_...`) → stored in workspace PVC |

The upstream design assumes daemons run on developer laptops. This
deployment is a deliberate divergence: the watcher in
[`19-nanitics-observatory`](../19-nanitics-observatory/) files tasks
into Multica, humans approve them, and now those approvals get claimed
and executed without any laptop in the loop.

---

## Layout

```
platform/20-multica-daemon/
├── README.md                 ← this file
├── Dockerfile                ← multica CLI + Codex + git on Node 20 / Debian slim
├── codex-config.toml         ← Azure Foundry provider config baked into the image
├── entrypoint.sh             ← configure server URL, login with PAT, daemon start
├── build-and-load.sh         ← build + k3d import helper
├── kustomization.yaml        ← kustomize entry point (excludes secret-token.yaml)
├── deployment.yaml           ← single-replica Recreate Deployment
├── workspace-pvc.yaml        ← 10Gi RWO PVC for ~/.multica + ~/.codex + repos
└── secret-token.yaml         ← TEMPLATE for the bootstrap PAT (out-of-band)
```

---

## One-time setup

### 1. Confirm the prereqs

- **Foundry secret** — the daemon's Codex inherits `AZURE_OPENAI_API_KEY`
  from the existing `nanitics-azure-foundry` Secret (key
  `AZURE_AI_FOUNDRY_API_KEY`). If you already set that up for the
  watcher in `19-nanitics-observatory`, you're done.
- **Multica server** — `multica-backend.odap-platform:80` must answer.
  `kubectl -n odap-platform get pods -l app.kubernetes.io/component=multica`
  should list four Running pods.

### 2. Build the image and import into k3d

```sh
cd platform/20-multica-daemon
./build-and-load.sh
```

That tags `odap/multica-daemon:dev` and imports it via
`k3d image import`. The first build pulls Node 20 base + `@openai/codex`
from npm; subsequent builds are layer-cached.

### 3. Mint a Personal Access Token in Multica

Open <https://multica.odap.local:8443/> in a browser, log in
(email-code flow against `karelgoense@gmail.com` for the dev cluster),
then **Settings → Personal Access Tokens → Create**. The token starts
with `mul_`. Copy it.

> **Identity matters.** The daemon will act as whoever this PAT
> belongs to. For production, create a dedicated `multica-daemon@example.com`
> user with claim rights restricted to the `platform-ops` workspace.
> For dev, your own user is fine.

### 4. Provision the Secret + apply

```sh
kubectl -n odap-platform create secret generic multica-daemon-auth \
  --from-literal=MULTICA_API_TOKEN='mul_<paste>' \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -k platform/20-multica-daemon
kubectl -n odap-platform rollout status deploy/multica-daemon
```

The daemon should reach **1/1 Running** within ~20s. The first boot
runs `multica login --token` against the PAT; subsequent restarts
reuse `~/.multica/auth.json` on the workspace PVC.

---

## Verify the loop

### a. Daemon is talking to the server

The pod log should end with `multica daemon starting` and then go
quiet (the daemon polls the server in the background; it doesn't log
heartbeats by default). Confirm it registered a runtime with the
server:

```sh
kubectl -n odap-platform exec deploy/multica-daemon -- multica runtime list
```

You should see one runtime keyed by this Pod's hostname.

### b. Codex can call Foundry

```sh
kubectl -n odap-platform exec deploy/multica-daemon -- \
  codex exec --skip-git-repo-check --model "$MULTICA_CODEX_MODEL" \
  "Reply with exactly the two characters: OK"
```

Expected: `OK`, with `provider: azure` and `model: gpt-5.4-nano` in
the trailing metadata. A 401 here means the Foundry key Secret is
stale; a 404 means `MULTICA_CODEX_MODEL` doesn't match a deployment
in your Foundry project.

### c. End-to-end: watcher → task → approval → daemon → codex

1. Trigger the watcher (`POST /run/watcher` on the Nanitics
   Observatory) to file a Multica task. While `MULTICA_DRY_RUN=true`
   on the watcher the payload is logged only — flip to `"false"` in
   the watcher's ConfigMap once `nanitics-multica-token` is set,
   then re-trigger.
2. In Multica's UI, find the new task in the `platform-ops`
   workspace, review the body, and add the **`approved`** label.
3. The daemon's poll loop notices the label, claims the task, and
   spawns codex with the task body as the prompt. The output appears
   in the task's comment thread.

---

## Day-2 ops

| Action | Command |
|---|---|
| Tail logs | `kubectl -n odap-platform logs -f deploy/multica-daemon` |
| Restart after PAT rotation | `kubectl -n odap-platform exec deploy/multica-daemon -- multica auth logout && kubectl -n odap-platform rollout restart deploy/multica-daemon` |
| Inspect Codex scratch | `kubectl -n odap-platform exec deploy/multica-daemon -- ls ~/.codex/.tmp` |
| Disk usage by task | `kubectl -n odap-platform exec deploy/multica-daemon -- multica daemon disk-usage` |
| Pause claims (preserve state) | `kubectl -n odap-platform scale deploy/multica-daemon --replicas=0` |
| Resume | `kubectl -n odap-platform scale deploy/multica-daemon --replicas=1` |
| Wipe (forces re-login on next boot) | `kubectl -n odap-platform delete pvc multica-daemon-workspace` (delete the deploy first) |

---

## Caveats and not-done

- **No GitHub credential.** The daemon can clone public HTTPS repos
  but cannot push. To open a PR from an approved task, mount a
  GitHub App credential (or a fine-grained PAT) into the workspace
  and add a `[github]` section to `~/.codex/config.toml`. Out of
  scope for this slice.
- **One coding-agent CLI.** Only Codex is installed. If a Multica
  task is assigned to Claude Code, the daemon will report
  `agent not available`. Adding Claude Code means baking
  `@anthropic-ai/claude-code` (npm) into the image and provisioning
  an `ANTHROPIC_API_KEY` Secret.
- **Single replica.** Daemons are not horizontally scalable in the
  upstream design — each one claims tasks independently. Scaling to
  2+ replicas risks duplicate claims. If throughput becomes a
  problem, use Multica's workspace partitioning instead.
- **PAT-to-PVC coupling.** The first successful `multica login` is
  cached on the workspace PVC. Rotating the Secret alone does NOT
  re-auth the daemon; you must `multica auth logout` (or delete the
  PVC) first. The Day-2 table above has the recipe.
- **kubelet-proxy fragility (k3d dev).** If `kubectl exec` /
  `kubectl logs` return 502, read container logs via
  `docker exec <node> sh -c 'find /var/log/pods -name "*.log" ...'`.
  This is a known k3d-after-sleep issue, not a daemon issue.
