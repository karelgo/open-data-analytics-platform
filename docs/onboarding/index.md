---
title: Onboarding
description: Startpunt voor nieuwe gebruikers van het UWV referentie data-platform — kies je pad op basis van rol.
tags:
  - onboarding
  - nieuw
---

# Onboarding — kies je pad

Welkom bij het **UWV Referentie Data- en Analyseplatform**. Deze pagina is
het startpunt voor iedereen die voor het eerst met het platform aan de
slag gaat. Kies hieronder het pad dat bij je rol past — elk pad eindigt
in een handleiding die in detail beschrijft wat je dagelijks doet.

!!! warning "Geen echte ODAP data"
    Dit platform is een **fictieve, illustratieve referentie-implementatie**.
    Alle datasets zijn synthetisch (alleen 9-prefix BSN's, `meta.synthetic: true`).
    Geen echte productie-ODAP data, geen echte productiecode.

---

## Welke onboarding past bij jou?

<div class="grid cards" markdown>

-   :material-account:{ .lg .middle } **Eindgebruiker**

    ---

    Je gaat met het platform werken vanuit een business-rol — Claims Analyst,
    Fraud Analyst, Marketing Analyst, Finance Analyst, researcher, … Je werkt via
    de portal, Superset-dashboards en (soms) ad-hoc Trino-queries.

    [:octicons-arrow-right-24: Naar pad 1](#pad-1-eindgebruiker-business-rollen)

-   :material-database-cog:{ .lg .middle } **Data-engineer of data-steward**

    ---

    Je bouwt en onderhoudt pipelines (NiFi, Kafka, Spark), dbt-modellen,
    of bewaakt datakwaliteit en lineage in OpenMetadata.

    [:octicons-arrow-right-24: Naar pad 2](#pad-2-data-engineer-data-steward)

-   :material-server-network:{ .lg .middle } **Platform-admin**

    ---

    Je installeert, beheert en bewaakt het cluster — Stackable-operators,
    Keycloak, OPA, ingress, secrets, observability.

    [:octicons-arrow-right-24: Naar pad 3](#pad-3-platform-admin)

-   :material-source-pull:{ .lg .middle } **Ontwikkelaar / contributor**

    ---

    Je draagt bij aan de repo zelf — code, manifests, documentatie.
    Begin met `make doctor`, `make cluster MODE=k3d` en de pre-commit
    hooks.

    [:octicons-arrow-right-24: Naar pad 4](#pad-4-contributor-ontwikkelaar)

</div>

---

## Gemeenschappelijk: voor alle rollen

Voordat je je pad induikt — deze zaken gelden voor *iedereen* die met het
platform werkt:

| Onderwerp | Wat moet je weten? |
|---|---|
| **MFA verplicht** | Alle Keycloak-accounts vereisen TOTP. Configureer Google Authenticator, Microsoft Authenticator of 1Password bij eerste inlog. |
| **Doelbinding eerst** | Het platform is **default-deny** (R-AVG-06). Toegang volgt uit je rol *plus* een gedeclareerd doel. Zie [Toegang aanvragen](../access-request-guide.md). |
| **Niets is "zomaar"** | Elke query wordt gelogd, elke toegang is herleidbaar. Treat audit-logs as real. |
| **Bij twijfel: vraag** | Eerst data-steward of platform-admin, dan pas zelf bedenken. |
| **Geen screenshots van persoonsgegevens** | Ook niet voor bug-rapporten — gebruik synthetische voorbeelden. |

> Zie ook de [zes regels voor iedereen](../rollen/index.md#zes-regels-die-voor-iedereen-gelden) op de Rollen-overzichtspagina.

---

## Pad 1 — Eindgebruiker (business-rollen)

Voor: Claims Analyst, Fraud Analyst, Claims Analyst,
Marketing Analyst, Finance Analyst, Operations Manager, proactief dienstverlener,
researcher.

### Stap 1 · Krijg je account

Je platform-admin maakt je Keycloak-account aan en kent één primaire rol
toe (bv. `claims_analyst`, `researcher`). Die rol bepaalt welke catalogs
en schemas je standaard mag zien — geen handmatige permissies nodig.

### Stap 2 · Log in op de portal

1. Open **<https://platform.odap.local:8443>** (k3d) of
   `https://platform.example.com` (aks).
2. Klik **Inloggen via Keycloak (UWV)**.
3. Vul gebruikersnaam + wachtwoord; wijzig wachtwoord bij eerste inlog.
4. Scan de QR-code met je TOTP-app en bevestig.

### Stap 3 · Verken **Mijn werkplek**

Op de portal-landing zie je alleen de applicaties waarvoor jouw rol een
grant heeft. Typische set voor business-rollen: Superset (dashboards),
Trino (ad-hoc queries via DBeaver/CLI), OpenMetadata (catalog, lineage).
NiFi/Airflow/Kafka zijn voor het platform-team — die zie je niet.

### Stap 4 · Lees jouw rol-handleiding

Elke handleiding behandelt: welke data je wél/niet ziet · dagelijkse
workflows met voorbeelden · escalatie bij problemen.

| Rol | Domein | Handleiding |
|---|---|---|
| Claims Analyst | AG / WIA | [01-claims-analyst](../handbooks/01-claims-analyst.md) |
| Fraud Analyst | WW / Handhaving | [02-fraud-analyst](../handbooks/02-fraud-analyst.md) |
| Claims Analyst | AG / Wajong (4-eyes) | [03-claims-analyst](../handbooks/03-claims-analyst.md) |
| Marketing Analyst | Klantcontact | [04-marketing-analyst](../handbooks/04-marketing-analyst.md) |
| Finance Analyst | Financiën / Beleid | [05-finance-analyst](../handbooks/05-finance-analyst.md) |
| Operations Manager | Sociaal-medische zaken | [06-operations-manager](../handbooks/06-operations-manager.md) |
| Marketing Analyst | Toeslagenwet | [07-marketing-analyst](../handbooks/07-marketing-analyst.md) |
| Researcher | Onderzoek (sandbox) | [08-researcher](../handbooks/08-researcher.md) |

### Stap 5 · Extra data nodig?

Buiten jouw standaard-scope? Vraag schemagrant aan via de portal-flow:
zie [Toegang aanvragen tot data](../access-request-guide.md). Approval
loopt via de owner in OpenMetadata; de bridge-service kent dan automatisch
een `data_access:<catalog>.<schema>` rol toe in Keycloak.

---

## Pad 2 — Data-engineer / Data-steward

Voor: data-engineers (pipelines, ingestion, transformaties) en
data-stewards (kwaliteit, governance, lineage, sensitive-review).

### Stap 1 · Begrijp de architectuur

Lees in deze volgorde:

1. [Architectuur — overzicht](../architectuur/index.md) — 15 componenten over 9 lagen.
2. [Datazones](../architectuur/datazones.md) — bronze → silver → gold → sensitive.
3. [Tabel-formaat abstractie](../architectuur/tabel-formaat.md) — waarom dbt-macros, niet hardcoded Delta.
4. [Naming conventions](../architectuur/naming.md) — `catalog.schema.table` patronen.

### Stap 2 · Lees relevante ADRs

- [ADR-0002 · Iceberg vs Delta](../adr/0002-iceberg-vs-delta.md) en
  [ADR-0006 · Delta gekozen](../adr/0006-delta-chosen-for-this-implementation.md)
- [ADR-0005 · dbt-trino als transformatielaag](../adr/0005-dbt-trino-as-transform.md)
- [ADR-0007 · Airflow pipeline-architectuur](../adr/0007-airflow-pipeline-architecture.md)
- [ADR-0008 · Self-service data-access](../adr/0008-self-service-data-access.md)

### Stap 3 · Tools die je gebruikt

| Component | Doel | URL (k3d) |
|---|---|---|
| **Airflow** | Orchestratie van dbt-runs en pipelines | `https://airflow.odap.local:8443` |
| **dbt-docs** | Model-lineage en docs | via portal `Mijn werkplek` |
| **OpenMetadata** | Catalog, lineage, ownership, data-quality, sensitive-review | `https://openmetadata.odap.local:8443` |
| **MinIO** | Object-storage (S3-compatible) | `https://minio.odap.local:8443` |

- NiFi-flows worden as-code beheerd in `nifi-flows/templates/` (REST-import via `kubectl port-forward`); geen UI.
- Trino is in-cluster; queries gaan via Superset, Jupyter, dbt of Airflow. Ad-hoc debug: `kubectl -n odap-platform port-forward svc/trino-coordinator 8443:8443`.

### Stap 4 · Lees jouw rol-handleiding

- [09 · Data-steward](../handbooks/09-data-steward.md) — datakwaliteit, governance, lineage, sensitive-review.
- [10 · Data-engineer](../handbooks/10-data-engineer.md) — pipelines, ingestion, transformaties, JIT op bronze.

### Stap 5 · Eerste hands-on

Een researcher-style sandbox + Delta-regressie-notebook zit klaar in
JupyterHub (`https://jupyter.odap.local:8443`). Verken een synthetische
dataset, draai een dbt-model, kijk hoe lineage in OpenMetadata bijwerkt.

---

## Pad 3 — Platform-admin

Voor: DevOps/SRE die het cluster installeert en draaiend houdt.

### Stap 1 · Begrijp de deployment-modes

Het platform draait in drie modes — `--mode={k3d|aks|stackit}` — die
hostnames, storage classes, ingress-shape en kustomize-overlays end-to-end
aansturen. `k3d` is voor laptop-ontwikkeling; `aks` en `stackit` zijn de
twee cloud-doelen (Azure resp. StackIT SKE).

Lees: [Deployment modes](../deployment-modes.md).

### Stap 2 · Doe een end-to-end deploy op je laptop

Vóór je productie aanraakt — eerst lokaal werkend krijgen op k3d:

```bash
make doctor MODE=k3d        # checkt tooling, kubectl context, /etc/hosts
make deploy   MODE=k3d      # cluster + bootstrap + platform + portal + smoke
```

Volledige snelstart per mode: zie [README.md](../README.md) in de repo-root
(sectie *Snelstart*).

### Stap 3 · Leer het runbook

Het [Runbook](../runbook.md) beschrijft de operationele realiteit:
break-glass procedures, incident-respons, certificate-rotatie,
backup/restore, schaling, debug-commando's.

### Stap 4 · Security & compliance

- [Security policy](../security.md) — disclosure, scope, hardening-defaults.
- [Compliance-mapping](../compliance-mapping.md) — elke R-NORA/AVG/BIO/NIS2/AI-Act-requirement → concreet bestand/setting.
- [Context (NORA/AVG/BIO/AI Act)](../context-summary.md) — wettelijk kader.

### Stap 5 · Lees jouw rol-handleiding

- [11 · Platform-admin](../handbooks/11-platform-admin.md) — cluster, security, break-glass, incident-respons.

---

## Pad 4 — Contributor (ontwikkelaar)

Voor: iedereen die aan de **repo zelf** bijdraagt — code, manifests, documentatie.

### Stap 1 · Clone en doctor

```bash
git clone https://github.com/fresh-minds/FreshStackableDataPlatform.git
cd FreshStackableDataPlatform
make doctor MODE=k3d   # vereist: docker, k3d, kubectl, helm, stackablectl, make
```

`make doctor` controleert tooling-versies, `/etc/hosts`, en de actieve
kubectl-context. Los meldingen op voor je verder gaat.

### Stap 2 · Pre-commit hooks

```bash
pip install pre-commit
pre-commit install
```

Pre-commit checks (zie [`.pre-commit-config.yaml`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/.pre-commit-config.yaml))
draaien automatisch bij elke `git commit`. **Skip ze niet** met `--no-verify` —
los het onderliggende probleem op.

### Stap 3 · Lokale deploy

```bash
make deploy MODE=k3d           # end-to-end, ~15-30 min op een fatsoenlijke laptop
# of stap-voor-stap:
make cluster         MODE=k3d
make bootstrap       MODE=k3d
make deploy-platform MODE=k3d
make seed
make test
```

### Stap 4 · Documentatie lokaal previewen

Deze site (MkDocs Material) draait je lokaal voor je een doc-PR opent:

```bash
pip install -r requirements-docs.txt
mkdocs serve            # http://127.0.0.1:8000
```

CI bouwt en publiceert via `.github/workflows/docs.yml` naar GitHub Pages
zodra je PR naar `main` mergt.

### Stap 5 · Belangrijke conventies

| Conventie | Waar gedocumenteerd? |
|---|---|
| Mode-aware deploys (`MODE=k3d\|aks`) | [Deployment modes](../deployment-modes.md) |
| Tabel-formaat via dbt-macro, niet hardcoded | [ADR-0006](../adr/0006-delta-chosen-for-this-implementation.md) |
| Doelbinding-eerst access-model | [ADR-0008](../adr/0008-self-service-data-access.md) |
| Nederlandstalige docs, Engelse identifiers | [docs/README.md § Conventies](../README.md) |
| Stackable-operators bezitten PDB's voor hun producten | (geen custom PDB authors voor kafka/hive/zk/trino/nifi/airflow/superset) |

### Stap 6 · Cleanup

```bash
make clean        # k3d: cluster delete
make aks-down     # aks: terraform destroy
```

---

## Volgende stappen

- Helemaal nieuw? Lees eerst de [Home-pagina](../index.md) voor de 30-seconden-pitch.
- Op zoek naar concrete business-flows? Bekijk de [Use cases](../use-cases/index.md) — 11 scenario's van WIA-funnel tot integrale klantreis.
- Beslissingen begrijpen? De [ADR-index](../adr/index.md) legt de fundamentele keuzes vast.
- Iets onduidelijk? Open een issue op [GitHub](https://github.com/fresh-minds/FreshStackableDataPlatform/issues) of escaleer via je platform-admin.
