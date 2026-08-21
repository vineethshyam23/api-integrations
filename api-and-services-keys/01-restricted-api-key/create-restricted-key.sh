#!/usr/bin/env bash
# Create an API key restricted to one API Gateway API (and optional IP allowlist).
# Replace PROJECT_ID / API_TARGET_SERVICE / CIDR placeholders before running.
# NEVER commit the printed key string.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-PROJECT_ID}"
DISPLAY_NAME="${DISPLAY_NAME:-analytics-sessions-prod}"
# Managed service name for your API Gateway API, e.g. from:
#   gcloud api-gateway apis describe API_ID --project=PROJECT_ID --format='value(managedService)'
API_TARGET_SERVICE="${API_TARGET_SERVICE:-API_TARGET_SERVICE.apigateway.PROJECT_ID.cloud.goog}"
# Optional: comma-separated CIDRs for server/ETL clients. Leave empty to skip IP restriction.
ALLOWED_IPS="${ALLOWED_IPS:-}"

echo "project=${PROJECT_ID} display_name=${DISPLAY_NAME}"
echo "Restricting key to API target: ${API_TARGET_SERVICE}"

gcloud config set project "${PROJECT_ID}"

# Create key (prints the secret once — capture to a secret store, not to git).
KEY_NAME="$(gcloud services api-keys create \
  --display-name="${DISPLAY_NAME}" \
  --format='value(name)')"

echo "Created key resource: ${KEY_NAME}"
echo "Copy the keyString from the create response into your secret store now."
echo "Then clear your shell history if the secret was echoed."

# API restriction: only the gateway managed service.
gcloud services api-keys update "${KEY_NAME}" \
  --clear-restrictions \
  --api-target="service=${API_TARGET_SERVICE}"

if [[ -n "${ALLOWED_IPS}" ]]; then
  # Application restriction: server IP allowlist (ETL / fixed egress).
  # Example: ALLOWED_IPS="203.0.113.10/32,198.51.100.0/24"
  IFS=',' read -r -a CIDRS <<< "${ALLOWED_IPS}"
  IP_ARGS=()
  for cidr in "${CIDRS[@]}"; do
    IP_ARGS+=(--allowed-ip-range="${cidr}")
  done
  gcloud services api-keys update "${KEY_NAME}" "${IP_ARGS[@]}"
  echo "Applied IP application restrictions: ${ALLOWED_IPS}"
else
  echo "No ALLOWED_IPS set — API restriction only. Prefer IP/referrer when clients allow it."
fi

gcloud services api-keys describe "${KEY_NAME}" \
  --format='yaml(displayName,restrictions)'

echo "Done. Call via GATEWAY_HOST with X-API-Key; do not paste the key into tickets or git."
