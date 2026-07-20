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

**Count:** 2 patterns

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
