"""
Core bar-by-bar backtesting engine.

Replays historical candles one by one, feeds them to a Strategy,
and manages the Portfolio. Never uses future data.

Usage:
    engine = BacktestEngine(settings)
    result = engine.run(strategy, data)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from framework.backtester.order import Trade
from framework.backtester.portfolio import Portfolio
from framework.config.settings import Settings
from framework.strategies.base import Signal, Strategy

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """
    Container for all backtest outputs.

    Holds the equity curve, trade list, processed data,
    and metadata about the run.
    """
    # Core results
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    data: Optional[pd.DataFrame] = None

    # Metadata
    strategy_name: str = ""
    strategy_version: int = 0
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    symbol: str = ""
    timeframe: str = ""
    start_date: str = ""
    end_date: str = ""
    initial_capital: float = 100000.0
    final_equity: float = 0.0
    execution_time_seconds: float = 0.0

    # Buy & hold reference
    buy_hold_equity: List[float] = field(default_factory=list)

    # Signal markers for charting
    buy_signals: List[Dict[str, Any]] = field(default_factory=list)
    sell_signals: List[Dict[str, Any]] = field(default_factory=list)


class BacktestEngine:
    """
    Bar-by-bar backtesting engine.

    Processes historical data one candle at a time:
    1. Pre-calculates indicators via strategy.init()
    2. Loops through each bar sequentially
    3. Checks SL/TP before getting new signals
    4. Executes strategy signals via portfolio
    5. Records equity and signals

    No look-ahead bias: strategy.next(i, ...) only uses data up to index i.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def run(
        self,
        strategy: Strategy,
        data: pd.DataFrame,
        symbol: str = "",
        timeframe: str = "",
    ) -> BacktestResult:
        """
        Execute a full backtest.

        Args:
            strategy: Strategy instance to test.
            data: OHLCV DataFrame with columns [Date, Open, High, Low, Close, Volume].
            symbol: Symbol being tested (for metadata).
            timeframe: Timeframe string (for metadata).

        Returns:
            BacktestResult with trades, equity curve, and metadata.
        """
        start_time = time.time()
        s = self.settings

        logger.info(
            "Starting backtest: %s on %s (%s) | %d bars | Capital: $%.2f",
            strategy.name, symbol, timeframe, len(data), s.initial_capital,
        )

        # ── 1. Pre-calculate indicators ──────────────────────
        data = strategy.init(data)

        # ── 2. Initialize portfolio ──────────────────────────
        # Extract risk_per_trade from strategy params
        default_params = strategy.get_default_params()
        merged_params = {**default_params, **strategy.params}
        risk_per_trade = merged_params.get("risk_per_trade", 0.01)
        atr_multiplier = merged_params.get("atr_multiplier", 2.0)

        portfolio = Portfolio(
            initial_capital=s.initial_capital,
            cash=s.initial_capital,
            execution_config=s.execution,
            risk_per_trade=risk_per_trade,
            atr_multiplier=atr_multiplier,
        )

        # ── 3. Calculate buy & hold reference ────────────────
        first_close = data.iloc[0]["Close"]
        bh_shares = int(s.initial_capital / first_close)
        bh_remainder = s.initial_capital - (bh_shares * first_close)

        # Track signals
        buy_signals = []
        sell_signals = []

        # ── 4. Bar-by-bar loop ───────────────────────────────
        for i in range(len(data)):
            row = data.iloc[i]

            # 4a. Update portfolio (mark-to-market, check SL/TP)
            exit_reason = portfolio.update(i, data)

            # 4b. Get strategy signal (only if SL/TP didn't close position)
            if exit_reason is None:
                signal = strategy.next(i, data)

                # 4c. Execute signal
                if signal.action != Signal.HOLD:
                    portfolio.execute_signal(signal, i, data)

                    # Record signal for charting
                    if signal.action == Signal.BUY:
                        buy_signals.append({
                            "index": i,
                            "date": str(row.get("Date", i)),
                            "price": signal.price,
                            "reason": signal.reason,
                        })
                    elif signal.action == Signal.SELL:
                        sell_signals.append({
                            "index": i,
                            "date": str(row.get("Date", i)),
                            "price": signal.price,
                            "reason": signal.reason,
                        })
            else:
                # SL/TP triggered — record as sell signal
                sell_signals.append({
                    "index": i,
                    "date": str(row.get("Date", i)),
                    "price": row["Close"],
                    "reason": exit_reason,
                })

        # ── 5. Force close any remaining position ────────────
        portfolio.force_close(len(data) - 1, data)

        # ── 6. Build buy & hold curve ────────────────────────
        buy_hold_equity = []
        for i in range(len(data)):
            bh_value = bh_remainder + (bh_shares * data.iloc[i]["Close"])
            buy_hold_equity.append(bh_value)

        # ── 7. Assemble result ───────────────────────────────
        elapsed = time.time() - start_time
        final_equity = portfolio.equity_curve[-1] if portfolio.equity_curve else s.initial_capital

        result = BacktestResult(
            trades=portfolio.closed_trades,
            equity_curve=portfolio.equity_curve,
            data=data,
            strategy_name=strategy.name,
            strategy_version=strategy.version,
            strategy_params=merged_params,
            symbol=symbol,
            timeframe=timeframe,
            start_date=str(data.iloc[0].get("Date", "")) if len(data) > 0 else "",
            end_date=str(data.iloc[-1].get("Date", "")) if len(data) > 0 else "",
            initial_capital=s.initial_capital,
            final_equity=final_equity,
            execution_time_seconds=elapsed,
            buy_hold_equity=buy_hold_equity,
            buy_signals=buy_signals,
            sell_signals=sell_signals,
        )

        logger.info(
            "Backtest complete: %s | Equity: $%.2f -> $%.2f (%.2f%%) | "
            "%d trades | %.2fs",
            strategy.name,
            s.initial_capital,
            final_equity,
            (final_equity / s.initial_capital - 1) * 100,
            len(portfolio.closed_trades),
            elapsed,
        )

        return result

    def run_multiple(
        self,
        strategy: Strategy,
        datasets: Dict[str, pd.DataFrame],
        timeframe: str = "",
    ) -> Dict[str, BacktestResult]:
        """
        Run backtest on multiple symbols.

        Args:
            strategy: Strategy instance.
            datasets: Dict of symbol -> DataFrame.
            timeframe: Timeframe string.

        Returns:
            Dict of symbol -> BacktestResult.
        """
        results = {}
        for symbol, data in datasets.items():
            try:
                # Create fresh strategy copy for each symbol
                from framework.strategies.adapter import get_strategy
                fresh_strategy = get_strategy(
                    f"v{strategy.version}", strategy.params
                )
                result = self.run(fresh_strategy, data, symbol=symbol, timeframe=timeframe)
                results[symbol] = result
            except Exception as e:
                logger.error("Backtest failed for %s: %s", symbol, e)
        return results
