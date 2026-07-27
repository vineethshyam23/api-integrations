# API Gateway

Patterns for Google Cloud API Gateway in front of Cloud Run / Cloud Functions.

## Patterns

| ID | Name | Folder |
|----|------|--------|
| 01 | Customer lookup via API Gateway (OpenAPI) | [`01-customer-lookup-openapi/`](./01-customer-lookup-openapi/) |
| 02 | Multi-route dashboard OpenAPI | [`02-multi-route-dashboard-openapi/`](./02-multi-route-dashboard-openapi/) |
| 03 | GA sessions / daily-visits OpenAPI (Cloud Run) | [`03-ga-sessions-daily-visits-openapi/`](./03-ga-sessions-daily-visits-openapi/) |

## Planned

- Dev vs prd gateway config discipline without hardcoded project IDs

## Rules

Add sanitized OpenAPI / gateway YAML only. Use placeholders for project IDs, backend URLs, and keys (`PROJECT_ID`, `GATEWAY_HOST`, `BACKEND_URL`, `YOUR_API_KEY`).
