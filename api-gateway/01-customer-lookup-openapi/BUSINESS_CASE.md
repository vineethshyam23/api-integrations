# Business case: Customer lookup behind API Gateway

## Problem

Teams need a small HTTP lookup that maps an account ID to application URLs across environments. The naive approach is to call a Cloud Function URL directly. That works for a prototype and then becomes a production liability: keys get shared in query strings without a contract, function URLs leak into clients, and there is no single place to revoke access without redeploying callers.

## Constraints that mattered

- Callers are internal tools or partner dashboards, not anonymous public traffic.
- Auth needed to be simple enough for non-GCP clients (API key), not full OIDC at the edge.
- Dev and prod backends differ by function URL; the OpenAPI file is the environment-specific artifact.
- Cold starts on Gen1 Cloud Functions meant the gateway deadline had to be higher than the default in some environments.

## Decision

Use **API Gateway + OpenAPI (`x-google-backend`)** in front of an HTTP Cloud Function:

1. Gateway validates the API key and routes to the function.
2. Function stays private to the gateway path (IAM still recommended on the function).
3. OpenAPI is the deployable contract — same file reviewers read and ops deploy.

## Tradeoffs

| Choice | Upside | Cost |
|--------|--------|------|
| API key at gateway | Fast to onboard clients | Key rotation and leakage risk; restrict keys tightly |
| Query param `key` | Matches many existing clients | Shows up in logs/proxies more than header keys |
| One route per config | Easy to reason about | Larger dashboards need multi-path specs (separate pattern) |
| Cloud Function backend | Cheap at low QPS | Cold start + Gen1/Gen2 differences |

## What we did not do here

- Apigee product / KVM layer — overkill for a single internal lookup.
- Custom domain + Cloud Armor — optional hardening for later.
- Inventing latency or cost savings numbers — measure in your project.
