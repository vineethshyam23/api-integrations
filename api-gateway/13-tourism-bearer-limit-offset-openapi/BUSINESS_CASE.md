# Business case: Bearer-only limit/offset catalog gateway

## Problem

Regional destination / partner feeds often start as a single Cloud Run catalog
endpoint with `limit` and `offset`. Later the same product grows a second path
(daily NTILE slice) and switches clients to `pageSize` / `pageNumber` with an
`X-API-KEY` edge contract. Teams then lose the original thin OpenAPI: either
they overwrite it with the dual-route revision, or they keep a stale YAML whose
`Bearer` scheme still maps to `X-API-KEY`.

Hiring and ops both need the **thin contract** documented separately:

- Pattern 13 already covers the dual-route ApiKeyAuth feed with page-based
  paging and asymmetric empty semantics.
- Pattern 18 already covers Bearer-only auth for a **non-paginated** single-id
  lookup.

Neither folder teaches "Bearer + `limit`/`offset` + `{records, pagination}` on
one Cloud Run path". That is the contract many partner SDKs still ship against
during the first integration.

## Constraints

- Edge auth must match what the partner SDK sends (`Authorization: Bearer`).
- Pagination dialect must match what the partner already coded (`limit` /
  `offset`), not what a later internal revision preferred (`pageSize` /
  `pageNumber`).
- Gateway OpenAPI alone is not enough: Cloud Run still needs invoker IAM and
  an app-layer shared-secret check if the backend URL leaks.
- Public teaching docs must not carry contact email, phone, or live hostnames.
- Do not invent FinOps savings or SLA claims for a pagination dialect change.

## Decision

Ship a dedicated **Bearer-only limit/offset** gateway OpenAPI that:

1. Defines one `BearerToken` scheme with `name: Authorization`.
2. Exposes a single `/catalog` path with `limit` / `offset` defaults.
3. Documents the `{records, pagination{total,limit,offset}}` envelope.
4. Keeps a Cloud Run path backend address + `protocol: h2`.
5. Adds `check-bearer-limit-offset-contract.sh` so deploy fails if Authorization
   mapping drifts, ApiKeyAuth sneaks in, or paging regresses to
   pageSize/pageNumber without changing the teaching intent.
6. Points at pattern 13 for the dual-route ApiKeyAuth evolution and pattern 18
   for Bearer-only non-paginated lookups — no duplicate handler Python here.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| Bearer only | Matches partner SDKs that only send Authorization | X-API-KEY-only clients need pattern 13 / 14 |
| limit/offset | Matches offset-based client loops and SQL pushdown | Clients using pageNumber need adapter math |
| Single path | Honest surface for the thin catalog | Daily / NTILE modes belong in pattern 13 |
| Contract check | Cheap regression gate across auth + paging | Regex/awk miss exotic YAML — keep the spec boring |
| OpenAPI-only (no main.py) | Avoids drift vs pattern 13 handler | Readers open pattern 13 for SQL pushdown details |

## What we did not do here

- Invent Apigee KVM / product policies (no Apigee notes in Cloud).
- Re-ship dual-route NTILE (already pattern 13).
- Re-ship Bearer-only CX user lookup (already pattern 18).
- Re-ship POS establishment single-id lookup (near-duplicate of pattern 01).
- Encode fake savings from switching pageSize ↔ limit/offset.
