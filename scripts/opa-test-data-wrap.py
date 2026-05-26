#!/usr/bin/env python3
"""Wrap opa-policies-src/data/role_mappings.json zodat `opa test` dezelfde
data-paden ziet als de Stackable OpaCluster in productie.

Stackable's opa-bundle-loader mount de ConfigMap onder
`data.configmap["<configmap-name>"]["<namespace>"]`. Onze rego-regels lezen
data via `data.configmap["opa-trino-bundle"]["odap-platform"].role_mappings.*`.

`opa test` weet niets van die conventie en laadt JSON op `data.<root>`. Dit
script wrapt de bron-JSON in dezelfde structuur als de productie-bundle,
zodat dezelfde regels in test én in productie werken — geen rego-conditionals
nodig.

Tevens strippen we `_`-prefixed velden (commentaar in de bron-JSON), conform
build-opa-bundle.sh.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def strip_underscored(obj):
    """Verwijder keys die met `_` beginnen — die zijn alleen commentaar."""
    if isinstance(obj, dict):
        return {k: strip_underscored(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [strip_underscored(v) for v in obj]
    return obj


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--src",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "opa-policies-src"
        / "data"
        / "role_mappings.json",
        help="Bron-JSON met top-level key `role_mappings`.",
    )
    parser.add_argument(
        "--dst",
        type=Path,
        required=True,
        help="Doel-pad voor de wrapped JSON.",
    )
    parser.add_argument(
        "--configmap-name",
        default="opa-trino-bundle",
        help="ConfigMap-naam (default: opa-trino-bundle).",
    )
    parser.add_argument(
        "--namespace",
        default="odap-platform",
        help="Kubernetes-namespace (default: odap-platform).",
    )
    args = parser.parse_args()

    if not args.src.exists():
        print(f"ERROR: source JSON niet gevonden: {args.src}", file=sys.stderr)
        return 1

    with args.src.open(encoding="utf-8") as fh:
        raw = json.load(fh)

    clean = strip_underscored(raw)
    # We dubbel-publishen onder twee paden:
    #   - data.configmap[name][namespace].*  (productie-pad; Stackable convention)
    #   - data.<root keys>                   (root-pad; voor legacy tests die
    #                                         `with data.role_mappings as ...` gebruiken)
    # Beide blijven consistent omdat ze van dezelfde bron komen.
    wrapped: dict = {
        "configmap": {
            args.configmap_name: {
                args.namespace: clean,
            }
        }
    }
    if isinstance(clean, dict):
        for k, v in clean.items():
            wrapped[k] = v

    args.dst.parent.mkdir(parents=True, exist_ok=True)
    with args.dst.open("w", encoding="utf-8") as fh:
        json.dump(wrapped, fh, indent=2, sort_keys=True)
    print(f"[opa-test-data-wrap] {args.src.name} → {args.dst} "
          f"(under data.configmap.{args.configmap_name}.{args.namespace})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
