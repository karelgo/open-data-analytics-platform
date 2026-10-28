#!/usr/bin/env python3
"""Validate resolved, inherited governance metadata for every active dbt model.

Run dbt parse first. Checking the manifest prevents a new schema file layout
from silently bypassing the governance check.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED = {
    'domain', 'legal_basis', 'purpose-limitation', 'bio_classificatie',
    'retention period_jaren', 'eigenaar', 'pii_kolommen', 'risk_tier',
}


def main():
    path = Path(__file__).resolve().parents[2] / 'dbt/target/manifest.json'
    if not path.exists():
        print('FAIL: dbt manifest missing; run dbt parse first', file=sys.stderr)
        return 1
    nodes = [node for node in json.loads(path.read_text())['nodes'].values()
             if node.get('resource_type') == 'model']
    errors = []
    for node in nodes:
        missing = REQUIRED - node.get('config', {}).get('meta', {}).keys()
        if missing:
            errors.append(f"{node['name']}: missing metadata {sorted(missing)}")
    if not nodes:
        errors.append('No active models found')
    for error in errors:
        print(f'FAIL: {error}', file=sys.stderr)
    print(f'Checked resolved governance metadata on {len(nodes)} models')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
