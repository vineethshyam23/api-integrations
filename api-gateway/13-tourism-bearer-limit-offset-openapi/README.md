# Pattern 21: Tourism Bearer limit/offset OpenAPI

Google Cloud API Gateway OpenAPI for a **single-route partner catalog** where
clients send `Authorization: Bearer <token>` and page with `limit` / `offset`.
The response envelope is `{ records, pagination: { total, limit, offset } }`.

This is the **thin Bearer + limit/offset** companion to:

→ [`../08-inbound-dual-route-daily-ntile/`](../08-inbound-dual-route-daily-ntile/)
(ApiKeyAuth, dual-route, `pageSize` / `pageNumber`)

→ [`../11-bearer-only-cloudrun-gateway-auth/`](../11-bearer-only-cloudrun-gateway-auth/)
(Bearer-only, single-id lookup, **no** pagination)

App-layer shared-secret validation still belongs on the service:

→ [`../../cloud-run-functions/02-vendor-api-key-auth-handler/`](../../cloud-run-functions/02-vendor-api-key-auth-handler/)

Do not confuse with:

- Pattern 13 — dual-route tourism feed; ApiKeyAuth; page-based paging
- Pattern 14 — dual-scheme OR contract (X-API-KEY **or** Bearer)
- Pattern 18 — Bearer-only CX `/getUsers` without limit/offset
- Pattern 01 — single-route establishment lookup by id (API key header)

## Why this pattern

Production catalogs often ship a thin Cloud Run OpenAPI first (Bearer +
limit/offset), then grow into dual-route ApiKeyAuth revisions. If the thin YAML
is overwritten in place, partner SDKs that still send Authorization and
offset-based loops break without an OpenAPI changelog. Keeping the thin
contract as its own folder documents the dialect split and gives deploy a
regression gate for both auth mapping and paging params.

## File index

| File | Purpose |
|------|---------|
| `openapi.yaml` | Sanitized Swagger 2.0: Cloud Run path backend + BearerToken + limit/offset |
| `check-bearer-limit-offset-contract.sh` | Fails on wrong Authorization mapping / ApiKeyAuth drift / pageSize regression |
| `deploy.sh` | Example API Gateway deploy (placeholders); runs the contract check first |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path and failure modes |
| `README.md` | This overview |

## Routes covered

| Path | Backend | Auth at edge | Paging |
|------|---------|--------------|--------|
| `/catalog` | `https://BACKEND_URL/catalog` (h2) | `BearerToken` only | `limit` / `offset` |

## Sanitization notes

Derived from:

- `dags/horeca_digital/cloud_functions/prd/tourismNrw.yml`

Removed or replaced:

- Product / regional tourism / company branding, contact email, internal license
- Real Cloud Run hostname and numeric project id → `BACKEND_URL`
- Path `/getTourismNrwData` → `/catalog`
- Scheme renamed from source `Bearer` → `BearerToken` (same Authorization
  mapping; clearer next to pattern 14 / 18)
- Added `protocol: h2` on `x-google-backend` (Cloud Run path backend practice)
- Column `google_places_id` → `places_legacy_id`; partner-specific id →
  `partner_ref_id`
- Contact email / phone / mobilephone fields dropped from the public sample
- Example PII-looking values → placeholders (`EST_ID`, `CITY`, `example.com`)
- Kept limit/offset defaults and `{records, pagination}` envelope shape

No API keys or OAuth tokens were present as secret material in the source YAML;
none are included here. Handler SQL lives in pattern 13 (`tourismnrw_api.py`
lineage) — this folder documents the thin gateway contract only.

## Quick start

1. Edit `openapi.yaml`: set `x-google-backend.address` to your Cloud Run URL +
   `/catalog`. Keep `BearerToken` → `Authorization` and `limit` / `offset`.
2. Run the contract gate:

```bash
bash check-bearer-limit-offset-contract.sh
```

3. Deploy API config + gateway (see `deploy.sh`). New OpenAPI revision = new
   config id.
4. Grant the gateway SA `roles/run.invoker` on the Cloud Run service. Prefer
   `--no-allow-unauthenticated` on the service. Cap `limit` in the handler.
5. Smoke:

```bash
curl -sS -H "Authorization: Bearer YOUR_API_KEY" \
  "https://GATEWAY_HOST/catalog?limit=100&offset=0"
```

Expect edge **401** without the Authorization header. Clients that only send
`X-API-KEY` or `pageSize` / `pageNumber` belong on pattern 13 / 14, not this one.

## Related patterns

- Inbound dual-route daily NTILE (ApiKeyAuth) → [`../08-inbound-dual-route-daily-ntile/`](../08-inbound-dual-route-daily-ntile/)
- Bearer-only CX user lookup → [`../11-bearer-only-cloudrun-gateway-auth/`](../11-bearer-only-cloudrun-gateway-auth/)
- Dual-scheme gateway auth → [`../09-dual-scheme-gateway-auth-contract/`](../09-dual-scheme-gateway-auth-contract/)
- Vendor API key auth handler → [`../../cloud-run-functions/02-vendor-api-key-auth-handler/`](../../cloud-run-functions/02-vendor-api-key-auth-handler/)
- Restricted API key (API & Services) → [`../../api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)
