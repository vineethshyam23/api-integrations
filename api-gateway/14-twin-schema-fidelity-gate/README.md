# Pattern 23: Twin schema fidelity gate

Paired OpenAPI configs for a **paginated market-potential extract** where DEV
and PRD must share the same 200 `$ref` names, definition key sets, typed
`records.items`, and response status codes. Backends differ. A
`check-schema-fidelity.sh` gate fails on the copy-paste footgun: PRD still
points at another product's response model with `additionalProperties: true`
while DEV already ships typed records.

Companion to:

→ [`../06-dev-prd-gateway-twins/`](../06-dev-prd-gateway-twins/)
(pattern 11 — security / path / property-type twin gate)

→ [`../../cloud-run-functions/04-env-scoped-bq-pagination/`](../../cloud-run-functions/04-env-scoped-bq-pagination/)
(pattern 08 — handler + single companion OpenAPI)

Do not confuse with:

- Pattern 11 — twin discipline focused on security drop and prop types
- Pattern 08 — runtime `DEPLOY_ENV` table selection; one OpenAPI file
- Pattern 16 — multi-route panel twins
- Pattern 19 — single-file path-security lint (no twin yet)

## Why this pattern

Pagination extracts get cloned from a working marketing/CX OpenAPI. The path
and `operationId` get renamed; the 200 `$ref` still says
`OtherProductDataResponse` / `MaileonDataResponse`. Records stay an untyped
object bag. DEV is later tightened with `MarketPotentialRecord`. Generators
and contract tests then disagree by environment. Pattern 11's gate may notice
property-key drift, but the teaching point here is explicit: **foreign `$ref`
names and untyped records are deploy blockers**, proven with a `--self`
fixture.

## File index

| File | Purpose |
|------|---------|
| `openapi.prd.yaml` | Sanitized production twin (typed `MarketPotentialResponse`) |
| `openapi.dev.yaml` | Sanitized development twin (same contract, DEV backend) |
| `fixtures/openapi.prd.foreign-ref.yaml` | Negative fixture — foreign `$ref` + untyped records + extra 403 |
| `check-schema-fidelity.sh` | Gate + `--self` positive control |
| `deploy.sh` | Env-aware API Gateway deploy; runs the gate first |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path, gate flow, failure modes |
| `README.md` | This overview |

## Routes covered

| Path | PRD backend | DEV backend | Auth | Envelope |
|------|-------------|-------------|------|----------|
| `/getMarketPotentialData` | `https://BACKEND_URL/getMarketPotentialData` (h2) | `https://BACKEND_URL_DEV/getMarketPotentialData` (h2) | `ApiKeyAuth` → `X-API-KEY` | `{ records, pagination }` typed |

## Sanitization notes

Derived from paired source configs:

- `dags/horeca_digital/cloud_functions/prd/pos_potential_sam_api_integrated.yml`
- `dags/horeca_digital/cloud_functions/dev/pos_potential_sam_api_integrated_dev.yml`

Source footguns kept as the **negative fixture**, not as the deployable twins:

- PRD 200 `$ref` named after another product + `records.items.additionalProperties: true`
- DEV typed `PosPotentialSamResponse` / record / pagination split
- Response status set drift (extra 403 on PRD only)

Removed or replaced in the aligned twins:

- Product / company branding, contact emails, internal license text
- Real Cloud Run hostnames and GCP project ids → `BACKEND_URL` / `BACKEND_URL_DEV`
- Path kept as `/getMarketPotentialData` (generic extract leaf; matches pattern 08 naming)
- Record field `cust_no` → `customer_no`
- Foreign response definition names → `MarketPotentialResponse` /
  `MarketPotentialRecord` / `Pagination` on **both** twins
- Status codes aligned (dropped the unpaired PRD-only 403 from the exemplar)

No API keys or OAuth tokens were present as secret material in the source YAML;
none are included here. Python handler remains pattern 08.

## Quick start

1. Edit both twins: set `x-google-backend.address` to your DEV and PRD Cloud Run
   URLs + `/getMarketPotentialData`. Keep `$ref` names and typed records aligned.
2. Prove the gate:

```bash
./check-schema-fidelity.sh
./check-schema-fidelity.sh --self   # must fail (exit non-zero), then print OK
```

3. Deploy one env:

```bash
ENV=dev ./deploy.sh
ENV=prd ./deploy.sh
```

4. Call via gateway:

```bash
curl -sS -H "X-API-KEY: YOUR_API_KEY" \
  "https://GATEWAY_HOST/getMarketPotentialData?countryCode=DE&pageSize=100&pageNumber=1"
```

## Related

- Env-scoped handler → [`cloud-run-functions/04-env-scoped-bq-pagination/`](../../cloud-run-functions/04-env-scoped-bq-pagination/)
- Security/path twin gate → [`../06-dev-prd-gateway-twins/`](../06-dev-prd-gateway-twins/)
- Restricted API keys → [`../../api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)
