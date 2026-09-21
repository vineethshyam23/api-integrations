#!/usr/bin/env bash
# Fail if openapi.yaml loses dual-scheme OR security, or renames schemes into
# the common "Bearer means X-API-KEY" pitfall. Run from this pattern folder.
set -euo pipefail

SPEC="${1:-openapi.yaml}"

if [[ ! -f "${SPEC}" ]]; then
  echo "Missing OpenAPI file: ${SPEC}" >&2
  exit 1
fi

fail() {
  echo "AUTH CONTRACT CHECK FAILED: $*" >&2
  exit 1
}

# Both schemes must exist under securityDefinitions.
grep -qE '^[[:space:]]*ApiKeyHeader:' "${SPEC}" || fail "ApiKeyHeader scheme missing"
grep -qE '^[[:space:]]*BearerToken:' "${SPEC}" || fail "BearerToken scheme missing"

# ApiKeyHeader must map to X-API-KEY (case-insensitive name check).
awk '
  /^[[:space:]]*ApiKeyHeader:/ { in_scheme=1; next }
  /^[[:space:]]*[A-Za-z0-9_]+:/ && in_scheme && !/^[[:space:]]*name:/ && !/^[[:space:]]*type:/ && !/^[[:space:]]*in:/ && !/^[[:space:]]*description:/ { in_scheme=0 }
  in_scheme && /^[[:space:]]*name:/ {
    line=$0
    gsub(/["'\'']/,"",line)
    if (tolower(line) !~ /x-api-key/) { exit 2 }
    found=1
  }
  END { exit(found ? 0 : 3) }
' "${SPEC}" || fail "ApiKeyHeader must set name: X-API-KEY"

# BearerToken must map to Authorization header (not X-API-KEY).
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

# Reject the classic pitfall: a scheme literally named Bearer that points at X-API-KEY.
if grep -qE '^[[:space:]]*Bearer:' "${SPEC}"; then
  # Allow only if that scheme's name is Authorization (unlikely); otherwise fail.
  awk '
    /^[[:space:]]*Bearer:/ { in_scheme=1; next }
    /^[[:space:]]*[A-Za-z0-9_]+:/ && in_scheme && !/^[[:space:]]*name:/ && !/^[[:space:]]*type:/ && !/^[[:space:]]*in:/ && !/^[[:space:]]*description:/ { in_scheme=0 }
    in_scheme && /^[[:space:]]*name:/ {
      line=tolower($0)
      gsub(/["'\'']/,"",line)
      if (line ~ /x-api-key/) { exit 2 }
    }
  ' "${SPEC}" || fail "scheme named Bearer maps to X-API-KEY — rename schemes to match headers"
fi

# Each secured path should list both schemes as alternatives (OR list).
for path in /getUser /getPosUser /getEstablishments; do
  block="$(awk -v p="  \"${path}\":" '
    $0 == p {grab=1; next}
    grab && /^  \"\// {exit}
    grab {print}
  ' "${SPEC}")"
  echo "${block}" | grep -q 'ApiKeyHeader: \[\]' || fail "${path} missing ApiKeyHeader security"
  echo "${block}" | grep -q 'BearerToken: \[\]' || fail "${path} missing BearerToken security"
done

# Backends should be Cloud Run path addresses (protocol h2 is the production hint).
grep -q 'protocol: "h2"' "${SPEC}" || fail "expected x-google-backend protocol h2 for Cloud Run path backends"

echo "AUTH CONTRACT CHECK OK: ${SPEC}"
