"""HTTP Cloud Run / Functions handler: inbound dual-route establishment extract.

Two paths, one service:
  /establishments       — full refined catalog (hard 404 on empty page)
  /establishments/daily — NTILE day-of-month bucket (soft empty + message)

Sanitized from a production partner tourism/inbound establishment feed.
Distinct from outbound OIDC pull (pattern 07) and multi-table marketing
triggers (pattern 12): same schema, two extract modes, calendar-aware daily slice.
"""

from __future__ import annotations

import calendar
import logging
import math
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from flask import Response, jsonify, request
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = bigquery.Client()

DEFAULT_PAGE_SIZE = 100
DEFAULT_PAGE_NUMBER = 1
MAX_PAGE_SIZE = 1000

# Explicit column list — never SELECT * on partner extracts.
ESTABLISHMENT_COLUMNS = [
    "name",
    "street",
    "postal_code",
    "city",
    "country",
    "formatted_address",
    "latitude",
    "longitude",
    "establishment_id",
    "places_legacy_id",
    "establishment_type",
    "cuisine_type",
    "price_category",
    "url",
    "flag_order",
    "flag_reservation",
    "menu_url",
    "rating",
    "opening_hours",
]


def _cors_origin() -> str:
    return os.environ.get("CORS_ALLOW_ORIGIN", "*")


def _expose_error_detail() -> bool:
    return os.environ.get("EXPOSE_ERROR_DETAIL", "").lower() in ("1", "true", "yes")


def _env_table(env_key: str, default: str) -> str:
    return os.environ.get(env_key, default).strip() or default


def _catalog_table() -> str:
    return _env_table(
        "ESTABLISHMENTS_TABLE",
        "PROJECT_ID.DATASET_ID.establishments",
    )


def _daily_table() -> str:
    return _env_table(
        "ESTABLISHMENTS_DAILY_TABLE",
        "PROJECT_ID.DATASET_ID.establishments_daily",
    )


def _cors_headers() -> Dict[str, str]:
    return {"Access-Control-Allow-Origin": _cors_origin()}


def _internal_error(
    exc: BaseException,
) -> Tuple[Response, int, Dict[str, str]]:
    body: Dict[str, Any] = {
        "error": 500,
        "description": "Internal Server Error",
    }
    if _expose_error_detail():
        body["detail"] = str(exc)
        body["exceptionType"] = type(exc).__name__
    return jsonify(body), 500, _cors_headers()


def _days_in_month_minus_1(now: Optional[datetime] = None) -> int:
    """Bucket count for NTILE: days in current month minus 1."""
    current = now or datetime.now()
    days_in_month = calendar.monthrange(current.year, current.month)[1]
    return max(days_in_month - 1, 1)


def _yesterday_day_of_month(now: Optional[datetime] = None) -> int:
    """Day-of-month for yesterday — selects today's NTILE bucket."""
    current = now or datetime.now()
    return (current - timedelta(days=1)).day


def _parse_paging() -> Union[Tuple[int, int], Tuple[Response, int, Dict[str, str]]]:
    page_size = request.args.get("pageSize", default=DEFAULT_PAGE_SIZE, type=int)
    page_number = request.args.get(
        "pageNumber", default=DEFAULT_PAGE_NUMBER, type=int
    )
    if (
        page_size is None
        or page_number is None
        or page_size < 1
        or page_number < 1
        or page_size > MAX_PAGE_SIZE
    ):
        return (
            jsonify(
                error=400,
                description=(
                    "pageSize and pageNumber must be positive integers; "
                    f"pageSize max is {MAX_PAGE_SIZE}"
                ),
            ),
            400,
            _cors_headers(),
        )
    return page_size, page_number


def _rows_to_records(df) -> List[Dict[str, Any]]:
    return df.replace({np.nan: None}).to_dict(orient="records")


def _select_list() -> str:
    return ",\n            ".join(ESTABLISHMENT_COLUMNS)


def fetch_full_catalog(
    page_size: int, page_number: int
) -> Union[Dict[str, Any], Tuple[Response, int]]:
    """Full catalog path — empty page is a hard 404."""
    offset = (page_number - 1) * page_size
    table = _catalog_table()
    cols = _select_list()

    data_sql = f"""
        SELECT DISTINCT
            {cols}
        FROM `{table}`
        ORDER BY establishment_id
        LIMIT @page_size OFFSET @offset
    """
    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM `{table}`
    """

    try:
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("page_size", "INT64", page_size),
                bigquery.ScalarQueryParameter("offset", "INT64", offset),
            ]
        )
        df = client.query(data_sql, job_config=job_config).to_dataframe()
        results = _rows_to_records(df)

        if not results:
            return jsonify(error=404, description="No data found"), 404

        count_df = client.query(count_sql).to_dataframe()
        total_count = int(count_df["total"].iloc[0])
        total_pages = math.ceil(total_count / page_size) if page_size else 0

        return {
            "records": results,
            "pagination": {
                "total": total_count,
                "pageSize": page_size,
                "pageNumber": page_number,
                "totalPages": total_pages,
            },
        }
    except Exception as exc:
        logger.exception("Full catalog query failed")
        return _internal_error(exc)[:2]


def fetch_daily_bucket(
    page_size: int, page_number: int, now: Optional[datetime] = None
) -> Union[Dict[str, Any], Tuple[Response, int]]:
    """
    Daily path: NTILE over establishment_id with yesterday's day-of-month as
    the bucket. First calendar day (and empty buckets) return 200 + message
    so partners can poll without treating quiet days as transport failures.
    """
    current = now or datetime.now()
    offset = (page_number - 1) * page_size
    bucket_count = _days_in_month_minus_1(current)
    bucket_index = _yesterday_day_of_month(current)
    table = _daily_table()
    cols = _select_list()

    # Soft-empty on the first calendar day — daily pipeline often idle then.
    if current.day == 1:
        return {
            "records": [],
            "message": "No new data got updated",
            "pagination": {
                "total": 0,
                "pageSize": page_size,
                "pageNumber": page_number,
                "totalPages": 0,
            },
        }

    data_sql = f"""
        SELECT DISTINCT
            {cols}
        FROM `{table}`
        QUALIFY NTILE(@bucket_count) OVER (ORDER BY establishment_id) = @bucket_index
        ORDER BY establishment_id
        LIMIT @page_size OFFSET @offset
    """
    count_sql = f"""
        WITH daily_slice AS (
            SELECT establishment_id
            FROM `{table}`
            QUALIFY NTILE(@bucket_count) OVER (ORDER BY establishment_id) = @bucket_index
        )
        SELECT COUNT(*) AS total
        FROM daily_slice
    """

    params = [
        bigquery.ScalarQueryParameter("bucket_count", "INT64", bucket_count),
        bigquery.ScalarQueryParameter("bucket_index", "INT64", bucket_index),
        bigquery.ScalarQueryParameter("page_size", "INT64", page_size),
        bigquery.ScalarQueryParameter("offset", "INT64", offset),
    ]

    try:
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        df = client.query(data_sql, job_config=job_config).to_dataframe()
        results = _rows_to_records(df)

        if not results:
            return {
                "records": [],
                "message": "No new data got updated",
                "pagination": {
                    "total": 0,
                    "pageSize": page_size,
                    "pageNumber": page_number,
                    "totalPages": 0,
                },
            }

        count_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("bucket_count", "INT64", bucket_count),
                bigquery.ScalarQueryParameter("bucket_index", "INT64", bucket_index),
            ]
        )
        count_df = client.query(count_sql, job_config=count_config).to_dataframe()
        total_count = int(count_df["total"].iloc[0])
        total_pages = math.ceil(total_count / page_size) if page_size else 0

        return {
            "records": results,
            "pagination": {
                "total": total_count,
                "pageSize": page_size,
                "pageNumber": page_number,
                "totalPages": total_pages,
            },
        }
    except Exception as exc:
        logger.exception("Daily bucket query failed")
        return _internal_error(exc)[:2]


def main(request):
    """Entry point for Cloud Functions / Functions Framework on Cloud Run."""
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": _cors_origin(),
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type, X-API-KEY",
            "Access-Control-Max-Age": "3600",
        }
        return ("", 204, headers)

    headers = _cors_headers()

    if request.method != "GET":
        return jsonify(error=405, description="Method Not Allowed"), 405, headers

    path = request.path.rstrip("/") or "/"
    # Check /daily before the catalog suffix so endswith("/establishments") never wins.
    if path.endswith("/establishments/daily") or path == "/establishments/daily":
        route = "daily"
    elif path.endswith("/establishments") or path == "/establishments":
        route = "full"
    else:
        return jsonify(error=404, description="Invalid endpoint"), 404, headers

    paging = _parse_paging()
    if not isinstance(paging, tuple) or len(paging) != 2 or not isinstance(paging[0], int):
        return paging  # already a Flask error triple

    page_size, page_number = paging

    if route == "full":
        result = fetch_full_catalog(page_size, page_number)
    else:
        result = fetch_daily_bucket(page_size, page_number)

    if isinstance(result, tuple):
        body, status = result[0], result[1]
        return body, status, headers

    return jsonify(result), 200, headers
