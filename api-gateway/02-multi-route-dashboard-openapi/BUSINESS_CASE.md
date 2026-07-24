# Business case: Multi-route dashboard OpenAPI

## Problem

A partner or internal dashboard needs several related reads — establishment profile, visits, orders, reservations, POS KPIs — not one lookup. Shipping a separate gateway API per route multiplies keys, hostnames, and deploy rituals. Shipping one mega-function behind a single path forces every change through one backend and one release train.

## Constraints that mattered

- Callers already think in resource-shaped GETs (`getVisits`, `getOrders`), not a single GraphQL-style endpoint.
- Backends evolve at different speeds: POS schema changed while visits stayed stable → need path versioning (`/v2/getPOS` vs `/v3/getPOS`) without breaking the gateway hostname.
- Auth had to stay API-key simple for non-GCP clients; header `X-API-Key` preferred over query `key` for dashboards that hit browser/proxy logs.
- Some POS queries are heavier than profile lookups → per-route `deadline` on `x-google-backend` matters.

## Decision

One **API Gateway OpenAPI config** with **multiple paths**, each with its own `x-google-backend.address`:

1. Gateway validates one API key for the whole surface.
2. Each path proxies to a dedicated Cloud Function (or versioned function).
3. OpenAPI remains the deployable contract and the review artifact.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| Multi-path, multi-backend | Independent deploys per domain | Gateway SA needs invoker on every function |
| Path versioning (`/v2`, `/v3`) | Migrate clients without dual gateways | Spec grows; retire old paths with discipline |
| Header API key | Cleaner than `?key=` in access logs | Older clients may still expect query keys |
| Shared pagination params | Predictable client UX | Copy-paste in Swagger 2.0 (no component reuse) |
| One gateway hostname | Stable integration contract | Blast radius if the whole config mis-deploys |

## What we did not do here

- Collapse all routes into one Cloud Function — possible, but loses independent scaling and release cadence.
- Apigee products / KVMs — useful later for partner packaging; not required for this gateway shape.
- Claiming dashboard latency or adoption numbers — measure in your project.
