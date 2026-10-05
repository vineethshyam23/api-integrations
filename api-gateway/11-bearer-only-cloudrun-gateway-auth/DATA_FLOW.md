# Data flow: Bearer-only CX user lookup via API Gateway

## Happy path

1. Client calls `GET https://GATEWAY_HOST/getUsers?establishment_id=EST_ID`
   with header `Authorization: Bearer YOUR_API_KEY`.
2. API Gateway matches `/getUsers`, requires the `BearerToken` scheme, and
   validates the credential binding for this API.
3. Gateway proxies to `https://BACKEND_URL/getUsers` (h2) using the gateway
   service account as invoker.
4. Cloud Run handler reads `Authorization`, strips the `Bearer ` prefix, and
   compares to the expected secret with a constant-time compare (see vendor
   API key auth handler pattern).
5. Handler runs a parameterized lookup and returns the user object (or 404).

Clients that only send `X-API-KEY` will fail at the edge on this pattern. That
is intentional. Use the dual-scheme pattern when both headers must work.

## Failure modes

| Symptom | Likely cause | Where it fails |
|---------|--------------|----------------|
| 401 from gateway | Token missing, wrong API restriction, or disabled key | API Gateway / API & Services |
| 403 from Cloud Run | Gateway SA lacks `run.invoker`, or public invoker denied | IAM |
| 401 from handler JSON body | Secret mismatch or empty expected secret | App layer |
| 400 missing parameter | `establishment_id` absent | Handler / contract |
| 404 not found | Establishment has no users | Handler / data |
| Works with X-API-KEY in curl, fails with Bearer | Published OpenAPI mapped Bearer→X-API-KEY or path still requires ApiKeyHeader | Contract drift — run `check-bearer-contract.sh` |
| Works with Bearer against dual-scheme API, fails here | Client still sending only X-API-KEY | Client / wrong pattern chosen |

## Payload notes

Successful payloads are a flat user object (account_id, name fields, optional
contact fields). Treat email and phone as PII: keep examples as placeholders
in public docs, and trim fields in production OpenAPI if the partner does not
need them.

Error bodies from a companion handler typically look like
`{ "error": <code>, "description": "..." }` with matching HTTP status. Do not
leak exception strings unless an explicit non-prod error-detail flag is on.

## Rotation sequence

1. Add a new secret version in Secret Manager; roll Cloud Run to read it.
2. Distribute the new Bearer value to the partner.
3. Disable the old platform key if you rotated an API & Services key separately.
4. Keep OpenAPI scheme names stable across rotations — only hosts and config
   ids change.
