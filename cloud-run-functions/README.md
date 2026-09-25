# Cloud Run / Cloud Functions

Patterns for HTTP and event-driven services used behind API Gateway or Apigee.

## Patterns

| ID | Name | Folder |
|----|------|--------|
| 01 | HTTP handler behind API Gateway | [`01-http-handler-behind-gateway/`](./01-http-handler-behind-gateway/) |
| 02 | Vendor API key auth handler | [`02-vendor-api-key-auth-handler/`](./02-vendor-api-key-auth-handler/) |
| 03 | OIDC outbound HTTP client (paginated pull) | [`03-oidc-outbound-http-client/`](./03-oidc-outbound-http-client/) |
| 04 | Env-scoped BigQuery pagination (DEPLOY_ENV) | [`04-env-scoped-bq-pagination/`](./04-env-scoped-bq-pagination/) |
| 05 | POS daily-transactions offset/limit (SQL pushdown) | [`05-pos-daily-transactions-offset-limit/`](./05-pos-daily-transactions-offset-limit/) |

## Planned

- Apigee proxy / product / KVM — only when `Documents/API` notes exist (do not invent)
- Remaining unused OpenAPI twin / panel dashboard variant — only if still unique vs gateway patterns 03 / 11

## Rules

Add sanitized function code and deployment notes only. No API keys, OAuth tokens, or live hostnames in source.
