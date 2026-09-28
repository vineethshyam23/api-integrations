# Business case: Multi-route panel dashboard gateway twins

## Problem

A panel dashboard gateway is rarely one backend. Establishment profile, visits, orders, reservations, and POS KPIs usually ship as separate Cloud Functions so teams can deploy POS without touching visits. Once you keep DEV and PRD OpenAPI twins, the failure mode shifts: not "did we forget security on the only path?" but "did someone leave `/v1/getVisits` pointed at the PRD function while the other four routes are correctly in DEV?" Clients then see a dashboard that is half correct and half production data — harder to spot than a clean 403.

## Constraints that mattered

- Public contract (paths, operationIds, query params, security scheme, response property types) must match across envs.
- **Every** path's `x-google-backend.address` must differ between twins — checking only the first backend is insufficient.
- Region mix is a real production detail: PRD may run establishment/POS in one region and the rest in another; DEV may consolidate. The gate must allow that and still fail on identical URLs.
- Expanding the surface (adding `/v3/getPOS`) must land in **both** twins in the same change set. A PRD-only expansion is contract drift that pattern 03's single-file OpenAPI cannot teach.
- Each gateway SA needs invoker on all backends for that env. One missing grant looks like a flaky KPI widget, not a gateway outage.
- Config ids are immutable — new OpenAPI revision means a new config id per env.

## Decision

Ship **paired multi-route OpenAPI files** plus:

1. A `check-twins.sh` that extends the pattern 11 checks with **pairwise backend inequality**, backend-count == path-count, and duplicate-backend detection within an env.
2. An env-aware `deploy.sh` that runs the gate first and uses separate API / gateway ids per env.
3. Explicit documentation that this twin pair stops at `/v2/getPOS` while a sibling expanded OpenAPI may already include `/v3` — twin lag is a managed decision, not an accident.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| Five routes in the twin pair | Matches how panel gateways are operated | Larger review surface than pattern 11 |
| Pairwise backend checks | Catches single-route env leaks | Slightly more script logic |
| Allow region mix | Reflects real PRD layout | Reviewers must not treat region diffs as failures |
| Keep `/v3/getPOS` out of this pair | Forces "expand both twins" discipline | Readers must cross-link pattern 03 for the v3 shape |
| Separate invoker grants per function | Blast radius limited per KPI domain | Five IAM bindings to maintain per env |

## Distinct from earlier patterns

- 03: one multi-route OpenAPI (teaching routes + versioning). No twin files, no pairwise backend gate.
- 11: twin discipline for a **single** path. Gate only needs "backends differ" once.
- 15: handler-side SQL OFFSET/LIMIT for POS v3 payloads — runtime, not gateway twins.
- This pattern: **multi-route twins** + pairwise backend inequality + region-mix / twin-lag notes.

## What we did not do here

- Apigee products / KVMs — no `Documents/API` notes in Cloud; do not invent.
- Shipping the `/v3/getPOS` expansion into these twins — that belongs in a coordinated twin update, or stays documented via pattern 03.
- Claiming incident-count reductions — measure that in your own rollout.
