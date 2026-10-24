"""
WindWise Backend — In-memory cache for expensive data fetches.

Caches the raw API responses and processed DataFrames for CACHE_TTL seconds.
All endpoints share the same cached result set.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd

from app.config import settings

logger = logging.getLogger(__name__)

CACHE_TTL = settings.cache_ttl


@dataclass
class CacheEntry:
    data: Any
    fetched_at: float = field(default_factory=time.time)

    def is_fresh(self) -> bool:
        return (time.time() - self.fetched_at) < CACHE_TTL


class DataCache:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._actuals_raw: Optional[CacheEntry] = None
        self._forecasts_raw: Optional[CacheEntry] = None
        self._actuals_df: Optional[CacheEntry] = None
        self._forecasts_df: Optional[CacheEntry] = None
        self._merged_df: Optional[CacheEntry] = None
        self._last_error: Optional[str] = None
        self._last_fetch_time: Optional[float] = None

    @property
    def last_error(self):
        return self._last_error

    @property
    def last_fetch_time(self):
        return self._last_fetch_time

    def set_error(self, msg: str):
        self._last_error = msg

    def clear_error(self):
        self._last_error = None

    def is_fresh(self) -> bool:
        return (
            self._actuals_raw is not None
            and self._actuals_raw.is_fresh()
            and self._merged_df is not None
            and self._merged_df.is_fresh()
        )

    def store(
        self,
        actuals_raw: list,
        forecasts_raw: list,
        actuals_df: pd.DataFrame,
        forecasts_df: pd.DataFrame,
        merged_df: pd.DataFrame,
    ):
        now = time.time()
        self._actuals_raw = CacheEntry(actuals_raw, now)
        self._forecasts_raw = CacheEntry(forecasts_raw, now)
        self._actuals_df = CacheEntry(actuals_df, now)
        self._forecasts_df = CacheEntry(forecasts_df, now)
        self._merged_df = CacheEntry(merged_df, now)
        self._last_fetch_time = now
        self._last_error = None

    def get(self):
        """Returns (actuals_raw, forecasts_raw, actuals_df, forecasts_df, merged_df)"""
        return (
            self._actuals_raw.data if self._actuals_raw else [],
            self._forecasts_raw.data if self._forecasts_raw else [],
            self._actuals_df.data if self._actuals_df else pd.DataFrame(),
            self._forecasts_df.data if self._forecasts_df else pd.DataFrame(),
            self._merged_df.data if self._merged_df else pd.DataFrame(),
        )


# Singleton cache
_cache = DataCache()


def get_cache() -> DataCache:
    return _cache
