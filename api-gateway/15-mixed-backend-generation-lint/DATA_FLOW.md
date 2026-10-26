# Data flow: mixed backend generation lint

## Happy path

1. Client calls `GET https://GATEWAY_HOST/getVisits?establishmentId=EST_ID`
   with header `X-API-KEY: YOUR_API_KEY`.
2. API Gateway matches the operation, requires `api_key`, validates the key
   binding for this API.
3. Gateway authenticates to `panel-visits-gbq` as the gateway SA
   (OIDC / IAM invoker).
4. Function runs a parameterized BigQuery read and returns JSON.
5. Same flow for `/getEstablishment`, `/getOrders`, `/getReservations` — each
   with its own `panel-*-gbq` backend.

## Pre-deploy gate

```text
edit openapi.yaml
        |
        v
check-backend-generation.sh  ----FAIL----> finish migration / rename backends
        |
       OK
        |
        v
deploy.sh (api-config + gateway)
```

Run the gate locally before `deploy.sh`, and again in CI. Also run
`check-backend-generation.sh --self` in a unit job — that proves the fixture
still fails and the aligned exemplar still passes.

## What the lint checks

| Check | Fail when | Fix |
|-------|-----------|-----|
| Generation suffix parity | Some backends end in `-gbq` / `_gbq`, others do not | Finish the rewrite or split into two APIs |
| Separator style | Underscore names mixed with hyphen names | Rename to one style (`panel-…` preferred) |
| Family token | First token after stripping env/version/gbq differs | Retire foreign `lookup-*` (etc.) under the panel family |

## Failure modes

| Symptom | Likely cause | Check |
|---------|--------------|-------|
| Lint fails on partial `-gbq` | Mid-migration OpenAPI | Align all four addresses or cut over via a new API id |
| Lint fails on family drift | Visits still on `lookup-*` | Point visits at `panel-visits-gbq`; revoke old invoker |
| Lint fails on separator drift | `_` and `-` mixed in one file | Normalize names before deploy |
| 403 on one route only | Gateway SA missing invoker on the odd function | Four IAM grants — names must match the OpenAPI |
| Lint OK but DEV shares PRD URL | Twin file not covered by this gate | Add pattern 16 pairwise backend check |
| 401 with valid key | Wrong API / key restriction / wrong header name | API & Services; `X-API-KEY` vs query `key` |

## What the lint does not cover

- Path-level `security:` presence (pattern 19)
- Twin contract / backend inequality between DEV and PRD (pattern 11 / 16)
- Schema fidelity of response `$ref` names (pattern 23)
- Application-layer auth inside the function
- Full OpenAPI schema validation
- Intentional dual-generation cutovers (use a second API or a short allowlist)

Keep this gate narrow: one failure mode class (backend naming generation), one
clear fix (align the addresses).
