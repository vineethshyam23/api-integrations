# Business case: GA dual-path analytics handler

## Problem

An analytics extraction surface exposes two HTTP contracts on one hostname:

1. `/daily-visits` — flat rows for simple ETL / beginner consumers
2. `/ga-sessions-data` — nested session objects for advanced flattening practice

API Gateway OpenAPI can declare both paths (see `api-gateway/03-...`). Deploying two backends doubles ops for low traffic. Deploying **one** backend means the function must know which contract the client asked for — and API Gateway does not always leave that path intact on `request.path`.

A naive handler that only inspects `request.path` mis-routes when:

- Both OpenAPI backends point at the same Cloud Run URI without path suffixes
- The platform strips the gateway path and only forwards original URI headers
- Callers hit the function URL directly during smoke tests

This pattern is the **backend that matches the dual-route OpenAPI**: multi-header path recovery, parameter fallbacks, and two parameterized BigQuery shapes.

## Constraints that mattered

- Gateway OpenAPI already documents page/limit envelopes and flat vs nested schemas.
- Billing project for query jobs may differ from the public dataset project (`bigquery-public-data`).
- Device category is a closed enum; date shards are `YYYYMMDD` table suffixes.
- Edge auth stays at the gateway (API key). Function deploys `--no-allow-unauthenticated`.
- Exception detail helps in staging; gate it with `EXPOSE_ERROR_DETAIL`.
- Debug endpoints that echo all headers are useful once and dangerous forever — omit them from the shipped pattern.

## Decision

Ship a single **`lookup` HTTP entry point** that:

1. Handles CORS preflight; rejects non-GET with **403**.
2. Validates `page` / `limit` (hard cap 500).
3. Collects path hints from `request.path`, `X-Forwarded-Path`, `X-Envoy-Original-Path`, `X-Original-URI`, and URL.
4. Resolves route with path priority, then query-param heuristics, then GA default.
5. Runs parameterized SQL for flat daily visits or nested GA sessions.
6. Returns `{records, pagination, filters_applied, metadata}` or **404** when empty.
7. Deploys with gateway SA invoker bindings only.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| One function, two routes | Single deploy, shared IAM / logging | Ambiguous routing if path + params conflict — log and default to GA |
| Multi-header path scan | Survives gateway rewrite differences | Slightly more logging noise; must not log secrets from headers |
| Param fallback when path missing | Smoke tests without gateway still work | Overlapping params can pick the wrong route — document the priority |
| Parameterized `@filters` | Removes quote-escaping / injection footguns from the original | Slightly more verbose than f-string SQL |
| Public sample defaults | No private warehouse required to exercise the pattern | Production must override tables before pointing real clients here |
| Keep GA as default | Matches original backward-compat behavior | Mis-routed daily-visits calls look like empty GA sessions — watch route logs |

## Distinct from nearby patterns

| Pattern | What it covers | Why this is different |
|---------|----------------|------------------------|
| `api-gateway/03-...` | Dual-route OpenAPI + Cloud Run path backends | Gateway contract only — not the dual-path handler |
| `cloud-run-functions/01-...` | Generic HTTP handler behind gateway | Single route / payload shape |
| `cloud-run-functions/04-...` | `DEPLOY_ENV` table pick + country allowlist | Market-potential extract, not GA dual-path routing |
| `cloud-run-functions/05-...` | Establishment POS SQL OFFSET pushdown | Panel POS history, not analytics dual-route |

## What we did not do here

- Inventing Apigee KVM / product config — no Apigee artifacts under GitLab `cloud_functions`.
- Claiming interview-task / progressive-learning metrics — keep the engineering shape only.
- Shipping the original format-string SQL — parameterized queries are the production bar.
- Replacing the companion OpenAPI — keep `api-gateway/03-...` pointed at this backend URI.
