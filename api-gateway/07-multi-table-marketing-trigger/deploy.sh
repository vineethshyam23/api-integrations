#!/usr/bin/env bash
# Example deploy: Cloud Run backend + API Gateway config for multi-table
# marketing-trigger extracts. Replace PROJECT_ID / REGION / BACKEND_URL /
# GATEWAY_SA before running. Prefer --set-secrets for table ids.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-PROJECT_ID}"
REGION="${REGION:-europe-west1}"
SERVICE_ID="${SERVICE_ID:-marketing-triggers}"
API_ID="${API_ID:-marketing-triggers-api}"
CONFIG_ID="${CONFIG_ID:-marketing-triggers-config-001}"
GATEWAY_ID="${GATEWAY_ID:-marketing-triggers-gw}"
OPENAPI_FILE="${OPENAPI_FILE:-openapi.yaml}"
SOURCE_DIR="${SOURCE_DIR:-.}"

echo "Using project=${PROJECT_ID} region=${REGION}"

gcloud config set project "${PROJECT_ID}"

gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  apigateway.googleapis.com servicecontrol.googleapis.com servicemanagement.googleapis.com

# Backend: one Cloud Run service serving all /triggers/* paths.
# Table ids: prefer Secret Manager over long-lived --set-env-vars.
gcloud run deploy "${SERVICE_ID}" \
  --source="${SOURCE_DIR}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --allow-unauthenticated=false \
  --set-env-vars="CORS_ALLOW_ORIGIN=https://CLIENT.example.com,EXPOSE_ERROR_DETAIL=false" \
  --quiet

BACKEND_URL="$(gcloud run services describe "${SERVICE_ID}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --format='value(status.url)' | sed 's#^https://##')"

echo "Backend host: ${BACKEND_URL}"
echo "Update openapi.yaml x-google-backend.address hosts to https://${BACKEND_URL}/triggers/..."
echo "Then create a new api-config id (do not overwrite in place)."

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

gcloud api-gateway gateways describe "${GATEWAY_ID}" \
  --location="${REGION}" \
  --project="${PROJECT_ID}" \
  --format="value(defaultHostname)"

echo "Grant the gateway SA roles/run.invoker on ${SERVICE_ID}."
echo "Set TRIGGER_*_TABLE and TRIGGER_FIELDS_METADATA_TABLE (prefer --set-secrets)."
