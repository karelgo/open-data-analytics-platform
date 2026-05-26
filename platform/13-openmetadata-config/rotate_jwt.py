"""Sync ingestion-bot JWT van OM Postgres → Kubernetes Secrets.

OM 1.5's `PUT /users/generateToken` retourneert soms de `fernet:`-encrypted
form i.p.v. de gedecrypte JWT, waardoor downstream consumers (Airflow KPO,
init-job, CronJobs) 401's krijgen. Werkbaar pad voor "rotation" is daarom:

  1. Admin draait OM UI → users → ingestion-bot → "Regenerate Token"
     (genereert nieuwe encrypted JWT in user_entity.json).
  2. Deze CronJob leest de huidige encrypted JWT uit Postgres,
     decrypt'm met de OM-fernet-key, en patcht het K8s-secret
     `openmetadata-admin.jwtToken` in zowel odap-meta als odap-platform.

Dit garandeert dat de K8s-secret altijd in sync is met de actieve token
in OM. Het is geen "echte" rotatie (OM moet 'm zelf re-issuen), maar het
sluit de gap dat een nieuwe token in OM niet vanzelf bij Airflow landt.

Voor productie: External Secrets Operator + Vault dynamic-secret backend.

Env-vars:
  POSTGRES_HOST       postgres-postgresql.odap-data.svc.cluster.local (default)
  POSTGRES_USER       postgres (default)
  POSTGRES_PASSWORD   <secret> — uit postgres-postgresql.password
  POSTGRES_DB         openmetadata (default)
  OM_FERNET_KEY       <secret> — uit openmetadata-fernetkey-secret
  BOT_USERNAME        ingestion-bot (default)
  K8S_SECRET_NS       odap-meta (primary)
  K8S_MIRROR_NS       odap-platform (KPO consumer)
"""
from __future__ import annotations

import base64
import json
import os
import sys

import psycopg2
import requests
from cryptography.fernet import Fernet, MultiFernet

BOT = os.environ.get("BOT_USERNAME", "ingestion-bot")

PG_HOST = os.environ.get(
    "POSTGRES_HOST", "postgres-postgresql.odap-data.svc.cluster.local"
)
PG_USER = os.environ.get("POSTGRES_USER", "postgres")
PG_PASS = os.environ["POSTGRES_PASSWORD"]
PG_DB = os.environ.get("POSTGRES_DB", "openmetadata")

FERNET_KEY = os.environ["OM_FERNET_KEY"]

SECRET_NAME = os.environ.get("K8S_SECRET_NAME", "openmetadata-admin")
SECRET_NS = os.environ.get("K8S_SECRET_NS", "odap-meta")
MIRROR_NS = os.environ.get("K8S_MIRROR_NS", "odap-platform")
SECRET_KEY = os.environ.get("K8S_SECRET_KEY", "jwtToken")

KUBE_HOST = "https://kubernetes.default.svc"
SA_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"
SA_CA_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"


def log(msg: str) -> None:
    print(f"[jwt-sync] {msg}", flush=True)


def fetch_encrypted_token() -> str:
    """Lees de huidige encrypted JWTToken uit OM's user_entity tabel."""
    conn = psycopg2.connect(
        host=PG_HOST,
        user=PG_USER,
        password=PG_PASS,
        dbname=PG_DB,
        connect_timeout=10,
    )
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "SELECT json->'authenticationMechanism'->'config'->>'JWTToken' "
                "FROM user_entity WHERE name=%s LIMIT 1;",
                (BOT,),
            )
            row = cur.fetchone()
            if not row or not row[0]:
                raise RuntimeError("ingestion-bot.JWTToken niet gevonden in DB")
            return row[0]
    finally:
        conn.close()


def decrypt(token: str) -> str:
    """OM slaat tokens als `fernet:<base64>` op. MultiFernet ondersteunt
    rotated keys (comma-separated)."""
    payload = token[len("fernet:"):] if token.startswith("fernet:") else token
    mf = MultiFernet([Fernet(k.encode()) for k in FERNET_KEY.split(",")])
    return mf.decrypt(payload.encode()).decode()


def patch_secret(namespace: str, value: str) -> None:
    with open(SA_TOKEN_PATH) as f:
        sa_token = f.read().strip()
    body = {"data": {SECRET_KEY: base64.b64encode(value.encode()).decode()}}
    r = requests.patch(
        f"{KUBE_HOST}/api/v1/namespaces/{namespace}/secrets/{SECRET_NAME}",
        headers={
            "Authorization": f"Bearer {sa_token}",
            "Content-Type": "application/strategic-merge-patch+json",
            "Accept": "application/json",
        },
        data=json.dumps(body),
        timeout=15,
        verify=SA_CA_PATH,
    )
    r.raise_for_status()
    log(f"  ✓ {namespace}/{SECRET_NAME}.{SECRET_KEY} gepatched")


def main() -> int:
    log(f"Sync JWT voor bot={BOT}")
    encrypted = fetch_encrypted_token()
    log(f"  encrypted len={len(encrypted)}")
    jwt = decrypt(encrypted)
    log(f"  gedecrypte JWT len={len(jwt)} (prefix={jwt[:20]}...)")
    patch_secret(SECRET_NS, jwt)
    if MIRROR_NS and MIRROR_NS != SECRET_NS:
        try:
            patch_secret(MIRROR_NS, jwt)
        except Exception as e:
            log(f"  ? mirror naar {MIRROR_NS} faalde: {e}")
    log("Sync voltooid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
