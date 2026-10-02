# Architecture: GA dual-path analytics handler

## Components

| Component | Role |
|-----------|------|
| Client / ETL job | Calls HTTPS with `X-API-Key` + route-specific query params |
| API Gateway | Edge OpenAPI, API key validation, path proxy to one backend |
| Gateway service account | Invoker identity for Gen2 / Cloud Run |
| HTTP Cloud Function (`lookup`) | Route resolve → parameterized query → JSON envelope |
| Path / header inputs | `path`, `X-Forwarded-Path`, `X-Envoy-Original-Path`, `X-Original-URI` |
| Env config | `BQ_PROJECT_ID`, public dataset, optional table overrides |
| Runtime service account | Identity for BigQuery jobs |
| BigQuery | Public sample (or overridden) daily visits / ga_sessions shards |

## Diagram

```mermaid
flowchart LR
  client[Client or ETL job]
  gw[API Gateway]
  edgeKey[API and Services key]
  gwSa[Gateway SA]
  fn[HTTP Cloud Function lookup]
  router[Route resolver]
  flatQ[daily-visits query]
  nestQ[ga-sessions query]
  envCfg[BQ_PROJECT_ID and table overrides]
  runtimeSa[Runtime SA]
  bq[(BigQuery analytics tables)]

  client -->|"GET /daily-visits or /ga-sessions-data"| gw
  edgeKey -.->|"validated at edge"| gw
  gw -->|"OIDC as Gateway SA + path headers"| fn
  gwSa -.-> fn
  fn --> router
  envCfg -.-> fn
  router -->|"/daily-visits"| flatQ
  router -->|"/ga-sessions-data or default"| nestQ
  flatQ -->|"parameterized SELECT"| bq
  nestQ -->|"parameterized SELECT + STRUCT"| bq
  runtimeSa -.->|"jobs run as"| bq
  fn -->|"200 envelope / 4xx / 5xx"| gw
  gw --> client
```

## Route resolution

```mermaid
flowchart TB
  start[Collect path sources]
  pathCheck{Explicit path match?}
  paramCheck{Param heuristic unambiguous?}
  daily[Serve daily-visits]
  ga[Serve ga-sessions]
  default[Default to ga-sessions]

  start --> pathCheck
  pathCheck -->|"only /daily-visits"| daily
  pathCheck -->|"only /ga-sessions-data"| ga
  pathCheck -->|"none / both"| paramCheck
  paramCheck -->|"only start_date/end_date"| daily
  paramCheck -->|"only date/country/device"| ga
  paramCheck -->|"ambiguous"| default
```

### Env checklist

| Variable | Required | Notes |
|----------|----------|-------|
| `BQ_PROJECT_ID` | Recommended | Job/billing project for the BigQuery client |
| `PUBLIC_PROJECT_ID` | No | Defaults to `bigquery-public-data` |
| `GA_DATASET_ID` | No | Defaults to `google_analytics_sample` |
| `DAILY_VISITS_TABLE` | No | Full `project.dataset.table` override |
| `GA_SESSIONS_TABLE_TEMPLATE` | No | Template with `{date}` for shard tables |
| `EXPOSE_ERROR_DETAIL` | No | `true` / `1` / `yes` only in non-prod |
| `CORS_ALLOW_ORIGIN` | No | Defaults to `*` — set a concrete origin in prod |

### IAM checklist

1. Deploy with `--no-allow-unauthenticated`.
2. Grant gateway SA `roles/cloudfunctions.invoker` and Gen2 `roles/run.invoker`.
3. Runtime SA: BigQuery job user; data viewer on the sample or overridden datasets.
4. Restrict the edge API key to this API in API & Services.
5. Release gate: confirm both OpenAPI backends share this URI and path suffixes match the resolver strings.

## Why one backend

Two low-traffic extract routes do not justify two Cloud Run services. The cost is careful route resolution and structured logging of which path source won. Prefer separate backends only when SLOs, scaling, or blast radius diverge.
