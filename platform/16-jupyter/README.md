# platform/16-jupyter — ODAP Lab (Jupyter notebooks)

Een Databricks/Microsoft-Fabric-stijl notebook-omgeving die binnen het
platform draait. Reachable op **`https://jupyter.odap.local:8443`**
na `make deploy-platform`.

## Wat zit erin

| Stuk | Wat | File |
|---|---|---|
| RBAC | ServiceAccount + Role voor KubeSpawner (mag Pod/PVC/Service in `odap-platform` aanmaken) | [`namespace-rbac.yaml`](namespace-rbac.yaml) |
| Hub config | `jupyterhub_config.py` — OAuthenticator (Keycloak), KubeSpawner, per-user env | [`configmap-jupyterhub.yaml`](configmap-jupyterhub.yaml) |
| Hub-DB | SQLite-PVC voor user/spawn state | [`pvc-hub-db.yaml`](pvc-hub-db.yaml) |
| Deployment | Hub + configurable-http-proxy in één pod | [`deployment-hub.yaml`](deployment-hub.yaml) |
| Service | `jupyter` (extern, port 80) + `hub` (intern, port 8081) | [`service.yaml`](service.yaml) |
| Ingress | `jupyter.odap.local` met WS-proxy | [`ingress.yaml`](ingress.yaml) |
| Secret | OIDC client-secret + configproxy-token | [`secret.yaml`](secret.yaml) |
| NetworkPolicy | Wat de Hub en singleuser-pods mogen | [`networkpolicy.yaml`](networkpolicy.yaml) |
| Starter notebooks | Pre-loaded onboarding-notebooks (welcome / trino / delta / minio / OM / git) | [`starter-notebooks/`](starter-notebooks/) |

## Architectuur

```
                  ┌──────────────────────────────────┐
Browser ──┐       │  jupyter.odap.local:8443 │
          │ TLS   │                                  │
          ▼       │   ingress-nginx                  │
┌─────────────────┴───────┐
│  Service `jupyter` :80  │
│  → configurable-http-   │
│    proxy :8000          │
└─────────┬───────────────┘
          │ HTTP
          ▼
┌──────────────────────────────────────────────────┐
│  Pod `jupyterhub` (in odap-platform)              │
│  ┌──────────┐         ┌──────────────────────┐   │
│  │ proxy    │ ◄────── │ JupyterHub :8081     │   │
│  │ :8000    │   set   │  - OAuthenticator    │   │
│  └──────────┘  route  │  - KubeSpawner       │   │
└────────────────────────┬─────────────────────┘   │
         │ create        │                          │
         ▼               ▼                          │
┌────────────────────┐  ┌───────────────────────┐  │
│ PVC jupyter-<u>    │  │ Pod jupyter-<username>│  │
│ ~/work/            │◄─┤ JupyterLab + odap_lab  │  │
└────────────────────┘  │ env: TRINO_/S3_/HMS_  │  │
                        └───────┬───────────────┘  │
                                │                   │
       ┌─────────┬──────────────┼─────────────┬─────┴──┐
       ▼         ▼              ▼             ▼        ▼
     Trino    MinIO/S3      HMS Thrift   OpenMetadata  Kafka
```

- **OAuthenticator** redirecte de browser naar de externe Keycloak-URL
  (zelfde split-URL truc als de portal's oauth2-proxy: extern URL voor de
  browser, intern Service-DNS voor token-redemption).
- **KubeSpawner** maakt per gebruiker een Pod aan op basis van
  `odap/jupyter-kernel:dev`. Een init-container kopieert de starter
  notebooks naar `~/work/starter/` op eerste spawn.
- **OPA-binding**: het notebook-pod krijgt `TRINO_USER = preferred_username`.
  Iedere Trino-query gaat dus onder de Keycloak-identiteit van de gebruiker
  langs OPA; geen extra policy-laag.

## Image bouwen

Het singleuser-image (kernel + odap_lab helper + jupyterlab-git) wordt buiten
de Kustomize-bundle gebouwd:

```bash
make jupyter-image
# of:
docker build -t odap/jupyter-kernel:dev \
  -f infrastructure/jupyter/kernel-python/Dockerfile .
k3d image import odap/jupyter-kernel:dev -c odap-platform
```

## Deploy

```bash
make deploy-platform
```

Of alleen deze laag (mits keycloak + minio + trino al draaien):

```bash
kubectl apply -k platform/16-jupyter/
```

## Login-flow

1. Browser → `https://jupyter.odap.local:8443`
2. JupyterHub redirect naar Keycloak (`jupyter` client).
3. Na succesvolle login → KubeSpawner maakt `jupyter-<username>` Pod aan
   met een fresh PVC `jupyter-<username>` (1 GiB, gerecycled bij user-stop).
4. JupyterLab opent met `starter/` voorbeelden + `work/` als root.

## Smoke

```bash
bash tests/smoke/12-jupyter-up.sh
```

## Bekende issues

- **Eerste spawn duurt 60-120 s** — pod moet de kernel-image pullen (lokaal
  uit k3d-cache na `make jupyter-image`) en de init-container moet
  notebooks kopiëren.
- **OAuthenticator + TLS verify**: de Hub praat `http://` naar Keycloak via
  het in-cluster Service. Browser ziet de externe HTTPS-URL. Issuer-claim
  blijft de externe URL (Keycloak draait met `proxy: edge`).
- **Trino-cluster heeft authentication: []**. Dat betekent dat ook
  notebook-cellen Trino kunnen aanspreken zonder password — de
  identiteit komt uit `X-Trino-User`, en OPA enforced de rest.
  Productie-overlay moet authenticatie aanzetten.
- **NetworkPolicy bewust uitgeschakeld op deze laag.** K3s's ingebouwde
  `kube-network-policies`-controller heeft cross-node visibility-gaps in
  deze k3d-topologie: de controller op de Hub-node kan niet altijd
  resolven uit welke namespace een binnenkomend ingress-nginx pakket
  komt, waardoor ~⅔ van de browser-requests `502 Connection refused`
  krijgen afhankelijk van welke ingress-nginx-replica de request
  afhandelt. De portal-laag draait om dezelfde reden zonder
  NetworkPolicy. Productie moet de policy terug aanzetten op een CNI met
  betrouwbare cross-node enforcement (Cilium / Calico / kube-router
  daemonset-mode).
- **Hub vermijdt de control-plane node.** `local-path-provisioner` pint de
  Hub-DB PV aan de node waar hij wordt geprovisioneerd; dezelfde k3d
  build heeft daarnaast onvoorspelbare pod-naar-pod routing van/naar
  de server-node. Een `nodeAffinity` blokkeert daarom scheduling op
  `node-role.kubernetes.io/control-plane`. Bij een verse cluster zonder
  agent-nodes (single-node k3d) moet die affinity worden verwijderd.
- **`crypt-key` in `secret.yaml` is dev-only.** De Fernet-key encrypt de
  per-user OAuth auth-state (access token). Geldige waarde = 64 hex chars.
  Roteer in productie via SealedSecret/SOPS/Vault — niet committen.
- **PyPI / GitHub egress** uit de notebook-pods is open. Air-gapped overlay
  moet die NetworkPolicy aanscherpen + een interne PyPI-mirror toevoegen.
