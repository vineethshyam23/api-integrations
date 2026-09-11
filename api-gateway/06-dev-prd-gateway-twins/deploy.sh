#!/usr/bin/env bash
# Deploy one env twin of the account-activities gateway.
# Set ENV=prd|dev (default prd). Each env gets its own API / config / gateway
# ids and OpenAPI file — do not overwrite prd config with the dev twin.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV="${ENV:-prd}"

case "${ENV}" in
  prd)
    OPENAPI_FILE="${OPENAPI_FILE:-${ROOT}/openapi.prd.yaml}"
    API_ID="${API_ID:-account-activities-api}"
    CONFIG_ID="${CONFIG_ID:-account-activities-prd-001}"
    GATEWAY_ID="${GATEWAY_ID:-account-activities-gw}"
    PROJECT_ID="${PROJECT_ID:-PROJECT_ID}"
    ;;
  dev)
    OPENAPI_FILE="${OPENAPI_FILE:-${ROOT}/openapi.dev.yaml}"
    API_ID="${API_ID:-account-activities-api-dev}"
    CONFIG_ID="${CONFIG_ID:-account-activities-dev-001}"
    GATEWAY_ID="${GATEWAY_ID:-account-activities-gw-dev}"
    PROJECT_ID="${PROJECT_ID:-PROJECT_ID_DEV}"
    ;;
  *)
    echo "ENV must be prd or dev (got: ${ENV})" >&2
    exit 2
    ;;
esac

REGION="${REGION:-europe-west1}"
GATEWAY_SA="${GATEWAY_SA:-GATEWAY_SA@${PROJECT_ID}.iam.gserviceaccount.com}"

echo "Deploying ENV=${ENV} project=${PROJECT_ID} openapi=${OPENAPI_FILE}"

# Contract gate before any cloud mutation.
bash "${ROOT}/check-twins.sh"

gcloud config set project "${PROJECT_ID}"

gcloud services enable apigateway.googleapis.com servicecontrol.googleapis.com \
  servicemanagement.googleapis.com

gcloud api-gateway apis create "${API_ID}" --project="${PROJECT_ID}" || true

# New OpenAPI revision = new config id. Never reuse a config id across envs.
gcloud api-gateway api-configs create "${CONFIG_ID}" \
  --api="${API_ID}" \
  --openapi-spec="${OPENAPI_FILE}" \
  --project="${PROJECT_ID}" \
  --backend-auth-service-account="${GATEWAY_SA}"

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

echo "Grant the gateway SA invoker on the ${ENV} backend function / Cloud Run service."
echo "Create / restrict an API key per env in API & Services — do not share prd keys into DEV clients."
