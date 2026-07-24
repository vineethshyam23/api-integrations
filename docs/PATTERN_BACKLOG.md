# Pattern backlog — API Integrations (GCP)

Scope: Cloud Run / Cloud Functions, API Gateway, Apigee, API & Services keys only.
One pattern shipped per automation run. Do not duplicate Done items.

## Done

| ID | Pattern | Folder | Shipped | PR |
|----|---------|--------|---------|-----|
| 01 | Customer lookup via API Gateway (OpenAPI) | `api-gateway/01-customer-lookup-openapi/` | 2026-07-17 | https://github.com/vineethshyam23/api-integrations/pull/1 |
| 02 | HTTP Cloud Function handler behind gateway | `cloud-run-functions/01-http-handler-behind-gateway/` | 2026-07-20 | https://github.com/vineethshyam23/api-integrations/pull/2 |
| 03 | Multi-route dashboard OpenAPI (establishment / visits) | `api-gateway/02-multi-route-dashboard-openapi/` | 2026-07-24 | https://github.com/vineethshyam23/api-integrations/pull/3 |

## Next candidates (not Done)

| Priority | Pattern | Target folder | Source hint |
|----------|---------|---------------|-------------|
| 1 | Apigee proxy / product / KVM pattern (placeholders only) | `apigee/01-...` | Optional local `Documents/API` notes if present; else platform practice template |
| 2 | API key creation + referrer/IP/API restriction template | `api-and-services-keys/01-...` | Platform practice; no real key material |
| 3 | GA sessions / daily-visits multi-route OpenAPI (analytics teaching shape) | `api-gateway/03-...` | `dev/swagger_api_gateway.yaml` — only if distinct enough from 03 |

## Out of scope here

- Airflow DAGs → `airflow-patterns`
- dbt models → `dbt-patterns`
- FinOps / portfolio narrative → `data-platform-portfolio`

## Notes

- Prefer unique engineering value over another near-duplicate single-route OpenAPI.
- Skip source files that are mostly secrets with little pattern value.
- Sanitize all project IDs, hostnames, keys, and company identifiers before commit.
