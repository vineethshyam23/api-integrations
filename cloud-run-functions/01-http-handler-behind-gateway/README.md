# Pattern 01 (Cloud Functions): HTTP handler behind API Gateway

Sanitized HTTP Cloud Function / Cloud Run handler meant to sit behind Google Cloud API Gateway. Covers multi-path routing when the gateway forwards paths, structured logging, parameterized BigQuery access, and IAM between gateway and backend.

Pairs with the gateway OpenAPI pattern in [`api-gateway/01-customer-lookup-openapi/`](../../api-gateway/01-customer-lookup-openapi/) (edge auth + `x-google-backend`). This folder is the **backend** side of that architecture for a multi-route analytics-style API.

## Why this pattern

- Gateway API keys alone are not enough if the function URL is publicly invokable.
- Gen2 backends often do not see the public OpenAPI path on `request.path` — you need forwarded-path handling or path-aware backend addresses.
- String-built SQL in handlers is a recurring production footgun; this rewrite uses query parameters.

## File index

| File | Purpose |
|------|---------|
| `main.py` | `lookup` HTTP entry point + route helpers + BQ queries |
| `requirements.txt` | Runtime dependencies |
| `deploy.sh` | Example Gen2 deploy + invoker bindings (placeholders) |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components, Mermaid diagrams, IAM checklist |
| `DATA_FLOW.md` | Request path and failure modes |
| `README.md` | This overview |

## Sanitization notes

Derived from `dags/horeca_digital/cloud_functions/dev/cloud_function_main.py` (and path behaviour implied by the companion swagger gateway YAML in the same tree).

Removed or replaced:

- Real GCP project IDs (`hd-dwh-*` → `PROJECT_ID` env)
- Contact emails / company product framing from companion OpenAPI
- Live Cloud Run hostnames from gateway swagger (`*.run.app` → placeholders in docs only)
- Demo `/debug` endpoint that echoed headers and args
- Emoji-heavy local test harness (`main()` block) — not useful in the pattern pack
- Unsafe f-string filters → parameterized BigQuery queries

No API keys or OAuth tokens were present in the Python source; none are included here. The public BigQuery sample dataset name is kept as a neutral stand-in for "read analytics tables".

## Quick start

1. Set env placeholders and deploy:

```bash
export PROJECT_ID=PROJECT_ID
export REGION=europe-west1
./deploy.sh
```

2. Point your gateway OpenAPI `x-google-backend.address` at the printed function URI (per path or shared — see `ARCHITECTURE.md`).

3. Call via the gateway, not the function URL:

```bash
curl -sS "https://GATEWAY_HOST/daily-visits?page=1&limit=5&key=YOUR_API_KEY"
curl -sS "https://GATEWAY_HOST/ga-sessions-data?date=20170801&country=United%20States&limit=2&key=YOUR_API_KEY"
```

4. Confirm function IAM: gateway SA can invoke; anonymous cannot.

## Related next patterns

- Multi-route dashboard OpenAPI → `api-gateway/02-...`
- API key restriction template → `api-and-services-keys/01-...`
- Apigee proxy / KVM (placeholders only) → `apigee/01-...`
