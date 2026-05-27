# UC-12 — FinOps (FOCUS) — Power BI / Fabric variant

**Doel**: dezelfde FOCUS-billing-export uit [UC-12](uc12-focus-finops.md), maar de
visualisatie-laag is **Microsoft Power BI** op de Fabric workspace i.p.v. Apache
Superset. Direct Lake-mode tegen het bestaande `uc11_lakehouse` SQL endpoint —
nul data-copy, nul refresh-schedule.

Mirror van het Superset-dashboard: zelfde 12 visuals in dezelfde 5 rijen, zelfde
KPI-strip, zelfde drill-downs. De data-pijplijn (CSV → bronze → silver → 5 gold-
marts) blijft onveranderd; de marts moeten alleen óók in de Fabric lakehouse
verschijnen voor Direct Lake kan lezen.

---

## 1. Waarom een tweede variant

Superset blijft de open-source baseline van het referentieplatform — generiek,
embeddable, geen vendor-lock. Voor ODAP roles die al een Microsoft 365 / Entra
ID-account hebben (en dus al een Power BI Pro-licentie via de tenant) is Power
BI vaak de comfortabelere consumption-UI:

- Direct Lake op OneLake — VertiPaq columnar in-memory, nul data-copy.
- Native Excel "Analyze in Excel" en Pivot — finance-mensen weten dat al.
- Tenant-SSO via Entra ID — geen extra Keycloak-mapping nodig.
- Composite models — power-user mag z'n eigen Excel-tabel ernaast plakken
  zonder de certified semantic model te forken.

Zie [FreshLakehouse/docs/research/powerbi-as-bi-and-self-service-layer.md](https://github.com/FreshMinds_Programming/FreshDataPlatform/blob/main/FreshLakehouse/docs/research/powerbi-as-bi-and-self-service-layer.md)
voor de bredere keuze tussen Superset en Power BI in het referentieplatform.

---

## 2. End-to-end flow

```
Finance medewerker
   │  Upload focus-yyyymm.csv via mc CLI of MinIO Console
   ▼
MinIO  s3://odap-staging/incoming/focus/<ts>-<file>.csv
   │
   ▼
ingest_csv_focus DAG (Airflow)
   │  csv_to_bronze.py + pyarrow type-cast
   ▼
bronze.finops.focus_billing  (Delta op MinIO)
   │
   ▼
silver_finops DAG → silver.finops.stg_focus_billing
   │
   ▼
gold_uc12_focus_finops DAG → 5 marts in gold.uc12_focus_finops
   │
   ├──▶ Apache Superset (lokaal k3d) — uc12-focus-finops dashboard      [UC-12 baseline]
   │
   └──▶ Fabric Lakehouse (uc11_lakehouse) — via dbt-fabricspark of seed-notebook
            │
            ▼
        Power BI semantic model  SM_uc12_focus_finops  (Direct Lake)
            │
            ▼
        Power BI report  uc12_focus_finops_dashboard
```

De Power BI-laag leeft in dezelfde Fabric workspace als UC-11 (`uc11_lakehouse`)
— één workspace, twee semantic models naast elkaar.

---

## 3. Artefacten

| Bestand | Wat |
|---|---|
| [scripts/fabric-generate-powerbi-uc12.py](../../scripts/fabric-generate-powerbi-uc12.py) | Genereert SemanticModel (`model.bim`) en PBIR-Report voor UC-12 |
| [scripts/fabric-upload-powerbi.py](../../scripts/fabric-upload-powerbi.py) | Generieke uploader — neemt `--project uc12_focus_finops` |
| [scripts/fabric-seed-uc12.py](../../scripts/fabric-seed-uc12.py) | One-shot synthetic-seed orkestrator (CSV → notebook → reframe) |
| [platform/12-powerbi/uc12_focus_finops/SemanticModel/](../../platform/12-powerbi/uc12_focus_finops/SemanticModel/) | `definition.pbism` + `model.bim` met 5 tabellen, 11 DAX measures |
| [platform/12-powerbi/uc12_focus_finops/Report/](../../platform/12-powerbi/uc12_focus_finops/Report/) | PBIR-tree, 12 visuals × 5 rijen (= 19 files) |
| [platform/11-airflow/fabric-notebooks/uc12_focus_seed.ipynb](../../platform/11-airflow/fabric-notebooks/uc12_focus_seed.ipynb) | Spark-notebook dat de 5 marts uit de CSV bouwt |
| [platform/11-airflow/include/fabric_helpers.py](../../platform/11-airflow/include/fabric_helpers.py) | OAuth2 client-credentials + Fabric REST helpers (gedeeld met UC-11) |

**Items in de Fabric workspace** na een succesvolle upload:

```
SemanticModel  uc12_focus_finops            7d480700-013b-4ab5-909a-d2ab17f93e26
Report         uc12_focus_finops_dashboard  3f508254-867b-4b58-9c7d-ebafb0947df2
```

URL's:
- Semantic model: `https://app.fabric.microsoft.com/groups/<WS>/datasets/<SM_ID>`
- Report: `https://app.fabric.microsoft.com/groups/<WS>/reports/<RP_ID>`

(`<WS>` = `FABRIC_WORKSPACE_ID` uit `secrets/local/uc11-multiplatform.env`.)

---

## 4. Semantic model — wat zit erin

5 tabellen, Direct Lake-mode tegen `dbo.mart_uc12_focus_*` in `uc11_lakehouse`:

| Tabel (in BI) | Source-tabel | Belangrijkste measures |
|---|---|---|
| `spend_monthly` | `mart_uc12_focus_spend_monthly` | `Effective Cost Total`, `List Cost Total`, `Billed Cost Total`, `Resource Count` |
| `service_breakdown` | `mart_uc12_focus_service_breakdown` | `Service Spend` |
| `commitment` | `mart_uc12_focus_commitment_utilization` | `Avg Commitment Coverage`, `Committed Spend`, `On-demand Spend` |
| `top_resources` | `mart_uc12_focus_top_resources` | `Resource Cost` |
| `savings` | `mart_uc12_focus_savings` | `Savings Total`, `Savings Pct` |

Geen relaties tussen tabellen (mart-by-mart consumption — elk dashboard-rij
filtert binnen één mart). Bewust gehouden zoals de Superset-dashboard waar
elke chart één dataset gebruikt.

Format-strings: `\€#,##0` voor bedragen, `0.0%` voor percentages, `yyyy-mm`
voor `billing_month`. Dat scheelt visuals-time formatting.

---

## 5. Het report — 12 visuals × 5 rijen

Exact dezelfde layout als de Superset-dashboard:

| Rij | Visuals |
|---|---|
| 1 | 4 KPI cards: Effective cost · List cost · Total savings · Avg commitment coverage % |
| 2 | 2 line charts: spend × maand × provider · commitment coverage × maand × service-categorie |
| 3 | 3 donut charts: spend per service-categorie · regio · environment |
| 4 | 2 bar charts: top services · spend per applicatie (uit tags) |
| 5 | 1 tabel: top-resources op effective cost |

PageId: `uc12dashpage1`. 1280×1040 viewport, fit-to-page. Schema: PBIR 2.7
(`visualContainer/2.7.0`).

---

## 6. Eerste keer deployen

### Voorwaarden
- Service Principal met workspace-Contributor op de Fabric workspace.
  Env-vars uit `secrets/local/uc11-multiplatform.env`:
  - `FABRIC_TENANT_ID`, `FABRIC_CLIENT_ID`, `FABRIC_CLIENT_SECRET`
  - `FABRIC_WORKSPACE_ID`, `FABRIC_LAKEHOUSE_ID`, `FABRIC_LAKEHOUSE_NAME`
  - `FABRIC_SQL_ENDPOINT_HOST` (gebruikt door de M-expression in `model.bim`)
- Python 3.9+. Geen externe deps — alles via `urllib` in `fabric_helpers.py`.

### Stappen

```bash
# 1. Laad de SP-creds in de shell
set -a; source secrets/local/uc11-multiplatform.env; set +a

# 2. Genereer SemanticModel + Report bestanden onder platform/12-powerbi/
python3 scripts/fabric-generate-powerbi-uc12.py

# 3. Upload de SemanticModel eerst (PBIR heeft het ID nodig)
python3 scripts/fabric-upload-powerbi.py --project uc12_focus_finops --semanticmodel-only

# 4. Regenereer met het echte SemanticModel-ID, dan upload het report
python3 scripts/fabric-generate-powerbi-uc12.py    # leest het ID via REST auto-discovery
python3 scripts/fabric-upload-powerbi.py --project uc12_focus_finops --report-only
```

Vanaf de tweede deploy is stap 3+4 één commando:

```bash
python3 scripts/fabric-generate-powerbi-uc12.py && \
python3 scripts/fabric-upload-powerbi.py --project uc12_focus_finops
```

De upload-script is idempotent: bestaande items krijgen een
`updateDefinition`-PUT in plaats van een create.

---

## 7. De marts in het lakehouse krijgen

De Power BI semantic model leest via Direct Lake uit
`dbo.mart_uc12_focus_*` in `uc11_lakehouse`. Tot die tabellen er staan, blijven
de visuals leeg. Drie opties om ze te seeden — kies de simpelste die jou past:

### Optie 0 — One-shot synthetic seed (snelste demo-pad)

Eén commando laadt `data-generation/focus-test.csv` (553 rijen FOCUS-spec) als
de 5 marts in `uc11_lakehouse` en triggert direct een Direct Lake reframe:

```bash
set -a; source secrets/local/uc11-multiplatform.env; set +a
python3 scripts/fabric-seed-uc12.py
```

Wat er gebeurt onder de motorkap (zie `scripts/fabric-seed-uc12.py`):

1. CSV upload naar `Files/uc12_seed/focus-test.csv` via OneLake DFS (3-step
   append-flow met `storage.azure.com` scope).
2. Upload van [`platform/11-airflow/fabric-notebooks/uc12_focus_seed.ipynb`](../../platform/11-airflow/fabric-notebooks/uc12_focus_seed.ipynb)
   naar de workspace (idempotent — bestaande notebook krijgt
   `updateDefinition`).
3. Trigger het notebook via `fabric_helpers.trigger_notebook` met
   `workspace_id` + `lakehouse_id` + `csv_relative_path` parameters.
4. Wacht tot Spark klaar is (~30-60s voor 553 rijen).
5. Trigger Direct Lake reframe via de Power BI Datasets API.
6. Verifieer dat alle 5 mart-tabellen in `list_lakehouse_tables` staan.

Het notebook is een 1:1 Spark-SQL spiegel van de dbt staging + 5 mart SQL —
zelfde kolomnamen, zelfde aggregaties, zelfde `rank_in_month` window-functie.
Idempotent: `mode("overwrite")` op elke target, dus opnieuw runnen vervangt de
data zonder dat oude rijen blijven hangen.

**Wanneer je dit niet wilt**: real data uit OCI/AWS — gebruik dan Optie A
(productie-pijplijn) of Optie C (shortcut).

### Optie A — dbt-fabricspark target (analoog aan UC-11)

UC-11 draait z'n marts al via een `fabric_dev` dbt-target op Fabric Spark (zie
`uc11_fabric.py` DAG). Voeg UC-12 toe aan dezelfde target:

1. Open `infrastructure/airflow/dbt/profiles.yml`, controleer dat de
   `fabric_dev`-target naar `uc11_lakehouse` schrijft.
2. `dbt run --target fabric_dev --select tag:uc12` (lokaal of via KPO).
3. De `mart_uc12_focus_*` tabellen verschijnen onder `dbo` in het lakehouse.

Caveat: de FOCUS-bron-tabel (`bronze.finops.focus_billing`) leeft op MinIO/Trino,
dus dbt-fabricspark heeft een aparte source-mapping nodig of een synthetic-
seed-stap. Zie het volgende blok.

### Optie B — synthetic seed-notebook in Fabric

Snelste pad om de Power BI-rapportage te demoën zonder de lokale pipeline te
draaien. Plan voor v1.1:

1. Upload `scripts/finops-generate-focus-csv.py` als helper.
2. Maak een notebook `uc12_focus_seed` in de Fabric workspace dat:
   - Synthetic FOCUS-data genereert (zelfde generator als lokaal)
   - `bronze.focus_billing` als Delta-tabel schrijft
   - De 5 marts opbouwt als directe Spark-SQL queries
3. Trigger 'm via de bestaande `fabric_helpers.trigger_notebook` zoals UC-11
   doet voor `uc11_seed_bronze`.

(Dit deel is nog **TODO** — de upload-flow + report rendert zodra de tabellen
er zijn. Tot dan tonen de visuals "No data" maar het schema klopt en RLS-
testen kunnen al beginnen.)

### Optie C — OneLake shortcut naar de MinIO-marts

Cross-cloud shortcut van `s3://warehouse/gold/uc12_focus_finops/*` naar
`Tables/uc12_focus_finops/*` in `uc11_lakehouse`. Voorbeeld in
[FreshLakehouse/docs/research](https://github.com/FreshMinds_Programming/FreshDataPlatform/blob/main/FreshLakehouse/docs/research/powerbi-as-bi-and-self-service-layer.md).

Vereist een werkende S3-credential in Fabric (cross-tenant), en dan staat de
data automatisch in sync — geen DAG, geen dbt-run. Trade-off: query-latency
hoger dan native Delta in OneLake (cross-region read).

---

## 8. Refresh-strategie

Direct Lake heeft géén refresh-schedule nodig. De Fabric service "frame't" de
semantic model automatisch als de Delta-tabellen wijzigen (`automatic updates =
ON`, default).

Voor een force-refresh (na een ad-hoc seed) gebruik:

```bash
# Via Fabric REST
TOKEN=$(python3 -c "
import sys, os
sys.path.insert(0, 'platform/11-airflow/include')
os.environ.update({})  # alle FABRIC_* env-vars zijn al geladen
from fabric_helpers import get_token
print(get_token())
")
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "https://api.fabric.microsoft.com/v1/workspaces/$FABRIC_WORKSPACE_ID/semanticModels/7d480700-013b-4ab5-909a-d2ab17f93e26/refreshes" \
  -H "Content-Type: application/json" \
  -d '{"type":"Full"}'
```

Of via de Fabric UI: open het semantic model → **Refresh now**.

---

## 9. Embed in de portal

Het portal-shell heeft sinds 2026-05-24 een **Dashboarding**-rail-item onder
Observability met twee sub-items:

```
Dashboarding
 ├── Power BI   →  /embed/powerbi/   (link naar app.fabric.microsoft.com)
 └── Superset   →  /embed/superset/
```

Het Power BI-embed valt momenteel terug op een "Open in nieuw tabblad"-knop
omdat Microsoft een restrictieve `frame-ancestors` CSP-header stuurt. Voor
een ingebouwde iframe-ervaring is een Power BI Embedded SDK-integratie met
App-Owns-Data + GenerateToken-backend nodig — zie
[FreshLakehouse/docs/research/powerbi-as-bi-and-self-service-layer.md](https://github.com/FreshMinds_Programming/FreshDataPlatform/blob/main/FreshLakehouse/docs/research/powerbi-as-bi-and-self-service-layer.md)
Fase 4 voor de wiring.

---

## 10. Bekende beperkingen / TODO's

| Beperking | Status | Notitie |
|---|---|---|
| Data nog niet automatisch in `uc11_lakehouse` | DONE (synthetic) | `scripts/fabric-seed-uc12.py` seedt vanuit `data-generation/focus-test.csv` (553 rijen). Real-data flow via Optie A/C nog open. |
| Geen RLS in de semantic model | TODO | TMDL `role` rules later toevoegen — Finance-RBAC pas relevant bij prod |
| `Effective Cost Total` rolt op over alle `charge_category` (incl. Credits/Tax) | Bewust | Mirror van Superset; aparte measure voor "Usage-only" volgt bij behoefte |
| `definition.pbism` is minimaal (geen "settings.usePowerBIServiceColumns") | OK | Direct Lake auto-detecteert het lakehouse-schema bij de eerste query |
| Power BI Pro / PPU vereist voor ontwikkelaars die het report editen | OK | Service Principal heeft genoeg voor upload via REST |
| Datepicker-UX op `billing_month` heeft een gedragsbug bij DateTime-cast naar yyyy-mm | Minor | Workaround: in slicers expliciet hierarchy verbergen |

---

## 11. Verder lezen

- [UC-12 — Superset variant (de baseline)](uc12-focus-finops.md)
- [UC-11 — Multi-platform demo (Trino + Databricks + Fabric)](uc11-customer-journey-walkthrough.md) — zelfde Fabric-patroon, andere data
- [FreshLakehouse Power BI plan](https://github.com/FreshMinds_Programming/FreshDataPlatform/blob/main/FreshLakehouse/docs/research/powerbi-as-bi-and-self-service-layer.md) — de bredere keuze tussen Superset en Power BI
- [Fabric REST — semantic models](https://learn.microsoft.com/en-us/rest/api/fabric/semanticmodel)
- [Direct Lake overview — Microsoft Learn](https://learn.microsoft.com/en-us/fabric/fundamentals/direct-lake-overview)
