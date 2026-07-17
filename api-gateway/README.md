# API Gateway

Patterns for Google Cloud API Gateway in front of Cloud Run / Cloud Functions.

## Patterns

| ID | Name | Folder |
|----|------|--------|
| 01 | Customer lookup via API Gateway (OpenAPI) | [`01-customer-lookup-openapi/`](./01-customer-lookup-openapi/) |

## Planned

- Multi-route dashboard OpenAPI (establishment / visits)
- Dev vs prd gateway config discipline without hardcoded project IDs

## Rules

Add sanitized OpenAPI / gateway YAML only. Use placeholders for project IDs, backend URLs, and keys (`PROJECT_ID`, `GATEWAY_HOST`, `BACKEND_URL`, `YOUR_API_KEY`).
