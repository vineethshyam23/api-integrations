# Architecture: POS KPI in-memory slice pagination (legacy)

## Components

| Component | Role |
|-----------|------|
| Panel / partner client | Still calls `/v2/getPOS` during migration |
| API Gateway | Edge OpenAPI, API key validation, path proxy |
| Gateway service account | Invoker identity for Gen2 / Cloud Run |
| HTTP Cloud Function (`lookup`) | Legacy body: LIMIT in BQ, slice in Python |
| `ENV` / `POS_KPI_TABLE` | Opaque project name + optional table override |
| Runtime service account | Identity for BigQuery jobs |
| BigQuery | POS KPI snapshot / mart |
| Smell gate script | CI check against *other* handlers (and `--self`) |

## Diagram

```mermaid
flowchart LR
  client[Panel or partner client]
  gw[API Gateway]
  edgeKey[API and Services key]
  gwSa[Gateway SA]
  fn[HTTP Cloud Function lookup v2]
  envCfg["ENV + POS_KPI_TABLE"]
  runtimeSa[Runtime SA]
  bq[(BigQuery POS KPI)]
  mem[Python list slice]

  client -->|"GET /v2/getPOS + X-API-Key"| gw
  edgeKey -.->|"validated at edge"| gw
  gw -->|"OIDC as Gateway SA"| fn
  gwSa -.-> fn
  envCfg -.->|"resolve project/table"| fn
  fn -->|"SELECT ... LIMIT N only"| bq
  runtimeSa -.->|"jobs run as"| bq
  bq -->|"up to N rows"| mem
  mem -->|"offset:offset+limit"| fn
  fn -->|"200 records / 4xx"| gw
  gw --> client
```

## Why this burns money and correctness

```mermaid
flowchart TB
  subgraph bad["v2 this pattern"]
    q1["SQL LIMIT = client limit"]
    s1["Python buffer offset:offset+limit"]
    q1 --> s1
    s1 -->|"offset greater than N"| empty["False empty page / 404"]
    s1 -->|"raise default limit to 9999"| waste["Large scan + RAM buffer"]
  end

  subgraph good["v3 pattern 15"]
    q2["SQL LIMIT @limit OFFSET @offset"]
    s2["Build records from page only"]
    q2 --> s2
  end
```

### Env checklist (legacy)

| Variable | Required | Notes |
|----------|----------|-------|
| `ENV` | Yes* | Legacy name for the BigQuery *project* — prefer `BQ_PROJECT_ID` on new code |
| `DATASET_ID` | Recommended | Used when `POS_KPI_TABLE` unset |
| `POS_KPI_TABLE` | No | Full `project.dataset.table` or `dataset.table` override |
| `POS_KPI_TABLE_ID` | No | Table leaf when building from dataset |

\* Or set `POS_KPI_TABLE` to a fully qualified table and still expect `ENV` if the Client needs an explicit project.

### IAM checklist

1. Deploy with `--no-allow-unauthenticated`.
2. Grant gateway SA `roles/cloudfunctions.invoker` and Gen2 `roles/run.invoker`.
3. Runtime SA: BigQuery job user + data viewer on the POS KPI dataset only.
4. Restrict the edge API key to this API in API & Services.
5. Plan retirement: flip `/v2/getPOS` traffic to pattern 15 or delete the path after clients migrate.

## Operability note

Memory sizing on this revision often crept from 256Mi toward 512Mi+ because the default limit pulled large buffers. That is a smell, not a capacity plan — fix the query shape instead of forever raising memory.
