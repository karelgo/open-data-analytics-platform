# ADR-0001: Stackable Data Platform als operator-baseline

| Status | **Geaccepteerd** |
|---|---|
| Datum | 2026-04-30 |
| Beslissers | Platform Architect, CTO |
| Gerelateerd | ADR-0002 (table format), ADR-0003 (OPA), ADR-0005 (dbt) |

---

## Context

Het ODAP platform moet open source zijn, vendor-onafhankelijk, SOC 2-conform en
declaratief op Kubernetes draaien. We hebben een keuze nodig voor de
"runtime-kit" die NiFi, Kafka, Spark, Trino, Hive Metastore, Airflow,
Superset, OPA en ZooKeeper als production-grade workloads op Kubernetes brengt.

Drie reële paden:

1. **Stackable Data Platform 26.3** — eigen Kubernetes-operators per
   component, verenigd via gedeelde CRDs (AuthenticationClass, S3Connection,
   ListenerClass, SecretClass).
2. **Helm-charts per component, zelf samengevoegd** — bv. Bitnami,
   Strimzi (Kafka), Spark Operator, Trino Helm — zelf TLS, auth en exposure
   integreren.
3. **Cloud-managed services** — Databricks / Microsoft Fabric / EMR —
   off-the-shelf maar vendor-bound.

---

## Beslissing

We kiezen **Stackable Data Platform 26.3** als operator-baseline.

---

## Motivatie

- **Convergente CRDs**. AuthenticationClass + S3Connection + SecretClass +
  ListenerClass werken **identiek** voor alle operators. Eén Keycloak-config
  geldt voor Trino én Superset én Airflow én NiFi. Dit scheelt
  significante glue-code in pad 2.
- **Referentie-demo lakehouse**. De `data-lakehouse-iceberg-trino-spark`-demo
  laat zien dat NiFi → Kafka → Spark → Iceberg/Hive → Trino + OPA + Superset
  end-to-end werkt op Stackable. Dit verkort de bouwtijd substantieel.
- **Open source en open governance**. Apache 2.0; CRDs, code en images zijn
  publiek (`docker.stackable.tech`) zonder license-lock-in.
- **Native Kubernetes**. Geen "VM-gebaseerd cluster van NiFi/Kafka/Trino" —
  alles is K8s-Pod, met StatefulSet/Deployment, NetworkPolicies, RBAC.
  Dit past 1-op-1 on the UWV-doelarchitecture (zone-scheiding, segmentatie).
- **Geschikt voor sovereign / on-prem deployment**. Geen cloud-leverancier
  vereist; werkt op IONOS, OpenShift, on-prem K8s — relevant voor UWV's
  bijzondere persoonsgegevens.
- **Versie-pinning per release**. `stackablectl` met release-bestand
  `infrastructure/stackablectl/release.yaml` borgt reproduceerbare deploys
  (R-BIO-19, R-NIS2-03 supply chain).

---

## Risico's en mitigaties

| Risico | Mitigatie |
|---|---|
| Stackable is een commerciële ondersteuner; project-bestaan afhankelijk van bedrijf | Apache 2.0 licentie + upstream vanilla images → fork/exit-pad blijft open |
| Operator-CRDs evolueren tussen releases | Versie pinnen in `release.yaml`; upgrades via ADR |
| Kleinere community dan upstream Kafka/Spark | Voor Trino en Iceberg/Delta is de upstream community direct te raadplegen via Stackable's vanilla builds |
| Delta Lake support is minder rijp dan Iceberg | Zie ADR-0006 — mitigaties via NiFi → Kafka → Spark-pad |

---

## Niet gekozen alternatieven

- **Self-hosted Helm-charts per component**. Geen unified auth/secret/exposure
  CRD-laag → hoge integratie-kosten. Skip.
- **Databricks / Fabric**. Vendor lock-in, geen sovereign-cloud-fit voor UWV
  in strikt-medische context. Skip.
- **Kubeflow + Apache Beam stack**. Geen 1-op-1 fit; gericht op ML-pipelines,
  niet op lakehouse + BI + governance. Skip.

---

## Implementatie-impact

- `infrastructure/stackablectl/release.yaml` legt operator-versies vast.
- Alle Stackable-CRDs in `platform/00-13/`.
- Geen mix met andere data-operators (bv. Strimzi voor Kafka) tenzij ADR.
