#!/usr/bin/env bash
# Fail if openapi.dev.yaml and openapi.prd.yaml diverge on contract surfaces
# that must stay identical across a multi-route panel gateway twin pair:
# paths, operationIds, path-level security, securityDefinitions, and
# definition property types.
#
# Allowed intentional diffs: info.title / info.version / info.description,
# and every x-google-backend.address (region mix and DEV consolidation OK).
#
# Multi-route extra: EVERY backend address must differ pairwise between twins.
# Identical backends on even one path is a fail — copying PRD URLs into DEV
# for "just this one route" is how mixed-env dashboards happen.
#
# Requires: python3 (stdlib only).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRD="${ROOT}/openapi.prd.yaml"
DEV="${ROOT}/openapi.dev.yaml"

if [[ ! -f "${PRD}" || ! -f "${DEV}" ]]; then
  echo "Missing twin files: ${PRD} and/or ${DEV}" >&2
  exit 2
fi

python3 - "${PRD}" "${DEV}" <<'PY'
import re
import sys
from pathlib import Path

prd_path, dev_path = Path(sys.argv[1]), Path(sys.argv[2])
prd_text, dev_text = prd_path.read_text(), dev_path.read_text()


def path_keys(text: str) -> list[str]:
    return re.findall(r"(?m)^  (/[^:\s]+):", text)


def operation_ids(text: str) -> list[str]:
    return re.findall(r"(?m)^\s+operationId:\s*[\"']?([^\"'\s]+)[\"']?", text)


def security_blocks(text: str) -> list[str]:
    return re.findall(
        r"(?m)^\s{6}security:\n(?:^\s{8}-[^\n]+\n)+",
        text,
    )


def security_def_header(text: str) -> tuple[str | None, str | None]:
    m = re.search(
        r"(?ms)^securityDefinitions:\n"
        r"(?:\s+#.*\n)*"
        r"\s+(\w+):\n"
        r"(?:\s+type:\s*apiKey\n)"
        r"\s+name:\s*[\"']?([^\"'\n]+)[\"']?\n"
        r"\s+in:\s*[\"']?([^\"'\n]+)[\"']?",
        text,
    )
    if not m:
        return None, None
    return f"{m.group(1)}|{m.group(2)}|{m.group(3)}", m.group(0)


def definition_prop_types(text: str) -> dict[str, str]:
    props: dict[str, str] = {}
    current_def = None
    current_prop = None
    in_defs = False
    for line in text.splitlines():
        if line.startswith("definitions:"):
            in_defs = True
            continue
        if not in_defs:
            continue
        if re.match(r"^[A-Za-z]", line) and not line.startswith(" "):
            break
        m_def = re.match(r"^  ([A-Za-z_][\w-]*):$", line)
        if m_def:
            current_def = m_def.group(1)
            current_prop = None
            continue
        m_prop = re.match(r"^      ([A-Za-z_][\w]*):$", line)
        if m_prop and current_def:
            current_prop = m_prop.group(1)
            continue
        m_type = re.match(r"^        type:\s*[\"']?([^\"'\s]+)[\"']?", line)
        if m_type and current_def and current_prop:
            props[f"{current_def}.{current_prop}"] = m_type.group(1)
            current_prop = None
    return props


def backend_addresses(text: str) -> list[str]:
    return re.findall(
        r"(?m)^\s+address:\s*[\"']?([^\"'\s]+)[\"']?",
        text,
    )


errors: list[str] = []

prd_paths, dev_paths = path_keys(prd_text), path_keys(dev_text)
if prd_paths != dev_paths:
    errors.append(f"path keys differ: prd={prd_paths} dev={dev_paths}")

if operation_ids(prd_text) != operation_ids(dev_text):
    errors.append(
        f"operationId set differs: prd={operation_ids(prd_text)} "
        f"dev={operation_ids(dev_text)}"
    )

prd_sec, dev_sec = security_blocks(prd_text), security_blocks(dev_text)
if len(prd_sec) != len(dev_sec):
    errors.append(
        f"path-level security block count differs: "
        f"prd={len(prd_sec)} dev={len(dev_sec)} "
        "(DEV often drops security: while leaving securityDefinitions — fail closed)"
    )
elif [re.sub(r"\s+", " ", s.strip()) for s in prd_sec] != [
    re.sub(r"\s+", " ", s.strip()) for s in dev_sec
]:
    errors.append("path-level security requirements differ between twins")

prd_sd, _ = security_def_header(prd_text)
dev_sd, _ = security_def_header(dev_text)
if prd_sd != dev_sd:
    errors.append(f"securityDefinitions header name/in differ: prd={prd_sd} dev={dev_sd}")

prd_props, dev_props = definition_prop_types(prd_text), definition_prop_types(dev_text)
if prd_props != dev_props:
    only_prd = sorted(set(prd_props) - set(dev_props))
    only_dev = sorted(set(dev_props) - set(prd_props))
    type_mismatches = sorted(
        k for k in set(prd_props) & set(dev_props) if prd_props[k] != dev_props[k]
    )
    errors.append(
        "definition property types / keys differ: "
        f"only_prd={only_prd} only_dev={only_dev} type_mismatches="
        + str([(k, prd_props[k], dev_props[k]) for k in type_mismatches])
    )

prd_backends, dev_backends = backend_addresses(prd_text), backend_addresses(dev_text)
if not prd_backends or not dev_backends:
    errors.append("missing x-google-backend address in one or both twins")
elif len(prd_backends) != len(dev_backends):
    errors.append(
        f"backend address count differs: prd={len(prd_backends)} "
        f"dev={len(dev_backends)}"
    )
elif len(prd_backends) != len(prd_paths):
    errors.append(
        f"backend count ({len(prd_backends)}) != path count ({len(prd_paths)}) "
        "— every route needs its own x-google-backend"
    )
else:
    identical = [
        (prd_paths[i], prd_backends[i], dev_backends[i])
        for i in range(len(prd_backends))
        if prd_backends[i] == dev_backends[i]
    ]
    if identical:
        errors.append(
            "one or more backend addresses are identical across twins "
            f"(path, prd, dev)={identical}"
        )
    if len(set(prd_backends)) != len(prd_backends):
        errors.append(
            f"duplicate PRD backends (each route should have a distinct function): "
            f"{prd_backends}"
        )
    if len(set(dev_backends)) != len(dev_backends):
        errors.append(
            f"duplicate DEV backends (each route should have a distinct function): "
            f"{dev_backends}"
        )

if errors:
    print("check-twins FAILED:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print("check-twins OK (multi-route):")
print(f"  paths={prd_paths}")
print(f"  operationIds={operation_ids(prd_text)}")
print(f"  securityDefinitions={prd_sd}")
print(f"  backends checked={len(prd_backends)} (all pairwise distinct)")
for i, path in enumerate(prd_paths):
    print(f"    {path}")
    print(f"      prd={prd_backends[i]}")
    print(f"      dev={dev_backends[i]}")
print(f"  definition props checked={len(prd_props)}")
PY
