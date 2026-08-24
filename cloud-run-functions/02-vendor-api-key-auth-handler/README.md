# Pattern 02 (Cloud Functions): Vendor API key auth handler

Sanitized HTTP Cloud Function / Cloud Run handler for a **vendor-facing** lookup API. Focus is application-layer shared-secret validation with `hmac.compare_digest`, multi-path routing (`/getUser`, `/getEstablishments`, `/getPosUser`), and parameterized BigQuery reads.

Complements:

- Gateway + IAM backend pattern → [`01-http-handler-behind-gateway/`](../01-http-handler-behind-gateway/)
- Restricted API key at API & Services → [`api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)

Edge API keys and backend IAM are still required. This pattern adds a third control: the handler itself rejects requests that lack a valid shared secret, which matters when a vendor client hits Cloud Run directly or when gateway auth is misconfigured.

## Why this pattern

- Vendor integrations often insist on `X-Api-Key` or `Authorization: Bearer` on every call.
- `==` comparisons on secrets are a footgun under timing side channels; `hmac.compare_digest` is the boring correct default in Python.
- Loading the expected key from env (or Secret Manager → env) keeps secrets out of source. A local `.env` fallback is useful for laptop tests and dangerous if committed — keep `.env` gitignored.
- Path-suffix routing matches how API Gateway / Cloud Run often forward `/getUser` etc. onto one service URL.

## File index

| File | Purpose |
|------|---------|
| `main.py` | `main` HTTP entry point, key check, BQ handlers |
| `requirements.txt` | Runtime dependencies |
| `deploy.sh` | Example Gen2 deploy + invoker bindings (placeholders) |
| `openapi.example.yaml` | Sanitized companion OpenAPI for the three routes |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path and failure modes |
| `README.md` | This overview |

## Sanitization notes

Derived from `dags/horeca_digital/cloud_functions/prd/medalia_api_integrated.py` and companion OpenAPI (`medalia_integrated.yml`).

Removed or replaced:

- Product / company naming (vendor CX integration → generic "vendor lookup")
- Real GCP project IDs and trusted dataset / table names → `PROJECT_ID` / `DATASET_ID` / env table names
- Live Cloud Run hostnames (`*.run.app`) → `BACKEND_URL`
- Contact emails and license branding from OpenAPI
- Example payloads that contained real-looking emails, phones, and person names
- Any implication of real key material — env name is `VENDOR_API_KEY`, value always `YOUR_API_KEY` in docs/scripts

No API keys or OAuth tokens from source are included here. Do not commit `.env`.

## Quick start

1. Set placeholders (use Secret Manager for the key in real deploys):

```bash
export PROJECT_ID=PROJECT_ID
export DATASET_ID=DATASET_ID
export REGION=europe-west1
export VENDOR_API_KEY=YOUR_API_KEY
./deploy.sh
```

2. Point gateway OpenAPI `x-google-backend.address` values at the function URI + path (see `openapi.example.yaml`).

3. Call via gateway (preferred) or only while testing with IAM credentials:

```bash
curl -sS -H "X-Api-Key: YOUR_API_KEY" \
  "https://GATEWAY_HOST/getUser?account_id=ACCOUNT_ID"

curl -sS -H "Authorization: Bearer YOUR_API_KEY" \
  "https://GATEWAY_HOST/getEstablishments?establishment_id=EST_ID"
```

4. Confirm: missing/wrong key → **401** from the handler; unauthenticated invoke → **403** from IAM when `--no-allow-unauthenticated` is set.

## Related next patterns

- Apigee proxy / product / KVM (placeholders only) → `apigee/01-...` when notes exist
- Outbound vendor HTTP client (pull) → only if a real outbound client appears under source
