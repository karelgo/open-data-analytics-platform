"""Reference backend voor de Academy auto-checks en voortgang-sync.

Loopt naast de portal-nginx (zelfde pod of een sidecar). De portal nginx
proxyt /api/learn/* naar deze service op poort 8088. Geen state op disk —
voortgang gaat naar Keycloak user-attributes via de admin-API.

Endpoints
---------
GET  /api/learn/progress
PUT  /api/learn/progress              {"progress": {...}}
GET  /api/learn/check/{check_id}      → {"ok": bool, "msg": str}

Vereiste env
------------
KEYCLOAK_URL                http(s)://keycloak.odap.local:8443
KEYCLOAK_REALM              uwv
KEYCLOAK_ADMIN_CLIENT_ID    portal-backend
KEYCLOAK_ADMIN_CLIENT_SEC   <secret>          (service-account)
TRINO_URL                   http://trino-coordinator:8080  (voor checks)
PROMETHEUS_URL              http://prometheus:9090         (voor checks)

Run lokaal
----------
    pip install fastapi uvicorn requests python-keycloak
    KEYCLOAK_URL=... uvicorn portal.scripts.learn-backend:app --port 8088
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

log = logging.getLogger("learn-backend")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="UDP Academy backend", version="0.1.0")

KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "uwv")
ATTR_KEY = "udp_progress"

PROGRESS_KEY_RE = re.compile(r"^[a-z_]+/(foundation|practitioner|expert)/\d+$")


def _username_from_request(req: Request) -> str:
    """oauth2-proxy zet X-Auth-Request-User; we vertrouwen alleen die header
    achter de proxy. Zonder header → 401 (geen anonymous voortgang)."""
    user = req.headers.get("x-auth-request-user")
    if not user:
        raise HTTPException(status_code=401, detail="not authenticated")
    return user


def _kc_admin_token() -> str:
    """Service-account token tegen Keycloak admin-API."""
    import requests

    if not KEYCLOAK_URL:
        raise HTTPException(status_code=503, detail="KEYCLOAK_URL not set")
    cid = os.environ["KEYCLOAK_ADMIN_CLIENT_ID"]
    sec = os.environ["KEYCLOAK_ADMIN_CLIENT_SEC"]
    r = requests.post(
        f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token",
        data={"grant_type": "client_credentials", "client_id": cid, "client_secret": sec},
        timeout=5,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _kc_user_attr(user: str, write: dict[str, Any] | None = None) -> dict[str, Any]:
    import requests

    token = _kc_admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    base = f"{KEYCLOAK_URL}/admin/realms/{KEYCLOAK_REALM}/users"

    # Lookup user-id
    r = requests.get(base, headers=headers, params={"username": user, "exact": True}, timeout=5)
    r.raise_for_status()
    users = r.json()
    if not users:
        raise HTTPException(status_code=404, detail=f"user not found: {user}")
    uid = users[0]["id"]

    if write is not None:
        # Merge + write back
        attrs = users[0].get("attributes", {})
        attrs[ATTR_KEY] = [str(write)]  # Keycloak attrs are arrays of strings
        r = requests.put(
            f"{base}/{uid}",
            headers=headers,
            json={"attributes": attrs},
            timeout=5,
        )
        r.raise_for_status()
        return write

    return users[0].get("attributes", {})


@app.get("/api/learn/progress")
async def get_progress(req: Request) -> JSONResponse:
    user = _username_from_request(req)
    attrs = _kc_user_attr(user)
    raw = (attrs.get(ATTR_KEY) or ["{}"])[0]
    import json

    try:
        progress = json.loads(raw)
    except Exception:
        progress = {}
    return JSONResponse({"user": user, "progress": progress})


@app.put("/api/learn/progress")
async def put_progress(req: Request) -> JSONResponse:
    user = _username_from_request(req)
    body = await req.json()
    progress = body.get("progress", {})
    if not isinstance(progress, dict):
        raise HTTPException(status_code=400, detail="progress must be an object")
    # Filter alleen valide keys, anders kan een client willekeurige attrs schrijven.
    cleaned = {k: v for k, v in progress.items() if PROGRESS_KEY_RE.match(k) and v in {"done", "in-progress"}}
    import json

    _kc_user_attr(user, write=json.dumps(cleaned))
    return JSONResponse({"ok": True, "stored": len(cleaned)})


# ─── Auto-checks per module ─────────────────────────────────────────────
# Elke check is een functie die {ok, msg} teruggeeft. Voeg toe naar smaak.

def _check_wia_practitioner_query(user: str) -> dict[str, Any]:
    # Probeer Trino audit-log: is er query met "doel: beoordeling/uitkering"
    # in de laatste 24u door deze user, op silver.wia.aanvraag, met regio_code-filter?
    # Zie tests/smoke/test_audit_query.py voor patroon.
    return {"ok": False, "msg": "audit-log koppeling niet geconfigureerd"}


def _check_engineer_pipeline(user: str) -> dict[str, Any]:
    # Read latest CI-run voor user's branch op tests/smoke/test_xyz_e2e.py.
    return {"ok": False, "msg": "CI-koppeling niet geconfigureerd"}


def _check_ping(_user: str) -> dict[str, Any]:
    """Liveness-style check, geen externe calls — gebruikt door readinessProbe."""
    return {"ok": True, "msg": "academy backend bereikbaar"}


CHECKS = {
    "_ping": _check_ping,
    "wia_practitioner_query": _check_wia_practitioner_query,
    "engineer_practitioner_pipeline": _check_engineer_pipeline,
    # Voeg verdere checks per module-id toe wanneer ondersteunende endpoints
    # beschikbaar zijn (Trino audit-log, CI-resultaten, OpenMetadata-API).
}


@app.get("/api/learn/check/{check_id}")
async def run_check(check_id: str, req: Request) -> JSONResponse:
    fn = CHECKS.get(check_id)
    if fn is None:
        raise HTTPException(status_code=404, detail=f"unknown check: {check_id}")
    # _ping vereist geen authenticatie — anders zou de readinessProbe falen.
    user = "_probe" if check_id == "_ping" else _username_from_request(req)
    try:
        result = fn(user)
    except Exception as exc:
        log.exception("check failed: %s", check_id)
        result = {"ok": False, "msg": f"check error: {exc}"}
    return JSONResponse(result)
