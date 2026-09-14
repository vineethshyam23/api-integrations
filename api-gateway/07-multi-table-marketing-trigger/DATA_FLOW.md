# Data flow: multi-table marketing-trigger extracts

## Happy path (paginated extract)

1. Client sends `GET /triggers/contacts?pageSize=100&pageNumber=1` to `GATEWAY_HOST` with header `X-API-KEY: YOUR_API_KEY`.
2. API Gateway validates the key. Missing / invalid → **403** at the edge (no Cloud Run hop).
3. Gateway proxies to Cloud Run `x-google-backend` address for that path.
4. Handler maps path → `contacts` config, resolves `TRIGGER_CONTACTS_TABLE`, runs shared paginated BigQuery read, returns `{records, pagination}`.
5. Gateway returns that status and body to the client.

## Path branch

```mermaid
sequenceDiagram
  participant C as Client
  participant G as API Gateway
  participant R as Cloud Run
  participant B as BigQuery

  C->>G: GET /triggers/payments?pageSize=50&pageNumber=2 + X-API-KEY
  G->>R: Proxy
  R->>R: PATH_TO_CONFIG → payments + TRIGGER_PAYMENTS_TABLE
  R->>B: SELECT cols … LIMIT @page_size OFFSET @offset
  R->>B: COUNT(*)
  B-->>R: Rows + total
  R-->>G: 200 TriggerPageResponse
  G-->>C: Same status + body
```

Unknown paths stop with **404 Endpoint not found** — no warehouse round trip.

## Fields-metadata path

```mermaid
sequenceDiagram
  participant C as Client
  participant G as API Gateway
  participant R as Cloud Run
  participant B as BigQuery

  C->>G: GET /triggers/fields-metadata + X-API-KEY
  G->>R: Proxy
  R->>B: SELECT src_model, src_field, dest_field, data_type …
  B-->>R: Rows
  R->>R: Group by src_model, sort keys
  R-->>G: 200 model-keyed map
  G-->>C: Same status + body
```

Empty metadata → **404**. No `pageSize` / `pageNumber` on this path.

## Client paging loop

```mermaid
flowchart TD
  start[pageNumber = 1]
  call[GET /triggers/…?pageSize=N&pageNumber=P]
  write[Consume records]
  check{pageNumber < totalPages?}
  next[pageNumber += 1]
  done[Stop or stop on 404]

  start --> call --> write --> check
  check -->|yes| next --> call
  check -->|no| done
```

Treat a **404** (empty page) as end-of-data for that path, not as a transport failure — unless page 1 is empty and you expected rows (then check table env / IAM).

## Failure modes

| Symptom | Likely cause | What to check |
|---------|--------------|---------------|
| 403 at gateway | Bad / missing `X-API-KEY` | Key restriction, header name (`X-API-KEY`), enabled APIs |
| 403 from Cloud Run | Invoker IAM | Gateway SA `roles/run.invoker` |
| 404 Endpoint not found | Typo / undeployed path | OpenAPI paths vs `PATH_TO_CONFIG` |
| 400 on paging | pageSize/pageNumber < 1 or pageSize > 10000 | OpenAPI max + handler caps |
| 404 No data found | Empty table or page past end | Table env; `total` from a known good page |
| 404 No mapping fields | Empty metadata table | `TRIGGER_FIELDS_METADATA_TABLE` |
| 500 from BQ | Table / IAM / column mismatch | Runtime SA; column list vs warehouse; keep detail gated |

## Logging and privacy

- Do not log full API keys.
- Log path + paging dimensions; avoid logging raw emails / phone fields from contact extracts.
- Marketing trigger payloads often include consent flags and establishment identifiers — treat retention like other CRM extracts.
- Correlate gateway request logs with Cloud Run logs when only one path fails (usually a missing `TRIGGER_*_TABLE` or dataset IAM miss).

## Generic sequence

```mermaid
sequenceDiagram
  participant C as Client
  participant G as API Gateway
  participant K as API and Services
  participant R as Cloud Run
  participant B as BigQuery

  C->>G: GET /triggers/… + params + X-API-KEY
  G->>K: Validate API key
  alt invalid key
    G-->>C: 403
  else valid key
    G->>R: Proxy
    alt unknown path / bad paging
      R-->>G: 404 / 400
      G-->>C: Same
    else ok
      R->>B: Parameterized path-scoped query
      B-->>R: Rows or empty
      R-->>G: 200 / 404 / 500
      G-->>C: Same status + body
    end
  end
```
