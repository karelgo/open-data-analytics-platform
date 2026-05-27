---
title: Originele referentie-architecture
description: Het bronvoorstel waarvan deze repo de implementatie is.
---

<!-- Auto-generated door scripts/docs_gen.py uit portal/src/data/components.ts.
     Changes handmatig vervallen bij de volgende CI-build — bewerk de TS-bron. -->

# Originele referentie-architecture

De huidige implementatie volgt:

- [`referentiearchitecture-odap-data-analytics.md`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/referentiearchitecture-odap-data-analytics.md)
  — 12 architectureprincipes, 10 use-cases, CGM-entiteiten, Sensitive Vault,
  data-mesh, wettelijke mappen.
- [`requirements.md`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/requirements.md)
  — Volledige requirements-matrix: SOC 2, AVG, ISO 27001 / ISO 27002, NIS2, AI Act met
  R-* codes (70+ rules).
- [`odap-platform-mapping-research.md`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/odap-platform-mapping-research.md)
  — Technische blauwdruk: component-mapping Stackable → Kubernetes.

Deze pagina is een **navigatie-stub** — de bron-documenten staan in de
repo-root als ware ze A4-rapporten. Voor implementatie-details zie de
[Architecture · Overview](index.md).

## Definition of Done

Het platform is "klaar" wanneer:

1. `make cluster && make bootstrap && make deploy-platform && make seed && make test`
   slaagt op een schoon k3d-cluster.
2. Superset toont dashboard "WIA Funnel" met 7 dagen synthetische data voor
   rol `data_steward`.
3. OpenMetadata toont end-to-end lineage van synthetische bron → dbt-model →
   Superset chart.
4. OPA weigert query op `client_360.bsn` voor rol zonder doel "claim payout";
   maskeert BSN voor `marketing_analyst`.
5. dbt-test `bsn_valid` faalt op een ingespoten ongeldige BSN-record.
6. OpenMetadata toont voor elke gold-tabel: eigenaar, purpose-limitation-tag,
   classificatie, retention period.
7. [`compliance-mapping`](../compliance-mapping.md) mapt elk
   R-GDPR/ISO27001/NIS2/NIS2 op een concreet bestand of setting.
8. CI-pipeline (GitHub Actions) groen op fresh clone.
9. Switching naar Iceberg vereist alleen wijziging in `platform-config.yaml`
   + Trino-catalog redeploy + dbt re-run — code blijft anders ongewijzigd.
10. Geen `latest`-tag, geen plaintext secret, geen TODO in production-policy
    zonder ticket-id.
