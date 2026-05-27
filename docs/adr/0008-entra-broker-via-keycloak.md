# ADR-0008: Microsoft Entra ID via Keycloak-brokering (i.p.v. parallelle IDPs)

| Status | **Geaccepteerd** |
|---|---|
| Datum | 2026-05-05 |
| Beslissers | Platform Architect, IAM, Security |
| Gerelateerd | [ADR-0001](0001-stackable-as-base.md) (Stackable als basis), [`platform/02-authentication/`](../../platform/02-authentication/), [referentiearchitecture § Centraal IdP](../../referentiearchitecture-odap-data-analytics.md) |

---

## Context

Het platform draait Keycloak als centrale OIDC-provider met 11 realm-rollen
en 7 OIDC-clients (MinIO, Trino, Superset, Airflow, NiFi, OpenMetadata,
Portal — zie [`realm.json`](../../infrastructure/helm/keycloak/realm.json)).
Trino, Superset, Airflow en NiFi consumeren dat via één Stackable
[`AuthenticationClass keycloak`](../../platform/02-authentication/authenticationclass-keycloak.yaml).
OPA-policies lezen `input.context.identity.groups` ([`trino-base.rego`](../../opa-policies-src/trino/trino-base.rego))
en mappen die naar
[`role_mappings.json`](../../opa-policies-src/data/role_mappings.json).

UWV's strategische identitys-stack is **Microsoft Entra ID**. De
referentiearchitecture ([§ Centraal IdP](../../referentiearchitecture-odap-data-analytics.md))
benoemt expliciet "**Entra ID** of Keycloak met SAML/OIDC" — beide zijn
kandidaten, niet beide zijn nodig.

De vraag: **kunnen Entra-medewerkers en interne ODAP realm-accounts naast
elkaar sign in on the platform, with a keuze on the loginpagina?**

## Beslissing

**Ja, via Keycloak Identity Brokering.** Entra ID wordt geconfigureerd
als externe **Identity Provider** binnen het bestaande `uwv` realm
(alias `entra`, `providerId: "oidc"`). Op de Keycloak-loginpagina toont
Keycloak automatisch een knop **"Microsoft Entra ID"** naast het
username/password-veld. De gebruiker kiest:

- **Lokaal platform account** → standaard Keycloak-flow (zoals nu).
- **Microsoft Entra ID** → redirect naar `login.microsoftonline.com`,
  Entra authenticeert (incl. eigen MFA / Conditional Access), Keycloak
  ontvangt een Entra-token, mapt Entra-security-group-GUIDs on the 11
  realm-rollen via `oidc-role-idp-mapper`, en geeft een gewoon
  Keycloak-token uit aan de downstream service.

Downstream services (Trino, Superset, Airflow, NiFi, OpenMetadata,
Portal, OPA-policies) blijven **onveranderd** — ze zien Keycloak-tokens
met dezelfde 11 realm-rol-claims als voorheen.

## Overwogen alternatieven

### Alt-A: Twee parallelle AuthenticationClasses (Keycloak + Entra naast elkaar in Stackable)

Stackable's `clusterConfig.authentication` is een **lijst** ([`trinocluster.yaml:29-31`](../../platform/09-trino/trinocluster.yaml#L29))
en kan meerdere IDPs accepteren. We zouden een tweede
`AuthenticationClass entra-id` aanmaken met Entra als OIDC-provider
en die toevoegen aan elke cluster-CRD.

**Niet gekozen omdat:**
- **Portal-laag breekt.** [`oauth2-proxy`](../../platform/15-portal/configmap-oauth2-proxy.yaml) ondersteunt
  maar één `oidc_issuer_url` per instance. Twee parallelle IDPs vereisen
  twee oauth2-proxy-deployments achter een ingress-rule + IDP-keuzepagina
  in [`Layout.astro`](../../portal/src/layouts/Layout.astro). Inschatting: 1-2 weken werk + permanente operationele complexiteit.
- **OpenMetadata accepteert maar één issuer** ([`infrastructure/helm/openmetadata/values.yaml`](../../infrastructure/helm/openmetadata/values.yaml)
  `authentication.oidcConfiguration`). Geen native multi-IDP-support.
- **OPA mapping verdubbelt.** `role_mappings.json` zou ofwel Entra-GUIDs
  moeten herkennen, ofwel een tweede mapping-bestand vereisen.
- **Sessiebeheer en cookies** worden complex bij twee parallelle proxies
  op hetzelfde cookie-domain.

### Alt-B: Entra ID volledig vervangt Keycloak

Verwijder Keycloak, point alle Stackable-services naar Entra ID direct.

**Niet gekozen omdat:**
- **Geen lokale dev-accounts.** De 11 realm-test-users in
  [`realm.json`](../../infrastructure/helm/keycloak/realm.json) (één per rol)
  geven een reproduceerbare dev/demo-omgeving zonder Azure-tenant-access.
- **MinIO-policy-claim mapping.** Keycloak's `minio-policy` mapper
  (oidc-usermodel-attribute-mapper, [`realm.json:339-348`](../../infrastructure/helm/keycloak/realm.json))
  kent MinIO-S3-policies toe op user-attribute-niveau. Entra ondersteunt dit
  niet zonder een Graph-API-shim.
- **Vendor lock-in (R-NORA-05).** Keycloak is open source en draagbaar; een
  pure Entra-stack koppelt de hele platform-auth aan één leverancier.
- **Break-glass.** Keycloak-realm-accounts blijven ook bruikbaar als de
  Azure-tenant onbereikbaar is (incident-scenario).

### Alt-C: SAML i.p.v. OIDC tussen Keycloak en Entra

Entra ondersteunt SAML 2.0 als alternatief voor OIDC.

**Niet gekozen omdat:**
- OIDC v2.0 sluit aan on the bestaande OIDC-stack (alle clients zijn OIDC).
- SAML-attribuut-mapping is verboser dan OIDC-claim-mapping.
- Geen functionele voordelen voor onze use case; SAML is alleen interessant
  als Entra OIDC zou ontbreken.

## Consequenties

### Positief

1. **Nul wijziging downstream.** AuthenticationClass, oauth2-proxy,
   OPA-policies, Stackable cluster-CRDs en de portal-Astro-app blijven
   ongewijzigd. Audit-impact: minimaal.
2. **Userskeuze op één pagina.** Keycloak's loginscherm rendert
   automatisch beide opties.
3. **MFA delegatie.** Entra Conditional Access kan MFA afdwingen voor
   `platform_admin`-groep zonder dat Keycloak-policies dat per gebruiker
   moeten regelen.
4. **Eén plek voor rol-mapping.** De 11 `oidc-role-idp-mapper`-entries in
   [`realm.json`](../../infrastructure/helm/keycloak/realm.json) zijn de
   enige plek waar Entra-group-GUIDs op platform-rollen mappen.
5. **Reversibel.** Brokering uitschakelen = `enabled: false` op de
   IdentityProvider; lokale users blijven werken.

### Negatief / risico's

1. **Account-takeover via "first broker login"-flow.** Als Keycloak's
   default flow op `Auto link` staat, kan een Entra-user met dezelfde
   email als een lokale realm-user dat account overnemen. **Mitigatie:**
   we gebruiken de default `first broker login`-flow met handmatige review;
   `Auto link` blijft uit.
2. **Group-overage claim.** Een Entra-user die in >200 groups zit krijgt
   geen `groups`-array in z'n token, maar een `_claim_names` overage. De
   role-mapper faalt dan stilletjes en de gebruiker komt rolloos binnen.
   **Mitigatie:** dedicated `platform-role-*`-security-groups gebruiken (niet
   alle UWV-groepen federen) — gedocumenteerd in [README](../../platform/02-authentication/README.md).
3. **GUID-drift per omgeving.** Group-GUIDs verschillen tussen dev/acc/prod
   tenants. **Mitigatie:** kustomize-overlay per omgeving (out-of-scope
   voor deze branch — placeholders staan klaar).
4. **Keycloak wordt single-point-of-failure.** Was het al, wordt
   onveranderd.
5. **Licentie/SSO-tier in Entra.** Group claims via OIDC vereisen geen
   premium-licentie, maar Conditional Access wel (Azure AD P1+). Out of
   scope voor deze ADR.

## Implementatie

| # | Stap | Bestand |
|---|------|---------|
| 1 | `identityProviders[]` met alias `entra`, OIDC v2.0 endpoints | [`infrastructure/helm/keycloak/realm.json`](../../infrastructure/helm/keycloak/realm.json) |
| 2 | 11× `oidc-role-idp-mapper` (group-GUID → realm-rol) + username-mapper + TOTP-trigger voor `platform_admin` | zelfde bestand, `identityProviderMappers[]` |
| 3 | `Secret keycloak-entra-broker` in `odap-auth` met `tenantId`, `clientId`, `clientSecret` | [`platform/01-secrets/dev-secrets.yaml`](../../platform/01-secrets/dev-secrets.yaml) |
| 4 | Keycloak-pod env-vars uit Secret (`ENTRA_*`, `optional: true`) | [`infrastructure/helm/keycloak/values.yaml`](../../infrastructure/helm/keycloak/values.yaml) |
| 5 | Setup-doc + bekende valkuilen | [`platform/02-authentication/README.md`](../../platform/02-authentication/README.md) |
| 6 | Smoke-test stub | [`scripts/test-entra-sso.sh`](../../scripts/test-entra-sso.sh) |

## Validatie / DoD

- [ ] Entra app-registration aangemaakt in een UWV test-tenant; redirect
      URI gewhitelisted.
- [ ] 11 `platform-role-*` security-groups aangemaakt en GUIDs in
      `realm.json` ingevuld (geen `REPLACE_ME_*` meer).
- [ ] Keycloak gestart, IdP `entra` zichtbaar in Admin UI.
- [ ] Eén Entra-testaccount logt in op portal en krijgt rolbadge
      (`claims_analyst`).
- [ ] Eén ODAP realm-account logt parallel in en blijft werken.
- [ ] Trino-CLI met Entra-user kan een SELECT op `bronze.persoon.persoon`
      uitvoeren met dezelfde row/column-policies als de equivalente
      lokale rol.
- [ ] OPA decision-log toont `input.context.identity.groups: ["claims_analyst"]`
      for the Entra-user.

## Open vraagstukken

1. **eHerkenning/DigiD-broker** — toekomstig; vergelijkbare aanpak (extra
   IdentityProvider in `uwv` realm).
2. **Account-link UI** — moet UWV-medewerkers de mogelijkheid bieden om
   hun bestaande realm-account te koppelen aan hun Entra-identity, voor
   geleidelijke migratie. Out-of-scope voor deze branch.
3. **Logout-flow** — Entra logout invalideert de Keycloak-sessie niet
   automatisch (single-logout vereist back-channel-config). Acceptabel
   voor dev, production eis nog te bepalen.
