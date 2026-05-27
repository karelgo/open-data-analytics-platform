---
title: "Handleiding — Platform-admin"
role: platform_admin
---

> Rol-key: `platform_admin` · Domein: Cluster + security · Risiconiveau toegang: maximaal (break-glass)

Deze handleiding is voor **platform-admins**. Je hebt break-glass-toegang
tot **alle catalogs**, inclusief `sensitive` en `sandbox`. Je rol is **niet
voor day-to-day werk** — je bent er voor incidenten, structurele wijzigingen
en governance van het platform zelf. **Elke break-glass-actie wordt gelogd
en achteraf gereviewd.**

---

## 1. Wat doet jouw rol?

Je bent eindverantwoordelijk voor de werking en veiligheid van het
platform. Je gebruikt het platform om:

- Cluster-incidenten op te lossen
- Toegang en rollen te beheren in Keycloak
- OPA-policies te beoordelen en te deployen
- Backups en restores uit te voeren
- Compliance-evidence te exporteren
- JIT-aanvragen van data-engineers goed te keuren
- Structurele wijzigingen (architectuur, ADR's, security) te begeleiden

---

## 2. Inloggen, MFA & applicaties

| Applicatie | Wat doe je daar? | URL |
|---|---|---|
| **Keycloak Admin** | Rolbeheer, gebruikers, MFA-policies | https://keycloak.odap.local/admin |
| **kubectl + k9s** | Alle clusters, alle pods | terminal |
| **Apache Airflow** | Maintenance-DAGs | https://airflow.odap.local |
| **OpenSearch / OPA-logs** | Audit-log review | via Vector ingestion |
| **OpenMetadata** | Service-config, governance | https://openmetadata.odap.local |
| **Prometheus + Grafana** | Metrics, alerts | https://grafana.odap.local |
| **MinIO Console** | Bucket-beheer | https://minio.odap.local |

- Trino break-glass queries: `kubectl -n odap-platform port-forward svc/trino-coordinator 8443:8443` en dan via DBeaver op `localhost:8443`.

> **MFA verplicht en hardware-gebonden.** Voor productie: WebAuthn-passkey of
> hardware-token (YubiKey). Geen TOTP-app op een mobiel.

---

## 3. Welke data zie je wel en niet?

### 3.1 Catalogs

Je hebt toegang tot **alles**: `bronze`, `silver`, `gold`, `sensitive`,
`sandbox`. Toegang valt onder **break-glass**: elke query staat de
volgende ochtend op het reviewscherm van de data-steward.

> **Vuistregel break-glass.** Doe het alleen voor:
> 1. Incident-respons (productie down, data corrupt)
> 2. Compliance-evidence verzamelen
> 3. Onderhouds-validatie (niet voor begripsmatige queries)
>
> Voor "ik wilde even kijken" gebruik je een eigen non-admin account.

### 3.2 Audit-discipline

Elke break-glass-query begint met een comment:

```sql
-- BREAK-GLASS REASON: incident INC-2026-04-30 / cliënt 999000123 / data corruptie review
SELECT ... FROM sensitive.eligibility_cases.dossier WHERE bsn = '999000123';
```

De data-steward valideert de volgende ochtend dat deze comments er zijn.

---

## 4. Dagelijkse workflows met voorbeelden

### 4.1 Workflow A — Cluster-health checken

```bash
# Snelste overview
make doctor

# Per Stackable-laag
kubectl get pods -n odap-platform
kubectl get pods -n odap-data
kubectl get pods -n odap-meta
kubectl get pods -n odap-monitoring
kubectl get pods -n odap-auth

# Custom resources
kubectl get trinocluster,kafkacluster,hivecluster,opacluster,airflowcluster,supersetcluster,nificluster -A
```

### 4.2 Workflow B — Nieuwe gebruiker toevoegen

> In productie: gebeurt via SSO-federatie (DigiD/eHerkenning of Entra ID).
> In deze referentie via Keycloak Admin.

1. Open https://keycloak.odap.local/admin → realm `uwv` → **Users → Add user**.
2. Vul username, email, voornaam, achternaam.
3. Tab **Credentials** → temporary password.
4. Tab **Role mappings** → wijs de juiste rol toe (één rol per persoon!).
5. Stuur de gebruiker zijn login-link + verzoek MFA in te stellen bij eerste login.

### 4.3 Workflow C — JIT-aanvraag goedkeuren

1. Data-engineer maakt ticket "TICKET-1234: bronze access 4u, doel debug iban".
2. Lees doel + scope. Bij twijfel: bel de data-engineer voor toelichting.
3. Activeer rol via Keycloak (4 uur). In productie: dit gaat via een
   automatiseringsscript dat de mapping in OPA tijdelijk aanpast.
4. Sluit het ticket met je goedkeuring; markeer in audit-log waarom.

### 4.4 Workflow D — OPA-policy deployen

Wijzigingen aan policies gebeuren in `opa-policies-src/`. Process:

```bash
# 1. Test lokaal
make opa-test                     # 23/23 PASS verwacht

# 2. Build bundle
scripts/build-opa-bundle.sh       # rendert ConfigMap

# 3. Deploy
kubectl apply -f platform/10-opa/

# 4. Verifieer
kubectl logs -n odap-platform <opa-pod>
# en draai smoke test:
tests/smoke/08-opa-decisions.sh
```

> **Pair-review verplicht.** OPA-policies krijgen altijd een tweede paar ogen
> (data-steward of senior platform-engineer) vóór deploy.

### 4.5 Workflow E — Backup uitvoeren

Volgens [`docs/runbook.md` § 5](../runbook.md):

```bash
# MinIO mirror
mc mirror local/odap-bronze backup-bucket/odap-bronze/$(date -I)/
mc mirror local/odap-silver backup-bucket/odap-silver/$(date -I)/
mc mirror local/odap-gold backup-bucket/odap-gold/$(date -I)/
mc mirror local/sensitive backup-bucket/sensitive/$(date -I)/

# Postgres dumps (Hive Metastore, Airflow, Superset, OpenMetadata)
for db in hive airflow superset openmetadata; do
  kubectl exec -n odap-platform postgres-$db-0 -- \
    pg_dump -U $db $db > backups/$db-$(date -I).sql
done

# Keycloak realm export
kubectl exec -n odap-auth keycloak-0 -- \
  /opt/keycloak/bin/kc.sh export --file /tmp/odap-realm.json --realm uwv
kubectl cp odap-auth/keycloak-0:/tmp/odap-realm.json backups/odap-realm-$(date -I).json
```

### 4.6 Workflow F — Incident-response (cluster down)

Volgens [`docs/runbook.md` § 4](../runbook.md):

1. **Triage**: `make doctor`, lees recente alerts in Grafana.
2. **Communicatie**: meld incident in Slack `#incidents`; zet status-page.
3. **Stabilize**: rolling restart van het falende component (`kubectl rollout restart`).
4. **Diagnose**: pod-logs, OPA-decision-log, OpenSearch.
5. **Resolve**: pas patch toe; als infra-niveau, escaleer naar SRE.
6. **Post-mortem**: schrijf binnen 48u een incident-rapport (geen schuldvinger).

### 4.7 Workflow G — Compliance-evidence exporteren

Voor een audit:

```bash
# OPA-tests
make opa-test > evidence/opa-test-$(date -I).log

# OpenMetadata classifications
curl -H "Authorization: Bearer $TOKEN" \
  https://openmetadata.odap.local/api/v1/tags?fields=classifications \
  > evidence/om-classifications-$(date -I).json

# dbt test history
dbt run --select metadata.dbt_test_results > evidence/dbt-tests-$(date -I).log

# OPA decision-log statistieken
opensearch-curl /logs-*/_search?q=opa.decision&size=0&_source=false \
  > evidence/opa-decisions-stats-$(date -I).json
```

Zie [`docs/runbook.md` § 10](../runbook.md) voor volledige procedure.

### 4.8 Workflow H — NIS2-meldplicht 24u/72u

Bij ernstig incident:

1. **Binnen 24u**: vroegsignalering bij Nationaal Cyber Security Centrum (NCSC).
2. **Binnen 72u**: officieel incident-rapport met scope, oorzaak, impact, mitigatie.
3. **Binnen 1 maand**: definitief evaluatierapport.

Templates en escalatie-paden: out-of-platform via Platform CISO.

---

## 5. Verantwoordelijkheden

In volgorde van prioriteit:

1. **Beschikbaarheid en integriteit** van het platform.
2. **Toegangs-discipline**: alleen wie het nodig heeft, alleen wat nodig is.
3. **Incident-respons**: snel, gestructureerd, navolgbaar.
4. **Backup en restore**: getest, niet alleen "ingericht".
5. **Compliance-evidence**: actueel, exporteerbaar.
6. **Beleidshygiëne**: ADR's, runbook, dependency-pinning.

---

## 6. Hulp, fouten & escalatie

| Probleem | Contact |
|---|---|
| Productie-incident | Volg runbook + UWV SRE-team |
| Beleidsvraag | Platform CISO + Data Office |
| Wettelijke vraag | Privacy Officer (FG) |
| Burnout / overbelasting | Manager + collega-admin (rol moet redundant zijn!) |

---

## 7. Wat je nooit doet

- Break-glass-toegang gebruiken voor "snelle vragen" — maak een non-admin account.
- Een productie-OPA-policy patchen zonder PR + tweede paar ogen.
- Direct `kubectl edit` op productie-CRDs — altijd via GitOps.
- Een wachtwoord in plaintext doorsturen, ook niet "tijdelijk".
- MFA disable-en voor "even debuggen".
- Nieuwe rollen creëren zonder vermelding in `role_mappings.json` + ADR.

---

**Vorige:** [10-data-engineer.md](10-data-engineer.md) ·
**Volgende:** [12-smoketest-systeem.md](12-smoketest-systeem.md) ·
**Index:** [README.md](README.md)
