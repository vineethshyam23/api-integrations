# Pattern 04: GA sessions / daily-visits OpenAPI (API Gateway + Cloud Run)

Google Cloud API Gateway OpenAPI config for an analytics extraction surface. Two routes share one hostname and one `X-API-Key`. Backends are **Cloud Run** URLs with path suffixes — not separate Cloud Function names. `/daily-visits` returns flat rows; `/ga-sessions-data` returns nested session objects plus a pagination envelope.

## Why this pattern

Patterns 01 and 03 already cover lookup and dashboard multi-route OpenAPI over Cloud Functions. This one is for extract / ETL-shaped APIs:

- Page/limit envelope (`has_next`) instead of offset arrays
- ISO / `YYYYMMDD` date filters (not `DD-MM-YYYY` panel dates)
- Explicit flat vs nested response contracts on the same gateway
- Cloud Run invoker IAM (`roles/run.invoker`) once per service

## File index

| File | Purpose |
|------|---------|
| `openapi.yaml` | Sanitized Swagger 2.0 dual-path config with Cloud Run backends |
| `deploy.sh` | Example `gcloud` API + config + gateway deploy |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path, pagination loop, failure modes |
| `README.md` | This overview |

## Routes covered

| Path | Backend placeholder | Notes |
|------|---------------------|-------|
| `/daily-visits` | `analytics-api.../daily-visits` | Flat `visit_date` + `total_visits`; date range filters |
| `/ga-sessions-data` | `analytics-api.../ga-sessions-data` | Nested session; dimension filters; higher deadline |

## Sanitization notes

Derived from `dags/horeca_digital/cloud_functions/dev/swagger_api_gateway.yaml`.

Removed or replaced:

- Contact email and interview / course branding in `info`
- Real Cloud Run hostname and GCP project number → `analytics-api-REGION-PROJECT_ID.a.run.app`
- Placeholder documentation URLs under tags
- Softened interview-task wording in descriptions; kept the engineering shape

No API keys, OAuth tokens, or KVM secret payloads were present in the source YAML; none are included here.

## Quick start

1. Edit `openapi.yaml` and set each `x-google-backend.address` to your Cloud Run service URLs (keep the path suffixes).
2. Deploy API config + gateway (see `deploy.sh`).
3. Grant the gateway service account `roles/run.invoker` on the Cloud Run service.
4. Create an API key in API & Services, restrict it to this API, and call:

```bash
curl -sS "https://GATEWAY_HOST/daily-visits?page=1&limit=50&start_date=2017-07-01" \
  -H "X-API-Key: YOUR_API_KEY"

curl -sS "https://GATEWAY_HOST/ga-sessions-data?page=1&limit=20&date=20170801&device_category=mobile" \
  -H "X-API-Key: YOUR_API_KEY"
```

## Related patterns

- Single-route customer lookup → [`../01-customer-lookup-openapi/`](../01-customer-lookup-openapi/)
- Multi-route dashboard OpenAPI → [`../02-multi-route-dashboard-openapi/`](../02-multi-route-dashboard-openapi/)
- HTTP handler behind gateway → [`../../cloud-run-functions/01-http-handler-behind-gateway/`](../../cloud-run-functions/01-http-handler-behind-gateway/)
- Apigee proxy / KVM → `apigee/` (planned)
- Restricted API key → [`../../api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)
