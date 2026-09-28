# Pattern 16: Multi-route panel dashboard gateway twins

Paired OpenAPI configs for a **five-route** establishment dashboard across DEV and PRD. Paths, operationIds, security, and response schemas stay identical; every `x-google-backend.address` differs. A `check-twins.sh` gate fails if any single route still points at the same backend URL — the multi-route footgun pattern 11 cannot see.

## Why this pattern

Pattern 03 ships one sanitized multi-route OpenAPI. Pattern 11 ships twin discipline for a **single** path. Real panel dashboards combine both: several independent Cloud Functions behind one hostname, and a DEV twin that must not silently share a PRD backend on "just visits."

Production details this folder preserves as teaching points:

- **Per-route backends** — establishment / visits / orders / reservations / POS each have their own function; invoker IAM is five grants, not one
- **Region mix** — PRD may keep establishment + POS in `REGION_A` and the rest in `REGION_B`; DEV may consolidate into one region. That is allowed. Identical URLs are not.
- **Twin lag** — this surface stops at `/v2/getPOS`. An expanded OpenAPI (see pattern 03 source lineage) may add `/v3/getPOS`; do not add that path to one twin only
- **Version title drift** — `info.version` / `info.title` may differ between envs; contract fields must not

## File index

| File | Purpose |
|------|---------|
| `openapi.prd.yaml` | Sanitized production twin (five routes) |
| `openapi.dev.yaml` | Sanitized development twin (same contract, DEV backends) |
| `check-twins.sh` | Gate: paths / security / schemas match; **every** backend differs pairwise |
| `deploy.sh` | Env-aware `gcloud` API + config + gateway deploy (`ENV=prd\|dev`) |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path, twin checks, failure modes |
| `README.md` | This overview |

## Routes covered

| Path | PRD backend placeholder | DEV backend placeholder |
|------|-------------------------|-------------------------|
| `/v2/getEstablishment` | `REGION_A-PROJECT_ID…/panel-establishment-gbq-v2` | `REGION_B-PROJECT_ID_DEV…/panel-establishment-dev-gbq-v2` |
| `/v1/getVisits` | `REGION_B-PROJECT_ID…/panel-visits-gbq` | `REGION_B-PROJECT_ID_DEV…/panel-visits-dev-gbq` |
| `/v1/getOrders` | `REGION_B-PROJECT_ID…/panel-orders-gbq` | `REGION_B-PROJECT_ID_DEV…/panel-orders-dev-gbq` |
| `/v1/getReservations` | `REGION_B-PROJECT_ID…/panel-reservations-gbq` | `REGION_B-PROJECT_ID_DEV…/panel-reservations-dev-gbq` |
| `/v2/getPOS` | `REGION_A-PROJECT_ID…/panel-pos-gbq-v2` | `REGION_B-PROJECT_ID_DEV…/panel-pos-dev-gbq-v2` |

## Sanitization notes

Derived from paired source configs:

- `dags/horeca_digital/cloud_functions/prd/hd-dish-panel-dashboard-gbq_v2.yml`
- `dags/horeca_digital/cloud_functions/dev/hd-dish-panel-dashboard-dev-gbq_v2.yml`

Contrast (not copied into this twin pair):

- `prd/dish_pos_openapi_spec.yml` — same surface plus `/v3/getPOS` (pattern 03 lineage). Twin files here intentionally stay at five routes so "expand both twins together" stays visible.

Removed or replaced:

- Product / company branding and placeholder documentation URLs
- Real Cloud Function hostnames and GCP project ids → `REGION_A` / `REGION_B` / `PROJECT_ID` / `PROJECT_ID_DEV`
- CRM vendor naming (`Salesforce ID` → CRM customer identifier)
- Product-flag field names (`has_Dish_*` → `has_website`, `has_pos`, …)
- Locale-specific payment channel labels → generic channel names
- Header name kept as `X-API-Key` (source already used that casing)

No API keys or OAuth tokens were present in the source YAML; none are included here.

## Quick start

1. Edit both twins: set each `x-google-backend.address` to your DEV and PRD function URLs. Keep paths / security / schemas aligned. Region mix is fine; identical URLs are not.
2. Run the contract gate:

```bash
bash check-twins.sh
```

3. Deploy each env separately:

```bash
ENV=dev bash deploy.sh
ENV=prd bash deploy.sh
```

4. Grant each gateway SA invoker on **all five** backends for that env. Create **separate** API keys; restrict each to its API.
5. Smoke both:

```bash
curl -sS "https://GATEWAY_HOST_DEV/v2/getEstablishment?establishmentId=EST-001" \
  -H "X-API-Key: YOUR_API_KEY_DEV"

curl -sS "https://GATEWAY_HOST/v1/getVisits?establishmentId=EST-001&limit=20" \
  -H "X-API-Key: YOUR_API_KEY"
```

## Related patterns

- Multi-route dashboard OpenAPI (single file, includes `/v3/getPOS`) → [`../02-multi-route-dashboard-openapi/`](../02-multi-route-dashboard-openapi/)
- Single-route DEV/PRD twin discipline → [`../06-dev-prd-gateway-twins/`](../06-dev-prd-gateway-twins/)
- POS daily-transactions offset/limit handler (`/v3` shape) → [`../../cloud-run-functions/05-pos-daily-transactions-offset-limit/`](../../cloud-run-functions/05-pos-daily-transactions-offset-limit/)
- Restricted API key → [`../../api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)
