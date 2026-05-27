# 12-superset

Apache Superset (BI) via Stackable's SupersetCluster CRD.

| Resource | Doel |
|---|---|
| `SupersetCluster superset` | Superset 4.1.1, 1 node, Postgres-backend, OIDC via Keycloak. |
| `ConfigMap superset-init-script` | Python-script voor post-deploy init. |
| `Job superset-init` | Registreert Trino als database, maakt datasets voor UC-01/04/05/06/07. |

## OIDC

Stackable's AuthenticationClass `keycloak` koppelt Superset aan Keycloak.
Mock-rollen (`data_steward`, `claims_analyst`, etc.) komen mee via `userRegistration`.
Superset's role-mapping doet dit automatisch op login (`syncRolesAt: Login`).

ODAP roles → Superset-rollen mapping is **default**: alle nieuwe users krijgen
`Public` (geen rechten). Een admin moet handmatig promoten naar `Alpha`/`Gamma`/`Admin`.
Production: pas de `customRoles` block toe in de AuthenticationClass.

## Trino-database

De init-Job registreert Trino met SQLAlchemy URI:
```
trino://smoketest:<pw>@trino-coordinator.odap-platform.svc.cluster.local:8443/bronze?protocol=https&verify=false
```

Default-catalog is `bronze`; via SQL Lab kunnen users `silver.*` en `gold.*`
queries draaien. Production: aparte connection per catalog (`bronze`, `silver`,
`gold`, `sensitive`) met fijnmazige RBAC.

## Datasets

De init-Job maakt 6 datasets aan:
- `gold.uc01_claims_funnel.mart_uc01_claims_funnel_daily`
- `gold.uc04_eligibility_outreach.mart_uc04_eligibility_outreach`
- `gold.uc05_customer_360.mart_uc05_customer_360`
- `gold.uc06_cost_forecast.mart_uc06_cost_5y`
- `gold.uc06_cost_forecast.mart_uc06_scenario_results`
- `gold.uc07_dq_policies.mart_uc07_dq_dagrapport`

> **Let op:** in fase 7 gebruikt de init-Job één Trino-database-connection met
> default-catalog `bronze`. Voor `gold.*` queries moet ofwel (a) een aparte
> Trino-DB-connection per catalog worden aangemaakt, ofwel (b) de bestaande
> dataset-definitie expliciet `gold.<schema>.<table>` als fully-qualified naam
> krijgen. De smoke-test verifieert alleen het bestaan van datasets; voor
> dashboards-die-eindusers-zien is een follow-up nodig.

## Apply

```bash
kubectl apply -k platform/12-superset/
# Wacht tot Superset Ready
kubectl -n odap-platform rollout status deploy/superset-node-default
# Init-Job runt automatisch (apply maakt 'm aan)
kubectl -n odap-platform wait --for=condition=complete job/superset-init --timeout=10m
```

## Validatie

```bash
kubectl -n odap-platform get supersetcluster
kubectl -n odap-platform get pods -l app.kubernetes.io/name=superset
kubectl -n odap-platform logs job/superset-init

# UI:
kubectl port-forward -n odap-platform svc/superset-node 8088:8088
# → http://localhost:8088
# Login: odap / odap-dev-only-CHANGE-ME (admin)
# Of via OIDC met ODAP realm users.
```

## Production

- `replicas: 2+` for the webnode.
- Custom Superset image met meegebakken Trino-driver + dependencies.
- Dashboards declaratief via Superset's `assets`-bundle in CI.
- Row-level security in Superset (op datasets) bovenop OPA-policies in Trino.
