# 02-authentication

Stackable AuthenticationClass voor de ODAP Keycloak realm + interne TLS-CA-secretclass.

| Resource | Doel |
|---|---|
| `AuthenticationClass keycloak` | OIDC-config voor Trino/Superset/Airflow/NiFi/OpenMetadata. Issuer: `https://keycloak.odap.local:8443/realms/odap`. |
| `SecretClass tls-internal` | Locatie voor het CA-cert dat de Keycloak-OIDC-endpoint heeft getekend. |

## CA distribution (TODO fase-1+)

Het CA-cert (`odap-platform-ca` Secret in `cert-manager`-namespace) moet
worden gekopieerd naar een Secret in `odap-platform`-namespace met label
`secrets.stackable.tech/class: tls-internal`. Twee opties:

1. **trust-manager** (`cert-manager.io/trust-manager`) Bundle-resource — propere oplossing; commit volgt in fase 3 zodra Trino het echt nodig heeft.
2. Tijdelijk: handmatige Secret-kopie in bootstrap.sh:

   ```bash
   kubectl get secret -n cert-manager odap-platform-ca -o jsonpath='{.data.ca\.crt}' \
     | base64 -d > /tmp/ca.crt
   kubectl -n odap-platform create secret generic odap-platform-ca-trust \
     --from-file=ca.crt=/tmp/ca.crt \
     --dry-run=client -o yaml \
     | kubectl label --local -f - secrets.stackable.tech/class=tls-internal -o yaml \
     | kubectl apply -f -
   ```

Wordt in fase 3 (Trino-deploy) volledig automatisch via trust-manager.

## Apply

```bash
kubectl apply -k platform/02-authentication/
```

---

## Entra ID brokering (feature/entra-id-broker)

Naast de Keycloak-eigen accounts kan het platform federeren met Microsoft
Entra ID. Architectuur: **Keycloak als IdP-broker** — Entra is een externe
Identity Provider in het `uwv` realm; downstream services (Trino, Superset,
Airflow, NiFi, OpenMetadata, Portal) blijven onveranderd Keycloak-tokens
zien. Op de Keycloak-loginpagina verschijnt een knop **"Microsoft Entra ID"**
naast het reguliere username/password-veld; de gebruiker kiest.

Zie [`docs/adr/0003-entra-broker-via-keycloak.md`](../../docs/adr/0003-entra-broker-via-keycloak.md)
voor de architectuurkeuze (broker vs. parallelle IDPs).

### Wat is in de repo gewijzigd

| Bestand | Wijziging |
|---|---|
| [`infrastructure/helm/keycloak/realm.json`](../../infrastructure/helm/keycloak/realm.json) | `identityProviders[0]` (alias `entra`, OIDC v2.0) + 13 `identityProviderMappers` (11 group→role, 1 username, 1 TOTP-trigger) |
| [`infrastructure/helm/keycloak/values.yaml`](../../infrastructure/helm/keycloak/values.yaml) | `extraEnvVars` uitgebreid met `ENTRA_TENANT_ID` / `ENTRA_CLIENT_ID` / `ENTRA_CLIENT_SECRET` (uit Secret) |
| [`platform/01-secrets/dev-secrets.yaml`](../01-secrets/dev-secrets.yaml) | `Secret keycloak-entra-broker` in `odap-auth` (placeholders) |

### Setup-stappen (eenmalig per omgeving)

#### 1. Azure app-registration

In de Azure portal (of via `az ad app create`):

```
Naam:           Open Data & Analytics Platform — Keycloak broker
Type:           Web
Redirect URI:   https://keycloak.odap.local:8443/realms/odap/broker/entra/endpoint
ID-token:       Aan (impliciet niet nodig; auth-code flow met PKCE)
```

API permissions (delegated):
- `openid`, `profile`, `email`, `offline_access` — Microsoft Graph
- `User.Read` — Microsoft Graph (default)
- `GroupMember.Read.All` — Microsoft Graph (admin consent vereist)

In het App-registration → Manifest:

```json
"groupMembershipClaims": "SecurityGroup"
```

(Dit zorgt dat security-group GUIDs in de `groups` claim van de id-token
komen — anders ontvangt Keycloak geen group-info en blijft de gebruiker
zonder rol.)

Maak een client secret aan onder **Certificates & secrets** en noteer de
**value** (niet de secret-ID).

#### 2. Group-GUIDs ophalen

Voor elke van de 11 platform-rollen moet er één Entra security-group
bestaan (idealiter `platform-role-{rolename}`). Vraag de GUIDs op:

```bash
az ad group show --group "platform-role-wia_beoordelaar" --query id -o tsv
# herhaal voor de andere 10 rollen
```

#### 3. Placeholders vervangen

Patch het realm-bestand met de echte waardes (Keycloak doet **geen** env-var
substitutie binnen `--import-realm` — de placeholders moeten letterlijk
vervangen worden vóór de import):

```bash
# tenant + client
sed -i.bak \
  -e "s/REPLACE_ME_ENTRA_TENANT_ID/$AZ_TENANT_ID/g" \
  -e "s/REPLACE_ME_ENTRA_CLIENT_ID/$AZ_CLIENT_ID/g" \
  -e "s/REPLACE_ME_ENTRA_CLIENT_SECRET/$AZ_CLIENT_SECRET/g" \
  infrastructure/helm/keycloak/realm.json

# group-GUIDs (één regel per rol)
for ROLE in wia_beoordelaar ww_handhaver wajong_arbeidsdeskundige \
            crm_medewerker fez_analist data_steward data_engineer \
            platform_admin researcher smz_planner proactief_dienstverlener; do
  GUID=$(az ad group show --group "platform-role-$ROLE" --query id -o tsv)
  sed -i.bak "s/REPLACE_ME_GROUP_GUID_$ROLE/$GUID/g" \
    infrastructure/helm/keycloak/realm.json
done

rm infrastructure/helm/keycloak/realm.json.bak
```

> **Productie:** vervang dit door een SealedSecret of External Secrets +
> Vault-injection, en gebruik de Keycloak Admin REST API (`PUT
> /admin/realms/odap/identity-provider/instances/entra`) om de IdP-config
> roterend bij te werken zonder realm-re-import.

#### 4. Deploy

```bash
helm upgrade --install keycloak bitnami/keycloak \
  -n odap-auth \
  -f infrastructure/helm/keycloak/values.yaml \
  --set-file extraDeploy[0]=infrastructure/helm/keycloak/realm.json
# of via je gebruikelijke 'make redeploy-keycloak'
```

Bij het herstarten van de Keycloak-pod wordt het realm opnieuw
geïmporteerd; de IdP `entra` verschijnt onder Realm settings → Identity
Providers en op de loginpagina.

### Verifiëren

Smoke-test:

```bash
./scripts/test-entra-sso.sh
```

Manueel:

1. Browse naar `https://platform.odap.local/` — oauth2-proxy
   redirect je naar Keycloak.
2. De Keycloak-loginpagina toont nu twee opties: username/password
   (interne platform accounts) of de knop **"Microsoft Entra ID"**.
3. Kies "Microsoft Entra ID" — wordt geredirect naar
   `login.microsoftonline.com`. Log in met een Entra-testaccount dat lid
   is van een van de 11 `platform-role-*` security-groups.
4. Eerste login: Keycloak's "first broker login"-flow vraagt of je het
   account wil koppelen aan een bestaand platform account (op email-match) of
   een nieuw lokaal account wil aanmaken. Voor een schone Entra-only flow:
   kies "Add to existing account" alleen als je dezelfde gebruiker al in
   de realm hebt; anders "Review profile" en doorgaan.
5. Eindresultaat: portal-topbar toont je rol-badge (bv. `wia_beoordelaar`)
   en je email — gefedereerd via Entra.

### Bekende valkuilen

| Probleem | Oplossing |
|---|---|
| Entra weigert `*.local` redirect | Gebruik in dev een echte test-tenant + ngrok-tunnel met publieke hostname; of een Azure dev-tenant met `*.localhost` whitelisted (recente Entra-update). |
| `groups` claim is leeg in token | Manifest `groupMembershipClaims: "SecurityGroup"` ontbreekt, of de gebruiker zit in >200 groepen → Entra zendt dan een `_claim_names` overage-claim. Optioneel: switch naar Graph API resolve. |
| Gebruiker heeft geen rol na login | GUID in realm.json matcht niet met groep-GUID in tenant. Check Keycloak Admin → Sessions → Last logged-in users → bekijk token. |
| MFA niet afgedwongen voor `platform_admin` | Keycloak's TOTP-policy geldt alleen voor lokale users. Voor brokered users moet **Entra Conditional Access** MFA afdwingen op de app-registration. De `entra-trigger-totp-for-platform-admin` mapper is een back-stop maar idealiter staat MFA al bij Entra. |
| `pkceEnabled: true` werkt niet | Sommige oudere Entra app-registrations hebben "Allow public client flows" nodig — staat default op `No`, laat dat ook zo voor confidential client. PKCE op confidential client is OK vanaf Keycloak 24. |
