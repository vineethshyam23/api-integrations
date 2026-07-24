# Data flow: Multi-route dashboard

## Happy path (example: visits)

1. Client sends `GET /v1/getVisits?establishmentId=<id>&limit=20` to `GATEWAY_HOST` with header `X-API-Key: YOUR_API_KEY`.
2. API Gateway validates the key. Missing / invalid → **403** at the edge (no backend hop).
3. Gateway matches the path to `x-google-backend.address` for `/v1/getVisits` and proxies the request.
4. Visits function validates params, queries its store, returns a JSON array of visit rows.
5. Gateway returns that status and body to the client.

Other routes follow the same edge auth + path-specific backend hop. Only the function URL and response schema change.

## Versioned POS migration

```mermaid
sequenceDiagram
  participant C as Client
  participant G as API Gateway
  participant P2 as panel-pos-v2
  participant P3 as panel-pos-v3

  Note over C,P3: During migration both routes stay live
  C->>G: GET /v2/getPOS + X-API-Key
  G->>P2: Proxy
  P2-->>G: PosKpiV2 JSON
  G-->>C: 200

  C->>G: GET /v3/getPOS + X-API-Key
  G->>P3: Proxy
  P3-->>G: PosKpiV3 JSON
  G-->>C: 200
```

Retire `/v2/getPOS` only after clients move. Removing a path is a new API config id + gateway update.

## Failure modes

| Symptom | Likely cause | What to check |
|---------|--------------|---------------|
| 403 at gateway | Bad / missing `X-API-Key` | Key restriction, header name, enabled APIs |
| 403 from one route only | Function IAM on that backend | Gateway SA invoker on **that** function |
| 404 establishment | Unknown id | Backend lookup / source table |
| 400 on dates | Pattern mismatch | Clients send `DD-MM-YYYY` for this API |
| 504 / deadline on POS | Heavy query / cold start | Raise path `deadline`; fix function latency |
| One route 500, others OK | Isolated backend fault | Logs for that function only |

## Logging and privacy

- Do not log full API keys. Prefer consumer project / key fingerprint if available.
- `establishmentId` is often customer-identifying — apply the same retention rules as other account identifiers.
- Correlate gateway request logs with function logs using request IDs when a single path misbehaves.

## Generic sequence

```mermaid
sequenceDiagram
  participant C as Client
  participant G as API Gateway
  participant K as API and Services
  participant F as Path-specific function

  C->>G: GET /v1/... + X-API-Key
  G->>K: Validate API key
  alt invalid key
    G-->>C: 403
  else valid key
    G->>F: Proxy by path
    F-->>G: 200 JSON / 4xx / 5xx
    G-->>C: Same status + body
  end
```
