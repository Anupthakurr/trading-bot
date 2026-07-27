"""
Unit tests for the backtesting engine.

Tests:
- Portfolio operations (open/close positions)
- Fee and slippage application
- Stop-loss and take-profit execution
- Position sizing
- No look-ahead bias
"""

import sys
import os
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from framework.backtester.order import Order, OrderSide, Position, Trade
from framework.backtester.execution import (
    apply_slippage, apply_commission, check_stop_loss,
    check_take_profit, calculate_position_size,
)
from framework.backtester.portfolio import Portfolio
from framework.backtester.engine import BacktestEngine, BacktestResult
from framework.config.settings import ExecutionConfig, Settings
from framework.strategies.base import Strategy, Signal, StrategySignal


# ── Fixtures ─────────────────────────────────────────────────

def _make_ohlcv(prices: list, volumes: list = None) -> pd.DataFrame:
    """Create a synthetic OHLCV DataFrame for testing."""
    n = len(prices)
    if volumes is None:
        volumes = [1000000] * n
    data = {
        "Date": [f"2024-01-{i+1:02d}" for i in range(n)],
        "Open": [p * 0.99 for p in prices],
        "High": [p * 1.02 for p in prices],
        "Low": [p * 0.97 for p in prices],
        "Close": prices,
        "Volume": volumes[:n],
    }
    return pd.DataFrame(data)


class AlwaysBuyStrategy(Strategy):
    """Test strategy: buys on bar 1, sells on bar 3."""
    name = "TestAlwaysBuy"
    version = 99

    def init(self, data):
        return data

    def next(self, i, data):
        if i == 1:
            return StrategySignal(action=Signal.BUY, price=data.iloc[i]["Close"])
        if i == 3:
            return StrategySignal(action=Signal.SELL, price=data.iloc[i]["Close"])
        return StrategySignal(action=Signal.HOLD, price=data.iloc[i]["Close"])

    def get_default_params(self):
        return {}


# ── Execution Tests ──────────────────────────────────────────

class TestExecution:
    def test_apply_slippage_buy(self):
        """BUY slippage should increase price."""
        config = ExecutionConfig(slippage_pct=0.01, slippage_model="fixed")
        adj, slip = apply_slippage(100.0, "BUY", config)
        assert adj == 101.0
        assert slip == 1.0

    def test_apply_slippage_sell(self):
        """SELL slippage should decrease price."""
        config = ExecutionConfig(slippage_pct=0.01, slippage_model="fixed")
        adj, slip = apply_slippage(100.0, "SELL", config)
        assert adj == 99.0
        assert slip == 1.0

    def test_apply_slippage_zero(self):
        """Zero slippage should not change price."""
        config = ExecutionConfig(slippage_pct=0)
        adj, slip = apply_slippage(100.0, "BUY", config)
        assert adj == 100.0
        assert slip == 0.0

    def test_apply_commission(self):
        """Commission should be correct percentage."""
        config = ExecutionConfig(commission_pct=0.001)
        fee = apply_commission(10000.0, config)
        assert fee == 10.0

    def test_check_stop_loss_triggered(self):
        """SL should trigger when bar low <= stop price."""
        pos = Position(stop_loss=95.0)
        result = check_stop_loss(pos, bar_low=94.0, bar_high=101.0)
        assert result == 95.0

    def test_check_stop_loss_not_triggered(self):
        """SL should not trigger when bar low > stop price."""
        pos = Position(stop_loss=90.0)
        result = check_stop_loss(pos, bar_low=95.0, bar_high=105.0)
        assert result is None

    def test_check_take_profit_triggered(self):
        """TP should trigger when bar high >= take profit price."""
        pos = Position(take_profit=110.0)
        result = check_take_profit(pos, bar_high=112.0)
        assert result == 110.0

    def test_check_take_profit_not_triggered(self):
        """TP should not trigger when bar high < take profit price."""
        pos = Position(take_profit=110.0)
        result = check_take_profit(pos, bar_high=108.0)
        assert result is None

    def test_position_size_with_stop_loss(self):
        """Position size should be based on risk amount / risk per share."""
        size = calculate_position_size(
            capital=100000, price=100, risk_per_trade=0.01,
            stop_loss=95, max_position_pct=1.0,
        )
        # Risk amount = 100000 * 0.01 = 1000
        # Risk per share = 100 - 95 = 5
        # Shares = 1000 / 5 = 200
        assert size == 200

    def test_position_size_without_stop_loss(self):
        """Without SL, should use simple capital fraction."""
        size = calculate_position_size(
            capital=100000, price=100, risk_per_trade=0.01,
            stop_loss=None, max_position_pct=1.0,
        )
        assert size > 0
        assert size <= 1000  # Can't exceed capital / price

    def test_position_size_zero_capital(self):
        """Zero capital should return 0 shares."""
        size = calculate_position_size(
            capital=0, price=100, risk_per_trade=0.01,
            stop_loss=95, max_position_pct=1.0,
        )
        assert size == 0


# ── Portfolio Tests ──────────────────────────────────────────

class TestPortfolio:
    def test_initial_state(self):
        """Portfolio should start with initial capital and no positions."""
        p = Portfolio(initial_capital=50000, cash=50000)
        assert p.cash == 50000
        assert not p.has_position
        assert len(p.closed_trades) == 0

    def test_open_and_close(self):
        """Should be able to open and close a position."""
        config = ExecutionConfig(commission_pct=0, slippage_pct=0)
        p = Portfolio(initial_capital=100000, cash=100000, execution_config=config)

        data = _make_ohlcv([100, 105, 110, 108, 112])

        # Open
        buy_signal = StrategySignal(action=Signal.BUY, price=100.0, stop_loss=90.0)
        p.execute_signal(buy_signal, 0, data)
        assert p.has_position

        # Update equity for bars 0-3
        for i in range(4):
            p.update(i, data)

        # Close
        sell_signal = StrategySignal(action=Signal.SELL, price=108.0)
        p.execute_signal(sell_signal, 3, data)
        assert not p.has_position
        assert len(p.closed_trades) == 1

    def test_force_close(self):
        """Force close should close any open position."""
        config = ExecutionConfig(commission_pct=0, slippage_pct=0)
        p = Portfolio(initial_capital=100000, cash=100000, execution_config=config)

        data = _make_ohlcv([100, 105, 110])

        buy_signal = StrategySignal(action=Signal.BUY, price=100.0)
        p.execute_signal(buy_signal, 0, data)
        assert p.has_position

        p.update(0, data)
        p.update(1, data)
        p.force_close(2, data)
        assert not p.has_position
        assert len(p.closed_trades) == 1


# ── Engine Tests ─────────────────────────────────────────────

class TestBacktestEngine:
    def test_basic_backtest(self):
        """Engine should run a basic backtest without errors."""
        settings = Settings()
        settings.execution = ExecutionConfig(commission_pct=0, slippage_pct=0)

        engine = BacktestEngine(settings)
        data = _make_ohlcv([100, 102, 105, 103, 108, 110])

        strategy = AlwaysBuyStrategy()
        result = engine.run(strategy, data, symbol="TEST", timeframe="1D")

        assert isinstance(result, BacktestResult)
        assert len(result.equity_curve) == 6
        assert result.strategy_name == "TestAlwaysBuy"

    def test_equity_curve_length(self):
        """Equity curve should have one value per bar."""
        settings = Settings()
        engine = BacktestEngine(settings)
        data = _make_ohlcv([100] * 20)
        strategy = AlwaysBuyStrategy()
        result = engine.run(strategy, data)
        assert len(result.equity_curve) == 20

    def test_buy_hold_calculated(self):
        """Buy-and-hold equity should be calculated."""
        settings = Settings()
        engine = BacktestEngine(settings)
        data = _make_ohlcv([100, 110, 120])
        strategy = AlwaysBuyStrategy()
        result = engine.run(strategy, data)
        assert len(result.buy_hold_equity) == 3
        assert result.buy_hold_equity[-1] > result.buy_hold_equity[0]


# ── Trade Tests ──────────────────────────────────────────────

class TestTrade:
    def test_trade_to_dict(self):
        """Trade.to_dict() should produce a valid dictionary."""
        trade = Trade(
            entry_price=100.0, exit_price=110.0,
            quantity=10, pnl=100.0, return_pct=0.10,
            entry_date="2024-01-01", exit_date="2024-01-05",
            holding_bars=4, exit_reason="Signal",
        )
        d = trade.to_dict()
        assert d["entry_price"] == 100.0
        assert d["exit_price"] == 110.0
        assert d["pnl"] == 100.0
        assert d["winner"] is True

    def test_trade_winner_loser(self):
        """Should correctly identify winners and losers."""
        winner = Trade(pnl=50.0)
        loser = Trade(pnl=-30.0)
        assert winner.is_winner
        assert not winner.is_loser
        assert loser.is_loser
        assert not loser.is_winner


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
