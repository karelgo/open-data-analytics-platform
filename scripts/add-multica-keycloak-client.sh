#!/usr/bin/env bash
# Add the `multica` OIDC client to the running Keycloak instance.
#
# Why this exists:
#   `infrastructure/helm/keycloak/realm.json` defines the multica client
#   declaratively, but Keycloak only imports the realm on FIRST startup.
#   When the realm already exists (upgrade / re-run scenarios) the import
#   is skipped, so the new client never lands.
#
# This script uses the Keycloak admin REST API to add (or update) the
# multica client in-place — idempotent, safe to re-run.
#
# Run: from the repo root, after `make bootstrap` finished. Requires
# kubectl to be pointed at the cluster.
#
# Vars (override if defaults don't fit):
#   KC_NAMESPACE  default: odap-auth
#   KC_REALM      default: uwv
#   KC_ADMIN_USER default: admin
#   KC_ADMIN_PW_SECRET   default: keycloak (key: admin-password)

set -euo pipefail

KC_NAMESPACE="${KC_NAMESPACE:-odap-auth}"
KC_REALM="${KC_REALM:-uwv}"
# Bitnami Keycloak chart defaults to KEYCLOAK_ADMIN=kcadmin (not 'admin').
# Pinned in infrastructure/helm/keycloak/values.yaml: adminUser: kcadmin.
KC_ADMIN_USER="${KC_ADMIN_USER:-kcadmin}"
KC_ADMIN_PW_SECRET="${KC_ADMIN_PW_SECRET:-keycloak}"
KC_SVC="${KC_SVC:-keycloak}"

# Fetch admin password
ADMIN_PW=$(kubectl -n "$KC_NAMESPACE" get secret "$KC_ADMIN_PW_SECRET" \
  -o jsonpath='{.data.admin-password}' 2>/dev/null | base64 -d)
if [ -z "$ADMIN_PW" ]; then
  echo "ERROR: cannot read admin password from secret/$KC_ADMIN_PW_SECRET in $KC_NAMESPACE"
  exit 1
fi

# Run admin-cli via kubectl exec into the keycloak pod — avoids dealing with
# external TLS / hostnames.
KC_POD=$(kubectl -n "$KC_NAMESPACE" get pod -l app.kubernetes.io/name=keycloak -o jsonpath='{.items[0].metadata.name}')
[ -z "$KC_POD" ] && { echo "ERROR: no keycloak pod found"; exit 1; }

echo "Using pod: $KC_POD"

# Get admin access token
TOKEN=$(kubectl -n "$KC_NAMESPACE" exec "$KC_POD" -- \
  curl -sf -X POST \
    "http://localhost:8080/realms/master/protocol/openid-connect/token" \
    -d "client_id=admin-cli" \
    -d "username=$KC_ADMIN_USER" \
    -d "password=$ADMIN_PW" \
    -d "grant_type=password" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

if [ -z "$TOKEN" ]; then
  echo "ERROR: failed to obtain admin token"
  exit 1
fi

# Check if multica client already exists
EXISTING=$(kubectl -n "$KC_NAMESPACE" exec "$KC_POD" -- \
  curl -sf -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8080/admin/realms/${KC_REALM}/clients?clientId=multica")

if echo "$EXISTING" | grep -q '"clientId":"multica"'; then
  echo "Multica client already exists — skipping create."
  exit 0
fi

# Build the client payload (mirror of realm.json entry)
PAYLOAD=$(cat <<'JSON'
{
  "clientId": "multica",
  "name": "ODAP Platform — Multica",
  "description": "OIDC-client for the oauth2-proxy voor https://multica.odap.local",
  "enabled": true,
  "protocol": "openid-connect",
  "publicClient": false,
  "secret": "odap-dev-only-CHANGE-ME-multica-secret",
  "standardFlowEnabled": true,
  "directAccessGrantsEnabled": false,
  "serviceAccountsEnabled": false,
  "redirectUris": [
    "https://multica.odap.local:8443/oauth2/callback",
    "https://multica.odap.local/oauth2/callback"
  ],
  "webOrigins": [
    "https://multica.odap.local:8443",
    "https://multica.odap.local"
  ],
  "attributes": {
    "post.logout.redirect.uris": "https://multica.odap.local:8443/*##https://multica.odap.local/*"
  },
  "defaultClientScopes": ["web-origins", "profile", "roles", "email"],
  "fullScopeAllowed": true,
  "protocolMappers": [
    {
      "name": "username-as-email",
      "protocol": "openid-connect",
      "protocolMapper": "oidc-usermodel-property-mapper",
      "consentRequired": false,
      "config": {
        "user.attribute": "username",
        "claim.name": "email",
        "jsonType.label": "String",
        "id.token.claim": "true",
        "access.token.claim": "true",
        "userinfo.token.claim": "true"
      }
    },
    {
      "name": "audience-multica",
      "protocol": "openid-connect",
      "protocolMapper": "oidc-audience-mapper",
      "consentRequired": false,
      "config": {
        "included.client.audience": "multica",
        "id.token.claim": "true",
        "access.token.claim": "true"
      }
    }
  ]
}
JSON
)

# Create the client. Pipe payload via stdin → curl --data-binary @-
HTTP_CODE=$(echo "$PAYLOAD" | kubectl -n "$KC_NAMESPACE" exec -i "$KC_POD" -- \
  curl -sf -o /dev/null -w "%{http_code}" \
    -X POST "http://localhost:8080/admin/realms/${KC_REALM}/clients" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    --data-binary @-)

if [ "$HTTP_CODE" = "201" ]; then
  echo "Multica client created in realm $KC_REALM."
else
  echo "ERROR: client create returned HTTP $HTTP_CODE"
  exit 1
fi
