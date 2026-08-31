# Business case: Env-scoped BigQuery pagination handler

## Problem

Partner and internal extract APIs often need the same HTTP surface in two GCP projects: a staging warehouse and a production warehouse. Teams that bake `project.dataset.table` into Python end up with:

1. Divergent forks of the same function, or last-minute edit-before-deploy mistakes.
2. Staging accidentally reading prod (or the reverse) when a copy-paste deploy misses a string.
3. 500 responses that dump warehouse errors to callers in production because someone left `str(exc)` in the JSON for debugging.

This pattern is the backend half of a country-filtered extract API: one codebase, env-driven table selection, parameterized pagination, and gated error detail.

## Constraints that mattered

- Callers filter by ISO country (`countryCode`) and page with `pageSize` / `pageNumber`.
- Allowed countries are a closed set — free-form country strings should fail at the edge of the handler, not deep in SQL.
- Dev and prod table defaults differ by project; ad-hoc backfills need a full-table override without code change.
- BigQuery filters must stay parameterized — country codes and pagination ints are untrusted query input.
- Exception detail helps operators in staging; it must not ship to partners in prod.
- One Gen2 / Cloud Run service backs a single path leaf that API Gateway addresses with `.../getMarketPotentialData`.

## Decision

Ship a single **`main` HTTP entry point** that:

1. Rejects non-GET (except CORS `OPTIONS`).
2. Requires `DEPLOY_ENV` ∈ `{dev, prod}` and resolves the default BQ table from it.
3. Honors optional `MARKET_POTENTIAL_BQ_TABLE` as a full `project.dataset.table` override.
4. Validates country against an allowlist, pages with a stable `{records, pagination}` envelope.
5. Returns exception `detail` / `exceptionType` only when `EXPOSE_ERROR_DETAIL` is truthy.
6. Deploys with `--no-allow-unauthenticated` and gateway SA invoker bindings.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| `DEPLOY_ENV` required at runtime | Hard fail if env unset — safer than silent wrong table | Deploy scripts must always set it; no "works on my laptop" default |
| Full-table override env | Backfills / shadow datasets without code change | Override typos still possible — log the resolved table every cold start |
| Parameterized `@country_code` / `@offset` | Avoids injection from query params | Slightly more verbose than f-string SQL |
| `pageNumber` starting at 1 + 404 past end | Matches sibling extract APIs partners already use | Clients must not treat 404 as "country unknown" only |
| Gated `EXPOSE_ERROR_DETAIL` | Staging debug without prod leakage | Easy to leave `true` on a prod service — review env in release checklist |
| CORS via env | Origin locked per environment | Mis-set origin breaks browser clients while curl still works |

## What we did not do here

- Application-layer shared-secret compare — see pattern 06 (`02-vendor-api-key-auth-handler`).
- Inventing Apigee KVM / product config — no Apigee artifacts under GitLab `cloud_functions`.
- Claiming latency or cost savings — measure cold starts and BQ bytes billed in your project.
- Multi-route marketing extract surfaces — ship those only when they add distinct gateway contracts.
