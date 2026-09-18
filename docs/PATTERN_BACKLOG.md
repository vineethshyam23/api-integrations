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
| 08 | Env-scoped BigQuery pagination handler (DEPLOY_ENV) | `cloud-run-functions/04-env-scoped-bq-pagination/` | 2026-08-31 | https://github.com/vineethshyam23/api-integrations/pull/8 |
| 09 | Multi-filter tickets OpenAPI (paired metro+store) | `api-gateway/04-multi-filter-tickets-openapi/` | 2026-09-04 | https://github.com/vineethshyam23/api-integrations/pull/9 |
| 10 | Menu-engineering country-split OpenAPI | `api-gateway/05-menu-engineering-country-split/` | 2026-09-07 | https://github.com/vineethshyam23/api-integrations/pull/10 |
| 11 | Dev vs prd API Gateway twins (contract parity gate) | `api-gateway/06-dev-prd-gateway-twins/` | 2026-09-11 | https://github.com/vineethshyam23/api-integrations/pull/11 |
| 12 | Multi-table marketing-trigger OpenAPI (shared pagination) | `api-gateway/07-multi-table-marketing-trigger/` | 2026-09-14 | https://github.com/vineethshyam23/api-integrations/pull/12 |
| 13 | Inbound dual-route daily NTILE pagination | `api-gateway/08-inbound-dual-route-daily-ntile/` | 2026-09-18 | https://github.com/vineethshyam23/api-integrations/pull/13 |

## Next candidates (not Done)

| Priority | Pattern | Target folder | Source hint |
|----------|---------|---------------|-------------|
| 1 | Apigee proxy / product / KVM pattern (placeholders only) | `apigee/01-...` | Optional local `Documents/API` notes if present; else skip inventing — wait for notes |
| 2 | Gateway OpenAPI + app-layer Bearer/key passthrough deep-dive | `api-gateway/09-...` | Medallia companion YAML (`medalia_integrated.yml` / `medallia.yml`) — only if distinct from pattern 06 |
| 3 | Remaining unused OpenAPI twin / panel dashboard variant | `api-gateway/09-...` | Only if still unique vs patterns 03 / 11 after review |

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
- 2026-08-28: shipped OIDC outbound paginated pull client from `prd/extract_tourism_data.py`. Maileon / tourismnrw_api.py remain BQ-backed inbound handlers (not outbound). Only `extract_tourism_data.py` used `requests` + identity token under `cloud_functions`.
- 2026-08-31: shipped env-scoped BQ pagination handler from `prd/pos_potential_sam_api_integrated.py` (+ companion OpenAPI). Focus: `DEPLOY_ENV` table defaults, optional full-table override, country allowlist, gated `EXPOSE_ERROR_DETAIL`. Skipped Medallia companion OpenAPI deep-dive (already covered lightly in pattern 06). Next: Apigee if notes appear; else odoo multi-filter gateway OpenAPI.
- 2026-09-04: shipped multi-filter tickets OpenAPI + parameterized handler from `prd/odoo-tickets-mde.yml` + `.py`. Focus: paired metroId+storeId, offset/limit, Cloud Run backend, f-string SQL removed. Apigee still blocked without `Documents/API`. Next: Apigee if notes; else menu-engineering country-split if distinct.
- 2026-09-07: shipped menu-engineering country-split OpenAPI + handler from `prd/dish-menu-engineering-pos.yml` + `.py`. Focus: country enum → env table map, ISO dates, parameterized BQ, SQL OFFSET. Apigee still blocked without `Documents/API`. Next: Apigee if notes; else dev/prd gateway twin discipline or a distinct remaining artifact.
- 2026-09-11: shipped DEV/PRD gateway twin discipline from `prd/dish-360-dashboard-de.yml` + `dev/dish-360-dashboard-de-dev.yml` (plus security-drop lesson from customer-lookup twins). Focus: paired OpenAPI, `check-twins.sh` contract gate, env-aware deploy. Aligned schema types; kept security on in both twins. Apigee still blocked without `Documents/API`. Next: Apigee if notes; else Maileon multi-table trigger API.
- 2026-09-14: shipped multi-table marketing-trigger OpenAPI + shared pagination helper from `prd/maileon_api_integrated.yml` + `.py`. Focus: path→table map, shared `fetch_data_with_pagination`, fields-metadata grouping, env table overrides, gated error detail. Paths renamed `/triggers/*`; column lists trimmed. Apigee still blocked without `Documents/API`. Next: Apigee if notes; else tourism inbound multi-route pagination.
- 2026-09-18: shipped inbound dual-route daily NTILE pagination from `prd/tourismnrw_integrated.yml` + `tourismnrw_api.py`. Focus: full catalog vs daily NTILE bucket, asymmetric empty semantics (404 vs soft 200+message), parameterized BQ, env table ids, PII columns trimmed. Apigee still blocked without `Documents/API`. Next: Apigee if notes; else Medallia companion OpenAPI deep-dive if still distinct from pattern 06.
