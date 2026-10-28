#!/usr/bin/env python3
"""Regenerate the portal's explicitly synthetic sample from the shared extractor."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='odap-jobs-portal-') as tmp:
    subprocess.run([sys.executable, str(ROOT / 'examples/dutch-it-jobs/job_market.py'),
                    '--mode', 'demo', '--date', '2026-10-28', '--days', '7', '--output-dir', tmp], check=True)
    observations = [json.loads(line) for path in sorted(Path(tmp).glob('snapshot_date=*/normalized/observations.jsonl'))
                    for line in path.read_text().splitlines() if line.strip()]
    assert observations and all(row['is_synthetic'] for row in observations)
    (ROOT / 'portal/public/job-market-demo.json').write_text(json.dumps({
        'is_synthetic': True, 'generated_from': 'examples/dutch-it-jobs/job_market.py --mode demo --date 2026-10-28 --days 7',
        'observations': observations}, ensure_ascii=False, indent=2) + '\n')
