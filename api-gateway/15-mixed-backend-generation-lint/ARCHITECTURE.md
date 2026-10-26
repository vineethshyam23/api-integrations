# Architecture: mixed backend generation lint

## Components

| Component | Role |
|-----------|------|
| Dashboard / partner client | Sends `X-API-KEY: YOUR_API_KEY` |
| API Gateway | One hostname; per-path proxy to Cloud Functions |
| Four Cloud Functions | Establishment / visits / orders / reservations — same generation |
| `check-backend-generation.sh` | Pre-deploy gate: family + separator + `-gbq` parity |
| API & Services key | Credential restricted to this API |
| BigQuery (typical) | Parameterized reads behind each migrated function |

## Request path (aligned)

```mermaid
flowchart LR
  client[Dashboard client]
  gw[API Gateway]
  est["CF panel-establishment-gbq"]
  visits["CF panel-visits-gbq"]
  orders["CF panel-orders-gbq"]
  res["CF panel-reservations-gbq"]

  client -->|"X-API-KEY"| gw
  gw -->|"/getEstablishment"| est
  gw -->|"/getVisits"| visits
  gw -->|"/getOrders"| orders
  gw -->|"/getReservations"| res
```

One family (`panel-`), one separator (`-`), one generation suffix (`-gbq`).
Invoker IAM is four grants on the same naming surface.

## The footgun vs the gate

```mermaid
flowchart TD
  mixed["Mixed backends in one OpenAPI"]
  legacy["panel_establishment"]
  foreign["lookup-getvisits"]
  gbq["panel_orders-gbq / panel_reservations-gbq"]
  ops[On-call / IAM checklist drift]
  lint[check-backend-generation.sh]
  fixed["Aligned panel-*-gbq"]
  deploy[deploy.sh]

  mixed --> legacy
  mixed --> foreign
  mixed --> gbq
  legacy --> ops
  foreign --> ops
  gbq --> ops
  lint -->|"FAIL on fixture"| mixed
  lint -->|"OK on openapi.yaml"| fixed
  fixed --> deploy
```

Partial `-gbq` migration and a foreign `lookup-*` visits backend are the same
class of defect: the gateway hostname implies one platform surface, the
addresses do not.

## Relation to other gates

```mermaid
flowchart LR
  this[Pattern 24 generation lint]
  security[Pattern 19 path-security lint]
  twins[Pattern 16 multi-route twins]

  this -->|"within-file naming"| gate1[Deploy gate]
  security -->|"within-file auth"| gate2[Deploy gate]
  twins -->|"DEV vs PRD URLs"| gate3[Deploy gate]
```

Use this lint on every multi-route OpenAPI PR. Keep pattern 19 for auth wiring.
Add pattern 16 once DEV/PRD twins exist. The three gates answer different
questions; none replaces the others.

## IAM checklist

- Gateway SA: invoker on **each** function (four grants, not one).
- Prefer `--no-allow-unauthenticated` on the functions.
- Restrict platform API keys to this API (see pattern 05).
- Runtime SA: least privilege on the tables each function reads.
- After a generation rename, revoke invoker on the retired function names.
- Never put real keys into OpenAPI examples or the negative fixture.

## Environment separation

Dev and prod differ by project, gateway host, and backend URLs. Keep family /
separator / generation suffix identical across envs even when regions differ.
Do not "temporarily" leave one DEV route on a foreign function name for curl
convenience — that temporary path becomes the production path.
