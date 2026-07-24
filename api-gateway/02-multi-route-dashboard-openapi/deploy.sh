#!/usr/bin/env bash
# Example deploy for a multi-route OpenAPI config + API Gateway.
# Replace PROJECT_ID / REGION / GATEWAY_SA placeholders before running.
# Backend function URLs live in openapi.yaml (x-google-backend per path).
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-PROJECT_ID}"
REGION="${REGION:-europe-west1}"
API_ID="${API_ID:-establishment-dashboard-api}"
CONFIG_ID="${CONFIG_ID:-establishment-dashboard-config-001}"
GATEWAY_ID="${GATEWAY_ID:-establishment-dashboard-gw}"
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

echo "Remember: grant the gateway SA invoker on EVERY backend function listed in openapi.yaml."
