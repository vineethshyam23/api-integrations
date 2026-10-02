#!/usr/bin/env bash
# Example Gen2 deploy for the GA dual-path analytics handler.
# Replace PROJECT_ID / REGION / SA placeholders before running.
# Do not put real table overrides or secrets in git or CI logs.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-PROJECT_ID}"
REGION="${REGION:-europe-west1}"
FUNCTION_NAME="${FUNCTION_NAME:-analytics-dual-path-api}"
RUNTIME="${RUNTIME:-python312}"
RUNTIME_SA="${RUNTIME_SA:-FUNCTION_SA@${PROJECT_ID}.iam.gserviceaccount.com}"
GATEWAY_SA="${GATEWAY_SA:-GATEWAY_SA@${PROJECT_ID}.iam.gserviceaccount.com}"

# Billing / job project for BigQuery client (queries may read a public dataset).
BQ_PROJECT_ID="${BQ_PROJECT_ID:-${PROJECT_ID}}"
PUBLIC_PROJECT_ID="${PUBLIC_PROJECT_ID:-bigquery-public-data}"
GA_DATASET_ID="${GA_DATASET_ID:-google_analytics_sample}"
# Optional full-table overrides. Leave empty to use public sample defaults.
DAILY_VISITS_TABLE="${DAILY_VISITS_TABLE:-}"
GA_SESSIONS_TABLE_TEMPLATE="${GA_SESSIONS_TABLE_TEMPLATE:-}"
# Dev-only: set true to return exception detail in 500 JSON. Never enable in prod.
EXPOSE_ERROR_DETAIL="${EXPOSE_ERROR_DETAIL:-false}"
CORS_ALLOW_ORIGIN="${CORS_ALLOW_ORIGIN:-https://CLIENT.example.com}"

echo "Deploying ${FUNCTION_NAME} to project=${PROJECT_ID} region=${REGION}"

gcloud config set project "${PROJECT_ID}"

ENV_VARS="BQ_PROJECT_ID=${BQ_PROJECT_ID},PUBLIC_PROJECT_ID=${PUBLIC_PROJECT_ID},GA_DATASET_ID=${GA_DATASET_ID},EXPOSE_ERROR_DETAIL=${EXPOSE_ERROR_DETAIL},CORS_ALLOW_ORIGIN=${CORS_ALLOW_ORIGIN}"
if [[ -n "${DAILY_VISITS_TABLE}" ]]; then
  ENV_VARS="${ENV_VARS},DAILY_VISITS_TABLE=${DAILY_VISITS_TABLE}"
fi
if [[ -n "${GA_SESSIONS_TABLE_TEMPLATE}" ]]; then
  ENV_VARS="${ENV_VARS},GA_SESSIONS_TABLE_TEMPLATE=${GA_SESSIONS_TABLE_TEMPLATE}"
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

URI="$(gcloud functions describe "${FUNCTION_NAME}" \
  --region="${REGION}" \
  --gen2 \
  --format="value(serviceConfig.uri)")"

echo "Function URI: ${URI}"
echo "Point OpenAPI x-google-backend.address for BOTH routes at this URI"
echo "(keep path suffixes /daily-visits and /ga-sessions-data on the gateway paths)."
echo "Reminder: keep EXPOSE_ERROR_DETAIL=false in prod."
