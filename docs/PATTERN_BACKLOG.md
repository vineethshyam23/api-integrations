# Pattern backlog — API Integrations (GCP)

Scope: Cloud Run / Cloud Functions, API Gateway, Apigee, API & Services keys only.
One pattern shipped per automation run. Do not duplicate Done items.

## Done

| ID | Pattern | Folder | Shipped | PR |
|----|---------|--------|---------|-----|
| 01 | Customer lookup via API Gateway (OpenAPI) | `api-gateway/01-customer-lookup-openapi/` | 2026-07-17 | https://github.com/vineethshyam23/api-integrations/pull/1 |
| 02 | HTTP Cloud Function handler behind gateway | `cloud-run-functions/01-http-handler-behind-gateway/` | 2026-07-20 | https://github.com/vineethshyam23/api-integrations/pull/2 |
| 03 | Multi-route dashboard OpenAPI (establishment / visits) | `api-gateway/02-multi-route-dashboard-openapi/` | 2026-07-24 | https://github.com/vineethshyam23/api-integrations/pull/3 |
| 04 | GA sessions / daily-visits OpenAPI (Cloud Run backends) | `api-gateway/03-ga-sessions-daily-visits-openapi/` | 2026-07-27 | https://github.com/vineethshyam23/api-integrations/pull/4 |
| 05 | Restricted API key (API & Services) | `api-and-services-keys/01-restricted-api-key/` | 2026-08-21 | https://github.com/vineethshyam23/api-integrations/pull/5 |

## Next candidates (not Done)

| Priority | Pattern | Target folder | Source hint |
|----------|---------|---------------|-------------|
| 1 | Apigee proxy / product / KVM pattern (placeholders only) | `apigee/01-...` | Optional local `Documents/API` notes if present; else skip inventing — wait for notes |
| 2 | Outbound / vendor-facing HTTP Cloud Function with structured logging + secret-safe key compare | `cloud-run-functions/02-...` | e.g. Medallia-style handler under `prd/medalia_api_integrated.py` — sanitize aggressively (strip real keys, project IDs, table names) |
| 3 | Outbound HTTP client Cloud Function (vendor API pull) | `cloud-run-functions/03-...` | Prefer a real outbound client if present under `prd/`; else skip inventing |

## Out of scope here

- Airflow DAGs → `airflow-patterns`
- dbt models → `dbt-patterns`
- FinOps / portfolio narrative → `data-platform-portfolio`

## Notes

- Prefer unique engineering value over another near-duplicate single-route OpenAPI.
- Skip source files that are mostly secrets with little pattern value.
- Sanitize all project IDs, hostnames, keys, and company identifiers before commit.
- Apigee remains blocked in Cloud without `Documents/API` notes; GitLab `cloud_functions` has no Apigee artifacts — do not invent.
- 2026-08-21: shipped API key restriction template (backlog priority after Apigee skip). Next source-backed candidate is Medallia-style key validation / handler under `prd/`.
