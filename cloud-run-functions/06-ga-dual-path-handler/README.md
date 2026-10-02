# Pattern 06 (Cloud Functions): GA dual-path handler

Sanitized HTTP Cloud Function that serves **two API Gateway routes from one backend**: flat `/daily-visits` and nested `/ga-sessions-data`. Focus is how the handler recovers the intended route when the gateway forwards path via headers (or strips it), plus parameterized BigQuery against a public sample dataset.

Complements:

- Gateway OpenAPI for the same routes → [`api-gateway/03-ga-sessions-daily-visits-openapi/`](../../api-gateway/03-ga-sessions-daily-visits-openapi/)
- Generic HTTP handler behind gateway → [`01-http-handler-behind-gateway/`](../01-http-handler-behind-gateway/)
- Restricted API key at API & Services → [`api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)

Edge API keys and backend IAM still apply. This pattern is about **route resolution + response-shape split inside one function**.

## Why this pattern

- Two OpenAPI paths often share one Cloud Run / Gen2 URI. `request.path` alone is unreliable once the gateway rewrites or strips the path.
- Production gateways may forward `X-Forwarded-Path`, `X-Envoy-Original-Path`, or `X-Original-URI` — the handler must check all of them.
- Flat daily visits and nested GA sessions need different SQL, filters, and JSON shapes, but not two deployables if traffic is low.
- Public BigQuery sample tables are a safe teaching / smoke-test source; overrides keep the same code path for private marts.

## File index

| File | Purpose |
|------|---------|
| `main.py` | `lookup` entry point, dual-route resolution, parameterized BQ |
| `requirements.txt` | Runtime dependencies |
| `deploy.sh` | Example Gen2 deploy + invoker bindings (placeholders) |
| `openapi.yaml` | Companion dual-route OpenAPI (both backends → same URI) |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path and failure modes |
| `README.md` | This overview |

## Sanitization notes

Derived from `dags/horeca_digital/cloud_functions/dev/cloud_function_main.py` (companion gateway YAML already shipped as pattern 04 / folder `api-gateway/03-...`).

Removed or replaced:

- Hard-coded billing project → `BQ_PROJECT_ID`
- Format-string / quote-escaped SQL filters → `@param` query parameters
- Unbounded header dump debug endpoint → removed
- Interview / progressive-learning demo `main()` with emoji output → removed
- Contact email and course branding (gateway sibling) → not present here
- Live Cloud Run hostnames → `BACKEND_URL` in companion OpenAPI

No API keys or OAuth tokens from source are included. Table overrides in docs are placeholders only.

## Quick start

1. Set placeholders:

```bash
export PROJECT_ID=PROJECT_ID
export REGION=europe-west1
export BQ_PROJECT_ID=PROJECT_ID
export EXPOSE_ERROR_DETAIL=true
chmod +x deploy.sh
./deploy.sh
```

2. Point **both** OpenAPI `x-google-backend.address` values at the function URI, keeping `/daily-visits` and `/ga-sessions-data` path suffixes (see `openapi.yaml` and pattern `api-gateway/03-...`).

3. Call via gateway:

```bash
curl -sS -H "X-API-Key: YOUR_API_KEY" \
  "https://GATEWAY_HOST/daily-visits?page=1&limit=5&start_date=2017-07-01"

curl -sS -H "X-API-Key: YOUR_API_KEY" \
  "https://GATEWAY_HOST/ga-sessions-data?page=1&limit=5&date=20170801&device_category=mobile"
```

4. Confirm: bad `date` / `device_category` → **400**; empty page → **404**; prod keeps `EXPOSE_ERROR_DETAIL=false`.

## Related next patterns

- Apigee proxy / product / KVM (placeholders only) → `apigee/01-...` when notes exist
- POS establishment lookup OpenAPI → `api-gateway/11-...` only if still unique vs pattern 01
