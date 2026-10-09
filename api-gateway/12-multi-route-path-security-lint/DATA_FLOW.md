# Data flow: multi-route path-security lint

## Happy path

1. Client calls `GET https://GATEWAY_HOST/getVisits?establishmentId=EST_ID`
   with header `X-API-KEY: YOUR_API_KEY`.
2. API Gateway matches the operation, requires `api_key`, validates the key
   binding for this API.
3. Gateway authenticates to the visits Cloud Function as the gateway SA
   (OIDC / IAM invoker).
4. Function runs a parameterized BigQuery read and returns JSON.
5. Same flow for `/getEstablishment`, `/getOrders`, `/getReservations` — each
   with its own backend address.

## Pre-deploy gate

```text
edit openapi.yaml
        |
        v
check-path-security.sh  ----FAIL----> fix missing security: blocks
        |
       OK
        |
        v
deploy.sh (api-config + gateway)
```

Run the gate locally before `deploy.sh`, and again in CI. Also run it against
`fixtures/openapi.missing-path-security.yaml` in a unit job that expects
non-zero exit — that proves the gate still detects the footgun.

## Failure modes

| Symptom | Likely cause | Check |
|---------|--------------|-------|
| 200 without API key on all routes | No path-level `security:` (definitions only) | `check-path-security.sh`; compare to fixture |
| 200 without key on one route only | That operation lost `security:` in a merge | Diff the path block; re-run lint |
| 401 with valid key | Wrong API / key restriction / wrong header name | API & Services restrictions; `X-API-KEY` vs query `key` |
| 403 / permission denied from backend | Gateway SA missing invoker on that function | Four IAM grants — one per backend |
| Lint OK but twin DEV open | Twin file not covered by this single-file gate | Add pattern 11 twin check for DEV/PRD pairs |
| Query `key` works, header fails | Clients still on legacy query scheme | Migrate clients; prefer header in both envs |

## What the lint does not cover

- Scheme **name** vs header **name** mismatches (see patterns 14 / 18 for Bearer)
- Twin contract drift between DEV and PRD (pattern 11 / 16)
- Backend URL equality across twins (pattern 16 pairwise backend gate)
- Application-layer shared-secret checks inside the function
- Full OpenAPI schema validation

Keep this gate narrow on purpose: one failure mode, one clear fix.
