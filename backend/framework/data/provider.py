"""
Market data providers.

Abstract DataProvider interface with concrete implementations
for yfinance (stocks, ETFs, crypto) and extensible for other sources.
Integrates with the DataCache for local caching.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

import pandas as pd
import yfinance as yf

from framework.data.cache import DataCache
from framework.data.timeframes import Timeframe, resample_ohlcv

logger = logging.getLogger(__name__)


class DataProvider(ABC):
    """Abstract base class for market data providers."""

    @abstractmethod
    def fetch(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data for a symbol.

        Args:
            symbol: Asset ticker (e.g. 'AAPL', 'BTC-USD').
            timeframe: Desired timeframe.
            start: Start date string (YYYY-MM-DD).
            end: End date string (YYYY-MM-DD).

        Returns:
            DataFrame with columns: [Date, Open, High, Low, Close, Volume].
            Date column is string-formatted YYYY-MM-DD (or datetime for intraday).
        """
        ...

    def fetch_multiple(
        self,
        symbols: List[str],
        timeframe: Timeframe,
        start: str,
        end: str,
    ) -> dict[str, pd.DataFrame]:
        """
        Fetch data for multiple symbols.

        Returns:
            Dict mapping symbol -> DataFrame.
        """
        results = {}
        for symbol in symbols:
            try:
                df = self.fetch(symbol, timeframe, start, end)
                results[symbol] = df
                logger.info("Fetched %s: %d bars", symbol, len(df))
            except Exception as e:
                logger.error("Failed to fetch %s: %s", symbol, e)
        return results


class YFinanceProvider(DataProvider):
    """
    Data provider using Yahoo Finance via the yfinance library.

    Supports stocks (AAPL, MSFT), ETFs (SPY), crypto (BTC-USD, ETH-USD),
    and forex pairs (EURUSD=X).
    """

    def __init__(self, cache: Optional[DataCache] = None):
        """
        Args:
            cache: Optional DataCache instance for local caching.
        """
        self.cache = cache

    def fetch(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data from Yahoo Finance with optional caching.

        For 4h timeframe, fetches 1h data and resamples.
        """
        tf_str = timeframe.value

        # Check cache first
        if self.cache:
            cached = self.cache.load(symbol, tf_str, start, end)
            if cached is not None:
                return cached

        logger.info("Downloading %s %s from %s to %s...", symbol, tf_str, start, end)

        # Normalize symbol for yfinance
        yf_symbol = self._normalize_symbol(symbol)

        # Determine fetch interval
        fetch_tf = timeframe
        if timeframe.needs_resample:
            fetch_tf = Timeframe.H1  # Fetch hourly, resample to 4h

        ticker = yf.Ticker(yf_symbol)

        # yfinance has max period limits for intraday data
        if fetch_tf in (Timeframe.M5, Timeframe.M15):
            # Max 60 days for 5m/15m
            df = ticker.history(
                start=start, end=end,
                interval=fetch_tf.yfinance_interval,
            )
        elif fetch_tf in (Timeframe.H1,):
            # Max 730 days for 1h
            df = ticker.history(
                start=start, end=end,
                interval=fetch_tf.yfinance_interval,
            )
        else:
            # Daily — no limit
            df = ticker.history(start=start, end=end, interval="1d")

        if df.empty:
            raise ValueError(
                f"No data returned for {symbol} ({tf_str}) "
                f"from {start} to {end}. Check symbol and date range."
            )

        # Standardize columns
        df = self._standardize(df)

        # Resample if needed (e.g., 1h → 4h)
        if timeframe.needs_resample:
            df = resample_ohlcv(df, timeframe)
            df.reset_index(inplace=True)
            df.rename(columns={"index": "Date"}, inplace=True)
            # Re-standardize date format
            if hasattr(df["Date"].iloc[0], "strftime"):
                df["Date"] = df["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")

        # Cache the result
        if self.cache:
            self.cache.save(df, symbol, tf_str, start, end)

        logger.info("Downloaded %s: %d bars", symbol, len(df))
        return df

    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol format for yfinance compatibility.

        Examples:
            BTCUSDT → BTC-USD
            ETHUSDT → ETH-USD
            AAPL → AAPL (unchanged)
            EURUSD → EURUSD=X
        """
        s = symbol.upper().strip()

        # Crypto: BTCUSDT → BTC-USD
        if s.endswith("USDT"):
            base = s[:-4]
            return f"{base}-USD"

        # Forex: check common pairs
        forex_bases = ["EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD"]
        for base in forex_bases:
            if s.startswith(base) and s.endswith("USD"):
                return f"{s}=X"
            if s.startswith("USD") and s[3:] in forex_bases:
                return f"{s}=X"

        return s

    @staticmethod
    def _standardize(df: pd.DataFrame) -> pd.DataFrame:
        """
        Standardize yfinance output to our canonical format.

        Ensures columns: [Date, Open, High, Low, Close, Volume]
        """
        df = df.copy()
        df.reset_index(inplace=True)

        # yfinance uses 'Date' or 'Datetime' as index name
        date_col = None
        for col in df.columns:
            if col.lower() in ("date", "datetime"):
                date_col = col
                break
        if date_col is None and df.columns[0] != "Date":
            df.rename(columns={df.columns[0]: "Date"}, inplace=True)
        elif date_col and date_col != "Date":
            df.rename(columns={date_col: "Date"}, inplace=True)

        # Ensure Date is string for daily data
        if hasattr(df["Date"].iloc[0], "strftime"):
            # Check if it's daily (no time component matters)
            sample = df["Date"].iloc[0]
            if hasattr(sample, "hour") and sample.hour == 0 and sample.minute == 0:
                df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
            else:
                df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d %H:%M:%S")

        # Keep only canonical columns
        keep_cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
        available = [c for c in keep_cols if c in df.columns]
        df = df[available]

        return df
