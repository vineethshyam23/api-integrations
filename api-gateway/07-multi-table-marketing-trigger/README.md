# Pattern 12: Multi-table marketing-trigger OpenAPI (API Gateway + Cloud Run)

Google Cloud API Gateway OpenAPI config for a **multi-path marketing-trigger extract**. One Cloud Run service backs six product-domain paths plus a fields-metadata endpoint. The handler keeps a `TABLE_CONFIGS` map and a shared `fetch_data_with_pagination` helper — that shared helper is the point of this pattern, not another single-route OpenAPI copy.

Complements:

- Multi-route dashboard (per-route backends, analytics shape) → [`../02-multi-route-dashboard-openapi/`](../02-multi-route-dashboard-openapi/)
- Env-scoped single-table pagination → [`../../cloud-run-functions/04-env-scoped-bq-pagination/`](../../cloud-run-functions/04-env-scoped-bq-pagination/)
- Dev/prd OpenAPI twin discipline → [`../06-dev-prd-gateway-twins/`](../06-dev-prd-gateway-twins/)

## Why this pattern

Marketing automation often needs the same paging contract across many warehouse tables (contacts, payments, POS, reservations, …). Options that fail in practice:

- One gateway API per table → key sprawl and client config hell
- One mega-query with a `dataset` query param → callers invent table names
- Copy-paste six nearly identical handlers → drift on caps, date formatting, envelopes

Better: one hostname, one API key, many paths. Each path is a closed enum in code (`PATH_TO_CONFIG`). Table ids live in env / Secret Manager. Pagination, date formatting, and `{records, pagination}` stay in one function.

The fields-metadata path is the second differentiator: partners need the source→destination field map without scraping OpenAPI schemas that intentionally use `additionalProperties`.

## File index

| File | Purpose |
|------|---------|
| `openapi.yaml` | Sanitized Swagger 2.0 multi-path gateway config |
| `main.py` | Cloud Run / Functions handler: path map + shared pagination + metadata |
| `requirements.txt` | Runtime dependencies |
| `deploy.sh` | Example Cloud Run + API Gateway deploy (placeholders) |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path and failure modes |
| `README.md` | This overview |

## Routes covered

| Path | Config key | Notes |
|------|------------|-------|
| `/triggers/contacts` | `contacts` | Paginated contact trigger rows |
| `/triggers/payments` | `payments` | Payments / KYC trigger rows |
| `/triggers/network-pay` | `network_pay` | Network-pay trigger rows |
| `/triggers/pos` | `pos` | POS activity trigger rows |
| `/triggers/reservations` | `reservations` | Reservation-tool trigger rows |
| `/triggers/website` | `website` | Website-builder trigger rows |
| `/triggers/fields-metadata` | (metadata table) | Model-keyed field map; no paging params |

All data paths share `pageSize` / `pageNumber` (max 10000) and return `{records, pagination}`.

## Sanitization notes

Derived from:

- `dags/horeca_digital/cloud_functions/prd/maileon_api_integrated.yml`
- `dags/horeca_digital/cloud_functions/prd/maileon_api_integrated.py`

Removed or replaced:

- Product / company / contact email / internal license branding
- Real Cloud Run hostname and numeric project id → `BACKEND_URL` / `PROJECT_ID`
- Real dataset / table ids → `PROJECT_ID.DATASET_ID.email_trigger_*` (+ env overrides)
- Vendor platform name in titles → generic "marketing trigger"
- Paths renamed to `/triggers/...` for teaching clarity
- Column lists trimmed to representative fields (no PII-heavy contact dump)
- Duplicate column entry from source contacts list removed via `dict.fromkeys`
- CORS default `*` → `CORS_ALLOW_ORIGIN` env
- Ungated exception `detail` on metadata errors → `EXPOSE_ERROR_DETAIL`
- Table ids moved behind env vars (`TRIGGER_*_TABLE`) instead of hardcoding project ids at import time

No API keys or OAuth tokens were present as secret material in the source YAML; none are included here.

## Quick start

1. Edit `openapi.yaml` and set every `x-google-backend.address` to your Cloud Run URL + path.
2. Deploy the handler with `TRIGGER_*_TABLE` and `TRIGGER_FIELDS_METADATA_TABLE` set (prefer secrets).
3. Deploy API config + gateway (see `deploy.sh`). New OpenAPI revision = new config id.
4. Grant the gateway SA `roles/run.invoker` on the Cloud Run service.
5. Create an API key in API & Services, restrict it to this API, and call:

```bash
curl -sS -H "X-API-KEY: YOUR_API_KEY" \
  "https://GATEWAY_HOST/triggers/contacts?pageSize=100&pageNumber=1"

curl -sS -H "X-API-KEY: YOUR_API_KEY" \
  "https://GATEWAY_HOST/triggers/fields-metadata"
```

Expect **400** for bad paging, **404** for empty pages / empty metadata, **403** at the edge for a bad key.

## Related patterns

- Multi-route dashboard OpenAPI → [`../02-multi-route-dashboard-openapi/`](../02-multi-route-dashboard-openapi/)
- Env-scoped BQ pagination → [`../../cloud-run-functions/04-env-scoped-bq-pagination/`](../../cloud-run-functions/04-env-scoped-bq-pagination/)
- Restricted API key → [`../../api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)
- Dev/prd gateway twins → [`../06-dev-prd-gateway-twins/`](../06-dev-prd-gateway-twins/)
- Apigee proxy / KVM → `apigee/` (blocked until notes exist)
