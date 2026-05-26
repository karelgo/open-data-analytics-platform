#!/usr/bin/env bash
# Maak (of hergebruik) de k3d-cluster.
# Idempotent: als de cluster al bestaat, doet niets.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CLUSTER_NAME="${CLUSTER_NAME:-odap-platform}"
CONFIG="$ROOT/infrastructure/k3d/k3d-cluster.yaml"

if ! command -v k3d >/dev/null 2>&1; then
  echo "ERROR: k3d niet gevonden. Installeer: https://k3d.io/" >&2
  exit 1
fi

if k3d cluster list -o json 2>/dev/null | jq -e ".[] | select(.name==\"${CLUSTER_NAME}\")" >/dev/null; then
  servers_running=$(k3d cluster list -o json | jq -r ".[] | select(.name==\"${CLUSTER_NAME}\") | .serversRunning")
  if [[ "${servers_running}" -gt 0 ]]; then
    echo "k3d cluster '${CLUSTER_NAME}' bestaat al en draait. Overslaan."
  else
    echo "==> k3d cluster '${CLUSTER_NAME}' bestaat maar staat stil. Starten..."
    k3d cluster start "${CLUSTER_NAME}"

    # Docker's bridge network can re-assign agent IPs across stop/start cycles.
    # k3s mints the kubelet serving cert at first boot with the IP it sees then
    # and does not auto-detect IP changes, so post-restart `kubectl logs/exec`
    # fails with `x509: certificate is valid for IP X, not IP Y`. We delete the
    # cert + key on each agent and bounce them so k3s regenerates with the
    # current IP. Adds ~15s; harmless if IPs happened to match.
    agents=()
    while IFS= read -r name; do
      [[ -n "$name" ]] && agents+=("$name")
    done < <(k3d node list -o json 2>/dev/null | \
              jq -r ".[] | select(.role==\"agent\" and (.name | startswith(\"k3d-${CLUSTER_NAME}-\"))) | .name")

    if (( ${#agents[@]} > 0 )); then
      echo "==> Refreshing kubelet serving certs on ${#agents[@]} agent(s) to match current Docker IPs"
      for agent in "${agents[@]}"; do
        docker exec "$agent" rm -f \
          /var/lib/rancher/k3s/agent/serving-kubelet.crt \
          /var/lib/rancher/k3s/agent/serving-kubelet.key 2>/dev/null || true
      done
      docker restart "${agents[@]}" >/dev/null
      echo "==> Waiting for kubelet to report current IPs in node status..."
      # Wait until each agent's reported InternalIP matches its current Docker IP.
      # Ready alone is not enough — the Ready condition flips back to True before
      # the kubelet patches its status with the new IP, and kubectl logs/exec
      # would still hit the stale IP for several seconds.
      for agent in "${agents[@]}"; do
        docker_ip="$(docker inspect "$agent" -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')"
        until [[ "$(kubectl get node "$agent" -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}' 2>/dev/null)" == "$docker_ip" ]]; do
          sleep 2
        done
      done
    fi
  fi
else
  echo "==> Cluster aanmaken vanaf $CONFIG"
  k3d cluster create --config "$CONFIG"
fi

# Pin kubectl's current-context to the local cluster.
#
# `k3d cluster create` sets the context on first creation, but
# `k3d cluster start` (the idempotent re-run path above) does NOT touch
# kubeconfig. Meanwhile `scripts/azure/aks-context.sh` (via
# `az aks get-credentials --overwrite-existing`) flips current to AKS.
# So after even one round-trip — "did some AKS work, came back locally,
# re-ran make cluster" — the current-context is still AKS and every
# kubectl that followed silently targeted the wrong cluster.
# This line closes the hole symmetrically with the AKS path.
echo "==> setting kubectl context: k3d-${CLUSTER_NAME}"
kubectl config use-context "k3d-${CLUSTER_NAME}"
kubectl get nodes
