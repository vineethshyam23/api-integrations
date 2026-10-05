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
| 10 | Multi-route panel dashboard gateway twins | [`10-multi-route-panel-gateway-twins/`](./10-multi-route-panel-gateway-twins/) |
| 11 | Bearer-only Cloud Run gateway auth | [`11-bearer-only-cloudrun-gateway-auth/`](./11-bearer-only-cloudrun-gateway-auth/) |

## Planned

- Apigee proxy / product / KVM when notes exist
- POS establishment lookup OpenAPI — only if still unique vs pattern 01
- Remaining unused multi-route security-drop / panel variants — only if still unique vs 03 / 11 / 16

## Rules

Add sanitized OpenAPI / gateway YAML only. Use placeholders for project IDs, backend URLs, and keys (`PROJECT_ID`, `GATEWAY_HOST`, `BACKEND_URL`, `YOUR_API_KEY`).
