"""HTTP Cloud Function: dual-path GA analytics handler behind API Gateway.

Sanitized rewrite of a single backend that serves two gateway routes:
- /daily-visits   — flat rows (visit_date, total_visits)
- /ga-sessions-data — nested session objects with STRUCT projections

Focus:
- Resolve the intended route when API Gateway forwards path via headers
  (X-Forwarded-Path / X-Envoy-Original-Path / X-Original-URI), not only request.path
- Fall back to query-parameter heuristics when path info is missing
- Parameterized BigQuery (no string-interpolated filters)
- Env-driven billing project + public dataset / table overrides
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from flask import Response, jsonify, request
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_PAGE = 1
DEFAULT_LIMIT = 50
MAX_LIMIT = 500
DEFAULT_GA_DATE_SUFFIX = "20170801"
VALID_DEVICE_CATEGORIES = frozenset({"desktop", "mobile", "tablet"})
# YYYYMMDD — used as table suffix on ga_sessions_* shards.
_DATE_SUFFIX_RE = re.compile(r"^\d{8}$")


def _expose_error_detail() -> bool:
    return os.environ.get("EXPOSE_ERROR_DETAIL", "").lower() in ("1", "true", "yes")


def _cors_origin() -> str:
    return os.environ.get("CORS_ALLOW_ORIGIN", "").strip() or "*"


def _apply_cors(response: Response) -> Response:
    response.headers["Access-Control-Allow-Origin"] = _cors_origin()
    return response


def _internal_error_payload(exc: BaseException) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "error": 500,
        "description": "Internal Server Error",
    }
    if _expose_error_detail():
        body["detail"] = str(exc)
        body["exceptionType"] = type(exc).__name__
    return body


def _bq_client() -> bigquery.Client:
    project = os.environ.get("BQ_PROJECT_ID", "").strip() or None
    return bigquery.Client(project=project)


def _public_project() -> str:
    return os.environ.get("PUBLIC_PROJECT_ID", "").strip() or "bigquery-public-data"


def _ga_dataset() -> str:
    return os.environ.get("GA_DATASET_ID", "").strip() or "google_analytics_sample"


def _daily_visits_table() -> str:
    """Full project.dataset.table for the flat daily-visits mart."""
    override = os.environ.get("DAILY_VISITS_TABLE", "").strip()
    if override:
        return override
    leaf = os.environ.get("DAILY_VISITS_TABLE_ID", "").strip() or "daily_visits"
    return f"{_public_project()}.{_ga_dataset()}.{leaf}"


def _ga_sessions_table(date_suffix: str) -> str:
    """Full project.dataset.table for a ga_sessions_YYYYMMDD shard."""
    override_tpl = os.environ.get("GA_SESSIONS_TABLE_TEMPLATE", "").strip()
    if override_tpl:
        # Expect a format like project.dataset.ga_sessions_{date}
        return override_tpl.format(date=date_suffix)
    return f"{_public_project()}.{_ga_dataset()}.ga_sessions_{date_suffix}"


def _parse_paging(args) -> Tuple[Optional[int], Optional[int], Optional[Tuple[Response, int]]]:
    try:
        page = int(args.get("page", DEFAULT_PAGE))
        limit = int(args.get("limit", DEFAULT_LIMIT))
    except (TypeError, ValueError):
        return (
            None,
            None,
            (
                jsonify(error=400, description="page and limit must be integers"),
                400,
            ),
        )

    if page < 1:
        return None, None, (jsonify(error=400, description="page must be >= 1"), 400)
    if limit < 1:
        return None, None, (jsonify(error=400, description="limit must be >= 1"), 400)
    if limit > MAX_LIMIT:
        limit = MAX_LIMIT

    return page, limit, None


def _collect_path_sources(req) -> List[str]:
    """Gather every path hint the gateway or platform may forward."""
    sources = [
        req.path or "",
        req.headers.get("X-Forwarded-Path", "") or "",
        req.headers.get("X-Envoy-Original-Path", "") or "",
        req.headers.get("X-Original-URI", "") or "",
        str(req.url or ""),
    ]
    return [s for s in sources if s]


def _resolve_route(path_sources: Sequence[str], args) -> str:
    """
    Decide which logical endpoint to serve.

    Returns ``daily-visits`` or ``ga-sessions``.
    Priority: explicit path match, then parameter heuristics, then GA default.
    """
    is_daily_visits_path = any("/daily-visits" in p for p in path_sources)
    is_ga_sessions_path = any("/ga-sessions-data" in p for p in path_sources)

    is_daily_visits_params = ("start_date" in args) or ("end_date" in args)
    is_ga_sessions_params = (
        ("date" in args)
        or ("country" in args)
        or ("device_category" in args)
        or ("channel_grouping" in args)
    )

    if is_daily_visits_path and not is_ga_sessions_path:
        route = "daily-visits"
    elif is_ga_sessions_path and not is_daily_visits_path:
        route = "ga-sessions"
    elif is_daily_visits_params and not is_ga_sessions_params:
        route = "daily-visits"
    elif is_ga_sessions_params and not is_daily_visits_params:
        route = "ga-sessions"
    else:
        # Ambiguous or missing path info — keep GA as the backward-compatible default.
        route = "ga-sessions"

    logger.info(
        "route_resolved route=%s daily_path=%s ga_path=%s daily_params=%s ga_params=%s sources=%s",
        route,
        is_daily_visits_path,
        is_ga_sessions_path,
        is_daily_visits_params,
        is_ga_sessions_params,
        path_sources,
    )
    return route


def _daily_visits_gbq(
    page: int,
    limit: int,
    start_date: Optional[str],
    end_date: Optional[str],
) -> Dict[str, Any]:
    table = _daily_visits_table()
    offset = (page - 1) * limit

    where_parts: List[str] = []
    params: List[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
        bigquery.ScalarQueryParameter("offset", "INT64", offset),
    ]
    if start_date:
        where_parts.append("visit_date >= @start_date")
        params.append(bigquery.ScalarQueryParameter("start_date", "DATE", start_date))
    if end_date:
        where_parts.append("visit_date <= @end_date")
        params.append(bigquery.ScalarQueryParameter("end_date", "DATE", end_date))

    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    query = f"""
    SELECT
      visit_date,
      total_visits
    FROM `{table}`
    {where_clause}
    ORDER BY visit_date DESC
    LIMIT @limit OFFSET @offset
    """
    count_query = f"""
    SELECT COUNT(*) AS total_count
    FROM `{table}`
    {where_clause}
    """

    client = _bq_client()
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    # Count query shares the same date params (omit limit/offset).
    count_params = [p for p in params if p.name in ("start_date", "end_date")]
    count_config = bigquery.QueryJobConfig(query_parameters=count_params)

    total_count = list(client.query(count_query, job_config=count_config))[0].total_count
    total_pages = max(1, (total_count + limit - 1) // limit) if total_count else 0

    records: List[Dict[str, Any]] = []
    for row in client.query(query, job_config=job_config):
        records.append(
            {
                "visit_date": str(row.visit_date),
                "total_visits": row.total_visits,
            }
        )

    return {
        "records": records,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_records": total_count,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1 and total_pages > 0,
        },
        "filters_applied": {
            "start_date": start_date,
            "end_date": end_date,
        },
        "metadata": {
            "records_returned": len(records),
            "api_version": "1.0",
            "dataset": table,
        },
    }


def _ga_sessions_gbq(
    page: int,
    limit: int,
    country_filter: str,
    device_category_filter: str,
    channel_grouping_filter: str,
    date_suffix: str,
) -> Dict[str, Any]:
    if not _DATE_SUFFIX_RE.match(date_suffix):
        raise ValueError("date must be YYYYMMDD")

    table = _ga_sessions_table(date_suffix)
    offset = (page - 1) * limit

    where_parts: List[str] = []
    params: List[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
        bigquery.ScalarQueryParameter("offset", "INT64", offset),
    ]

    if country_filter and len(country_filter) >= 2:
        where_parts.append("geoNetwork.country = @country")
        params.append(bigquery.ScalarQueryParameter("country", "STRING", country_filter))

    if device_category_filter:
        device = device_category_filter.lower()
        if device not in VALID_DEVICE_CATEGORIES:
            raise ValueError(
                f"device_category must be one of {sorted(VALID_DEVICE_CATEGORIES)}"
            )
        where_parts.append("device.deviceCategory = @device_category")
        params.append(bigquery.ScalarQueryParameter("device_category", "STRING", device))

    if channel_grouping_filter:
        where_parts.append("channelGrouping = @channel_grouping")
        params.append(
            bigquery.ScalarQueryParameter(
                "channel_grouping", "STRING", channel_grouping_filter
            )
        )

    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

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
      geoNetwork,
      STRUCT(
        device.browser,
        device.operatingSystem,
        device.isMobile
      ) AS device,
      STRUCT(
        trafficSource.referralPath,
        trafficSource.source,
        trafficSource.medium,
        trafficSource.keyword,
        trafficSource.adContent
      ) AS trafficSource,
      customDimensions,
      (
        SELECT ARRAY_AGG(
          STRUCT(
            hitNumber,
            time,
            type,
            isInteraction,
            page.pagePath,
            page.pageTitle,
            page.hostname
          )
          ORDER BY hitNumber
          LIMIT 3
        )
        FROM UNNEST(hits)
      ) AS hits_sample
    FROM `{table}`
    {where_clause}
    ORDER BY visitStartTime DESC
    LIMIT @limit OFFSET @offset
    """
    count_query = f"""
    SELECT COUNT(*) AS total_count
    FROM `{table}`
    {where_clause}
    """

    client = _bq_client()
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    count_params = [
        p for p in params if p.name in ("country", "device_category", "channel_grouping")
    ]
    count_config = bigquery.QueryJobConfig(query_parameters=count_params)

    logger.info(
        "ga_sessions_query table=%s page=%s limit=%s filters=%s",
        table,
        page,
        limit,
        {
            "country": country_filter or None,
            "device_category": device_category_filter or None,
            "channel_grouping": channel_grouping_filter or None,
        },
    )

    total_count = list(client.query(count_query, job_config=count_config))[0].total_count
    total_pages = max(1, (total_count + limit - 1) // limit) if total_count else 0

    records: List[Dict[str, Any]] = []
    for row in client.query(query, job_config=job_config):
        records.append(
            {
                "visitId": row.visitId,
                "visitNumber": row.visitNumber,
                "visitStartTime": row.visitStartTime,
                "date": row.date,
                "fullVisitorId": row.fullVisitorId,
                "channelGrouping": row.channelGrouping,
                "totals": dict(row.totals) if row.totals else {},
                "geoNetwork": dict(row.geoNetwork) if row.geoNetwork else {},
                "device": dict(row.device) if row.device else {},
                "trafficSource": dict(row.trafficSource) if row.trafficSource else {},
                "customDimensions": [dict(cd) for cd in (row.customDimensions or [])],
                "hits_sample": [dict(hit) for hit in (row.hits_sample or [])],
            }
        )

    return {
        "records": records,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_records": total_count,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_previous": page > 1 and total_pages > 0,
        },
        "filters_applied": {
            "country": country_filter or None,
            "device_category": device_category_filter or None,
            "channel_grouping": channel_grouping_filter or None,
            "date": date_suffix,
        },
        "metadata": {
            "records_returned": len(records),
            "api_version": "1.0",
            "dataset": table,
        },
    }


def lookup(request_obj=None) -> Union[Tuple[Response, int], Response]:
    """
    Cloud Functions / Cloud Run HTTP entry point.

    Accepts an optional request object for local tests; defaults to flask.request.
    """
    req = request_obj or request

    if req.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": _cors_origin(),
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type, X-API-Key, Authorization",
            "Access-Control-Max-Age": "3600",
        }
        return ("", 204, headers)

    if req.method != "GET":
        return jsonify(error=403, description="Method not allowed"), 403

    page, limit, err = _parse_paging(req.args)
    if err is not None:
        return err

    assert page is not None and limit is not None

    try:
        path_sources = _collect_path_sources(req)
        route = _resolve_route(path_sources, req.args)

        if route == "daily-visits":
            start_date = (req.args.get("start_date") or "").strip() or None
            end_date = (req.args.get("end_date") or "").strip() or None
            result = _daily_visits_gbq(page, limit, start_date, end_date)
            empty_description = "No daily visits found"
        else:
            country = (req.args.get("country") or "").strip()
            device = (req.args.get("device_category") or "").strip()
            channel = (req.args.get("channel_grouping") or "").strip()
            date_suffix = (req.args.get("date") or DEFAULT_GA_DATE_SUFFIX).strip()
            try:
                result = _ga_sessions_gbq(
                    page, limit, country, device, channel, date_suffix
                )
            except ValueError as ve:
                return jsonify(error=400, description=str(ve)), 400
            empty_description = "No sessions found"

        if not result["records"]:
            return jsonify(error=404, description=empty_description), 404

        logger.info(
            "served route=%s page=%s records=%s",
            route,
            page,
            len(result["records"]),
        )
        response = jsonify(result)
        return _apply_cors(response), 200

    except Exception as exc:  # noqa: BLE001 — edge returns gated 500; detail logged
        logger.exception("handler_failed")
        return jsonify(**_internal_error_payload(exc)), 500
