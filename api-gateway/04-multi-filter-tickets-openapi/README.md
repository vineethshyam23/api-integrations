# Pattern 09: Multi-filter tickets OpenAPI (API Gateway + Cloud Run)

Google Cloud API Gateway OpenAPI config for a helpdesk ticket lookup surface. One path (`/tickets`), one `X-API-Key`, Cloud Run backend. Callers filter by establishment, a **paired** metro+store identity, or a metro account identifier. Companion `main.py` shows the 400 pair check and parameterized BigQuery — the part OpenAPI cannot express alone.

## Why this pattern

Patterns 01–04 already cover single-route lookup, dashboard multi-route, and analytics extract OpenAPI. This one is for compound filter contracts:

- Optional filters that are not all independent (`metroId` + `storeId` must travel together)
- Offset/limit + `count` (not a `has_next` envelope)
- Header API key in front of Cloud Run
- Parameterized warehouse reads (sanitize away f-string SQL from source)

## File index

| File | Purpose |
|------|---------|
| `openapi.yaml` | Sanitized Swagger 2.0 path + securityDefinitions + response schemas |
| `main.py` | Sanitized Cloud Run / Functions handler with parameterized BQ |
| `deploy.sh` | Example `gcloud` API + config + gateway deploy |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path, pair validation, failure modes |
| `README.md` | This overview |

## Routes covered

| Path | Backend placeholder | Notes |
|------|---------------------|-------|
| `/tickets` | `tickets-api-REGION-PROJECT_ID.a.run.app` | Multi-filter GET; pair check in handler |

## Sanitization notes

Derived from:

- `dags/horeca_digital/cloud_functions/prd/odoo-tickets-mde.yml`
- `dags/horeca_digital/cloud_functions/prd/odoo-tickets-mde.py`

Removed or replaced:

- Product / company branding and contact email in `info`
- Real Cloud Run hostname and GCP project number → `tickets-api-REGION-PROJECT_ID.a.run.app`
- Dataset / table names → `PROJECT_ID.DATASET_ID.helpdesk_ticket`
- Country literal → env `TICKETS_COUNTRY_SCOPE` / placeholder
- Path renamed `/odoo-tickets` → `/tickets` for generic teaching
- Source f-string SQL interpolation → BigQuery query parameters
- Verbose per-ticket print logging → structured filter-dimension logs
- Exception detail gated behind `EXPOSE_ERROR_DETAIL`

No API keys or OAuth tokens were present in the source YAML; none are included here.

## Quick start

1. Edit `openapi.yaml` and set `x-google-backend.address` to your Cloud Run URL.
2. Deploy the handler (`main.py`) to Cloud Run / Cloud Functions with `TICKETS_BQ_TABLE` and `TICKETS_COUNTRY_SCOPE` set (prefer secrets for anything sensitive).
3. Deploy API config + gateway (see `deploy.sh`).
4. Grant the gateway service account `roles/run.invoker` on the Cloud Run service.
5. Create an API key in API & Services, restrict it to this API, and call:

```bash
curl -sS "https://GATEWAY_HOST/tickets?establishmentId=EST-001&limit=50" \
  -H "X-API-Key: YOUR_API_KEY"

curl -sS "https://GATEWAY_HOST/tickets?metroId=M1&storeId=42&offset=0&limit=100" \
  -H "X-API-Key: YOUR_API_KEY"
```

Expect **400** if you send only `metroId` or only `storeId`.

## Related patterns

- Single-route customer lookup → [`../01-customer-lookup-openapi/`](../01-customer-lookup-openapi/)
- Multi-route dashboard OpenAPI → [`../02-multi-route-dashboard-openapi/`](../02-multi-route-dashboard-openapi/)
- GA sessions / daily-visits OpenAPI → [`../03-ga-sessions-daily-visits-openapi/`](../03-ga-sessions-daily-visits-openapi/)
- Env-scoped BQ pagination handler → [`../../cloud-run-functions/04-env-scoped-bq-pagination/`](../../cloud-run-functions/04-env-scoped-bq-pagination/)
- Restricted API key → [`../../api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)
- Apigee proxy / KVM → `apigee/` (blocked until notes exist)
