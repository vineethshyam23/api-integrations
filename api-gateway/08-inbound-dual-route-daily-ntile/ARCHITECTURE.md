# Architecture: inbound dual-route daily NTILE via API Gateway

## Components

| Component | Role |
|-----------|------|
| Partner / destination client | Calls `/establishments` or `/establishments/daily` with `X-API-KEY` + paging |
| API Gateway | Validates key; proxies each path to the same Cloud Run service |
| API key (API & Services) | Credential restricted to this API / gateway |
| Cloud Run service | Path branch → full catalog or daily NTILE BQ read |
| BigQuery catalog table | Full refined establishment snapshot |
| BigQuery daily table | Source for NTILE day-of-month buckets |

## Diagram

```mermaid
flowchart LR
  client[Partner client]
  gw[API Gateway]
  key[API and Services key]
  run[Cloud Run establishments-inbound]
  bqFull[BQ establishments]
  bqDaily[BQ establishments_daily]

  client -->|"X-API-KEY + pageSize/pageNumber"| gw
  key -.->|"validated at edge"| gw
  gw -->|"proxy /establishments*"| run
  run -->|"/establishments"| bqFull
  run -->|"/establishments/daily"| bqDaily
```

## Path branch and empty semantics

```mermaid
flowchart TD
  req[Incoming GET]
  route{path}
  full[fetch_full_catalog]
  daily[fetch_daily_bucket]
  hard404[404 No data found]
  soft200["200 records=[] + message"]
  ok200[200 records + pagination]
  bad[404 Invalid endpoint]

  req --> route
  route -->|"/establishments"| full
  route -->|"/establishments/daily"| daily
  route -->|other| bad
  full -->|rows| ok200
  full -->|empty| hard404
  daily -->|first-of-month or empty bucket| soft200
  daily -->|rows| ok200
```

## Daily NTILE selection

```mermaid
flowchart LR
  cal[Calendar: days_in_month - 1]
  yday[Yesterday day-of-month]
  ntile["NTILE(bucket_count) OVER (ORDER BY establishment_id)"]
  page[LIMIT @page_size OFFSET @offset]
  env["{records, pagination} or soft empty"]

  cal --> ntile
  yday --> ntile
  ntile --> page --> env
```

Bucket count is `days_in_month - 1`. Bucket index is yesterday's day-of-month. First calendar day short-circuits to soft empty before querying — the daily pipeline is often idle then.

## IAM checklist

- Gateway SA needs `roles/run.invoker` on the Cloud Run service.
- Prefer denying public invoker on Cloud Run; only the gateway SA should call it.
- Restrict the API key to this API in API & Services; rotate keys without redeploying the service.
- Runtime SA needs BigQuery job user + data viewer on **both** catalog and daily datasets — easy to grant only one and break a single path.

## Environment separation

- Dev vs prod: different `x-google-backend.address` hosts and different `ESTABLISHMENTS_*_TABLE` values.
- Prefer Secret Manager / `--set-secrets` for table ids; avoid baking project ids into the image.
- Keep `EXPOSE_ERROR_DETAIL=false` in prod.
- When renaming paths: update OpenAPI + handler route checks in the same change set.

## Why include the handler here

Gateway YAML shows two nearly identical paging contracts. The production risk is the **asymmetric empty semantics** and the NTILE calendar math. Shipping `main.py` makes those choices visible next to the OpenAPI, not buried in a private Functions repo.
