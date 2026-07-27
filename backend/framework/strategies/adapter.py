"""
Adapter that wraps the existing engine.py V1/V2/V3 strategy logic
into the new Strategy interface — WITHOUT modifying engine.py.

This module imports indicator functions from the original engine.py
and re-implements the signal logic in a bar-by-bar fashion compatible
with the new backtesting framework.
"""

import sys
import os
import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# Add backend dir to path so we can import the original engine module
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from engine import calculate_rsi, calculate_atr  # type: ignore
from framework.strategies.base import Strategy, Signal, StrategySignal

logger = logging.getLogger(__name__)


class V1SMAStrategy(Strategy):
    """
    V1 — Simple SMA Crossover (adapter from original engine.py).

    Goes long when short SMA > long SMA.
    Exits when short SMA < long SMA.
    """

    name = "V1 — SMA Crossover"
    version = 1

    def get_default_params(self) -> Dict[str, Any]:
        return {"short_window": 20, "long_window": 50}

    def init(self, data: pd.DataFrame) -> pd.DataFrame:
        p = {**self.get_default_params(), **self.params}
        data = data.copy()
        data["SMA_short"] = data["Close"].rolling(
            window=p["short_window"], min_periods=1
        ).mean()
        data["SMA_long"] = data["Close"].rolling(
            window=p["long_window"], min_periods=1
        ).mean()
        return data

    def next(self, i: int, data: pd.DataFrame) -> StrategySignal:
        if i < 1:
            return StrategySignal(action=Signal.HOLD, price=data.iloc[i]["Close"])

        row = data.iloc[i]
        prev = data.iloc[i - 1]

        # Crossover: short crosses above long
        if row["SMA_short"] > row["SMA_long"] and prev["SMA_short"] <= prev["SMA_long"]:
            return StrategySignal(
                action=Signal.BUY, price=row["Close"], reason="SMA crossover (bullish)"
            )
        # Crossunder: short crosses below long
        elif row["SMA_short"] < row["SMA_long"] and prev["SMA_short"] >= prev["SMA_long"]:
            return StrategySignal(
                action=Signal.SELL, price=row["Close"], reason="SMA crossunder (bearish)"
            )

        return StrategySignal(action=Signal.HOLD, price=row["Close"])

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "short_window": [10, 15, 20, 25],
            "long_window": [30, 40, 50, 60],
        }


class V2SMARSIStrategy(Strategy):
    """
    V2 — SMA Crossover + RSI Filter (adapter from original engine.py).

    Buys on SMA crossover only if RSI < overbought threshold.
    Sells on SMA crossunder OR RSI > overbought.
    """

    name = "V2 — SMA + RSI Filter"
    version = 2

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "short_window": 20,
            "long_window": 50,
            "rsi_period": 14,
            "rsi_overbought": 70,
        }

    def init(self, data: pd.DataFrame) -> pd.DataFrame:
        p = {**self.get_default_params(), **self.params}
        data = data.copy()
        data["SMA_short"] = data["Close"].rolling(
            window=p["short_window"], min_periods=1
        ).mean()
        data["SMA_long"] = data["Close"].rolling(
            window=p["long_window"], min_periods=1
        ).mean()
        data["RSI"] = calculate_rsi(data["Close"], periods=p["rsi_period"])
        return data

    def next(self, i: int, data: pd.DataFrame) -> StrategySignal:
        if i < 1:
            return StrategySignal(action=Signal.HOLD, price=data.iloc[i]["Close"])

        p = {**self.get_default_params(), **self.params}
        row = data.iloc[i]
        prev = data.iloc[i - 1]
        rsi_ob = p["rsi_overbought"]

        # Buy: SMA crossover AND RSI not overbought
        if (
            row["SMA_short"] > row["SMA_long"]
            and prev["SMA_short"] <= prev["SMA_long"]
            and row["RSI"] < rsi_ob
        ):
            return StrategySignal(
                action=Signal.BUY,
                price=row["Close"],
                reason=f"SMA crossover + RSI={row['RSI']:.1f}<{rsi_ob}",
            )

        # Sell: SMA crossunder OR RSI overbought while in position
        if row["SMA_short"] < row["SMA_long"] and prev["SMA_short"] >= prev["SMA_long"]:
            return StrategySignal(
                action=Signal.SELL,
                price=row["Close"],
                reason="SMA crossunder",
            )
        if row["RSI"] > rsi_ob and prev["RSI"] <= rsi_ob:
            return StrategySignal(
                action=Signal.SELL,
                price=row["Close"],
                reason=f"RSI overbought ({row['RSI']:.1f}>{rsi_ob})",
            )

        return StrategySignal(action=Signal.HOLD, price=row["Close"])

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "short_window": [10, 15, 20, 25],
            "long_window": [30, 40, 50, 60],
            "rsi_period": [10, 14, 20],
            "rsi_overbought": [65, 70, 75],
        }


class V3ATRRiskStrategy(Strategy):
    """
    V3 — ATR Risk Management (adapter from original engine.py).

    Builds on V2 with:
    - ATR-based fixed stop-loss
    - Risk-based position sizing (risk_per_trade % of capital)
    """

    name = "V3 — ATR Risk Management"
    version = 3

    def get_default_params(self) -> Dict[str, Any]:
        return {
            "short_window": 20,
            "long_window": 50,
            "rsi_period": 14,
            "rsi_overbought": 70,
            "atr_period": 14,
            "atr_multiplier": 2.0,
            "risk_per_trade": 0.01,
        }

    def init(self, data: pd.DataFrame) -> pd.DataFrame:
        p = {**self.get_default_params(), **self.params}
        data = data.copy()
        data["SMA_short"] = data["Close"].rolling(
            window=p["short_window"], min_periods=1
        ).mean()
        data["SMA_long"] = data["Close"].rolling(
            window=p["long_window"], min_periods=1
        ).mean()
        data["RSI"] = calculate_rsi(data["Close"], periods=p["rsi_period"])
        data["ATR"] = calculate_atr(data, periods=p["atr_period"])
        return data

    def next(self, i: int, data: pd.DataFrame) -> StrategySignal:
        if i < 1:
            return StrategySignal(action=Signal.HOLD, price=data.iloc[i]["Close"])

        p = {**self.get_default_params(), **self.params}
        row = data.iloc[i]
        prev = data.iloc[i - 1]
        rsi_ob = p["rsi_overbought"]
        atr_mult = p["atr_multiplier"]

        # Buy: SMA crossover + RSI filter + ATR stop loss
        if (
            row["SMA_short"] > row["SMA_long"]
            and prev["SMA_short"] <= prev["SMA_long"]
            and row["RSI"] < rsi_ob
        ):
            atr_risk = row["ATR"] * atr_mult
            stop_loss = row["Close"] - atr_risk if atr_risk > 0 else None
            return StrategySignal(
                action=Signal.BUY,
                price=row["Close"],
                stop_loss=stop_loss,
                reason=f"SMA cross + RSI={row['RSI']:.1f} | SL={stop_loss:.2f}" if stop_loss else "SMA cross + RSI filter",
            )

        # Sell: crossunder OR RSI overbought
        if row["SMA_short"] < row["SMA_long"] and prev["SMA_short"] >= prev["SMA_long"]:
            return StrategySignal(
                action=Signal.SELL,
                price=row["Close"],
                reason="SMA crossunder",
            )
        if row["RSI"] > rsi_ob and prev["RSI"] <= rsi_ob:
            return StrategySignal(
                action=Signal.SELL,
                price=row["Close"],
                reason=f"RSI overbought ({row['RSI']:.1f})",
            )

        return StrategySignal(action=Signal.HOLD, price=row["Close"])

    def get_param_grid(self) -> Dict[str, List[Any]]:
        return {
            "short_window": [10, 15, 20, 25],
            "long_window": [30, 40, 50, 60],
            "rsi_period": [10, 14, 20],
            "atr_multiplier": [1.5, 2.0, 2.5, 3.0],
            "risk_per_trade": [0.005, 0.01, 0.02],
        }


# ── Factory ──────────────────────────────────────────────────

STRATEGY_REGISTRY: Dict[str, type] = {
    "v1": V1SMAStrategy,
    "v2": V2SMARSIStrategy,
    "v3": V3ATRRiskStrategy,
}


def get_strategy(version: str, params: Optional[Dict[str, Any]] = None) -> Strategy:
    """
    Factory function to create a strategy by version string.

    Args:
        version: 'v1', 'v2', 'v3', or 'v4'.
        params: Optional parameter overrides.

    Returns:
        Strategy instance.
    """
    # V4 is imported here to avoid circular imports
    if version == "v4":
        from framework.strategies.v4_momentum import V4MomentumStrategy
        STRATEGY_REGISTRY["v4"] = V4MomentumStrategy

    cls = STRATEGY_REGISTRY.get(version)
    if cls is None:
        raise ValueError(
            f"Unknown strategy version '{version}'. "
            f"Available: {list(STRATEGY_REGISTRY.keys())}"
        )
    return cls(params=params)
