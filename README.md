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

## Repository structure

```
api-integrations/
├── cloud-run-functions/     # Cloud Run / Cloud Functions service patterns
├── api-gateway/             # API Gateway configs and routing patterns
├── apigee/                  # Apigee proxy / product / KVM patterns
├── api-and-services-keys/   # API key lifecycle and restriction patterns
└── docs/                    # Architecture and runbooks (non-architecture docs too)
```

Each pattern folder is expected to include:

- `README.md` — use case, design, lessons learned
- Implementation files (YAML, OpenAPI, Python, etc.)
- `architecture.md` when a diagram is useful

---

## Digest fields (Confluence automation)

When documenting changes, use a Field | Value table with:

- Commit ID
- Commit message
- Summary of changes
- Code / config files created
- Architecture file created
- Docs created (excl. architecture)

---

## Status

Scaffold only. Patterns will be filled from real GCP work (sanitized).
