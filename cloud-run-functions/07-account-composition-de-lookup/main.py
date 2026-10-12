"""HTTP Cloud Function: account-composition lookup with OR-union match strategies.

Sanitized rewrite of a dashboard DE lookup handler. Focus:
- Compose a country-scoped account id from prefix + store + metro (zero-stripped)
- Accept metro alone, metro+store, metroAccountIdentifier, or a long id in metroId
- OR-union those strategies with BigQuery ArrayQueryParameter + UNNEST
- Parameterized SQL, hard limit caps, gated exception detail

Distinct from the paired-filter tickets handler (pattern 09), which requires
metroId+storeId together and ANDs independent filters — it does not compose ids.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple, Union

from flask import Response, jsonify
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_OFFSET = 0
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000

# Country account layout: PREFIX + store(zfill STORE_WIDTH) + metro(zfill METRO_WIDTH).
# Source used a hard-coded national prefix; keep it deploy-configurable here.
DEFAULT_ACCOUNT_PREFIX = "COUNTRY_ACCOUNT_PREFIX"
DEFAULT_STORE_WIDTH = 3
DEFAULT_METRO_WIDTH = 8

# Activity / lead columns returned to callers. Keep explicit — never SELECT *.
# Source returned email and similar contact fields; omit PII from the public exemplar.
RETURN_COLUMNS = (
    "subject",
    "assigned_id",
    "description",
    "type",
    "created_date",
    "sub_type",
    "event_topic",
    "is_closed",
    "name_id",
    "outcome",
    "activity_id",
    "start_date",
    "lead_account_id",
    "metro_account_identifier",
    "user_id",
    "profile_name",
    "won_status",
    "metro_id",
    "store_id",
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
    project = os.environ.get("BQ_PROJECT_ID", "").strip() or None
    return bigquery.Client(project=project)


def _resolve_table() -> str:
    """
    Full ``project.dataset.table`` for the activity / lead extract.

    ACCOUNT_LOOKUP_TABLE overrides when set. Otherwise build from
    BQ_PROJECT_ID + DATASET_ID + table leaf.
    """
    override = os.environ.get("ACCOUNT_LOOKUP_TABLE", "").strip()
    if override:
        return override

    project = os.environ.get("BQ_PROJECT_ID", "").strip()
    dataset = os.environ.get("DATASET_ID", "").strip() or "DATASET_ID"
    table = (
        os.environ.get("ACCOUNT_LOOKUP_TABLE_ID", "").strip()
        or "account_activity_lookup"
    )

    if not project:
        raise ValueError(
            "BQ_PROJECT_ID is required when ACCOUNT_LOOKUP_TABLE is unset. "
            "Set BQ_PROJECT_ID=PROJECT_ID or ACCOUNT_LOOKUP_TABLE=project.dataset.table."
        )
    return f"{project}.{dataset}.{table}"


def _account_prefix() -> str:
    return (
        os.environ.get("ACCOUNT_ID_PREFIX", "").strip() or DEFAULT_ACCOUNT_PREFIX
    )


def _store_width() -> int:
    raw = os.environ.get("ACCOUNT_STORE_WIDTH", "").strip()
    if not raw:
        return DEFAULT_STORE_WIDTH
    return int(raw)


def _metro_width() -> int:
    raw = os.environ.get("ACCOUNT_METRO_WIDTH", "").strip()
    if not raw:
        return DEFAULT_METRO_WIDTH
    return int(raw)


def _strip_leading_zeros(value: Optional[str]) -> Optional[str]:
    """Normalize padded numeric strings so '00154530' and '154530' match."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.lstrip("0") or "0"


def _compose_account_ids(metro: Optional[str], store: Optional[str]) -> List[str]:
    """
    Build the country-scoped account identifier used in warehouse extracts.

    Layout: PREFIX + store(zfill N) + metro(zfill M).
    Example with PREFIX=COUNTRY_ACCOUNT_PREFIX, store=58, metro=154530
    → COUNTRY_ACCOUNT_PREFIX05800154530.
    """
    if not metro or not store:
        return []
    prefix = _account_prefix()
    store_part = store.zfill(_store_width())
    metro_part = metro.zfill(_metro_width())
    return [f"{prefix}{store_part}{metro_part}"]


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


def _build_match_clause(
    metro: Optional[str],
    store: Optional[str],
    account_ids: List[str],
) -> Tuple[str, List[Any]]:
    """
    OR-union match strategies into one WHERE fragment + query parameters.

    Strategies:
      1. metro + store (zero-stripped equality)
      2. metro alone (when store absent)
      3. composed / explicit account ids via UNNEST(@account_ids)
    """
    matches: List[str] = []
    params: List[Any] = []

    if metro and store:
        matches.append(
            "(LTRIM(CAST(metro_id AS STRING), '0') = @metro"
            " AND CAST(store_id AS STRING) = @store)"
        )
        params.append(bigquery.ScalarQueryParameter("metro", "STRING", metro))
        params.append(bigquery.ScalarQueryParameter("store", "STRING", store))
    elif metro:
        matches.append("LTRIM(CAST(metro_id AS STRING), '0') = @metro")
        params.append(bigquery.ScalarQueryParameter("metro", "STRING", metro))

    if account_ids:
        matches.append(
            "CAST(metro_account_identifier AS STRING) IN UNNEST(@account_ids)"
        )
        params.append(
            bigquery.ArrayQueryParameter("account_ids", "STRING", account_ids)
        )

    if not matches:
        raise ValueError("No match strategies available for the given filters")

    return " OR ".join(matches), params


def fetch_account_activity(
    metro_id: Optional[str],
    store_id: Optional[str],
    metro_account_identifier: Optional[str],
    offset: int,
    limit: int,
) -> Dict[str, Any]:
    """Run a parameterized SELECT with OR-union identity matching + SQL paging."""
    metro = _strip_leading_zeros(metro_id)
    store = _strip_leading_zeros(store_id)
    account = (
        str(metro_account_identifier).strip() if metro_account_identifier else None
    )

    account_ids = _compose_account_ids(metro, store)
    if account:
        account_ids.append(account)
    # Callers sometimes paste the full composed id into metroId.
    if metro and len(metro) > _metro_width():
        account_ids.append(metro)

    # Dedupe while preserving order (compose + explicit + long-metro may overlap).
    seen: set = set()
    unique_ids: List[str] = []
    for aid in account_ids:
        if aid not in seen:
            seen.add(aid)
            unique_ids.append(aid)

    match_sql, match_params = _build_match_clause(metro, store, unique_ids)

    table = _resolve_table()
    columns = ", ".join(RETURN_COLUMNS)
    created_from = os.environ.get("ACCOUNT_LOOKUP_CREATED_FROM", "2024-02-01").strip()

    # Table id and created_from come from deploy-time env only — never from request input.
    query = f"""
    SELECT {columns}
    FROM `{table}`
    WHERE created_date >= @created_from
      AND ({match_sql})
    ORDER BY created_date DESC
    LIMIT @limit
    OFFSET @offset
    """

    params: List[Any] = [
        bigquery.ScalarQueryParameter("created_from", "DATE", created_from),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
        bigquery.ScalarQueryParameter("offset", "INT64", offset),
    ]
    params.extend(match_params)

    logger.info(
        "account_lookup metro=%s store=%s account_ids=%s offset=%s limit=%s table=%s",
        metro,
        store,
        unique_ids,
        offset,
        limit,
        table,
    )

    client = _bq_client()
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    rows = client.query(query, job_config=job_config).result()

    records: List[Dict[str, Any]] = []
    for row in rows:
        records.append({col: row[col] for col in RETURN_COLUMNS})

    return {"records": records, "count": len(records)}


def lookup(request) -> Union[Response, Tuple[Response, int]]:
    """
    GET handler for account-composition activity lookup.

    Query params:
      metroId and/or metroAccountIdentifier (at least one required)
      storeId (optional; enables composition + paired metro/store match)
      offset (default 0), limit (default 100, max 1000)
    """
    if request.method != "GET":
        return jsonify(error=405, description="Method Not Allowed"), 405

    metro_id = request.args.get("metroId")
    store_id = request.args.get("storeId")
    metro_account_identifier = request.args.get("metroAccountIdentifier")

    if not metro_id and not metro_account_identifier:
        return (
            jsonify(
                error=400,
                description="metroId or metroAccountIdentifier is required",
            ),
            400,
        )

    offset, limit, paging_error = _parse_paging(request.args)
    if paging_error is not None:
        return paging_error

    try:
        payload = fetch_account_activity(
            metro_id,
            store_id,
            metro_account_identifier,
            offset,
            limit,
        )
    except ValueError as exc:
        logger.exception("Configuration or filter error in account lookup")
        return jsonify(_internal_error_payload(exc)), 500
    except Exception as exc:
        logger.exception("BigQuery account lookup query failed")
        return jsonify(_internal_error_payload(exc)), 500

    if not payload["records"]:
        return jsonify(error=404, description="Establishment not found"), 404

    return jsonify(payload), 200
