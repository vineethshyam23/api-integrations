# Business case: GA sessions / daily-visits OpenAPI

## Problem

Downstream jobs need analytics extracts over HTTPS with a stable contract: page through results, filter by date or dimensions, and choose between a flat daily rollup and a nested session payload. Putting that surface on raw Cloud Run URLs forces every consumer to learn IAM tokens or exposes the service more widely than you want. A second full gateway for each shape also doubles key and hostname ops.

## Constraints that mattered

- Callers are often batch / ETL tools, not browser SPAs — they need an envelope (`records` + `pagination`) more than a bare JSON array.
- Flat vs nested is intentional: simple sinks should not parse `device` / `geoNetwork`; advanced flattening tasks need the nesting intact.
- Backend is Cloud Run with path-based routes (`/daily-visits`, `/ga-sessions-data`), not one Cloud Function URL per path.
- Auth stays API-key at the edge (`X-API-Key` header) so non-GCP clients stay simple; Cloud Run itself should not be `allUsers` invoker.
- Session queries can be heavier than daily rollups → higher `deadline` on the nested route.

## Decision

One **API Gateway OpenAPI config** with **two analytics paths**, both API-key protected, each `x-google-backend` pointing at a Cloud Run URL + path:

1. Gateway validates the key once for the surface.
2. Path selects flat daily visits vs nested GA sessions.
3. OpenAPI is the reviewable contract for pagination, filters, and response shapes.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| Shared Cloud Run service, two paths | One deployable backend binary | Gateway + Run both need careful path forwarding |
| Pagination envelope | Predictable ETL loops (`has_next`) | Slightly more payload than a raw array |
| Nested session schema | Matches warehouse nesting for teaching / ETL | Larger responses; higher deadline |
| Header API key | Cleaner logs than `?key=` | Must document header for every client |
| Dimension filters on sessions only | Keeps daily route simple | Spec asymmetry clients must learn |

## Distinct from pattern 03

Pattern 03 is a dashboard surface (establishment / visits / orders / POS) over Cloud Functions with offset/limit arrays and locale-style dates. This pattern is an **analytics extraction** surface over **Cloud Run**, with page/limit envelopes, ISO / `YYYYMMDD` dates, and nested session objects. Same gateway product — different teaching shape.

## What we did not do here

- Apigee products / KVMs — useful for partner packaging later; not required for this gateway + Run shape.
- Shipping the Cloud Run Python itself in this folder — focus is the OpenAPI edge contract.
- Claiming extract volume or latency numbers — measure in your project.
