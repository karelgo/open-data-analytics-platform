#!/usr/bin/env python3
"""Improvements #11 — CI-check dat elke dbt mart-model verplichte meta-velden heeft.

Gebruikt door `.github/workflows/dbt-parse.yml`. Faalt non-zero als één of meer
mart-models een verplicht `meta`-veld missen. Strict op marts; soft op staging.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

# Verplichte meta-velden per laag.
REQUIRED_MARTS = [
    "domain",
    "legal_basis",
    "purpose-limitation",
    "bio_classificatie",
    "retention period_jaren",
    "eigenaar",
    "pii_kolommen",
    "risk_tier",
]

REQUIRED_STAGING = [
    "domain",
    "purpose-limitation",
    "bio_classificatie",
    "eigenaar",
]


def check_yml(path: Path, required: list[str]) -> list[str]:
    """Returnt lijst van violations in `path`; leeg = OK."""
    with path.open() as f:
        try:
            data = yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:
            return [f"YAML parse error: {exc}"]

    violations: list[str] = []
    for model in data.get("models", []):
        meta = model.get("meta") or {}
        # Sta toe dat schema.yml een `placeholder: true` flag heeft (UC-02 etc.)
        if meta.get("placeholder"):
            continue
        for field in required:
            if field not in meta:
                violations.append(f"{model['name']}: missing meta.{field}")
            else:
                value = meta[field]
                if (
                    isinstance(value, list)
                    and len(value) == 0
                    and field != "pii_kolommen"
                ):
                    violations.append(f"{model['name']}: meta.{field} is leeg")
    return violations


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    dbt_models = repo_root / "dbt" / "models"

    fail_count = 0

    print("== Marts (strict) ==")
    for yml in sorted(dbt_models.glob("marts/**/_*.yml")):
        violations = check_yml(yml, REQUIRED_MARTS)
        rel = yml.relative_to(repo_root)
        if not violations:
            print(f"  OK   {rel}")
        else:
            for v in violations:
                print(f"  FAIL {rel}: {v}")
            fail_count += len(violations)

    print()
    print("== Staging (best-effort) ==")
    for yml in sorted(dbt_models.glob("staging/**/_*.yml")):
        violations = check_yml(yml, REQUIRED_STAGING)
        rel = yml.relative_to(repo_root)
        if not violations:
            print(f"  OK   {rel}")
        else:
            # Staging is soft — log as warning, don't fail
            for v in violations:
                print(f"  WARN {rel}: {v}")

    print()
    if fail_count > 0:
        print(f"FAIL: {fail_count} verplichte meta-velden ontbreken in marts.")
        return 1
    print("OK: alle marts hebben alle verplichte meta-velden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
