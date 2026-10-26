# Pattern 24: Mixed backend generation lint

Google Cloud API Gateway OpenAPI for a **four-route** panel dashboard where
every `x-google-backend` Cloud Function must share one naming family, one
separator style, and one generation suffix. Partial migrations — some routes
on `-gbq`, one still on a legacy name, visits pointing at a foreign
`lookup-*` function — look fine in review and break operability in production.

This is the **single-file** companion to twin backend discipline:

→ [`../10-multi-route-panel-gateway-twins/`](../10-multi-route-panel-gateway-twins/)
(compares DEV vs PRD; catches identical URLs across twins)

Do not confuse with:

- Pattern 03 / 16 — multi-route OpenAPI / twins that already ship aligned names
- Pattern 19 — path-security lint (auth wiring, not backend naming)
- Pattern 11 — twin contract parity across two files

## Why this pattern

A transitional panel OpenAPI in source kept four routes on one hostname while
the backends drifted:

| Path | Source-style backend shape | Problem |
|------|----------------------------|---------|
| `/getEstablishment` | `…/panel_establishment` | Legacy, no `-gbq` |
| `/getVisits` | `…/lookup-getvisits` | Foreign family + hyphen style |
| `/getOrders` | `…/panel_orders-gbq` | Migrated |
| `/getReservations` | `…/panel_reservations-gbq` | Migrated |

Clients see one API. On-call sees three naming conventions and two data-plane
generations. Invoker IAM checklists miss the foreign function. Rolling a
BigQuery rewrite "for the panel" silently leaves visits on the old path.

Pattern 16 catches DEV sharing a PRD URL. This folder catches **within-file**
generation drift when there is only one OpenAPI (or a PR that only edits one
env).

## File index

| File | Purpose |
|------|---------|
| `openapi.yaml` | Sanitized Swagger 2.0: four routes, aligned `panel-*-gbq` backends, header `X-API-KEY` |
| `fixtures/openapi.mixed-backends.yaml` | Negative fixture — mixed family / separator / `-gbq` (lint must fail) |
| `check-backend-generation.sh` | Fails on partial `-gbq`, separator drift, or family token drift |
| `deploy.sh` | Example API Gateway deploy; runs the lint first |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path and failure modes |
| `README.md` | This overview |

## Routes covered

| Path | Backend placeholder | Auth at edge |
|------|---------------------|--------------|
| `/getEstablishment` | `…/panel-establishment-gbq` | `api_key` (X-API-KEY) |
| `/getVisits` | `…/panel-visits-gbq` | `api_key` (X-API-KEY) |
| `/getOrders` | `…/panel-orders-gbq` | `api_key` (X-API-KEY) |
| `/getReservations` | `…/panel-reservations-gbq` | `api_key` (X-API-KEY) |

## Sanitization notes

Derived from:

- `dags/horeca_digital/cloud_functions/prd/hd-dish-panel-dashboard-new.yml`

Removed or replaced:

- Product / company / contact branding and CRM-specific field labels
- Real Cloud Function hostnames / project ids → `REGION-PROJECT_ID`
- Query-string API key (`name: key`, `in: query`) → header `X-API-KEY` in the
  aligned exemplar (fixture keeps query `key` to mirror the transitional source)
- Product feature flags renamed to generic `has_website` / `has_reservation` /
  `has_order`
- Backend names rewritten to placeholders that preserve the **engineering
  shape** (legacy vs `-gbq` vs foreign family) without live identifiers
- Negative fixture keeps the mixed shape for the lint demo

No API keys or OAuth tokens were present as secret material in the source YAML;
none are included here.

## Quick start

1. Edit `openapi.yaml`: set each `x-google-backend.address` to your function
   URLs. Keep one family (`panel-…`), one separator, and the same generation
   suffix on every route.
2. Run the gate:

```bash
bash check-backend-generation.sh
bash check-backend-generation.sh --self
# --self must FAIL the fixture, then OK openapi.yaml
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

## Related patterns

- Multi-route dashboard OpenAPI → [`../02-multi-route-dashboard-openapi/`](../02-multi-route-dashboard-openapi/)
- Multi-route panel dashboard twins → [`../10-multi-route-panel-gateway-twins/`](../10-multi-route-panel-gateway-twins/)
- Multi-route path-security lint → [`../12-multi-route-path-security-lint/`](../12-multi-route-path-security-lint/)
- Restricted API key (API & Services) → [`../../api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)
