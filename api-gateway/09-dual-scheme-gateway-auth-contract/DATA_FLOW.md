# Data flow: dual-scheme vendor lookup via API Gateway

## Happy path (X-API-KEY)

1. Client calls `GET https://GATEWAY_HOST/getUser?account_id=ACCOUNT_ID` with header `X-API-KEY: YOUR_API_KEY`.
2. API Gateway matches `/getUser`, requires one of the declared schemes, validates the platform API key binding.
3. Gateway proxies to `https://BACKEND_URL/getUser` (h2) using the gateway service account as invoker.
4. Cloud Run handler reads `X-Api-Key` (case variants), compares to `VENDOR_API_KEY` with `hmac.compare_digest`.
5. Handler runs a parameterized BigQuery lookup and returns `{ "ACCOUNT_ID": [ ...rows ] }` with CORS headers as configured.

## Happy path (Authorization Bearer)

1. Same URL, header `Authorization: Bearer YOUR_API_KEY`.
2. Gateway accepts the `BearerToken` scheme (`Authorization` apiKey header).
3. Handler strips the `Bearer ` prefix, then constant-time compares to the expected secret.
4. Downstream BQ path is identical.

Either header shape must succeed for the same secret. If only one works, the OpenAPI schemes and the handler disagree — fix the contract, do not "document around" it.

## Failure modes

| Symptom | Likely cause | Where it fails |
|---------|--------------|----------------|
| 401 from gateway / API key rejected | Key missing, wrong API restriction, or disabled key | API Gateway / API & Services |
| 403 from Cloud Run | Gateway SA lacks `run.invoker`, or public invoker denied and caller is not the gateway | IAM |
| 401 from handler JSON body | Secret mismatch, empty `VENDOR_API_KEY`, or client sent a third header name | App layer |
| 400 missing parameter | `account_id` / `enterprise_id`+`country_code` / `establishment_id` absent | Handler |
| 404 not found | Query returned no rows | Handler / data |
| Works in curl with X-API-KEY, fails in SDK using Bearer | Published OpenAPI had a single misnamed scheme | Contract drift — run `check-auth-contract.sh` |
| Works with Bearer, fails with X-API-KEY | Gateway config only lists one scheme, or handler only reads Authorization | Same — dual OR list + dual handler accept |

## Empty and error envelopes

Successful payloads use id-keyed envelopes (`{id: [rows]}`), not `{records, pagination}`. That is intentional for this vendor contract — do not "normalize" it without a versioned API break.

Error bodies from the companion handler look like `{ "error": <code>, "description": "..." }` with matching HTTP status. Do not leak exception strings unless `EXPOSE_ERROR_DETAIL` is explicitly enabled in a non-prod env (handler concern).

## Rotation sequence

1. Add new secret version in Secret Manager; roll Cloud Run to read it (or dual-accept briefly if you implement dual expected keys — this pattern does not).
2. Distribute the new value to the vendor.
3. Disable the old API & Services key if you rotated the platform key separately.
4. Keep OpenAPI scheme names stable across rotations — only hosts and config ids change.
