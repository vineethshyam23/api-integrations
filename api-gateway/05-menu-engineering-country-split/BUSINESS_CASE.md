# Business case: menu-engineering country-split OpenAPI

## Problem

Menu engineering consumers need sold-item rows for one establishment, but the warehouse keeps country-scoped fact tables (DE vs FR, and more later). Publishing one URL per country multiplies keys, gateways, and client config. Better: one gateway path, one API key, and a small `country` enum that selects the table behind the handler.

## Constraints that mattered

- Country is a **closed enum** on the public contract (`de` / `fr`), not a free-form string that becomes a table name.
- Table ids live in env / Secret Manager. Callers never supply dataset or table names.
- Establishment id is required; date window and offset/limit are optional with sane caps.
- Dates must match what BigQuery DATE filters expect. Source OpenAPI said DD-MM-YYYY while the handler defaults were ISO — that mismatch is a production footgun; this pattern standardizes on YYYY-MM-DD.
- Query values must be parameterized. Source used f-string interpolation into WHERE — rewrite during sanitization.
- Offset belongs in SQL (`OFFSET`/`LIMIT`), not as a Python slice after already limiting the query result.

## Decision

One **API Gateway OpenAPI config** with a single `/menu-pos` path, header `X-API-Key`, Cloud Function backend. Ship a companion handler that:

1. Validates country against an allowlist map.
2. Resolves `country` → table id from env defaults.
3. Runs a parameterized join (sold items ↔ establishment license map).
4. Returns `{records, count}` or structured 4xx/5xx JSON.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| Country enum on one path | One hostname / one key for multi-country POS | Handler must keep enum and table map aligned |
| Env table map | Add a country without changing the public path name | Deploy-time config discipline across envs |
| ISO dates in OpenAPI + handler | Matches BQ DATE; fewer silent empty windows | Clients that already send DD-MM-YYYY must migrate |
| Parameterized SQL | Safe against injection from query strings | Slightly more boilerplate |
| Unknown country → 400 | Fail closed | Source defaulted unknown values to DE — convenient but wrong for auditability |

## Distinct from patterns 03 and 09

- 03: multi-route dashboard (several paths, per-route backends) — not a country table switch.
- 09: multi-filter tickets with paired metro+store on one Cloud Run path — filter combinatorics, not country-scoped facts.
- This pattern: **one route**, **country enum → table map**, date window + paging, Cloud Function + gateway.

## What we did not do here

- Apigee products / KVMs — no notes available in Cloud; do not invent.
- Inventing additional countries beyond the source enum.
- Claiming latency or row-volume savings — measure in your project.
