# Business case: Twin schema fidelity gate

## Problem

Pattern 11 catches the loud twin failures — path-level `security:` dropped in
DEV, backends accidentally identical, property types int-vs-string. A quieter
class still ships: someone copies an OpenAPI from another product, renames the
path, and leaves the old response `$ref` (`OtherProductDataResponse` /
`MaileonDataResponse`). Records stay `additionalProperties: true`. DEV later
gets a typed record model. Clients generated from DEV bind fields; clients
generated from PRD get a bag of maps. Status code sets drift too (extra 403 on
one twin). Curl still returns 200. Partner SDKs disagree.

## Constraints that mattered

- Public contract includes **definition names** and **records item shape**, not
  only path strings and security scheme `name`/`in`.
- Typed `$ref` on `records.items` is the bar for pagination extracts that
  partners generate against. Untyped objects are a temporary shortcut, not a
  twin-safe end state.
- Response status sets must match across envs so error handling docs and mock
  servers stay honest.
- Backend addresses must still differ (same rule as pattern 11).
- Handler / warehouse logic already lives elsewhere (pattern 08). This folder
  is the **gateway twin schema** discipline only.

## Decision

Ship **aligned** `openapi.prd.yaml` / `openapi.dev.yaml` for one
`/getMarketPotentialData` extract, plus:

1. `check-schema-fidelity.sh` — fails on foreign 200 `$ref` names, definition
   key drift, `additionalProperties` on records, and status-code set drift.
2. A negative fixture + `--self` mode so the gate has a positive control.
3. Env-aware `deploy.sh` that always runs the gate first.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| Gate on `$ref` names + definition keys | Catches copy-paste from another product | Rename requires editing both twins |
| Require typed records `$ref` | Generators and contract tests bind fields | Slightly more YAML to maintain |
| Status-code set parity | Error docs match both envs | Temptation to "document only PRD IAM 403" |
| Keep security / path checks too | One script before deploy | Overlaps pattern 11 slightly — intentional |

## Distinct from earlier patterns

- **08** — env-scoped BigQuery pagination **handler** + a single companion
  OpenAPI (untyped records were acceptable there as a handler-first ship).
- **11** — twin gate focused on security drop, paths, and property **types**.
  Does not teach foreign `$ref` names or `additionalProperties` vs typed items.
- **12 / 16** — multi-route panel twins / marketing extracts — different surface.
- **19** — single-file path-security lint when no twin exists yet.

## What we did not do here

- Apigee products / KVMs — no `Documents/API` notes; do not invent.
- Re-shipping the Python handler — see
  `cloud-run-functions/04-env-scoped-bq-pagination/`.
- Claiming partner onboarding time savings — measure in your own rollout.
