# Business case: DEV vs PRD API Gateway twins

## Problem

Once an API Gateway surface exists, you need a second copy for the non-prod project. Teams copy-paste the OpenAPI file, change the backend URL, and move on. Weeks later DEV no longer matches PRD: auth is optional in one env, schema types disagree, or a client that "worked in DEV" fails against production with a 403 or a type error. The cost shows up as flaky partner onboarding, not as a clean compile error.

## Constraints that mattered

- Public contract (paths, operationIds, query params, security scheme name/`in`, response property types) must be identical across envs.
- Backend addresses **must** differ — separate GCP project / Cloud Function / Cloud Run service.
- Path-level `security:` is easy to delete in DEV "so we can curl without a key." That teaches the wrong habit and can ship if someone promotes the DEV file.
- Schema type drift (int vs string on the same field) is common when handlers evolve independently; generators and typed clients break.
- Config ids are immutable in API Gateway — each OpenAPI revision needs a new config id. Reusing a PRD config id in DEV (or the reverse) is an ops trap.

## Decision

Ship **paired OpenAPI files** (`openapi.prd.yaml` / `openapi.dev.yaml`) for one account-activities surface, plus:

1. A `check-twins.sh` gate that fails on contract drift and on identical backends.
2. An env-aware `deploy.sh` that always runs the gate first and uses separate API / gateway ids per env.

The exemplar is a single `/getActivities` path with header `X-API-Key` — deliberately simple so the twin discipline is the teaching point, not another filter combinatorics story.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| Two OpenAPI files | Clear review diffs; env-specific backends | Manual sync unless gated |
| `check-twins.sh` before deploy | Catches security drops and type drift early | Regex/structure checks ≠ full OpenAPI validate |
| Separate gateway ids per env | Hard to accidentally point PRD traffic at DEV | More `gcloud` objects to manage |
| Align schema types during sanitization | Clients can generate once | Must resist "leave source quirks" when quirks are bugs |
| Keep DEV auth on | Partners exercise the real key path | Slightly more setup for local smoke tests |

## Distinct from earlier patterns

- 01 / 05 / 09 / 10: one sanitized OpenAPI (sometimes + handler). Mentions env separation in prose only.
- 08: env-scoped **handler** table defaults (`DEPLOY_ENV`) — runtime, not gateway twin files.
- This pattern: **two gateway configs**, contract parity gate, deploy-time discipline. Backend handler is intentionally out of scope.

## What we did not do here

- Apigee products / KVMs — no `Documents/API` notes in Cloud; do not invent.
- Inventing a full CI pipeline — `check-twins.sh` is the reusable core; wire it into your repo's CI as you prefer.
- Claiming reduced incident counts — measure that in your own rollout.
