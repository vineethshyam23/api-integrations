# Business case: OIDC outbound pull from Cloud Run

## Problem

Inbound API patterns (gateway + Cloud Function) answer "how do partners call us?" A different failure mode shows up on the data platform side: a job or extract needs to **pull** from another team's private HTTPS service. Teams then do one of three bad things:

1. Turn the target service public "just for the extract."
2. Paste a long-lived API key into a script or DAG variable and forget rotation.
3. Hardcode the Cloud Run URL (including project number) and break on every environment promote.

This pattern is the sanitized outbound half: identity token to a private Cloud Run URL, paginated GET, environment-driven base URL.

## Constraints that mattered

- Target is Cloud Run / Gen2 with IAM invokers only — not an API key product.
- Callers include both laptop/ops (`gcloud`) and in-GCP workloads (ADC / runtime SA).
- Feed contracts use `pageSize` / `pageNumber` and a `records` array — walk until short page.
- Dev and prod backends differ by hostname; the script must not embed either.
- Logs must never include Bearer tokens or full Authorization headers.

## Decision

Ship a small **Python client** that:

1. Resolves `BACKEND_URL` from env (fail closed on missing / placeholder values).
2. Obtains an OIDC ID token — prefer `google.oauth2.id_token.fetch_id_token(audience=BACKEND_URL)`, fall back to `gcloud auth print-identity-token` for local ops (same idea as the source script).
3. GETs `/getCatalogData` or `/getCatalogDailyData` with pagination params.
4. Aggregates `records`, optionally writes JSON / CSV.

This is intentionally not wrapped as a Flask Cloud Function. The source artifact is a pull client; packaging it as another inbound HTTP handler would invent a different product.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| OIDC to Cloud Run (no API key in script) | Fits IAM; rotation = SA membership | Caller must have `run.invoker`; audience must match |
| google-auth first, gcloud fallback | Works in GCP and on laptops | Two code paths to test; gcloud not on all images |
| Env-driven `BACKEND_URL` | Clean env separation | Easy to point staging at prod by mistake — use separate SAs |
| Page walk + `--max-pages` | Avoids silent truncation / runaway loops | Need agreement on page-size semantics with the API owner |
| Optional pandas CSV | Handy for analysts | Extra dependency; JSON-only is enough for pipelines |

## What we did not do here

- Invent an Apigee KVM / product pack — no Apigee artifacts in the Cloud Functions source tree / no local `Documents/API` notes in Cloud.
- Claim throughput or cost savings — measure bytes pulled and Cloud Run billable time in your project.
- Turn this into an Airflow DAG — that belongs in `airflow-patterns`, not this repo.
