# Business case: mixed backend generation lint

## Problem

Multi-route panel gateways grow by rewriting one Cloud Function at a time.
Someone migrates orders and reservations to a BigQuery-backed generation
(`-gbq`), leaves establishment on the legacy name, and points visits at an
older `lookup-*` function that happened to still work. The OpenAPI deploys.
Clients keep calling the same hostname. Reviewers miss it because every path
still has an `address:` and path-level auth.

Operationally you now have:

- Three naming conventions under one API (underscore, hyphen, foreign family)
- Two data-plane generations with different SLOs and IAM surfaces
- An invoker grant checklist that is easy to get wrong on the odd-one-out route

That is worse than an openly unfinished migration: the gateway *looks* complete.

## Constraints

- Google Cloud API Gateway proxies each path to its own `x-google-backend`.
  There is no platform check that those backends share a naming convention.
- Region mix across routes is sometimes intentional (pattern 16). Generation
  suffix mix and foreign function families usually are not.
- Twin gates (pattern 16) compare DEV vs PRD. They do not fail a single file
  whose four PRD backends already disagree with each other.
- Query-string API keys leak via logs and Referer. Prefer header `X-API-KEY`
  when aligning the exemplar.

## Tradeoffs

| Choice | Why | Cost |
|--------|-----|------|
| Single-file backend-generation lint | Catches partial migration before twins exist | Does not replace pairwise twin URL checks |
| Fail on partial `-gbq` / `_gbq` | Matches the real rewrite footgun | Intentional dual-generation cutovers need a temporary allowlist or a short-lived second API |
| Fail on family / separator drift | Catches `lookup-*` leftovers and `_` vs `-` mashups | Strict; rename functions or keep a dedicated OpenAPI per generation |
| Negative fixture in-repo | Proves the gate still detects the smell | Risk someone deploys the fixture if they skip the lint |
| Header API key in aligned exemplar | Avoids query leakage | Source used query `key` — clients need a coordinated switch |

## Why not invent Apigee / ship another near-duplicate panel OpenAPI

Apigee notes are not available in Cloud. Shipping `hd-dish-panel-dashboard-new.yml`
as "yet another four-route panel" duplicates patterns 03 / 16 / 19. The unique
lesson is the **mixed backend generation** inside that file — extract the gate,
ship an aligned exemplar, keep the mixed shape only as a fixture.
