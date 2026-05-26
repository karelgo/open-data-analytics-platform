#!/usr/bin/env bash
# Start a kubectl port-forward to the AKS ingress-nginx, bound to 127.0.0.2
# so it doesn't conflict with a concurrently-running k3d cluster on 127.0.0.1.
#
# Why use this when there's a public DNS + Let's Encrypt? Because some
# corp networks block outbound to Azure public IP ranges, so the public LB
# IP times out from the user's machine. The kubectl PF tunnels through the
# AKS API server (typically allowed because that's how `kubectl` works at
# all), so it's the reliable fallback when public access is blocked.
#
# /etc/hosts mapping (one-time setup — run on your Mac with sudo):
#   sudo bash -c 'echo "127.0.0.2 platform.example.com \\
#       keycloak.example.com \\
#       grafana.example.com \\
#       prometheus.example.com \\
#       minio.example.com \\
#       minio-api.example.com \\
#       superset.example.com \\
#       airflow.example.com \\
#       dbt-docs.example.com" >> /etc/hosts'
#
# Then browse to https://platform.example.com:8443/.
# (Browsers warn about the cert because it's issued for port 443; accept once.)
#
# 127.0.0.2 is not bound to lo0 by default on macOS. This script adds it
# automatically (will prompt for sudo password if missing).
#
# Usage:
#   bash scripts/azure/aks-pf.sh           # start in background
#   bash scripts/azure/aks-pf.sh stop
#   bash scripts/azure/aks-pf.sh status
set -euo pipefail

LOG=/tmp/aks-pf.log
PIDFILE=/tmp/aks-pf.pid
ADDR=127.0.0.2

cmd="${1:-start}"

ensure_lo_alias() {
  if ! ifconfig lo0 2>/dev/null | grep -q "inet $ADDR "; then
    echo "127.0.0.2 not bound to lo0 — adding alias (sudo)…"
    sudo ifconfig lo0 alias "$ADDR" up
  fi
}

case "$cmd" in
  start)
    if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "Already running: pid $(cat "$PIDFILE"). Use 'stop' to kill."
      exit 0
    fi
    ensure_lo_alias
    nohup kubectl --context odap-platform-aks -n ingress-nginx port-forward \
      --address "$ADDR" \
      svc/ingress-nginx-controller 8443:443 8080:80 \
      >"$LOG" 2>&1 &
    echo $! > "$PIDFILE"
    sleep 3
    if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      printf '\033[1;32mOK\033[0m  AKS port-forward running on %s:8443 / %s:8080 (pid %s)\n' "$ADDR" "$ADDR" "$(cat "$PIDFILE")"
      echo "  log:        $LOG"
      echo "  hostnames:  https://{platform,keycloak,grafana,prometheus,minio,minio-api,superset,airflow,dbt-docs}.example.com:8443"
      if ! grep -q "example.com" /etc/hosts 2>/dev/null; then
        echo
        echo "  /etc/hosts is missing the .com entries. Run once:"
        echo
        echo "    sudo bash -c 'echo \"127.0.0.2 platform.example.com keycloak.example.com grafana.example.com prometheus.example.com minio.example.com minio-api.example.com superset.example.com airflow.example.com dbt-docs.example.com\" >> /etc/hosts'"
      fi
    else
      echo "FAIL: port-forward died. See $LOG"
      exit 1
    fi
    ;;
  stop)
    if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      kill "$(cat "$PIDFILE")"
      rm -f "$PIDFILE"
      echo "Stopped."
    else
      echo "Not running."
      rm -f "$PIDFILE" 2>/dev/null || true
    fi
    ;;
  status)
    if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "Running: pid $(cat "$PIDFILE")"
      lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -E "^kubectl.*$ADDR:8(080|443)" || true
    else
      echo "Not running."
    fi
    ;;
  *)
    echo "Usage: $0 {start|stop|status}" >&2
    exit 2
    ;;
esac
