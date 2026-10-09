# Pattern 19: Multi-route path-security lint

Google Cloud API Gateway OpenAPI for a **four-route** panel dashboard where
every operation must attach a path-level `security:` block. Declaring
`securityDefinitions` alone does not enforce auth — API Gateway only applies
schemes that operations reference.

This is the **single-file** companion to twin security discipline:

→ [`../06-dev-prd-gateway-twins/`](../06-dev-prd-gateway-twins/) (compares DEV vs PRD; catches security drop between twins)

Do not confuse with:

- Pattern 03 / 16 — multi-route OpenAPI / twins that already ship with path security
- Pattern 11 — twin contract parity (paths, schemas, security counts across two files)
- Pattern 14 / 18 — Bearer / dual-scheme auth mapping

## Why this pattern

An early DEV panel OpenAPI in source declared `securityDefinitions` (query
`key`) and four routes — establishment, visits, orders, reservations — with
**no** path-level `security:` on any operation. Swagger UI shows a scheme.
Engineers assume the gateway requires a key. Curl without a key returns 200.
That is worse than an openly unauthenticated API: the config *looks* secured.

Pattern 11 catches the same footgun when a DEV twin drops security while PRD
keeps it. This folder covers the case where there is **only one file** (or the
first env ships alone) and you need a deploy gate before a twin exists.

## File index

| File | Purpose |
|------|---------|
| `openapi.yaml` | Sanitized Swagger 2.0: four routes, path `security:` on every operation, header `X-API-KEY` |
| `fixtures/openapi.missing-path-security.yaml` | Negative fixture — schemes declared, no path security (lint must fail) |
| `check-path-security.sh` | Fails if any HTTP operation lacks path-level `security:` when definitions exist |
| `deploy.sh` | Example API Gateway deploy; runs the lint first |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path and failure modes |
| `README.md` | This overview |

## Routes covered

| Path | Backend placeholder | Auth at edge |
|------|---------------------|--------------|
| `/getEstablishment` | `…/panel-establishment-dev-gbq` | `api_key` (X-API-KEY) |
| `/getVisits` | `…/panel-visits-dev-gbq` | `api_key` (X-API-KEY) |
| `/getOrders` | `…/panel-orders-dev-gbq` | `api_key` (X-API-KEY) |
| `/getReservations` | `…/panel-reservations-dev-gbq` | `api_key` (X-API-KEY) |

## Sanitization notes

Derived from:

- `dags/horeca_digital/cloud_functions/dev/hd-dish-panel-dashboard-dev-gbq.yml`

Removed or replaced:

- Product / company / contact branding and Salesforce-specific field labels
- Real Cloud Function hostnames / project ids → `REGION-PROJECT_ID`
- Query-string API key (`name: key`, `in: query`) → header `X-API-KEY` (query keys leak via access logs and Referer)
- Product feature flags renamed to generic `has_website` / `has_reservation` / `has_order`
- Added path-level `security:` on every operation (the source file lacked these)
- Negative fixture preserves the missing-security shape for the lint demo

No API keys or OAuth tokens were present as secret material in the source YAML;
none are included here.

## Quick start

1. Edit `openapi.yaml`: set each `x-google-backend.address` to your function URLs.
   Keep path-level `security:` on every operation.
2. Run the gate (expect OK on the fixed file, FAIL on the fixture):

```bash
bash check-path-security.sh
bash check-path-security.sh fixtures/openapi.missing-path-security.yaml
# second command should exit non-zero
```

3. Deploy API config + gateway (see `deploy.sh`). New OpenAPI revision = new
   config id.
4. Grant the gateway SA invoker on **each** backend function. Prefer
   `--no-allow-unauthenticated` on the functions.
5. Smoke:

```bash
curl -sS -H "X-API-KEY: YOUR_API_KEY" \
  "https://GATEWAY_HOST/getEstablishment?establishmentId=EST_ID"
```

Expect edge **401** without the header on every route, not only the first one
you remembered to secure.

## Related patterns

- Dev/prd gateway twins → [`../06-dev-prd-gateway-twins/`](../06-dev-prd-gateway-twins/)
- Multi-route panel dashboard twins → [`../10-multi-route-panel-gateway-twins/`](../10-multi-route-panel-gateway-twins/)
- Multi-route dashboard OpenAPI → [`../02-multi-route-dashboard-openapi/`](../02-multi-route-dashboard-openapi/)
- Restricted API key (API & Services) → [`../../api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)
