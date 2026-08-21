# Business case: Restricted API keys

## Problem

API Gateway fronts Cloud Functions / Cloud Run with a simple shared secret model: clients send an API key, the edge validates it, and only the gateway service account can invoke the backend. That works until someone creates a key with **no API restrictions** and **no application restrictions**. The string then works against every enabled API in the project and from any network. When it leaks (CI log, screenshot, partner email), blast radius is the whole project surface — not one gateway route.

## Constraints that mattered

- Consumers are mixed: notebooks, Airflow / Cloud Run jobs, occasionally browser tools. Not everyone can use IAM user tokens.
- Gateway OpenAPI already declares `api_key` in `securityDefinitions`; ops still need a matching credential policy in API & Services.
- Dev and prod must not share keys. Environment separation is cheaper than forensic key hunting.
- Rotation must not require redeploying Cloud Run or re-uploading OpenAPI — only client config and the Credentials page.
- Real key strings must never land in git. Automation that “helps” by committing create output is a hard fail.

## Decision

Treat **API key restriction** as a first-class pattern next to OpenAPI:

1. Create keys only for a named purpose (one gateway API, one environment).
2. Apply **API restrictions** to the managed service for that gateway API (not “don’t restrict key”).
3. Apply **application restrictions** when the client model allows: IP for fixed egress ETL, HTTP referrers for browser-only tools, none only for tightly controlled server clients with compensating controls.
4. Prefer header delivery (`X-API-Key`) over query `?key=` so access logs and browser history are less likely to retain the secret.
5. Rotate by dual-key cutover; delete the old key after clients move.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| API restrictions only | Stops cross-API abuse with one key | Still callable from any IP if stolen |
| + IP restrictions | Strong for fixed ETL egress | Breaks for roaming / serverless without stable egress |
| + HTTP referrers | Fits browser dashboards | Trivial to spoof; not enough alone for high-value APIs |
| Header vs query param | Cleaner logs and history | Every client must set the header |
| Dual-key rotation | Zero-downtime cutover | Short window with two valid keys |

## What we did not do here

- Apigee products / KVMs — different credential packaging; still placeholders-only when that pattern ships.
- OAuth / IAP for end users — right for interactive apps; heavier than batch API consumers need.
- Claiming breach probability or dollar savings — measure in your incident process.
