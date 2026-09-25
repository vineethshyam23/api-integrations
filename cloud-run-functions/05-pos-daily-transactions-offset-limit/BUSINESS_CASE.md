# Business case: POS daily-transactions offset/limit handler

## Problem

Panel and partner clients need establishment-scoped POS daily transaction history behind API Gateway. An early handler (v2-style) fetched a large `LIMIT` from BigQuery and then sliced `offset`/`limit` in Python. That pattern:

1. Bills BigQuery for rows the client never sees.
2. Breaks down as history grows — memory and latency climb with the establishment's row count.
3. Often ships with string-interpolated SQL (`WHERE establishment_id = '{}'`), which is an injection footgun even when IDs look "safe".
4. Uses a vague `ENV` env var as the BigQuery *project* name, which confuses deploy scripts and on-call.

This pattern is the **v3 backend rewrite**: SQL `LIMIT`/`OFFSET` pushdown, parameterized filters, and an explicit `BQ_PROJECT_ID` contract.

## Constraints that mattered

- Callers already know `establishmentId` + `offset`/`limit` from the multi-route dashboard OpenAPI (see `api-gateway/02-...`).
- Response shape stays a `{records}` envelope — not a bare array — so clients that parse that key keep working.
- Empty results return **404** with "Establishment not found" (same contract as sibling panel routes).
- Hard cap on `limit` (100) so a misconfigured client cannot force large scans.
- Edge auth stays at the gateway (API key). This function deploys `--no-allow-unauthenticated`.
- Exception detail helps in staging; gate it with `EXPOSE_ERROR_DETAIL`.

## Decision

Ship a single **`lookup` HTTP entry point** that:

1. Rejects non-GET with **405**.
2. Requires `establishmentId`; validates `offset`/`limit` bounds.
3. Resolves the table from `POS_DAILY_TX_TABLE` or `BQ_PROJECT_ID` + `DATASET_ID`.
4. Runs a parameterized `SELECT ... WHERE establishment_id = @establishment_id LIMIT @limit OFFSET @offset`.
5. Returns `{records: [...]}` or **404** when empty.
6. Deploys with gateway SA invoker bindings only.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| SQL OFFSET vs Python slice | Bytes billed and RAM track the page, not the full history | Deep OFFSET pages can still be expensive on unpartitioned tables — prefer date filters later if needed |
| Parameterized `@establishment_id` | Removes format-string SQL | Slightly more verbose than the original one-liner |
| `BQ_PROJECT_ID` instead of `ENV` | Readable deploy contract; matches other patterns | Migrations must rename the env var once |
| Full-table override env | Shadow datasets / backfills without code change | Override typos still possible — log the resolved table |
| 404 on empty page | Matches existing panel clients | Clients cannot tell "unknown id" from "past last page" without an extra COUNT |
| No `pageNumber` envelope | Keeps the v3 client contract (`offset`/`limit` only) | Different from pattern 04's `{records, pagination}` — intentional |

## Distinct from nearby patterns

| Pattern | What it covers | Why this is different |
|---------|----------------|------------------------|
| `api-gateway/02-...` | Multi-route OpenAPI including `/v2` vs `/v3` getPOS | Gateway routing only — not the handler rewrite |
| `cloud-run-functions/04-...` | `DEPLOY_ENV` table pick + `pageSize`/`pageNumber` + country allowlist | Country extract API, not establishment daily POS history |
| v2 source (`dish-panel-pos-gbq-v2.py`) | Wide KPI row + in-memory slice | This pattern documents why that approach was retired |

## What we did not do here

- Inventing Apigee KVM / product config — no Apigee artifacts under GitLab `cloud_functions`.
- Claiming scan-cost savings — measure billed bytes before/after in your project.
- Replacing the multi-route dashboard OpenAPI — keep `/v3/getPOS` address pointed here.
