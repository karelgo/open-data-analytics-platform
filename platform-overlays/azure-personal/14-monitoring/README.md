# azure-personal/14-monitoring

Test-overlay for the alert-email-pijp tegen een eigen Azure-tenant —
in dit geval `freshminds.nl` / `dev-stackable-rg` / `acs`. Bedoeld
om te bewijzen dat Alertmanager → Azure Communication Services Email →
echte inbox werkt, zonder een Platform SMTP relay nodig te hebben.

## Hoe het verschilt van de andere overlays

| Overlay | Doel | SMTP-target |
|---|---|---|
| `platform/14-monitoring/` (base) | k3d-dev | MailHog in-cluster |
| `platform-overlays/aks/14-monitoring/` | production | `smtp-relay.uwv.nl:587` |
| `platform-overlays/azure-personal/14-monitoring/` | **persoonlijke test** | ACS Email + MailHog (parallel) |

Deze overlay **vervangt MailHog niet** — alerts gaan parallel naar beide.
Zo zie je in MailHog dat Alertmanager 'm aanmaakte én in je echte inbox
dat de Azure-route werkt.

## One-off: Azure-resources + Entra-app

Resources `emailcs` (Email Communication Services + AzureManaged
sender-domain) en `acs` (Communication Services) zijn al aangemaakt
in `dev-stackable-rg`. Voor SMTP-auth is nog een Entra-app + client-
secret + Contributor-rol op `acs` nodig.

### Optie A — CLI (als Graph wél bereikbaar is)

```bash
az login --scope https://graph.microsoft.com//.default
bash scripts/azure/setup-acs-email-test.sh
```

Doet alles automatisch. Idempotent — her-run rolt secret + overschrijft
overlay + k8s-Secret.

### Optie B — Portal (als Graph geblokkeerd is door Conditional Access)

CA-policies van `freshminds.nl` blokkeren Graph-tokens via CLI. De
portal-MFA-flow voldoet wél aan de policy, dus daar pak je het op.

**B.1 — App registration aanmaken**

[Entra ID → App registrations → + New registration](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/CreateApplicationBlade)

- **Name**: `odap-platform-alertmanager-smtp`
- **Supported account types**: *Accounts in this organizational directory only (single tenant)*
- **Redirect URI**: leeg
- → **Register**

Op de Overview-pagina kopieer de **Application (client) ID** (uuid).
De Service Principal in *Enterprise applications* wordt automatisch
aangemaakt — niet apart doen.

**B.2 — Client secret genereren**

In de app → **Certificates & secrets → + New client secret**.
Description `alertmanager-smtp`, expiry 12 maanden, **Add**.

Kopieer **direct** de waarde from the kolom **Value** (NIET *Secret ID*) —
die verdwijnt na page-refresh.

**B.3 — Contributor-rol op `acs`**

[dev-stackable-rg → acs](https://portal.azure.com/#@freshminds.nl/resource/subscriptions/4910a5a6-aec6-405d-9294-c7f2845512a4/resourceGroups/dev-stackable-rg/providers/Microsoft.Communication/communicationServices/acs/overview) →
**Access control (IAM) → + Add → Add role assignment**:

- Role tab: zoek `Contributor` → select → Next.
- Members tab: *User, group, or service principal* → **+ Select members** →
  typ `odap-platform-alertmanager-smtp` → select → Select.
- Review + assign → Review + assign.

**B.4 — Finaliseer in repo**

```bash
bash scripts/azure/setup-acs-email-test.sh \
  --app-client-id <APPLICATION_CLIENT_ID_UIT_B.1> \
  --client-secret '<VALUE_UIT_B.2>'
```

Script slaat alle Graph-calls over en doet alleen:
- SMTP-username samenstellen (`acs.<app-id>.<tenant-id>`)
- `alertmanager-add-acs.yaml` patchen met die username
- k8s-Secret `alertmanager-receivers` patchen met `smtp_password_acs`

## Activeren in k3d

```bash
# Normale dev-deploy (start MailHog + Alertmanager etc.)
make deploy MODE=k3d

# Schakel de azure-personal overlay erover heen
kubectl apply -k platform-overlays/azure-personal/14-monitoring/

# Verstuur synthetische alert
make alert-test
```

Verwacht:

- **MailHog**: `https://mailhog.odap.local:8443/` → mail #1
- **Echte inbox**: `karel.goense@freshminds.nl` → subject begint met
  `[ACS-test FIRING] SyntheticTestAlert`

Beide binnen ~30s.

## Debuggen

```bash
# Alertmanager-logs (zoekt naar SMTP-fouten)
kubectl -n odap-monitoring logs -l app.kubernetes.io/name=alertmanager \
  --tail=200 | grep -iE 'smtp|tls'

# Verifieer dat de overlay correct rendered
kubectl kustomize platform-overlays/azure-personal/14-monitoring/ \
  | grep -A 10 'smtp.azurecomm.net'

# Check dat secret-key bestaat
kubectl -n odap-monitoring get secret alertmanager-receivers \
  -o jsonpath='{.data.smtp_password_acs}' | base64 -d | wc -c
```

Veelvoorkomende fouten:

| Fout | Oorzaak |
|---|---|
| `535 5.7.139 SMTP AUTH failed` | client-secret in k8s-Secret komt niet overeen met Entra-app. Re-run het script. |
| `550 5.7.1 Sender address is not authorized` | `from:`-domain wijkt af van de Azure-managed-domain. Check `alertmanager-add-acs.yaml`. |
| `Unable to connect to smtp.azurecomm.net:587` | Egress-firewall blokkeert SMTP-uitgaand op 587. Test met `kubectl run -it --rm test --image=busybox -- nc -vz smtp.azurecomm.net 587`. |
| Alert komt in MailHog maar niet in Azure-inbox | Het Entra-app heeft de Contributor-rol nog niet op `acs`. `az role assignment list --assignee <app-id> --scope <acs-id>`. |

## Cost

ACS Email free tier: **250 mails/dag** gratis. Boven dat ~€0.00025/mail.
Test-runs blijven ruim binnen gratis.

## Opruimen

```bash
# Verwijder de overlay-config from the cluster (laat base intact)
kubectl delete -k platform-overlays/azure-personal/14-monitoring/

# Of nuke alle Azure-resources
az group delete --name dev-stackable-rg --yes  # ALS er niets anders in zit
az communication delete   --name acs       --resource-group dev-stackable-rg --yes
az communication email delete --name emailcs --resource-group dev-stackable-rg --yes
az ad app delete --id "$(az ad app list --display-name odap-platform-alertmanager-smtp --query '[0].appId' -o tsv)"
```
