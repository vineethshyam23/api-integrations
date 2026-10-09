#!/usr/bin/env bash
# Example deploy: API Gateway config for a multi-route panel OpenAPI.
# Runs check-path-security.sh first so a securityDefinitions-only draft
# cannot become a live unauthenticated gateway.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-PROJECT_ID}"
REGION="${REGION:-europe-west1}"
API_ID="${API_ID:-panel-dashboard-api}"
CONFIG_ID="${CONFIG_ID:-panel-dashboard-path-sec-001}"
GATEWAY_ID="${GATEWAY_ID:-panel-dashboard-gw}"
OPENAPI_FILE="${OPENAPI_FILE:-openapi.yaml}"

echo "Using project=${PROJECT_ID} region=${REGION}"

bash "$(dirname "$0")/check-path-security.sh" "${OPENAPI_FILE}"

gcloud config set project "${PROJECT_ID}"

gcloud services enable apigateway.googleapis.com \
  servicecontrol.googleapis.com servicemanagement.googleapis.com

echo "Confirm each x-google-backend.address points at the correct function URL."
echo "New OpenAPI revision requires a new api-config id (do not overwrite in place)."

gcloud api-gateway apis create "${API_ID}" --project="${PROJECT_ID}" || true

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

echo "Grant roles/cloudfunctions.invoker (or roles/run.invoker) on each backend to GATEWAY_SA@${PROJECT_ID}.iam.gserviceaccount.com"
echo "Create / rotate a restricted API key for clients; never put YOUR_API_KEY into OpenAPI."
echo "Smoke (expect 401 without header):"
echo "  curl -sS -H \"X-API-KEY: YOUR_API_KEY\" \\"
echo "    \"https://GATEWAY_HOST/getEstablishment?establishmentId=EST_ID\""
