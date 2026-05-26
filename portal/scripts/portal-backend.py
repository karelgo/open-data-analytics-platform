"""Portal-backend voor recents + favorites + search aggregator.

Loopt als een aparte Pod naast de portal-nginx. nginx proxyt
/api/portal/* naar deze service op poort 8089 (configureerbaar via
PORT env). State op disk via SQLite — één tabel per feature, primary
key op (user_email, item_key) zodat upserts idempotent zijn.

Endpoints
---------
GET    /api/portal/recents              → list (last 20 per user, DESC opened_at)
POST   /api/portal/recents              {key, type, service, title, subtitle, href}
GET    /api/portal/favorites            → list (all favorites per user, DESC starred_at)
POST   /api/portal/favorites            {key, type, service, title, subtitle, href}
DELETE /api/portal/favorites/{key}      → remove favorite
GET    /api/portal/search?q=…           → aggregated results across services
GET    /api/portal/_ping                liveness (no auth)

Auth
----
oauth2-proxy zet X-Auth-Request-Email; we vertrouwen alleen die header
achter de proxy. Zonder header → 401.

Vereiste env
------------
PORTAL_DB_PATH       /var/lib/portal-backend/portal.db   (default)
PORT                 8089                                (default)
OPENMETADATA_URL     http://openmetadata-server.odap-platform.svc:8585  (optional)
OPENMETADATA_TOKEN   <jwt>                               (optional bot-token)
AIRFLOW_URL          http://airflow-webserver.odap-platform.svc:8080 (optional)
AIRFLOW_USER         <user>                              (optional)
AIRFLOW_PASS         <pass>                              (optional)
SUPERSET_URL         http://superset.odap-platform.svc:8088  (optional)
GRAFANA_URL          http://prometheus-grafana.odap-monitoring.svc  (optional)
GRAFANA_API_KEY      <key>                               (optional)

Run lokaal
----------
    pip install fastapi 'uvicorn[standard]' pydantic httpx
    PORTAL_DB_PATH=./portal.db uvicorn portal.scripts.portal-backend:app --port 8089
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import time
from collections import deque
from contextlib import closing
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

log = logging.getLogger("portal-backend")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="UDP Portal backend", version="0.1.0")

DB_PATH = os.environ.get("PORTAL_DB_PATH", "/var/lib/portal-backend/portal.db")
MAX_RECENTS = 20  # how many recent items to keep per user


# ─── DB setup ────────────────────────────────────────────────────────────
def _db() -> sqlite3.Connection:
    """Open a fresh connection. SQLite is single-writer; we keep per-request
    connections short-lived to avoid lock contention. Foreign keys aren't
    needed (no relations between tables). Row factory returns dicts."""
    conn = sqlite3.connect(DB_PATH, isolation_level=None)  # autocommit
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")  # better concurrency
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


@app.on_event("startup")
def _ensure_schema() -> None:
    """Create tables if they don't exist. Idempotent — safe to run on every
    pod start. Schema migrations would go here too."""
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    with closing(_db()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS recents (
              user_email TEXT NOT NULL,
              item_key   TEXT NOT NULL,
              type       TEXT NOT NULL,
              service    TEXT NOT NULL,
              title      TEXT NOT NULL,
              subtitle   TEXT NOT NULL DEFAULT '',
              href       TEXT NOT NULL,
              opened_at  TEXT NOT NULL DEFAULT (datetime('now')),
              PRIMARY KEY (user_email, item_key)
            );
            CREATE INDEX IF NOT EXISTS idx_recents_user_opened
              ON recents (user_email, opened_at DESC);

            CREATE TABLE IF NOT EXISTS favorites (
              user_email TEXT NOT NULL,
              item_key   TEXT NOT NULL,
              type       TEXT NOT NULL,
              service    TEXT NOT NULL,
              title      TEXT NOT NULL,
              subtitle   TEXT NOT NULL DEFAULT '',
              href       TEXT NOT NULL,
              starred_at TEXT NOT NULL DEFAULT (datetime('now')),
              PRIMARY KEY (user_email, item_key)
            );
            CREATE INDEX IF NOT EXISTS idx_favorites_user_starred
              ON favorites (user_email, starred_at DESC);
            """
        )
    log.info("portal-backend ready: %s", DB_PATH)


# ─── Auth ────────────────────────────────────────────────────────────────
def _email_from_request(req: Request) -> str:
    """oauth2-proxy passes the user's email to upstream. Different versions /
    configs use different header names — we accept the three commonly-set
    variants in order of preference. Empty / missing → 401 (no anonymous state).

    Headers checked (first hit wins):
      - X-Auth-Request-Email  : set by oauth2-proxy when `set_xauthrequest=true`
                                on the upstream request (newer versions)
      - X-Forwarded-Email     : standard upstream header when
                                `pass_user_headers=true`
      - X-Auth-Request-User   : username fallback
    """
    for hdr in ("x-auth-request-email", "x-forwarded-email", "x-auth-request-user"):
        val = req.headers.get(hdr, "").strip()
        if val:
            return val
    raise HTTPException(status_code=401, detail="not authenticated")


# ─── Schemas ─────────────────────────────────────────────────────────────
class Item(BaseModel):
    """Body voor POST /api/portal/recents en /api/portal/favorites.
    De `key` is een opaque identifier (client-side gegenereerd) zodat
    dezelfde service/href een idempotente upsert geeft."""
    key:      str = Field(..., min_length=1, max_length=300)
    type:     str = Field(..., min_length=1, max_length=40)
    service:  str = Field(..., min_length=1, max_length=40)
    title:    str = Field(..., min_length=1, max_length=300)
    subtitle: str = Field(default="", max_length=300)
    href:     str = Field(..., min_length=1, max_length=1000)


# ─── Recents ─────────────────────────────────────────────────────────────
@app.get("/api/portal/recents")
async def get_recents(req: Request) -> JSONResponse:
    email = _email_from_request(req)
    with closing(_db()) as conn:
        rows = conn.execute(
            """
            SELECT item_key AS key, type, service, title, subtitle, href, opened_at
            FROM recents
            WHERE user_email = ?
            ORDER BY opened_at DESC
            LIMIT ?
            """,
            (email, MAX_RECENTS),
        ).fetchall()
    return JSONResponse({"items": [dict(r) for r in rows]})


@app.post("/api/portal/recents")
async def post_recents(item: Item, req: Request) -> JSONResponse:
    email = _email_from_request(req)
    with closing(_db()) as conn:
        # UPSERT — bumps opened_at on every call. After insert, prune the
        # oldest entries beyond MAX_RECENTS to keep the table small per user.
        conn.execute(
            """
            INSERT INTO recents (user_email, item_key, type, service, title, subtitle, href, opened_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT (user_email, item_key) DO UPDATE SET
              type     = excluded.type,
              service  = excluded.service,
              title    = excluded.title,
              subtitle = excluded.subtitle,
              href     = excluded.href,
              opened_at = datetime('now')
            """,
            (email, item.key, item.type, item.service, item.title, item.subtitle, item.href),
        )
        # Prune older entries beyond MAX_RECENTS.
        conn.execute(
            """
            DELETE FROM recents
            WHERE user_email = ?
              AND item_key NOT IN (
                SELECT item_key FROM recents
                WHERE user_email = ?
                ORDER BY opened_at DESC
                LIMIT ?
              )
            """,
            (email, email, MAX_RECENTS),
        )
    return JSONResponse({"ok": True})


# ─── Favorites ───────────────────────────────────────────────────────────
@app.get("/api/portal/favorites")
async def get_favorites(req: Request) -> JSONResponse:
    email = _email_from_request(req)
    with closing(_db()) as conn:
        rows = conn.execute(
            """
            SELECT item_key AS key, type, service, title, subtitle, href, starred_at
            FROM favorites
            WHERE user_email = ?
            ORDER BY starred_at DESC
            """,
            (email,),
        ).fetchall()
    return JSONResponse({"items": [dict(r) for r in rows]})


@app.post("/api/portal/favorites")
async def post_favorites(item: Item, req: Request) -> JSONResponse:
    email = _email_from_request(req)
    with closing(_db()) as conn:
        conn.execute(
            """
            INSERT INTO favorites (user_email, item_key, type, service, title, subtitle, href, starred_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT (user_email, item_key) DO UPDATE SET
              type     = excluded.type,
              service  = excluded.service,
              title    = excluded.title,
              subtitle = excluded.subtitle,
              href     = excluded.href
            """,
            (email, item.key, item.type, item.service, item.title, item.subtitle, item.href),
        )
    return JSONResponse({"ok": True, "starred": True})


@app.delete("/api/portal/favorites/{key:path}")
async def delete_favorite(key: str, req: Request) -> JSONResponse:
    email = _email_from_request(req)
    with closing(_db()) as conn:
        cur = conn.execute(
            "DELETE FROM favorites WHERE user_email = ? AND item_key = ?",
            (email, key),
        )
        removed = cur.rowcount
    return JSONResponse({"ok": True, "starred": False, "removed": removed})


# ─── Search aggregator ───────────────────────────────────────────────────
# Cross-service search. Pulls from OpenMetadata (catalog · primary source),
# Airflow REST, Superset, and Grafana in parallel, normalizes results to
# a common {type, service, title, sub, href} shape and caches per query
# for 30 seconds. Failures per source are silent — partial results are
# returned alongside successful sources.

SEARCH_CACHE_TTL = 30  # seconds
SEARCH_TIMEOUT = 3.0   # per-source HTTP timeout
SEARCH_PER_SOURCE_LIMIT = 8

_search_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_search_cache_lock = Lock()


def _cache_get(key: str) -> list[dict[str, Any]] | None:
    with _search_cache_lock:
        entry = _search_cache.get(key)
        if entry and (time.time() - entry[0]) < SEARCH_CACHE_TTL:
            return entry[1]
        return None


def _cache_set(key: str, value: list[dict[str, Any]]) -> None:
    with _search_cache_lock:
        _search_cache[key] = (time.time(), value)
        # Bounded cache — keep last 200 queries.
        if len(_search_cache) > 200:
            oldest = sorted(_search_cache.items(), key=lambda kv: kv[1][0])[:50]
            for k, _ in oldest:
                _search_cache.pop(k, None)


def _normalize_om(hit: dict[str, Any]) -> dict[str, Any] | None:
    """Translate one OpenMetadata search hit into our common shape.
    Returns None for entity types we don't surface in Cmd+K."""
    src = hit.get("_source") or {}
    et = src.get("entityType", "")
    name = src.get("displayName") or src.get("name") or ""
    fqn = src.get("fullyQualifiedName") or name
    if not name:
        return None
    if et == "table":
        return {
            "type": "table", "service": "openmetadata",
            "title": name,
            "sub": f"Catalog · {fqn}",
            "href": f"/embed/openmetadata/?path=%2Ftable%2F{fqn}",
        }
    if et == "dashboard":
        # OpenMetadata's "Dashboard" entity usually wraps a Superset dashboard,
        # so we link straight to OM (lineage view), with the Superset brand-icon
        # by convention.
        return {
            "type": "dashboard", "service": "superset",
            "title": name,
            "sub": f"Dashboard · {fqn}",
            "href": f"/embed/openmetadata/?path=%2Fdashboard%2F{fqn}",
        }
    if et == "pipeline":
        return {
            "type": "pipeline", "service": "airflow",
            "title": name,
            "sub": f"Pipeline · {fqn}",
            "href": f"/embed/openmetadata/?path=%2Fpipeline%2F{fqn}",
        }
    if et == "glossaryTerm":
        return {
            "type": "table", "service": "openmetadata",
            "title": name,
            "sub": f"Glossary · {fqn}",
            "href": f"/embed/openmetadata/?path=%2Fglossary%2F{fqn}",
        }
    return None


async def _search_openmetadata(client: httpx.AsyncClient, q: str) -> list[dict[str, Any]]:
    base = os.environ.get("OPENMETADATA_URL", "").rstrip("/")
    if not base:
        return []
    headers = {"Accept": "application/json"}
    token = os.environ.get("OPENMETADATA_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = await client.get(
            f"{base}/api/v1/search/query",
            params={
                "q": q,
                "from": 0,
                "size": SEARCH_PER_SOURCE_LIMIT,
                "index": "all_search_index",
            },
            headers=headers,
            timeout=SEARCH_TIMEOUT,
        )
        r.raise_for_status()
        hits = ((r.json().get("hits") or {}).get("hits")) or []
    except Exception as exc:
        log.info("OpenMetadata search failed: %s", exc)
        return []
    out: list[dict[str, Any]] = []
    for h in hits:
        norm = _normalize_om(h)
        if norm:
            out.append(norm)
    return out


async def _search_airflow(client: httpx.AsyncClient, q: str) -> list[dict[str, Any]]:
    base = os.environ.get("AIRFLOW_URL", "").rstrip("/")
    if not base:
        return []
    user = os.environ.get("AIRFLOW_USER")
    pwd = os.environ.get("AIRFLOW_PASS")
    auth: tuple[str, str] | None = (user, pwd) if user and pwd else None
    try:
        # Airflow v2 REST: /api/v1/dags with dag_id_pattern
        r = await client.get(
            f"{base}/api/v1/dags",
            params={
                "dag_id_pattern": f"%{q}%",
                "limit": SEARCH_PER_SOURCE_LIMIT,
                "only_active": "true",
            },
            auth=auth,
            timeout=SEARCH_TIMEOUT,
        )
        r.raise_for_status()
        dags = r.json().get("dags") or []
    except Exception as exc:
        log.info("Airflow search failed: %s", exc)
        return []
    return [
        {
            "type": "dag", "service": "airflow",
            "title": d.get("dag_id", "unknown"),
            "sub": (d.get("description") or "Airflow DAG")[:120],
            "href": f"/embed/airflow/?path=%2Fdags%2F{d.get('dag_id', '')}",
        }
        for d in dags
        if d.get("dag_id")
    ]


async def _search_superset(client: httpx.AsyncClient, q: str) -> list[dict[str, Any]]:
    base = os.environ.get("SUPERSET_URL", "").rstrip("/")
    if not base:
        return []
    # Superset's REST query DSL via Rison-encoded filters is brittle for
    # ad-hoc string search; for v1 we let OpenMetadata be the primary
    # source for dashboards (OM ingests Superset metadata). When SUPERSET_URL
    # is set + a service-token is available, extend here with the Superset
    # /api/v1/dashboard/?q=… call.
    return []


async def _search_grafana(client: httpx.AsyncClient, q: str) -> list[dict[str, Any]]:
    base = os.environ.get("GRAFANA_URL", "").rstrip("/")
    if not base:
        return []
    key = os.environ.get("GRAFANA_API_KEY")
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        r = await client.get(
            f"{base}/api/search",
            params={"query": q, "limit": SEARCH_PER_SOURCE_LIMIT, "type": "dash-db"},
            headers=headers,
            timeout=SEARCH_TIMEOUT,
        )
        r.raise_for_status()
        rows = r.json() or []
    except Exception as exc:
        log.info("Grafana search failed: %s", exc)
        return []
    return [
        {
            "type": "dashboard", "service": "grafana",
            "title": row.get("title", "untitled"),
            "sub": f"Grafana · {row.get('folderTitle', 'General')}",
            "href": f"/embed/grafana/?path=%2Fd%2F{row.get('uid', '')}",
        }
        for row in rows
        if row.get("uid")
    ]


# Order in which result-groups appear in the palette. Mirrors TYPE_ORDER
# in CommandPalette.tsx so the user sees a consistent grouping.
_GROUP_PRIORITY = {
    "dashboard": 0,
    "dag":       1,
    "table":     2,
    "notebook":  3,
    "query":     4,
    "pipeline":  5,
}


@app.get("/api/portal/search")
async def search(req: Request, q: str = "") -> JSONResponse:
    """Cross-service search. `q` is plain text; min 2 chars to avoid
    flooding the bron-services with one-letter requests. Results are
    grouped client-side (CommandPalette) by `type`; here we just merge
    and sort by group-priority so the JSON has a stable order."""
    _ = _email_from_request(req)  # auth required (no anonymous search)
    q = q.strip()
    if len(q) < 2:
        return JSONResponse({"items": [], "q": q, "cached": False})

    cache_key = q.lower()
    cached = _cache_get(cache_key)
    if cached is not None:
        return JSONResponse({"items": cached, "q": q, "cached": True})

    # Parallel fetch — single shared httpx client so connections pool.
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            _search_openmetadata(client, q),
            _search_airflow(client, q),
            _search_superset(client, q),
            _search_grafana(client, q),
            return_exceptions=True,
        )

    merged: list[dict[str, Any]] = []
    for r in results:
        if isinstance(r, list):
            merged.extend(r)
        elif isinstance(r, Exception):
            log.info("search source raised: %s", r)

    merged.sort(key=lambda x: _GROUP_PRIORITY.get(x.get("type", ""), 99))
    _cache_set(cache_key, merged)
    return JSONResponse({"items": merged, "q": q, "cached": False})


# ─── Notifications SSE stream ────────────────────────────────────────────
# In-memory event store (last 50). A background asyncio task polls Airflow
# for failed DAG runs every 30s and appends new ones to _events. Each
# connected EventSource client has its own asyncio.Queue subscription so
# events fan-out without blocking the poller.
#
# Bron-uitbreidingen (later):
#   - Superset shares: poll /api/v1/log/?type=DashboardModelView.related_objects
#   - OPA grants: tail the policy decision log
#   - dbt runs: poll dbt Cloud (or self-hosted) API
# Toevoegen = nieuwe _poll_* coroutine + asyncio.create_task in _start_pollers.

EVENT_HISTORY = 50
POLL_INTERVAL = 30  # seconds between Airflow polls

_events: deque[dict[str, Any]] = deque(maxlen=EVENT_HISTORY)
_event_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
_events_lock = Lock()
# Track which DAG-run ids we've already turned into events so a single
# failure doesn't get reported on every poll.
_seen_failed_runs: set[str] = set()


def _publish_event(evt: dict[str, Any]) -> None:
    """Append to history + fan-out to all subscribers. Subscribers with
    a full queue (slow consumer) silently drop the event for that client."""
    with _events_lock:
        _events.append(evt)
        subscribers = list(_event_subscribers)
    for q in subscribers:
        try:
            q.put_nowait(evt)
        except asyncio.QueueFull:
            log.info("dropping event for slow subscriber")


def _fmt_ago(iso_ts: str | None) -> str:
    """Compact relative-time formatting. Mirrors formatAgo() in
    WorkspaceHome.astro so the bell + recents look identical."""
    if not iso_ts:
        return 'nu'
    try:
        when = datetime.fromisoformat(iso_ts.replace('Z', '+00:00'))
    except ValueError:
        return 'nu'
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - when
    secs = max(0, int(delta.total_seconds()))
    if secs < 60:    return 'nu'
    if secs < 3600:  return f'{secs // 60}m'
    if secs < 86400: return f'{secs // 3600}u'
    return f'{secs // 86400}d'


async def _poll_airflow_failures() -> None:
    """Background task: every POLL_INTERVAL seconds, fetch recently failed
    DAG runs and emit events for ones we haven't seen yet."""
    base = os.environ.get("AIRFLOW_URL", "").rstrip("/")
    user = os.environ.get("AIRFLOW_USER")
    pwd  = os.environ.get("AIRFLOW_PASS")
    if not base:
        log.info("AIRFLOW_URL not set — failure poller disabled")
        return
    auth: tuple[str, str] | None = (user, pwd) if user and pwd else None

    # Don't backfill the entire failure history on first start — only
    # report failures from the past hour. After that, the deduplication
    # set kicks in and we only see truly new ones.
    since = datetime.now(timezone.utc) - timedelta(hours=1)

    async with httpx.AsyncClient() as client:
        while True:
            try:
                r = await client.get(
                    f"{base}/api/v1/dags/~/dagRuns",
                    params={
                        "state": "failed",
                        "execution_date_gte": since.isoformat(),
                        "limit": 20,
                        "order_by": "-execution_date",
                    },
                    auth=auth,
                    timeout=8.0,
                )
                r.raise_for_status()
                runs = r.json().get("dag_runs") or []
                for run in runs:
                    run_key = f"{run.get('dag_id')}/{run.get('dag_run_id')}"
                    if run_key in _seen_failed_runs:
                        continue
                    _seen_failed_runs.add(run_key)
                    dag_id = run.get('dag_id', '')
                    _publish_event({
                        'id':     run_key,
                        'tone':   'down',
                        'title':  f"Airflow · {dag_id} gefaald",
                        'detail': f"Run {run.get('dag_run_id', '')}",
                        'ago':    _fmt_ago(run.get('execution_date') or run.get('end_date')),
                        'href':   f"/embed/airflow/?path=%2Fdags%2F{dag_id}",
                    })
            except Exception as exc:
                log.info("airflow poll failed: %s", exc)
            await asyncio.sleep(POLL_INTERVAL)


@app.on_event("startup")
async def _start_pollers() -> None:
    """Spin up background poll-tasks once the app is ready. Tasks run
    forever; pod restart re-seeds them. Keep a reference so the GC
    doesn't reap them."""
    app.state.poll_airflow = asyncio.create_task(_poll_airflow_failures())


@app.get("/api/portal/events")
async def events_stream(req: Request) -> StreamingResponse:
    """Server-Sent Events stream. Replays the recent-event history on
    connect, then streams new events as the pollers publish them.

    Compat-note: nginx must have `proxy_buffering off` for this location,
    otherwise events stack up until the buffer flushes (worst-case at
    proxy_read_timeout). We also set `X-Accel-Buffering: no` so nginx
    skips buffering even if the per-location config is missing."""
    _ = _email_from_request(req)

    async def event_gen():
        # 1. Replay the recent history so a fresh tab gets context.
        with _events_lock:
            history = list(_events)
        for evt in history:
            yield f"data: {json.dumps(evt)}\n\n"

        # 2. Subscribe to live events via a per-client queue.
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=20)
        with _events_lock:
            _event_subscribers.add(q)
        try:
            # 3. Heartbeat every 25s so proxies + browsers keep the
            # connection alive. Browser auto-reconnects on close, but
            # without traffic some proxies cut the stream at 60s.
            while True:
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=25.0)
                    yield f"data: {json.dumps(evt)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"   # SSE comment, ignored by client
        finally:
            with _events_lock:
                _event_subscribers.discard(q)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection":    "keep-alive",
            "X-Accel-Buffering": "no",  # tell nginx: don't buffer me
        },
    )


# ─── Power BI embed ──────────────────────────────────────────────────────
# Mint short-lived embed tokens voor de Astro-portal via een Service Principal.
# De SP heeft Workspace-Contributor op de Fabric workspace (zie
# secrets/local/uc11-multiplatform.env). We doen geen pure User-Owns-Data
# (waar de user z'n eigen Entra-token gebruikt) omdat dat een per-user
# Power BI Pro/PPU licentie zou eisen. In plaats daarvan: App-Owns-Data
# met een `effectiveIdentity` waarin de gefedereerde Entra-email wordt
# meegegeven — Power BI logt de user voor audit en kan via DAX (USERNAME,
# CUSTOMDATA) row-level security toepassen.
#
# De email komt uit oauth2-proxy's X-Auth-Request-Email header — wat door
# de Keycloak-Entra-IdP-broker (ADR-0008) ge-federeerde Entra-mail is wanneer
# de user via Entra inlogt.
#
# Env-vars (uit K8s Secret `powerbi-embed-creds` in odap-platform):
#   FABRIC_TENANT_ID, FABRIC_CLIENT_ID, FABRIC_CLIENT_SECRET, FABRIC_WORKSPACE_ID

PBI_AUTHORITY_TPL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
PBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"
PBI_API_BASE = "https://api.powerbi.com/v1.0/myorg"

# In-memory token cache — SP-token leeft ~60min, embed-token max 60min.
# We bewaren beide met TTL, lock om dubbele refresh te voorkomen.
_pbi_token_cache: dict[str, tuple[str, float]] = {}
_pbi_token_lock = Lock()


async def _pbi_sp_token() -> str:
    """OAuth2 client-credentials token voor de Power BI API. Caches tot 5min
    voor expiry."""
    cached = _pbi_token_cache.get("sp")
    if cached and cached[1] > time.time() + 60:
        return cached[0]
    with _pbi_token_lock:
        # double-check binnen de lock
        cached = _pbi_token_cache.get("sp")
        if cached and cached[1] > time.time() + 60:
            return cached[0]
        tenant = os.environ.get("FABRIC_TENANT_ID", "")
        cid    = os.environ.get("FABRIC_CLIENT_ID", "")
        secret = os.environ.get("FABRIC_CLIENT_SECRET", "")
        if not (tenant and cid and secret):
            raise HTTPException(
                status_code=503,
                detail="powerbi: FABRIC_TENANT_ID/CLIENT_ID/CLIENT_SECRET niet gezet",
            )
        async with httpx.AsyncClient(timeout=15) as cli:
            resp = await cli.post(
                PBI_AUTHORITY_TPL.format(tenant=tenant),
                data={
                    "client_id":     cid,
                    "client_secret": secret,
                    "scope":         PBI_SCOPE,
                    "grant_type":    "client_credentials",
                },
            )
        if resp.status_code != 200:
            log.error("powerbi token: %s %s", resp.status_code, resp.text[:300])
            raise HTTPException(status_code=503, detail="powerbi: SP-token faalt")
        body = resp.json()
        access_token = body["access_token"]
        expires_at   = time.time() + int(body.get("expires_in", 3600))
        _pbi_token_cache["sp"] = (access_token, expires_at)
        return access_token


async def _pbi_get(path: str, token: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as cli:
        resp = await cli.get(
            f"{PBI_API_BASE}{path}",
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code != 200:
        log.error("powerbi GET %s: %s %s", path, resp.status_code, resp.text[:300])
        raise HTTPException(status_code=resp.status_code, detail=f"powerbi GET {path}: {resp.text[:200]}")
    return resp.json()


async def _pbi_post(path: str, token: str, body: dict) -> dict:
    async with httpx.AsyncClient(timeout=20) as cli:
        resp = await cli.post(
            f"{PBI_API_BASE}{path}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=body,
        )
    if resp.status_code not in (200, 201):
        log.error("powerbi POST %s: %s %s", path, resp.status_code, resp.text[:300])
        raise HTTPException(status_code=resp.status_code, detail=f"powerbi POST {path}: {resp.text[:200]}")
    return resp.json()


@app.get("/api/portal/powerbi/reports")
async def list_powerbi_reports(req: Request) -> dict:
    """Lijst de reports in de geconfigureerde workspace.

    Front-end gebruikt dit voor een dropdown op /embed/powerbi/. Auth-gewise
    is dit user-context — de SP haalt de lijst op, maar we returnen 'm
    alleen aan een ingelogde portal-gebruiker."""
    user_email = _email_from_request(req)  # noqa: F841 — audit/log
    ws = os.environ.get("FABRIC_WORKSPACE_ID", "")
    if not ws:
        raise HTTPException(status_code=503, detail="FABRIC_WORKSPACE_ID niet gezet")
    token = await _pbi_sp_token()
    data = await _pbi_get(f"/groups/{ws}/reports", token)
    items = [
        {"id": r["id"], "name": r["name"], "datasetId": r.get("datasetId"),
         "embedUrl": r.get("embedUrl"), "webUrl": r.get("webUrl")}
        for r in data.get("value", [])
    ]
    return {"workspace_id": ws, "reports": items}


@app.post("/api/portal/powerbi/embed/{report_id}")
async def generate_powerbi_embed_token(report_id: str, req: Request) -> dict:
    """Mint een short-lived embed token voor één report.

    Body: optioneel `{"roles": [...], "customData": "..."}` voor RLS-rules
    die niet alleen op email filteren. Default: alleen `username=<email>`.

    Returnt:
        {
          "embedUrl":   "https://app.powerbi.com/reportEmbed?...",
          "accessToken": "<embed_token>",
          "expiration": "2026-05-25T12:34:56Z",
          "reportId":   "<id>",
          "datasetId":  "<id>"
        }
    """
    user_email = _email_from_request(req)
    ws = os.environ.get("FABRIC_WORKSPACE_ID", "")
    if not ws:
        raise HTTPException(status_code=503, detail="FABRIC_WORKSPACE_ID niet gezet")

    body: dict[str, Any] = {}
    try:
        if req.headers.get("content-length", "0") != "0":
            body = await req.json()
    except Exception:
        body = {}

    token = await _pbi_sp_token()

    # 1. Haal report-metadata op — geeft datasetId en embedUrl.
    report = await _pbi_get(f"/groups/{ws}/reports/{report_id}", token)
    dataset_id = report.get("datasetId")
    embed_url  = report.get("embedUrl")
    if not (dataset_id and embed_url):
        raise HTTPException(
            status_code=500,
            detail=f"powerbi: report {report_id} mist datasetId of embedUrl",
        )

    # 2. V2 embed-token via het top-level `/GenerateToken` endpoint
    #    (Direct Lake-datasets vereisen V2 — V1 op `/reports/<id>/GenerateToken`
    #    geeft "Embedding a DirectLake dataset is not supported with V1").
    #
    #    `effectiveIdentity` (RLS doorgifte) is alleen mogelijk als de
    #    semantic model een "fixed identity"-cloud-connection heeft. Zonder
    #    dat geeft Power BI 403 "Creating embed token with effective identity
    #    is not supported for this datasource". We sturen 'm daarom alleen
    #    mee als de caller expliciet `effectiveIdentity=true` aanvinkt of
    #    `roles`/`customData` meegeeft (= RLS-intent expliciet maakt). Audit-
    #    only doorgifte van de user-email gebeurt via de logregel hieronder.
    token_body: dict[str, Any] = {
        "datasets":         [{"id": dataset_id}],
        "reports":          [{"id": report_id, "allowEdit": False}],
        "targetWorkspaces": [{"id": ws}],
    }
    want_identity = bool(
        body.get("effectiveIdentity")
        or body.get("roles")
        or body.get("customData")
    )
    if want_identity:
        effective_identity: dict[str, Any] = {
            "username": user_email,
            "datasets": [dataset_id],
        }
        if isinstance(body.get("roles"), list) and body["roles"]:
            effective_identity["roles"] = body["roles"]
        if isinstance(body.get("customData"), str) and body["customData"]:
            effective_identity["customData"] = body["customData"]
        token_body["identities"] = [effective_identity]

    minted = await _pbi_post("/GenerateToken", token, token_body)

    log.info(
        "powerbi embed-token minted: user=%s report=%s expires=%s",
        user_email, report_id, minted.get("expiration"),
    )
    return {
        "embedUrl":   embed_url,
        "accessToken": minted["token"],
        "expiration": minted.get("expiration"),
        "reportId":   report_id,
        "datasetId":  dataset_id,
    }


# ─── Liveness ────────────────────────────────────────────────────────────
@app.get("/api/portal/_ping")
async def ping() -> dict[str, Any]:
    """Geen auth — gebruikt door readinessProbe + smoke test."""
    return {"ok": True, "msg": "portal backend bereikbaar"}
