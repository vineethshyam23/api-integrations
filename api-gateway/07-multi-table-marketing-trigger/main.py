"""HTTP Cloud Run / Functions handler: multi-table marketing-trigger extracts.

One service, many paths. Each path resolves through TABLE_CONFIGS to a BigQuery
table + column list, then shares fetch_data_with_pagination. A separate
fields-metadata path returns source→destination field maps grouped by model.

Sanitized from a production multi-path marketing-automation trigger API.
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from typing import Any, Dict, List, Tuple, Union

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

# Path segment → config key. Keep OpenAPI paths and this map in lockstep.
PATH_TO_CONFIG = {
    "/triggers/contacts": "contacts",
    "/triggers/payments": "payments",
    "/triggers/network-pay": "network_pay",
    "/triggers/pos": "pos",
    "/triggers/reservations": "reservations",
    "/triggers/website": "website",
}


def _cors_origin() -> str:
    return os.environ.get("CORS_ALLOW_ORIGIN", "*")


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


def _env_table(env_key: str, default: str) -> str:
    return os.environ.get(env_key, default).strip() or default


def table_configs() -> Dict[str, Dict[str, Any]]:
    """
    Resolve per request so deploys can change env without import-time surprises.

    Defaults are placeholders only — override with TRIGGER_*_TABLE env vars
    (prefer Secret Manager / --set-secrets in real deploys).
    """
    return {
        "contacts": {
            "table": _env_table(
                "TRIGGER_CONTACTS_TABLE",
                "PROJECT_ID.DATASET_ID.email_trigger_contacts",
            ),
            "columns": [
                "account_id",
                "establishment_id",
                "country",
                "email_permission",
                "sms_permission",
                "primary_language",
            ],
            "date_columns": [
                "pos_activation_date",
                "unsubscribed_date",
            ],
            "order_by": "establishment_id",
        },
        "payments": {
            "table": _env_table(
                "TRIGGER_PAYMENTS_TABLE",
                "PROJECT_ID.DATASET_ID.email_trigger_payments",
            ),
            "columns": [
                "establishment_id",
                "account_id",
                "asset_status",
                "kyc_successful",
                "total_trx",
                "total_trx_volume",
                "active_flag",
            ],
            "date_columns": [
                "created_date",
                "disabled_date",
                "last_trx_date",
            ],
            "order_by": "establishment_id",
        },
        "network_pay": {
            "table": _env_table(
                "TRIGGER_NETWORK_PAY_TABLE",
                "PROJECT_ID.DATASET_ID.email_trigger_network_pay",
            ),
            "columns": [
                "establishment_id",
                "account_id",
                "asset_status",
                "kyc_successful",
                "total_trx",
                "total_trx_volume",
                "active_flag",
            ],
            "date_columns": [
                "created_date",
                "disabled_date",
            ],
            "order_by": "establishment_id",
        },
        "pos": {
            "table": _env_table(
                "TRIGGER_POS_TABLE",
                "PROJECT_ID.DATASET_ID.email_trigger_pos",
            ),
            "columns": [
                "establishment_id",
                "pos_onboarded",
                "pos_total_trx",
                "pos_total_amount",
            ],
            "date_columns": [
                "pos_first_trx_date",
                "pos_last_trx_date",
            ],
            "order_by": "establishment_id",
        },
        "reservations": {
            "table": _env_table(
                "TRIGGER_RESERVATIONS_TABLE",
                "PROJECT_ID.DATASET_ID.email_trigger_reservations",
            ),
            "columns": [
                "establishment_id",
                "active_rt",
                "last_6_months_reservations",
                "last_4_weeks_reservations",
            ],
            "date_columns": [
                "creation_date_rt",
                "deletion_date_rt",
            ],
            "order_by": "establishment_id",
        },
        "website": {
            "table": _env_table(
                "TRIGGER_WEBSITE_TABLE",
                "PROJECT_ID.DATASET_ID.email_trigger_website",
            ),
            "columns": [
                "establishment_id",
                "dw_onboarded_customer",
                "dw_active_more_than_30_days",
                "dw_has_reservation_tool",
            ],
            "date_columns": [
                "dw_creation_date",
                "dw_deletion_date",
            ],
            "order_by": "establishment_id",
        },
    }


def fields_metadata_table() -> str:
    return _env_table(
        "TRIGGER_FIELDS_METADATA_TABLE",
        "PROJECT_ID.DATASET_ID.email_trigger_fields_mapping_metadata",
    )


def fetch_data_with_pagination(
    table_config: Dict[str, Any],
    page_size: int,
    page_number: int,
) -> Union[Dict[str, Any], Tuple[Response, int]]:
    """Shared paginated BigQuery read used by every trigger path."""
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
    order_by = table_config.get("order_by", "establishment_id")

    # Explicit column list — never SELECT *. Deduplicate in case configs drift.
    all_columns = list(
        dict.fromkeys(
            table_config["columns"]
            + table_config.get("date_columns", [])
            + table_config.get("timestamp_columns", [])
        )
    )
    columns = ", ".join(all_columns)

    # Table id comes from env / defaults, not from the request.
    # LIMIT / OFFSET stay parameterized.
    query = f"""
    SELECT {columns}
    FROM `{table_name}`
    ORDER BY {order_by} ASC
    LIMIT @page_size OFFSET @offset
    """
    count_query = f"SELECT COUNT(*) AS total FROM `{table_name}`"

    try:
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("page_size", "INT64", page_size),
                bigquery.ScalarQueryParameter("offset", "INT64", offset),
            ]
        )
        df = client.query(query, job_config=job_config).to_dataframe()

        date_columns = set(table_config.get("date_columns", []))
        for col in df.columns:
            if col in date_columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
                df[col] = df[col].dt.strftime("%Y-%m-%d").where(df[col].notna(), None)

        results = df.replace({np.nan: None}).to_dict(orient="records")
        if not results:
            return jsonify(error=404, description="No data found"), 404

        count_df = client.query(count_query).to_dataframe()
        total_count = int(count_df["total"].iloc[0])
        total_pages = (total_count + page_size - 1) // page_size

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
        logger.error("BigQuery query on %s failed: %s", table_name, error)
        return jsonify(**_internal_error_payload(error)), 500


def fetch_fields_metadata() -> Union[
    Dict[str, List[Dict[str, Any]]], Tuple[Response, int]
]:
    """
    Field-mapping metadata for the marketing platform.

    Response: { "<src_model>": [ {src_field, dest_field, data_type}, ... ], ... }
    """
    table = fields_metadata_table()
    query = f"""
        SELECT src_model, src_field, dest_field, data_type
        FROM `{table}`
        ORDER BY src_model, src_field
    """

    try:
        query_job = client.query(query)
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for row in query_job.result():
            r = dict(row)
            model = r.get("src_model")
            field = r.get("src_field")
            if model is None or field is None:
                continue
            grouped[model].append(
                {
                    "src_field": field,
                    "dest_field": r.get("dest_field"),
                    "data_type": r.get("data_type"),
                }
            )

        if not grouped:
            return (
                jsonify(error=404, description="No mapping fields metadata found"),
                404,
            )

        return {model: grouped[model] for model in sorted(grouped.keys())}
    except Exception as error:
        logger.error("Query on %s failed: %s", table, error)
        return jsonify(**_internal_error_payload(error)), 500


def main(request) -> Union[Response, Tuple[Any, int, Dict[str, str]]]:
    """Cloud Functions / Cloud Run HTTP entry point."""
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": _cors_origin(),
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type, X-API-KEY",
            "Access-Control-Max-Age": "3600",
        }
        return ("", 204, headers)

    headers = {"Access-Control-Allow-Origin": _cors_origin()}

    if request.method != "GET":
        return jsonify(error=405, description="Method Not Allowed"), 405, headers

    try:
        path = request.path.rstrip("/") or "/"
        # Accept with or without trailing slash for local runners.
        if path != "/triggers/fields-metadata" and path.endswith("/"):
            path = path[:-1]

        if path == "/triggers/fields-metadata":
            result = fetch_fields_metadata()
        elif path in PATH_TO_CONFIG:
            page_size = request.args.get(
                "pageSize", default=DEFAULT_PAGE_SIZE, type=int
            )
            page_number = request.args.get(
                "pageNumber", default=DEFAULT_PAGE_NUMBER, type=int
            )
            config_key = PATH_TO_CONFIG[path]
            result = fetch_data_with_pagination(
                table_configs()[config_key],
                page_size=page_size,
                page_number=page_number,
            )
        else:
            return jsonify(error=404, description="Endpoint not found"), 404, headers

        if isinstance(result, tuple):
            return result[0], result[1], headers

        return jsonify(result), 200, headers
    except Exception as error:
        logger.error("Request processing failed: %s", error)
        return jsonify(**_internal_error_payload(error)), 500, headers
