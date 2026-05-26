---
title: Datazones
description: Medallion-architectuur (bronze/silver/gold) + sensitive vault — zone-scheiding en toegang.
---

<!-- Auto-generated door scripts/docs_gen.py uit portal/src/data/components.ts.
     Wijzigingen handmatig vervallen bij de volgende CI-build — bewerk de TS-bron. -->

# Datazones

Vier MinIO-buckets, elk met eigen Trino-catalog, plus een aparte vault voor
bijzondere persoonsgegevens (art. 9 AVG). De zone-naam in de portal en in
de OPA-policies zijn 1-op-1.

## Overzicht

| Catalog | Bucket | Inhoud | Toegang (default) |
|---|---|---|---|
| `bronze` | `odap-bronze` | Onveranderbare brondata (incl. raw PII) | data-engineers (JIT) |
| `silver` | `odap-silver` | Geconformeerd, gepseudonimiseerd waar mogelijk | analisten + engineers |
| `gold` | `odap-gold` | CGM-conforme business products | domein-rollen via RBAC |
| `sensitive` | `sensitive` | Bijzondere persoonsgegevens (art. 9 AVG, medisch) | strikt; 4-eyes principe |
| `sandbox` | `sandbox` | Gepseudonimiseerd — voor researchers | researcher (read-only) |

## Toegangsstrategie

```mermaid
flowchart LR
    bronze[bronze<br/>raw + PII] -- "ETL: pseudonimiseer" --> silver[silver<br/>geconformeerd]
    silver -- "dbt-modellen" --> gold[gold<br/>marts voor BI]
    bronze -- "alleen via vault-flow" --> sensitive[sensitive<br/>art. 9 AVG]
    silver -- "pseudo-export" --> sandbox[sandbox<br/>research]

    style sensitive fill:#fee,stroke:#c33
    style sandbox fill:#eef,stroke:#33c
```

OPA-policies zijn **format-agnostisch**: ze kijken naar
`catalog.schema.table`- en kolomnamen, niet naar het onderliggende
bestandsformaat. Switching tussen Delta en Iceberg laat de policies
onveranderd (zie [ADR-0002](../adr/0002-iceberg-vs-delta.md)).

## Wat zie je per rol?

Dit volgt 1-op-1 de rol-handleidingen:

- **WIA-beoordelaar / Wajong-arbeidsdeskundige / etc.** → primair `gold`,
  beperkt `silver` (eigen domein). Geen `bronze`.
- **Data-engineer** → `bronze` (JIT), `silver`, `gold`, `sensitive` (alleen
  via break-glass).
- **Data-steward** → read-only over alle zones (governance).
- **Researcher** → uitsluitend `sandbox`.
- **Platform-admin** → alles, maar elke query wordt audit-logged (zie
  [Runbook § 10.3](../runbook.md#103-per-release-audit-trail)).

Welke kolommen je in een gold-mart precies ziet hangt af van de OPA-policies
in [`opa-policies-src/`](https://github.com/fresh-minds/FreshStackableDataPlatform/tree/main/opa-policies-src).
Zie [Identiteit & autorisatie](auth.md) voor de policy-flow.
