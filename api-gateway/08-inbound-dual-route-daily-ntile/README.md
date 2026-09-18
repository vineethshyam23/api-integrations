# Pattern 13: Inbound dual-route daily NTILE pagination (API Gateway + Cloud Run)

Google Cloud API Gateway OpenAPI config for a **partner-facing establishment feed** with two extract modes on one Cloud Run service:

1. `/establishments` — full refined catalog, hard **404** on empty pages
2. `/establishments/daily` — calendar NTILE bucket over `establishment_id`, soft **200** with empty `records` + `message` on quiet days (including first-of-month)

Complements:

- Outbound OIDC paginated pull → [`../../cloud-run-functions/03-oidc-outbound-http-client/`](../../cloud-run-functions/03-oidc-outbound-http-client/) (this pattern is **inbound** BQ, not outbound HTTP)
- Multi-table marketing-trigger OpenAPI → [`../07-multi-table-marketing-trigger/`](../07-multi-table-marketing-trigger/) (many tables; here: **same schema, two modes**)
- Multi-route dashboard OpenAPI → [`../02-multi-route-dashboard-openapi/`](../02-multi-route-dashboard-openapi/)

## Why this pattern

Regional tourism / destination partners often need both a full baseline dump and a paced daily incremental. Options that fail in practice:

- One path + a `mode=daily` query param → clients get the modes wrong; OpenAPI cannot document distinct empty-page semantics cleanly
- Separate services per mode → double keys, double invoker bindings, double deploy ceremony
- Hard 404 on quiet daily days → partner jobs treat "no slice today" as an outage

Better: two paths, one hostname, one API key. Full catalog stays strict. Daily path uses NTILE over a stable id with day-of-month as the bucket selector, and returns a soft empty envelope when the bucket is quiet so polling stays simple.

## File index

| File | Purpose |
|------|---------|
| `openapi.yaml` | Sanitized Swagger 2.0 dual-path gateway config |
| `main.py` | Cloud Run / Functions handler: full + daily NTILE |
| `requirements.txt` | Runtime dependencies |
| `deploy.sh` | Example Cloud Run + API Gateway deploy (placeholders) |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path and failure modes |
| `README.md` | This overview |

## Routes covered

| Path | Behavior | Empty semantics |
|------|----------|-----------------|
| `/establishments` | Full catalog `LIMIT/OFFSET` + `COUNT` | **404** No data found |
| `/establishments/daily` | NTILE bucket for yesterday's day-of-month | **200** `{records:[], message, pagination}` |

Both share `pageSize` / `pageNumber` (max 1000) and return `{records, pagination}` (optional `message` on daily).

## Sanitization notes

Derived from:

- `dags/horeca_digital/cloud_functions/prd/tourismnrw_integrated.yml`
- `dags/horeca_digital/cloud_functions/prd/tourismnrw_api.py`
  (identical twin: `cloud_function_tourismnrw.py`)

Removed or replaced:

- Product / partner / regional tourism branding and contact email
- Real Cloud Run hostname and numeric project id → `BACKEND_URL` / `PROJECT_ID`
- Real dataset / table ids → `ESTABLISHMENTS_TABLE` / `ESTABLISHMENTS_DAILY_TABLE` env
- Paths renamed `/getTourismNrwData` → `/establishments`, `/getTourismNrwDailyData` → `/establishments/daily`
- Column `google_places_id` → `places_legacy_id` (generic transition id)
- Contact email / phone columns dropped from the public sample schema
- f-string / `.format()` SQL for LIMIT/OFFSET and NTILE args → BigQuery query parameters
- `print(query)` removed; use structured logging only
- CORS default `*` → `CORS_ALLOW_ORIGIN` env
- Ungated 500 bodies → `EXPOSE_ERROR_DETAIL`
- Added `ORDER BY establishment_id` for stable paging
- Added pageSize max (1000) to match practical partner caps

No API keys or OAuth tokens were present as secret material in the source YAML; none are included here.

## Quick start

1. Edit `openapi.yaml` and set every `x-google-backend.address` to your Cloud Run URL + path.
2. Deploy the handler with `ESTABLISHMENTS_TABLE` and `ESTABLISHMENTS_DAILY_TABLE` set (prefer secrets). Align column names with your warehouse (including `places_legacy_id` or rename in code).
3. Deploy API config + gateway (see `deploy.sh`). New OpenAPI revision = new config id.
4. Grant the gateway SA `roles/run.invoker` on the Cloud Run service.
5. Create an API key in API & Services, restrict it to this API, and call:

```bash
curl -sS -H "X-API-KEY: YOUR_API_KEY" \
  "https://GATEWAY_HOST/establishments?pageSize=100&pageNumber=1"

curl -sS -H "X-API-KEY: YOUR_API_KEY" \
  "https://GATEWAY_HOST/establishments/daily?pageSize=100&pageNumber=1"
```

Expect **400** for bad paging, **404** for empty full-catalog pages, **200** with empty records + message on quiet daily days, **403** at the edge for a bad key.

## Related patterns

- OIDC outbound HTTP client → [`../../cloud-run-functions/03-oidc-outbound-http-client/`](../../cloud-run-functions/03-oidc-outbound-http-client/)
- Multi-table marketing-trigger → [`../07-multi-table-marketing-trigger/`](../07-multi-table-marketing-trigger/)
- Env-scoped BQ pagination → [`../../cloud-run-functions/04-env-scoped-bq-pagination/`](../../cloud-run-functions/04-env-scoped-bq-pagination/)
- Restricted API key → [`../../api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)
- Apigee proxy / KVM → `apigee/` (blocked until notes exist)
