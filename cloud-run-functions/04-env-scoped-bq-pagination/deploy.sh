#!/usr/bin/env bash
# Example Gen2 deploy for the env-scoped BigQuery pagination handler.
# Replace PROJECT_ID / REGION / SA placeholders before running.
# Do not put real table overrides or secrets in git or CI logs.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-PROJECT_ID}"
REGION="${REGION:-europe-west1}"
FUNCTION_NAME="${FUNCTION_NAME:-market-potential-api}"
RUNTIME="${RUNTIME:-python312}"
RUNTIME_SA="${RUNTIME_SA:-FUNCTION_SA@${PROJECT_ID}.iam.gserviceaccount.com}"
GATEWAY_SA="${GATEWAY_SA:-GATEWAY_SA@${PROJECT_ID}.iam.gserviceaccount.com}"
# Required: exactly "dev" or "prod" (lowercase). Drives default BQ table.
DEPLOY_ENV="${DEPLOY_ENV:-dev}"
# Optional full project.dataset.table override. Leave empty to use defaults.
MARKET_POTENTIAL_BQ_TABLE="${MARKET_POTENTIAL_BQ_TABLE:-}"
# Dev-only: set true to return exception detail in 500 JSON. Never enable in prod.
EXPOSE_ERROR_DETAIL="${EXPOSE_ERROR_DETAIL:-false}"
CORS_ALLOW_ORIGIN="${CORS_ALLOW_ORIGIN:-https://CLIENT.example.com}"

echo "Deploying ${FUNCTION_NAME} to project=${PROJECT_ID} region=${REGION} DEPLOY_ENV=${DEPLOY_ENV}"

gcloud config set project "${PROJECT_ID}"

ENV_VARS="DEPLOY_ENV=${DEPLOY_ENV},EXPOSE_ERROR_DETAIL=${EXPOSE_ERROR_DETAIL},CORS_ALLOW_ORIGIN=${CORS_ALLOW_ORIGIN}"
if [[ -n "${MARKET_POTENTIAL_BQ_TABLE}" ]]; then
  ENV_VARS="${ENV_VARS},MARKET_POTENTIAL_BQ_TABLE=${MARKET_POTENTIAL_BQ_TABLE}"
fi

gcloud functions deploy "${FUNCTION_NAME}" \
  --gen2 \
  --runtime="${RUNTIME}" \
  --region="${REGION}" \
  --source="." \
  --entry-point=main \
  --trigger-http \
  --no-allow-unauthenticated \
  --service-account="${RUNTIME_SA}" \
  --set-env-vars="${ENV_VARS}" \
  --memory=512Mi \
  --timeout=60s

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

echo "Reminder: keep EXPOSE_ERROR_DETAIL=false in prod; point OpenAPI BACKEND_URL at the URI above + /getMarketPotentialData."
