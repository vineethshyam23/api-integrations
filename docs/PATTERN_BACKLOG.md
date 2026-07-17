# Pattern backlog — API Integrations (GCP)

Scope: Cloud Run / Cloud Functions, API Gateway, Apigee, API & Services keys only.
One pattern shipped per automation run. Do not duplicate Done items.

## Done

| ID | Pattern | Folder | Shipped | PR |
|----|---------|--------|---------|-----|
| 01 | Customer lookup via API Gateway (OpenAPI) | `api-gateway/01-customer-lookup-openapi/` | 2026-07-17 | https://github.com/vineethshyam23/api-integrations/pull/1 |

## Next candidates (not Done)

| Priority | Pattern | Target folder | Source hint |
|----------|---------|---------------|-------------|
| 1 | HTTP Cloud Function handler behind gateway (structured logging + IAM/OIDC notes) | `cloud-run-functions/01-...` | `cloud_functions/dev/cloud_function_main.py` or panel/lookup `*.py` |
| 2 | Multi-route dashboard OpenAPI (establishment / visits style) | `api-gateway/02-...` | `prd/dish_pos_openapi_spec.yml` / panel dashboard YAML |
| 3 | Apigee proxy / product / KVM pattern (placeholders only) | `apigee/01-...` | Optional local `Documents/API` notes if present |
| 4 | API key creation + referrer/IP/API restriction template | `api-and-services-keys/01-...` | Platform practice; no real key material |

## Out of scope here

- Airflow DAGs → `airflow-patterns`
- dbt models → `dbt-patterns`
- FinOps / portfolio narrative → `data-platform-portfolio`

## Notes

- Prefer unique engineering value over another near-duplicate single-route OpenAPI.
- Skip source files that are mostly secrets with little pattern value.
- Sanitize all project IDs, hostnames, keys, and company identifiers before commit.
