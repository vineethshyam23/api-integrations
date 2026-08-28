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
| 06 | Vendor API key auth handler (hmac.compare_digest) | `cloud-run-functions/02-vendor-api-key-auth-handler/` | 2026-08-24 | https://github.com/vineethshyam23/api-integrations/pull/6 |
| 07 | OIDC outbound HTTP client (paginated pull) | `cloud-run-functions/03-oidc-outbound-http-client/` | 2026-08-28 | https://github.com/vineethshyam23/api-integrations/pull/7 |

## Next candidates (not Done)

| Priority | Pattern | Target folder | Source hint |
|----------|---------|---------------|-------------|
| 1 | Apigee proxy / product / KVM pattern (placeholders only) | `apigee/01-...` | Optional local `Documents/API` notes if present; else skip inventing — wait for notes |
| 2 | Gateway OpenAPI + app-layer key passthrough deep-dive | `api-gateway/04-...` | Only if distinct from patterns 01–04 / 06 companion OpenAPI |
| 3 | Outbound client variants (custom audience / workload identity notes) | `cloud-run-functions/04-...` | Only if a distinct source artifact appears — do not invent |

## Out of scope here

- Airflow DAGs → `airflow-patterns`
- dbt models → `dbt-patterns`
- FinOps / portfolio narrative → `data-platform-portfolio`

## Notes

- Prefer unique engineering value over another near-duplicate single-route OpenAPI.
- Skip source files that are mostly secrets with little pattern value.
- Sanitize all project IDs, hostnames, keys, and company identifiers before commit.
- Apigee remains blocked in Cloud without `Documents/API` notes; GitLab `cloud_functions` has no Apigee artifacts — do not invent.
- 2026-08-21: shipped API key restriction template (backlog priority after Apigee skip).
- 2026-08-24: shipped vendor API key auth handler from `prd/medalia_api_integrated.py` (+ companion OpenAPI). Apigee still blocked without `Documents/API`.
- 2026-08-28: shipped OIDC outbound paginated pull client from `prd/extract_tourism_data.py`. Maileon / tourismnrw_api.py remain BQ-backed inbound handlers (not outbound). Only `extract_tourism_data.py` used `requests` + identity token under `cloud_functions`. Next: Apigee if notes appear; else distinct gateway deep-dive only if not duplicate.
