#!/usr/bin/env bash
# Smell gate: fail if a Python handler still pages with an in-memory slice
# after a warehouse LIMIT (the v2 anti-pattern this folder documents).
#
# Usage:
#   ./check-inmemory-slice-smell.sh path/to/handler.py [more.py ...]
#   ./check-inmemory-slice-smell.sh --self   # expect FAIL on this folder's main.py
#
# Exit 0 = clean (no smell). Exit 1 = smell found or usage error.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${1:-}" == "--self" ]]; then
  set -- "${ROOT}/main.py"
fi

if [[ $# -lt 1 ]]; then
  echo "usage: $0 path/to/handler.py [...] | $0 --self" >&2
  exit 1
fi

# Heuristics that together indicate LIMIT-then-slice paging.
# Individual matches can be noisy; require at least two distinct smell classes.
smell_limit_format=0
smell_python_slice=0
smell_huge_default_limit=0
smell_env_as_project=0

for f in "$@"; do
  if [[ ! -f "$f" ]]; then
    echo "missing file: $f" >&2
    exit 1
  fi
  # format/f-string LIMIT without nearby OFFSET in the same SQL construction
  if grep -Eqi "LIMIT\s*[{(]|LIMIT\s*\{|LIMIT \{\}|LIMIT %|LIMIT \"|\.format\([^)]*limit" "$f"; then
    if ! grep -Eqi "OFFSET\s*@|OFFSET\s*\{|OFFSET %|OFFSET \{\}" "$f"; then
      smell_limit_format=1
      echo "SMELL limit-without-offset-sql: $f"
    fi
  fi
  if grep -Eq '\[_?offset\s*:|buffer\[offset|tmpresult\[_?offset|page\s*=\s*\w+\[offset' "$f"; then
    smell_python_slice=1
    echo "SMELL python-offset-slice: $f"
  fi
  if grep -Eq 'DEFAULT_LIMIT\s*=\s*9999|limit.*,\s*['\''"]9999|get\(['\''"]limit['\''"].*9999' "$f"; then
    smell_huge_default_limit=1
    echo "SMELL huge-default-limit: $f"
  fi
  # ENV used as BigQuery project (same line or assigned then passed to Client).
  if grep -Eq 'Client\(project=os\.environ\.get\(['\''"]ENV['\''"]' "$f" \
    || { grep -Eq 'environ\.get\(['\''"]ENV['\''"]' "$f" && grep -Eq 'bigquery\.Client\(project=' "$f"; }; then
    smell_env_as_project=1
    echo "SMELL env-as-bq-project: $f"
  fi
done

score=$((smell_limit_format + smell_python_slice + smell_huge_default_limit + smell_env_as_project))

if [[ "$score" -ge 2 ]]; then
  echo "FAIL: in-memory-slice pagination smell detected (score=${score}/4)."
  echo "Prefer SQL LIMIT/OFFSET + parameterized filters (see pattern 15)."
  exit 1
fi

echo "OK: no multi-signal in-memory-slice smell in: $*"
exit 0
