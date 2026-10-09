# Business case: multi-route path-security lint

## Problem

Multi-route panel APIs grow path by path. Someone adds `securityDefinitions`
early (Swagger UI shows a lock icon) and defers wiring `security:` under each
operation "until we have a real key." The gateway config deploys. Every route
is reachable without credentials. Reviewers miss it because the file *contains*
auth language.

When the surface has four independent Cloud Function backends, forgetting
path security is a full unauthenticated data plane — establishment metadata,
visits, orders, and reservations — not a single forgotten stub.

## Constraints

- Google Cloud API Gateway only enforces schemes referenced by path/operation
  `security:` (or a global `security:`). Unused `securityDefinitions` are
  documentation, not policy.
- DEV often ships first without a PRD twin. Twin gates (pattern 11) cannot run
  until a second file exists.
- Query-string API keys (`?key=`) show up in access logs, CDN logs, and
  Referer headers. Prefer header `X-API-KEY`.
- Per-route backends still need per-function invoker IAM even after edge auth
  is correct.

## Tradeoffs

| Choice | Why | Cost |
|--------|-----|------|
| Single-file path-security lint | Catches the footgun before twins exist | Does not replace twin parity once both envs ship |
| Fail closed when definitions exist but ops lack `security:` | Matches "looks secured" risk | Intentional public routes need an empty global security or a documented exception |
| Header API key in sanitized exemplar | Avoids query leakage | Source used query `key` — migration needs client updates |
| Negative fixture in-repo | Proves the gate fails for real | Risk someone deploys the fixture if they skip the lint |

## Why not invent Apigee / another OpenAPI

Apigee notes are not available in Cloud. Another near-duplicate single-route
lookup adds little. This pattern extracts a reusable gate from a real broken
DEV config and pairs it with a corrected multi-route exemplar.
