#!/usr/bin/env bash
# Example Gen2 deploy for the account-composition DE lookup handler.
# Replace PROJECT_ID / REGION / SA / PREFIX placeholders before running.
# Do not put real table IDs, prefixes tied to live customer data, or secrets in git.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-PROJECT_ID}"
REGION="${REGION:-europe-west1}"
FUNCTION_NAME="${FUNCTION_NAME:-account-composition-lookup}"
RUNTIME="${RUNTIME:-python312}"
RUNTIME_SA="${RUNTIME_SA:-FUNCTION_SA@${PROJECT_ID}.iam.gserviceaccount.com}"
GATEWAY_SA="${GATEWAY_SA:-GATEWAY_SA@${PROJECT_ID}.iam.gserviceaccount.com}"
BQ_PROJECT_ID="${BQ_PROJECT_ID:-${PROJECT_ID}}"
DATASET_ID="${DATASET_ID:-DATASET_ID}"
ACCOUNT_LOOKUP_TABLE="${ACCOUNT_LOOKUP_TABLE:-}"
# Country-scoped account layout. Replace with your national / org prefix at deploy.
ACCOUNT_ID_PREFIX="${ACCOUNT_ID_PREFIX:-COUNTRY_ACCOUNT_PREFIX}"
ACCOUNT_STORE_WIDTH="${ACCOUNT_STORE_WIDTH:-3}"
ACCOUNT_METRO_WIDTH="${ACCOUNT_METRO_WIDTH:-8}"
ACCOUNT_LOOKUP_CREATED_FROM="${ACCOUNT_LOOKUP_CREATED_FROM:-2024-02-01}"
# Dev-only: set true to return exception detail in 500 JSON. Never enable in prod.
EXPOSE_ERROR_DETAIL="${EXPOSE_ERROR_DETAIL:-false}"

echo "Deploying ${FUNCTION_NAME} to project=${PROJECT_ID} region=${REGION} BQ_PROJECT_ID=${BQ_PROJECT_ID}"

gcloud config set project "${PROJECT_ID}"

ENV_VARS="BQ_PROJECT_ID=${BQ_PROJECT_ID},DATASET_ID=${DATASET_ID},ACCOUNT_ID_PREFIX=${ACCOUNT_ID_PREFIX},ACCOUNT_STORE_WIDTH=${ACCOUNT_STORE_WIDTH},ACCOUNT_METRO_WIDTH=${ACCOUNT_METRO_WIDTH},ACCOUNT_LOOKUP_CREATED_FROM=${ACCOUNT_LOOKUP_CREATED_FROM},EXPOSE_ERROR_DETAIL=${EXPOSE_ERROR_DETAIL}"
if [[ -n "${ACCOUNT_LOOKUP_TABLE}" ]]; then
  ENV_VARS="${ENV_VARS},ACCOUNT_LOOKUP_TABLE=${ACCOUNT_LOOKUP_TABLE}"
fi

gcloud functions deploy "${FUNCTION_NAME}" \
  --gen2 \
  --runtime="${RUNTIME}" \
  --region="${REGION}" \
  --source="." \
  --entry-point=lookup \
  --trigger-http \
  --no-allow-unauthenticated \
  --service-account="${RUNTIME_SA}" \
  --set-env-vars="${ENV_VARS}" \
  --memory=256Mi \
  --timeout=45s

gcloud functions add-invoker-policy-binding "${FUNCTION_NAME}" \
  --region="${REGION}" \
  --member="serviceAccount:${GATEWAY_SA}" \
  --role="roles/cloudfunctions.invoker"

gcloud run services add-iam-policy-binding "${FUNCTION_NAME}" \
  --region="${REGION}" \
  --member="serviceAccount:${GATEWAY_SA}" \
  --role="roles/run.invoker" || true

gcloud functions describe "${FUNCTION_NAME}" \
  --region="${REGION}" \
  --gen2 \
  --format="value(serviceConfig.uri)"

echo "Reminder: keep EXPOSE_ERROR_DETAIL=false in prod; point OpenAPI x-google-backend at this URI for /account-activity."
