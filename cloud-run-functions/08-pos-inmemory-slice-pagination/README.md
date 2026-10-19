# Pattern 22: POS KPI in-memory slice pagination (legacy / anti-pattern)

Sanitized HTTP Cloud Function that documents the **v2 POS KPI** paging mistake: BigQuery `LIMIT` without `OFFSET`, then Python list slicing — usually paired with a default `limit` of 9999 so page-2 requests still "work".

This is the museum companion to pattern 15 (SQL pushdown). Keep it while `/v2/getPOS` traffic remains; do not copy it for new services.

Complements:

- Production rewrite → [`../05-pos-daily-transactions-offset-limit/`](../05-pos-daily-transactions-offset-limit/)
- Multi-route dashboard OpenAPI (`/v2` vs `/v3` getPOS) → [`../../api-gateway/02-multi-route-dashboard-openapi/`](../../api-gateway/02-multi-route-dashboard-openapi/)
- Restricted API key at API & Services → [`../../api-and-services-keys/01-restricted-api-key/`](../../api-and-services-keys/01-restricted-api-key/)

## Why this pattern

- Pattern 15 already explains the fix in prose; teams still ask for the original shape when reviewing migrations.
- CI needs a positive control (`./check-inmemory-slice-smell.sh --self`) and a gate for other handlers.
- Gateway path versioning alone does not teach why v2 burned bytes and returned false 404s.

## File index

| File | Purpose |
|------|---------|
| `main.py` | Legacy `lookup` handler with intentional smells called out |
| `openapi.yaml` | Companion OpenAPI for `/v2/getPOS` |
| `requirements.txt` | Runtime dependencies |
| `deploy.sh` | Example Gen2 deploy (placeholders; higher memory note) |
| `check-inmemory-slice-smell.sh` | Multi-signal smell gate (`--self` expects FAIL) |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path and false-negative modes |
| `README.md` | This overview |

## Sanitization notes

Derived from `dags/horeca_digital/cloud_functions/prd/dish-panel-pos-gbq-v2.py`.

Removed or replaced:

- Product / company naming and real dataset / table identifiers → `DATASET_ID.pos_kpi_snapshot` / `POS_KPI_TABLE`
- Real GCP project IDs → `PROJECT_ID` / legacy `ENV` placeholder
- Live Cloud Function hostnames → `REGION-PROJECT_ID.cloudfunctions.net/panel-pos-v2`
- Payment-channel column typos / locale labels → `contact` / `card` / `online` / `invoice` (aligned with dashboard OpenAPI)
- Unused `flask.escape` / `abort` imports dropped

Intentionally **kept** (teaching):

- Format-string SQL for id + LIMIT
- In-memory `buffer[offset:offset+limit]` after warehouse LIMIT
- Default limit `9999`
- Unused `startDate` / `endDate`
- `ENV` as BigQuery project env name
- Bare `except` → 404
- Double-`jsonify` defect on the empty-page return path

No API keys or OAuth tokens from source are included.

## Quick start

1. Confirm the smell gate fails on this museum handler (expected):

```bash
chmod +x check-inmemory-slice-smell.sh
./check-inmemory-slice-smell.sh --self
# expect exit 1
```

2. Point the gate at a production rewrite (expect OK):

```bash
./check-inmemory-slice-smell.sh ../05-pos-daily-transactions-offset-limit/main.py
# expect exit 0
```

3. Demo deploy only if you still need `/v2/getPOS` live (prefer retiring it):

```bash
export PROJECT_ID=PROJECT_ID
export REGION=europe-west1
export ENV=PROJECT_ID
export DATASET_ID=DATASET_ID
chmod +x deploy.sh
./deploy.sh
```

4. Call via gateway:

```bash
curl -sS -H "X-API-Key: YOUR_API_KEY" \
  "https://GATEWAY_HOST/v2/getPOS?establishmentId=EST-1001&offset=0&limit=20"
```

5. Reproduce the classic false empty page (do not "fix" by raising limit in new code):

```bash
curl -sS -H "X-API-Key: YOUR_API_KEY" \
  "https://GATEWAY_HOST/v2/getPOS?establishmentId=EST-1001&offset=20&limit=20"
# Often 404 even when more rows exist — warehouse returned only 20 rows.
```

## Related next patterns

- Apigee proxy / product / KVM (placeholders only) → `apigee/01-...` when `Documents/API` notes exist
- POS establishment header-key lookup OpenAPI → only if clearly unique vs pattern 01
- Dana helpdesk tickets → only if distinct from pattern 09
