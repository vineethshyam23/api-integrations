# Pattern 03: Multi-route dashboard OpenAPI (API Gateway)

Google Cloud API Gateway OpenAPI config with several dashboard routes behind one hostname. Each path has its own `x-google-backend` Cloud Function address. API-key auth uses the `X-API-Key` header. Path versioning (`/v2/getPOS` vs `/v3/getPOS`) shows how to migrate response schemas without spinning up a second gateway.

## Why this pattern

Pattern 01 is a single lookup route. Real dashboards need a small surface of related GETs:

- One public contract and one key for clients
- Independent backends so POS can ship without redeploying visits
- Explicit versioned paths when a KPI payload changes shape

## File index

| File | Purpose |
|------|---------|
| `openapi.yaml` | Sanitized Swagger 2.0 multi-path config with per-route backends |
| `deploy.sh` | Example `gcloud` API + config + gateway deploy |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path, versioning, failure modes |
| `README.md` | This overview |

## Routes covered

| Path | Backend placeholder | Notes |
|------|---------------------|-------|
| `/v2/getEstablishment` | `panel-establishment-v2` | Profile + product flags |
| `/v1/getVisits` | `panel-visits` | Paginated; date filters |
| `/v1/getOrders` | `panel-orders` | Paginated; date filters |
| `/v1/getReservations` | `panel-reservations` | Paginated; date filters |
| `/v2/getPOS` | `panel-pos-v2` | Legacy KPI shape |
| `/v3/getPOS` | `panel-pos-v3` | Newer slim KPI shape |

## Sanitization notes

Derived from `dags/horeca_digital/cloud_functions/prd/dish_pos_openapi_spec.yml` (panel / establishment dashboard OpenAPI; companion panel YAML under `prd/` and `dev/`).

Removed or replaced:

- Company / product titles and branding (`HD`, `DISH`, etc.)
- Real GCP project IDs and Cloud Function hostnames → `REGION-PROJECT_ID` / `panel-*`
- CRM vendor naming (`Salesforce ID` → `crm_id`)
- Product-flag field names (`has_Dish_*` → `has_website`, `has_pos`, …)
- Locale-specific payment labels in POS v2 → generic channel names
- Placeholder documentation URLs / contact emails from source `info` / tags

No API keys, OAuth tokens, or KVM secret payloads were present in the source YAML; none are included here.

## Quick start

1. Edit `openapi.yaml` and set each `x-google-backend.address` to your function URLs.
2. Deploy API config + gateway (see `deploy.sh`).
3. Grant the gateway service account invoker on **every** backend function.
4. Create an API key in API & Services, restrict it to this API, and call:

```bash
curl -sS "https://GATEWAY_HOST/v2/getEstablishment?establishmentId=EST-123" \
  -H "X-API-Key: YOUR_API_KEY"

curl -sS "https://GATEWAY_HOST/v1/getVisits?establishmentId=EST-123&limit=20" \
  -H "X-API-Key: YOUR_API_KEY"
```

## Related patterns

- Single-route customer lookup → [`../01-customer-lookup-openapi/`](../01-customer-lookup-openapi/)
- HTTP handler behind gateway → [`../../cloud-run-functions/01-http-handler-behind-gateway/`](../../cloud-run-functions/01-http-handler-behind-gateway/)
- API key restriction template → `api-and-services-keys/` (planned)
