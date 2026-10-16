# Data flow: Bearer-only partner catalog via API Gateway

## Happy path

1. Client calls `GET https://GATEWAY_HOST/catalog?limit=100&offset=0` with
   header `Authorization: Bearer YOUR_API_KEY`.
2. API Gateway matches `/catalog`, requires the `BearerToken` scheme, and
   validates the credential binding for this API.
3. Gateway proxies to `https://BACKEND_URL/catalog` (h2) using the gateway
   service account as invoker.
4. Cloud Run handler reads `Authorization`, strips the `Bearer ` prefix, and
   compares to the expected secret with a constant-time compare (see vendor
   API key auth handler pattern).
5. Handler validates `limit` / `offset` (apply a hard max; reject negatives),
   runs parameterized `LIMIT` / `OFFSET` plus a `COUNT(*)` (or equivalent), and
   returns `{ records, pagination: { total, limit, offset } }`.

Clients that only send `X-API-KEY`, or that send `pageSize` / `pageNumber`,
will not match this published contract. That is intentional. Use pattern 13
when the product has moved to ApiKeyAuth + page-based dual routes.

## Failure modes

| Symptom | Likely cause | Where it fails |
|---------|--------------|----------------|
| 401 from gateway | Token missing, wrong API restriction, or disabled key | API Gateway / API & Services |
| 403 from Cloud Run | Gateway SA lacks `run.invoker`, or public invoker denied | IAM |
| 401 from handler JSON body | Secret mismatch or empty expected secret | App layer |
| 400 invalid paging | Negative offset, limit below 1, or above handler cap | Handler / contract |
| 404 no data | Empty page (strict catalog semantics) | Handler / data |
| Works with X-API-KEY in curl, fails with Bearer | Published OpenAPI mapped Bearer→X-API-KEY or path still requires ApiKeyAuth | Contract drift — run `check-bearer-limit-offset-contract.sh` |
| Partner page loop off-by-one | Client still using pageNumber math against limit/offset | Client / wrong pattern chosen |
| Gateway OK, huge responses | Handler ignored limit cap | Backend — enforce max regardless of OpenAPI default |

## Payload notes

Successful payloads are:

```json
{
  "records": [ { "establishment_id": "EST_ID", "...": "..." } ],
  "pagination": { "total": 5000, "limit": 100, "offset": 0 }
}
```

Contact email and phone columns from warehouse extracts are dropped from this
public sample schema. Keep examples as placeholders; trim further in production
if the partner does not need address or website fields.

Error bodies from a companion handler typically look like
`{ "error": <code>, "description": "..." }` with matching HTTP status. Do not
leak exception strings unless an explicit non-prod error-detail flag is on.

## Rotation / evolution sequence

1. Add a new secret version in Secret Manager; roll Cloud Run to read it.
2. Distribute the new Bearer value to the partner.
3. Disable the old platform key if you rotated an API & Services key separately.
4. When the product adds a daily NTILE path or switches to pageSize/pageNumber
   + X-API-KEY, **publish a new OpenAPI revision** (pattern 13 lineage) instead
   of silently mutating this thin contract. Keep scheme names and paging
   dialect stable for clients still pinned to this revision.
