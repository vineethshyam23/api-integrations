"""
Vendor-facing HTTP Cloud Function / Cloud Run handler with app-layer API key checks.

Pattern focus:
- Constant-time key compare (hmac.compare_digest) for X-Api-Key or Bearer
- Prefer env VENDOR_API_KEY; optional .env fallback for local only
- Path routing for a small multi-route vendor lookup API
- Parameterized BigQuery reads; project/dataset from env

Entry point name: main  (set as --entry-point=main on deploy)

This is application auth on the backend. Pair with gateway edge auth + IAM
invoker bindings (see pattern 01 and api-and-services-keys/01).
"""

from __future__ import annotations

import hmac
import json
import logging
import os
from pathlib import Path
from typing import Any

from flask import Request, jsonify
from google.cloud import bigquery

logger = logging.getLogger("vendor_api")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

# Reuse across warm invocations
_bq_client: bigquery.Client | None = None
_key_cache: str | None = None
_key_loaded = False


def _log(severity: str, message: str, **fields: Any) -> None:
    payload = {"severity": severity, "message": message, **fields}
    logger.log(
        getattr(logging, severity, logging.INFO),
        json.dumps(payload, default=str),
    )


def _config() -> dict[str, str]:
    return {
        "project_id": os.environ.get("PROJECT_ID", "PROJECT_ID"),
        "dataset_id": os.environ.get("DATASET_ID", "DATASET_ID"),
        # Table names stay configurable so this pattern is not tied to one mart
        "users_table": os.environ.get("USERS_TABLE", "vendor_users"),
        "establishments_table": os.environ.get(
            "ESTABLISHMENTS_TABLE", "vendor_establishments"
        ),
        "pos_users_table": os.environ.get("POS_USERS_TABLE", "vendor_pos_users"),
    }


def _bq() -> bigquery.Client:
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client(project=_config()["project_id"])
    return _bq_client


def _expected_api_key() -> str:
    """
    Load the shared secret once per instance.

    Production: set VENDOR_API_KEY on the function / Cloud Run service.
    Local: optional .env with VENDOR_API_KEY=... (never commit that file).
    """
    global _key_cache, _key_loaded
    if _key_loaded:
        return _key_cache or ""
    _key_loaded = True

    exp = (os.environ.get("VENDOR_API_KEY") or "").strip()
    if exp:
        _key_cache = exp
        return exp

    for directory in (Path(__file__).resolve().parent, Path.cwd()):
        path = directory / ".env"
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("VENDOR_API_KEY="):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    _key_cache = value
                    return value
        except OSError as exc:
            _log("WARNING", "env_file_unreadable", path=str(path), error=str(exc))

    return ""


def _provided_key(request: Request) -> str:
    prov = (
        request.headers.get("X-Api-Key")
        or request.headers.get("x-api-key")
        or request.headers.get("X-API-KEY")
        or ""
    ).strip()
    if prov:
        return prov
    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def _api_key_valid(request: Request) -> bool:
    expected = _expected_api_key()
    if not expected:
        _log("ERROR", "vendor_api_key_not_configured")
        return False
    provided = _provided_key(request)
    if not provided:
        return False
    try:
        return hmac.compare_digest(
            provided.encode("utf-8"),
            expected.encode("utf-8"),
        )
    except (TypeError, ValueError):
        return False


def _fqn(table_env_key: str) -> str:
    cfg = _config()
    return f"`{cfg['project_id']}.{cfg['dataset_id']}.{cfg[table_env_key]}`"


def _rows_or_error(job) -> list[dict[str, Any]] | tuple[Any, int]:
    try:
        rows = [dict(row.items()) for row in job.result()]
        # Normalize: JSON cannot carry some BQ types cleanly; stringify dates.
        cleaned: list[dict[str, Any]] = []
        for row in rows:
            cleaned.append({k: (str(v) if hasattr(v, "isoformat") else v) for k, v in row.items()})
        return cleaned
    except Exception as exc:  # noqa: BLE001 — edge handler
        _log("ERROR", "query_failed", error=str(exc))
        return jsonify(error=500, description="Internal Server Error"), 500


def fetch_users(account_id: str):
    if not account_id:
        return jsonify(error=400, description="Missing account_id"), 400

    query = f"""
    SELECT DISTINCT
      account_id,
      establishment_id,
      salutation,
      first_name,
      last_name,
      mobilephone,
      email
    FROM {_fqn("users_table")}
    WHERE account_id = @account_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("account_id", "STRING", account_id),
        ]
    )
    result = _rows_or_error(_bq().query(query, job_config=job_config))
    if isinstance(result, tuple):
        return result
    if not result:
        return jsonify(error=404, description="Users not found"), 404
    return {account_id: result}


def fetch_establishments(establishment_id: str):
    if not establishment_id:
        return jsonify(error=400, description="Missing establishment_id"), 400

    query = f"""
    SELECT DISTINCT
      account_id,
      establishment_name,
      IF(
        establishment_registration_date IS NULL,
        NULL,
        CAST(DATE(establishment_registration_date) AS STRING)
      ) AS establishment_registration_date,
      establishment_street,
      establishment_postalcode,
      establishment_city,
      establishment_country_code,
      subscription_status,
      IF(
        subscription_start_date IS NULL,
        NULL,
        CAST(DATE(subscription_start_date) AS STRING)
      ) AS subscription_start_date,
      IF(
        asset_disabled_date IS NULL,
        NULL,
        CAST(DATE(asset_disabled_date) AS STRING)
      ) AS asset_disabled_date,
      main_category,
      product_code,
      paid_asset
    FROM {_fqn("establishments_table")}
    WHERE establishment_id = @establishment_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "establishment_id", "STRING", establishment_id
            ),
        ]
    )
    result = _rows_or_error(_bq().query(query, job_config=job_config))
    if isinstance(result, tuple):
        return result
    if not result:
        return jsonify(error=404, description="Establishment not found"), 404
    return {establishment_id: result}


def fetch_pos_users(enterprise_id: str, country_code: str):
    if not enterprise_id or not country_code:
        return (
            jsonify(error=400, description="Missing enterprise_id or country_code"),
            400,
        )

    query = f"""
    SELECT DISTINCT
      account_id,
      establishment_id,
      salutation,
      first_name,
      last_name,
      mobilephone,
      email
    FROM {_fqn("pos_users_table")}
    WHERE CAST(enterprise_id AS STRING) = @enterprise_id
      AND country_code = @country_code
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("enterprise_id", "STRING", enterprise_id),
            bigquery.ScalarQueryParameter("country_code", "STRING", country_code),
        ]
    )
    result = _rows_or_error(_bq().query(query, job_config=job_config))
    if isinstance(result, tuple):
        return result
    if not result:
        return jsonify(error=404, description="Users not found"), 404
    return {f"{enterprise_id}_{country_code}": result}


def _cors_headers() -> dict[str, str]:
    origin = os.environ.get("CORS_ALLOW_ORIGIN", "*")
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Api-Key",
        "Access-Control-Max-Age": "3600",
    }


def _with_cors(body, status: int):
    headers = _cors_headers()
    if hasattr(body, "headers"):
        for k, v in headers.items():
            body.headers[k] = v
        return body, status
    return body, status, headers


def main(request: Request):
    """Cloud Functions / Cloud Run HTTP entry point."""
    if request.method == "OPTIONS":
        return ("", 204, _cors_headers())

    headers = _cors_headers()

    if request.method != "GET":
        return jsonify(error=405, description="Method Not Allowed"), 405, headers

    if not _api_key_valid(request):
        _log("WARNING", "auth_rejected", path=request.path)
        return (
            jsonify(
                error=401,
                description="Unauthorized - valid X-Api-Key or Bearer token required",
            ),
            401,
            headers,
        )

    path = request.path or ""
    _log("INFO", "request_accepted", path=path)

    try:
        if path.endswith("/getUser") or path == "/getUser":
            result = fetch_users(request.args.get("account_id") or "")
        elif path.endswith("/getEstablishments") or path == "/getEstablishments":
            result = fetch_establishments(request.args.get("establishment_id") or "")
        elif path.endswith("/getPosUser") or path == "/getPosUser":
            result = fetch_pos_users(
                request.args.get("enterprise_id") or "",
                request.args.get("country_code") or "",
            )
        else:
            return jsonify(error=404, description="Endpoint not found"), 404, headers

        if isinstance(result, tuple):
            return _with_cors(result[0], result[1])

        response = jsonify(result)
        for k, v in headers.items():
            response.headers[k] = v
        _log("INFO", "request_ok", path=path)
        return response, 200
    except ValueError as exc:
        _log("ERROR", "value_error", error=str(exc), path=path)
        return jsonify(error=400, description="Invalid parameter value"), 400, headers
    except Exception as exc:  # noqa: BLE001
        _log("ERROR", "request_failed", error=str(exc), path=path)
        return jsonify(error=500, description="Internal Server Error"), 500, headers
