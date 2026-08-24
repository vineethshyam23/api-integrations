# Architecture: Vendor API key auth handler

## Components

| Component | Role |
|-----------|------|
| Vendor client | Calls HTTPS with `X-Api-Key` or Bearer token |
| API Gateway (optional but preferred) | Edge OpenAPI, optional second key / quota, OIDC to backend |
| Gateway service account | Invoker identity for Gen2 / Cloud Run |
| HTTP Cloud Function (`main`) | App-layer key check, route, query, JSON |
| Secret / env (`VENDOR_API_KEY`) | Expected shared secret (Secret Manager in prod) |
| Runtime service account | Identity for BigQuery jobs |
| BigQuery | Trusted mart / views for users, establishments, POS users |

## Diagram

```mermaid
flowchart LR
  vendor[Vendor client]
  gw[API Gateway]
  edgeKey[API and Services key]
  appKey[VENDOR_API_KEY secret]
  gwSa[Gateway SA]
  fn[HTTP Cloud Function main]
  runtimeSa[Runtime SA]
  bq[(BigQuery)]

  vendor -->|"GET /getUser etc + X-Api-Key"| gw
  edgeKey -.->|"optional edge validation"| gw
  gw -->|"OIDC as Gateway SA"| fn
  gwSa -.-> fn
  appKey -.->|"hmac.compare_digest"| fn
  fn --> bq
  runtimeSa -.->|"jobs run as"| bq
  fn -->|"200 JSON / 401 / 4xx / 5xx"| gw
  gw --> vendor
```

## Auth layers

Edge auth, IAM, and application auth are independent controls:

```mermaid
sequenceDiagram
  participant V as Vendor
  participant G as API Gateway
  participant K as API and Services
  participant F as Cloud Function
  participant S as VENDOR_API_KEY
  participant BQ as BigQuery

  V->>G: HTTPS + header key
  G->>K: Validate edge key if configured
  alt edge key invalid
    G-->>V: 403
  else edge OK
    G->>F: Proxy with OIDC Gateway SA
    Note over F: IAM rejects if invoker missing
    F->>S: Load expected secret
    F->>F: hmac.compare_digest provided vs expected
    alt app key invalid
      F-->>G: 401
      G-->>V: 401
    else app key OK
      F->>BQ: Parameterized query Runtime SA
      BQ-->>F: Rows
      F-->>G: 200 JSON
      G-->>V: 200 JSON
    end
  end
```

### IAM + secret checklist

1. Deploy with `--no-allow-unauthenticated`.
2. Grant gateway SA `roles/cloudfunctions.invoker` and Gen2 `roles/run.invoker`.
3. Store `VENDOR_API_KEY` in Secret Manager; mount or inject at runtime. Avoid long-lived plaintext in deploy scripts.
4. Runtime SA: BigQuery job user + data viewer on the dataset only.
5. Rotate vendor keys with the partner on a schedule; invalidate old values by updating the secret, not by editing source.

## Path routing

Gateway OpenAPI in this pattern sets `x-google-backend.address` to `https://BACKEND_URL/getUser` (and siblings). The handler accepts exact path or suffix match so rewrites that preserve the leaf path still work.

If the gateway collapses everything to `/`, prefer fixing OpenAPI backend addresses rather than adding brittle query heuristics for vendor contracts.

## Environment separation

| Concern | Dev | Prod |
|---------|-----|------|
| `PROJECT_ID` / `DATASET_ID` | Dev warehouse | Prod warehouse |
| `VENDOR_API_KEY` | Dev partner key | Prod partner key |
| Gateway / runtime SAs | Dev identities | Prod identities |
| `CORS_ALLOW_ORIGIN` | Staging origin | Vendor / portal origin only |
| OpenAPI `BACKEND_URL` | Dev function URI | Prod function URI |

Do not bake project IDs, table names, or key values into the Python module.
