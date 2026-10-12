# Pattern 07 (Cloud Functions) / Pattern 20 overall: Account-composition DE lookup

Sanitized HTTP Cloud Function for **country-scoped account activity lookup** with backend account-id composition, zero-stripped metro/store matching, and an OR-union of identity strategies (including `ArrayQueryParameter` + `UNNEST`). Focus is the compose / OR-union contract that pair-required filter APIs cannot express.

Complements:

- Multi-filter tickets OpenAPI (paired metro+store, AND filters) → [`api-gateway/04-multi-filter-tickets-openapi/`](../../api-gateway/04-multi-filter-tickets-openapi/)
- POS daily-transactions offset/limit → [`05-pos-daily-transactions-offset-limit/`](../05-pos-daily-transactions-offset-limit/)
- Restricted API key at API & Services → [`api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)

Edge API keys and backend IAM still apply. This pattern is about how the **backend resolves messy account identity** before paging warehouse activity.

## Why this pattern

- Callers disagree on whether they hold metro+store, a composed account id, or both.
- Leading-zero padding differs across UI generations; warehouse columns may store padded or stripped forms.
- Hard-coding a national prefix and a live GCP project in source makes the handler non-portable and unsafe to publish.
- Returning contact email in a teaching exemplar widens PII surface without teaching anything about composition.

## File index

| File | Purpose |
|------|---------|
| `main.py` | `lookup` HTTP entry point, compose + OR-union + parameterized SQL page read |
| `requirements.txt` | Runtime dependencies |
| `deploy.sh` | Example Gen2 deploy + invoker bindings (placeholders) |
| `openapi.yaml` | Sanitized companion OpenAPI for `/account-activity` |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path, identity paths, failure modes |
| `README.md` | This overview |

## Sanitization notes

Derived from `dags/horeca_digital/cloud_functions/prd/dashboard_360_de_lookup.py`.

Removed or replaced:

- Product / company naming and real dataset / table identifiers → `DATASET_ID.account_activity_lookup`
- Real GCP project ids and vague `ENV` project env → `BQ_PROJECT_ID` / `PROJECT_ID`
- Hard-coded national account prefix → `ACCOUNT_ID_PREFIX` / `COUNTRY_ACCOUNT_PREFIX`
- Live Cloud Function / Cloud Run hostnames → `BACKEND_URL`
- Path / operation naming tied to a specific dashboard product → `/account-activity`
- Contact email column from response payload (PII) — omitted from `RETURN_COLUMNS`
- Bare exception text in 500 responses → gated `EXPOSE_ERROR_DETAIL`
- Source default `limit=9999` → default 100 with hard cap 1000
- Inline company examples in comments → generic layout documentation

No API keys or OAuth tokens from source are included. Prefix and table values in docs are placeholders only.

## Quick start

1. Set placeholders:

```bash
export PROJECT_ID=PROJECT_ID
export REGION=europe-west1
export BQ_PROJECT_ID=PROJECT_ID
export DATASET_ID=DATASET_ID
export ACCOUNT_ID_PREFIX=COUNTRY_ACCOUNT_PREFIX
export EXPOSE_ERROR_DETAIL=true
chmod +x deploy.sh
./deploy.sh
```

2. Point gateway OpenAPI `x-google-backend.address` for `/account-activity` at the function URI (see `openapi.yaml`).

3. Call via gateway:

```bash
curl -sS -H "X-API-Key: YOUR_API_KEY" \
  "https://GATEWAY_HOST/account-activity?metroId=154530&storeId=58&offset=0&limit=50"

curl -sS -H "X-API-Key: YOUR_API_KEY" \
  "https://GATEWAY_HOST/account-activity?metroAccountIdentifier=COUNTRY_ACCOUNT_PREFIX05800154530&limit=20"
```

4. Confirm: missing both identity params → **400**; empty page → **404**; wrong prefix at deploy → silent 404 (check env); prod keeps `EXPOSE_ERROR_DETAIL=false`.

## Related next patterns

- Apigee proxy / product / KVM (placeholders only) → `apigee/01-...` when `Documents/API` notes exist
- Tourism Bearer limit/offset OpenAPI → only if still unique vs pattern 13 / 18
- POS establishment lookup OpenAPI → only if clearly unique vs pattern 01
