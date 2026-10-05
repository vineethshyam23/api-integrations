# Business case: Bearer-only Cloud Run gateway auth

## Problem

Some partner / CX platforms only speak `Authorization: Bearer <token>`. Teams
that already run API Gateway often copy an `X-API-Key` OpenAPI template and
rename the scheme to `Bearer` while leaving `name: X-API-KEY`. Clients following
the scheme name send Authorization; clients following the `name` field send
X-API-KEY. Support tickets follow.

Pattern 14 solves the case where **both** headers must work (dual OR schemes).
This pattern covers the narrower production case: **Bearer only**, mapped
correctly to the Authorization header, in front of a single Cloud Run path
backend. It is the honest edge contract when the vendor SDK cannot (or must
not) send X-API-KEY.

## Constraints that mattered

- API Gateway still models the shared secret as Swagger 2.0 `apiKey` in header —
  this is not OAuth2 / OIDC just because the header says Bearer.
- One Cloud Run service path (`/getUsers`) with `protocol: h2`.
- App-layer validation stays on the service — gateway rejection and handler
  rejection are different failure domains.
- Response schemas include PII-shaped fields (email, phone). Public teaching
  docs keep placeholders only; production field lists should be scoped to what
  the partner actually needs.
- Secrets never belong in OpenAPI examples, git, or long-lived deploy env vars.

## Decision

Ship a dedicated **Bearer-only** gateway auth pattern that:

1. Defines one `BearerToken` scheme with `name: Authorization`.
2. Requires that scheme on `/getUsers` (no OR list, no X-API-KEY scheme).
3. Keeps a Cloud Run path backend address + h2 protocol.
4. Adds `check-bearer-contract.sh` so deploy fails if the Authorization mapping
   drifts or someone reintroduces the Bearer→X-API-KEY pitfall / dual schemes
   without changing the teaching intent.
5. Points to the vendor key handler pattern for app-layer compare instead of
   duplicating Python here.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| Bearer only | Matches CX SDKs that only send Authorization | Clients that only have X-API-KEY need dual-scheme (pattern 14) |
| Scheme type `apiKey` | Correct for shared-secret tokens on API Gateway | Reviewers must not assume OAuth2 |
| Single path | Smallest honest surface for one lookup | Multi-route surfaces need per-path security copies |
| Contract check script | Cheap regression gate | Regex/awk miss exotic YAML — keep the spec boring |
| Reference existing handler | No duplicate `main.py` drift | Readers open two folders |

## What we did not do here

- Invent Apigee KVM / product policies (no Apigee notes in Cloud).
- Re-ship dual-scheme auth (already pattern 14).
- Re-ship the vendor key handler (already `cloud-run-functions/02-...`).
- Claim gateway-only auth is enough — IAM invoker + app-layer secret still required.
- Encode fake FinOps savings or unsupported SLAs.
