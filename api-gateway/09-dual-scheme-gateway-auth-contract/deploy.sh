#!/usr/bin/env bash
# Example deploy: API Gateway config for dual-scheme vendor lookup OpenAPI.
# Backend handler lives in cloud-run-functions/02-vendor-api-key-auth-handler.
# Prefer Secret Manager for VENDOR_API_KEY — do not bake keys into --set-env-vars.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-PROJECT_ID}"
REGION="${REGION:-europe-west1}"
API_ID="${API_ID:-vendor-lookup-api}"
CONFIG_ID="${CONFIG_ID:-vendor-lookup-auth-contract-001}"
GATEWAY_ID="${GATEWAY_ID:-vendor-lookup-gw}"
OPENAPI_FILE="${OPENAPI_FILE:-openapi.yaml}"
BACKEND_URL="${BACKEND_URL:-BACKEND_URL}"

echo "Using project=${PROJECT_ID} region=${REGION}"

# Local gate before spending a config revision.
bash "$(dirname "$0")/check-auth-contract.sh" "${OPENAPI_FILE}"

gcloud config set project "${PROJECT_ID}"

gcloud services enable apigateway.googleapis.com \
  servicecontrol.googleapis.com servicemanagement.googleapis.com

echo "Confirm openapi.yaml x-google-backend.address hosts use https://${BACKEND_URL}/getUser|getPosUser|getEstablishments"
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

echo "Grant roles/run.invoker on the Cloud Run service to GATEWAY_SA@${PROJECT_ID}.iam.gserviceaccount.com"
echo "Create / rotate an API key in API & Services restricted to this API."
echo "Smoke:"
echo "  curl -sS -H \"X-API-KEY: YOUR_API_KEY\" \"https://GATEWAY_HOST/getUser?account_id=ACCOUNT_ID\""
echo "  curl -sS -H \"Authorization: Bearer YOUR_API_KEY\" \"https://GATEWAY_HOST/getEstablishments?establishment_id=EST_ID\""
