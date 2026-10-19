#!/usr/bin/env bash
# Example Gen2 deploy for the LEGACY POS KPI in-memory-slice handler.
# Prefer panel-pos-v3 (pattern 15) for new traffic. Keep this only while
# /v2/getPOS clients still need the old shape.
# Replace PROJECT_ID / REGION / SA placeholders before running.
# Do not put real table IDs or secrets in git or CI logs.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-PROJECT_ID}"
REGION="${REGION:-europe-west1}"
FUNCTION_NAME="${FUNCTION_NAME:-panel-pos-v2}"
RUNTIME="${RUNTIME:-python312}"
RUNTIME_SA="${RUNTIME_SA:-FUNCTION_SA@${PROJECT_ID}.iam.gserviceaccount.com}"
GATEWAY_SA="${GATEWAY_SA:-GATEWAY_SA@${PROJECT_ID}.iam.gserviceaccount.com}"
# Legacy source used ENV as the BigQuery project — keep the name so the
# museum handler matches production history; set it to PROJECT_ID in demos.
ENV="${ENV:-${PROJECT_ID}}"
DATASET_ID="${DATASET_ID:-DATASET_ID}"
POS_KPI_TABLE="${POS_KPI_TABLE:-}"

echo "Deploying LEGACY ${FUNCTION_NAME} to project=${PROJECT_ID} region=${REGION} ENV=${ENV}"
echo "Reminder: this handler pages in memory after BigQuery LIMIT. Prefer pattern 15 for new clients."

gcloud config set project "${PROJECT_ID}"

ENV_VARS="ENV=${ENV},DATASET_ID=${DATASET_ID}"
if [[ -n "${POS_KPI_TABLE}" ]]; then
  ENV_VARS="${ENV_VARS},POS_KPI_TABLE=${POS_KPI_TABLE}"
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

echo "Point OpenAPI x-google-backend for /v2/getPOS at this URI only while migrating."
