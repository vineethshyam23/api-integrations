#!/usr/bin/env bash
# Example deploy: API Gateway config for Bearer-only CX user lookup OpenAPI.
# Backend is Cloud Run (path /getUsers). Prefer Secret Manager for the shared
# secret the service validates — do not bake keys into --set-env-vars or OpenAPI.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-PROJECT_ID}"
REGION="${REGION:-europe-west1}"
API_ID="${API_ID:-cx-user-lookup-api}"
CONFIG_ID="${CONFIG_ID:-cx-user-lookup-bearer-001}"
GATEWAY_ID="${GATEWAY_ID:-cx-user-lookup-gw}"
OPENAPI_FILE="${OPENAPI_FILE:-openapi.yaml}"
BACKEND_URL="${BACKEND_URL:-BACKEND_URL}"

echo "Using project=${PROJECT_ID} region=${REGION}"

bash "$(dirname "$0")/check-bearer-contract.sh" "${OPENAPI_FILE}"

gcloud config set project "${PROJECT_ID}"

gcloud services enable apigateway.googleapis.com \
  servicecontrol.googleapis.com servicemanagement.googleapis.com

echo "Confirm openapi.yaml x-google-backend.address is https://${BACKEND_URL}/getUsers"
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
echo "Create / rotate an API key or shared secret for Bearer clients; restrict platform keys to this API when using API & Services."
echo "Smoke:"
echo "  curl -sS -H \"Authorization: Bearer YOUR_API_KEY\" \\"
echo "    \"https://GATEWAY_HOST/getUsers?establishment_id=EST_ID\""
