# Business case: inbound dual-route daily NTILE pagination

## Problem

A destination / tourism partner needs a warehouse-backed establishment feed with two consumption modes:

1. **Full catalog** — baseline sync, paginate until done, treat empty as end-of-data.
2. **Daily slice** — paced incremental so the partner does not pull the whole table every night.

Those modes share the same schema and auth front door, but they do **not** share empty-page semantics. Quiet days on the daily path are normal. Empty pages on the full catalog path usually mean misconfiguration or end-of-data.

## Constraints that mattered

- One public hostname and one API key family for both modes.
- Paths are a closed set in OpenAPI — not a free-form `?mode=` that clients invent.
- Table ids come from env / Secret Manager. Callers never name project/dataset/table.
- Daily distribution must be deterministic and cover the month without a separate orchestration DAG in the API layer: NTILE over a stable id keyed by day-of-month.
- Soft empty on daily (200 + message) so partner schedulers do not page on-call for first-of-month or empty buckets.
- Hard 404 on full catalog empty pages so baseline jobs stop cleanly.
- Explicit column lists — no `SELECT *`, and no contact email / phone in the public teaching sample.

## Decision

One **API Gateway OpenAPI config** with two paths, header `X-API-KEY`, single Cloud Run backend. Ship a companion handler that:

1. Routes `/establishments` vs `/establishments/daily`.
2. Resolves table ids from `ESTABLISHMENTS_TABLE` / `ESTABLISHMENTS_DAILY_TABLE`.
3. Runs parameterized `LIMIT/OFFSET` + `COUNT` for the full path.
4. Runs parameterized `NTILE(@bucket_count) … = @bucket_index` for the daily path, with first-of-month short-circuit to soft empty.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| Two paths, one backend | One deploy, one invoker binding, one key | OpenAPI paths and handler route map must stay aligned |
| NTILE by day-of-month | No external scheduler state in the API | Bucket sizes uneven near month boundaries; first day soft-empty by design |
| Soft empty on daily | Quiet days are not outages | Clients must treat `message` + empty `records` as success |
| Hard 404 on full empty | Clear stop condition for baseline jobs | Page-past-end looks the same as empty table — check `total` on a known good page |
| Env table map | Swap datasets per env without code forks | Deploy discipline; prefer secrets over long-lived env history |

## Distinct from patterns 07 / 12 / 03

- **07**: outbound OIDC HTTP client pulling a remote API. This pattern is **inbound** BigQuery behind the gateway.
- **12**: many product tables, path→`TABLE_CONFIGS`, fields-metadata. This pattern is **one schema, two extract modes**, with calendar NTILE as the differentiator.
- **03**: multi-route dashboard / analytics OpenAPI — different response shapes and often per-route backends.

## What we did not do here

- Apigee products / KVMs — no `Documents/API` notes in Cloud; do not invent.
- Shipping contact email / phone columns in the public sample.
- Claiming partner SLA or cost savings — measure in your project.
- Rewriting NTILE into a date-partitioned incremental (valid alternative if the daily table is already date-keyed).
