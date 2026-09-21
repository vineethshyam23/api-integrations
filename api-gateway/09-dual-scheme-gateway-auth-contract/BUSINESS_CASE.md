# Business case: dual Bearer + API-key gateway auth contract

## Problem

Vendor-facing lookup APIs almost always end up supporting two client habits:

1. `X-API-KEY: <secret>` — common in partner runbooks and API Gateway examples
2. `Authorization: Bearer <secret>` — what many SDKs and CX platforms generate by default

Teams then publish one OpenAPI `securityDefinitions` entry named `Bearer` that actually maps to `X-API-KEY`. Swagger UI lies. Codegen lies. On-call spends a day proving "the key works in curl but not in Postman."

Meanwhile the Cloud Run handler already accepts both headers (defense in depth with `hmac.compare_digest`). The missing piece is an **honest edge contract**: declare both schemes, mark them as alternatives, and gate deploys so the naming pitfall cannot regress into the published API config.

## Constraints that mattered

- API Gateway consumes Swagger 2.0; security OR vs AND is easy to get wrong.
- One Cloud Run service backs three path backends (`/getUser`, `/getPosUser`, `/getEstablishments`) with `protocol: h2`.
- App-layer validation stays on the handler — gateway API keys are necessary but not sufficient if the service URL leaks.
- Secrets never belong in OpenAPI examples, git, or long-lived `--set-env-vars` (Secret Manager → runtime env).
- Schema examples in the original source contained real-looking PII — public repos need placeholders only.

## Decision

Ship a dedicated **gateway auth-contract** pattern that:

1. Defines `ApiKeyHeader` (`X-API-KEY`) and `BearerToken` (`Authorization`) as separate `apiKey` schemes.
2. Lists both under each path's `security` as alternatives (Swagger OR).
3. Keeps full response envelopes (`{id: [rows]}`) so the OpenAPI matches what vendor clients parse.
4. Adds `check-auth-contract.sh` so CI / deploy fails if someone reintroduces a misnamed `Bearer`→`X-API-KEY` scheme.
5. Points to the existing handler pattern instead of duplicating Python.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| Two schemes, OR list | Matches real client headers; honest docs | Slightly longer OpenAPI; reviewers must know Swagger OR vs AND |
| Keep scheme type `apiKey` for Bearer | Correct for shared-secret tokens on API Gateway | Not OAuth2 — do not pretend this is OIDC |
| Contract check script | Cheap regression gate | Regex/awk will miss exotic YAML layouts — keep the spec boring |
| Reference handler pattern | No duplicate `main.py` drift | Readers must open two folders |
| Full schemas in OpenAPI | Better partner onboarding | Must sanitize examples aggressively |

## What we did not do here

- Invent Apigee KVM / product policies (no Apigee notes in Cloud).
- Re-ship the vendor key handler (already pattern 06 under `cloud-run-functions`).
- Claim gateway-only auth is enough — IAM invoker + app-layer secret still required.
- Encode fake FinOps savings or unsupported SLAs.
