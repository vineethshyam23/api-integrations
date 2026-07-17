#!/usr/bin/env bash
# Example deploy for a single OpenAPI config + API Gateway.
# Replace all YOUR_* / PROJECT_ID / REGION placeholders before running.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-PROJECT_ID}"
REGION="${REGION:-europe-west1}"
API_ID="${API_ID:-customer-lookup-api}"
CONFIG_ID="${CONFIG_ID:-customer-lookup-config-001}"
GATEWAY_ID="${GATEWAY_ID:-customer-lookup-gw}"
OPENAPI_FILE="${OPENAPI_FILE:-openapi.yaml}"

echo "Using project=${PROJECT_ID} region=${REGION}"

gcloud config set project "${PROJECT_ID}"

# Enable APIs once per project (safe to re-run).
gcloud services enable apigateway.googleapis.com servicecontrol.googleapis.com \
  servicemanagement.googleapis.com

# Create API (ignore error if it already exists).
gcloud api-gateway apis create "${API_ID}" --project="${PROJECT_ID}" || true

# Each OpenAPI change needs a new config id.
gcloud api-gateway api-configs create "${CONFIG_ID}" \
  --api="${API_ID}" \
  --openapi-spec="${OPENAPI_FILE}" \
  --project="${PROJECT_ID}" \
  --backend-auth-service-account="GATEWAY_SA@${PROJECT_ID}.iam.gserviceaccount.com"

# Create or update gateway to point at the new config.
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
