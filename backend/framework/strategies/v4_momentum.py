"""
V4 — Enhanced Momentum Strategy.

Combines multiple confirmations for high-probability entries:
- EMA crossover (trend direction)
- RSI filter (avoid overbought)
- MACD histogram confirmation (momentum)
- Volume filter (above-average volume)
- ATR trailing stop-loss (adaptive risk management)
- Risk-based position sizing

This is a NEW strategy — does NOT modify V1/V2/V3.
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from framework.strategies.base import Strategy, Signal, StrategySignal

logger = logging.getLogger(__name__)


def _calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def _calculate_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate MACD indicator.

    Returns:
        Tuple of (macd_line, signal_line, histogram).
    """
    ema_fast = _calculate_ema(close, fast)
    ema_slow = _calculate_ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI (self-contained, no dependency on engine.py)."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    high_low = df["High"] - df["Low"]
    high_close = np.abs(df["High"] - df["Close"].shift())
    low_close = np.abs(df["Low"] - df["Close"].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(period).mean()


class V4MomentumStrategy(Strategy):
    """
    V4 — Enhanced Momentum Strategy.

    Entry conditions (ALL must be true):
        1. Fast EMA > Slow EMA (uptrend)
        2. Fast EMA just crossed above Slow EMA (crossover)
        3. RSI < rsi_overbought (not overbought)
        4. MACD histogram > 0 (positive momentum)
        5. Volume > volume_ma-period average (participation confirmation)

    Exit conditions (ANY triggers exit):
        1. Fast EMA < Slow EMA (trend reversal)
        2. RSI > rsi_overbought (overbought)
        3. MACD histogram turns negative
        4. Trailing stop-loss hit (handled by backtester engine)

    Risk management:
        - ATR-based trailing stop-loss
        - Risk-per-trade position sizing
    """

    name = "V4 - Enhanced Momentum"
    version = 4

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "fast_ema": 12,
            "slow_ema": 26,
            "rsi_period": 14,
            "rsi_overbought": 70,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "atr_period": 14,
            "atr_multiplier": 2.5,
            "volume_ma": 20,
            "risk_per_trade": 0.01,
        }

    def init(self, data: pd.DataFrame) -> pd.DataFrame:
        """Pre-calculate all indicators."""
        p = {**self.get_default_params(), **self.params}
        data = data.copy()

        # EMAs
        data["EMA_fast"] = _calculate_ema(data["Close"], p["fast_ema"])
        data["EMA_slow"] = _calculate_ema(data["Close"], p["slow_ema"])

        # RSI
        data["RSI"] = _calculate_rsi(data["Close"], p["rsi_period"])

        # MACD
        macd_line, signal_line, histogram = _calculate_macd(
            data["Close"],
            fast=p["macd_fast"],
            slow=p["macd_slow"],
            signal=p["macd_signal"],
        )
        data["MACD"] = macd_line
        data["MACD_signal"] = signal_line
        data["MACD_hist"] = histogram

        # ATR
        data["ATR"] = _calculate_atr(data, p["atr_period"])

        # Volume MA
        data["Volume_MA"] = data["Volume"].rolling(window=p["volume_ma"], min_periods=1).mean()

        return data

    def next(self, i: int, data: pd.DataFrame) -> StrategySignal:
        """Generate signal for bar i using multi-confirmation logic."""
        p = {**self.get_default_params(), **self.params}
        row = data.iloc[i]

        # Need at least 2 bars for crossover detection
        if i < 1:
            return StrategySignal(action=Signal.HOLD, price=row["Close"])

        prev = data.iloc[i - 1]
        rsi_ob = p["rsi_overbought"]
        atr_mult = p["atr_multiplier"]

        # ── Check for BUY signal ─────────────────────────────
        ema_crossover = (
            row["EMA_fast"] > row["EMA_slow"]
            and prev["EMA_fast"] <= prev["EMA_slow"]
        )
        rsi_ok = row["RSI"] < rsi_ob if not np.isnan(row["RSI"]) else False
        macd_positive = row["MACD_hist"] > 0 if not np.isnan(row["MACD_hist"]) else False
        volume_ok = row["Volume"] > row["Volume_MA"] if not np.isnan(row["Volume_MA"]) else True

        if ema_crossover and rsi_ok and macd_positive and volume_ok:
            atr_val = row["ATR"] if not np.isnan(row["ATR"]) else 0
            atr_risk = atr_val * atr_mult
            stop_loss = row["Close"] - atr_risk if atr_risk > 0 else None

            reasons = []
            reasons.append("EMA crossover")
            reasons.append(f"RSI={row['RSI']:.1f}")
            reasons.append(f"MACD_hist={row['MACD_hist']:.4f}")
            reasons.append(f"Vol>{row['Volume_MA']:.0f}")

            return StrategySignal(
                action=Signal.BUY,
                price=row["Close"],
                stop_loss=stop_loss,
                reason=" | ".join(reasons),
            )

        # ── Check for SELL signal ────────────────────────────
        # EMA crossunder
        ema_crossunder = (
            row["EMA_fast"] < row["EMA_slow"]
            and prev["EMA_fast"] >= prev["EMA_slow"]
        )
        # RSI overbought crossing
        rsi_overbought = (
            not np.isnan(row["RSI"])
            and not np.isnan(prev["RSI"])
            and row["RSI"] > rsi_ob
            and prev["RSI"] <= rsi_ob
        )
        # MACD histogram turns negative
        macd_reversal = (
            not np.isnan(row["MACD_hist"])
            and not np.isnan(prev["MACD_hist"])
            and row["MACD_hist"] < 0
            and prev["MACD_hist"] >= 0
        )

        if ema_crossunder:
            return StrategySignal(
                action=Signal.SELL,
                price=row["Close"],
                reason="EMA crossunder (trend reversal)",
            )
        if rsi_overbought:
            return StrategySignal(
                action=Signal.SELL,
                price=row["Close"],
                reason=f"RSI overbought ({row['RSI']:.1f}>{rsi_ob})",
            )
        if macd_reversal:
            return StrategySignal(
                action=Signal.SELL,
                price=row["Close"],
                reason="MACD histogram turned negative",
            )

        return StrategySignal(action=Signal.HOLD, price=row["Close"])

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "fast_ema": [8, 10, 12, 15, 20],
            "slow_ema": [20, 26, 30, 40, 50],
            "rsi_period": [10, 14, 20],
            "rsi_overbought": [65, 70, 75, 80],
            "atr_multiplier": [1.5, 2.0, 2.5, 3.0, 4.0],
            "risk_per_trade": [0.005, 0.01, 0.02, 0.03],
        }
