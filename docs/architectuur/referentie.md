---
title: Originele referentie-architectuur
description: Het bronvoorstel waarvan deze repo de implementatie is.
---

<!-- Auto-generated door scripts/docs_gen.py uit portal/src/data/components.ts.
     Wijzigingen handmatig vervallen bij de volgende CI-build — bewerk de TS-bron. -->

# Originele referentie-architectuur

De huidige implementatie volgt:

- [`referentiearchitectuur-odap-data-analytics.md`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/referentiearchitectuur-odap-data-analytics.md)
  — 12 architectuurprincipes, 10 use-cases, CGM-entiteiten, Sensitive Vault,
  data-mesh, wettelijke mappen.
- [`requirements.md`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/requirements.md)
  — Volledige requirements-matrix: NORA, AVG, BIO/BIO2, NIS2, AI Act met
  R-* codes (70+ rules).
- [`odap-platform-mapping-research.md`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/odap-platform-mapping-research.md)
  — Technische blauwdruk: component-mapping Stackable → Kubernetes.

Deze pagina is een **navigatie-stub** — de bron-documenten staan in de
repo-root als ware ze A4-rapporten. Voor implementatie-details zie de
[Architectuur · Overzicht](index.md).

## Definition of Done

Het platform is "klaar" wanneer:

1. `make cluster && make bootstrap && make deploy-platform && make seed && make test`
   slaagt op een schoon k3d-cluster.
2. Superset toont dashboard "WIA Funnel" met 7 dagen synthetische data voor
   rol `data_steward`.
3. OpenMetadata toont end-to-end lineage van synthetische bron → dbt-model →
   Superset chart.
4. OPA weigert query op `client_360.bsn` voor rol zonder doel "uitkering";
   maskeert BSN voor `crm_medewerker`.
5. dbt-test `bsn_valid` faalt op een ingespoten ongeldige BSN-record.
6. OpenMetadata toont voor elke gold-tabel: eigenaar, doelbinding-tag,
   classificatie, bewaartermijn.
7. [`compliance-mapping`](../compliance-mapping.md) mapt elk
   R-NORA/AVG/BIO/NIS2 op een concreet bestand of setting.
8. CI-pipeline (GitHub Actions) groen op fresh clone.
9. Switching naar Iceberg vereist alleen wijziging in `platform-config.yaml`
   + Trino-catalog redeploy + dbt re-run — code blijft anders ongewijzigd.
10. Geen `latest`-tag, geen plaintext secret, geen TODO in productie-policy
    zonder ticket-id.
