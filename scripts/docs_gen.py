#!/usr/bin/env python3
"""Genereer architectuur-pagina's voor de MkDocs-site uit portal/src/data/components.ts.

De portal-registry blijft de single source of truth voor componenten, lagen
en rol-mappings. Dit script parseert die TypeScript-bron en schrijft markdown
naar docs/architectuur/. CI draait dit voor `mkdocs build`.

Outputs:
  docs/architectuur/index.md         — overzicht + swim-lane diagram (mermaid)
  docs/architectuur/componenten.md   — per-component pagina (tabel + detail)
  docs/architectuur/datazones.md     — medallion + sensitive uitleg
  docs/architectuur/auth.md          — Keycloak + OPA + AuthenticationClass
  docs/architectuur/tabel-formaat.md — Delta vs Iceberg abstractie
  docs/architectuur/naming.md        — naming conventions
  docs/architectuur/referentie.md    — link naar originele referentiearch
  docs/index.md                       — site-landing
  docs/rollen/index.md                — overzicht 12 rollen + matrix
  docs/use-cases/index.md             — UC overzicht
  docs/adr/index.md                   — ADR overzicht
  docs/security.md                    — security policy (kopie van SECURITY.md)

Aanroep:
  python scripts/docs_gen.py           # schrijft alles
  python scripts/docs_gen.py --check   # exit 1 als output drift t.o.v. bron

Geen externe dependencies: pure-stdlib parser. De TS-file is een platte
object-literal-export — voldoende voor regex + json.loads na quote-fix.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORTAL_COMPONENTS_TS = ROOT / "portal" / "src" / "data" / "components.ts"
DOCS_DIR = ROOT / "docs"


# ───────────────────────── TypeScript parser ─────────────────────────


def _extract_array_literal(src: str, identifier: str) -> str:
    """Return the JS object-array literal assigned to `export const <identifier>`."""
    pattern = re.compile(
        rf"export\s+const\s+{re.escape(identifier)}\s*:\s*[^=]+=\s*(\[.*?^\];)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(src)
    if not match:
        raise SystemExit(f"Could not locate `export const {identifier}` in components.ts")
    raw = match.group(1).rstrip(";")
    return raw


def _ts_array_to_json(literal: str) -> list[dict]:
    """Convert a tame TS object-literal array into a JSON-parseable form.

    Handles the specific patterns used in portal/src/data/components.ts:
    - single-quoted strings → double-quoted
    - // line comments → stripped
    - /* block comments */ → stripped
    - trailing commas inside objects / arrays → removed
    - bare identifier keys → quoted
    """
    s = literal

    # 1. Strip /* … */ block comments first (multiline).
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)

    # 2. Strip // line comments (not inside strings — we do a quick heuristic
    #    that skips // when the line is inside obvious string content).
    out_lines: list[str] = []
    for line in s.splitlines():
        # Find the first // that isn't inside a quoted string.
        in_single = False
        in_double = False
        cut = None
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "\\" and i + 1 < len(line):
                i += 2
                continue
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            elif not in_single and not in_double and ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                cut = i
                break
            i += 1
        out_lines.append(line if cut is None else line[:cut])
    s = "\n".join(out_lines)

    # 3. Quote bare keys: `  name: ` → `  "name": ` (key followed by colon).
    s = re.sub(r"([\{\,]\s*)([A-Za-z_][A-Za-z0-9_-]*)\s*:", r'\1"\2":', s)

    # 4. Single-quoted string values → double-quoted. (Step 3 quoted keys already.)
    #    Replace top-level `'…'` with `"…"`. JSON does not allow single quotes.
    def _swap_quotes(text: str) -> str:
        result: list[str] = []
        i = 0
        in_dbl = False
        while i < len(text):
            ch = text[i]
            if ch == '"' and (i == 0 or text[i - 1] != "\\"):
                in_dbl = not in_dbl
                result.append(ch)
            elif ch == "'" and not in_dbl:
                # Find the matching single quote.
                j = i + 1
                while j < len(text):
                    if text[j] == "\\" and j + 1 < len(text):
                        j += 2
                        continue
                    if text[j] == "'":
                        break
                    j += 1
                literal_value = text[i + 1 : j]
                # Escape any double quotes within.
                literal_value = literal_value.replace("\\", "\\\\").replace('"', '\\"')
                result.append(f'"{literal_value}"')
                i = j
            else:
                result.append(ch)
            i += 1
        return "".join(result)

    s = _swap_quotes(s)

    # 5. Remove trailing commas: `,]` or `,}` (with optional whitespace).
    s = re.sub(r",(\s*[\]\}])", r"\1", s)

    try:
        return json.loads(s)
    except json.JSONDecodeError as exc:
        # Schrijf debug-output zodat we de generator-fout in CI kunnen vinden.
        debug_path = ROOT / ".docs_gen_debug.json"
        debug_path.write_text(s, encoding="utf-8")
        raise SystemExit(
            f"docs_gen: kon TS-literal niet als JSON parsen ({exc}). "
            f"Tussenstap geschreven naar {debug_path.relative_to(ROOT)}."
        ) from exc


@dataclass(frozen=True)
class Component:
    id: str
    name: str
    layer: str
    stage: str
    short: str
    purpose: str
    icon: str
    url: str | None
    prometheus_job: str | None
    roles_using: tuple[str, ...]


@dataclass(frozen=True)
class Stage:
    id: str
    title: str
    blurb: str
    kind: str
    category: str | None
    tags: tuple[str, ...]


def load_registry() -> tuple[list[Component], list[Stage]]:
    src = PORTAL_COMPONENTS_TS.read_text(encoding="utf-8")
    comps_raw = _ts_array_to_json(_extract_array_literal(src, "components"))
    stages_raw = _ts_array_to_json(_extract_array_literal(src, "stages"))

    comps = [
        Component(
            id=c["id"],
            name=c["name"],
            layer=c["layer"],
            stage=c["stage"],
            short=c["short"],
            purpose=c["purpose"],
            icon=c["icon"],
            url=c.get("url"),
            prometheus_job=c.get("prometheusJob"),
            roles_using=tuple(c.get("rolesUsing") or ()),
        )
        for c in comps_raw
    ]
    stages = [
        Stage(
            id=s["id"],
            title=s["title"],
            blurb=s["blurb"],
            kind=s["kind"],
            category=s.get("category"),
            tags=tuple(s.get("tags") or ()),
        )
        for s in stages_raw
    ]
    return comps, stages


# ───────────────────────── markdown writers ─────────────────────────


GENERATED_BANNER = (
    "<!-- Auto-generated door scripts/docs_gen.py uit portal/src/data/components.ts.\n"
    "     Wijzigingen handmatig vervallen bij de volgende CI-build — bewerk de TS-bron. -->\n"
)


def _inject_banner(content: str) -> str:
    """Voor markdown-files met YAML frontmatter: voeg HTML-banner toe NA de frontmatter."""
    if not content.startswith("---\n"):
        return content
    end = content.find("\n---\n", 4)
    if end == -1:
        return content
    head = content[: end + 5]  # include the closing '---\n'
    tail = content[end + 5 :]
    return f"{head}\n{GENERATED_BANNER}\n{tail.lstrip()}"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".md":
        content = _inject_banner(content)
    path.write_text(content, encoding="utf-8")


def render_index(stages: list[Stage], comps: list[Component]) -> str:
    pipeline_stages = [s for s in stages if s.id != "sources"]
    role_count = len({r for c in comps for r in c.roles_using if r != "*"})

    return f"""---
title: Home
description: ODAP reference implementation van een compliant data- en analyticsplatform.
hide:
  - navigation
---

# Open Data & Analytics Platform

Een **fictieve, illustratieve** referentie-implementatie van een modern data-
en analyticsplatform voor UWV, gebouwd op open source en gericht op compliance
met NORA, AVG, BIO/BIO2, NIS2 en de AI Act.

!!! warning "Geen echte ODAP data"
    Geen echte BSN's, geen echte productiecode. Alle datasets zijn synthetisch
    en gemarkeerd met `# SYNTHETIC DATA — OPEN DATA AND ANALYTICS PLATFORM — NOT FOR REAL USE`.
    Deze repo is geen ODAP product en geen aanbestedingsstuk.

## Wat vind je hier?

<div class="grid cards" markdown>

-   :material-sitemap:{{ .lg .middle }} **Architectuur**

    ---

    {len(comps)} componenten over {len(pipeline_stages)} lagen — van ingestie
    tot consumptie, met identity, observability en governance als
    cross-cutting lanen.

    [:octicons-arrow-right-24: Open architectuur](architectuur/index.md)

-   :material-account-group:{{ .lg .middle }} **Voor wie?**

    ---

    {role_count} rollen met elk eigen handleiding: WIA-beoordelaar,
    WW-handhaver, data-engineer, platform-admin, … Toegang en data-zichtbaarheid
    komen uit OPA-policies en Keycloak-rollen.

    [:octicons-arrow-right-24: Bekijk rollen](rollen/index.md)

-   :material-target:{{ .lg .middle }} **Use cases**

    ---

    11 concrete business-flows — van WIA-funnel (UC-01) tot
    integrale klantreis (UC-11) — met scope, CGM-entiteiten, doelbinding
    en AI-Act-classificatie.

    [:octicons-arrow-right-24: Bekijk use cases](use-cases/index.md)

-   :material-clipboard-text:{{ .lg .middle }} **Beslissingen**

    ---

    8 ADRs leggen de fundamentele keuzes vast: Stackable, Delta vs Iceberg,
    OPA als Trino-authz, OpenMetadata als catalog, dbt-trino als
    transformatielaag.

    [:octicons-arrow-right-24: Bekijk ADRs](adr/index.md)

-   :material-shield-check:{{ .lg .middle }} **Compliance**

    ---

    Iedere R-NORA/AVG/BIO/NIS2/AI-Act-requirement is gemapt op een concreet
    bestand of setting — herleidbaar in code en config.

    [:octicons-arrow-right-24: Compliance-mapping](compliance-mapping.md)

-   :material-cog:{{ .lg .middle }} **Operations**

    ---

    Runbook, security-policy, documentatie-gaps, roadmap. De operationele
    realiteit van het platform.

    [:octicons-arrow-right-24: Operations](runbook.md)

</div>

## Snelstart

```bash
# Voorvereisten: Docker Desktop (≥ 8 GB / ≥ 4 CPU), k3d ≥ 5.6, kubectl, helm, stackablectl

git clone https://github.com/fresh-minds/FreshStackableDataPlatform.git
cd FreshStackableDataPlatform

# DNS-injectie voor lokale toegang
echo "127.0.0.1 keycloak.odap.local \\
  superset.odap.local airflow.odap.local \\
  minio.odap.local openmetadata.odap.local" | sudo tee -a /etc/hosts

# Cluster + platform deployen (~15-30 min op de eerste run)
make cluster        # k3d cluster create
make bootstrap      # cert-manager, MinIO, Postgres, Keycloak, Stackable operators
make deploy-platform # Trino, Spark, Kafka, NiFi, Airflow, Superset, OpenMetadata
make seed           # synthetische data laden (10k cliënten)
make test           # smoke tests
```

## Wat is de stack?

| Laag | Component | Kort |
|---|---|---|
| Identiteit | **Keycloak** | OIDC, MFA, rol-claims |
| Ingestie | **NiFi → Kafka** | Visuele flows, schaalbare event-bus |
| Opslag | **MinIO + Hive Metastore** | S3-compatible, Delta-tabellen, catalog |
| Verwerking | **Spark (Stackable)** | Structured Streaming + batch |
| Query | **Trino + OPA** | SQL over lakehouse met policy-checks |
| Transformatie | **dbt-trino** | Staging → intermediate → marts, format-agnostisch |
| Orkestratie | **Airflow** | DAGs voor batch + dbt-runs |
| BI | **Superset** | Dashboards + SQL Lab |
| Governance | **OpenMetadata** | Catalog, glossary, lineage, DQ |
| Observability | **Vector → OpenSearch + Prometheus + OTEL** | Logs, metrics, traces |

Alle componenten via **Stackable Data Platform 26.3** operators.

## Bijdragen

Issues, PR's en feedback welkom via [GitHub](https://github.com/fresh-minds/FreshStackableDataPlatform).
Een nieuwe doc volgt de bestaande structuur (ADR ↔ use-case ↔ handleiding);
kruisverwijzingen worden bijgewerkt in dit document én in de index.
"""


def render_architectuur_index(stages: list[Stage], comps: list[Component]) -> str:
    pipeline_stages = [s for s in stages if s.kind in ("pipeline-step", "output") and s.id != "sources"]
    overlay_stages = [s for s in stages if s.kind == "overlay"]
    side_stages = [s for s in stages if s.kind == "side"]

    # Mermaid swim-lane diagram. Voor leesbaarheid: dataflow horizontaal,
    # cross-cutting lagen daaronder.
    mermaid_nodes: list[str] = []
    mermaid_edges: list[str] = []

    pipeline_order = ["ingestion", "storage", "transformation", "consumption"]
    for s_id in pipeline_order:
        s = next((x for x in stages if x.id == s_id), None)
        if not s:
            continue
        s_comps = [c for c in comps if c.stage == s_id]
        if not s_comps:
            continue
        names = " + ".join(c.name for c in s_comps)
        mermaid_nodes.append(f'    {s_id}["**{s.title}**<br/>{names}"]')

    for a, b in zip(pipeline_order, pipeline_order[1:]):
        mermaid_edges.append(f"    {a} --> {b}")

    mermaid_block = "\n".join(mermaid_nodes + mermaid_edges)

    # Markdown lane-tabellen.
    lane_md: list[str] = []
    laneorder = ["ingestion", "storage", "transformation", "consumption", "discovery", "pipeline", "observability", "identity", "agents"]
    for s_id in laneorder:
        s = next((x for x in stages if x.id == s_id), None)
        if not s:
            continue
        s_comps = [c for c in comps if c.stage == s_id]
        if not s_comps:
            continue
        anchor = s.id
        lane_md.append(f"### {s.title} {{ #{anchor} }}\n")
        lane_md.append(f"{s.blurb}\n")
        lane_md.append("| Component | Verantwoordelijkheid | Doel |")
        lane_md.append("|---|---|---|")
        for c in s_comps:
            comp_link = f"[{c.name}](componenten.md#{c.id})"
            lane_md.append(f"| {comp_link} | {c.short} | {c.purpose} |")
        lane_md.append("")

    return f"""---
title: Architectuur
description: Overzicht van de ODAP platformarchitectuur — lagen, dataflow, cross-cutting zorgen.
---

# Architectuur

Het platform is opgebouwd als een **keten van lagen** — data komt binnen
(ingestie), wordt opgeslagen (lakehouse), bewerkt en gemodelleerd
(transformatie) en uiteindelijk geconsumeerd in dashboards en data-producten.
Daaroverheen liggen vijf cross-cutting lanen — **identity**, **discovery**,
**pipeline-orkestratie**, **observability** en **agents** — die overal raken.

## Dataflow (high-level)

```mermaid
flowchart LR
{mermaid_block}
```

Auth/authz en observability raken alle componenten — zie
[Identiteit & autorisatie](auth.md) en [Operations / Runbook](../runbook.md).

## Mapping op de UWV-referentiearchitectuur

| Laag in referentie-arch. | Component in deze repo |
|---|---|
| Bronnen | `data-generation/` — synthetische generators voor Polisadm/WW/WIA/Wajong/CRM/FEZ |
| Ingestie & integratie | `platform/07-nifi/` (NiFi) + `platform/06-kafka/` (Kafka) + `nifi-flows/templates/` |
| Opslag (lakehouse, medallion) | MinIO (`platform/03-storage/`) + Delta-tabellen + `platform/05-hive-metastore/` |
| Processing & ML | `platform/08-spark/apps/` (PySpark via SparkApplication) + `dbt/` (Trino-side transforms) |
| Semantische laag | dbt-marts (`dbt/models/marts/uc0x_*/`) + Trino views (`gold` catalog) |
| Consumptie | `platform/12-superset/` (BI) + Trino REST/JDBC voor toekomstige API-laag |
| IAM | Keycloak (`infrastructure/helm/keycloak/`) + Stackable AuthenticationClass (`platform/02-authentication/`) |
| Authorisatie | `platform/10-opa/` + `opa-policies-src/` (Rego) |
| Catalog / lineage / DQ | OpenMetadata (`infrastructure/helm/openmetadata/`) + `platform/13-openmetadata-config/` |
| Observability | Vector (Stackable) + Prometheus (`infrastructure/helm/prometheus-stack/`) + OpenSearch (gedeeld) |
| Secrets / TLS | cert-manager + Stackable secret-operator |

## Componenten per laag

{chr(10).join(lane_md)}

## Verder lezen

- [Componenten in detail](componenten.md) — per component een eigen sectie
- [Datazones](datazones.md) — medallion + sensitive uitleg
- [Identiteit & autorisatie](auth.md) — Keycloak + OPA
- [Tabel-formaat abstractie](tabel-formaat.md) — Delta vs Iceberg
- [Naming conventions](naming.md)
- [Originele referentie-architectuur](referentie.md) — bron-document
"""


def render_componenten(comps: list[Component], stages: list[Stage]) -> str:
    by_stage = {s.id: s for s in stages}

    sections: list[str] = []
    stage_order = ["identity", "ingestion", "storage", "transformation", "consumption", "discovery", "pipeline", "observability", "agents"]
    for stage_id in stage_order:
        stage = by_stage.get(stage_id)
        if not stage:
            continue
        comps_in = [c for c in comps if c.stage == stage_id]
        if not comps_in:
            continue
        sections.append(f"## {stage.title}\n")
        sections.append(f"_{stage.blurb}_\n")
        for c in comps_in:
            url_md = f"[Live UI ↗]({c.url})" if c.url and c.url.startswith("http") else (f"`{c.url}`" if c.url else "_geen UI_")
            prom = f"`{c.prometheus_job}`" if c.prometheus_job else "_niet gemonitord_"

            if "*" in c.roles_using:
                roles_str = "**alle rollen**"
            else:
                roles_str = ", ".join(f"`{r}`" for r in c.roles_using) if c.roles_using else "_geen specifieke rol_"

            sections.append(f"### {c.name} {{ #{c.id} }}\n")
            sections.append(f"!!! abstract \"Wat doet {c.name}?\"")
            sections.append(f"    {c.purpose}\n")
            sections.append(f"**Laag:** `{c.layer}` · **Stage:** `{c.stage}` · **Prometheus job:** {prom}")
            sections.append("")
            sections.append(f"{c.short}")
            sections.append("")
            sections.append(f"- **URL:** {url_md}")
            sections.append(f"- **Gebruikt door:** {roles_str}")
            sections.append("")

    role_matrix = _render_role_matrix(comps)

    return f"""---
title: Componenten
description: Per-component overzicht — verantwoordelijkheid, doel, URL, gebruikende rollen.
---

# Componenten

Per-component overzicht. Voor het diagram op laag-niveau zie
[Architectuur · Overzicht](index.md); voor de relatie tussen rollen en
componenten zie de [rol-matrix](#rol-matrix) onderaan.

{chr(10).join(sections)}

## Rol-matrix {{ #rol-matrix }}

Welke rol gebruikt welk component? Een ✓ betekent dat de rol in deze
referentie-implementatie via de portal-shortcuts naar de UI van het
component wordt gestuurd. Een lege cel betekent dat de rol normaliter geen
directe toegang nodig heeft (toegang kan alsnog via JIT/break-glass).

{role_matrix}
"""


def _render_role_matrix(comps: list[Component]) -> str:
    # Alle unieke business-rollen verzamelen, exclude '*'.
    all_roles: set[str] = set()
    for c in comps:
        for r in c.roles_using:
            if r != "*":
                all_roles.add(r)

    role_order = [
        "wia_beoordelaar", "ww_handhaver", "wajong_arbeidsdeskundige",
        "crm_medewerker", "fez_analist", "smz_planner", "proactief_dienstverlener",
        "researcher", "data_steward", "data_engineer", "platform_admin",
    ]
    # Behoud volgorde + voeg onbekende rollen toe.
    roles = [r for r in role_order if r in all_roles] + sorted(all_roles - set(role_order))

    # Header: component-id's als kolommen kort houden.
    header = "| Rol | " + " | ".join(c.id for c in comps) + " |"
    sep = "|---|" + "|".join(["---"] * len(comps)) + "|"
    rows = [header, sep]
    for role in roles:
        cells = []
        for c in comps:
            if "*" in c.roles_using or role in c.roles_using:
                cells.append("✓")
            else:
                cells.append("")
        rows.append(f"| `{role}` | " + " | ".join(cells) + " |")
    return "\n".join(rows)


def render_datazones() -> str:
    return f"""---
title: Datazones
description: Medallion-architectuur (bronze/silver/gold) + sensitive vault — zone-scheiding en toegang.
---

# Datazones

Vier MinIO-buckets, elk met eigen Trino-catalog, plus een aparte vault voor
bijzondere persoonsgegevens (art. 9 AVG). De zone-naam in de portal en in
de OPA-policies zijn 1-op-1.

## Overzicht

| Catalog | Bucket | Inhoud | Toegang (default) |
|---|---|---|---|
| `bronze` | `odap-bronze` | Onveranderbare brondata (incl. raw PII) | data-engineers (JIT) |
| `silver` | `odap-silver` | Geconformeerd, gepseudonimiseerd waar mogelijk | analisten + engineers |
| `gold` | `odap-gold` | CGM-conforme business products | domein-rollen via RBAC |
| `sensitive` | `sensitive` | Bijzondere persoonsgegevens (art. 9 AVG, medisch) | strikt; 4-eyes principe |
| `sandbox` | `sandbox` | Gepseudonimiseerd — voor researchers | researcher (read-only) |

## Toegangsstrategie

```mermaid
flowchart LR
    bronze[bronze<br/>raw + PII] -- "ETL: pseudonimiseer" --> silver[silver<br/>geconformeerd]
    silver -- "dbt-modellen" --> gold[gold<br/>marts voor BI]
    bronze -- "alleen via vault-flow" --> sensitive[sensitive<br/>art. 9 AVG]
    silver -- "pseudo-export" --> sandbox[sandbox<br/>research]

    style sensitive fill:#fee,stroke:#c33
    style sandbox fill:#eef,stroke:#33c
```

OPA-policies zijn **format-agnostisch**: ze kijken naar
`catalog.schema.table`- en kolomnamen, niet naar het onderliggende
bestandsformaat. Switching tussen Delta en Iceberg laat de policies
onveranderd (zie [ADR-0002](../adr/0002-iceberg-vs-delta.md)).

## Wat zie je per rol?

Dit volgt 1-op-1 de rol-handleidingen:

- **WIA-beoordelaar / Wajong-arbeidsdeskundige / etc.** → primair `gold`,
  beperkt `silver` (eigen domein). Geen `bronze`.
- **Data-engineer** → `bronze` (JIT), `silver`, `gold`, `sensitive` (alleen
  via break-glass).
- **Data-steward** → read-only over alle zones (governance).
- **Researcher** → uitsluitend `sandbox`.
- **Platform-admin** → alles, maar elke query wordt audit-logged (zie
  [Runbook](../runbook.md#audit-trail)).

Welke kolommen je in een gold-mart precies ziet hangt af van de OPA-policies
in [`opa-policies-src/`](https://github.com/fresh-minds/FreshStackableDataPlatform/tree/main/opa-policies-src).
Zie [Identiteit & autorisatie](auth.md) voor de policy-flow.
"""


def render_auth() -> str:
    return f"""---
title: Identiteit & autorisatie
description: Hoe Keycloak en OPA samen bepalen wie wat mag zien.
---

# Identiteit & autorisatie

Toegang is geen kwestie van losse user-accounts per service — alle componenten
delegeren authenticatie naar **Keycloak** (OIDC) en autorisatie op queries
naar **Open Policy Agent (OPA)**.

## Auth-flow

```mermaid
sequenceDiagram
    participant U as Gebruiker (browser)
    participant K as Keycloak
    participant T as Trino
    participant O as OPA
    participant D as Data (MinIO via Hive)

    U->>K: GET /auth?client_id=trino
    K-->>U: redirect met code
    U->>T: GET /ui?code=…
    T->>K: token exchange
    K-->>T: id_token + role claims
    U->>T: SQL query
    T->>O: input {{ token, query, table, columns }}
    O-->>T: allow + row_filter + column_masks
    T->>D: pushdown query (gefilterd + gemaskeerd)
    D-->>T: gefilterde rijen
    T-->>U: resultaten
```

## Identity provider — Keycloak

- **Realm:** `uwv` in [`infrastructure/helm/keycloak/realm.json`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/infrastructure/helm/keycloak/realm.json)
- **Mock-rollen** in deze referentie:
    - Business: `wia_beoordelaar`, `ww_handhaver`, `wajong_arbeidsdeskundige`,
      `crm_medewerker`, `fez_analist`, `smz_planner`, `proactief_dienstverlener`,
      `researcher`
    - Tech: `data_steward`, `data_engineer`, `platform_admin`
- **MFA:** TOTP verplicht voor tech-rollen; aanbevolen voor business-rollen
  (configureerbaar in realm-export).
- **Token-claim** `groups` bevat de Keycloak-groepen → mapt naar OPA-rollen.

Elk component (Trino, Superset, Airflow, NiFi, OpenMetadata) configureert
Keycloak via een Stackable `AuthenticationClass` — zie
[`platform/02-authentication/`](https://github.com/fresh-minds/FreshStackableDataPlatform/tree/main/platform/02-authentication).

## Authorisatie — OPA + Rego

Trino delegeert elke query naar OPA via het `opa-authorizer`-plugin:

```
Trino-query ──► OPA bundle (uit ConfigMap) ──► allow/deny + row filters + column masks
```

De Rego-policies in [`opa-policies-src/`](https://github.com/fresh-minds/FreshStackableDataPlatform/tree/main/opa-policies-src):

| Policy | Doel |
|---|---|
| `trino-base.rego` | OIDC token-validatie, role-mapping |
| `trino-data-access.rego` | Catalog/schema/table-toegang per rol |
| `trino-doelbinding.rego` | Doelbinding (purpose) afdwingen op gold-tabellen |
| `trino-row-filters.rego` | Rij-filters per rol (bijv. WW-handhaver ziet alleen WW-claims) |
| `trino-column-masks.rego` | Kolom-maskering (PII, gezondheid → hash of `***`) |
| `trino-platform-roles.rego` | UWV-rol-definities (single source) |

Build van de bundle: `scripts/build-opa-bundle.sh`, geïntegreerd in
`make deploy-platform`.

!!! tip "Doelbinding eerst"
    Bij elke query controleert OPA of er een **geldig doel** is meegegeven
    (bijv. `uitkering`, `handhaving`, `onderzoek`). Zonder doel: deny.
    Doelbinding is harder dan rol — een WIA-beoordelaar zonder doel
    `uitkering` krijgt ook in zijn eigen mart geen data.

## Zie ook

- [ADR-0003 · OPA als Trino-authz](../adr/0003-opa-as-trino-authz.md)
- [ADR-0008 · Self-service data-access](../adr/0008-self-service-data-access.md)
- [Toegang aanvragen (handleiding)](../access-request-guide.md)
- [Compliance-mapping § AVG](../compliance-mapping.md)
"""


def render_tabelformaat() -> str:
    return f"""---
title: Tabel-formaat abstractie
description: Eén platform-config bepaalt Delta of Iceberg overal.
---

# Tabel-formaat abstractie

Eén centrale variabele bepaalt of het hele platform op Delta of Iceberg
draait. Geen hardcoded format-keuze in dbt-models, Spark-jobs, Trino-catalogs
of NiFi-flows.

```yaml
# platform-config.yaml
platform:
  table_format: delta   # delta | iceberg
```

## Wie leest die variabele?

| Component | Hoe |
|---|---|
| **Trino-catalogs** | Templates onder `platform/09-trino/catalogs/*.yaml.tmpl` worden gerenderd door `scripts/render-trino-catalogs.sh` op basis van `table_format`. Connector wordt `delta-lake` of `iceberg`. |
| **dbt** | `dbt_project.yml` zet `vars: table_format: "{{{{ env_var('TABLE_FORMAT', 'delta') }}}}"`. Macro `table_format_properties()` levert de juiste `properties{{}}` per model. |
| **Spark** | Env var `TABLE_FORMAT` op `SparkApplication`. Helper `spark-jobs/lib/lakehouse_io.py` schakelt `write_iceberg()` vs `write_delta()`. |
| **NiFi** | Twee templates onder `nifi-flows/templates/{{iceberg,delta}}/`. Per default deployen we de Delta-variant (= NiFi → Kafka, en Spark schrijft Delta). |
| **Airflow** | DAGs lezen `Variable.get("TABLE_FORMAT")`. Maintenance-DAG kiest `OPTIMIZE`/`VACUUM` (Delta) of `expire_snapshots`/`rewrite_data_files` (Iceberg). |

**Geen** hardcoded `delta` of `iceberg` buiten deze plekken.

## Waarom deze abstractie?

Zie [ADR-0002 · Iceberg vs Delta](../adr/0002-iceberg-vs-delta.md) voor de
afweging en [ADR-0006 · Delta gekozen voor deze implementatie](../adr/0006-delta-chosen-for-this-implementation.md)
voor waarom deze referentie-implementatie Delta default.

## Ingestion-pad bij Delta (afwijking van Iceberg-demo)

Stackable's referentie-demo `data-lakehouse-iceberg-trino-spark` gebruikt
NiFi's native `PutIceberg`-processor. Voor **Delta is er geen native NiFi-
processor**. Daarom wordt voor de Delta-route alle bron-data via NiFi naar
**Kafka** geschreven; Spark Structured Streaming consumeert Kafka en schrijft
naar Delta op MinIO.

```mermaid
flowchart LR
    Bron[Bron-mock] --> NiFi[NiFi<br/>PublishKafka]
    NiFi --> Kafka[Kafka topic<br/>uwv.&lt;domain&gt;.&lt;event&gt;]
    Kafka --> Spark[Spark Structured Streaming<br/>SparkApplication, K8s]
    Spark --> Delta[Delta-tabel in MinIO<br/>s3a://odap-bronze/...]
    Delta --> Hive[Hive Metastore registreert tabel]
```

Iceberg-pad (toekomstig of switch-back): NiFi's `PutIceberg` schrijft direct
naar bronze; Spark blijft beschikbaar voor silver/gold-transformaties.
"""


def render_naming() -> str:
    return f"""---
title: Naming conventions
description: Namen voor namespaces, schemas, topics, DNS — consistent over alle componenten.
---

# Naming conventions

Eén consistente naamgevingsstrategie maakt zoeken in OpenMetadata, lineage
en logs een stuk eenvoudiger. Alle componenten houden zich hieraan.

## Kubernetes namespaces

| Namespace | Inhoud |
|---|---|
| `odap-platform` | Stackable workloads (Trino, Spark, Kafka, NiFi, OPA, …) |
| `odap-data` | Synthetic data jobs, dbt-runners |
| `odap-meta` | OpenMetadata stack |
| `odap-monitoring` | Prometheus, Grafana, Vector |
| `odap-auth` | Keycloak |

## Trino-schemas

| Pattern | Voorbeelden |
|---|---|
| `bronze.uwv.<entity>` | `bronze.uwv.wia_aanvraag`, `bronze.uwv.ww_uitkering` |
| `silver.<domain>.<entity>` | `silver.wia.aanvraag_pseudo`, `silver.crm.contact` |
| `gold.<uc_id>.<artifact>` | `gold.uc01_wia_funnel.daily_kpi`, `gold.uc05_client_360.profile` |
| `sensitive.<domain>.<entity>` | `sensitive.medisch.diagnose` |

Domein-codes: `ww`, `wia`, `wajong`, `crm`, `fez`, `polisadm`, `smz`.

## dbt-modellen

```
<layer>_<domain>_<entity>.sql
```

Voorbeelden:

- `stg_wia_aanvraag.sql` — staging-laag
- `int_wia_funnel_daily.sql` — intermediate
- `mart_uc01_wia_funnel_daily.sql` — mart (gold)

## Kafka-topics

```
uwv.<domain>.<event>
```

Voorbeelden:

- `uwv.wia.aanvraag`
- `uwv.wia.beoordeling`
- `uwv.ww.uitkering`

## DNS

```
<service>.odap.local
```

Voor lokale k3d-clusters. In AKS-deploys (`example.com`)
rewrite de portal client-side; zie
[`portal/src/layouts/Layout.astro`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/portal/src/layouts/Layout.astro).

## OpenMetadata services

| Service-naam | Inhoud |
|---|---|
| `trino-prod` | Trino-instance met alle catalogs (bronze/silver/gold/sensitive/sandbox) |
| `dbt` | dbt-project (lineage + tests) |
| `superset-prod` | Superset BI (dashboards) |
| `airflow` | Airflow (pipeline-runs) |
| `kafka` | Kafka (event-topics + schemas) |
"""


def render_referentie() -> str:
    return f"""---
title: Originele referentie-architectuur
description: Het bronvoorstel waarvan deze repo de implementatie is.
---

# Originele referentie-architectuur

De huidige implementatie volgt:

- [`referentiearchitectuur-odap-data-analytics.md`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/referentiearchitectuur-odap-data-analytics.md)
  — 12 architectuurprincipes, 10 use-cases, CGM-entiteiten, Sensitive Vault,
  data-mesh, wettelijke mappen.
- [`requirements.md`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/requirements.md)
  — Volledige requirements-matrix: NORA, AVG, BIO/BIO2, NIS2, AI Act met
  R-* codes (70+ rules).
- [`odap-platform-mapping-research.md`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/odap-platform-mapping-research.md)
  — Technische blauwdruk: component-mapping Stackable → Kubernetes.

Deze pagina is een **navigatie-stub** — de bron-documenten staan in de
repo-root als ware ze A4-rapporten. Voor implementatie-details zie de
[Architectuur · Overzicht](index.md).

## Definition of Done

Het platform is "klaar" wanneer:

1. `make cluster && make bootstrap && make deploy-platform && make seed && make test`
   slaagt op een schoon k3d-cluster.
2. Superset toont dashboard "WIA Funnel" met 7 dagen synthetische data voor
   rol `data_steward`.
3. OpenMetadata toont end-to-end lineage van synthetische bron → dbt-model →
   Superset chart.
4. OPA weigert query op `client_360.bsn` voor rol zonder doel "uitkering";
   maskeert BSN voor `crm_medewerker`.
5. dbt-test `bsn_valid` faalt op een ingespoten ongeldige BSN-record.
6. OpenMetadata toont voor elke gold-tabel: eigenaar, doelbinding-tag,
   classificatie, bewaartermijn.
7. [`compliance-mapping`](../compliance-mapping.md) mapt elk
   R-NORA/AVG/BIO/NIS2 op een concreet bestand of setting.
8. CI-pipeline (GitHub Actions) groen op fresh clone.
9. Switching naar Iceberg vereist alleen wijziging in `platform-config.yaml`
   + Trino-catalog redeploy + dbt re-run — code blijft anders ongewijzigd.
10. Geen `latest`-tag, geen plaintext secret, geen TODO in productie-policy
    zonder ticket-id.
"""


def render_rollen_index(comps: list[Component]) -> str:
    matrix = _render_role_matrix(comps)
    return f"""---
title: Rollen — overzicht
description: Welke rollen het platform onderscheidt en wie wat ziet.
---

# Rollen op het platform

Het platform onderscheidt **11 menselijke rollen** + **1 systeemrol**,
gemodelleerd in [`infrastructure/helm/keycloak/realm.json`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/infrastructure/helm/keycloak/realm.json)
en [`opa-policies-src/data/role_mappings.json`](https://github.com/fresh-minds/FreshStackableDataPlatform/blob/main/opa-policies-src/data/role_mappings.json).

## Business-rollen (eindgebruikers)

| # | Rol | Domein | Handleiding |
|---|---|---|---|
| 1 | WIA-beoordelaar | AG / WIA | [01-wia-beoordelaar](../handbooks/01-wia-beoordelaar.md) |
| 2 | WW-handhaver | WW | [02-ww-handhaver](../handbooks/02-ww-handhaver.md) |
| 3 | Wajong-arbeidsdeskundige | AG / Wajong | [03-wajong-arbeidsdeskundige](../handbooks/03-wajong-arbeidsdeskundige.md) |
| 4 | CRM-medewerker | CRM / Klantcontact | [04-crm-medewerker](../handbooks/04-crm-medewerker.md) |
| 5 | FEZ-analist | Financiën | [05-fez-analist](../handbooks/05-fez-analist.md) |
| 6 | SMZ-planner | Sociaal-medische zaken | [06-smz-planner](../handbooks/06-smz-planner.md) |
| 7 | Proactief dienstverlener | Toeslagenwet (proactief) | [07-proactief-dienstverlener](../handbooks/07-proactief-dienstverlener.md) |
| 8 | Researcher | Onderzoek (sandbox) | [08-researcher](../handbooks/08-researcher.md) |

## Technische rollen (platform-team)

| # | Rol | Verantwoordelijkheid | Handleiding |
|---|---|---|---|
| 9 | Data-steward | Datakwaliteit, governance, lineage | [09-data-steward](../handbooks/09-data-steward.md) |
| 10 | Data-engineer | Pipelines, ingestion, transformaties | [10-data-engineer](../handbooks/10-data-engineer.md) |
| 11 | Platform-admin | Cluster, security, break-glass | [11-platform-admin](../handbooks/11-platform-admin.md) |

## Systeemrol

| # | Rol | Functie | Handleiding |
|---|---|---|---|
| 12 | Smoketest | Service-account voor automated tests + dbt-runs | [12-smoketest-systeem](../handbooks/12-smoketest-systeem.md) |

## Zes regels die voor iedereen gelden

1. **Doelbinding eerst** — gebruik data alleen voor de taak waarvoor je rol toegang heeft.
2. **Niets is "zomaar"** — elke query wordt gelogd, elke toegang is herleidbaar.
3. **Mens beslist** — algoritmes geven advies, jij neemt het besluit.
4. **Bij twijfel niet doen** — vraag eerst de data-steward of platform-admin.
5. **Geen schermafbeeldingen van persoonsgegevens** — ook niet voor bug-rapporten.
6. **Geen wachtwoorden delen** — ook niet "even snel" met collega's.

## Welke rol ziet welk component?

{matrix}

Een ✓ in `keycloak` betekent dat alle rollen erover SSO'en. Voor `multica`,
`prometheus`, en sommige observability-componenten beperken we toegang
expliciet tot platform-rollen.
"""


def render_use_cases_index() -> str:
    return f"""---
title: Use cases — overzicht
description: 11 concrete business-flows met scope, doelbinding, CGM-entiteiten en datapad.
---

# Use cases

Elf use-case-specs onder [`use-cases/`](https://github.com/fresh-minds/FreshStackableDataPlatform/tree/main/docs/use-cases),
elk met scope, CGM-entiteiten, doelbinding, AI-Act-classificatie en
Definition-of-Done-anchors.

| ID | Titel | Status | Domein | AI-Act |
|---|---|---|---|---|
| [UC-01](uc01-wia-funnel.md) | WIA-funnel-dashboard (DoD-anchor) | Mart aanwezig | AG/WIA | Laag |
| [UC-02](uc02-wajong-ai.md) | Wajong AI-ondersteuning (hoog-risico) | Placeholder | AG/Wajong | **Hoog** |
| [UC-03](uc03-ww-risk.md) | WW-risico-screening (verboden-grens) | Placeholder + guard-test | WW | Verboden-grens |
| [UC-04](uc04-proactieve-tw.md) | Proactieve TW-eligibility | Mart aanwezig | TW | Beperkt |
| [UC-05](uc05-client-360.md) | Klant-360 (gepseudonimiseerd) | Mart aanwezig | CRM | Laag |
| [UC-06](uc06-schadelast.md) | Schadelast-prognose 5 jaar | Mart aanwezig | FEZ | Laag |
| [UC-07](uc07-dq-polisadm.md) | DQ-dagrapport polisadministratie | Mart aanwezig | Polisadm | n.v.t. |
| [UC-08](uc08-smz-planning.md) | SMZ-capaciteitsplanning | Placeholder | SMZ | Beperkt |
| [UC-09](uc09-reint-effect.md) | Re-integratie-effectmeting | Mart aanwezig | Re-integratie | Beperkt |
| [UC-10](uc10-gegevensdiensten.md) | Gegevensdiensten-API | Placeholder | Cross-domein | n.v.t. |
| [UC-11](uc11-klantreis.md) | Integrale Klantreis (event-stream + fasen) | Mart aanwezig · [walkthrough](uc11-klantreis-walkthrough.md) | Cross-domein | Beperkt |

## UC-11 — speciale walkthrough

UC-11 heeft een aparte **demo-walkthrough** in
[uc11-klantreis-walkthrough](uc11-klantreis-walkthrough.md) —
stap-voor-stap rondleiding door alle platform-onderdelen, met directe
links naar de live UI's (portal, dbt-docs, OpenMetadata, Trino, Airflow,
Superset). Handig als presentatie-script of als onboarding-tour.

## Use-case format

Elke spec volgt dezelfde indeling:

- **Status in deze repo** — Volledig geïmplementeerd / Placeholder
- **Domein** — bv. AG/WIA, WW, CRM, FEZ
- **Risicoclassificatie** — laag / beperkt / hoog / verboden-grens (per AI Act)
- **AVG-grondslag** — art. 6 lid 1{{a,b,c,d,e,f}}
- **Bewaartermijn (gold)** — typisch 7 jaar (besluitvormingsdata)
- **Probleem** — waarom deze use-case bestaat
- **Doel** — wat moet er anders zijn na implementatie
- **Data** — bronnen, klassificaties, CGM-entiteiten
- **Architectuur-pad** — concrete repo-bestanden van bron → dashboard
- **DoD-anchor** — welk dbt-model + welke OPA-test bewijst dat het werkt
"""


def render_adr_index() -> str:
    return f"""---
title: Beslissingen (ADRs) — overzicht
description: Architecture Decision Records die de fundamentele keuzes vastleggen.
---

# Architecture Decision Records (ADRs)

Numbered, immutable. Een nieuwe beslissing krijgt een nieuw ADR; de oude
wordt niet bewerkt maar als "superseded by" gemarkeerd.

| ADR | Beslissing | Status |
|---|---|---|
| [0001](0001-stackable-as-base.md) | Stackable Data Platform als basis | Accepted |
| [0002](0002-iceberg-vs-delta.md) | Iceberg vs Delta — afweging | Superseded by 0006 |
| [0003](0003-opa-as-trino-authz.md) | OPA als Trino-autorisatie-engine | Accepted |
| [0004](0004-openmetadata-as-catalog.md) | OpenMetadata als catalog/lineage/DQ | Accepted |
| [0005](0005-dbt-trino-as-transform.md) | dbt-trino als transformatielaag | Accepted |
| [0006](0006-delta-chosen-for-this-implementation.md) | Delta gekozen voor deze implementatie | Accepted |
| [0007](0007-airflow-pipeline-architecture.md) | Airflow pipeline-architectuur | Accepted |
| [0008](0008-self-service-data-access.md) | Self-service data-access flow | Accepted |

## ADR-format

Elke ADR volgt dezelfde indeling:

- **Status** — Proposed / Accepted / Deprecated / Superseded by N
- **Context** — wat speelt er, welke krachten werken op de keuze
- **Beslissing** — wat is besloten
- **Gevolgen** — wat verandert er door deze keuze
- **Alternatieven** — wat is overwogen en waarom afgewezen
"""


def render_architecture_redirect() -> str:
    """Vervang de oude top-level architecture.md door een korte redirect-stub.

    De inhoud is verhuisd naar `architectuur/index.md` + de andere bestanden
    onder `architectuur/`. We laten dit bestand bestaan om verwijzingen
    elders niet te breken.
    """
    return """---
title: Architectuur (verplaatst)
description: De architectuur-documentatie is verplaatst naar /architectuur/.
---

# Architectuur is verplaatst

De architectuur-documentatie staat nu onder
[Architectuur · Overzicht](architectuur/index.md), opgedeeld in:

- [Overzicht](architectuur/index.md) — dataflow + lagen
- [Componenten](architectuur/componenten.md) — per-component pagina's
- [Datazones](architectuur/datazones.md)
- [Identiteit & autorisatie](architectuur/auth.md)
- [Tabel-formaat abstractie](architectuur/tabel-formaat.md)
- [Naming conventions](architectuur/naming.md)
- [Originele referentie](architectuur/referentie.md)
"""


def render_security() -> str:
    """Kopieer SECURITY.md naar docs/security.md met front matter."""
    security_path = ROOT / "SECURITY.md"
    if not security_path.exists():
        return f"""---
title: Security Policy
---

# Security Policy

_(SECURITY.md niet gevonden in repo-root — voeg toe en regenereer.)_
"""
    body = security_path.read_text(encoding="utf-8")
    return f"""---
title: Security Policy
description: Hoe kwetsbaarheden te rapporteren — NIS2-compliant disclosure flow.
---

{body}
"""


# ───────────────────────── extra assets ─────────────────────────


def render_extra_css() -> str:
    return """/* Auto-generated door scripts/docs_gen.py.
   Aanpassingen overleven niet — wijzig in de generator. */

/* platform-amber accent override op het Material amber-palet zodat het exact de
   portal-amber matcht (oklch(0.78 0.18 76) in de portal tokens). */
:root {
  --md-primary-fg-color:        #d68f00;
  --md-primary-fg-color--light: #ecb24a;
  --md-primary-fg-color--dark:  #a86d00;
  --md-accent-fg-color:         #d68f00;
}

[data-md-color-scheme="slate"] {
  --md-primary-fg-color:        #ecb24a;
  --md-accent-fg-color:         #ecb24a;
  --md-typeset-a-color:         #ecb24a;
}

/* Mermaid diagrammen iets meer ademruimte. */
.md-typeset .mermaid {
  text-align: center;
  margin: 1.5rem 0;
}

/* Grid-cards op de homepage: iets meer ademruimte. */
.md-typeset .grid.cards > ul > li {
  padding: 1.2rem 1.2rem 1.4rem;
}

/* Mono-tone code-tags binnen lopende tekst — strak, niet schreeuwend. */
.md-typeset code {
  background-color: var(--md-code-bg-color);
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 0.92em;
}

/* Anchored sub-headings (sectie-anchors zoals #ingestion) krijgen wat
   bovenmarge zodat de sticky-header ze niet afdekt. */
.md-typeset h3[id] {
  scroll-margin-top: 4rem;
}
"""


def render_favicon_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#d68f00"/>
  <text x="16" y="22" font-family="Inter, sans-serif" font-weight="700" font-size="13"
        fill="#1a1a1a" text-anchor="middle">UWV</text>
</svg>
"""


def render_logo_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 32">
  <rect x="0" y="2" width="28" height="28" rx="5" fill="#d68f00"/>
  <text x="14" y="22" font-family="Inter, sans-serif" font-weight="700" font-size="12"
        fill="#1a1a1a" text-anchor="middle">UWV</text>
  <text x="36" y="22" font-family="Inter, sans-serif" font-weight="500" font-size="15"
        fill="currentColor">Platform Docs</text>
</svg>
"""


# ───────────────────────── tags page (stub for plugins.tags) ─────────────────────────


def render_tags_page() -> str:
    return """---
title: Tags
description: Browsing per tag — handig om alle "compliance"-pagina's of alle "operations"-pagina's snel te vinden.
---

# Tags

<!-- material-tags-plugin vult dit automatisch met alle tags die in
     individuele pagina's worden gedeclareerd via front-matter `tags: [...]`.
     Voeg tags toe in een nieuwe doc als volgt:

     ---
     tags:
       - compliance
       - avg
     ---

-->
"""


# ───────────────────────── main ─────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Genereer docs-site pagina's uit portal/src/data/components.ts.")
    parser.add_argument("--check", action="store_true", help="Faal als output drift t.o.v. bron-bestand.")
    args = parser.parse_args()

    comps, stages = load_registry()

    targets: dict[Path, str] = {
        DOCS_DIR / "index.md": render_index(stages, comps),
        DOCS_DIR / "architecture.md": render_architecture_redirect(),
        DOCS_DIR / "architectuur" / "index.md": render_architectuur_index(stages, comps),
        DOCS_DIR / "architectuur" / "componenten.md": render_componenten(comps, stages),
        DOCS_DIR / "architectuur" / "datazones.md": render_datazones(),
        DOCS_DIR / "architectuur" / "auth.md": render_auth(),
        DOCS_DIR / "architectuur" / "tabel-formaat.md": render_tabelformaat(),
        DOCS_DIR / "architectuur" / "naming.md": render_naming(),
        DOCS_DIR / "architectuur" / "referentie.md": render_referentie(),
        DOCS_DIR / "rollen" / "index.md": render_rollen_index(comps),
        DOCS_DIR / "use-cases" / "index.md": render_use_cases_index(),
        DOCS_DIR / "adr" / "index.md": render_adr_index(),
        DOCS_DIR / "security.md": render_security(),
        DOCS_DIR / "tags.md": render_tags_page(),
        DOCS_DIR / "assets" / "extra.css": render_extra_css(),
        DOCS_DIR / "assets" / "favicon.svg": render_favicon_svg(),
        DOCS_DIR / "assets" / "logo.svg": render_logo_svg(),
    }

    if args.check:
        drift: list[str] = []
        for path, content in targets.items():
            expected = _inject_banner(content) if path.suffix == ".md" else content
            if not path.exists() or path.read_text(encoding="utf-8") != expected:
                drift.append(str(path.relative_to(ROOT)))
        if drift:
            print("docs_gen --check: drift gedetecteerd voor:", file=sys.stderr)
            for d in drift:
                print(f"  - {d}", file=sys.stderr)
            print("\nLos op met: python scripts/docs_gen.py", file=sys.stderr)
            sys.exit(1)
        print("docs_gen --check: geen drift.")
        return

    for path, content in targets.items():
        write(path, content)
    print(f"docs_gen: geschreven {len(targets)} bestanden.")


if __name__ == "__main__":
    main()
