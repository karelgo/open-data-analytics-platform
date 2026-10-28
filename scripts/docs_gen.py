#!/usr/bin/env python3
"""Generate component/decision indexes while preserving authored job-market docs.

Run normally to write the indexes, or with --check to verify their content.
The portal component registry is the source for the component inventory.
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


# Only stable registry/decision indexes are generated. The job-market landing,
# architecture, data dictionary and handbooks are authored documentation.

def targets():
    comps, stages = load_registry()
    components = "# Platform components\n\nThe active data journey is [Dutch IT Job Market](../use-cases/dutch-it-job-market.md). Optional infrastructure is listed here for reference; it is not required by that batch pipeline.\n\n| Component | Role | Stage |\n|---|---|---|\n"
    for comp in comps:
        components += f"| {comp.name} | {comp.short} | {comp.stage} |\n"
    decisions = "# Architecture decisions\n\nDecisions record the platform's history. Earlier domain examples mentioned in these records are historical; the active use case is [Dutch IT Job Market](../use-cases/dutch-it-job-market.md).\n\n"
    for path in sorted((DOCS_DIR / "adr").glob("[0-9]*.md")):
        title = next((line.lstrip("# ") for line in path.read_text().splitlines() if line.startswith("# ")), path.stem)
        decisions += f"- [{title}]({path.name})\n"
    security = (ROOT / "SECURITY.md").read_text()
    return {DOCS_DIR / "architecture/components.md": components, DOCS_DIR / "adr/index.md": decisions, DOCS_DIR / "security.md": security}


def main():
    parser = argparse.ArgumentParser(description="Generate platform component and decision indexes without overwriting authored use-case documentation.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    drift = []
    for path, content in targets().items():
        if args.check:
            if not path.exists() or path.read_text() != content:
                drift.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    if drift:
        raise SystemExit("Generated documentation drift: " + ", ".join(drift))
    print("Documentation indexes verified." if args.check else "Documentation indexes generated.")


if __name__ == "__main__":
    main()
