#!/usr/bin/env python3
"""CI-check: platform-config.yaml ↔ platform-config-cm.yaml stay in sync.

Per ADR-0010, the YAML file at repo root is the design-time source of truth
and the ConfigMap at `platform/00-namespaces/platform-config-cm.yaml` is the
runtime mirror. When you edit one you must edit the other. This script fails
the CI build if the documented key-pairs no longer agree.

Mapping table — extend when new keys land in either side.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
YAML_PATH = ROOT / "platform-config.yaml"
CM_PATH = ROOT / "platform" / "00-namespaces" / "platform-config-cm.yaml"

# (dot.path.in.yaml, key.in.configmap.data)
# Add new pairs here whenever you wire a config-value into the runtime CM.
KEY_PAIRS: list[tuple[str, str]] = [
    ("platform.table_format", "TABLE_FORMAT"),
    ("platform.catalog_backend", "CATALOG_BACKEND"),
    ("platform.object_store", "OBJECT_STORE"),
    ("platform.region", "REGION"),
    ("platform.scale_profile", "SCALE_PROFILE"),
    ("buckets.raw", "BUCKET_RAW"),
    ("use_case.name", "USE_CASE"),
    ("use_case.schedule", "JOBS_SCHEDULE"),
    ("use_case.timezone", "JOBS_TIMEZONE"),
    ("use_case.default_mode", "JOBS_MODE"),
    ("buckets.bronze", "BUCKET_BRONZE"),
    ("buckets.silver", "BUCKET_SILVER"),
    ("buckets.gold", "BUCKET_GOLD"),
    ("buckets.sensitive", "BUCKET_SENSITIVE"),
    ("buckets.staging", "BUCKET_STAGING"),
    ("buckets.checkpoints", "BUCKET_CHECKPOINTS"),
    ("buckets.meta", "BUCKET_META"),
]


def dot_get(obj: dict, path: str):
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def main() -> int:
    if not YAML_PATH.exists():
        print(f"FAIL: {YAML_PATH} not found", file=sys.stderr)
        return 1
    if not CM_PATH.exists():
        print(f"FAIL: {CM_PATH} not found", file=sys.stderr)
        return 1

    yaml_doc = yaml.safe_load(YAML_PATH.read_text())
    cm_doc = yaml.safe_load(CM_PATH.read_text())

    # The ConfigMap file contains a leading comment-only document; pick the
    # first manifest that has `kind: ConfigMap`.
    if isinstance(cm_doc, list):
        cm_doc = next(
            (d for d in cm_doc if isinstance(d, dict) and d.get("kind") == "ConfigMap"),
            None,
        )
    cm_data = (cm_doc or {}).get("data") or {}
    if not cm_data:
        print(f"FAIL: {CM_PATH} has no data block", file=sys.stderr)
        return 1

    mismatches: list[str] = []
    missing_in_yaml: list[str] = []
    missing_in_cm: list[str] = []

    for yaml_key, cm_key in KEY_PAIRS:
        yaml_val = dot_get(yaml_doc, yaml_key)
        cm_val = cm_data.get(cm_key)
        if yaml_val is None:
            missing_in_yaml.append(yaml_key)
            continue
        if cm_val is None:
            missing_in_cm.append(cm_key)
            continue
        # Cast both to str — ConfigMap values are always strings; the YAML
        # might have `region: eu-nl-1` (str) but `scale_profile: scaled-down`
        # (str) so this is uniform.
        if str(yaml_val) != str(cm_val):
            mismatches.append(
                f"  - {yaml_key} = {yaml_val!r}  vs  data.{cm_key} = {cm_val!r}"
            )

    failed = bool(mismatches or missing_in_yaml or missing_in_cm)
    if failed:
        print("FAIL: platform-config drift detected", file=sys.stderr)
        if mismatches:
            print("Mismatched values:", file=sys.stderr)
            print("\n".join(mismatches), file=sys.stderr)
        if missing_in_yaml:
            print(
                f"Missing in {YAML_PATH.name}: {', '.join(missing_in_yaml)}",
                file=sys.stderr,
            )
        if missing_in_cm:
            print(
                f"Missing in {CM_PATH.name} data block: {', '.join(missing_in_cm)}",
                file=sys.stderr,
            )
        print(
            "\nFix: bring the two files into sync, or update KEY_PAIRS in this script.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {len(KEY_PAIRS)} key pairs match between YAML and ConfigMap.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
