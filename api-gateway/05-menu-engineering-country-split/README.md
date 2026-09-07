# Pattern 10: Menu-engineering country-split OpenAPI (API Gateway + Cloud Function)

Google Cloud API Gateway OpenAPI config for a menu-engineering POS sold-items surface. One path (`/menu-pos`), one `X-API-Key`, HTTP Cloud Function backend. Callers pass a required establishment id and an optional **country enum** (`de` / `fr`) that selects a country-scoped warehouse table. Companion `main.py` shows the allowlist → table map and parameterized BigQuery — the part OpenAPI cannot express alone.

## Why this pattern

Patterns 03 and 09 already cover multi-route dashboards and paired compound filters. This one is for multi-country fact tables behind a single public contract:

- Closed `country` enum on the gateway, not a free-form table name
- Env-backed table map (`MENU_POS_TABLE_DE` / `MENU_POS_TABLE_FR`)
- ISO date window + offset/limit with SQL `OFFSET` (not post-query Python slices)
- Parameterized warehouse reads (sanitize away f-string SQL from source)

## File index

| File | Purpose |
|------|---------|
| `openapi.yaml` | Sanitized Swagger 2.0 path + securityDefinitions + response schemas |
| `main.py` | Sanitized Cloud Function handler with country table map + parameterized BQ |
| `deploy.sh` | Example `gcloud` API + config + gateway deploy |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path, country branch, failure modes |
| `README.md` | This overview |

## Routes covered

| Path | Backend placeholder | Notes |
|------|---------------------|-------|
| `/menu-pos` | `REGION-PROJECT_ID.cloudfunctions.net/menu-engineering-pos` | Country enum → table map in handler |

## Sanitization notes

Derived from:

- `dags/horeca_digital/cloud_functions/prd/dish-menu-engineering-pos.yml`
- `dags/horeca_digital/cloud_functions/prd/dish-menu-engineering-pos.py`

Removed or replaced:

- Product / company branding and contact email in `info`
- Real Cloud Function hostname and GCP project id → `REGION-PROJECT_ID.cloudfunctions.net/menu-engineering-pos`
- Dataset / table names → `PROJECT_ID.DATASET_ID.pos_sold_items_{de,fr}` (+ establishments map)
- Path renamed `/dish-pos` → `/menu-pos` for generic teaching
- Source f-string SQL interpolation → BigQuery query parameters
- Source Python post-`LIMIT` offset slice → SQL `OFFSET` / `LIMIT`
- Source OpenAPI DD-MM-YYYY vs handler ISO defaults → aligned on YYYY-MM-DD
- Source silent fallback of unknown country to DE → **400** for unsupported country
- Exception detail gated behind `EXPOSE_ERROR_DETAIL`

No API keys or OAuth tokens were present in the source YAML; none are included here.

## Quick start

1. Edit `openapi.yaml` and set `x-google-backend.address` to your function URL.
2. Deploy the handler (`main.py`) with `MENU_POS_TABLE_DE`, `MENU_POS_TABLE_FR`, and `MENU_POS_ESTABLISHMENTS_TABLE` set (prefer secrets for anything sensitive).
3. Deploy API config + gateway (see `deploy.sh`).
4. Grant the gateway service account invoker on the function.
5. Create an API key in API & Services, restrict it to this API, and call:

```bash
curl -sS "https://GATEWAY_HOST/menu-pos?establishmentUID=EST-001&country=de&limit=50" \
  -H "X-API-Key: YOUR_API_KEY"

curl -sS "https://GATEWAY_HOST/menu-pos?establishmentUID=EST-001&country=fr&startDate=2024-01-01&endDate=2024-01-31" \
  -H "X-API-Key: YOUR_API_KEY"
```

Expect **400** for an unsupported `country`, non-ISO dates, or out-of-range `limit`.

## Related patterns

- Multi-route dashboard OpenAPI → [`../02-multi-route-dashboard-openapi/`](../02-multi-route-dashboard-openapi/)
- Multi-filter tickets OpenAPI → [`../04-multi-filter-tickets-openapi/`](../04-multi-filter-tickets-openapi/)
- Env-scoped BQ pagination handler → [`../../cloud-run-functions/04-env-scoped-bq-pagination/`](../../cloud-run-functions/04-env-scoped-bq-pagination/)
- Restricted API key → [`../../api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)
- Apigee proxy / KVM → `apigee/` (blocked until notes exist)
