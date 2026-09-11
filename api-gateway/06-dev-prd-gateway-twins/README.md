# Pattern 11: Dev vs prd API Gateway twins

Paired OpenAPI configs for the same public API surface across DEV and PRD. Paths, operationIds, security, and response schemas stay identical; only `x-google-backend.address` (and env-labelled titles) change. A small `check-twins.sh` fails the deploy if contract drift sneaks in.

## Why this pattern

Patterns 01–05 / 09–10 each ship a single sanitized gateway YAML for one surface. In production you almost always keep **two** configs — and that is where real incidents hide:

- DEV drops path-level `security:` while `securityDefinitions` remains (auth looks configured, gateway does not enforce the key)
- Backend function names drift (`…-lookup` vs `…-lookup-gbq`) without documentation
- Definition property types diverge (`integer` in PRD, `string` in DEV) and client generators disagree
- Someone copies the PRD config into the DEV project (or the reverse) and points at the wrong warehouse

This folder is the discipline for that twin pair — not another single-route tutorial.

## File index

| File | Purpose |
|------|---------|
| `openapi.prd.yaml` | Sanitized production twin |
| `openapi.dev.yaml` | Sanitized development twin (same contract, different backend) |
| `check-twins.sh` | Local gate: paths / security / schema types must match; backends must differ |
| `deploy.sh` | Env-aware `gcloud` API + config + gateway deploy (`ENV=prd\|dev`) |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path, twin checks, failure modes |
| `README.md` | This overview |

## Routes covered

| Path | PRD backend placeholder | DEV backend placeholder |
|------|-------------------------|-------------------------|
| `/getActivities` | `REGION-PROJECT_ID.cloudfunctions.net/account-activities-lookup` | `REGION-PROJECT_ID_DEV.cloudfunctions.net/account-activities-lookup` |

## Sanitization notes

Derived from paired source configs:

- `dags/horeca_digital/cloud_functions/prd/dish-360-dashboard-de.yml`
- `dags/horeca_digital/cloud_functions/dev/dish-360-dashboard-de-dev.yml`

Also informed by twin footguns observed on:

- `prd/customer-lookup-co.yml` vs `dev/customer-lookup-co-dev.yml` (DEV dropped path `security:`)
- `prd/dish-menu-engineering-pos.yml` vs `dev/dish-menu-engineering-pos-dev.yml` (clean backend-only diff)

Removed or replaced:

- Product / company branding, contact emails, Jira links
- Real Cloud Function hostnames and GCP project ids → `PROJECT_ID` / `PROJECT_ID_DEV` placeholders
- Query param `metroId` → `accountId`; field `metro_account_identifier` → `account_identifier`
- Email field removed from the response schema (PII not needed for the teaching pattern)
- Source schema type drift (`assigned_id` / `lead_account_id` / `user_id` int vs string) → **aligned to string** in both twins
- Header name normalized to `X-API-Key` (source used `X-API-KEY`)

No API keys or OAuth tokens were present in the source YAML; none are included here.

## Quick start

1. Edit both twins: set `x-google-backend.address` to your DEV and PRD function URLs. Keep paths / security / schemas aligned.
2. Run the contract gate:

```bash
bash check-twins.sh
```

3. Deploy each env separately:

```bash
ENV=dev bash deploy.sh
ENV=prd bash deploy.sh
```

4. Grant each gateway SA invoker on its env backend. Create **separate** API keys; restrict each to its API.
5. Smoke both:

```bash
curl -sS "https://GATEWAY_HOST_DEV/getActivities?accountId=ACC-001" \
  -H "X-API-Key: YOUR_API_KEY_DEV"

curl -sS "https://GATEWAY_HOST/getActivities?accountId=ACC-001" \
  -H "X-API-Key: YOUR_API_KEY"
```

## Related patterns

- Customer lookup (single OpenAPI) → [`../01-customer-lookup-openapi/`](../01-customer-lookup-openapi/)
- Menu-engineering country-split → [`../05-menu-engineering-country-split/`](../05-menu-engineering-country-split/)
- Restricted API key → [`../../api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)
- Env-scoped handler tables → [`../../cloud-run-functions/04-env-scoped-bq-pagination/`](../../cloud-run-functions/04-env-scoped-bq-pagination/)
- Apigee proxy / KVM → `apigee/` (blocked until notes exist)
