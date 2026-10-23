#!/usr/bin/env bash
# Fail if openapi.dev.yaml and openapi.prd.yaml diverge on schema-fidelity
# surfaces that pattern 11's twin gate does not emphasize:
#   - 200 response $ref target names (no foreign product leftovers)
#   - definition key sets
#   - records items must be a $ref (not additionalProperties: true)
#   - HTTP response status code sets per operation
# Also re-checks paths / operationIds / path security / backends differ.
#
# Usage:
#   ./check-schema-fidelity.sh              # compare openapi.prd.yaml vs openapi.dev.yaml
#   ./check-schema-fidelity.sh --self       # must FAIL using the foreign-ref fixture
#
# Requires: python3 (stdlib only).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRD="${ROOT}/openapi.prd.yaml"
DEV="${ROOT}/openapi.dev.yaml"
FIXTURE="${ROOT}/fixtures/openapi.prd.foreign-ref.yaml"

SELF=0
if [[ "${1:-}" == "--self" ]]; then
  SELF=1
  PRD="${FIXTURE}"
fi

if [[ ! -f "${PRD}" || ! -f "${DEV}" ]]; then
  echo "Missing twin files: ${PRD} and/or ${DEV}" >&2
  exit 2
fi

set +e
python3 - "${PRD}" "${DEV}" <<'PY'
import re
import sys
from pathlib import Path

prd_path, dev_path = Path(sys.argv[1]), Path(sys.argv[2])
prd_text, dev_text = prd_path.read_text(), dev_path.read_text()


def path_keys(text: str) -> list[str]:
    # Support both `  /path:` and `  "/path":`
    return re.findall(r'(?m)^  "?(/[^"\s:]+)"?:\s*$', text)


def operation_ids(text: str) -> list[str]:
    return re.findall(r"(?m)^\s+operationId:\s*[\"']?([^\"'\s]+)[\"']?", text)


def security_blocks(text: str) -> list[str]:
    return re.findall(
        r"(?m)^\s{6}security:\n(?:^\s{8}-[^\n]+\n)+",
        text,
    )


def security_def_header(text: str) -> str | None:
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
        return None
    return f"{m.group(1)}|{m.group(2)}|{m.group(3)}"


def backend_addresses(text: str) -> list[str]:
    return re.findall(
        r"(?m)^\s+address:\s*[\"']?([^\"'\s]+)[\"']?",
        text,
    )


def response_status_sets(text: str) -> dict[str, list[str]]:
    """Map operationId -> sorted list of response status codes."""
    result: dict[str, list[str]] = {}
    current_op: str | None = None
    in_responses = False
    statuses: list[str] = []
    for line in text.splitlines():
        m_op = re.match(r"^\s+operationId:\s*[\"']?([^\"'\s]+)[\"']?", line)
        if m_op:
            if current_op is not None:
                result[current_op] = sorted(statuses)
            current_op = m_op.group(1)
            statuses = []
            in_responses = False
            continue
        if re.match(r"^\s+responses:\s*$", line):
            in_responses = True
            continue
        if in_responses:
            # leave responses block on next peer key at same indent as responses
            if re.match(r"^\s{6}\w", line) and not re.match(r"^\s{6}'?\d", line):
                in_responses = False
                continue
            m_st = re.match(r"^\s{8}['\"]?(\d{3}|default)['\"]?:\s*$", line)
            if m_st and current_op:
                statuses.append(m_st.group(1))
    if current_op is not None:
        result[current_op] = sorted(statuses)
    return result


def response_ref_targets(text: str) -> dict[str, str]:
    """Map operationId -> 200 schema $ref definition name."""
    result: dict[str, str] = {}
    current_op: str | None = None
    in_200 = False
    for line in text.splitlines():
        m_op = re.match(r"^\s+operationId:\s*[\"']?([^\"'\s]+)[\"']?", line)
        if m_op:
            current_op = m_op.group(1)
            in_200 = False
            continue
        if re.match(r"^\s{8}['\"]?200['\"]?:\s*$", line):
            in_200 = True
            continue
        if in_200:
            if re.match(r"^\s{8}['\"]?\d{3}['\"]?:", line):
                in_200 = False
                continue
            m_ref = re.search(
                r"\$ref:\s*[\"']?#/definitions/([^\"'\s]+)[\"']?",
                line,
            )
            if m_ref and current_op:
                result[current_op] = m_ref.group(1)
                in_200 = False
    return result


def definition_keys(text: str) -> list[str]:
    keys: list[str] = []
    in_defs = False
    for line in text.splitlines():
        if line.startswith("definitions:"):
            in_defs = True
            continue
        if not in_defs:
            continue
        if re.match(r"^[A-Za-z]", line) and not line.startswith(" "):
            break
        m = re.match(r"^  ([A-Za-z_][\w]*):\s*$", line)
        if m:
            keys.append(m.group(1))
    return sorted(keys)


def records_items_shape(text: str) -> dict[str, str]:
    """
    For each definition that has a `records:` array property, classify items:
      - 'ref:<Name>' when items.$ref is set
      - 'additionalProperties' when items is object + additionalProperties
      - 'other' otherwise
    """
    shapes: dict[str, str] = {}
    current_def: str | None = None
    in_records = False
    in_items = False
    depth_hint = ""
    for line in text.splitlines():
        if line.startswith("definitions:"):
            continue
        m_def = re.match(r"^  ([A-Za-z_][\w]*):\s*$", line)
        if m_def and line.startswith("  ") and not line.startswith("   "):
            current_def = m_def.group(1)
            in_records = False
            in_items = False
            continue
        if current_def is None:
            continue
        if re.match(r"^      records:\s*$", line):
            in_records = True
            in_items = False
            continue
        if in_records and re.match(r"^      [A-Za-z_]", line) and not line.startswith(
            "      records:"
        ):
            in_records = False
            in_items = False
            continue
        if in_records and re.match(r"^        items:\s*$", line):
            in_items = True
            continue
        if in_items:
            m_ref = re.search(
                r"\$ref:\s*[\"']?#/definitions/([^\"'\s]+)[\"']?",
                line,
            )
            if m_ref:
                shapes[current_def] = f"ref:{m_ref.group(1)}"
                in_items = False
                in_records = False
                continue
            if re.search(r"additionalProperties:\s*true", line):
                shapes[current_def] = "additionalProperties"
                in_items = False
                in_records = False
                continue
            if re.match(r"^          type:\s*", line):
                depth_hint = "typed"
                continue
            # leave items block
            if re.match(r"^        [A-Za-z_]", line) and not line.startswith(
                "        items:"
            ):
                if current_def not in shapes:
                    shapes[current_def] = "other" if depth_hint else "other"
                in_items = False
                in_records = False
    return shapes


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
        f"prd={len(prd_sec)} dev={len(dev_sec)}"
    )
elif [re.sub(r"\s+", " ", s.strip()) for s in prd_sec] != [
    re.sub(r"\s+", " ", s.strip()) for s in dev_sec
]:
    errors.append("path-level security requirements differ between twins")

prd_sd, dev_sd = security_def_header(prd_text), security_def_header(dev_text)
if prd_sd != dev_sd:
    errors.append(f"securityDefinitions header name/in differ: prd={prd_sd} dev={dev_sd}")

prd_refs, dev_refs = response_ref_targets(prd_text), response_ref_targets(dev_text)
if prd_refs != dev_refs:
    errors.append(
        f"200 response $ref targets differ (foreign leftover?): "
        f"prd={prd_refs} dev={dev_refs}"
    )

prd_defs, dev_defs = definition_keys(prd_text), definition_keys(dev_text)
if prd_defs != dev_defs:
    errors.append(
        f"definition key sets differ: "
        f"only_prd={sorted(set(prd_defs) - set(dev_defs))} "
        f"only_dev={sorted(set(dev_defs) - set(prd_defs))}"
    )

prd_status, dev_status = response_status_sets(prd_text), response_status_sets(dev_text)
if prd_status != dev_status:
    errors.append(
        f"response status code sets differ: prd={prd_status} dev={dev_status}"
    )

prd_shapes, dev_shapes = records_items_shape(prd_text), records_items_shape(dev_text)
# Any twin using additionalProperties on records while the other uses $ref is a fail.
all_defs = set(prd_shapes) | set(dev_shapes)
for d in sorted(all_defs):
    ps, ds = prd_shapes.get(d), dev_shapes.get(d)
    if ps != ds:
        errors.append(
            f"records items shape for definition {d!r} differs: "
            f"prd={ps} dev={ds}"
        )
    if ps == "additionalProperties" or ds == "additionalProperties":
        errors.append(
            f"definition {d!r} uses additionalProperties: true on records items "
            f"— require a typed $ref (got prd={ps} dev={ds})"
        )

# Also flag foreign-looking 200 $ref names that do not match the path leaf theme.
for env_label, refs in (("prd", prd_refs), ("dev", dev_refs)):
    for op, name in refs.items():
        if re.search(r"(?i)maileon|otherproduct|legacy|copy|tmp", name):
            errors.append(
                f"{env_label} operation {op} 200 $ref looks foreign: {name}"
            )

prd_backends, dev_backends = backend_addresses(prd_text), backend_addresses(dev_text)
if not prd_backends or not dev_backends:
    errors.append("missing x-google-backend address in one or both twins")
elif prd_backends == dev_backends:
    errors.append(
        "backend addresses are identical — twins should point at different "
        "env backends (BACKEND_URL vs BACKEND_URL_DEV)"
    )

if errors:
    print("check-schema-fidelity FAILED:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print("check-schema-fidelity OK:")
print(f"  paths={path_keys(prd_text)}")
print(f"  operationIds={operation_ids(prd_text)}")
print(f"  200 $refs={prd_refs}")
print(f"  definitions={prd_defs}")
print(f"  statuses={prd_status}")
print(f"  records_shapes={prd_shapes}")
print(f"  backend prd={prd_backends[0]}")
print(f"  backend dev={dev_backends[0]}")
PY
status=$?
set -e

if [[ "${SELF}" -eq 1 ]]; then
  if [[ "${status}" -eq 0 ]]; then
    echo "check-schema-fidelity --self FAILED: expected foreign-ref fixture to fail" >&2
    exit 1
  fi
  echo "check-schema-fidelity --self OK (foreign-ref fixture correctly failed)"
  exit 0
fi

exit "${status}"
