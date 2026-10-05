#!/usr/bin/env bash
# Fail if openapi.yaml loses Bearer-only Authorization mapping or reintroduces
# the "Bearer means X-API-KEY" pitfall / dual-scheme drift. Run from this folder.
set -euo pipefail

SPEC="${1:-openapi.yaml}"

if [[ ! -f "${SPEC}" ]]; then
  echo "Missing OpenAPI file: ${SPEC}" >&2
  exit 1
fi

fail() {
  echo "BEARER CONTRACT CHECK FAILED: $*" >&2
  exit 1
}

grep -qE '^[[:space:]]*BearerToken:' "${SPEC}" || fail "BearerToken scheme missing"

# BearerToken must map to Authorization (not X-API-KEY).
awk '
  /^[[:space:]]*BearerToken:/ { in_scheme=1; next }
  /^[[:space:]]*[A-Za-z0-9_]+:/ && in_scheme && !/^[[:space:]]*name:/ && !/^[[:space:]]*type:/ && !/^[[:space:]]*in:/ && !/^[[:space:]]*description:/ { in_scheme=0 }
  in_scheme && /^[[:space:]]*name:/ {
    line=$0
    gsub(/["'\'']/,"",line)
    if (tolower(line) !~ /authorization/) { exit 2 }
    found=1
  }
  END { exit(found ? 0 : 3) }
' "${SPEC}" || fail "BearerToken must set name: Authorization"

# This pattern is Bearer-only — reject accidental dual-scheme additions without
# an intentional rename of the folder / docs.
if grep -qE '^[[:space:]]*ApiKeyHeader:' "${SPEC}"; then
  fail "ApiKeyHeader present — this pattern is Bearer-only; use dual-scheme pattern 14 for OR auth"
fi

# Reject classic pitfall: scheme literally named Bearer that points at X-API-KEY.
if grep -qE '^[[:space:]]*Bearer:' "${SPEC}"; then
  awk '
    /^[[:space:]]*Bearer:/ { in_scheme=1; next }
    /^[[:space:]]*[A-Za-z0-9_]+:/ && in_scheme && !/^[[:space:]]*name:/ && !/^[[:space:]]*type:/ && !/^[[:space:]]*in:/ && !/^[[:space:]]*description:/ { in_scheme=0 }
    in_scheme && /^[[:space:]]*name:/ {
      line=tolower($0)
      gsub(/["'\'']/,"",line)
      if (line ~ /x-api-key/) { exit 2 }
    }
  ' "${SPEC}" || fail "scheme named Bearer maps to X-API-KEY — use BearerToken → Authorization"
fi

# Path must require BearerToken.
block="$(awk '
  $0 == "  \"/getUsers\":" {grab=1; next}
  grab && /^  \"\// {exit}
  grab {print}
' "${SPEC}")"
echo "${block}" | grep -q 'BearerToken: \[\]' || fail "/getUsers missing BearerToken security"

# Cloud Run path backend with h2.
grep -q 'protocol: "h2"' "${SPEC}" || fail "expected x-google-backend protocol h2 for Cloud Run path backend"
grep -q 'BACKEND_URL' "${SPEC}" || fail "expected BACKEND_URL placeholder in x-google-backend.address"

echo "BEARER CONTRACT CHECK OK: ${SPEC}"
