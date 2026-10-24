"""
WindWise Backend — Elexon BMRS API client.

Fetches FUELHH (actual generation by fuel type) and WINDFOR (wind forecast)
data for January 2026 using the /stream endpoints.

Key design decisions:
- Uses settlementDate parameters for FUELHH (actual generation).
- Uses publishDateTime parameters for WINDFOR to retrieve forecasts published
  before the day-ahead gate closure cutoff.
- Implements retry with exponential back-off for 429/5xx responses.
- Returns raw list[dict] — callers are responsible for processing.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

ELEXON_BASE = settings.elexon_base_url
TIMEOUT = settings.api_timeout

# January 2026 date range
JAN_2026_START = date(2026, 1, 1)
JAN_2026_END = date(2026, 1, 31)


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    retries: int = 3,
) -> Any:
    """GET a URL with retry/back-off. Returns parsed JSON."""
    for attempt in range(retries):
        try:
            response = await client.get(url, params=params, timeout=TIMEOUT)
            if response.status_code == 429:
                wait = 2 ** attempt * 5
                logger.warning("Rate limited. Waiting %ss before retry.", wait)
                await asyncio.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            if attempt == retries - 1:
                raise
            logger.warning("Timeout on attempt %d/%d", attempt + 1, retries)
            await asyncio.sleep(2 ** attempt)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500 and attempt < retries - 1:
                logger.warning(
                    "Server error %d on attempt %d/%d",
                    exc.response.status_code,
                    attempt + 1,
                    retries,
                )
                await asyncio.sleep(2 ** attempt)
                continue
            raise
    return []


async def fetch_fuelhh_wind_actuals() -> list[dict]:
    """
    Fetch FUELHH data for WIND fuel type for January 2026.

    Uses settlementDate filter (2026-01-01 to 2026-01-31).
    Returns list of raw records from the API.
    """
    url = f"{ELEXON_BASE}/datasets/FUELHH/stream"
    params = {
        "settlementDateFrom": JAN_2026_START.isoformat(),
        "settlementDateTo": JAN_2026_END.isoformat(),
        "fuelType": "WIND",
    }
    logger.info("Fetching FUELHH WIND actuals for January 2026 …")
    async with httpx.AsyncClient() as client:
        data = await _get_json(client, url, params)
    if not isinstance(data, list):
        logger.warning("Unexpected FUELHH response type: %s", type(data))
        return []
    logger.info("Fetched %d FUELHH WIND records", len(data))
    return data


async def fetch_windfor_forecasts() -> list[dict]:
    """
    Fetch WINDFOR forecasts published during the period relevant for
    January 2026 day-ahead purchasing decisions.

    The cutoff for purchasing decisions for delivery date D is
    D-1 at 09:20 UTC (EPEX SPOT GB day-ahead gate closure).

    To cover all eligible forecasts for January 2026 (01 Jan – 31 Jan),
    we need forecasts published from:
      - 31 Dec 2025 00:00 UTC  (cutoff for 01 Jan deliveries)
    to
      - 31 Jan 2026 09:20 UTC  (cutoff for 31 Jan deliveries)

    We fetch a slightly wider window to be safe.
    """
    url = f"{ELEXON_BASE}/datasets/WINDFOR/stream"

    publish_from = datetime(2025, 12, 30, 0, 0, 0, tzinfo=timezone.utc)
    publish_to = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)

    params = {
        "publishDateTimeFrom": publish_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "publishDateTimeTo": publish_to.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    logger.info("Fetching WINDFOR forecasts from %s to %s …", publish_from, publish_to)
    async with httpx.AsyncClient() as client:
        data = await _get_json(client, url, params)
    if not isinstance(data, list):
        logger.warning("Unexpected WINDFOR response type: %s", type(data))
        return []
    logger.info("Fetched %d WINDFOR records", len(data))
    return data
