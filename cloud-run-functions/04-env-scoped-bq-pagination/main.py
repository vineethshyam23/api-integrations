"""HTTP Cloud Function: env-scoped BigQuery table + paginated market-potential reads.

Sanitized from a production POS / market-potential extract handler. Focus:
DEPLOY_ENV-driven table selection, optional full-table override, country allowlist,
parameterized pagination, and gated error detail for non-prod debugging.
"""

import logging
import os
from typing import Any, Dict, Tuple, Union

import numpy as np
import pandas as pd
from flask import Response, jsonify, request
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = bigquery.Client()

DEFAULT_PAGE_SIZE = 100
DEFAULT_PAGE_NUMBER = 1
MAX_PAGE_SIZE = 10000
ALLOWED_COUNTRY_CODES = ("DE", "FR", "ES", "IT")

# Columns returned to callers. Keep this list explicit — never SELECT *.
DEFAULT_COLUMNS = (
    "country_code",
    "cust_no",
    "home_store_id",
    "annual_sale",
)


def _cors_origin() -> str:
    # Prefer an explicit allow-list origin in prod; "*" is only for local bring-up.
    return os.environ.get("CORS_ALLOW_ORIGIN", "*")


def _expose_error_detail() -> bool:
    """Return exception detail in JSON only when EXPOSE_ERROR_DETAIL is truthy (dev)."""
    return os.environ.get("EXPOSE_ERROR_DETAIL", "").lower() in ("1", "true", "yes")


def _internal_error_payload(exc: BaseException) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "error": 500,
        "description": "Internal Server Error",
    }
    if _expose_error_detail():
        body["detail"] = str(exc)
        body["exceptionType"] = type(exc).__name__
    return body


def _resolve_bq_table() -> str:
    """
    Resolve the BigQuery table for this API.

    DEPLOY_ENV is required and must be exactly ``dev`` or ``prod`` (lowercase).
    Optional MARKET_POTENTIAL_BQ_TABLE = full ``project.dataset.table`` overrides
    the default for that environment.
    """
    raw = os.environ.get("DEPLOY_ENV", "").strip()
    if raw == "dev":
        default_table = "PROJECT_ID_DEV.DATASET_ID.market_potential"
    elif raw == "prod":
        default_table = "PROJECT_ID.DATASET_ID.market_potential"
    else:
        if not raw:
            raise ValueError(
                "DEPLOY_ENV is required. Set DEPLOY_ENV=dev or DEPLOY_ENV=prod (lowercase)."
            )
        raise ValueError(
            f"Invalid DEPLOY_ENV={raw!r}. Must be exactly dev or prod (lowercase)."
        )

    override = os.environ.get("MARKET_POTENTIAL_BQ_TABLE", "").strip()
    resolved = override if override else default_table

    logger.info(
        "market_potential BQ table: %s (DEPLOY_ENV=%s)",
        resolved,
        raw,
    )
    return resolved


def _table_config() -> Dict[str, Any]:
    # Resolve per request so cold starts fail clearly and deploys can change env
    # without relying on import-time evaluation quirks.
    return {
        "table": _resolve_bq_table(),
        "columns": list(DEFAULT_COLUMNS),
    }


def fetch_data_with_pagination(
    table_config: Dict[str, Any],
    country_code: str,
    page_size: int,
    page_number: int,
) -> Union[Dict[str, Any], Tuple[Response, int]]:
    """Fetch rows for one country with pageSize / pageNumber pagination."""
    if page_size < 1 or page_number < 1:
        return (
            jsonify(
                error=400,
                description="pageSize and pageNumber must be positive integers",
            ),
            400,
        )
    if page_size > MAX_PAGE_SIZE:
        return (
            jsonify(error=400, description=f"pageSize cannot exceed {MAX_PAGE_SIZE}"),
            400,
        )

    offset = (page_number - 1) * page_size
    table_name = table_config["table"]
    column_list = (
        table_config["columns"]
        + table_config.get("date_columns", [])
        + table_config.get("timestamp_columns", [])
    )
    columns = ", ".join(column_list)

    count_query = f"""
    SELECT COUNT(*) as total
    FROM `{table_name}`
    WHERE country_code = @country_code
    """

    query = f"""
    SELECT {columns}
    FROM `{table_name}`
    WHERE country_code = @country_code
    ORDER BY country_code, cust_no, home_store_id
    LIMIT @page_size OFFSET @offset
    """

    try:
        count_job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("country_code", "STRING", country_code),
            ]
        )
        count_df = client.query(count_query, job_config=count_job_config).to_dataframe()
        total_count = int(count_df["total"].iloc[0])
        total_pages = (
            (total_count + page_size - 1) // page_size if total_count else 0
        )

        # Empty / past-last page → 404 (same contract as sibling extract APIs)
        if offset >= total_count:
            return jsonify(error=404, description="No data found"), 404

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("country_code", "STRING", country_code),
                bigquery.ScalarQueryParameter("page_size", "INT64", page_size),
                bigquery.ScalarQueryParameter("offset", "INT64", offset),
            ]
        )

        df = client.query(query, job_config=job_config).to_dataframe()

        date_columns = set(table_config.get("date_columns", []))
        for col in df.columns:
            if col in date_columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
                df[col] = (
                    df[col].dt.strftime("%Y-%m-%d").where(df[col].notna(), None)
                )

        results = df.replace({np.nan: None}).to_dict(orient="records")

        if not results:
            return jsonify(error=404, description="No data found"), 404

        return {
            "records": results,
            "pagination": {
                "total": total_count,
                "pageSize": page_size,
                "pageNumber": page_number,
                "totalPages": total_pages,
            },
        }

    except Exception as error:
        logger.exception("BigQuery query on %s failed", table_name)
        return jsonify(_internal_error_payload(error)), 500


def fetch_market_potential(
    country_code: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    page_number: int = DEFAULT_PAGE_NUMBER,
) -> Union[Dict[str, Any], Tuple[Response, int]]:
    return fetch_data_with_pagination(
        _table_config(), country_code, page_size, page_number
    )


def main(request) -> Union[Response, Tuple[Union[str, Response], int, Dict[str, str]]]:
    """
    GET /getMarketPotentialData

    Query params:
      countryCode or country_code (required): ISO 3166-1 alpha-2 in the allowlist
      pageSize, pageNumber (optional): pagination, pageNumber starts at 1
    """
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": _cors_origin(),
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type, X-API-KEY, X-Api-Key",
            "Access-Control-Max-Age": "3600",
        }
        return ("", 204, headers)

    headers = {"Access-Control-Allow-Origin": _cors_origin()}

    if request.method != "GET":
        return jsonify(error=405, description="Method Not Allowed"), 405, headers

    try:
        path = request.path

        raw_country = request.args.get("countryCode") or request.args.get(
            "country_code"
        )
        if raw_country is None or not str(raw_country).strip():
            return (
                jsonify(
                    error=400,
                    description=(
                        "countryCode query parameter is required "
                        "(ISO 3166-1 alpha-2, e.g. DE)"
                    ),
                ),
                400,
                headers,
            )
        country_code = str(raw_country).strip().upper()
        if country_code not in ALLOWED_COUNTRY_CODES:
            return (
                jsonify(
                    error=400,
                    description=(
                        "Invalid countryCode. It has to be one of the following "
                        f"values: {', '.join(ALLOWED_COUNTRY_CODES)}"
                    ),
                ),
                400,
                headers,
            )

        page_size = request.args.get("pageSize", default=DEFAULT_PAGE_SIZE, type=int)
        page_number = request.args.get(
            "pageNumber", default=DEFAULT_PAGE_NUMBER, type=int
        )

        # Accept exact path or suffix (gateway sometimes preserves leaf only).
        if path == "/getMarketPotentialData" or path.endswith(
            "/getMarketPotentialData"
        ):
            result = fetch_market_potential(
                country_code=country_code,
                page_size=page_size,
                page_number=page_number,
            )
        else:
            return jsonify(error=404, description="Endpoint not found"), 404, headers

        if isinstance(result, tuple):
            return result[0], result[1], headers

        return jsonify(result), 200, headers

    except Exception as error:
        logger.exception("Request processing failed")
        return jsonify(_internal_error_payload(error)), 500, headers
