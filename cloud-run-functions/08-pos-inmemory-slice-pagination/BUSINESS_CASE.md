# Business case: POS KPI in-memory slice pagination (legacy / anti-pattern)

## Problem

Early panel POS backends needed establishment-scoped KPI rows behind API Gateway. The first working handler (v2) did three things that looked fine in a demo and failed under real history:

1. Interpolated `establishment_id` and `LIMIT` into SQL with `.format(...)`.
2. Applied **only** `LIMIT` in BigQuery, then sliced `offset:offset+limit` in Python.
3. Defaulted `limit` to **9999** so page-2+ requests still had enough rows in memory to slice.

That combination bills warehouse bytes for rows the client never sees, blows Cloud Function memory as histories grow, and still returns false **404** when `offset >= LIMIT` (common when clients pass a small `limit` and a non-zero `offset`). Date query params were accepted for "future filtering" but left unused.

Pattern 15 is the production rewrite (SQL `LIMIT`/`OFFSET`, parameterized filters, hard cap). This pattern is the **museum baseline**: sanitize the real v2 shape so reviewers, migrants, and CI smell gates share the same reference.

## Constraints that mattered

- `/v2/getPOS` was already live on the multi-route dashboard OpenAPI — you cannot delete the path on day one.
- Response stayed a `{records}` object in the function even when some gateway schemas typed a bare array (align schemas when you bump the API config).
- Edge auth stayed at the gateway (`X-API-Key`). Backend stays `--no-allow-unauthenticated`.
- Migration means keep v2 address pointed here until clients finish moving to `/v3/getPOS` / pattern 15.

## Decision

Ship a sanitized **legacy** `lookup` handler that deliberately preserves the anti-patterns, plus:

1. Companion OpenAPI for `/v2/getPOS` documenting unused dates and the huge default limit.
2. A `check-inmemory-slice-smell.sh` gate you can point at *other* handlers so the smell cannot quietly return.
3. Docs that map each smell to the pattern 15 fix — no invented savings claims.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| Keep anti-patterns in code | Honest teaching artifact; CI has a positive control (`--self`) | Someone may copy without reading the banner |
| Museum folder vs only prose in pattern 15 | Concrete greppable smells + OpenAPI contract | Extra pattern to maintain until `/v2` is retired |
| Smell script (multi-signal) | Low false-positive rate vs single grep | May miss clever variants — treat as a gate, not a proof |
| Leave double-`jsonify` defect | Matches a real production footgun on the 404 path | Demos of the error path look broken — intentional |

## Distinct from nearby patterns

| Pattern | What it covers | Why this is different |
|---------|----------------|------------------------|
| `cloud-run-functions/05-...` (pattern 15) | SQL LIMIT/OFFSET pushdown + parameterized filters | Production rewrite — this folder is the before |
| `api-gateway/02-...` | Multi-route OpenAPI including `/v2` vs `/v3` getPOS | Gateway routing only — not the handler body |
| `cloud-run-functions/04-...` | Env-scoped country extract paging | Different product surface; not POS KPI v2 |

## What we did not do here

- Inventing Apigee — no Apigee artifacts under GitLab `cloud_functions`.
- Claiming byte/cost savings — measure billed bytes before/after in your project.
- Shipping POS establishment single-route OpenAPI (near-duplicate of pattern 01) or Dana tickets (near-duplicate of pattern 09).
