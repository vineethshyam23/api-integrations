# Pattern 05 (Cloud Functions): POS daily-transactions offset/limit

Sanitized HTTP Cloud Function for **establishment-scoped POS daily transactions** with pagination pushed into BigQuery (`LIMIT` / `OFFSET`). Focus is the v3 rewrite away from format-string SQL and Python list slicing, plus an explicit `BQ_PROJECT_ID` deploy contract.

Complements:

- Multi-route dashboard OpenAPI (`/v2` vs `/v3` getPOS) → [`api-gateway/02-multi-route-dashboard-openapi/`](../../api-gateway/02-multi-route-dashboard-openapi/)
- Env-scoped country extract pagination → [`04-env-scoped-bq-pagination/`](../04-env-scoped-bq-pagination/)
- Restricted API key at API & Services → [`api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)

Edge API keys and backend IAM still apply. This pattern is about how the **backend pages warehouse history safely** for one establishment.

## Why this pattern

- v2-style handlers that `LIMIT` a large set and slice in Python waste BigQuery bytes and RAM as histories grow.
- String-interpolated `establishment_id` filters are an avoidable injection risk.
- Naming the job project `ENV` made deploy scripts and on-call harder than `BQ_PROJECT_ID`.
- Clients already speak `establishmentId` + `offset`/`limit` on `/v3/getPOS` — keep that contract, fix the implementation.

## File index

| File | Purpose |
|------|---------|
| `main.py` | `lookup` HTTP entry point, parameterized SQL page read |
| `requirements.txt` | Runtime dependencies |
| `deploy.sh` | Example Gen2 deploy + invoker bindings (placeholders) |
| `openapi.yaml` | Sanitized companion OpenAPI for `/v3/getPOS` |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path and failure modes |
| `README.md` | This overview |

## Sanitization notes

Derived from `dags/horeca_digital/cloud_functions/prd/dish-panel-pos-gbq-v3.py` (contrast with v2 sibling for the anti-pattern).

Removed or replaced:

- Product / company naming and real dataset / table identifiers → `DATASET_ID.pos_daily_transactions`
- Real GCP project IDs and the vague `ENV` project env → `BQ_PROJECT_ID` / `PROJECT_ID`
- Live Cloud Function hostnames → `BACKEND_URL`
- Format-string SQL (`.format(est_id, limit, offset)`) → `@establishment_id` / `@limit` / `@offset`
- Bare `except:` that mapped every failure to 404 → typed 400 / 404 / 500 with gated detail
- `print(query)` of interpolated SQL → structured log of table + paging only

No API keys or OAuth tokens from source are included. Table override values in docs are placeholders only.

## Quick start

1. Set placeholders:

```bash
export PROJECT_ID=PROJECT_ID
export REGION=europe-west1
export BQ_PROJECT_ID=PROJECT_ID
export DATASET_ID=DATASET_ID
export EXPOSE_ERROR_DETAIL=true
chmod +x deploy.sh
./deploy.sh
```

2. Point gateway OpenAPI `x-google-backend.address` for `/v3/getPOS` at the function URI (see `openapi.yaml`).

3. Call via gateway:

```bash
curl -sS -H "X-API-Key: YOUR_API_KEY" \
  "https://GATEWAY_HOST/v3/getPOS?establishmentId=EST-1001&offset=0&limit=20"
```

4. Confirm: missing `establishmentId` → **400**; empty page → **404**; prod keeps `EXPOSE_ERROR_DETAIL=false`.

## Related next patterns

- Apigee proxy / product / KVM (placeholders only) → `apigee/01-...` when notes exist
- Remaining unused OpenAPI twin / panel dashboard variant → `api-gateway/10-...` only if still unique vs 03 / 11
