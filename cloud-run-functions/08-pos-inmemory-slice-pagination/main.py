"""LEGACY / ANTI-PATTERN: POS KPI handler with in-memory offset after BigQuery LIMIT.

Sanitized from a real v2 panel POS Cloud Function. Keep this folder as the
migration baseline next to pattern 15 (SQL LIMIT/OFFSET pushdown).

Intentional smells retained for teaching (do not copy into new services):

1. Format-string SQL for establishment_id and LIMIT
2. BigQuery LIMIT without OFFSET, then Python list slice for paging
3. Default client limit of 9999 (forces large scans "to make paging work")
4. startDate / endDate accepted but unused (filter commented out)
5. Vague ENV env var used as the BigQuery job project
6. Bare except mapped to 404
7. Error-path return shape that can double-wrap a Flask Response

Prefer ``cloud-run-functions/05-pos-daily-transactions-offset-limit/`` for
production. Use ``check-inmemory-slice-smell.sh`` to catch regressions.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union

from flask import Response, jsonify, request
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ANTI-PATTERN: default limit large enough that callers treat the function as
# "fetch everything then slice". Pattern 15 caps at 100 and pages in SQL.
DEFAULT_LIMIT = 9999
DEFAULT_OFFSET = 0

# Sanitized column names (source used product-specific payment labels / typos).
RETURN_COLUMNS = (
    "persistence_id",
    "establishment_id",
    "asset_created_date",
    "created_at",
    "turnover_current_month",
    "turnover_week_1",
    "turnover_week_2",
    "turnover_week_3",
    "turnover_week_4",
    "turnover_percentage_change",
    "completed_orders",
    "percentage_change",
    "completed_orders_by_contact",
    "completed_orders_by_card",
    "completed_orders_by_online",
    "completed_orders_by_invoice",
    "turnover_last_month",
    "completed_orders_last_month",
)


def _resolve_table() -> str:
    """Table id from env only — never from request input."""
    override = os.environ.get("POS_KPI_TABLE", "").strip()
    if override:
        return override
    dataset = os.environ.get("DATASET_ID", "").strip() or "DATASET_ID"
    table = os.environ.get("POS_KPI_TABLE_ID", "").strip() or "pos_kpi_snapshot"
    return f"{dataset}.{table}"


def _fetch_pos_kpi(
    establishment_id: str,
    _start_date: str,
    _end_date: str,
    offset: int,
    limit: int,
) -> Union[Dict[str, List[Dict[str, Any]]], Tuple[Response, int]]:
    """
    Fetch POS KPI rows for one establishment.

    ANTI-PATTERN block: SQL applies LIMIT only; offset is applied in Python
    after the query returns. When callers pass limit=N and offset>0, the
    warehouse only returns N rows and the slice often yields an empty page
    (false 404). Teams then raise default limit to 9999 to "fix" paging,
    which bills and buffers far more than the client needs.
    """
    table = _resolve_table()
    columns = ", ".join(RETURN_COLUMNS)

    # ANTI-PATTERN: string formatting of filter + LIMIT (injection + no OFFSET).
    # Date params are accepted by the HTTP handler but intentionally unused here
    # — same as the source (filter left commented out).
    _ = (_start_date, _end_date)
    query = """
        SELECT {columns}
        FROM `{table}`
        WHERE establishment_id = '{establishment_id}'
        LIMIT {limit}
    """.format(
        columns=columns,
        table=table,
        establishment_id=establishment_id,
        limit=limit,
    )

    # ANTI-PATTERN: ENV as BigQuery project name (opaque for deploy + on-call).
    project = os.environ.get("ENV") or None
    client = bigquery.Client(project=project)

    logger.info(
        "pos_kpi_v2_legacy query table=%s offset=%s limit=%s "
        "(in-memory slice after LIMIT — prefer SQL OFFSET)",
        table,
        offset,
        limit,
    )

    rows = client.query(query).result()
    buffer: List[Dict[str, Any]] = []
    for row in rows:
        buffer.append(
            {
                "persistence_id": row["persistence_id"],
                "establishment_id": row["establishment_id"],
                "asset_created_date": (
                    str(row["asset_created_date"])
                    if row["asset_created_date"] is not None
                    else None
                ),
                "created_at": (
                    str(row["created_at"]) if row["created_at"] is not None else None
                ),
                "turnover_current_month": row["turnover_current_month"],
                "turnover_week_1": row["turnover_week_1"],
                "turnover_week_2": row["turnover_week_2"],
                "turnover_week_3": row["turnover_week_3"],
                "turnover_week_4": row["turnover_week_4"],
                "turnover_percentage_change": row["turnover_percentage_change"],
                "completed_orders": row["completed_orders"],
                "percentage_change": row["percentage_change"],
                "completed_orders_by_contact": row["completed_orders_by_contact"],
                "completed_orders_by_card": row["completed_orders_by_card"],
                "completed_orders_by_online": row["completed_orders_by_online"],
                "completed_orders_by_invoice": row["completed_orders_by_invoice"],
                "turnover_last_month": row["turnover_last_month"],
                "completed_orders_last_month": row["completed_orders_last_month"],
            }
        )

    # ANTI-PATTERN: page in process memory after the warehouse already limited.
    page = buffer[offset : offset + limit]
    if not page:
        return jsonify(error=404, description="Establishment not found"), 404
    return {"records": page}


def lookup(request) -> Union[Response, Tuple[Response, int]]:
    """
    GET handler for legacy POS KPI lookup (do not use for new APIs).

    Query params:
      establishmentId (required)
      startDate / endDate (accepted, unused in this legacy body)
      offset (default 0), limit (default 9999)
    """
    if request.method != "GET":
        return jsonify(error=403, description="Method not allowed"), 403

    args = request.args
    establishment_id: Optional[str] = args.get("establishmentId")
    if establishment_id is None or not str(establishment_id).strip():
        return (
            jsonify(
                error=400,
                description="establishmentId query parameter is required",
            ),
            400,
        )
    establishment_id = str(establishment_id).strip()

    start_date = args.get("startDate", "1900-01-01")
    end_date = args.get("endDate", "2099-12-31")
    try:
        offset = int(args.get("offset", DEFAULT_OFFSET))
        limit = int(args.get("limit", DEFAULT_LIMIT))
    except (TypeError, ValueError):
        return (
            jsonify(error=400, description="offset and limit must be integers"),
            400,
        )

    try:
        result = _fetch_pos_kpi(
            establishment_id, start_date, end_date, offset, limit
        )
        # ANTI-PATTERN / known defect: on the empty-page path, _fetch_pos_kpi
        # already returns (Response, 404). Wrapping that tuple with jsonify
        # and forcing 200 produces a broken client body. Pattern 15 returns
        # the handler result directly without this second wrap.
        return jsonify(result), 200
    except Exception:
        # ANTI-PATTERN: bare except collapses config + BQ failures into 404.
        logger.exception("pos_kpi_v2_legacy failed")
        return jsonify(error=404, description="Establishment not found"), 404
