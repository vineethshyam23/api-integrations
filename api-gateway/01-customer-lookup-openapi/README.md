# Pattern 01: Customer Lookup via API Gateway (OpenAPI)

Google Cloud API Gateway config that fronts an HTTP Cloud Function for a simple customer-account lookup. The gateway owns API-key auth; the backend returns environment-specific application URLs for a given account ID.

## Why this pattern

Lookup endpoints are easy to over-expose. Putting API Gateway in front of the function gives you:

- A stable public hostname separate from the function URL
- API-key enforcement before traffic hits compute
- An OpenAPI contract that doubles as deployable gateway config

This is the smallest useful gateway + function shape used for internal / partner-facing lookups.

## File index

| File | Purpose |
|------|---------|
| `openapi.yaml` | Sanitized Swagger 2.0 / OpenAPI config with `x-google-backend` |
| `deploy.sh` | Example `gcloud` deploy flow (placeholders only) |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagram |
| `DATA_FLOW.md` | Request path and failure modes |
| `README.md` | This overview |

## Sanitization notes

Derived from a real gateway OpenAPI under `dags/horeca_digital/cloud_functions/` (customer-lookup style configs in `dev/` and `prd/`).

Removed or replaced:

- Company / product titles and contact emails
- Real GCP project IDs and Cloud Function hostnames
- Domain-specific field names (`metroId` → `accountId`, CO env URL fields → generic `app_*_url`)
- Live backend addresses → `REGION-PROJECT_ID` / `customer-lookup` placeholders

No API keys, OAuth tokens, or KVM payloads were present in the source YAML; none are included here.

## Quick start

1. Copy `openapi.yaml` and set `x-google-backend.address` to your function URL.
2. Deploy an API config + gateway (see `deploy.sh`).
3. Create an API key in API & Services, restrict it to this API, and call:

```bash
curl -sS "https://GATEWAY_HOST/Customer?accountId=12345&key=YOUR_API_KEY"
```

4. Prefer header-based keys (`X-API-Key`) for new APIs; this pattern keeps query `key` to match common existing gateway configs.

## Related next patterns

- Cloud Function HTTP handler behind this gateway → `cloud-run-functions/`
- API key restriction template → `api-and-services-keys/`
- Broader multi-route dashboard OpenAPI → later `api-gateway/` entry
