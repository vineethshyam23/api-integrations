# Architecture: Customer lookup via API Gateway

## Components

| Component | Role |
|-----------|------|
| Client | Internal tool or dashboard calling HTTPS |
| API Gateway | Validates API key, terminates TLS, proxies to backend |
| API key (API & Services) | Credential bound to this API / gateway |
| Cloud Function (HTTP) | Looks up account → returns env URLs (JSON) |
| Data store (optional) | BigQuery / Firestore / SQL behind the function — not part of this pattern's config |

## Diagram

```mermaid
flowchart LR
  client[Client]
  gw[API Gateway]
  key[API and Services key]
  fn[HTTP Cloud Function]
  store[(Lookup store)]

  client -->|"GET /Customer?accountId=&key="| gw
  key -.->|"key validated by gateway"| gw
  gw -->|"x-google-backend"| fn
  fn --> store
  fn -->|"200 Customer JSON"| gw
  gw --> client
```

## Environment separation

Ship **separate API configs** (or at least separate `x-google-backend.address` values) for dev and prod. Do not encode project IDs in shared libraries — keep them in the OpenAPI deployed per environment.

```mermaid
flowchart TB
  subgraph dev [DEV]
    gwDev[Gateway DEV]
    fnDev[Function DEV]
    gwDev --> fnDev
  end

  subgraph prd [PRD]
    gwPrd[Gateway PRD]
    fnPrd[Function PRD]
    gwPrd --> fnPrd
  end

  clientsDev[Dev clients + restricted keys] --> gwDev
  clientsPrd[Prod clients + restricted keys] --> gwPrd
```

## Operability notes

- Treat the OpenAPI file as the source of truth for routes and auth requirements.
- If the backend 403s while the gateway accepts the key, check function IAM (gateway service account invoker role).
- Prefer restricting API keys by API + optional referrer/IP (see `api-and-services-keys/` patterns).
