#!/usr/bin/env bash
# Example deploy of the HTTP handler as a Gen2 Cloud Function (Cloud Run under the hood).
# Replace PROJECT_ID / REGION / SA placeholders before running.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-PROJECT_ID}"
REGION="${REGION:-europe-west1}"
FUNCTION_NAME="${FUNCTION_NAME:-analytics-lookup}"
RUNTIME="${RUNTIME:-python312}"
# Service account used by the function at runtime (BigQuery job user, etc.)
RUNTIME_SA="${RUNTIME_SA:-FUNCTION_SA@${PROJECT_ID}.iam.gserviceaccount.com}"
# Gateway (or other invoker) service account that may call this function
GATEWAY_SA="${GATEWAY_SA:-GATEWAY_SA@${PROJECT_ID}.iam.gserviceaccount.com}"

echo "Deploying ${FUNCTION_NAME} to project=${PROJECT_ID} region=${REGION}"

gcloud config set project "${PROJECT_ID}"

gcloud functions deploy "${FUNCTION_NAME}" \
  --gen2 \
  --runtime="${RUNTIME}" \
  --region="${REGION}" \
  --source="." \
  --entry-point=lookup \
  --trigger-http \
  --no-allow-unauthenticated \
  --service-account="${RUNTIME_SA}" \
  --set-env-vars="PROJECT_ID=${PROJECT_ID},CORS_ALLOW_ORIGIN=https://DASHBOARD_ORIGIN.example.com" \
  --memory=512Mi \
  --timeout=60s

# Only the gateway (or CI invoker) should call this URL directly.
gcloud functions add-invoker-policy-binding "${FUNCTION_NAME}" \
  --region="${REGION}" \
  --member="serviceAccount:${GATEWAY_SA}" \
  --role="roles/cloudfunctions.invoker"

# Gen2 also needs Cloud Run invoker on the underlying service in many setups.
gcloud run services add-iam-policy-binding "${FUNCTION_NAME}" \
  --region="${REGION}" \
  --member="serviceAccount:${GATEWAY_SA}" \
  --role="roles/run.invoker" || true

gcloud functions describe "${FUNCTION_NAME}" \
  --region="${REGION}" \
  --gen2 \
  --format="value(serviceConfig.uri)"
