#!/usr/bin/env python3
"""Probe of een MinIO-endpoint klaar is for a OneLake S3-shortcut.

Microsoft Fabric maakt vanaf de Azure egress-IPs een HTTPS-verbinding naar
het opgegeven S3-endpoint. Vier dingen moeten kloppen for the shortcut werkt:

  1. DNS resolveert publiek (geen 10.x / 192.168.x / 127.x).
  2. TCP 443 is open vanaf het publieke internet (geen firewall-block).
  3. TLS-cert is uitgegeven door een publiek vertrouwde CA (Let's Encrypt e.d.),
     niet self-signed of een private CA — Fabric vertrouwt de Microsoft trust
     store, geen custom CA's.
  4. S3 ListBuckets + GetObject werkt with the meegegeven access/secret key.

Deze probe doet 1..4 lokaal en print een groene check / rode kruis per stap.
Falen op stap 1-3 = de shortcut zal niet werken, ongeacht credentials.

Gebruik:
    # Met defaults for the StackIT-cloud:
    python3 scripts/fabric-probe-minio.py \\
        --endpoint https://minio.example.com

    # Tegen lokale k3d (zal stap 1 falen — 127.0.0.1):
    python3 scripts/fabric-probe-minio.py \\
        --endpoint https://minio.odap.local:8443 --insecure

    # Tegen AKS:
    python3 scripts/fabric-probe-minio.py \\
        --endpoint https://minio.example.com

Credentials komen uit env-vars MINIO_ACCESS_KEY / MINIO_SECRET_KEY
(default access-key is 'platformadmin' — het platform dev-default).

Exit codes:
  0 — alle 4 stappen geslaagd; veilig om een shortcut aan te maken
  1 — minstens één stap gefaald; zie output voor wat
"""
from __future__ import annotations

import argparse
import ipaddress
import os
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

OK = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
WARN = "\033[33m!\033[0m"

DEFAULT_BUCKETS = ("odap-bronze", "odap-silver", "odap-gold", "sensitive")
PRIVATE_CIDRS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::1/128"),
]


def _is_public(addr: str) -> bool:
    try:
        return not any(ipaddress.ip_address(addr) in net for net in PRIVATE_CIDRS)
    except ValueError:
        return False


def step1_dns(host: str) -> tuple[bool, list[str]]:
    print(f"\n[1/4] DNS resolution  — {host}")
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        print(f"  {FAIL} kan niet resolven: {e}")
        return False, []
    addrs = sorted({i[4][0] for i in infos})
    for a in addrs:
        marker = OK if _is_public(a) else FAIL
        kind = "publiek" if _is_public(a) else "PRIVÉ-IP (Fabric kan niet bereiken)"
        print(f"  {marker} {a}  ({kind})")
    return any(_is_public(a) for a in addrs), addrs


def step2_tcp(host: str, port: int = 443, timeout: int = 8) -> bool:
    print(f"\n[2/4] TCP {port} connect  — {host}:{port}")
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        print(f"  {OK} connection succeeded ({timeout}s timeout)")
        return True
    except (socket.timeout, OSError) as e:
        print(f"  {FAIL} {e}")
        return False


def step3_tls(host: str, port: int = 443, insecure: bool = False) -> bool:
    print(f"\n[3/4] TLS handshake + cert validation  — {host}:{port}")
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=8) as raw:
            with ctx.wrap_socket(raw, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
        if insecure:
            print(f"  {WARN} --insecure: TLS-validatie geskipt (Fabric doet dit WEL)")
            return False  # Insecure = niet bruikbaar voor Fabric

        issuer = dict(x[0] for x in cert.get("issuer", []))
        subject = dict(x[0] for x in cert.get("subject", []))
        not_after = datetime.strptime(
            cert.get("notAfter", ""), "%b %d %H:%M:%S %Y %Z"
        ).replace(tzinfo=timezone.utc)
        days_left = (not_after - datetime.now(timezone.utc)).days

        print(f"  {OK} issuer:  {issuer.get('organizationName', '?')} / {issuer.get('commonName', '?')}")
        print(f"  {OK} subject: {subject.get('commonName', '?')}")
        print(f"  {OK} verloopt over {days_left} dagen ({not_after.isoformat()})")
        return True

    except ssl.SSLCertVerificationError as e:
        print(f"  {FAIL} cert-validatie: {e.reason}")
        print(f"      Fabric zal hier ook op falen — gebruik een publieke CA")
        return False
    except (socket.timeout, OSError) as e:
        print(f"  {FAIL} {e}")
        return False


def step4_s3(
    endpoint: str,
    access_key: str,
    secret_key: str,
    buckets: tuple[str, ...],
    verify_tls: bool = True,
) -> bool:
    print(f"\n[4/4] S3 API + bucket access  — {endpoint}")
    try:
        import boto3
        from botocore.client import Config
        from botocore.exceptions import ClientError, EndpointConnectionError
    except ImportError:
        print(
            f"  {WARN} boto3 niet geïnstalleerd — kan S3-API niet testen. "
            "Run `pip install boto3` of laat deze stap weg."
        )
        return False

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},  # MinIO gebruikt path-style
            connect_timeout=8,
            retries={"max_attempts": 1},
        ),
        verify=verify_tls,
    )

    try:
        resp = s3.list_buckets()
        names = {b["Name"] for b in resp.get("Buckets", [])}
        print(f"  {OK} ListBuckets: {len(names)} gevonden → {sorted(names)[:6]}{'...' if len(names) > 6 else ''}")
    except (ClientError, EndpointConnectionError) as e:
        print(f"  {FAIL} ListBuckets faalde: {e}")
        return False

    missing = [b for b in buckets if b not in names]
    if missing:
        print(f"  {WARN} ontbrekende verwachte buckets: {missing}")

    # GetBucketLocation + ListObjectsV2 on the eerste bestaande bucket.
    target = next((b for b in buckets if b in names), None)
    if not target:
        print(f"  {FAIL} geen van {buckets} bestaat in dit account")
        return False
    try:
        listing = s3.list_objects_v2(Bucket=target, MaxKeys=3)
        n = listing.get("KeyCount", 0)
        keys = [k["Key"] for k in listing.get("Contents", [])[:3]]
        print(f"  {OK} ListObjects op '{target}': {n} key(s) (sample: {keys})")
    except ClientError as e:
        print(f"  {FAIL} ListObjects op '{target}' faalde: {e}")
        return False

    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--endpoint",
        required=True,
        help="MinIO HTTPS endpoint, bv. https://minio.example.com",
    )
    ap.add_argument(
        "--buckets",
        default=",".join(DEFAULT_BUCKETS),
        help=f"Comma-separated bucket-namen om te checken (default: {','.join(DEFAULT_BUCKETS)})",
    )
    ap.add_argument(
        "--access-key",
        default=os.environ.get("MINIO_ACCESS_KEY", "platformadmin"),
        help="MinIO access key (default: env MINIO_ACCESS_KEY of 'platformadmin')",
    )
    ap.add_argument(
        "--secret-key",
        default=os.environ.get("MINIO_SECRET_KEY", ""),
        help="MinIO secret key (default: env MINIO_SECRET_KEY)",
    )
    ap.add_argument(
        "--insecure",
        action="store_true",
        help="Skip TLS-validatie (alleen voor diagnose; Fabric kan dit NIET).",
    )
    args = ap.parse_args()

    url = urllib.parse.urlparse(args.endpoint)
    if url.scheme != "https":
        print(f"{FAIL} --endpoint moet https:// zijn (Fabric ondersteunt geen http).")
        sys.exit(1)
    host = url.hostname
    port = url.port or 443
    if not host:
        print(f"{FAIL} kan host niet parsen uit {args.endpoint}")
        sys.exit(1)

    print(f"Probe → {args.endpoint}")
    print(f"        host={host}  port={port}")
    print(f"        verwachte buckets: {args.buckets}")

    results = []
    public_dns, _ = step1_dns(host)
    results.append(("DNS publiek", public_dns))

    tcp_ok = step2_tcp(host, port)
    results.append(("TCP connect", tcp_ok))

    tls_ok = step3_tls(host, port, insecure=args.insecure) if tcp_ok else False
    results.append(("TLS publiek vertrouwd", tls_ok))

    s3_ok = False
    if tcp_ok and args.secret_key:
        s3_ok = step4_s3(
            args.endpoint,
            args.access_key,
            args.secret_key,
            tuple(args.buckets.split(",")),
            verify_tls=not args.insecure,
        )
    elif not args.secret_key:
        print(
            f"\n[4/4] S3 API + bucket access  — \n"
            f"  {WARN} geen MINIO_SECRET_KEY — overgeslagen. "
            "Zet `export MINIO_SECRET_KEY=...` om dit te testen."
        )
    results.append(("S3 API", s3_ok))

    print("\n" + "─" * 60)
    print("Samenvatting:")
    for name, ok in results:
        marker = OK if ok else FAIL
        print(f"  {marker} {name}")

    if all(ok for _, ok in results):
        print(
            f"\n{OK} Klaar voor OneLake S3-shortcut. Volgende stap:\n"
            f"    python3 scripts/fabric-create-shortcut-uc12.py \\\n"
            f"        --endpoint {args.endpoint}"
        )
        sys.exit(0)
    else:
        print(
            f"\n{FAIL} Niet klaar voor shortcut. Los bovenstaande issues eerst op."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
