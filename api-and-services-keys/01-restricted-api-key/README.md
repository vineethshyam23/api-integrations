# Pattern 05: Restricted API key (API & Services)

How to create a Google Cloud API key that is usable only for the intended API Gateway (or other enabled API), and optionally locked to HTTP referrers or IP ranges. Covers creation, restriction, safe client usage, and rotation without redeploying backends.

Patterns 01–04 assume a key at the edge. This folder is the credential side of that design — what you do in **API & Services** so a leaked key string is less useful.

## Why this pattern

- An unrestricted key that can call every enabled API in the project is a standing incident waiting for a paste into a ticket or notebook.
- Gateway OpenAPI `securityDefinitions` alone do not restrict *which* APIs the key may use; that lives in the key’s application restrictions.
- Referrer vs IP vs “none” is a product decision: browser dashboards, fixed ETL egress, and server-to-server partners need different shapes.

## File index

| File | Purpose |
|------|---------|
| `create-restricted-key.sh` | Example `gcloud` create + restrict + describe (placeholders only) |
| `key-policy.example.yaml` | Restriction checklist as config-shaped docs |
| `client-usage.examples.sh` | Header vs query usage; what not to log |
| `BUSINESS_CASE.md` | Problem, constraints, tradeoffs |
| `ARCHITECTURE.md` | Components + Mermaid diagrams |
| `DATA_FLOW.md` | Create → restrict → call → rotate |
| `README.md` | This overview |

## Sanitization notes

This pattern is platform practice for API Gateway surfaces already documented in this repo (customer lookup, dashboard, analytics extracts). It is **not** copied from a secret-bearing notes file.

- No real key material, project numbers, or live hostnames
- Placeholders: `PROJECT_ID`, `GATEWAY_HOST`, `YOUR_API_KEY`, `API_TARGET_SERVICE`
- Do not paste `gcloud` create output key strings into git, Confluence, or PR bodies

## Quick start

1. Enable the gateway / target API in the project (already true if you deployed patterns 01–04).
2. Edit placeholders in `create-restricted-key.sh` and run it, or follow the same steps in Console → APIs & Services → Credentials.
3. Restrict the key to the managed service name for your API Gateway API (and add referrer or IP restrictions if the client model allows).
4. Call through the gateway only:

```bash
curl -sS "https://GATEWAY_HOST/daily-visits?page=1&limit=5" \
  -H "X-API-Key: YOUR_API_KEY"
```

5. Rotate by creating a second restricted key, cutting over clients, then deleting the old key — backends and OpenAPI stay unchanged.

## Related patterns

- Customer lookup OpenAPI → [`../../api-gateway/01-customer-lookup-openapi/`](../../api-gateway/01-customer-lookup-openapi/)
- Multi-route dashboard OpenAPI → [`../../api-gateway/02-multi-route-dashboard-openapi/`](../../api-gateway/02-multi-route-dashboard-openapi/)
- GA sessions OpenAPI → [`../../api-gateway/03-ga-sessions-daily-visits-openapi/`](../../api-gateway/03-ga-sessions-daily-visits-openapi/)
- HTTP handler behind gateway → [`../../cloud-run-functions/01-http-handler-behind-gateway/`](../../cloud-run-functions/01-http-handler-behind-gateway/)
