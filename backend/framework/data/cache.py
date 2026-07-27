"""
Local data cache manager.

Caches downloaded OHLCV data as CSV files to avoid redundant API calls.
Supports configurable TTL (time-to-live) for cache freshness.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DataCache:
    """
    File-based cache for OHLCV market data.

    Stores data as CSV files in a configurable cache directory.
    Filenames encode the symbol, timeframe, and date range.
    """

    def __init__(self, cache_dir: str = "data_cache", ttl_hours: int = 24):
        """
        Args:
            cache_dir: Directory for cached files (relative to backend/).
            ttl_hours: Hours before cached data is considered stale.
        """
        self.cache_dir = os.path.join(_BACKEND_DIR, cache_dir)
        self.ttl_hours = ttl_hours
        os.makedirs(self.cache_dir, exist_ok=True)
        logger.debug("Cache directory: %s (TTL: %dh)", self.cache_dir, ttl_hours)

    def _cache_key(self, symbol: str, timeframe: str, start: str, end: str) -> str:
        """Generate a filesystem-safe cache filename."""
        safe_symbol = symbol.replace("/", "_").replace("-", "_").upper()
        return f"{safe_symbol}_{timeframe}_{start}_{end}.csv"

    def _cache_path(self, key: str) -> str:
        """Full path for a cache key."""
        return os.path.join(self.cache_dir, key)

    def is_fresh(self, symbol: str, timeframe: str, start: str, end: str) -> bool:
        """
        Check if cached data exists and is within TTL.

        Args:
            symbol: Asset ticker (e.g. 'AAPL').
            timeframe: Timeframe string (e.g. '1D').
            start: Start date string.
            end: End date string.

        Returns:
            True if cache hit is fresh, False otherwise.
        """
        key = self._cache_key(symbol, timeframe, start, end)
        path = self._cache_path(key)

        if not os.path.exists(path):
            return False

        modified_time = datetime.fromtimestamp(os.path.getmtime(path))
        age = datetime.now() - modified_time

        if age > timedelta(hours=self.ttl_hours):
            logger.debug("Cache stale for %s (%s old)", key, age)
            return False

        logger.debug("Cache fresh for %s (%s old)", key, age)
        return True

    def load(self, symbol: str, timeframe: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """
        Load cached data if available and fresh.

        Returns:
            DataFrame with OHLCV data, or None if cache miss.
        """
        if not self.is_fresh(symbol, timeframe, start, end):
            return None

        key = self._cache_key(symbol, timeframe, start, end)
        path = self._cache_path(key)

        try:
            df = pd.read_csv(path, parse_dates=["Date"])
            logger.info("Cache HIT: %s (%d rows)", key, len(df))
            return df
        except Exception as e:
            logger.warning("Cache read error for %s: %s", key, e)
            return None

    def save(
        self, df: pd.DataFrame, symbol: str, timeframe: str, start: str, end: str
    ) -> None:
        """
        Save DataFrame to cache.

        Args:
            df: OHLCV DataFrame with a 'Date' column.
            symbol: Asset ticker.
            timeframe: Timeframe string.
            start: Start date string.
            end: End date string.
        """
        key = self._cache_key(symbol, timeframe, start, end)
        path = self._cache_path(key)

        try:
            df.to_csv(path, index=False)
            logger.info("Cache SAVE: %s (%d rows)", key, len(df))
        except Exception as e:
            logger.error("Cache write error for %s: %s", key, e)

    def clear(self) -> int:
        """
        Remove all cached files.

        Returns:
            Number of files removed.
        """
        count = 0
        for fname in os.listdir(self.cache_dir):
            if fname.endswith(".csv"):
                os.remove(os.path.join(self.cache_dir, fname))
                count += 1
        logger.info("Cache cleared: %d files removed", count)
        return count
