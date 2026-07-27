"""
Unit tests for the performance metrics calculator.

Tests each metric calculation against known values and edge cases.
"""

import sys
import os
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from framework.backtester.engine import BacktestResult
from framework.backtester.order import Trade
from framework.metrics.calculator import MetricsCalculator, PerformanceMetrics


# ── Helpers ──────────────────────────────────────────────────

def _make_result(
    equity: list,
    trades: list = None,
    initial_capital: float = 100000.0,
    buy_hold: list = None,
) -> BacktestResult:
    """Create a BacktestResult for testing."""
    return BacktestResult(
        equity_curve=equity,
        trades=trades or [],
        initial_capital=initial_capital,
        final_equity=equity[-1] if equity else initial_capital,
        buy_hold_equity=buy_hold or equity,
    )


def _make_trade(pnl: float, holding_bars: int = 5) -> Trade:
    """Create a Trade with given P&L."""
    return Trade(
        pnl=pnl,
        entry_price=100.0,
        exit_price=100.0 + pnl / 10,
        quantity=10,
        return_pct=pnl / 1000,
        holding_bars=holding_bars,
        commission_total=1.0,
        entry_date="2024-01-01",
        exit_date="2024-01-06",
    )


# ── Tests ────────────────────────────────────────────────────

class TestMetricsCalculator:
    def setup_method(self):
        self.calc = MetricsCalculator(annualization_factor=252, risk_free_rate=0.02)

    def test_total_return(self):
        """Total return should be (final / initial - 1) * 100."""
        result = _make_result([100000, 105000, 110000])
        m = self.calc.calculate(result)
        assert m.total_return_pct == pytest.approx(10.0, rel=0.01)

    def test_negative_return(self):
        """Negative returns should be correctly calculated."""
        result = _make_result([100000, 95000, 90000])
        m = self.calc.calculate(result)
        assert m.total_return_pct == pytest.approx(-10.0, rel=0.01)

    def test_zero_trades(self):
        """Should handle zero trades gracefully."""
        result = _make_result([100000, 100000, 100000])
        m = self.calc.calculate(result)
        assert m.num_trades == 0
        assert m.win_rate_pct == 0
        assert m.profit_factor == 0

    def test_win_rate(self):
        """Win rate should be winners / total * 100."""
        trades = [_make_trade(100), _make_trade(50), _make_trade(-30)]
        result = _make_result([100000, 100100, 100150, 100120], trades=trades)
        m = self.calc.calculate(result)
        assert m.win_rate_pct == pytest.approx(66.67, rel=0.01)

    def test_all_winners(self):
        """100% win rate."""
        trades = [_make_trade(100), _make_trade(200)]
        result = _make_result([100000, 100100, 100300], trades=trades)
        m = self.calc.calculate(result)
        assert m.win_rate_pct == 100.0

    def test_all_losers(self):
        """0% win rate."""
        trades = [_make_trade(-100), _make_trade(-200)]
        result = _make_result([100000, 99900, 99700], trades=trades)
        m = self.calc.calculate(result)
        assert m.win_rate_pct == 0.0

    def test_profit_factor(self):
        """Profit factor = sum(profits) / |sum(losses)|."""
        trades = [_make_trade(300), _make_trade(-100)]
        result = _make_result([100000, 100300, 100200], trades=trades)
        m = self.calc.calculate(result)
        assert m.profit_factor == pytest.approx(3.0, rel=0.01)

    def test_profit_factor_no_losses(self):
        """Profit factor should be inf when no losses."""
        trades = [_make_trade(100), _make_trade(200)]
        result = _make_result([100000, 100100, 100300], trades=trades)
        m = self.calc.calculate(result)
        assert m.profit_factor == float("inf")

    def test_max_drawdown(self):
        """Max drawdown should capture the largest peak-to-trough decline."""
        # Equity goes 100k → 120k → 96k → 110k
        # Drawdown from 120k to 96k = -20%
        result = _make_result([100000, 120000, 96000, 110000])
        m = self.calc.calculate(result)
        assert m.max_drawdown_pct == pytest.approx(-20.0, rel=0.01)

    def test_drawdown_no_decline(self):
        """Max drawdown should be 0 if equity only goes up."""
        result = _make_result([100000, 105000, 110000, 115000])
        m = self.calc.calculate(result)
        assert m.max_drawdown_pct == pytest.approx(0.0, abs=0.01)

    def test_expectancy(self):
        """Expectancy = (win_rate * avg_profit) + (loss_rate * avg_loss)."""
        trades = [_make_trade(200), _make_trade(100), _make_trade(-50)]
        result = _make_result([100000, 100200, 100300, 100250], trades=trades)
        m = self.calc.calculate(result)
        # Win rate = 2/3, avg_profit = 150, loss_rate = 1/3, avg_loss = -50
        expected = (2 / 3 * 150) + (1 / 3 * (-50))
        assert m.expectancy == pytest.approx(expected, rel=0.01)

    def test_holding_time(self):
        """Average holding time should be mean of holding_bars."""
        trades = [_make_trade(100, holding_bars=10), _make_trade(-50, holding_bars=4)]
        result = _make_result([100000, 100100, 100050], trades=trades)
        m = self.calc.calculate(result)
        assert m.avg_holding_bars == pytest.approx(7.0, rel=0.01)

    def test_empty_equity_curve(self):
        """Empty equity curve should return default metrics."""
        result = _make_result([])
        m = self.calc.calculate(result)
        assert m.total_return_pct == 0.0
        assert m.num_trades == 0

    def test_commission_tracking(self):
        """Total commission should sum across all trades."""
        trades = [_make_trade(100), _make_trade(200)]  # Each has commission=1.0
        result = _make_result([100000, 100100, 100300], trades=trades)
        m = self.calc.calculate(result)
        assert m.total_commission == 2.0

    def test_summary_table(self):
        """Summary table should be a non-empty string."""
        trades = [_make_trade(100)]
        result = _make_result([100000, 100100], trades=trades)
        m = self.calc.calculate(result)
        table = m.summary_table()
        assert isinstance(table, str)
        assert "Total Return" in table

    def test_calculate_from_trades(self):
        """Static method should rebuild metrics from just trades."""
        trades = [_make_trade(100), _make_trade(-50), _make_trade(200)]
        m = MetricsCalculator.calculate_from_trades(trades, initial_capital=10000)
        assert m.final_equity == pytest.approx(10250, rel=0.01)
        assert m.num_trades == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
