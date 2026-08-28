# Pattern 03 (Cloud Functions): OIDC outbound HTTP client

Sanitized **outbound** client that pulls a paginated JSON feed from a private Cloud Run (or Gen2 Cloud Functions) HTTPS endpoint using a Google identity token (OIDC). Complements the inbound handler patterns:

- Path-routing analytics handler → [`01-http-handler-behind-gateway/`](../01-http-handler-behind-gateway/)
- Vendor inbound API key check → [`02-vendor-api-key-auth-handler/`](../02-vendor-api-key-auth-handler/)

Those patterns are "someone calls us." This one is "we call a protected service" — the direction that shows up when a batch job, laptop extract, or Cloud Run Job needs to read another team's API without API keys in source.

## Why this pattern

- Cloud Run `--no-allow-unauthenticated` means callers need an ID token whose audience matches the service URL (or configured custom audience).
- Ops scripts often use `gcloud auth print-identity-token`; in-GCP callers should use ADC / `google.oauth2.id_token.fetch_id_token` with `audience=BACKEND_URL`.
- Warehouse and partner feeds are usually paged. Blind single-shot GETs truncate silently; walk until a short page.
- Hardcoded `*.run.app` hostnames and project numbers in scripts become rot the moment you promote environments.

## File index

| File | Purpose |
|------|---------|
| `client.py` | OIDC token helpers, page fetch, pagination, JSON/CSV export |
| `requirements.txt` | `requests`, `google-auth`, optional `pandas` for CSV |
| `run_example.sh` | Placeholder env + small sample pull |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Request path and failure modes |
| `README.md` | This overview |

## Sanitization notes

Derived from `dags/horeca_digital/cloud_functions/prd/extract_tourism_data.py` (read-only GitLab sparse clone).

Removed or replaced:

- Live Cloud Run hostname (`*.run.app` with project number) → `BACKEND_URL`
- Product / regional feed naming → generic catalog / daily endpoints (`getCatalogData`, `getCatalogDailyData`)
- Bare `print` debugging → structured logging without Authorization headers
- Implicit infinite pagination → optional `--max-pages` guard

No API keys, OAuth refresh tokens, or identity tokens are stored in this folder. Tokens are fetched at runtime and never logged.

## Quick start

1. Install deps and set the backend origin (no trailing slash):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export BACKEND_URL=https://SERVICE-HASH.REGION.run.app
```

2. Authenticate as a principal that has `roles/run.invoker` on that service:

```bash
# laptop
gcloud auth login
gcloud auth application-default login

# or rely on Cloud Run Job / Functions runtime SA in GCP
```

3. Pull:

```bash
python client.py --page-size 100 --max-pages 2 --out-json catalog_sample.json
# daily leaf:
python client.py --daily --page-size 100 --out-json catalog_daily.json
```

4. Confirm: wrong SA / missing invoker → **403** from Cloud Run; bad `BACKEND_URL` → connection / 404; empty feed → client exits non-zero after logging.

## Related next patterns

- Apigee proxy / product / KVM (placeholders only) → `apigee/01-...` when notes exist
- Gateway OpenAPI + app-layer key passthrough — only if distinct from patterns 01–04 / 06
