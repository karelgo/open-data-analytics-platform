"""Verrijk OpenMetadata-tables met compliance meta uit dbt manifest.json.

Loopt nadat `metadata ingest -c dbt-workflow.yaml` heeft gedraaid en de
tabellen in OM bestaan. Per dbt-model:

  - Doelbinding.*, LegalBasis.*, Confidentiality.*, AI.Risk-*   → tags
  - CGM.<term>                                                  → glossary-terms
  - meta.eigenaar (divisie_*)                                   → owner (team)
  - config.tags (uc01 / uc11 / cross / sandbox / marts)         → Tier1..4
  - meta.bewaartermijn_jaren / dpia_id / risk-flags             → Custom Properties
  - meta.pii_kolommen[]                                         → PII.* op kolom
  - meta.domain                                                  → OM Domain
  - dbt config.tags                                              → OM Data Product(s)

PATCH-based en idempotent. Tags worden UNIE'd met bestaande tags (handmatige
edits in de UI overleven). Owner wordt alleen gezet als er geen owner staat.

OM 1.5-specifieke gotchas die in deze code zijn afgevangen:
  - Glossary-term FQN gebruikt ASCII namen (`Cliënt` → `Client` strip-accent).
  - Domain veld is singular `/domain` (1.7+ heeft `/domains` array).
  - Enum custom properties verwachten een ARRAY (`["true"]`), niet scalaire.
  - Owner-toewijzing alleen aan Team-type `Group` (niet `BusinessUnit`).

Env-vars:
  OM_URL              http://openmetadata.odap-meta.svc.cluster.local:8585
  OM_JWT_TOKEN        admin/bot JWT
  OM_TRINO_SERVICE    trino (default)
  DBT_BUCKET          odap-meta
  DBT_PREFIX          dbt/latest/
  MINIO_ENDPOINT      https://minio.odap-platform.svc.cluster.local:9000
  MINIO_ACCESS_KEY    platformadmin
  MINIO_SECRET_KEY    <secret>
"""
from __future__ import annotations

import json
import os
import sys
import unicodedata
from typing import Any
from urllib.parse import quote

import boto3
import requests
import yaml


def _strip_accents(value: str) -> str:
    """CGM-glossary `name` is ASCII; dbt-meta kan diakritieken bevatten
    ('Cliënt' → 'Client')."""
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(c)
    )


OM_URL = os.environ.get(
    "OM_URL", "http://openmetadata.odap-meta.svc.cluster.local:8585"
).rstrip("/")
OM_TOKEN = os.environ["OM_JWT_TOKEN"]
SERVICE_NAME = os.environ.get("OM_TRINO_SERVICE", "trino")

DBT_BUCKET = os.environ.get("DBT_BUCKET", "odap-meta")
DBT_PREFIX = os.environ.get("DBT_PREFIX", "dbt/latest/").rstrip("/") + "/"
MINIO_ENDPOINT = os.environ.get(
    "MINIO_ENDPOINT", "https://minio.odap-platform.svc.cluster.local:9000"
)
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "platformadmin")
MINIO_SECRET_KEY = os.environ["MINIO_SECRET_KEY"]
MINIO_REGION = os.environ.get("MINIO_REGION", "eu-nl-1")

MAPPING_PATH = os.environ.get("MAPPING_PATH", "/config/dbt-meta-mapping.yaml")

HEADERS = {
    "Authorization": f"Bearer {OM_TOKEN}",
    "Content-Type": "application/json",
}
PATCH_HEADERS = {
    "Authorization": f"Bearer {OM_TOKEN}",
    "Content-Type": "application/json-patch+json",
}


def log(msg: str) -> None:
    print(f"[enrich] {msg}", flush=True)


def fetch_manifest() -> dict:
    """Haal manifest.json uit MinIO. Faalt hard als bucket/object ontbreekt."""
    log(
        f"Lees s3://{DBT_BUCKET}/{DBT_PREFIX}manifest.json via {MINIO_ENDPOINT}"
    )
    s3 = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name=MINIO_REGION,
        verify=os.environ.get("REQUESTS_CA_BUNDLE", True),
    )
    obj = s3.get_object(Bucket=DBT_BUCKET, Key=f"{DBT_PREFIX}manifest.json")
    return json.loads(obj["Body"].read())


def load_mapping() -> dict:
    with open(MAPPING_PATH) as f:
        return yaml.safe_load(f)


def get_table(fqn: str) -> dict | None:
    """Haal table-entity bij FQN. Tags + extension + domains + dataProducts
    expliciet meegehaald — OM laat ze anders uit het 'lite' antwoord.

    OM 1.12: veld heet `domains` (plural array), niet `domain`. De 1.5 single
    `domain` is hernoemd in 1.7+; de v12 server geeft 400 op `?fields=domain`."""
    url = (
        f"{OM_URL}/api/v1/tables/name/{quote(fqn, safe='.')}"
        "?fields=tags,owners,extension,columns,domains,dataProducts"
    )
    r = requests.get(url, headers=HEADERS, timeout=15)
    if r.status_code == 200:
        return r.json()
    if r.status_code == 404:
        return None
    log(f"  ! GET {fqn} faalt status={r.status_code} body={r.text[:200]}")
    return None


def lookup_entity_id(kind: str, name: str) -> str | None:
    """kind = 'teams' | 'users' | 'glossaryTerms'. Geeft entity-id of None."""
    if kind == "glossaryTerms":
        url = f"{OM_URL}/api/v1/glossaryTerms/name/CGM.{name}"
    else:
        url = f"{OM_URL}/api/v1/{kind}/name/{name}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    if r.status_code == 200:
        return r.json().get("id")
    return None


_DOMAIN_REF_CACHE: dict[str, dict] = {}
_DATAPRODUCT_REF_CACHE: dict[str, dict] = {}


def _domain_ref(name: str) -> dict | None:
    if name in _DOMAIN_REF_CACHE:
        return _DOMAIN_REF_CACHE[name]
    r = requests.get(
        f"{OM_URL}/api/v1/domains/name/{name}", headers=HEADERS, timeout=10
    )
    if r.status_code != 200:
        return None
    ref = {"id": r.json()["id"], "type": "domain", "name": name}
    _DOMAIN_REF_CACHE[name] = ref
    return ref


def _dataproduct_ref(name: str) -> dict | None:
    if name in _DATAPRODUCT_REF_CACHE:
        return _DATAPRODUCT_REF_CACHE[name]
    r = requests.get(
        f"{OM_URL}/api/v1/dataProducts/name/{name}",
        headers=HEADERS,
        timeout=10,
    )
    if r.status_code != 200:
        return None
    ref = {"id": r.json()["id"], "type": "dataProduct", "name": name}
    _DATAPRODUCT_REF_CACHE[name] = ref
    return ref


def tag_label(fqn: str, source: str = "Classification") -> dict:
    """OM TagLabel-shape (1.5+). 'state: Confirmed' = niet-suggested."""
    return {
        "tagFQN": fqn,
        "source": source,
        "labelType": "Automated",
        "state": "Confirmed",
    }


def union_tags(existing: list[dict], new_fqns: list[tuple[str, str]]) -> list[dict]:
    """UNION op tagFQN. `new_fqns` = [(fqn, source)]. Bestaande tags blijven
    behouden (incl. handmatig in UI gezette tags)."""
    by_fqn = {t["tagFQN"]: t for t in existing or []}
    for fqn, source in new_fqns:
        if fqn not in by_fqn:
            by_fqn[fqn] = tag_label(fqn, source)
    return list(by_fqn.values())


def derive_tier(model_tags: list[str], mapping: dict) -> str:
    rules = mapping.get("tier_rules", {})
    by_tag = rules.get("by_dbt_tag", {})
    ranks = {"Tier1": 1, "Tier2": 2, "Tier3": 3, "Tier4": 4}
    best = rules.get("default", "Tier4")
    for t in model_tags:
        candidate = by_tag.get(t)
        if candidate and ranks.get(candidate, 5) < ranks.get(best, 5):
            best = candidate
    return best


def map_doelbinding(values: list[str], mapping: dict) -> list[str]:
    out = []
    for v in values or []:
        fqn = mapping["doelbinding_to_tag"].get(str(v).lower())
        if fqn:
            out.append(fqn)
        else:
            log(f"  ? onbekende doelbinding={v}")
    return out


def map_legal_basis(value: str, mapping: dict) -> list[str]:
    if not value:
        return []
    return mapping["legal_basis_to_tags"].get(value, [])


def map_bio_classificatie(value: str, mapping: dict) -> str | None:
    if not value:
        return None
    return mapping["bio_classificatie_to_tag"].get(str(value).lower())


def map_risk_tier(value: str, mapping: dict) -> str | None:
    if not value:
        return None
    return mapping["risk_tier_to_tag"].get(str(value).lower())


def build_table_tags(
    node: dict, mapping: dict, existing_tags: list[dict]
) -> list[dict]:
    """Verzamel alle tag-FQNs voor de tabel-entiteit. Glossary-terms gaan
    ook als tags mee maar met source=Glossary."""
    meta = node.get("meta") or {}
    new_fqns: list[tuple[str, str]] = []

    for fqn in map_doelbinding(meta.get("doelbinding", []), mapping):
        new_fqns.append((fqn, "Classification"))

    for fqn in map_legal_basis(meta.get("legal_basis"), mapping):
        new_fqns.append((fqn, "Classification"))

    bio_fqn = map_bio_classificatie(meta.get("bio_classificatie"), mapping)
    if bio_fqn:
        new_fqns.append((bio_fqn, "Classification"))

    risk_fqn = map_risk_tier(meta.get("risk_tier"), mapping)
    if risk_fqn:
        new_fqns.append((risk_fqn, "Classification"))

    # Tier — derived from config.tags.
    config_tags = (node.get("config") or {}).get("tags") or []
    tier = derive_tier([str(t).lower() for t in config_tags], mapping)
    new_fqns.append((f"Tier.{tier}", "Classification"))

    # CGM glossary-terms — source=Glossary. Strip accent voor FQN-match
    # (CGM-glossary `name` is ASCII; dbt-meta kan 'Cliënt' bevatten).
    for term in meta.get("cgm_entiteiten", []) or []:
        term_fqn = f"CGM.{_strip_accents(str(term))}"
        new_fqns.append((term_fqn, "Glossary"))

    # AI.HumanInTheLoop tag-vlag — los van de Risk-* tag.
    if meta.get("human_in_the_loop"):
        new_fqns.append(("AI.HumanInTheLoop", "Classification"))

    return union_tags(existing_tags, new_fqns)


def build_column_patches(
    node: dict, mapping: dict, table_columns: list[dict]
) -> list[dict]:
    """Voor elke kolom in pii_kolommen[] → PII.* tag toevoegen aan de juiste
    kolom-entry. Returnt JSON-Patch ops. Case-insensitive match op kolom-naam."""
    pii_cols = (node.get("meta") or {}).get("pii_kolommen") or []
    if not pii_cols:
        return []
    pii_map = mapping["pii_column_to_tag"]
    ops = []

    name_to_idx = {
        (col.get("name") or "").lower(): idx
        for idx, col in enumerate(table_columns or [])
    }

    for pii_col_name in pii_cols:
        idx = name_to_idx.get(str(pii_col_name).lower())
        if idx is None:
            log(f"    ? PII-kolom '{pii_col_name}' niet gevonden in OM-tabel")
            continue
        pii_fqn = pii_map.get(str(pii_col_name).lower())
        if not pii_fqn:
            log(f"    ? geen PII-mapping voor '{pii_col_name}'")
            continue
        existing = table_columns[idx].get("tags") or []
        if any(t.get("tagFQN") == pii_fqn for t in existing):
            continue
        merged = existing + [tag_label(pii_fqn, "Classification")]
        ops.append(
            {
                "op": "add" if not existing else "replace",
                "path": f"/columns/{idx}/tags",
                "value": merged,
            }
        )

    return ops


def build_extension(node: dict, mapping: dict) -> dict:
    """Custom-properties payload. Lege velden worden overgeslagen; bestaande
    waardes blijven behouden via merge_extension."""
    meta = node.get("meta") or {}
    ext: dict[str, Any] = {}

    if "bewaartermijn_jaren" in meta:
        ext["bewaartermijn_jaren"] = int(meta["bewaartermijn_jaren"])
    if meta.get("dpia_id"):
        ext["dpia_id"] = str(meta["dpia_id"])
    if meta.get("algoritmeregister_id"):
        ext["algoritmeregister_id"] = str(meta["algoritmeregister_id"])
    if meta.get("legal_basis"):
        ext["legal_basis_text"] = str(meta["legal_basis"])
    if meta.get("domain"):
        ext["dbt_domain"] = str(meta["domain"])

    # Enum custom properties in OM 1.5 worden als ARRAY opgeslagen ook bij
    # multiSelect=false; ["true"] / ["false"] — niet scalaire strings.
    for boolflag in (
        "human_in_the_loop",
        "toegang_via_OPA_policies",
        "profilering",
        "opt_out_supported",
        "sandbox_only",
        "pseudonymized",
        "publiek_te_publiceren",
        "juistheid_AVG_art_5_1d",
    ):
        if boolflag in meta:
            ext[boolflag] = ["true"] if meta[boolflag] else ["false"]

    return ext


def merge_extension(existing: dict | None, new: dict) -> dict:
    out = dict(existing or {})
    out.update(new)
    return out


def resolve_owner(node: dict, mapping: dict) -> dict | None:
    """eigenaar → team-ref. Probeer eerst Team; val terug op User."""
    eigenaar = (node.get("meta") or {}).get("eigenaar")
    if not eigenaar:
        return None
    team_name = mapping["eigenaar_to_team"].get(eigenaar, eigenaar)
    team_id = lookup_entity_id("teams", team_name)
    if team_id:
        return {"id": team_id, "type": "team", "name": team_name}
    user_id = lookup_entity_id("users", eigenaar)
    if user_id:
        return {"id": user_id, "type": "user", "name": eigenaar}
    log(f"  ? eigenaar '{eigenaar}' niet vindbaar als team/user")
    return None


def resolve_domain(node: dict, mapping: dict) -> dict | None:
    dbt_domain = (node.get("meta") or {}).get("domain")
    if not dbt_domain:
        return None
    om_name = mapping.get("dbt_domain_to_om", {}).get(str(dbt_domain).lower())
    if not om_name:
        log(f"  ? geen domain-mapping voor dbt-domain '{dbt_domain}'")
        return None
    ref = _domain_ref(om_name)
    if ref is None:
        log(f"  ? OM-domain '{om_name}' niet vindbaar")
    return ref


def resolve_data_products(node: dict, mapping: dict) -> list[dict]:
    """Match dbt config.tags tegen data_products[].dbt_tag. Zelfde tabel kan
    in meerdere data-products zitten (UC11 events + phases delen 'uc11')."""
    config_tags = {
        str(t).lower() for t in (node.get("config") or {}).get("tags") or []
    }
    products = mapping.get("data_products", [])
    refs = []
    for p in products:
        tag = str(p.get("dbt_tag", "")).lower()
        if tag and tag in config_tags:
            ref = _dataproduct_ref(p["name"])
            if ref:
                refs.append(ref)
    return refs


def patch_table(table: dict, ops: list[dict]) -> None:
    if not ops:
        return
    url = f"{OM_URL}/api/v1/tables/{table['id']}"
    r = requests.patch(url, headers=PATCH_HEADERS, data=json.dumps(ops), timeout=20)
    if r.status_code not in (200, 201):
        log(
            f"  ! PATCH {table['fullyQualifiedName']} status={r.status_code} "
            f"body={r.text[:300]}"
        )


def build_table_patch_ops(table: dict, node: dict, mapping: dict) -> list[dict]:
    ops: list[dict] = []

    # Tags (incl. glossary + tier).
    new_tags = build_table_tags(node, mapping, table.get("tags") or [])
    if new_tags:
        ops.append(
            {
                "op": "add" if not table.get("tags") else "replace",
                "path": "/tags",
                "value": new_tags,
            }
        )

    # Custom properties — merge in bestaande extension.
    new_ext = build_extension(node, mapping)
    if new_ext:
        merged = merge_extension(table.get("extension"), new_ext)
        ops.append(
            {
                "op": "add" if not table.get("extension") else "replace",
                "path": "/extension",
                "value": merged,
            }
        )

    # Owner — alleen zetten als de tabel nog geen owner heeft (respecteer
    # handmatige toewijzingen via de UI).
    if not table.get("owners"):
        owner = resolve_owner(node, mapping)
        if owner:
            ops.append({"op": "add", "path": "/owners", "value": [owner]})

    # Domain — OM 1.12+ gebruikt `/domains` array (was singular `/domain` in
    # 1.5). We schrijven een lijst met één entry; bestaande domains worden
    # gerespecteerd via UNION-op-naam.
    dom = resolve_domain(node, mapping)
    if dom:
        existing_doms = table.get("domains") or []
        existing_names = {d.get("name") for d in existing_doms}
        if dom["name"] not in existing_names:
            merged = existing_doms + [dom]
            ops.append(
                {
                    "op": "add" if not existing_doms else "replace",
                    "path": "/domains",
                    "value": merged,
                }
            )

    # Data Products — UNION met bestaande (respecteer handmatige toewijzing).
    dp_refs = resolve_data_products(node, mapping)
    if dp_refs:
        existing = table.get("dataProducts") or []
        existing_names = {p.get("name") for p in existing}
        merged = list(existing)
        for ref in dp_refs:
            if ref["name"] not in existing_names:
                merged.append(ref)
        if len(merged) != len(existing):
            ops.append(
                {
                    "op": "add" if not existing else "replace",
                    "path": "/dataProducts",
                    "value": merged,
                }
            )

    # Kolom-niveau PII tags.
    ops.extend(build_column_patches(node, mapping, table.get("columns") or []))

    return ops


def iter_model_nodes(manifest: dict):
    """Yield (fqn, node) voor elke dbt-model. FQN gebruikt OM-conventie
    service.database.schema.table."""
    nodes = manifest.get("nodes") or {}
    for node_id, node in nodes.items():
        if node.get("resource_type") != "model":
            continue
        database = node.get("database")
        schema = node.get("schema")
        table = node.get("alias") or node.get("name")
        if not (database and schema and table):
            continue
        fqn = f"{SERVICE_NAME}.{database}.{schema}.{table}"
        yield fqn, node


def main() -> int:
    mapping = load_mapping()
    manifest = fetch_manifest()

    total = 0
    enriched = 0
    missing = 0

    for fqn, node in iter_model_nodes(manifest):
        total += 1
        table = get_table(fqn)
        if table is None:
            log(f"  - {fqn}: niet in OM (skip — wacht op dbt-ingest)")
            missing += 1
            continue

        ops = build_table_patch_ops(table, node, mapping)
        if not ops:
            log(f"  = {fqn}: niets te veranderen")
            continue

        patch_table(table, ops)
        log(f"  + {fqn}: {len(ops)} patches")
        enriched += 1

    log(
        f"Klaar. dbt-models={total}  enriched={enriched}  missing-in-OM={missing}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
