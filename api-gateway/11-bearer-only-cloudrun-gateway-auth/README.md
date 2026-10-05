# Pattern 18: Bearer-only Cloud Run gateway auth

Google Cloud API Gateway OpenAPI for a **single-route CX user lookup** where
clients send only `Authorization: Bearer <token>`. The edge contract declares
one `apiKey` scheme whose `name` is `Authorization` — not `X-API-KEY` renamed
to look like Bearer.

This is the **Bearer-only** companion to:

→ [`../09-dual-scheme-gateway-auth-contract/`](../09-dual-scheme-gateway-auth-contract/) (OR list: X-API-KEY **or** Bearer)

App-layer shared-secret validation (constant-time compare) still belongs on the
service:

→ [`../../cloud-run-functions/02-vendor-api-key-auth-handler/`](../../cloud-run-functions/02-vendor-api-key-auth-handler/)

Do not confuse with:

- Pattern 01 / 03 — query `key` or header `X-API-Key` only
- Pattern 05 — API & Services key restriction (platform credential lifecycle)
- Pattern 14 — dual-scheme OR contract + misnaming pitfall gate

## Why this pattern

Production OpenAPI often grows this footgun when a team "adds Bearer support":

```yaml
securityDefinitions:
  Bearer:
    type: apiKey
    name: X-API-KEY   # schema says Bearer, header is X-API-KEY
    in: header
```

CX SDKs send `Authorization: Bearer …`. Gateway docs and codegen disagree.
Pattern 14 documents both headers. This folder documents the case where the
product decision is **Bearer only**, mapped correctly, with a deploy gate that
fails if Authorization mapping is lost or an X-API-KEY scheme sneaks back in.

## File index

| File | Purpose |
|------|---------|
| `openapi.yaml` | Sanitized Swagger 2.0: Cloud Run path backend + BearerToken only |
| `check-bearer-contract.sh` | Fails on wrong Authorization mapping / dual-scheme drift / pitfall |
| `deploy.sh` | Example API Gateway deploy (placeholders); runs the contract check first |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path and failure modes |
| `README.md` | This overview |

## Routes covered

| Path | Backend | Auth at edge |
|------|---------|--------------|
| `/getUsers` | `https://BACKEND_URL/getUsers` (h2) | `BearerToken` only |

## Sanitization notes

Derived from:

- `dags/horeca_digital/cloud_functions/prd/medallia.yml`

Removed or replaced:

- Product / company / contact email / internal license branding
- Real Cloud Run hostname and numeric project id → `BACKEND_URL`
- Example PII-looking values → `ACCOUNT_ID`, `user@example.com`, `+10000000000`
- Scheme renamed from source `Bearer` → `BearerToken` (same Authorization
  mapping; clearer next to dual-scheme `BearerToken` in pattern 14)
- Kept `protocol: h2` and path suffix on `x-google-backend.address`

No API keys or OAuth tokens were present as secret material in the source YAML;
none are included here.

## Quick start

1. Edit `openapi.yaml`: set `x-google-backend.address` to your Cloud Run URL +
   `/getUsers`. Keep `BearerToken` → `Authorization`.
2. Run the contract gate:

```bash
bash check-bearer-contract.sh
```

3. Deploy API config + gateway (see `deploy.sh`). New OpenAPI revision = new
   config id.
4. Grant the gateway SA `roles/run.invoker` on the Cloud Run service. Prefer
   `--no-allow-unauthenticated` on the service.
5. Smoke:

```bash
curl -sS -H "Authorization: Bearer YOUR_API_KEY" \
  "https://GATEWAY_HOST/getUsers?establishment_id=EST_ID"
```

Expect edge **401** without the Authorization header. Clients that only send
`X-API-KEY` belong on the dual-scheme pattern, not this one.

## Related patterns

- Dual-scheme gateway auth (Bearer **or** API key) → [`../09-dual-scheme-gateway-auth-contract/`](../09-dual-scheme-gateway-auth-contract/)
- Vendor API key auth handler → [`../../cloud-run-functions/02-vendor-api-key-auth-handler/`](../../cloud-run-functions/02-vendor-api-key-auth-handler/)
- Restricted API key (API & Services) → [`../../api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)
- Dev/prd gateway twins → [`../06-dev-prd-gateway-twins/`](../06-dev-prd-gateway-twins/)
