# Pattern 14: Dual-scheme gateway auth contract (Bearer + API key)

Google Cloud API Gateway OpenAPI for a **vendor lookup** API where clients send either `X-API-KEY` or `Authorization: Bearer <token>`. The edge contract declares both as alternative `apiKey` schemes so Swagger UI, codegen, and API Gateway stay aligned with an app-layer handler that already accepts either header.

This is the **gateway half** of the Medallia-style vendor integration. The handler (constant-time compare, path routing, BQ) ships as:

→ [`../../cloud-run-functions/02-vendor-api-key-auth-handler/`](../../cloud-run-functions/02-vendor-api-key-auth-handler/)

Do not confuse with:

- Pattern 01 / 03 — query `key` or header `X-API-Key` only, no dual-scheme docs
- Pattern 05 — API & Services key restriction (platform credential), not OpenAPI scheme design
- Pattern 06 (Cloud Functions numbering) — app-layer `hmac.compare_digest` only; its `openapi.example.yaml` is a thin single-scheme stub

## Why this pattern

Production OpenAPI often grows a footgun:

```yaml
securityDefinitions:
  Bearer:
    type: apiKey
    name: X-API-KEY   # name says Bearer, header is X-API-KEY
    in: header
```

Clients following the scheme name send `Authorization: Bearer …`. Clients following the `name` field send `X-API-KEY`. Support tickets follow. The backend may accept both (pattern 06 does); the gateway document should say so explicitly with **two** schemes and OR security lists — not one misnamed scheme.

## File index

| File | Purpose |
|------|---------|
| `openapi.yaml` | Sanitized Swagger 2.0: three Cloud Run path backends + dual schemes + schemas |
| `check-auth-contract.sh` | Fails on missing dual schemes or Bearer→X-API-KEY naming pitfall |
| `deploy.sh` | Example API Gateway deploy (placeholders); runs the contract check first |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path and failure modes |
| `README.md` | This overview |

## Routes covered

| Path | Backend | Auth at edge |
|------|---------|--------------|
| `/getUser` | `https://BACKEND_URL/getUser` (h2) | `ApiKeyHeader` **or** `BearerToken` |
| `/getPosUser` | `https://BACKEND_URL/getPosUser` (h2) | same |
| `/getEstablishments` | `https://BACKEND_URL/getEstablishments` (h2) | same |

Swagger 2.0 OR semantics: `security` is a list of alternative requirement objects.

## Sanitization notes

Derived from:

- `dags/horeca_digital/cloud_functions/prd/medalia_integrated.yml`
- Companion handler already shipped from `prd/medalia_api_integrated.py` (pattern 06)

Removed or replaced:

- Product / company / contact email / internal license branding
- Live Cloud Run host + numeric project id → `BACKEND_URL` / `PROJECT_ID`
- Real-looking person names, emails, phones, UUIDs in schema examples → placeholders
- Misnamed single `Bearer`→`X-API-KEY` scheme → explicit `ApiKeyHeader` + `BearerToken`
- No API key material, OAuth tokens, or `apikey=` query values

Handler source is not re-copied here — reuse pattern 06 `main.py` / `deploy.sh`.

## Quick start

1. Deploy / point the Cloud Run handler from pattern 06; set `VENDOR_API_KEY` via Secret Manager.
2. Edit `openapi.yaml` so each `x-google-backend.address` uses your Cloud Run host + path.
3. Run `./check-auth-contract.sh` then `./deploy.sh` (placeholders).
4. Grant gateway SA `roles/run.invoker` on the service; restrict an API & Services key to this API.
5. Smoke both header shapes:

```bash
curl -sS -H "X-API-KEY: YOUR_API_KEY" \
  "https://GATEWAY_HOST/getUser?account_id=ACCOUNT_ID"

curl -sS -H "Authorization: Bearer YOUR_API_KEY" \
  "https://GATEWAY_HOST/getEstablishments?establishment_id=EST_ID"
```

Missing/wrong secret → **401** from the handler. Unauthenticated invoke against Cloud Run → **403** from IAM when public invoker is denied.

## Related next patterns

- Apigee proxy / product / KVM (placeholders only) → `apigee/01-...` when notes exist
- Remaining unused OpenAPI twin / panel variant — only if still unique vs patterns 03 / 11
