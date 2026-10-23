# Architecture: Twin schema fidelity gate

## Components

| Component | Role |
|-----------|------|
| Partner / internal client | Calls the same path against DEV or PRD hostname |
| API Gateway (DEV) | Serves `openapi.dev.yaml`; validates DEV API key |
| API Gateway (PRD) | Serves `openapi.prd.yaml`; validates PRD API key |
| API keys (API & Services) | Separate keys per env; restrict each to its API |
| Cloud Run / Gen2 (DEV) | Dev warehouse extract |
| Cloud Run / Gen2 (PRD) | Prod warehouse extract |
| `check-schema-fidelity.sh` | Deploy gate: `$ref` names, definition keys, typed records, statuses |
| Foreign-ref fixture | Positive control — gate must fail when PRD carries another product's schema |

## Diagram

```mermaid
flowchart TB
  client[Client / SDK generator]
  gwDev[API Gateway DEV]
  gwPrd[API Gateway PRD]
  keyDev[API key DEV]
  keyPrd[API key PRD]
  fnDev[Backend DEV]
  fnPrd[Backend PRD]
  gate[check-schema-fidelity.sh]
  fixture[fixtures/openapi.prd.foreign-ref.yaml]

  gate -.->|"200 $ref names"| gwDev
  gate -.->|"typed records items"| gwPrd
  gate -.->|"status sets + backends differ"| gwDev
  fixture -.->|"--self must FAIL"| gate

  client -->|"X-API-KEY DEV + /getMarketPotentialData"| gwDev
  client -->|"X-API-KEY PRD + /getMarketPotentialData"| gwPrd
  keyDev -.->|"validated at edge"| gwDev
  keyPrd -.->|"validated at edge"| gwPrd
  gwDev -->|"h2 x-google-backend DEV"| fnDev
  gwPrd -->|"h2 x-google-backend PRD"| fnPrd
```

## What must match vs what must differ

```mermaid
flowchart LR
  subgraph match [Must match across twins]
    paths[paths + operationIds]
    auth[ApiKeyAuth name/in + path security]
    ref200[200 schema $ref target names]
    defs[definition key sets]
    typed[records items = typed $ref]
    codes[response status code sets]
  end
  subgraph differ [Must differ]
    backend[x-google-backend.address]
    title[info.title / description labels]
  end
```

| Surface | Rule |
|---------|------|
| Paths / operationIds | Identical |
| Path-level `security:` | Identical (ApiKeyAuth) |
| 200 `$ref` definition name | Identical — no foreign product leftovers |
| `definitions:` keys | Identical sets |
| `records.items` | `$ref` to a record definition — not `additionalProperties: true` |
| Response status codes | Identical sets per operation |
| `x-google-backend.address` | **Different** (`BACKEND_URL` vs `BACKEND_URL_DEV`) |

## Why this sits next to pattern 11

Pattern 11's `check-twins.sh` already fails many of these cases indirectly when
definition property keys diverge. This folder makes the **schema fidelity**
lesson explicit for pagination extracts: foreign `$ref` names and untyped
record bags are first-class failures, with a fixture that proves the gate
works (`--self` must fail).

## Operability notes

1. Run `./check-schema-fidelity.sh` and `./check-schema-fidelity.sh --self`
   in CI before any `api-configs create`.
2. When you rename a definition, rename it in **both** twins in the same PR.
3. Prefer promoting the typed DEV schema into PRD over "simplifying" PRD back
   to `additionalProperties` to silence generator noise.
4. Handler IAM / table selection remain in the Cloud Run service (pattern 08).
