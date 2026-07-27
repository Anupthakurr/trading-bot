"""
Timeframe definitions and OHLCV resampling utilities.

Supports: 5m, 15m, 1h, 4h, 1D timeframes with conversion
between them and pandas frequency strings.
"""

from enum import Enum
from typing import Optional

import pandas as pd


class Timeframe(Enum):
    """Supported trading timeframes."""
    M1  = "1m"
    M5  = "5m"
    M15 = "15m"
    H1  = "1h"
    H4  = "4h"
    D1  = "1D"

    @property
    def pandas_freq(self) -> str:
        """Return pandas-compatible frequency string."""
        mapping = {
            "1m":  "1min",
            "5m":  "5min",
            "15m": "15min",
            "1h":  "1h",
            "4h":  "4h",
            "1D":  "1D",
        }
        return mapping[self.value]

    @property
    def yfinance_interval(self) -> str:
        """Return yfinance-compatible interval string."""
        mapping = {
            "1m":  "1m",
            "5m":  "5m",
            "15m": "15m",
            "1h":  "1h",
            "4h":  "1h",   # yfinance doesn't support 4h; we fetch 1h and resample
            "1D":  "1d",
        }
        return mapping[self.value]

    @property
    def needs_resample(self) -> bool:
        """Whether this timeframe requires resampling from a lower timeframe."""
        return self == Timeframe.H4

    @property
    def annualization_factor(self) -> float:
        """Number of bars per year, used for annualizing returns."""
        factors = {
            "1m":  252 * 6.5 * 60,   # ~98,280 bars/year (stocks)
            "5m":  252 * 6.5 * 12,   # ~19,656 bars/year (stocks)
            "15m": 252 * 6.5 * 4,    # ~6,552
            "1h":  252 * 6.5,        # ~1,638
            "4h":  252 * 1.625,      # ~409.5
            "1D":  252,              # Standard trading days
        }
        return factors[self.value]

    @property
    def display_name(self) -> str:
        """Human-readable name."""
        names = {
            "1m":  "1 Minute",
            "5m":  "5 Minutes",
            "15m": "15 Minutes",
            "1h":  "1 Hour",
            "4h":  "4 Hours",
            "1D":  "Daily",
        }
        return names[self.value]

    @classmethod
    def from_string(cls, value: str) -> "Timeframe":
        """Parse a timeframe from a string like '1h', '1D', '5m'."""
        normalized = value.strip()
        for member in cls:
            if member.value.lower() == normalized.lower():
                return member
        raise ValueError(
            f"Unknown timeframe '{value}'. "
            f"Supported: {[t.value for t in cls]}"
        )


def resample_ohlcv(
    df: pd.DataFrame,
    target_timeframe: Timeframe,
    source_timeframe: Optional[Timeframe] = None,
) -> pd.DataFrame:
    """
    Resample OHLCV data to a higher timeframe.

    Args:
        df: DataFrame with DatetimeIndex and columns [Open, High, Low, Close, Volume].
        target_timeframe: Desired output timeframe.
        source_timeframe: Source timeframe (for validation). Optional.

    Returns:
        Resampled DataFrame with proper OHLCV aggregation.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        if "Date" in df.columns:
            df = df.copy()
            df["Date"] = pd.to_datetime(df["Date"])
            df.set_index("Date", inplace=True)
        else:
            raise ValueError("DataFrame must have a DatetimeIndex or a 'Date' column.")

    freq = target_timeframe.pandas_freq

    resampled = df.resample(freq).agg({
        "Open":   "first",
        "High":   "max",
        "Low":    "min",
        "Close":  "last",
        "Volume": "sum",
    }).dropna()

    return resampled
