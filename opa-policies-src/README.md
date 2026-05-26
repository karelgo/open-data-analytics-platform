# opa-policies-src/ — Rego policies voor Trino

Bron van de OPA-bundle die [Trino](../platform/09-trino/) gebruikt voor
authorisatie. Implementeert default-deny + vier authorisatie-lagen:
**rollen → doelbinding → row filters → column masks**.

> Zie [ADR-0003](../docs/adr/0003-opa-as-trino-authz.md) voor de keuze
> van OPA als Trino-authz, en
> [`docs/compliance-mapping.md`](../docs/compliance-mapping.md) voor de
> gerelateerde requirements (R-AVG-05/06/07, R-BIO-11).

## Layout

```
opa-policies-src/
├── Makefile                    # local-test targets (fmt / test / bundle)
├── trino/
│   ├── trino-base.rego         # default-deny + allow-aggregator (fase 9)
│   ├── trino-platform-roles.rego    # role → catalog/schema mapping
│   ├── trino-doelbinding.rego  # purpose-binding (R-AVG-05/06)
│   ├── trino-row-filters.rego  # regio-filter, doelbinding-filter (R-BIO-11)
│   ├── trino-column-masks.rego # PII / medisch maskeren (R-AVG-07)
│   └── trino-*_test.rego       # rego-unit-tests per laag
└── data/
    └── role_mappings.json  # data-laag — wie mag wat zien
```

Trino's OPA-access-controller-spec (v2):
<https://trino.io/docs/current/security/opa-access-control.html>

## Authorisatie-stack

`trino-base.rego` weigert default. `allow` wordt opgebouwd door:

1. **Role-mapping** (`trino-platform-roles.rego`) — koppelt OIDC-rol uit Keycloak
   aan toegestane catalogs + schemas. Bron-of-truth in
   `data/role_mappings.json`.
2. **Doelbinding** (`trino-doelbinding.rego`) — query-purpose-claim moet
   overlappen met `meta.doelbinding` van het resource (R-AVG-05/06).
3. **Row filters** (`trino-row-filters.rego`) — Trino voegt per query een
   `WHERE`-clause toe (regio-filter, doelbinding-filter).
4. **Column masks** (`trino-column-masks.rego`) — Per (rol × kolom) een
   SQL-mask die Trino in de SELECT toepast (BSN → `XXX***NNN`, etc.).

## Lokaal testen

```bash
# Vanuit deze map
make test            # opa test trino/ + data.json
make fmt             # opa fmt --diff trino/
make bundle          # = bash ../scripts/build-opa-bundle.sh

# Via top-level Makefile
make opa-test        # fmt + test
make opa-bundle      # test + sync naar platform/10-opa/policies/
```

`opa` (≥ 0.60) moet op de `PATH` staan — `scripts/doctor.sh` checkt dit.

## Rollen — `data/role_mappings.json`

JSON met één key per rol. Per rol:

| Veld | Wat |
|---|---|
| `_role_purpose` | Vrije-tekst toelichting (waarom bestaat de rol?). |
| `catalogs` | Lijst toegestane catalogs (`bronze`, `silver`, `gold`, …). |
| `schemas` | Lijst toegestane schemas, of `null` voor "alles in `catalogs`". |
| `purposes` | Toegestane doelbindingen (`uitkering`, `reintegratie`, `sturingsinfo`, `kwaliteitscontrole`, `*`). |
| `can_see_pii` | Boolean — bepaalt BSN/naam-mask. |
| `can_see_medical` | Boolean — bepaalt medisch-veld-mask. |
| `can_see_bankrekening` | Boolean — bepaalt IBAN-mask. |
| `regio_filter` | `false` = geen filter, anders regio-code (`AMS`, `RTM`, …). |
| `break_glass` | Noodtoegang met audit-log; tijdelijk. |

Een rol toevoegen → JSON bewerken → `make test` → `make bundle` → re-deploy
de `OpaCluster` met de nieuwe bundle (zie
[`platform/10-opa/README.md`](../platform/10-opa/README.md)).

## Bundle-deploy

`scripts/build-opa-bundle.sh` doet:

1. `opa fmt --diff trino/` (faal als format off is).
2. `opa test trino/ data/role_mappings.json` (faal als tests rood).
3. Sync `trino/*.rego` + `data/*.json` naar `platform/10-opa/policies/`.
4. ConfigMap-rollout via `kubectl apply -k platform/10-opa/`.

Geen geheim: dit zijn policies en role-mappings, geen credentials.

## Conventies

- Eén `package trino` voor alle bestanden — Trino verwacht decisions
  onder `data.trino.*`.
- Helpers en defaults in `trino-base.rego`; per-laag bestanden importeren
  niet expliciet maar relyen op rego's automatische package-merge.
- Tests gebruiken `import rego.v1` (rego v1-syntaxis).
- Test-bestanden: `<policy>_test.rego`. Eén test per (rol × scenario).
- Geen wildcards in `purposes` zonder `_role_purpose`-toelichting (audit-spoor).
