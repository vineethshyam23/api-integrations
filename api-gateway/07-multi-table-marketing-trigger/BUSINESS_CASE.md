# Business case: multi-table marketing-trigger OpenAPI

## Problem

Marketing automation platforms need fresh establishment / contact / product-usage signals from the warehouse. Those signals live in **separate tables** (contacts vs payments vs POS vs reservations …) but consumers want one authenticated front door, one paging contract, and a way to discover field mappings without reverse-engineering schemas.

Shipping six independent Cloud Run services + six gateways multiplies keys, IAM, and deploy ceremony. Letting callers pass a free-form table name is worse — they will invent identifiers and you will spend nights debugging 403s from BigQuery.

## Constraints that mattered

- One public hostname and one API key family for all trigger extracts.
- Paths are a **closed set** in OpenAPI and in the handler path map — not a `?table=` query param.
- Table ids come from env / Secret Manager per environment. Callers never supply project/dataset/table.
- Shared pagination: `pageSize` / `pageNumber`, max 10000, `{records, pagination}` envelope with `totalPages`.
- Date columns normalized to `YYYY-MM-DD` before JSON so the marketing platform does not see mixed GMT strings.
- Explicit column lists — never `SELECT *` on marketing extracts (schema drift and accidental PII).
- A metadata endpoint for source→destination field maps, grouped by source model.

## Decision

One **API Gateway OpenAPI config** with seven paths, header `X-API-KEY`, single Cloud Run backend. Ship a companion handler that:

1. Maps path → config key (`PATH_TO_CONFIG`).
2. Resolves table id from `TRIGGER_*_TABLE` env (placeholder defaults for local reading).
3. Runs shared `fetch_data_with_pagination` (parameterized LIMIT/OFFSET + COUNT).
4. Serves `/triggers/fields-metadata` as a model-keyed dict (no paging).

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| Multi-path, one backend | One deploy, one invoker binding, one key | OpenAPI path list and `PATH_TO_CONFIG` must stay aligned |
| Shared pagination helper | Caps / envelope / date formatting stay consistent | A bug in the helper hits every path |
| Env table map | Swap datasets per env without code forks | Deploy discipline; prefer secrets over `--set-env-vars` history |
| Fields-metadata endpoint | Partners sync mappings without schema scraping | Extra BQ table + IAM; empty map → 404 |
| Trimmed column lists in the sample | Safer public teaching artifact | Real deploys must expand columns to match production contracts |

## Distinct from patterns 02 / 03 / 08

- 02 / 03: multi-route **dashboard / analytics** OpenAPI — different response shapes and (often) per-route backends. Not a shared TABLE_CONFIGS + pagination helper for marketing triggers.
- 08: **single** env-scoped table with country filter — `DEPLOY_ENV` is the story. This pattern is many tables, one service, path-keyed config.
- This pattern: **path → table map**, shared paginator, plus fields-metadata.

## What we did not do here

- Apigee products / KVMs — no `Documents/API` notes in Cloud; do not invent.
- Shipping the full production contact column dump (PII-heavy) — keep representative fields.
- Claiming open/click rates or cost savings — measure in your project.
