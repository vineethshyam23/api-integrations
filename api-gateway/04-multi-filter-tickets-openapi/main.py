"""HTTP Cloud Run / Cloud Function: multi-filter helpdesk ticket lookup.

Sanitized companion to the OpenAPI gateway config in this folder.
Focus: paired metroId+storeId validation, multiple optional filters,
parameterized BigQuery (no string-interpolated WHERE values), offset/limit.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union

from flask import Request, jsonify
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_OFFSET = 0
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000

# Country scope is fixed for this extract surface — set via env, not query.
# Keeps the public contract from becoming a free-form country scan.
DEFAULT_COUNTRY = os.environ.get("TICKETS_COUNTRY_SCOPE", "COUNTRY_NAME")

# Full table id: project.dataset.table — override per env in Secret Manager / deploy.
BQ_TABLE = os.environ.get(
    "TICKETS_BQ_TABLE",
    "PROJECT_ID.DATASET_ID.helpdesk_ticket",
)


def _expose_error_detail() -> bool:
    return os.environ.get("EXPOSE_ERROR_DETAIL", "").lower() in ("1", "true", "yes")


def _parse_int(raw: Optional[str], name: str, default: int) -> Tuple[Optional[int], Optional[str]]:
    if raw is None or raw == "":
        return default, None
    try:
        return int(raw), None
    except (TypeError, ValueError):
        return None, f"{name} must be an integer"


def _get_tickets(
    establishment_id: Optional[str],
    metro_id: Optional[str],
    store_id: Optional[str],
    metro_account_identifier: Optional[str],
    offset: int,
    limit: int,
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """Query helpdesk tickets with optional filters. Values are query params, not SQL text."""

    # Paired filters: metro + store must arrive together.
    if store_id and not metro_id:
        return (
            {"error": 400, "description": "storeId cannot be used without metroId"},
            400,
        )
    if metro_id and not store_id:
        return (
            {"error": 400, "description": "metroId requires storeId to be provided"},
            400,
        )

    if offset < 0:
        return {"error": 400, "description": "offset must be >= 0"}, 400
    if limit < 1 or limit > MAX_LIMIT:
        return (
            {
                "error": 400,
                "description": f"limit must be between 1 and {MAX_LIMIT}",
            },
            400,
        )

    where_parts: List[str] = [
        "ticket_number IS NOT NULL",
        "_valid_flag = TRUE",
        "country = @country",
    ]
    params: List[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("country", "STRING", DEFAULT_COUNTRY),
        bigquery.ScalarQueryParameter("row_limit", "INT64", limit),
        bigquery.ScalarQueryParameter("row_offset", "INT64", offset),
    ]

    if establishment_id:
        where_parts.append("LOWER(establishment_id) = LOWER(@establishment_id)")
        params.append(
            bigquery.ScalarQueryParameter(
                "establishment_id", "STRING", establishment_id
            )
        )

    if metro_id and store_id:
        where_parts.append("metro_id = @metro_id")
        where_parts.append("store_id = @store_id")
        params.append(bigquery.ScalarQueryParameter("metro_id", "STRING", metro_id))
        # store_id may arrive as a string from query args; coerce to INT64.
        try:
            store_id_int = int(store_id)
        except (TypeError, ValueError):
            return {"error": 400, "description": "storeId must be an integer"}, 400
        params.append(
            bigquery.ScalarQueryParameter("store_id", "INT64", store_id_int)
        )

    if metro_account_identifier:
        where_parts.append("metro_account_identifier = @metro_account_identifier")
        params.append(
            bigquery.ScalarQueryParameter(
                "metro_account_identifier", "STRING", metro_account_identifier
            )
        )

    where_clause = " AND ".join(where_parts)
    # Table id comes from env, not caller input — do not concatenate user strings here.
    qry = f"""
        SELECT
            ticket_number,
            ticket_name,
            CAST(create_date AS STRING) AS create_date,
            ticket_type,
            ticket_tag,
            CAST(close_date AS STRING) AS close_date,
            country,
            escalated_check,
            current_status,
            ticket_medium,
            metro_account_identifier,
            metro_id,
            store_id,
            establishment_id
        FROM `{BQ_TABLE}`
        WHERE {where_clause}
        ORDER BY create_date DESC
        LIMIT @row_limit
        OFFSET @row_offset
    """

    logger.info(
        "tickets query filters: establishment=%s metro=%s store=%s account=%s "
        "offset=%s limit=%s",
        bool(establishment_id),
        bool(metro_id),
        bool(store_id),
        bool(metro_account_identifier),
        offset,
        limit,
    )

    client = bigquery.Client()
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    rows = client.query(qry, job_config=job_config).result()

    records: List[Dict[str, Any]] = []
    for row in rows:
        records.append(
            {
                "ticket_number": row["ticket_number"],
                "ticket_name": row["ticket_name"],
                "create_date": row["create_date"],
                "ticket_type": row["ticket_type"],
                "ticket_tag": row["ticket_tag"],
                "close_date": row["close_date"],
                "country": row["country"],
                "escalated_check": row["escalated_check"],
                "current_status": row["current_status"],
                "ticket_medium": row["ticket_medium"],
                "metro_account_identifier": row["metro_account_identifier"],
                "metro_id": row["metro_id"],
                "store_id": row["store_id"],
                "establishment_id": row["establishment_id"],
            }
        )

    if not records:
        return {"error": 404, "description": "No tickets found"}, 404

    return {"records": records, "count": len(records)}


def lookup(request: Request):
    """Cloud Functions / Functions Framework entrypoint. GET only."""
    if request.method != "GET":
        return jsonify(error=403, description="Method not allowed"), 403

    args = request.args
    establishment_id = args.get("establishmentId") or None
    metro_id = args.get("metroId") or None
    store_id = args.get("storeId") or None
    metro_account_identifier = args.get("metroAccountIdentifier") or None

    offset, err = _parse_int(args.get("offset"), "offset", DEFAULT_OFFSET)
    if err:
        return jsonify(error=400, description=err), 400
    limit, err = _parse_int(args.get("limit"), "limit", DEFAULT_LIMIT)
    if err:
        return jsonify(error=400, description=err), 400

    assert offset is not None and limit is not None

    try:
        result = _get_tickets(
            establishment_id=establishment_id,
            metro_id=metro_id,
            store_id=store_id,
            metro_account_identifier=metro_account_identifier,
            offset=offset,
            limit=limit,
        )
        if isinstance(result, tuple):
            return jsonify(result[0]), result[1]
        return jsonify(result), 200
    except Exception as exc:
        logger.exception("Error querying tickets")
        body: Dict[str, Any] = {
            "error": 500,
            "description": "Internal server error",
        }
        if _expose_error_detail():
            body["detail"] = str(exc)
        return jsonify(body), 500
