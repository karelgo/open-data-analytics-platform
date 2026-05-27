# Handbook — Smoketest (systeemrol)

> Rol-key: `smoketest` · Type: **service-account, geen mens** · Risiconiveau access: middel

Dit is **geen rol voor mensen**. Het is een service-account voor
geautomatiseerde tests, dbt-runs in CI en smoke tests bij deploy.
Deze handbook is for the **platform-admins en data-engineers** die
deze rol configureren en bewaken.

---

--8<-- "_snippets/url-modes.md"

## 1. Waar wordt deze rol gebruikt?

- **CI-pipeline** (`ci/github-actions/`) — bij elke PR run je `dbt parse`, `opa test`, smoke tests.
- **Smoke tests** (`scripts/run-smoke-tests.sh`, `tests/smoke/*.sh`) — verifiëren dat het cluster werkt.
- **dbt-runs** in Airflow voor `staging`/`marts` — non-interactief.
- **Geen interactieve users** — login geweigerd, alleen service-account-flow.

---

## 2. Hoe is deze rol opgezet?

### 2.1 In OPA

```json
"smoketest": {
  "_role_purpose": "Static-auth user voor smoke-tests + dbt-runs.",
  "catalogs": ["bronze", "silver", "gold"],
  "schemas": null,
  "purposes": ["*"],
  "can_see_pii": true,
  "can_see_medical": false,
  "can_see_bankrekening": false,
  "regio_filter": false,
  "break_glass": false
}
```

> **Waarom alle purposes (`*`)?** Smoke tests valideren dat queries
> *technisch* werken. De purposes zijn niet bedoeld als purpose-limitation maar
> als test-coverage. In production wordt deze rol **alleen vanuit de CI**
> aangesproken, niet vanaf werkstations.

### 2.2 Authenticatie

Geen password-flow. Het service-account gebruikt:

- **Static OIDC client credentials** (Keycloak `client_credentials`-grant)
- Secret in `Stackable secret-operator` (production: External Secrets + Vault)

### 2.3 Geen sensitive

`smoketest` heeft **geen** access tot `sensitive.*` of `sandbox.*`.

---

## 3. Wat doet deze rol concreet?

### 3.1 dbt-runs

```bash
# In Airflow-DAG of CI
dbt run --target prod --profiles-dir /etc/dbt/profiles
dbt test --target prod
```

Het `profiles.yml` haalt credentials uit env-vars (mounted via secret-operator).

### 3.2 Smoke tests

```bash
# tests/smoke/01-trino-up.sh
trino --user smoketest --catalog gold --execute "SELECT 1"

# tests/smoke/05-dbt-runs.sh
dbt build --select +mart_uc01_claims_funnel_daily

# tests/smoke/08-opa-decisions.sh
# verifieert dat OPA accept/deny correct werkt
```

### 3.3 Synthetische data laden

```bash
# data-generation/seed.py via Airflow seed-DAG
python -m data_generation.seed --rows 10000 --user smoketest
```

---

## 4. Bewaking

### 4.1 Wat moet je monitoren?

| Metric | Verwacht | Alert-threshold |
|---|---|---|
| `smoketest` queries per uur | < 200 | > 500 = mogelijk runaway-job |
| `smoketest` access tot `silver/wia/aanvraag` | dagelijks 1-5x | > 50/dag = pipeline-loop |
| Failed auth voor `smoketest` | 0 | > 0 = secret-rotation issue |
| Decision-log entries `smoketest` op `gold.*` | normaal | sudden spike = onderzoeken |

Alerts gaan via Prometheus → AlertManager → Slack `#platform-alerts`.

### 4.2 Periodieke review

Maandelijks (data-steward + platform-admin):

1. Bekijk OPA decision-log voor `smoketest` op production-zones.
2. Controleer of er **geen** queries zijn met cliënt-specifieke filters
   (`WHERE bsn = '...'`) — dat zou betekenen dat een mens deze rol misbruikt.
3. Verifieer dat secret-rotatie afgelopen periode is uitgevoerd.

---

## 5. Wat te doen bij anomalieën?

### 5.1 Onverwachte spike in smoke-queries

1. Check Airflow voor lopende DAGs — vermoedelijk een retry-loop.
2. Pauzeer de DAG.
3. Research de fout.
4. Hervat na fix.

### 5.2 `smoketest` doet plotseling sensitive-queries

Dit is **niet** mogelijk volgens OPA-policy: deny default. Als toch:

1. **Direct** smoke-test deactiveren in Keycloak.
2. Research hoe een sensitive-query überhaupt door OPA kwam.
3. Audit-log van laatste 24u exporteren.
4. Incident melden volgens NIS2-procedure (zie [11-platform-admin.md](11-platform-admin.md) § 4.8).

### 5.3 Failed auth — secret rotation

Als CI-runs failen met `401 Unauthorized` voor `smoketest`:

1. Secret is verlopen of geroteerd zonder propagatie.
2. Vernieuw via secret-operator:
   ```bash
   kubectl annotate secret smoketest-oidc-secret -n odap-platform \
     stackable.tech/refresh=$(date +%s)
   ```
3. Restart de DAG / smoke-test.

---

## 6. Beveiligingsregels

- **Geen interactief gebruik.** Login als `smoketest` vanaf een werkstation
  is technisch geblokkeerd (geen direct grant).
- **Geen gedeeld secret.** Het OIDC-client-secret komt alleen uit de
  secret-operator; staat **niet** in code, niet in env-files, niet in chats.
- **Roteer per kwartaal** (production). In dev: bij elke fresh `make bootstrap`.
- **Audit-log = bewijs.** Bij twijfel over wat de rol gedaan heeft, lees
  de log; vraag het niet aan de developers.

---

## 7. Wat je nooit doet

- `smoketest`-credentials gebruiken voor "snel een query" — gebruik je eigen account.
- `smoketest` extra rechten geven om een test te laten slagen — fix de test.
- Een production-DAG schrijven die `smoketest` als impersonatie van een mens-rol gebruikt.

---

**Vorige:** [11-platform-admin.md](11-platform-admin.md) ·
**Index:** [README.md](README.md)
