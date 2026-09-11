#!/usr/bin/env bash
# Fail if openapi.dev.yaml and openapi.prd.yaml diverge on contract surfaces
# that must stay identical: paths, operationIds, security requirements,
# securityDefinitions, and definition property types.
#
# Allowed intentional diffs: info.title / info.description, and
# x-google-backend.address (and optional deadline).
#
# Requires: python3 (stdlib only). No PyYAML dependency — uses a thin
# structural extract via regex + JSON for the checks we care about.
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
    # Swagger 2 path keys under paths: (indent 2, starts with /)
    return re.findall(r"(?m)^  (/[^:\s]+):", text)


def operation_ids(text: str) -> list[str]:
    return re.findall(r"(?m)^\s+operationId:\s*[\"']?([^\"'\s]+)[\"']?", text)


def security_blocks(text: str) -> list[str]:
    # Capture path-level "security:" lists (api_key / ApiKeyAuth / Bearer).
    # Do not use DOTALL — ".+" would swallow the rest of the file.
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
    # Map "Definition.prop" -> type for Activity-style definitions.
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
        m_def = re.match(r"^  ([A-Za-z_][\w]*):$", line)
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

if path_keys(prd_text) != path_keys(dev_text):
    errors.append(
        f"path keys differ: prd={path_keys(prd_text)} dev={path_keys(dev_text)}"
    )

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
elif prd_backends == dev_backends:
    errors.append(
        "backend addresses are identical — twins should point at different "
        "env backends (PROJECT_ID vs PROJECT_ID_DEV / separate Cloud Run URLs)"
    )

if errors:
    print("check-twins FAILED:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print("check-twins OK:")
print(f"  paths={path_keys(prd_text)}")
print(f"  operationIds={operation_ids(prd_text)}")
print(f"  securityDefinitions={prd_sd}")
print(f"  backend prd={prd_backends[0]}")
print(f"  backend dev={dev_backends[0]}")
print(f"  definition props checked={len(prd_props)}")
PY
