# Architecture: Multi-route panel dashboard gateway twins

## Components

| Component | Role |
|-----------|------|
| Partner / internal client | Calls the same paths against DEV or PRD hostname |
| API Gateway (DEV) | Serves `openapi.dev.yaml`; validates DEV API key |
| API Gateway (PRD) | Serves `openapi.prd.yaml`; validates PRD API key |
| API keys (API & Services) | Separate keys per env; restrict each to its API |
| Panel Cloud Functions (×5 per env) | Establishment, visits, orders, reservations, POS |
| `check-twins.sh` | Local / CI gate before config create |

## Diagram

```mermaid
flowchart TB
  client[Client]
  gwDev[API Gateway DEV]
  gwPrd[API Gateway PRD]
  keyDev[API key DEV]
  keyPrd[API key PRD]
  twinCheck[check-twins.sh]

  subgraph prdBackends [PRD backends]
    estPrd[establishment REGION_A]
    visitsPrd[visits REGION_B]
    ordersPrd[orders REGION_B]
    resPrd[reservations REGION_B]
    posPrd[POS REGION_A]
  end

  subgraph devBackends [DEV backends]
    estDev[establishment REGION_B]
    visitsDev[visits REGION_B]
    ordersDev[orders REGION_B]
    resDev[reservations REGION_B]
    posDev[POS REGION_B]
  end

  twinCheck -.->|"paths security schemas + pairwise backends"| gwDev
  twinCheck -.->|"paths security schemas + pairwise backends"| gwPrd

  client -->|"X-API-Key DEV + /v2|/v1 paths"| gwDev
  client -->|"X-API-Key PRD + /v2|/v1 paths"| gwPrd
  keyDev -.->|"validated at edge"| gwDev
  keyPrd -.->|"validated at edge"| gwPrd

  gwDev --> estDev
  gwDev --> visitsDev
  gwDev --> ordersDev
  gwDev --> resDev
  gwDev --> posDev

  gwPrd --> estPrd
  gwPrd --> visitsPrd
  gwPrd --> ordersPrd
  gwPrd --> resPrd
  gwPrd --> posPrd
```

## What must match vs what must differ

```mermaid
flowchart LR
  subgraph match [Must match]
    paths[Paths and operationIds]
    sec[security + securityDefinitions]
    schemas[Definition property types]
    params[Query params and date patterns]
  end
  subgraph differ [Must differ]
    backends[Every x-google-backend.address]
    titles[info.title / version labels]
    keys[API keys and gateway hostnames]
  end
  subgraph allowed [Allowed]
    regions[Region mix PRD vs consolidated DEV]
    lagNote[Documented lag vs expanded OpenAPI]
  end
```

## IAM checklist

- Each gateway SA needs invoker on **all five** backends for its env — not just establishment.
- Do not grant the PRD gateway SA invoker on DEV functions "for convenience," and never the reverse.
- Prefer denying public invoker on every backend.
- Restrict each API key to its API / gateway in API & Services.
- Runtime SA on each backend needs warehouse access for that env's datasets — separate from the gateway SA.

## Environment separation

- Separate GCP projects (or at least separate gateway + function names) for DEV and PRD.
- New OpenAPI revision → new `CONFIG_ID`. Never overwrite; never reuse a PRD config id in DEV.
- Keep both twin files in the same folder so reviewers see multi-route diffs in one PR.
- Run `check-twins.sh` in CI on every change to either file.
- When adding a route (for example `/v3/getPOS`), update **both** twins and extend invoker grants before deploy.

## Footguns this architecture avoids

1. **Single-route env leak** — four DEV backends correct, one still PRD; pairwise check fails.
2. **Security drop in DEV** — `securityDefinitions` present, path `security:` missing on some routes.
3. **Duplicate backends within an env** — two paths accidentally share one function URL.
4. **Twin lag without documentation** — PRD-only `/v3` expansion while DEV twin stays at five routes.
5. **Partial invoker grants** — gateway 200 on establishment, 403/500 on POS; looks like "POS is broken" not IAM.
