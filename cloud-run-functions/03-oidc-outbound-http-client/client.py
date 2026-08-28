"""
OIDC outbound HTTP client for a paginated Cloud Run (or Cloud Functions) feed.

Local / ops path: identity token via `gcloud auth print-identity-token`.
In-GCP path: google-auth ID token with audience = BACKEND_URL.

Set BACKEND_URL to the HTTPS origin of the protected service (no trailing slash).
Never hardcode project numbers or live *.run.app hostnames.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

import requests

try:
    import google.auth.transport.requests as google_auth_requests
    import google.oauth2.id_token as google_id_token

    _HAS_GOOGLE_AUTH = True
except ImportError:  # optional — laptop ops can still use gcloud
    google_auth_requests = None  # type: ignore[assignment]
    google_id_token = None  # type: ignore[assignment]
    _HAS_GOOGLE_AUTH = False

try:
    import pandas as pd

    _HAS_PANDAS = True
except ImportError:
    pd = None  # type: ignore[assignment]
    _HAS_PANDAS = False

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 100
DEFAULT_TIMEOUT_SEC = 60

# Leaf paths on the protected backend. Override via env if your contract differs.
ENDPOINT_FULL = os.environ.get("FEED_ENDPOINT_FULL", "getCatalogData")
ENDPOINT_DAILY = os.environ.get("FEED_ENDPOINT_DAILY", "getCatalogDailyData")


def get_backend_url() -> str:
    url = os.environ.get("BACKEND_URL", "").rstrip("/")
    if not url:
        raise RuntimeError(
            "BACKEND_URL is required (e.g. https://SERVICE-HASH.REGION.run.app)"
        )
    if "YOUR_" in url or "PROJECT_NUMBER" in url:
        raise RuntimeError("BACKEND_URL still contains placeholders — set a real URL")
    return url


def get_auth_token(audience: str) -> str:
    """
    Prefer google-auth (works on Cloud Run / GCE / ADC).
    Fall back to gcloud for laptop / CI where the CLI is already authenticated.
    """
    token = _token_via_google_auth(audience)
    if token:
        return token
    token = _token_via_gcloud()
    if token:
        return token
    raise RuntimeError(
        "Failed to obtain identity token. "
        "Use ADC / workload identity, or `gcloud auth login` + Application Default Credentials."
    )


def _token_via_google_auth(audience: str) -> Optional[str]:
    if not _HAS_GOOGLE_AUTH or google_auth_requests is None or google_id_token is None:
        logger.debug("google-auth not installed; skipping ADC ID token path")
        return None

    try:
        request = google_auth_requests.Request()
        return google_id_token.fetch_id_token(request, audience)
    except Exception as exc:  # ADC missing or wrong audience — try gcloud next
        logger.info("google-auth ID token unavailable: %s", exc)
        return None


def _token_via_gcloud() -> Optional[str]:
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-identity-token"],
            capture_output=True,
            text=True,
            check=True,
        )
        token = result.stdout.strip()
        return token or None
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.info("gcloud identity token unavailable: %s", exc)
        return None


def fetch_page(
    page_size: int = DEFAULT_PAGE_SIZE,
    page_number: int = 1,
    daily: bool = False,
    timeout: int = DEFAULT_TIMEOUT_SEC,
) -> Optional[Dict[str, Any]]:
    """
    GET one page from the protected feed.

    Expects JSON shaped like: {"records": [...], ...pagination fields...}
    """
    backend = get_backend_url()
    endpoint = ENDPOINT_DAILY if daily else ENDPOINT_FULL
    url = f"{backend}/{endpoint}"

    token = get_auth_token(audience=backend)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    params = {"pageSize": page_size, "pageNumber": page_number}

    response = requests.get(url, headers=headers, params=params, timeout=timeout)

    if response.status_code == 200:
        return response.json()

    # Do not log Authorization headers or token material.
    logger.error(
        "feed_request_failed status=%s page=%s body_preview=%s",
        response.status_code,
        page_number,
        (response.text or "")[:200],
    )
    return None


def fetch_all(
    daily: bool = False,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Walk pages until a short page or empty records. Optional max_pages guard."""
    all_records: List[Dict[str, Any]] = []
    page_number = 1

    while True:
        if max_pages is not None and page_number > max_pages:
            logger.warning("stopped_at_max_pages max_pages=%s", max_pages)
            break

        logger.info("fetching page=%s page_size=%s daily=%s", page_number, page_size, daily)
        result = fetch_page(page_size=page_size, page_number=page_number, daily=daily)

        if not result or "records" not in result:
            break

        records = result["records"] or []
        all_records.extend(records)

        if len(records) < page_size:
            break

        page_number += 1

    return all_records


def save_json(records: List[Dict[str, Any]], filename: str) -> None:
    if not records:
        logger.warning("no records to save path=%s", filename)
        return
    with open(filename, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2)
    logger.info("saved_json count=%s path=%s", len(records), filename)


def save_csv(records: List[Dict[str, Any]], filename: str) -> None:
    if not records:
        logger.warning("no records to save path=%s", filename)
        return
    if not _HAS_PANDAS or pd is None:
        raise RuntimeError("pandas is required for CSV export")

    pd.DataFrame(records).to_csv(filename, index=False)
    logger.info("saved_csv count=%s path=%s", len(records), filename)


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Pull a paginated feed from a Cloud Run service using OIDC"
    )
    parser.add_argument("--daily", action="store_true", help="Use daily endpoint leaf")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--out-json", default="catalog_data.json")
    parser.add_argument("--out-csv", default=None, help="Optional CSV path")
    args = parser.parse_args(argv)

    try:
        records = fetch_all(
            daily=args.daily,
            page_size=args.page_size,
            max_pages=args.max_pages,
        )
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 2

    if not records:
        logger.error("no records returned")
        return 1

    save_json(records, args.out_json)
    if args.out_csv:
        save_csv(records, args.out_csv)

    logger.info("done count=%s", len(records))
    return 0


if __name__ == "__main__":
    sys.exit(main())
