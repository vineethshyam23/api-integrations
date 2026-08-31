# Cloud Run / Cloud Functions

Patterns for HTTP and event-driven services used behind API Gateway or Apigee.

## Patterns

| ID | Name | Folder |
|----|------|--------|
| 01 | HTTP handler behind API Gateway | [`01-http-handler-behind-gateway/`](./01-http-handler-behind-gateway/) |
| 02 | Vendor API key auth handler | [`02-vendor-api-key-auth-handler/`](./02-vendor-api-key-auth-handler/) |
| 03 | OIDC outbound HTTP client (paginated pull) | [`03-oidc-outbound-http-client/`](./03-oidc-outbound-http-client/) |
| 04 | Env-scoped BigQuery pagination (DEPLOY_ENV) | [`04-env-scoped-bq-pagination/`](./04-env-scoped-bq-pagination/) |

## Planned

- Auth between gateway and backend deep-dive (OIDC audience / custom claims)
- Apigee proxy / product / KVM — only when `Documents/API` notes exist (do not invent)
- Multi-filter tickets OpenAPI (paired query params) — `prd/odoo-tickets-mde.yml` if still unused

## Rules

Add sanitized function code and deployment notes only. No API keys, OAuth tokens, or live hostnames in source.
