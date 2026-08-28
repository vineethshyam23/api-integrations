# Data flow: OIDC outbound HTTP client

## Happy path

1. Operator or job sets `BACKEND_URL=https://SERVICE-HASH.REGION.run.app` (no trailing slash).
2. Client resolves identity:
   - Prefer `google.oauth2.id_token.fetch_id_token(request, audience=BACKEND_URL)`
   - Else `gcloud auth print-identity-token` (local ops, same approach as the source script)
3. Client GETs `{BACKEND_URL}/getCatalogData?pageSize=N&pageNumber=1` with `Authorization: Bearer <id_token>`.
4. On 200, reads `records` from JSON. Continues `pageNumber += 1` until a page returns fewer than `pageSize` rows, `records` missing, or `--max-pages` hits.
5. Writes aggregated records to JSON (and optional CSV).

Example success page body (truncated / fake data):

```json
{
  "records": [
    {
      "establishment_id": "EST_ID",
      "name": "Example Venue",
      "city": "Example City",
      "country": "DE"
    }
  ],
  "pageNumber": 1,
  "pageSize": 100
}
```

Exact pagination envelope fields beyond `records` vary by API owner — the client only requires `records` for the walk.

## Failure modes

| Symptom | Likely cause | What to check |
|---------|--------------|---------------|
| RuntimeError `BACKEND_URL is required` | Env not set | Export `BACKEND_URL` |
| RuntimeError placeholders | Still using example host | Replace `SERVICE-HASH` / `REGION` |
| 401 / 403 from Cloud Run | Not an invoker, or wrong token type/audience | SA has `run.invoker`; audience = service URL; use ID token not access token |
| google-auth fails, gcloud missing | Container without CLI and without ADC | Attach runtime SA / workload identity; install `google-auth` |
| Empty / non-zero exit | Feed empty or auth failed mid-walk | Logs `feed_request_failed`; confirm path leaf names |
| Truncated extract | Stopped early | Raise `--max-pages` or page size; confirm API short-page semantics |
| Timeout | Slow backend / large page | Lower `pageSize`; raise timeout; check Cloud Run concurrency |

## Logging

Lines look like:

```text
INFO fetching page=1 page_size=100 daily=False
ERROR feed_request_failed status=403 page=1 body_preview=...
INFO saved_json count=42 path=catalog_sample.json
```

Never log Bearer tokens, `Authorization` header values, or raw identity JWTs. Status codes and short body previews are enough for triage.

## Sequence (client-local)

```mermaid
sequenceDiagram
  participant M as main
  participant T as get_auth_token
  participant H as Cloud Run feed
  participant S as sink

  M->>T: audience=BACKEND_URL
  T-->>M: ID token
  loop pages
    M->>H: GET leaf + Bearer + page params
    alt non-200
      H-->>M: 4xx/5xx
      M-->>M: log status, stop walk
    else 200
      H-->>M: JSON with records
      M->>M: append; stop if short page
    end
  end
  M->>S: write JSON / optional CSV
```
