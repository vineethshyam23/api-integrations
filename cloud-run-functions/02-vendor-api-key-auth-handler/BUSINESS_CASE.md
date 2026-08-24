# Business case: Vendor API key auth on Cloud Functions

## Problem

Vendor integrations (CX platforms, POS partners, marketing tools) need a small HTTPS API that returns account / establishment / POS-user records from the warehouse. Teams usually put API Gateway in front and stop there. That leaves two gaps:

1. If the Cloud Run URL leaks, or gateway IAM is wrong, the backend may still answer without an application-level shared secret.
2. Handlers that check keys with plain string equality, or that embed secrets in source / OpenAPI examples, create operational and security debt.

This pattern is the backend half of a vendor-facing lookup API: constant-time key compare, env-driven secret, path routing, parameterized queries.

## Constraints that mattered

- Callers send `X-Api-Key` or `Authorization: Bearer <token>` — both show up in vendor docs.
- Secret must not live in git. Env var (fed from Secret Manager) is the production path; `.env` is for local only.
- One Gen2 function backs multiple routes; paths like `/getUser` must still work when the gateway appends the path to `BACKEND_URL`.
- BigQuery filters must stay parameterized — vendor IDs are untrusted query input.
- Dev and prod differ by project, dataset, runtime SA, and key value — none of that belongs hardcoded in Python.

## Decision

Ship a single **`main` HTTP entry point** that:

1. Rejects non-GET (except CORS `OPTIONS`).
2. Loads expected key from `VENDOR_API_KEY` (or local `.env`), then validates with `hmac.compare_digest`.
3. Routes on path suffix to users / establishments / POS-user queries.
4. Deploys with `--no-allow-unauthenticated` and gateway SA invoker bindings.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| App-layer key + gateway key + IAM | Defense in depth for vendor APIs | Three places to rotate / debug 401 vs 403 |
| `hmac.compare_digest` | Constant-time compare | Requires bytes-compatible strings; reject empty expected key hard |
| Env / Secret Manager for secret | Keeps keys out of source | Easy to accidentally put secret in `--set-env-vars` logs — prefer secret volumes |
| `.env` fallback | Faster local bring-up | Must stay gitignored; never ship to Cloud Run as a file |
| One function, three paths | Shared auth + CORS + logging | Path matching must tolerate gateway suffixes |
| Return `{id: [rows]}` envelope | Matches common vendor client expectations | Slightly odd vs `{records: [...]}` — keep consistent with the contract you published |

## What we did not do here

- Full Apigee product / KVM — no Apigee artifacts in the Cloud Functions source tree.
- Claiming latency or cost savings — measure cold starts and BQ bytes billed in your project.
- Inventing an outbound vendor pull client — this handler is inbound (vendor calls us).
