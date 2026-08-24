#!/usr/bin/env bash
# Example Gen2 deploy for the vendor API key auth handler.
# Replace PROJECT_ID / REGION / SA / secret placeholders before running.
# Do not put real key material in git, shell history, or CI logs.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-PROJECT_ID}"
REGION="${REGION:-europe-west1}"
FUNCTION_NAME="${FUNCTION_NAME:-vendor-lookup-api}"
RUNTIME="${RUNTIME:-python312}"
RUNTIME_SA="${RUNTIME_SA:-FUNCTION_SA@${PROJECT_ID}.iam.gserviceaccount.com}"
GATEWAY_SA="${GATEWAY_SA:-GATEWAY_SA@${PROJECT_ID}.iam.gserviceaccount.com}"
DATASET_ID="${DATASET_ID:-DATASET_ID}"
# Prefer Secret Manager in real deploys; env shown only as a placeholder shape.
VENDOR_API_KEY="${VENDOR_API_KEY:-YOUR_API_KEY}"

echo "Deploying ${FUNCTION_NAME} to project=${PROJECT_ID} region=${REGION}"

gcloud config set project "${PROJECT_ID}"

gcloud functions deploy "${FUNCTION_NAME}" \
  --gen2 \
  --runtime="${RUNTIME}" \
  --region="${REGION}" \
  --source="." \
  --entry-point=main \
  --trigger-http \
  --no-allow-unauthenticated \
  --service-account="${RUNTIME_SA}" \
  --set-env-vars="PROJECT_ID=${PROJECT_ID},DATASET_ID=${DATASET_ID},CORS_ALLOW_ORIGIN=https://VENDOR_CLIENT.example.com,VENDOR_API_KEY=${VENDOR_API_KEY}" \
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

echo "Reminder: rotate VENDOR_API_KEY via Secret Manager; avoid --set-env-vars for secrets long-term."
