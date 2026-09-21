# API Gateway

Patterns for Google Cloud API Gateway in front of Cloud Run / Cloud Functions.

## Patterns

| ID | Name | Folder |
|----|------|--------|
| 01 | Customer lookup via API Gateway (OpenAPI) | [`01-customer-lookup-openapi/`](./01-customer-lookup-openapi/) |
| 02 | Multi-route dashboard OpenAPI | [`02-multi-route-dashboard-openapi/`](./02-multi-route-dashboard-openapi/) |
| 03 | GA sessions / daily-visits OpenAPI (Cloud Run) | [`03-ga-sessions-daily-visits-openapi/`](./03-ga-sessions-daily-visits-openapi/) |
| 04 | Multi-filter tickets OpenAPI (paired metro+store) | [`04-multi-filter-tickets-openapi/`](./04-multi-filter-tickets-openapi/) |
| 05 | Menu-engineering country-split OpenAPI | [`05-menu-engineering-country-split/`](./05-menu-engineering-country-split/) |
| 06 | Dev vs prd API Gateway twins | [`06-dev-prd-gateway-twins/`](./06-dev-prd-gateway-twins/) |
| 07 | Multi-table marketing-trigger OpenAPI | [`07-multi-table-marketing-trigger/`](./07-multi-table-marketing-trigger/) |
| 08 | Inbound dual-route daily NTILE pagination | [`08-inbound-dual-route-daily-ntile/`](./08-inbound-dual-route-daily-ntile/) |
| 09 | Dual-scheme gateway auth contract (Bearer + API key) | [`09-dual-scheme-gateway-auth-contract/`](./09-dual-scheme-gateway-auth-contract/) |

## Planned

- Apigee proxy / product / KVM when notes exist
- Remaining unused OpenAPI twin / panel dashboard variant — only if still unique vs patterns 03 / 11

## Rules

Add sanitized OpenAPI / gateway YAML only. Use placeholders for project IDs, backend URLs, and keys (`PROJECT_ID`, `GATEWAY_HOST`, `BACKEND_URL`, `YOUR_API_KEY`).
