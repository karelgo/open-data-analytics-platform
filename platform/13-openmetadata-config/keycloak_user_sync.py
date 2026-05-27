"""Sync Keycloak realm-users → OpenMetadata Users.

OM 1.5 heeft geen SCIM-provisioner; nieuwe Keycloak-users verschijnen pas in
OM zodra ze inloggen. Dat breekt:
  - Owner-toewijzing aan users die nog niet zijn ingelogd.
  - DQ-Test-Suite reviewer-mailings.
  - Lineage-attributie aan "wie heeft die DAG getriggerd".

Dit script:
  1. Logt in op Keycloak admin-API met password-flow (kcadmin service-account
     uit Bitnami Keycloak chart).
  2. Lijst alle users in realm odap (paginated).
  3. POSTet elke user naar OM /api/v1/users (idempotent — 409 = bestaat al).
  4. PATCH /users/{id} update voor display-name/email wijzigingen.

Wordt door een CronJob aangeroepen (dagelijks). Sla onbekende velden over.

Env-vars:
  OM_URL              http://openmetadata.odap-meta.svc.cluster.local:8585
  OM_JWT_TOKEN        admin/bot JWT met user-create-recht
  KEYCLOAK_URL        http://keycloak.odap-auth.svc.cluster.local
  KEYCLOAK_REALM      uwv (default)
  KEYCLOAK_CLIENT_ID  admin-cli (default — public client)
  KEYCLOAK_ADMIN_USER kcadmin (Bitnami chart default)
  KEYCLOAK_ADMIN_PW   <secret>
"""
from __future__ import annotations

import json
import os
import sys

import requests

OM_URL = os.environ.get(
    "OM_URL", "http://openmetadata.odap-meta.svc.cluster.local:8585"
).rstrip("/")
OM_TOKEN = os.environ["OM_JWT_TOKEN"]

KC_URL = os.environ.get(
    "KEYCLOAK_URL", "http://keycloak.odap-auth.svc.cluster.local"
).rstrip("/")
KC_REALM = os.environ.get("KEYCLOAK_REALM", "demo")
KC_CLIENT = os.environ.get("KEYCLOAK_CLIENT_ID", "admin-cli")
KC_USER = os.environ["KEYCLOAK_ADMIN_USER"]
KC_PASS = os.environ["KEYCLOAK_ADMIN_PW"]

OM_HEADERS = {
    "Authorization": f"Bearer {OM_TOKEN}",
    "Content-Type": "application/json",
}

# Truststore voor zelf-ondertekende ingress-CA in dev.
CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE")


def log(msg: str) -> None:
    print(f"[kc-sync] {msg}", flush=True)


def get_kc_token() -> str:
    """Krijgt admin-token via password-flow op master-realm. Keycloak's
    admin-API draait altijd op master, niet op het odap-realm."""
    r = requests.post(
        f"{KC_URL}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": KC_CLIENT,
            "username": KC_USER,
            "password": KC_PASS,
        },
        timeout=15,
        verify=CA_BUNDLE or True,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def list_kc_users(token: str) -> list[dict]:
    """Paginate over /admin/realms/<realm>/users."""
    out: list[dict] = []
    first = 0
    page = 100
    while True:
        r = requests.get(
            f"{KC_URL}/admin/realms/{KC_REALM}/users",
            headers={"Authorization": f"Bearer {token}"},
            params={"first": first, "max": page, "briefRepresentation": "true"},
            timeout=20,
            verify=CA_BUNDLE or True,
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        if len(batch) < page:
            break
        first += page
    return out


def upsert_om_user(user: dict) -> None:
    username = user.get("username")
    if not username:
        return
    email = user.get("email") or f"{username}@odap.local"
    display = (
        " ".join(filter(None, [user.get("firstName"), user.get("lastName")]))
        or username
    )

    body = {
        "name": username,
        "displayName": display,
        "email": email,
        "isBot": False,
        "isAdmin": False,
    }
    r = requests.post(
        f"{OM_URL}/api/v1/users",
        headers=OM_HEADERS,
        data=json.dumps(body),
        timeout=15,
    )
    if r.status_code in (200, 201):
        log(f"  + {username}")
        return
    if r.status_code in (409, 422):
        # Bestaat al — check of email/displayName moeten worden bijgewerkt.
        rr = requests.get(
            f"{OM_URL}/api/v1/users/name/{username}",
            headers=OM_HEADERS,
            timeout=10,
        )
        if rr.status_code != 200:
            return
        existing = rr.json()
        if (
            existing.get("displayName") == display
            and existing.get("email") == email
        ):
            log(f"  = {username}")
            return
        # JSON-Patch update — alleen de gewijzigde velden vervangen.
        # OM PUT /users vereist een volledige User-entity (lastig samen te
        # stellen met alle versie-velden); PATCH is robuster.
        ops = []
        if existing.get("displayName") != display:
            ops.append(
                {
                    "op": "replace" if existing.get("displayName") else "add",
                    "path": "/displayName",
                    "value": display,
                }
            )
        if existing.get("email") != email:
            ops.append(
                {
                    "op": "replace" if existing.get("email") else "add",
                    "path": "/email",
                    "value": email,
                }
            )
        if not ops:
            log(f"  = {username}")
            return
        upd = requests.patch(
            f"{OM_URL}/api/v1/users/{existing['id']}",
            headers={
                **OM_HEADERS,
                "Content-Type": "application/json-patch+json",
            },
            data=json.dumps(ops),
            timeout=15,
        )
        if upd.status_code in (200, 201):
            log(f"  ~ {username} (geupdate)")
        else:
            log(
                f"  ! update {username} status={upd.status_code} "
                f"body={upd.text[:150]}"
            )
        return
    log(f"  ! {username} status={r.status_code} body={r.text[:200]}")


def main() -> int:
    log(f"Sync Keycloak realm={KC_REALM} → OM {OM_URL}")
    token = get_kc_token()
    users = list_kc_users(token)
    log(f"  Keycloak users in {KC_REALM}: {len(users)}")
    for u in users:
        upsert_om_user(u)
    log("Sync voltooid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
