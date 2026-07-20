# Business case: HTTP Cloud Function behind API Gateway

## Problem

API Gateway OpenAPI gives you a contract and edge auth. Without a disciplined backend handler, teams still leak function URLs to clients, treat the function as "public with a key on the gateway only", and lose request context when the gateway rewrites paths. Debugging then becomes "why did every request hit the default route?"

This pattern is the backend half of the gateway + function shape: one HTTP entry point that can serve multiple OpenAPI paths, log enough to operate, and stay private to the gateway via IAM.

## Constraints that mattered

- Callers authenticate at the gateway (API key). The function should not be world-invokable.
- One deployed function often backs several OpenAPI paths; Gen2 / Cloud Run may not preserve the public path on `request.path`.
- Analytics-style handlers query BigQuery — cold starts and query latency need structured logs, not print debugging.
- Dev and prod differ by `PROJECT_ID` and invoker service accounts; those stay in env / deploy flags.

## Decision

Ship a single **`lookup` HTTP entry point** that:

1. Resolves the intended route from forwarded-path headers (and conservative query heuristics).
2. Emits JSON log lines with severity + route (no API keys, no full header dumps).
3. Runs BigQuery with **query parameters**, not f-string filters.
4. Is deployed with `--no-allow-unauthenticated` and invoker binding for the gateway SA.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| One function, many paths | Fewer deploys; shared pagination / error shape | Routing logic must be explicit |
| IAM on function + API key on gateway | Defense in depth | Two places to misconfigure (403 vs 403) |
| Parameterized SQL | Safe filters; clearer plans | Slightly more boilerplate than string format |
| Gen2 / Cloud Run | Better concurrency and IAM model | Need both functions + run invoker bindings in some projects |
| CORS from env | Dashboard origins stay configurable | Easy to leave `*` in prod if nobody checks |

## What we did not do here

- Full OpenAPI for these routes — that is a separate `api-gateway/` pattern (multi-route dashboard).
- Apigee policies / KVM — wrong layer for a single analytics lookup service.
- Claiming query cost savings — measure slot usage in your project.
