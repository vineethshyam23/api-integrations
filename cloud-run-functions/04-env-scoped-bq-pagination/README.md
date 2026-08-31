# Pattern 04 (Cloud Functions): Env-scoped BigQuery pagination

Sanitized HTTP Cloud Function / Cloud Run handler for a **country-filtered, paginated warehouse extract**. Focus is environment separation via `DEPLOY_ENV`, optional full-table override, parameterized BigQuery, and gated 500 detail for non-prod debugging.

Complements:

- Multi-route dashboard / analytics OpenAPI → [`api-gateway/02-...`](../../api-gateway/02-multi-route-dashboard-openapi/), [`api-gateway/03-...`](../../api-gateway/03-ga-sessions-daily-visits-openapi/)
- Vendor app-layer key handler → [`02-vendor-api-key-auth-handler/`](../02-vendor-api-key-auth-handler/)
- Restricted API key at API & Services → [`api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)

Edge API keys and backend IAM still apply. This pattern is about how the **backend picks the right table and fails safely** when the same code ships to more than one GCP project.

## Why this pattern

- Extract APIs often share one codebase across `dev` and `prod` but must never read the wrong warehouse by accident.
- Hardcoding `project.dataset.table` in Python forces forks or risky edits per environment.
- `DEPLOY_ENV=dev|prod` plus an optional `MARKET_POTENTIAL_BQ_TABLE` override is a small, auditable contract for deploy scripts and Cloud Run env vars.
- Partners page large country slices with `pageSize` / `pageNumber`; returning `{records, pagination}` keeps clients stable.
- Exception text in JSON is useful in staging and a leak in production — gate it with `EXPOSE_ERROR_DETAIL`.

## File index

| File | Purpose |
|------|---------|
| `main.py` | `main` HTTP entry point, table resolve, paginated BQ read |
| `requirements.txt` | Runtime dependencies |
| `deploy.sh` | Example Gen2 deploy + invoker bindings (placeholders) |
| `openapi.yaml` | Sanitized companion OpenAPI for the extract route |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path and failure modes |
| `README.md` | This overview |

## Sanitization notes

Derived from `dags/horeca_digital/cloud_functions/prd/pos_potential_sam_api_integrated.py` and companion OpenAPI (`pos_potential_sam_api_integrated.yml`).

Removed or replaced:

- Product / company naming and real dataset / table identifiers → `DATASET_ID.market_potential`
- Real GCP project IDs → `PROJECT_ID` / `PROJECT_ID_DEV`
- Live Cloud Run hostnames (`*.run.app`) → `BACKEND_URL`
- Contact emails and internal license branding from OpenAPI
- Route renamed to `/getMarketPotentialData` (generic extract shape)
- CORS default `*` replaced with `CORS_ALLOW_ORIGIN` env (deploy script defaults to an example origin)

No API keys or OAuth tokens from source are included. Table override env values in docs are placeholders only.

## Quick start

1. Set placeholders:

```bash
export PROJECT_ID=PROJECT_ID
export REGION=europe-west1
export DEPLOY_ENV=dev
export EXPOSE_ERROR_DETAIL=true
export CORS_ALLOW_ORIGIN=https://CLIENT.example.com
./deploy.sh
```

2. Point gateway OpenAPI `x-google-backend.address` at the function URI + `/getMarketPotentialData` (see `openapi.yaml`).

3. Call via gateway:

```bash
curl -sS -H "X-API-KEY: YOUR_API_KEY" \
  "https://GATEWAY_HOST/getMarketPotentialData?countryCode=DE&pageSize=100&pageNumber=1"
```

4. Confirm: missing `DEPLOY_ENV` → **500** with (optional) detail; bad country → **400**; empty page → **404**; prod keeps `EXPOSE_ERROR_DETAIL=false`.

## Related next patterns

- Apigee proxy / product / KVM (placeholders only) → `apigee/01-...` when notes exist
- Multi-filter tickets OpenAPI (paired query params) → `api-gateway/04-...` if still unused
- Gateway Bearer / header passthrough deep-dive — only if distinct from pattern 06 companion OpenAPI
