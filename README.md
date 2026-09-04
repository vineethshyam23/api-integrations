# API Integrations (GCP)

Personal reference for API platforms and integrations built on Google Cloud — Cloud Run / Cloud Functions, API Gateway, Apigee, and API keys managed in API & Services.

All examples are sanitized. No real project IDs, API keys, or customer endpoints.

---

## Scope

| Area | What this repo covers |
|------|------------------------|
| **Cloud Run / Cloud Functions** | HTTP services and event-driven functions behind APIs |
| **API Gateway** | Fronting services, routes, auth, and environment configs |
| **Apigee** | Proxies, products, environments, KVMs, and policy patterns |
| **API & Services (API keys)** | Key creation, restriction, and safe consumption patterns |

---

## Patterns

| # | Pattern | Category | Folder |
|---|---------|----------|--------|
| 01 | Customer lookup via API Gateway (OpenAPI) | API Gateway | [`api-gateway/01-customer-lookup-openapi/`](./api-gateway/01-customer-lookup-openapi/) |
| 02 | HTTP handler behind API Gateway | Cloud Run / Cloud Functions | [`cloud-run-functions/01-http-handler-behind-gateway/`](./cloud-run-functions/01-http-handler-behind-gateway/) |
| 03 | Multi-route dashboard OpenAPI | API Gateway | [`api-gateway/02-multi-route-dashboard-openapi/`](./api-gateway/02-multi-route-dashboard-openapi/) |
| 04 | GA sessions / daily-visits OpenAPI | API Gateway | [`api-gateway/03-ga-sessions-daily-visits-openapi/`](./api-gateway/03-ga-sessions-daily-visits-openapi/) |
| 05 | Restricted API key (API & Services) | API & Services keys | [`api-and-services-keys/01-restricted-api-key/`](./api-and-services-keys/01-restricted-api-key/) |
| 06 | Vendor API key auth handler | Cloud Run / Cloud Functions | [`cloud-run-functions/02-vendor-api-key-auth-handler/`](./cloud-run-functions/02-vendor-api-key-auth-handler/) |
| 07 | OIDC outbound HTTP client (paginated pull) | Cloud Run / Cloud Functions | [`cloud-run-functions/03-oidc-outbound-http-client/`](./cloud-run-functions/03-oidc-outbound-http-client/) |
| 08 | Env-scoped BigQuery pagination (DEPLOY_ENV) | Cloud Run / Cloud Functions | [`cloud-run-functions/04-env-scoped-bq-pagination/`](./cloud-run-functions/04-env-scoped-bq-pagination/) |
| 09 | Multi-filter tickets OpenAPI (paired metro+store) | API Gateway | [`api-gateway/04-multi-filter-tickets-openapi/`](./api-gateway/04-multi-filter-tickets-openapi/) |

**Count:** 9 patterns

---

## Repository structure

```
api-integrations/
├── cloud-run-functions/     # Cloud Run / Cloud Functions service patterns
├── api-gateway/             # API Gateway configs and routing patterns
├── apigee/                  # Apigee proxy / product / KVM patterns
├── api-and-services-keys/   # API key lifecycle and restriction patterns
└── docs/                    # Backlog, runbooks (non-architecture docs)
```

Each pattern folder includes:

- `README.md` — overview, file index, sanitization notes, quick start
- `BUSINESS_CASE.md` — problem, constraints, tradeoffs
- `ARCHITECTURE.md` — Mermaid architecture diagram (required)
- `DATA_FLOW.md` — request path and failure modes
- Implementation files (YAML, OpenAPI, Python, shell, etc.)

Backlog: [`docs/PATTERN_BACKLOG.md`](./docs/PATTERN_BACKLOG.md)

---

## Digest fields (Confluence automation)

When documenting changes, use a Field | Value table with:

- Commit ID
- Commit message
- Summary of changes
- Code / config files created
- Architecture file created
- Docs created (excl. architecture)
