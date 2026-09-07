#!/usr/bin/env bash
# Example deploy for menu-engineering country-split OpenAPI + API Gateway
# in front of an HTTP Cloud Function. Replace PROJECT_ID / REGION / GATEWAY_SA
# before running. Backend URL lives in openapi.yaml (x-google-backend).
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-PROJECT_ID}"
REGION="${REGION:-europe-west1}"
API_ID="${API_ID:-menu-pos-api}"
CONFIG_ID="${CONFIG_ID:-menu-pos-config-001}"
GATEWAY_ID="${GATEWAY_ID:-menu-pos-gw}"
OPENAPI_FILE="${OPENAPI_FILE:-openapi.yaml}"

echo "Using project=${PROJECT_ID} region=${REGION}"

gcloud config set project "${PROJECT_ID}"

gcloud services enable apigateway.googleapis.com servicecontrol.googleapis.com \
  servicemanagement.googleapis.com

gcloud api-gateway apis create "${API_ID}" --project="${PROJECT_ID}" || true

# New OpenAPI revision = new config id. Do not overwrite in place.
gcloud api-gateway api-configs create "${CONFIG_ID}" \
  --api="${API_ID}" \
  --openapi-spec="${OPENAPI_FILE}" \
  --project="${PROJECT_ID}" \
  --backend-auth-service-account="GATEWAY_SA@${PROJECT_ID}.iam.gserviceaccount.com"

if gcloud api-gateway gateways describe "${GATEWAY_ID}" --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud api-gateway gateways update "${GATEWAY_ID}" \
    --api="${API_ID}" \
    --api-config="${CONFIG_ID}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}"
else
  gcloud api-gateway gateways create "${GATEWAY_ID}" \
    --api="${API_ID}" \
    --api-config="${CONFIG_ID}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}"
fi

gcloud api-gateway gateways describe "${GATEWAY_ID}" \
  --location="${REGION}" \
  --project="${PROJECT_ID}" \
  --format="value(defaultHostname)"

echo "Remember: grant the gateway SA cloudfunctions.invoker (or run.invoker) on the backend."
echo "Prefer Secret Manager / --set-secrets for MENU_POS_TABLE_DE / MENU_POS_TABLE_FR."
