"""
HTTP Cloud Function / Cloud Run entry point intended to sit behind API Gateway.

Pattern focus:
- Path routing when the gateway forwards (or rewrites) the original path
- Structured JSON logging suitable for Cloud Logging
- Project / dataset IDs from environment, not hardcoded GCP projects
- Parameterized BigQuery queries (no string-interpolated filters)

Entry point name: lookup  (set as --entry-point=lookup on deploy)
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from flask import Request, jsonify
from google.cloud import bigquery

# Cloud Logging picks up severity from the "severity" field when using
# a JSON formatter (or the google-cloud-logging handler in production).
logger = logging.getLogger("analytics_api")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)


def _log(severity: str, message: str, **fields: Any) -> None:
    payload = {"severity": severity, "message": message, **fields}
    logger.log(
        getattr(logging, severity, logging.INFO),
        json.dumps(payload, default=str),
    )


def _config() -> dict[str, str]:
    return {
        # Billing / job project — where queries run
        "project_id": os.environ.get("PROJECT_ID", "PROJECT_ID"),
        # Read-only analytics dataset (public sample used as a stand-in)
        "public_project": os.environ.get("PUBLIC_BQ_PROJECT", "bigquery-public-data"),
        "dataset_id": os.environ.get("DATASET_ID", "google_analytics_sample"),
    }


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATE_SUFFIX_RE = re.compile(r"^\d{8}$")
_DEVICE_CATEGORIES = frozenset({"desktop", "mobile", "tablet"})


def _resolved_paths(request: Request) -> list[str]:
    """Collect path candidates — gateway may strip or forward the original path."""
    return [
        request.path or "",
        request.headers.get("X-Forwarded-Path", ""),
        request.headers.get("X-Envoy-Original-Path", ""),
        request.headers.get("X-Original-URI", ""),
        request.url or "",
    ]


def _route_from_request(request: Request) -> str:
    """
    Decide which handler to run.

    When API Gateway points each OpenAPI path at the same function URL,
    the backend often sees "/" or the function name only. Prefer gateway
    forwarded-path headers, then fall back to query-shape heuristics.
    """
    paths = _resolved_paths(request)
    args = request.args

    has_daily = any("/daily-visits" in p for p in paths if p)
    has_sessions = any("/ga-sessions-data" in p for p in paths if p)

    if has_daily and not has_sessions:
        return "daily-visits"
    if has_sessions and not has_daily:
        return "ga-sessions"

    daily_params = "start_date" in args or "end_date" in args
    session_params = any(k in args for k in ("date", "country", "device_category"))

    if daily_params and not session_params:
        return "daily-visits"
    if session_params and not daily_params:
        return "ga-sessions"

    # Default matches the historical single-route behaviour of this API.
    return "ga-sessions"


def _parse_page_limit(args) -> tuple[int, int] | tuple[Any, int]:
    """Returns (page, limit) or a Flask (response, status) error tuple."""
    try:
        page = int(args.get("page", "1"))
        limit = min(int(args.get("limit", "50")), 500)
    except (TypeError, ValueError):
        return jsonify(error=400, description="page and limit must be integers"), 400
    if page < 1:
        return jsonify(error=400, description="Page must be >= 1"), 400
    if limit < 1:
        return jsonify(error=400, description="Limit must be >= 1"), 400
    return page, limit


def _is_error_response(value: Any) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[1], int)
        and value[1] >= 400
    )


def _daily_visits(page: int, limit: int, start_date: str | None, end_date: str | None):
    cfg = _config()
    # Demo stand-in table. In production this is your refined mart / view.
    table = f"`{cfg['public_project']}.google_analytics_sample.ga_sessions_20170801`"

    where = ["1=1"]
    params: list[bigquery.ScalarQueryParameter] = []
    if start_date:
        if not _DATE_RE.match(start_date):
            return jsonify(error=400, description="start_date must be YYYY-MM-DD"), 400
        where.append("PARSE_DATE('%Y%m%d', date) >= @start_date")
        params.append(bigquery.ScalarQueryParameter("start_date", "DATE", start_date))
    if end_date:
        if not _DATE_RE.match(end_date):
            return jsonify(error=400, description="end_date must be YYYY-MM-DD"), 400
        where.append("PARSE_DATE('%Y%m%d', date) <= @end_date")
        params.append(bigquery.ScalarQueryParameter("end_date", "DATE", end_date))

    where_sql = " AND ".join(where)
    offset = (page - 1) * limit

    query = f"""
    SELECT
      PARSE_DATE('%Y%m%d', date) AS visit_date,
      COUNT(*) AS total_visits
    FROM {table}
    WHERE {where_sql}
    GROUP BY visit_date
    ORDER BY visit_date DESC
    LIMIT @limit OFFSET @offset
    """
    count_query = f"""
    SELECT COUNT(*) AS total_count FROM (
      SELECT PARSE_DATE('%Y%m%d', date) AS visit_date
      FROM {table}
      WHERE {where_sql}
      GROUP BY visit_date
    )
    """

    client = bigquery.Client(project=cfg["project_id"])
    job_params = params + [
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
        bigquery.ScalarQueryParameter("offset", "INT64", offset),
    ]
    job_config = bigquery.QueryJobConfig(query_parameters=job_params)
    count_config = bigquery.QueryJobConfig(query_parameters=params)

    total_count = list(client.query(count_query, job_config=count_config).result())[0].total_count
    total_pages = max(1, (total_count + limit - 1) // limit) if total_count else 0

    records = [
        {"visit_date": str(row.visit_date), "total_visits": row.total_visits}
        for row in client.query(query, job_config=job_config).result()
    ]
    if not records:
        return jsonify(error=404, description="No daily visits found"), 404

    return {
        "records": records,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_records": total_count,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1,
        },
        "filters_applied": {"start_date": start_date, "end_date": end_date},
        "metadata": {"records_returned": len(records), "api_version": "1.0"},
    }


def _ga_sessions(
    page: int,
    limit: int,
    country: str,
    device_category: str,
    channel_grouping: str,
    date_suffix: str,
):
    cfg = _config()
    if not _DATE_SUFFIX_RE.match(date_suffix):
        return jsonify(error=400, description="date must be YYYYMMDD"), 400

    table = (
        f"`{cfg['public_project']}.{cfg['dataset_id']}.ga_sessions_{date_suffix}`"
    )

    where = ["1=1"]
    params: list[bigquery.ScalarQueryParameter] = []

    if country and len(country) >= 2:
        where.append("geoNetwork.country = @country")
        params.append(bigquery.ScalarQueryParameter("country", "STRING", country))

    if device_category:
        device = device_category.lower()
        if device not in _DEVICE_CATEGORIES:
            return jsonify(error=400, description="Invalid device_category"), 400
        where.append("device.deviceCategory = @device_category")
        params.append(
            bigquery.ScalarQueryParameter("device_category", "STRING", device)
        )

    if channel_grouping:
        where.append("channelGrouping = @channel_grouping")
        params.append(
            bigquery.ScalarQueryParameter("channel_grouping", "STRING", channel_grouping)
        )

    where_sql = " AND ".join(where)
    offset = (page - 1) * limit

    query = f"""
    SELECT
      visitId,
      visitNumber,
      visitStartTime,
      date,
      fullVisitorId,
      channelGrouping,
      STRUCT(
        totals.visits,
        totals.hits,
        totals.pageviews,
        totals.bounces,
        totals.newVisits
      ) AS totals,
      STRUCT(
        device.browser,
        device.operatingSystem,
        device.isMobile
      ) AS device
    FROM {table}
    WHERE {where_sql}
    ORDER BY visitStartTime DESC
    LIMIT @limit OFFSET @offset
    """
    count_query = f"""
    SELECT COUNT(*) AS total_count
    FROM {table}
    WHERE {where_sql}
    """

    client = bigquery.Client(project=cfg["project_id"])
    job_params = params + [
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
        bigquery.ScalarQueryParameter("offset", "INT64", offset),
    ]
    job_config = bigquery.QueryJobConfig(query_parameters=job_params)
    count_config = bigquery.QueryJobConfig(query_parameters=params)

    _log(
        "INFO",
        "ga_sessions_query",
        date_suffix=date_suffix,
        page=page,
        limit=limit,
        has_country=bool(country),
        has_device=bool(device_category),
    )

    total_count = list(client.query(count_query, job_config=count_config).result())[0].total_count
    total_pages = max(1, (total_count + limit - 1) // limit) if total_count else 0

    records = []
    for row in client.query(query, job_config=job_config).result():
        records.append(
            {
                "visitId": row.visitId,
                "visitNumber": row.visitNumber,
                "visitStartTime": row.visitStartTime,
                "date": row.date,
                "fullVisitorId": row.fullVisitorId,
                "channelGrouping": row.channelGrouping,
                "totals": dict(row.totals) if row.totals else {},
                "device": dict(row.device) if row.device else {},
            }
        )

    if not records:
        return jsonify(error=404, description="No sessions found"), 404

    return {
        "records": records,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_records": total_count,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1,
        },
        "filters_applied": {
            "country": country or None,
            "device_category": device_category or None,
            "channel_grouping": channel_grouping or None,
            "date": date_suffix,
        },
        "metadata": {"records_returned": len(records), "api_version": "1.0"},
    }


def _cors_headers() -> dict[str, str]:
    # Prefer locking this to known dashboard origins in production.
    origin = os.environ.get("CORS_ALLOW_ORIGIN", "*")
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET",
        "Access-Control-Allow-Headers": "Content-Type, X-API-Key",
        "Access-Control-Max-Age": "3600",
    }


def lookup(request: Request):
    """Cloud Functions / Cloud Run HTTP entry point."""
    if request.method == "OPTIONS":
        return ("", 204, _cors_headers())

    if request.method != "GET":
        return jsonify(error=403, description="Method not allowed"), 403

    parsed = _parse_page_limit(request.args)
    if _is_error_response(parsed):
        return parsed
    page, limit = parsed  # type: ignore[misc]

    route = _route_from_request(request)
    _log(
        "INFO",
        "request_routed",
        route=route,
        path=request.path,
        forwarded_path=request.headers.get("X-Forwarded-Path", ""),
        envoy_original_path=request.headers.get("X-Envoy-Original-Path", ""),
        page=page,
        limit=limit,
    )

    try:
        if route == "daily-visits":
            result = _daily_visits(
                page,
                limit,
                request.args.get("start_date") or None,
                request.args.get("end_date") or None,
            )
        else:
            result = _ga_sessions(
                page,
                limit,
                request.args.get("country", ""),
                request.args.get("device_category", ""),
                request.args.get("channel_grouping", ""),
                request.args.get("date", "20170801"),
            )

        # Handler may return (response, status) for 4xx
        if isinstance(result, tuple):
            body, status = result
            if hasattr(body, "headers"):
                for k, v in _cors_headers().items():
                    body.headers[k] = v
            return body, status

        response = jsonify(result)
        for k, v in _cors_headers().items():
            response.headers[k] = v
        _log(
            "INFO",
            "request_ok",
            route=route,
            records=len(result.get("records", [])),
        )
        return response, 200
    except Exception as exc:  # noqa: BLE001 — edge handler; log and return 500
        _log("ERROR", "request_failed", error=str(exc), route=route)
        return jsonify(error=500, description="Internal server error"), 500
