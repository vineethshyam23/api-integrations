"""HTTP Cloud Function: establishment-scoped POS daily transactions with SQL OFFSET/LIMIT.

Sanitized rewrite of a panel POS v3 handler. Focus:
- Push pagination into BigQuery (LIMIT/OFFSET), not Python list slicing
- Parameterized filters (no string-interpolated establishment IDs)
- Explicit BQ_PROJECT_ID / table env vars instead of a vague ENV project name
- Required establishmentId + hard limit caps
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union

from flask import Response, jsonify, request
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_OFFSET = 0
DEFAULT_LIMIT = 20
MAX_LIMIT = 100

# Columns returned to callers. Keep explicit — never SELECT *.
RETURN_COLUMNS = (
    "country",
    "persistence_id",
    "establishment_id",
    "pos_order_date",
    "total_completed_orders",
    "total_order_amount",
)


def _expose_error_detail() -> bool:
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


def _bq_client() -> bigquery.Client:
    # Prefer an explicit billing/job project. Fall back to ADC default project.
    project = os.environ.get("BQ_PROJECT_ID", "").strip() or None
    return bigquery.Client(project=project)


def _resolve_table() -> str:
    """
    Full ``project.dataset.table`` for daily POS transactions.

    POS_DAILY_TX_TABLE overrides when set. Otherwise build from
    BQ_PROJECT_ID + DATASET_ID + table leaf.
    """
    override = os.environ.get("POS_DAILY_TX_TABLE", "").strip()
    if override:
        return override

    project = os.environ.get("BQ_PROJECT_ID", "").strip()
    dataset = os.environ.get("DATASET_ID", "").strip() or "DATASET_ID"
    table = os.environ.get("POS_DAILY_TX_TABLE_ID", "").strip() or "pos_daily_transactions"

    if not project:
        raise ValueError(
            "BQ_PROJECT_ID is required when POS_DAILY_TX_TABLE is unset. "
            "Set BQ_PROJECT_ID=PROJECT_ID or POS_DAILY_TX_TABLE=project.dataset.table."
        )
    return f"{project}.{dataset}.{table}"


def _parse_paging(args) -> Tuple[Optional[int], Optional[int], Optional[Tuple[Response, int]]]:
    """Return (offset, limit, None) on success, or (None, None, error_response)."""
    try:
        offset = int(args.get("offset", DEFAULT_OFFSET))
        limit = int(args.get("limit", DEFAULT_LIMIT))
    except (TypeError, ValueError):
        return (
            None,
            None,
            (
                jsonify(
                    error=400,
                    description="offset and limit must be integers",
                ),
                400,
            ),
        )

    if offset < 0:
        return None, None, (jsonify(error=400, description="offset must be >= 0"), 400)
    if limit < 1:
        return None, None, (jsonify(error=400, description="limit must be >= 1"), 400)
    if limit > MAX_LIMIT:
        return (
            None,
            None,
            (
                jsonify(error=400, description=f"limit cannot exceed {MAX_LIMIT}"),
                400,
            ),
        )
    return offset, limit, None


def fetch_daily_transactions(
    establishment_id: str,
    offset: int,
    limit: int,
) -> Dict[str, List[Dict[str, Any]]]:
    """Run a parameterized SELECT with SQL LIMIT/OFFSET for one establishment."""
    table = _resolve_table()
    columns = ", ".join(RETURN_COLUMNS)

    # Table id comes from deploy-time env only — never from request input.
    query = f"""
    SELECT {columns}
    FROM `{table}`
    WHERE establishment_id = @establishment_id
    ORDER BY pos_order_date DESC
    LIMIT @limit OFFSET @offset
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "establishment_id", "STRING", establishment_id
            ),
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
            bigquery.ScalarQueryParameter("offset", "INT64", offset),
        ]
    )

    logger.info(
        "pos_daily_tx query table=%s offset=%s limit=%s",
        table,
        offset,
        limit,
    )

    client = _bq_client()
    rows = client.query(query, job_config=job_config).result()

    records: List[Dict[str, Any]] = []
    for row in rows:
        records.append(
            {
                "country": row["country"],
                "persistence_id": row["persistence_id"],
                "establishment_id": row["establishment_id"],
                "pos_order_date": (
                    str(row["pos_order_date"]) if row["pos_order_date"] else None
                ),
                "total_completed_orders": row["total_completed_orders"],
                "total_order_amount": row["total_order_amount"],
            }
        )
    return {"records": records}


def lookup(request) -> Union[Response, Tuple[Response, int]]:
    """
    GET handler for establishment-scoped POS daily transactions.

    Query params:
      establishmentId (required)
      offset (default 0), limit (default 20, max 100)
    """
    if request.method != "GET":
        return jsonify(error=405, description="Method Not Allowed"), 405

    establishment_id: Optional[str] = request.args.get("establishmentId")
    if establishment_id is None or not str(establishment_id).strip():
        return (
            jsonify(
                error=400,
                description="establishmentId query parameter is required",
            ),
            400,
        )
    establishment_id = str(establishment_id).strip()

    offset, limit, paging_error = _parse_paging(request.args)
    if paging_error is not None:
        return paging_error

    try:
        payload = fetch_daily_transactions(establishment_id, offset, limit)
    except ValueError as exc:
        # Missing/invalid env (BQ_PROJECT_ID / table resolve)
        logger.exception("Configuration error resolving POS daily tx table")
        return jsonify(_internal_error_payload(exc)), 500
    except Exception as exc:
        logger.exception("BigQuery POS daily transactions query failed")
        return jsonify(_internal_error_payload(exc)), 500

    if not payload["records"]:
        # Empty page for an unknown id or past the end — same 404 contract as v2/v3 panel APIs
        return jsonify(error=404, description="Establishment not found"), 404

    return jsonify(payload), 200
