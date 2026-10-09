#!/usr/bin/env bash
# Fail if an OpenAPI (Swagger 2) file declares securityDefinitions but any
# HTTP operation under paths: lacks a path-level security: block.
#
# Distinct from pattern 11 twin comparison: this gate runs on a single
# multi-route file. Useful when there is no DEV twin yet, or when a solo
# config ships first and "we will add security later" never happens.
#
# Requires: python3 (stdlib only).
set -euo pipefail

SPEC="${1:-openapi.yaml}"

if [[ ! -f "${SPEC}" ]]; then
  echo "Missing OpenAPI file: ${SPEC}" >&2
  exit 2
fi

python3 - "${SPEC}" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()

if not re.search(r"(?m)^securityDefinitions:\s*$", text):
    print(f"PATH SECURITY CHECK FAILED: {path}: no securityDefinitions block")
    sys.exit(1)

# Split into path operation blocks: indent-2 path key, then indent-4 method.
path_keys = re.findall(r"(?m)^  (/[^:\s]+):\s*$", text)
if not path_keys:
    print(f"PATH SECURITY CHECK FAILED: {path}: no paths found")
    sys.exit(1)

# Extract each path's body until the next path or top-level key.
path_bodies: list[tuple[str, str]] = []
for m in re.finditer(r"(?m)^  (/[^:\s]+):\n((?:^    .*\n|^$\n)*)", text):
    path_bodies.append((m.group(1), m.group(2)))

if not path_bodies:
    print(f"PATH SECURITY CHECK FAILED: {path}: could not parse path bodies")
    sys.exit(1)

http_methods = {"get", "post", "put", "patch", "delete", "options", "head"}
missing: list[str] = []

for path_key, body in path_bodies:
    # Method blocks at indent 4
    methods = list(
        re.finditer(
            r"(?m)^    ([a-z]+):\n((?:^      .*\n|^$\n)*)",
            body,
        )
    )
    for mm in methods:
        method = mm.group(1)
        if method not in http_methods:
            continue
        op_body = mm.group(2)
        # Path-level security on the operation (indent 6)
        if not re.search(r"(?m)^      security:\n(?:^        -[^\n]+\n)+", op_body):
            missing.append(f"{method.upper()} {path_key}")

if missing:
    print(
        f"PATH SECURITY CHECK FAILED: {path}: "
        f"securityDefinitions present but path-level security missing on:"
    )
    for item in missing:
        print(f"  - {item}")
    print(
        "Attach security: under every operation, or remove unused "
        "securityDefinitions. See fixtures/openapi.missing-path-security.yaml."
    )
    sys.exit(1)

# Prefer header API keys over query `key` (access logs / referrers).
sd = re.search(
    r"(?ms)^securityDefinitions:\n"
    r"(?:\s+#.*\n)*"
    r"\s+(\w+):\n"
    r"(?:\s+type:\s*apiKey\n)"
    r"\s+name:\s*[\"']?([^\"'\n]+)[\"']?\n"
    r"\s+in:\s*[\"']?([^\"'\n]+)[\"']?",
    text,
)
if sd:
    scheme, name, loc = sd.group(1), sd.group(2), sd.group(3)
    if loc.strip().lower() == "query":
        print(
            f"PATH SECURITY CHECK WARN: {path}: scheme {scheme} uses "
            f"in: query (name={name}). Prefer header X-API-KEY to avoid "
            "credential leakage via access logs and Referer."
        )

print(
    f"PATH SECURITY CHECK OK: {path} "
    f"({len(path_bodies)} paths, all operations have path-level security)"
)
PY
