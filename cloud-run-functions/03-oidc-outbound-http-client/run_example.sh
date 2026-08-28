#!/usr/bin/env bash
# Example: pull one page-walk from a protected Cloud Run feed with OIDC.
# Replace placeholders. Do not commit real hostnames or tokens.

set -euo pipefail

export BACKEND_URL="${BACKEND_URL:-https://SERVICE-HASH.REGION.run.app}"
export FEED_ENDPOINT_FULL="${FEED_ENDPOINT_FULL:-getCatalogData}"
export FEED_ENDPOINT_DAILY="${FEED_ENDPOINT_DAILY:-getCatalogDailyData}"

# Caller needs roles/run.invoker (or equivalent) on the target service.
# Local: gcloud auth login && gcloud auth application-default login
# In-GCP: use the job / function runtime SA with run.invoker on BACKEND_URL.

python client.py --page-size 100 --max-pages 2 --out-json catalog_sample.json
