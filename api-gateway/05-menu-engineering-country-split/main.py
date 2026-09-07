"""HTTP Cloud Function: country-split menu engineering POS lookup.

Sanitized companion to the OpenAPI gateway config in this folder.
Focus: country enum → country-scoped BigQuery table map, parameterized
SQL (no f-string WHERE values), ISO date window, SQL OFFSET/LIMIT.
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from flask import Request, jsonify
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_OFFSET = 0
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000
DEFAULT_COUNTRY = "de"
DEFAULT_START = "1900-01-01"
DEFAULT_END = "2099-12-31"

# ISO date only — source OpenAPI advertised DD-MM-YYYY while the handler
# passed values straight into BQ DATE filters. Align the contract on ISO.
_ISO_DATE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")

# Country → full table id. Override per env; never take table names from the caller.
# Format: project.dataset.table (or dataset.table if project is defaulted by client).
_DEFAULT_TABLE_MAP = {
    "de": "PROJECT_ID.DATASET_ID.pos_sold_items_de",
    "fr": "PROJECT_ID.DATASET_ID.pos_sold_items_fr",
}

# Optional CRM join table for license → establishment mapping.
_DEFAULT_EST_TABLE = os.environ.get(
    "MENU_POS_ESTABLISHMENTS_TABLE",
    "PROJECT_ID.DATASET_ID.pos_establishments",
)


def _country_table_map() -> Dict[str, str]:
    """Build country→table map from env overrides when present."""
    mapping = dict(_DEFAULT_TABLE_MAP)
    de = os.environ.get("MENU_POS_TABLE_DE")
    fr = os.environ.get("MENU_POS_TABLE_FR")
    if de:
        mapping["de"] = de
    if fr:
        mapping["fr"] = fr
    return mapping


def _expose_error_detail() -> bool:
    return os.environ.get("EXPOSE_ERROR_DETAIL", "").lower() in ("1", "true", "yes")


def _parse_int(raw: Optional[str], name: str, default: int) -> Tuple[Optional[int], Optional[str]]:
    if raw is None or raw == "":
        return default, None
    try:
        return int(raw), None
    except (TypeError, ValueError):
        return None, f"{name} must be an integer"


def _parse_date(raw: Optional[str], name: str, default: str) -> Tuple[Optional[str], Optional[str]]:
    if raw is None or raw == "":
        return default, None
    if not _ISO_DATE.match(raw):
        return None, f"{name} must be YYYY-MM-DD"
    return raw, None


def _get_menu_pos(
    establishment_uid: str,
    country: str,
    start_date: str,
    end_date: str,
    offset: int,
    limit: int,
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], int]]:
    """Query sold items for one establishment from a country-scoped table."""

    table_map = _country_table_map()
    country_key = country.lower().strip()
    if country_key not in table_map:
        allowed = ", ".join(sorted(table_map))
        return (
            {
                "error": 400,
                "description": f"country must be one of: {allowed}",
            },
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
    if start_date > end_date:
        return (
            {"error": 400, "description": "startDate must be <= endDate"},
            400,
        )

    sold_items_table = table_map[country_key]
    establishments_table = _DEFAULT_EST_TABLE

    # Table ids come from env / defaults — never concatenate caller strings into FROM.
    qry = f"""
        SELECT
            a.item_id AS order_id,
            a.menu_item_id AS item_id,
            a.menu_item_name AS item_name,
            a.item_count AS quantity,
            a.item_price AS item_price,
            a.VAT_percentage AS tax_rate,
            CAST(a.createdAt AS STRING) AS timestamp,
            CAST(a.receiptNr AS INT64) AS invoice_id
        FROM `{sold_items_table}` AS a
        LEFT JOIN (
            SELECT DISTINCT
                metro_id,
                establishment_id,
                POS_License_ID__c
            FROM `{establishments_table}`
            WHERE ProductCode__c = @product_code
        ) AS b
            ON a.storeLicenseId = b.POS_License_ID__c
        WHERE b.establishment_id = @establishment_uid
          AND a.workDay BETWEEN @start_date AND @end_date
        ORDER BY a.createdAt, a.item_id
        LIMIT @row_limit
        OFFSET @row_offset
    """

    params = [
        bigquery.ScalarQueryParameter("establishment_uid", "STRING", establishment_uid),
        bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
        bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
        bigquery.ScalarQueryParameter("row_limit", "INT64", limit),
        bigquery.ScalarQueryParameter("row_offset", "INT64", offset),
        bigquery.ScalarQueryParameter(
            "product_code",
            "STRING",
            os.environ.get("MENU_POS_PRODUCT_CODE", "POS_L_Package"),
        ),
    ]

    logger.info(
        "menu-pos query country=%s offset=%s limit=%s has_dates=%s",
        country_key,
        offset,
        limit,
        start_date != DEFAULT_START or end_date != DEFAULT_END,
    )

    client = bigquery.Client()
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    rows = client.query(qry, job_config=job_config).result()

    records: List[Dict[str, Any]] = []
    for row in rows:
        records.append(
            {
                "order_id": row["order_id"],
                "item_id": row["item_id"],
                "item_name": row["item_name"],
                "quantity": row["quantity"],
                "item_price": row["item_price"],
                "tax_rate": row["tax_rate"],
                "timestamp": row["timestamp"],
                "invoice_id": row["invoice_id"],
            }
        )

    if not records:
        return {"error": 404, "description": "Establishment not found"}, 404

    return {"records": records, "count": len(records)}


def lookup(request: Request):
    """Cloud Functions / Functions Framework entrypoint. GET only."""
    if request.method != "GET":
        return jsonify(error=403, description="Method not allowed"), 403

    args = request.args
    establishment_uid = args.get("establishmentUID")
    if not establishment_uid:
        return jsonify(error=400, description="establishmentUID is required"), 400

    country = (args.get("country") or DEFAULT_COUNTRY).lower().strip()

    start_date, err = _parse_date(args.get("startDate"), "startDate", DEFAULT_START)
    if err:
        return jsonify(error=400, description=err), 400
    end_date, err = _parse_date(args.get("endDate"), "endDate", DEFAULT_END)
    if err:
        return jsonify(error=400, description=err), 400

    offset, err = _parse_int(args.get("offset"), "offset", DEFAULT_OFFSET)
    if err:
        return jsonify(error=400, description=err), 400
    limit, err = _parse_int(args.get("limit"), "limit", DEFAULT_LIMIT)
    if err:
        return jsonify(error=400, description=err), 400

    assert start_date is not None and end_date is not None
    assert offset is not None and limit is not None

    try:
        result = _get_menu_pos(
            establishment_uid=establishment_uid,
            country=country,
            start_date=start_date,
            end_date=end_date,
            offset=offset,
            limit=limit,
        )
        if isinstance(result, tuple):
            return jsonify(result[0]), result[1]
        return jsonify(result), 200
    except Exception as exc:
        logger.exception("Error querying menu POS items")
        body: Dict[str, Any] = {
            "error": 500,
            "description": "Internal server error",
        }
        if _expose_error_detail():
            body["detail"] = str(exc)
        return jsonify(body), 500
