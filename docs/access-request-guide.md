# Access request tot data — usersgids

Praktische gids for the request van access to a dataset on the platform
data-platform. Architecture: zie [ADR-0008](adr/0008-self-service-data-access.md).
Bridge-service: zie [platform/18-om-access-bridge/](../platform/18-om-access-bridge/README.md).

> **De bridge wordt automatisch meegedeployd** als laatste stap van
> `make deploy-platform` (zodra OpenMetadata het admin-JWT-secret heeft
> gepubliceerd). Op een verse k3d/AKS-cluster verwacht je hem live te
> zien als `kubectl -n odap-platform get deploy om-access-bridge`.
> Bij een hibernated SKE-cluster of als je `SKIP_OM_BRIDGE=1` hebt
> gezet, draai 'm los met `make deploy-om-bridge` (zie
> [scripts/deploy-platform.sh](../scripts/deploy-platform.sh)). Het
> portal-formulier én de handmatige OM-flow gaan beide stuk zonder de
> bridge — je submit zal 404/502 geven of je Task blijft hangen zonder
> grant.

---

## TL;DR — 30 seconden (portal-flow)

1. Open Mijn workspace → scroll naar **"Andere data nodig?"** → klik **"Vraag access aan"**.
2. Vul het formulier in: dataset-FQN, usersnaam, purpose-limitation, motivatie.
3. Submit. De portal maakt namens jou een Task aan in OpenMetadata en stuurt 'm to the owner.
4. Bij approval krijg je automatisch de rol `data_access:<catalog>.<schema>` toegekend.

Direct: `https://platform.odap.local:8443/access-request`.

> Liever handmatig in OpenMetadata? Dat kan ook — zie [§ Handmatige variant](#handmatige-variant-direct-in-openmetadata) onderaan.

---

## Wat is "access request" hier?

Het ODAP platform gebruikt **default-deny** met purpose-limitation (R-AVG-06). Jouw
primaire rol (`claims_analyst`, `marketing_analyst`, `researcher`, …)
bepaalt welke catalogs/schemas je *standaard* mag zien. Als je daarnaast
access nodig hebt tot een andere zone — bv. `gold.uc05_customer_360` —
loopt dat via deze flow:

1. Jij maakt een Task on the asset in OpenMetadata.
2. De Owner/Reviewer keurt de Task goed.
3. De **om-access-bridge** vertaalt de approval naar een realm-role
   `data_access:<catalog>.<schema>` in Keycloak.
4. OPA-Rego herkent die rol als grant; Trino laat de query door zolang je
   een purpose-limitation-purpose declareert die on the granted resource staat.

De grant geldt op **schema-niveau** (catalog.schema), niet per tabel.

---

## Portal-flow (aanbevolen)

### 1. Open het access-request-formulier

Via Mijn workspace → sectie *"Andere data nodig?"* → knop **"Vraag
access aan"**. Of direct: <https://platform.odap.local:8443/access-request>.

### 2. Vul de velden in

| Veld | Wat je invult |
|---|---|
| **Welke dataset?** | OM-FQN — bv. `trino.gold.uc11_customer_journey.mart_uc11_journey_events`. Vind 'm via OpenMetadata → Explore → klik on the asset → kopieer de FQN onder de titel. |
| **Wie ben je?** | Je Keycloak-usersnaam (eerste deel van je e-mail, bv. `researcher`, `finance.analyst`). |
| **Voor welk doel?** | Kies een purpose-limitation (GDPR Art. 5(1)(b)). |
| **Hoe lang?** | Optioneel — bv. "2 maanden, t/m 2026-08-01". |
| **Motivatie** | Korte uitleg: project, waarom de bestaande aggregaten niet volstaan, etc. |

### 3. Verzend

De portal maakt namens jou een Task aan in OpenMetadata, met
**`Request Access`** automatisch in de description en de owner van het
asset als assignee. Je ziet meteen of het gelukt is + de Task-ID.

### 4. Wat ziet de Reviewer?

De Owner/Reviewer:
- Krijgt notificatie in OM (Activity Feed van het asset + **My Data**).
- Klikt **Accept Suggestion** of **Resolve → Approved**.
- Bij Reject: motivatie in een comment; geen grant.

### 5. Bij approval — automatisch

1. OM publiceert een `taskResolved`-event to the [om-access-bridge](../platform/18-om-access-bridge/) (HMAC-signed).
2. Bridge parsed het asset FQN → `<catalog>.<schema>` → ensures realm-role `data_access:<catalog>.<schema>` in Keycloak en kent 'm aan jou toe.
3. Bij je volgende JWT-refresh (binnen 15 min) zit de nieuwe rol in je token.
4. OPA-Rego accepteert de rol als grant; purpose-limitation moet kloppen with the purposes die op die resource staan (zie [data.json](../platform/10-opa/policies/data.json) → `resource_purposes`).

---

## Voorbeelden

### Voorbeeld 1 — Researcher wil naar UC-11 customer journey-mart

```
Asset:      trino.gold.uc11_customer_journey.mart_uc11_journey_events
Requester:  researcher
Purpose:    onderzoek
Duration:   2 maanden, t/m 2026-08-01
Motivation: UC-11 funnel-analyse — afsluitratio per kanaal. Synthetische
            cohort + aggregaten, geen individuele BSN's.
```

Grant na approval: realm-role `data_access:gold.uc11_customer_journey`.

> ⚠️ **Heads-up:** deze specifieke `mart_*` tabel heeft lineage geregistreerd
> in OM en raakt op OM 1.12 momenteel de OpenSearch lineage-script bug —
> de approval-PUT geeft 500. Zie de FAQ "Mijn aanvraag op een
> `mart_*` of `uc11_*` tabel faalt met 500" onderaan for the workaround
> (admin kent de role handmatig toe). Een staging/silver-tabel uit
> dezelfde catalog werkt nu wél foutloos via dezelfde grant.

### Voorbeeld 2 — Finance Analyst wil bronze-data voor reconciliatie

```
Asset:      trino.bronze.policies.holders
Requester:  finance.analyst
Purpose:    kwaliteitscontrole
Duration:   2 weken
Motivation: Q2 bronze-reconciliatie — silver/gold-aggregaten checken
            tegen bronze na Q2-ETL-incident.
```

Grant: `data_access:bronze.demo`.

---

## Handmatige variant (direct in OpenMetadata)

Voor wie liever in OM blijft, of voor scriptbare scenario's: dezelfde
flow handmatig.

1. Open <https://openmetadata.odap.local:8443>.
2. Sidebar links → **Explore** → filter Tables → zoek dataset.
3. Op asset-pagina: tab **Activity Feed** → **+ Add Task** → **Request Description**.
4. **Description (of message of taskName) bevat ergens `Request Access`** —
   case-insensitive, hoeft niet aan het begin. Anders triggert de bridge
   niet (zie `_parse_grant` "convention guard").
5. Assignee = de Owner / Reviewer rechts on the asset-pagina. Is dat een
   team zonder users in OM? Set dan een persoon als secundaire owner;
   de portal-flow expandeert dat automatisch, de handmatige niet.
6. Submit. Verder loopt het identiek aan de portal-flow.

> De portal-flow doet stap 3–5 voor je en voorkomt dat je de
> "Request Access"-string vergeet (anders blijft de Task hangen).

---

## Veelgestelde vragen

**Hoe lang duurt het for the grant actief is?**
Zodra de Task is gesloten met Approved: binnen seconden in Keycloak,
binnen één JWT-refresh in Trino (≤ 15 min, of forceer met logout-login).

**Kan ik mijn grants zien?**
Ja — in OpenMetadata onder je profiel zie je je rollen (via SSO). Of in
Keycloak: open `/realms/odap/account/` en bekijk de "Roles" sectie.

**Hoe trek ik een grant in?**
Vraag een platform-admin om de `data_access:<...>`-rol uit Keycloak te
verwijderen. Een automatische intrekkings-flow (TTL op grant) staat als
follow-up in [docs/improvements.md](improvements.md).

**Wat als de Owner/Reviewer niet reageert?**
Default-SLA: 5 werkdagen. Daarna mag je platform-admin escaleren. (Een
SLA-DAG op open Tasks is een open issue.)

**Aan wie wordt mijn Task toegewezen als de owner een team is?**
Veel datasets hebben een **team/group als owner** (bv. `divisie_customer interaction`)
in plaats van een persoon. De portal-flow expandeert team-owners
automatisch naar hun users. Als de owner-team géén users heeft
gekoppeld in OM, valt de bridge terug op `data.steward` zodat de Task
niet ongeassigned blijft hangen. Wil je dat van een specifiek persoon
afhangen? Zet die persoon expliciet als owner on the asset in
OpenMetadata.

**Mijn aanvraag op een `mart_*` of `uc11_*` tabel faalt met "500 server
error" tijdens approval — wat is dat?**
Bekend probleem in OM 1.12 op assets **met lineage of data-products**:
de `PUT /api/v1/feed/tasks/{id}/resolve` API gooit een
`script_exception` on the OpenSearch lineage-index, en de Task wordt niet
afgesloten → geen webhook → geen grant. Tijdelijke workaround tot OM-fix:
laat de platform-admin het Keycloak realm-role
`data_access:<catalog>.<schema>` with the hand toekennen. Tracking:
[OS lineage script bug — onderzoekstaak (open)](improvements.md).
Niet-lineage assets (bv. staging-tabellen in `bronze`/`gold.crm`) werken
zonder probleem.

**De bridge zegt 400 op mijn Task — wat ging er fout?**
Vier veelvoorkomende oorzaken:

| Status / log-bericht | Wat te doen |
|---|---|
| `Task is niet als access-request gemarkeerd` | Voeg `Request Access` toe aan de description en re-submit. |
| `Asset FQN ... niet bruikbaar` | Asset is geen Trino-table. Alleen `trino.<catalog>.<schema>.<table>` of de OM entity-ref `<#E::table::...>` wordt herkend; voor andere asset-types (Topics, Dashboards) is dit pad nog niet ondersteund. |
| `Task niet approved/closed` | Reviewer heeft de Task gesloten met **Reject** (eventType `taskClosed`) i.p.v. **Accept Suggestion** (eventType `taskResolved`). Maak een nieuwe Task. |
| `HMAC-signature klopt niet` | Bridge-secret in `om-access-bridge-secret` matcht niet met OM's stored secret. Run `make deploy-om-bridge` om beide opnieuw te bootstrappen. |

---

## Voor reviewers — wat doe ik?

Als Owner/Reviewer van een dataset:

1. Je krijgt notificatie in OM bij een nieuwe access-request Task.
2. Bekijk de description: wie vraagt, waarvoor, hoe lang.
3. Check of de aanvrager de purpose mag declareren (zie
   [trino-purpose-limitation.rego](../opa-policies-src/trino/trino-purpose-limitation.rego))
   — als de aanvrager's primaire rol de purpose niet kent, helpt de grant
   niet en moet je afwijzen of escaleren.
4. Klik **Accept Suggestion** (≡ `PUT /tasks/{id}/resolve` → fires
   `taskResolved` → bridge kent de role toe).
5. Vermeld in een comment de geldigheidsduur (audit-trail).

**Voor afwijzing:** gebruik **Close** (een andere knop / actie, niet
"Resolve") en zet een motivatie in een comment. Onder de motorkap is
dat `PUT /tasks/{id}/close` → fires `taskClosed`. De bridge negeert
`taskClosed`-events expliciet, dus er volgt géén grant — perfect voor
audit-trail "aanvraag afgewezen". Vermijd "Resolve" for a rejection,
want dat zou de role wél toekennen.

---

## Voor ontwikkelaars — pad voor uitbreiding

- **Native access-request-task-type benutten**: OM draait inmiddels op
  **1.12.8** (zie [platform/13-openmetadata-config/](../platform/13-openmetadata-config/)).
  Het 1.6+ gat dat in ADR-0008 als "out of scope" stond is dus open — te
  onderzoeken of OM 1.12 een native task-type/API biedt dat de bridge
  kan consumeren in plaats van de string-match op `Request Access` in
  de description. Tot dat onderzoek af is, blijft de huidige convention
  guard leidend.
- **Portal-formulier** dat de Task automatisch aanmaakt (optie B uit
  ADR-0008 follow-up): heeft een ADR-0009 nodig.
- **TTL op grants**: dagelijkse CronJob die `data_access:*` rollen ouder
  dan X weken intrekt. Mooie eerste-uitbreiding.
- **Inzage/wisrecht (R-AVG-10)**: dit is een **andere** flow — gebruiker
  vraagt inzage in eigen data, niet access tot een dataset. Zie
  `gdpr_request`-DAG in [docs/improvements.md](improvements.md).
