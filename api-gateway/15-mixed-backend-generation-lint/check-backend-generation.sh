#!/usr/bin/env bash
# Fail if a multi-route OpenAPI mixes Cloud Function / Cloud Run backend
# naming generations inside one gateway config.
#
# Catches three footguns seen when panel routes migrate independently:
#   1. Partial -gbq / _gbq suffix (some routes migrated, others not)
#   2. Separator drift (underscore names mixed with hyphen names)
#   3. Family drift (first token after strip differs — e.g. panel vs lookup)
#
# Distinct from:
#   - pattern 16 twin pairwise backend inequality (DEV vs PRD URLs)
#   - pattern 19 path-security lint (auth wiring)
#   - pattern 03 multi-route OpenAPI (aligned exemplar, no generation gate)
#
# Usage:
#   ./check-backend-generation.sh [openapi.yaml]
#   ./check-backend-generation.sh --self
#       Must FAIL the mixed fixture, then OK the aligned openapi.yaml.
#
# Requires: python3 (stdlib only).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPEC="${1:-${ROOT}/openapi.yaml}"
FIXTURE="${ROOT}/fixtures/openapi.mixed-backends.yaml"

if [[ "${1:-}" == "--self" ]]; then
  echo "== self-check: mixed fixture must FAIL =="
  set +e
  bash "$0" "${FIXTURE}"
  rc=$?
  set -e
  if [[ "${rc}" -eq 0 ]]; then
    echo "SELF CHECK FAILED: fixture was expected to fail but passed" >&2
    exit 1
  fi
  echo "== self-check: aligned openapi.yaml must OK =="
  bash "$0" "${ROOT}/openapi.yaml"
  echo "SELF CHECK OK: fixture failed as expected; aligned OpenAPI passed"
  exit 0
fi

if [[ ! -f "${SPEC}" ]]; then
  echo "Missing OpenAPI file: ${SPEC}" >&2
  exit 2
fi

python3 - "${SPEC}" <<'PY'
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

path = Path(sys.argv[1])
text = path.read_text()

addresses = re.findall(
    r"(?m)^\s+address:\s*[\"']?([^\"'\s]+)[\"']?",
    text,
)
if len(addresses) < 2:
    print(
        f"BACKEND GENERATION CHECK FAILED: {path}: "
        f"need >= 2 x-google-backend addresses for a multi-route gate "
        f"(found {len(addresses)})"
    )
    sys.exit(1)


def service_name(url: str) -> str:
    """Last path segment of Cloud Functions / Cloud Run URL."""
    parsed = urlparse(url)
    segments = [s for s in parsed.path.split("/") if s]
    if not segments:
        return url.rstrip("/").rsplit("/", 1)[-1]
    return segments[-1]


names = [service_name(a) for a in addresses]
errors: list[str] = []

# 1) Generation suffix parity: -gbq / _gbq (optionally before -vN / _vN)
gbq_re = re.compile(r"[-_]gbq(?:[-_]v\d+)?$", re.I)
has_gbq = [bool(gbq_re.search(n)) for n in names]
if any(has_gbq) and not all(has_gbq):
    migrated = [n for n, g in zip(names, has_gbq) if g]
    legacy = [n for n, g in zip(names, has_gbq) if not g]
    errors.append(
        "partial -gbq / _gbq migration across routes — "
        f"migrated={migrated} legacy={legacy}"
    )

# 2) Separator style: underscore-heavy vs hyphen-heavy names must not mix
def sep_style(name: str) -> str:
    # Ignore the generation token when classifying separators.
    core = gbq_re.sub("", name)
    underscores = core.count("_")
    hyphens = core.count("-")
    if underscores and hyphens:
        return "mixed"
    if underscores:
        return "underscore"
    if hyphens:
        return "hyphen"
    return "plain"


styles = {sep_style(n) for n in names}
# "plain" can coexist with either style; underscore+hyphen cannot.
meaningful = {s for s in styles if s in {"underscore", "hyphen", "mixed"}}
if "mixed" in meaningful or ({"underscore", "hyphen"} <= meaningful):
    errors.append(
        "separator drift across backends — "
        f"styles={ {n: sep_style(n) for n in names} }"
    )

# 3) Family token: strip env/version/gbq suffixes, require shared first token
SUFFIXES = re.compile(
    r"(?:[-_](?:dev|prd|prod|gbq|v\d+))+$",
    re.I,
)


def family_token(name: str) -> str:
    normalized = name.replace("_", "-").lower()
    # Peel known suffixes repeatedly
    prev = None
    while prev != normalized:
        prev = normalized
        normalized = SUFFIXES.sub("", normalized)
    parts = [p for p in normalized.split("-") if p]
    return parts[0] if parts else normalized


families = [family_token(n) for n in names]
if len(set(families)) > 1:
    errors.append(
        "backend family drift — first tokens differ after stripping "
        f"env/version/gbq: {list(zip(names, families))}"
    )

if errors:
    print(f"BACKEND GENERATION CHECK FAILED: {path}:")
    for err in errors:
        print(f"  - {err}")
    print(
        "Align function names under one family + separator + generation "
        "suffix (or finish the migration). See fixtures/openapi.mixed-backends.yaml."
    )
    sys.exit(1)

print(
    f"BACKEND GENERATION CHECK OK: {path} "
    f"({len(names)} backends, family={families[0]!r}, "
    f"gbq_suffix={'yes' if all(has_gbq) else 'no'})"
)
for i, (addr, name) in enumerate(zip(addresses, names)):
    print(f"  [{i}] {name}")
PY
