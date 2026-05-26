# ADR-0008: Self-service data access via OpenMetadata + OPA-brug

| Status | **Geaccepteerd** |
|---|---|
| Datum | 2026-05-11 |
| Bijgewerkt | 2026-05-24 (versie-update) |
| Beslissers | Platform Architect, Data Office, CISO |
| Gerelateerd | ADR-0003 (OPA), ADR-0004 (OpenMetadata) |

> **Versie-update 2026-05-24** — OpenMetadata draait inmiddels op chart/app
> **1.12.8** (was 1.5.7 toen deze ADR werd geschreven). De convention guard
> hieronder blijft van toepassing zolang de bridge op de string
> `"Request Access"` matcht in de task-description. Onderzoek of OM 1.12 een
> native access-request-task-type biedt dat de bridge i.p.v. de string kan
> consumeren, staat als follow-up — zie
> [docs/access-request-guide.md](../access-request-guide.md) §Voor ontwikkelaars.

---

## Context

Het platform kent geen self-service mechanisme om data-toegang aan te vragen.
Een nieuwe gebruiker die toegang wil tot een specifieke dataset moet nu
buiten het platform om bij een platform-admin aankloppen — er is geen
audit-trail, geen reviewer-workflow en geen koppeling met R-AVG-06
(doelbinding) of R-AVG-10 (inzage).

Tegelijk staan twee bouwstenen al in de stack:

- **OpenMetadata 1.5+** als catalog (ADR-0004; deze repo draait op 1.12.8) —
  kent sinds 1.5+ een ingebouwde *Request Access*-flow met **Tasks**,
  **Conversations** en **Reviewers/Owners** op Glossary-terms en Data Assets.
- **OPA-Rego** als authorisatielaag voor Trino (ADR-0003) — leest realm-roles
  uit Keycloak via de `groups`-claim en doet daarmee RBAC, doelbinding,
  column-masking en row-filtering.

Wat ontbreekt is de **brug** tussen een goedgekeurde aanvraag in OpenMetadata
en een effectieve grant in OPA-Rego.

---

## Beslissing

**Self-service data access loopt via OpenMetadata-Tasks (conventie:
description bevat `Request Access`). Een nieuwe service `om-access-bridge`
vertaalt goedgekeurde Tasks naar realm-roles in Keycloak; OPA-Rego
herkent een `data_access:<catalog>.<schema>` rol als geldige grant en
accepteert de bijbehorende purposes.**

> **Conventie** — OM 1.5 heeft géén ingebouwd "Request Access"-task-type.
> We hergebruiken `RequestDescription` met een **convention guard** in de
> bridge: alleen Tasks waarvan de description of message de string
> `request access` (case-insensitive) bevat worden als grant verwerkt.
> Volledige UI-stappen + voorbeelden: [docs/access-request-guide.md](../access-request-guide.md).

Componenten:

1. **OpenMetadata config** — elke Glossary-term + Data Asset krijgt
   `reviewers` en een `owner`. De init-Job POST de reviewers nu ook mee
   (was eerder `name + description` only).
2. **`om-access-bridge`** — kleine FastAPI-service in
   `platform/18-om-access-bridge/`. Ontvangt OM webhook-events op
   `POST /webhooks/om`, valideert HMAC-signature, en bij `entityType=task` +
   `eventType=taskResolved` + `status=approved` patcht de target-user in
   Keycloak: nieuwe realm-role `data_access:<catalog>.<schema>` toevoegen.
3. **Keycloak** — nieuwe confidential client `om-access-bridge` met
   service-account + realm-management role `manage-users`. Geen
   user-attribute mapper nodig: de grant wordt een realm-role en komt via
   de bestaande `roles`-claim mee.
4. **OPA-Rego** — nieuwe policy `trino-data-access.rego`:
   - `role_allows_resource` accepteert óók grant-rollen
     (`data_access:<catalog>.<schema>`).
   - `user_allowed_purposes` voegt voor zo'n grant de purposes uit
     `resource_required_purposes` toe (de granted resource bepaalt zelf
     welke doelbinding-codes mogen).
5. **Portal** — knop *"Vraag toegang aan in de catalogus"* op
   `portal/src/pages/me.astro` deeplinkt naar OpenMetadata.

---

## Motivatie

- **Gebruikt wat er al staat.** OM-Tasks, Conversations en Reviewers zijn
  community-features (sinds 1.5). Geen extra UI-bouwwerk.
- **Audit-trail komt gratis mee.** Wie aanvroeg, wie approvde, wanneer —
  zit in OM's Task-historie + Keycloak's event log + OPA decision-log.
- **Eén bron-van-waarheid voor authorizatie.** OPA blijft policy-engine;
  grants worden Keycloak-realm-roles. Geen tweede policy-store.
- **Minimaal nieuwe operationele last.** Eén Python-service van <200 LOC,
  geen DB nodig (state zit in Keycloak), past in het bestaande
  `nanitics-observatory`-deploy-patroon (FastAPI + plain Deployment +
  kustomize).
- **Compliance-anchors.** R-AVG-06 (doelbinding) blijft afgedwongen via de
  bestaande `resource_required_purposes` mapping; R-AVG-10 (inzage en
  rectificatie) krijgt voor het eerst een platform-pad — de Task-history
  in OM is de audit-bron.

---

## Risico's en mitigaties

| Risico | Mitigatie |
|---|---|
| Webhook spoofing → ongeautoriseerde grants | HMAC-SHA256 op `X-OM-Signature`-header met shared secret in `om-access-bridge-secret`; tijdvenster ±5min; replay-protectie via processed-event-set in memory |
| Race conditions (parallelle approvals zelfde user) | Keycloak Admin API is idempotent op role-assign; bridge faalt fail-closed |
| Bridge offline tijdens approval | OM retried webhooks 3× exponential backoff; manual replay-endpoint `/replay/{task_id}` voor recovery |
| Grant-explosie (1 rol per catalog.schema-combi) | Conventie: rollen scopen op `<catalog>.<schema>`, niet per tabel; reviewer kan in OM één grant op glossary-term doen die meerdere assets dekt |
| Ongebruikte grants blijven hangen | TTL-veld in role-attributes (`grantedAt`, `expiresAt`) + dagelijkse cleanup-CronJob (out of scope deze ADR, separate improvement) |
| Geen self-registratie in Keycloak | Out of scope; nieuwe gebruikers komen via Platform IdP federatie (separate improvement). Voor dev-omgeving kan registratie via overlay aanstaan |

---

## Niet gekozen alternatieven

- **User-attribute + custom JWT-claim mapper.** Cleaner data-model maar
  vereist nieuwe `protocolMapper` op elke Trino-/Superset-client; Trino's
  OPA-plugin geeft niet alle JWT-claims door, alleen `groups` zit
  gegarandeerd in `input.context.identity.groups`. Realm-roles benutten
  dat bestaande pad zonder mapper-werk. Skip.
- **OPA-data-feed direct vanuit OM** (`reverse-metadata` of `om-export`).
  Vereist een extra ConfigMap-sync + bundle-rebuild per grant; verandert
  policy-data buiten Keycloak om wat audit-fragmenteert. Skip — Keycloak
  blijft single source of truth voor identity.
- **Apache Ranger overnemen.** Ranger heeft self-service ingebouwd maar
  conflicteert met ADR-0003. Skip.
- **Custom request-form in de portal.** Verdubbelt wat OM al biedt; meer
  code, eigen audit-store, geen connector naar Glossary/Data Assets.
  Skip — portal linkt naar OM in plaats van het na te bouwen.

---

## Implementatie-impact

- `platform/13-openmetadata-config/init-job.yaml` — POST `reviewers` +
  `owner` mee voor elke glossary-term (regel ~115).
- `platform/13-openmetadata-config/glossary-cgm.yaml` — `dataOwner` en
  `reviewers` per term waar relevant.
- `platform/18-om-access-bridge/` — nieuwe service-directory met
  `app/`, `deployment.yaml`, `service.yaml`, `configmap.yaml`,
  `secret.yaml`, `kustomization.yaml`.
- `infrastructure/helm/keycloak/realm.json` — nieuwe client
  `om-access-bridge` met `serviceAccountsEnabled: true` en
  `realm-management.manage-users` rol.
- `opa-policies-src/trino/trino-data-access.rego` — grant-policy
  `data_access:<catalog>.<schema>` rol-pattern.
- `opa-policies-src/trino/trino-data-access_test.rego` — unit-tests.
- `portal/src/pages/me.astro` — knop "Vraag toegang aan" in de hulp-sectie.
- `Makefile` — target `deploy-om-bridge` + smoke test
  `tests/smoke/10-om-access-bridge.sh`.
- `docs/improvements.md` — R-AVG-10 update (van 🔴 naar 🟠: GDPR-DAG nog
  open, access-request-pad nu wel aanwezig).
