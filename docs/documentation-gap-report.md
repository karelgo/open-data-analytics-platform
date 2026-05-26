# Documentation gap report — UDP_Stackable

Audit datum: 2026-05-05. Scope: alle bestanden onder `UDP_Stackable/`,
exclusief `dbt_packages/`, `node_modules/`, `dist/`, `.git/`.

> **Update 2026-05-05 (zelfde sessie):** items A.1, A.2, A.3, A.4, A.6 en B.1
> zijn opgelost. Zie ✅-markeringen hieronder.

Het platform is over het algemeen **goed gedocumenteerd**: 16/16 platform-
componenten hebben een README, 6 ADR's leggen kernkeuzes vast, en alle
10 use-cases hebben een spec. Onderstaande lijst is wat (nog) ontbreekt of
afwijkt van wat je elders in de repo wel hebt staan.

---

## A. Top-level / project-niveau

Veel directories op het root-niveau hebben geen README terwijl hun
buurman dat wel heeft. Voor een referentie-implementatie waar lezers vaak
"hoe lees ik deze map" als eerste vraag stellen, is dit de grootste gap.

| # | Pad | Wat ontbreekt | Prio |
|---|---|---|---|
| A.1 ✅ | `platform/README.md` | ~~Index-README voor de 16 genummerde componenten (00–15).~~ Toegevoegd. | 🟠 hoog |
| A.2 ✅ | `docs/README.md` | ~~Geen index voor `docs/`.~~ Toegevoegd. | 🟠 hoog |
| A.3 ✅ | `scripts/README.md` | ~~12 scripts zonder overzicht~~ — overzicht-tabellen + happy-path toegevoegd. | 🟠 hoog |
| A.4 ✅ | `tests/README.md` | ~~Drie sub-mappen zonder uitleg~~ — smoke/integration/e2e gedocumenteerd, conventies + CI-link toegevoegd. | 🟠 hoog |
| A.5 | `ci/README.md` | 6 GitHub-Actions workflows + `check-dbt-meta.py` zonder overzicht. Lezers moeten elk YAML-bestand openen om te begrijpen wat de pipeline doet. | 🟡 polish |
| A.6 ✅ | `opa-policies-src/README.md` | ~~Geen README ondanks Makefile + 5 policies + tests.~~ Toegevoegd: bundle-opbouw, rol-schema, Trino-spec-link. | 🟠 hoog |
| A.7 | `nifi-flows/README.md` | Alleen `templates/delta/` en `templates/iceberg/` hebben elk een README; de map daarboven niet — geen link tussen "welke variant gebruik je wanneer". | 🟡 polish |
| A.8 | `infrastructure/README.md` | Alleen `infrastructure/azure/` heeft een README. `helm/`, `k3d/`, `stackablectl/` zijn niet uitgelegd. | 🟡 polish |
| A.9 | `CONTRIBUTING.md` | Reeds op roadmap (improvements #1.18). Flow voor "ik wil een UC / generator / policy toevoegen" ontbreekt. | 🟡 polish |
| A.10 | `CHANGELOG.md` | Reeds op roadmap (improvements #1.17). Nu alleen `WORKLOG.md` als sessie-log — niet hetzelfde als een release-changelog. | 🟡 polish |
| A.11 | `.github/` (PR + issue templates) | Geen `.github/` map. Voor een reference-platform met meerdere bijdragers handig om PR-template + issue-templates (bug / use-case / ADR-voorstel) toe te voegen. | 🟡 polish |
| A.12 | `CODE_OF_CONDUCT.md` | Niet aanwezig. Voor een open-source-licentie (Apache 2.0) gebruikelijk maar optioneel. | ⚪ optioneel |

---

## B. dbt-laag

dbt is **goed** gedocumenteerd op staging- en marts-niveau (compliance-meta
in elke `_*.yml`). Onderstaande items vormen de openstaande gaten.

| # | Pad | Wat ontbreekt | Prio |
|---|---|---|---|
| B.1 ✅ | `dbt/dbt_project.yml` | ~~Config-gat~~ — `uc09_reint_effect` toegevoegd aan `models.odap_data_platform.marts.*`. | 🔴 blocker |
| B.2 | `dbt/macros/*.sql` | Geen enkele macro heeft een `{% docs %}` block. De 8 macros (`apply_doelbinding_tag`, `generate_database_name`, `generate_schema_name`, `pseudonymize`, `table_format`, `test_bsn_valid`, `test_iban_valid`, `test_lh_nummer_valid`) verschijnen daardoor leeg in `dbt docs generate`. | 🟠 hoog |
| B.3 | `dbt/tests/*.sql` | De 2 singular tests hebben header-comments maar geen schema-beschrijving en geen referentie vanuit `compliance-mapping.md`. UC-03-test (R-AI Act-relevant) verdient een expliciete koppeling. | 🟡 polish |
| B.4 | `dbt/snapshots/` | Lege map. Geen README of `.gitkeep`-uitleg of er bewust geen snapshots zijn (en zo ja, waarom — doelbinding? ARV-bewaartermijnen?). | 🟡 polish |
| B.5 | `dbt/models/marts/uc{02,03,08,10}*/` | 4 lege mart-mappen. Reeds op roadmap (improvements #1.1, #1.12). Documentatie-impact: lezers van `dbt_project.yml` zien geen schema-config en kunnen niet uit de map alleen opmaken of dit "TODO" of "intentionally placeholder" is. Een `_README.md` in elke lege map (één regel, "TODO fase X — zie use-case spec") helpt. | 🟡 polish |
| B.6 | `spark-jobs/README.md` (regel "lakehouse_maintenance.py — TBD fase 6") | **Stale:** `platform/11-airflow/dags/lakehouse_maintenance.py` bestaat al. README suggereert dat de taak nog open is. | 🟡 polish |

---

## C. Operationeel / runbook-niveau

| # | Pad | Wat ontbreekt | Prio |
|---|---|---|---|
| C.1 | `docs/runbook.md` | Zelf-aangegeven als "skeleton (fase 0)". Veel TODO-items. Acceptabel zolang het platform niet productie-rijp is, maar de TODO-secties in §2.2, §4.x verdienen tenminste verwijzing naar de bestaande `make`-targets en `scripts/doctor.sh`. | 🟠 hoog |
| C.2 | `docs/data-contracts.md` (nieuw) | Bronze-sources zijn beschreven in `dbt/models/staging/_sources.yml` (8 topics) en in NiFi-templates. Een gecombineerd "data contract"-document per `uwv.<domain>.<entity>`-topic — schema-evolutie-regels, eigenaar, SLA, voorbeelddata — ontbreekt. | 🟡 polish |
| C.3 | `docs/lineage.md` of diagram in `docs/architecture.md` | Lineage van Kafka-topic → bronze.uwv.* → silver.<domein>.* → gold.<uc>.* is impliciet (door dbt-refs), maar er is geen overzichtsdiagram. OpenMetadata genereert het runtime, maar een statisch fallback-diagram is handig voor lezers zonder cluster. | 🟡 polish |
| C.4 | `platform/13-openmetadata-config/ingestion-pipelines/` | Lege map (improvements #1.14). Verwacht: voorbeeld-pipeline-yaml's. | 🟡 polish |
| C.5 | Airflow DAGs (`platform/11-airflow/dags/`) | DAGs hebben docstrings ✓. Wat ontbreekt: een `README.md` in `dags/` met DAG-overzicht + schedule + eigenaar — handig voor data-stewards die de UI niet altijd open hebben. | 🟡 polish |
| C.6 | `docs/onboarding.md` (nieuw) | Voor nieuwe ontwikkelaars: prerequisites, eerste-week-pad ("clone → make cluster → make seed → eerste UC bekijken"). Nu verspreid over README + handleidingen. | 🟡 polish |

---

## D. Sterke punten (geen actie nodig)

Voor de volledigheid: deze onderdelen zijn **al goed**:

- 16/16 platform-componenten hebben een README met consistente structuur.
- 6 ADR's voor de kernkeuzes (Stackable, Iceberg-vs-Delta, OPA-authz,
  OpenMetadata-catalog, dbt-trino-transform, Delta-keuze).
- 10 use-case-specs onder `docs/use-cases/`, alle 10 voorzien van CGM-
  entiteiten en compliance-koppeling.
- 13 handleidingen onder `docs/handbooks/` (per persona) inclusief
  README-index.
- Compliance-mapping (NORA / AVG / BIO / NIS2 / AI Act) als één tabel.
- `WORKLOG.md` (54k regels) als sessie-log — uitstekend voor traceability,
  zij het geen vervanger van een CHANGELOG.
- `improvements.md` lijst de bekende gaps al expliciet (411 regels) — veel
  van bovenstaande items staan er al in.
- Top-level `README.md` is helder en volledig (snelstart + repo-layout-
  tabel + doc-index).
- dbt staging/marts schema-yml's bevatten compliance-meta (`legal_basis`,
  `doelbinding`, `bio_classificatie`, `bewaartermijn_jaren`, `risk_tier`,
  `pii_kolommen`, `cgm_entiteiten`).

---

## E. Aanbevolen volgorde

1. **B.1** dbt_project.yml uc09-config-fix (concrete bug, niet doc).
2. **A.1, A.2, A.3, A.4, A.6** — vijf README's die het meest aan
   onboarding en dagelijks gebruik bijdragen.
3. **B.2** macro-docs (`{% docs %}`) — verbetert `dbt docs generate`.
4. **C.1** runbook-skeleton invullen voor de paden die wél werken.
5. **A.7, A.8, A.5, B.3, B.4, C.5** — polish.
6. **A.9, A.10, A.11, C.2, C.3, C.6** — bestaande roadmap-items
   en/of langere termijn.
