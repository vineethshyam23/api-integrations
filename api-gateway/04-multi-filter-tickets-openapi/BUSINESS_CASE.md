# Business case: multi-filter helpdesk tickets OpenAPI

## Problem

Support and analytics consumers need a stable HTTPS way to pull helpdesk tickets for a single country scope, keyed by different identity shapes: establishment id, a metro+store pair, or a metro account identifier. Exposing the Cloud Run URL directly either forces every client onto IAM tokens or leaves the service broader than you want. An OpenAPI gateway contract makes the filter rules reviewable and keeps credentials at the edge.

## Constraints that mattered

- `metroId` and `storeId` are a **pair**. One without the other is invalid — OpenAPI can document both as optional, but the backend must enforce the combination (400).
- Callers are often partner tools and internal dashboards, not browser SPAs — header `X-API-Key` stays simpler than OIDC for those clients.
- Backend is Cloud Run; warehouse reads use BigQuery. Query values must never be string-interpolated into SQL.
- Country scope is fixed for this extract surface (env-configured). Do not open a free-form country filter on the public contract.
- Offset/limit is enough for this lookup shape; a `has_next` pagination envelope is a different teaching pattern (see pattern 04).

## Decision

One **API Gateway OpenAPI config** with a single `/tickets` path, API-key protected, `x-google-backend` pointing at Cloud Run. Ship a sanitized companion handler that:

1. Validates the metro/store pair and offset/limit bounds.
2. Builds a parameterized BigQuery job (`@params`) instead of f-string WHERE values.
3. Returns `{records, count}` or structured 4xx/5xx JSON.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| Multiple optional filters on one path | One hostname / one key for several lookup styles | Spec + handler must stay aligned on which combos are legal |
| Paired metro+store in app code | Correct 400 semantics | OpenAPI alone cannot express "both or neither" |
| Parameterized SQL | Safe against injection from query strings | Slightly more boilerplate than naive string build |
| Header API key | Cleaner access logs than `?key=` | Every client must send `X-API-Key` |
| Fixed country via env | Smaller attack / scan surface | Separate gateway or env for another country |

## Distinct from patterns 01–04

- 01: single required account id lookup over Cloud Functions.
- 03: multi-route dashboard (establishment / visits / orders) over Cloud Functions.
- 04: analytics extract with page/limit envelopes and nested vs flat payloads over Cloud Run.
- This pattern: **one route**, multiple filter shapes, **paired compound key**, companion handler with parameterized BQ — Cloud Run + gateway.

## What we did not do here

- Apigee products / KVMs — no notes available in Cloud; do not invent.
- Shipping a second country as a query param — keep scope env-bound.
- Claiming ticket volume or latency numbers — measure in your project.
