# Cloud Run / Cloud Functions

Patterns for HTTP and event-driven services used behind API Gateway or Apigee.

## Patterns

| ID | Name | Folder |
|----|------|--------|
| 01 | HTTP handler behind API Gateway | [`01-http-handler-behind-gateway/`](./01-http-handler-behind-gateway/) |

## Planned

- Auth between gateway and backend deep-dive (OIDC audience / custom claims)
- Environment separation (dev / prd) without hardcoding project IDs — covered in part by pattern 01 deploy env

## Rules

Add sanitized function code and deployment notes only. No API keys, OAuth tokens, or live hostnames in source.
