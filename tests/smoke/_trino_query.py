"""Trino REST query helper.

Stackable 26.3 dropped the bundled trino CLI from the server image; smoke
tests previously called `/stackable/trino-cli/trino`. This helper runs the
same queries via the REST API using only stdlib (urllib + ssl + base64).

Invoked from a smoke test as:
  kubectl -n NS exec sts/trino-coordinator-default -c trino -- \
    python3 /tmp/_trino_query.py "SHOW CATALOGS"
or piped via stdin from kubectl cp + exec.
"""
import base64
import json
import os
import ssl
import sys
import urllib.request

USER = os.environ.get("TRINO_USER", "smoketest")
PASSWORD = os.environ.get("TRINO_PASSWORD", "")
SERVER = os.environ.get("TRINO_SERVER", "https://localhost:8443")

if len(sys.argv) < 2:
    sys.exit("usage: _trino_query.py 'SQL'")

query = sys.argv[1]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Stackable TrinoCluster met `authentication: []` accepteert alleen
# X-Trino-User; Basic auth zou 401 geven. Alleen sturen als password gezet.
headers = {
    "X-Trino-User": USER,
    "Content-Type": "text/plain",
}
if PASSWORD:
    auth = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
    headers["Authorization"] = f"Basic {auth}"

req = urllib.request.Request(
    f"{SERVER}/v1/statement", data=query.encode(), method="POST", headers=headers
)
resp = json.loads(urllib.request.urlopen(req, context=ctx).read())

rows = list(resp.get("data") or [])
while resp.get("nextUri"):
    next_req = urllib.request.Request(resp["nextUri"], headers=headers)
    resp = json.loads(urllib.request.urlopen(next_req, context=ctx).read())
    if resp.get("data"):
        rows.extend(resp["data"])
    if resp.get("error"):
        sys.exit(f"Trino error: {resp['error']}")

for row in rows:
    print("\t".join("" if v is None else str(v) for v in row))
