# Architecture: Env-scoped BigQuery pagination handler

## Components

| Component | Role |
|-----------|------|
| Partner / ETL client | Calls HTTPS with `X-API-KEY` + `countryCode` + pagination |
| API Gateway | Edge OpenAPI, API key validation, path proxy to backend |
| Gateway service account | Invoker identity for Gen2 / Cloud Run |
| HTTP Cloud Function (`main`) | Env resolve, validate, query, JSON |
| `DEPLOY_ENV` / table override | Selects which warehouse table the job reads |
| `EXPOSE_ERROR_DETAIL` | Gates whether 500 bodies include exception text |
| Runtime service account | Identity for BigQuery jobs |
| BigQuery | Dev or prod mart / view for market potential |

## Diagram

```mermaid
flowchart LR
  client[Partner or ETL client]
  gw[API Gateway]
  edgeKey[API and Services key]
  gwSa[Gateway SA]
  fn[HTTP Cloud Function main]
  envCfg[DEPLOY_ENV and table override]
  runtimeSa[Runtime SA]
  bqDev[(BQ PROJECT_ID_DEV)]
  bqProd[(BQ PROJECT_ID)]

  client -->|"GET /getMarketPotentialData + X-API-KEY"| gw
  edgeKey -.->|"validated at edge"| gw
  gw -->|"OIDC as Gateway SA"| fn
  gwSa -.-> fn
  envCfg -.->|"resolve table"| fn
  fn -->|"DEPLOY_ENV=dev"| bqDev
  fn -->|"DEPLOY_ENV=prod"| bqProd
  runtimeSa -.->|"jobs run as"| bqDev
  runtimeSa -.->|"jobs run as"| bqProd
  fn -->|"200 JSON / 4xx / 5xx"| gw
  gw --> client
```

## Environment selection

```mermaid
flowchart TB
  start[Request accepted]
  check{DEPLOY_ENV set?}
  bad[500 — missing or invalid DEPLOY_ENV]
  override{MARKET_POTENTIAL_BQ_TABLE set?}
  useOverride[Use override project.dataset.table]
  useDefault[Use default for dev or prod]
  query[Parameterized COUNT + SELECT]

  start --> check
  check -->|no / invalid| bad
  check -->|dev or prod| override
  override -->|yes| useOverride
  override -->|no| useDefault
  useOverride --> query
  useDefault --> query
```

### Env checklist

| Variable | Required | Notes |
|----------|----------|-------|
| `DEPLOY_ENV` | Yes | Exactly `dev` or `prod` (lowercase) |
| `MARKET_POTENTIAL_BQ_TABLE` | No | Full `project.dataset.table` override |
| `EXPOSE_ERROR_DETAIL` | No | `true` / `1` / `yes` only in non-prod |
| `CORS_ALLOW_ORIGIN` | Recommended | Explicit origin; avoid `*` in prod |

### IAM checklist

1. Deploy with `--no-allow-unauthenticated`.
2. Grant gateway SA `roles/cloudfunctions.invoker` and Gen2 `roles/run.invoker`.
3. Runtime SA: BigQuery job user + data viewer on the **target** dataset only (dev SA ≠ prod SA).
4. Restrict the edge API key to this API in API & Services.
5. Release gate: confirm `DEPLOY_ENV` and `EXPOSE_ERROR_DETAIL` on the Cloud Run revision before traffic.

## Why path backends

OpenAPI sets `x-google-backend.address` to `https://BACKEND_URL/getMarketPotentialData`. The handler accepts exact path or suffix match so gateway rewrites that preserve the leaf still work.

If you later split country extracts across services, update OpenAPI addresses and invoker grants per service — do not encode project IDs in the Python module.
