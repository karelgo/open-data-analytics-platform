# om-access-bridge

Brug tussen **OpenMetadata** (Tasks / Request Access) en **Keycloak**
(realm-roles) — onderdeel van [ADR-0008](../../docs/adr/0008-self-service-data-access.md).

## Hoe het werkt

```
 OpenMetadata           om-access-bridge          Keycloak
 ─────────────          ────────────────          ────────
   user X klikt
   "Request Access"
   op Dataset Y
        │
        ▼
   Task aangemaakt
        │
   Reviewer approve't
        │
        ▼
   EventSubscription ──►  POST /webhooks/om  ──► realm-role
   (HMAC-signed)          parse(task.about)       data_access:<cat>.<schema>
                          → user + role           toegekend aan user X
                                                      │
                                                      ▼
                                                 next JWT bevat
                                                 nieuwe rol → OPA
                                                 ziet de grant
```

OPA-Rego (zie [trino-data-access.rego](../../opa-policies-src/trino/trino-data-access.rego))
accepteert een `data_access:<catalog>.<schema>` rol als geldige grant en
laat de bijbehorende purposes uit `resource_purposes` automatisch toe.

## Endpoints

| Method | Path                     | Doel |
|---|---|---|
| GET    | `/health`                | liveness/readiness |
| POST   | `/webhooks/om`           | OM EventSubscription target (HMAC-signed) |
| POST   | `/replay/{task_id}`      | manuele her-toepassing bij gemiste webhook |

## Build + deploy (lokaal k3d)

```bash
./build-and-load.sh

# Bootstrap secrets (eenmalig — zie secret.yaml voor uitleg):
kubectl -n odap-platform create secret generic om-access-bridge-secret \
  --from-literal=KEYCLOAK_CLIENT_SECRET='<...>' \
  --from-literal=OM_WEBHOOK_SECRET='<32-bytes-random>' \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -k .
```

## OM EventSubscription configureren

Eén keer per cluster. Vanuit een pod met OM-token:

```bash
curl -X POST http://openmetadata.odap-meta.svc.cluster.local:8585/api/v1/events/subscriptions \
  -H "Authorization: Bearer ${OM_JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "om-access-bridge",
    "alertType": "Notification",
    "subscriptionType": "Generic",
    "subscriptionConfig": {
      "endpoint": "http://om-access-bridge.odap-platform.svc.cluster.local/webhooks/om",
      "secretKey": "<must match OM_WEBHOOK_SECRET>"
    },
    "filteringRules": {
      "resources": ["task"],
      "rules": [{ "name": "matchAnyEventType", "effect": "include", "arguments": ["taskResolved"] }]
    }
  }'
```

## Smoke

```bash
make smoke   # roept tests/smoke/10-om-access-bridge.sh aan
```

Of geïsoleerd via:

```bash
bash tests/smoke/10-om-access-bridge.sh
```

## Security model

- **HMAC-SHA256** about the raw body met header `X-OM-Signature: sha256=<hex>`
  en `X-OM-Timestamp` (unix-seconds). Replay-window ±300s.
- **Replay-set** in memory voorkomt dubbele grants per `task.id`.
- Service-account in Keycloak heeft alleen `manage-users` + `view-realm` —
  geen client-admin rechten.
- ConfigMap is plain; alle geheimen in `om-access-bridge-secret` (idealiter
  externe Secret-store, zie `infrastructure/`-roadmap).
