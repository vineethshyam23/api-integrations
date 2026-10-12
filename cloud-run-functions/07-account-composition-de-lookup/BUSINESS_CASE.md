# Business case: Account-composition DE lookup handler

## Problem

Dashboard and panel clients look up account activity using messy real-world identity inputs:

1. Some callers know `metroId` + `storeId` and expect the backend to **compose** the warehouse account id (`PREFIX + store(zfill) + metro(zfill)`).
2. Some already hold `metroAccountIdentifier` and should bypass composition.
3. Some paste the full composed id into the `metroId` slot.
4. Metro / store values arrive zero-padded inconsistently (`00154530` vs `154530`).

A naive "require paired filters and AND them" contract (see pattern 09 tickets) rejects valid callers and cannot express composition. An early production handler hard-coded a national prefix and a live project id, returned contact email in the payload, and used a vague `ENV` project name — fine for a one-off, brittle as a reusable platform pattern.

## Constraints that mattered

- At least one of `metroId` or `metroAccountIdentifier` must be present — empty identity is a **400**, not a full-table scan.
- `storeId` is optional; when present with metro it enables composition **and** a paired metro+store predicate.
- Match strategies must be **OR-unioned** (caller may hit via composed id *or* raw metro columns).
- Response shape stays `{records, count}`; empty → **404** "Establishment not found" (same panel convention as sibling routes).
- Edge auth stays at the gateway (API key). Function deploys `--no-allow-unauthenticated`.
- Exception detail helps in staging; gate it with `EXPOSE_ERROR_DETAIL`.
- Do not ship PII columns (email) or live national prefixes / project ids in the public exemplar.

## Decision

Ship a single **`lookup` HTTP entry point** that:

1. Rejects non-GET with **405**.
2. Requires `metroId` and/or `metroAccountIdentifier`; validates paging bounds.
3. Zero-strips metro/store, composes account ids from env-configurable prefix + widths.
4. Builds an OR-union WHERE with `ArrayQueryParameter` + `UNNEST` for account ids.
5. Runs parameterized `SELECT ... LIMIT/OFFSET` against an env-resolved table.
6. Returns `{records, count}` or **404** when empty.
7. Deploys with gateway SA invoker bindings only.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| OR-union vs AND-only filters | Survives mixed client identity styles | Can over-match if composed id collides with unrelated metro rows — mitigate with created_date floor + narrow table |
| Compose in backend vs force clients to send composed id | One contract for legacy + new callers | Prefix / zfill widths become deploy config that must stay in sync with warehouse ETL |
| `ArrayQueryParameter` + UNNEST | Safe multi-id match without string-joined SQL | Slightly more verbose than a single equality |
| Env `ACCOUNT_ID_PREFIX` instead of hard-coded national code | Reusable across countries / orgs | Wrong prefix at deploy = silent empty results (404), not a loud 500 |
| Drop email from RETURN_COLUMNS | Safer public exemplar; less PII surface | Callers that relied on email need a separate consented field set |
| 404 on empty page | Matches existing panel clients | Cannot distinguish "unknown id" from "past last page" without COUNT |

## Distinct from nearby patterns

| Pattern | What it covers | Why this is different |
|---------|----------------|------------------------|
| `api-gateway/04-...` (pattern 09) | Paired metro+store **required together**, AND filters, tickets OpenAPI | No account-id composition; no OR-union; no zero-strip / long-metro fallback |
| `cloud-run-functions/05-...` | Establishment-scoped POS daily tx with SQL OFFSET | Single required `establishmentId`; no identity composition |
| `cloud-run-functions/04-...` | `DEPLOY_ENV` country extract pagination | Country allowlist + pageNumber envelope, not account composition |
| Gateway twin / panel OpenAPI patterns | Route + auth contracts | Do not encode the compose / OR-union logic |

## What we did not do here

- Inventing Apigee KVM / product config — no Apigee artifacts under GitLab `cloud_functions`, and no local `Documents/API` notes this run.
- Shipping POS establishment lookup OpenAPI — still a near-duplicate of pattern 01 single-route lookup.
- Claiming match-rate or latency improvements — measure in your project before quoting numbers.
