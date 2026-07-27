"""
Performance metrics calculator.

Computes 13+ professional trading metrics from backtest results:
Total Return, Annualized Return, Win Rate, Number of Trades,
Average Profit, Average Loss, Profit Factor, Sharpe Ratio,
Sortino Ratio, Maximum Drawdown, Calmar Ratio, Expectancy,
and Average Holding Time.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from framework.backtester.engine import BacktestResult
from framework.backtester.order import Trade

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for all computed performance metrics."""

    # Return metrics
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0

    # Trade statistics
    num_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate_pct: float = 0.0

    # P&L metrics
    total_profit: float = 0.0
    total_loss: float = 0.0
    average_profit: float = 0.0
    average_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0

    # Risk metrics
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    calmar_ratio: float = 0.0

    # Time metrics
    avg_holding_bars: float = 0.0
    avg_holding_time: str = ""

    # Additional
    total_commission: float = 0.0
    buy_hold_return_pct: float = 0.0
    initial_capital: float = 0.0
    final_equity: float = 0.0

    # Drawdown curve (for charting)
    drawdown_curve: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excludes large arrays)."""
        d = {}
        for key, value in self.__dict__.items():
            if key == "drawdown_curve":
                continue  # Skip large array
            if isinstance(value, float):
                d[key] = round(value, 4)
            else:
                d[key] = value
        return d

    def summary_table(self) -> str:
        """Format metrics as a printable ASCII table."""
        lines = [
            "+--------------------------------------------------+",
            "|           PERFORMANCE METRICS SUMMARY            |",
            "+--------------------------------------------------+",
            f"|  Initial Capital        : ${self.initial_capital:>14,.2f}   |",
            f"|  Final Equity           : ${self.final_equity:>14,.2f}   |",
            f"|  Total Return           : {self.total_return_pct:>14.2f}%  |",
            f"|  Annualized Return      : {self.annualized_return_pct:>14.2f}%  |",
            f"|  Buy & Hold Return      : {self.buy_hold_return_pct:>14.2f}%  |",
            "+--------------------------------------------------+",
            f"|  Total Trades           : {self.num_trades:>14d}   |",
            f"|  Winning Trades         : {self.winning_trades:>14d}   |",
            f"|  Losing Trades          : {self.losing_trades:>14d}   |",
            f"|  Win Rate               : {self.win_rate_pct:>14.2f}%  |",
            "+--------------------------------------------------+",
            f"|  Average Profit         : ${self.average_profit:>14,.2f}   |",
            f"|  Average Loss           : ${self.average_loss:>14,.2f}   |",
            f"|  Largest Win            : ${self.largest_win:>14,.2f}   |",
            f"|  Largest Loss           : ${self.largest_loss:>14,.2f}   |",
            f"|  Profit Factor          : {self.profit_factor:>14.2f}   |",
            f"|  Expectancy             : ${self.expectancy:>14,.2f}   |",
            "+--------------------------------------------------+",
            f"|  Sharpe Ratio           : {self.sharpe_ratio:>14.2f}   |",
            f"|  Sortino Ratio          : {self.sortino_ratio:>14.2f}   |",
            f"|  Max Drawdown           : {self.max_drawdown_pct:>14.2f}%  |",
            f"|  Calmar Ratio           : {self.calmar_ratio:>14.2f}   |",
            "+--------------------------------------------------+",
            f"|  Avg Holding Time       : {self.avg_holding_time:>14s}   |",
            f"|  Total Commission       : ${self.total_commission:>14,.2f}   |",
            "+--------------------------------------------------+",
        ]
        return "\n".join(lines)


class MetricsCalculator:
    """
    Calculates all performance metrics from a BacktestResult.

    Usage:
        calc = MetricsCalculator(annualization_factor=252)
        metrics = calc.calculate(backtest_result)
        print(metrics.summary_table())
    """

    def __init__(
        self,
        annualization_factor: float = 252,
        risk_free_rate: float = 0.02,
    ):
        """
        Args:
            annualization_factor: Number of bars per year for return scaling.
            risk_free_rate: Annual risk-free rate for Sharpe/Sortino.
        """
        self.annualization_factor = annualization_factor
        self.risk_free_rate = risk_free_rate

    def calculate(self, result: BacktestResult) -> PerformanceMetrics:
        """
        Compute all metrics from a backtest result.

        Args:
            result: BacktestResult from the backtesting engine.

        Returns:
            PerformanceMetrics with all computed values.
        """
        m = PerformanceMetrics()
        trades = result.trades
        equity = result.equity_curve

        if not equity:
            logger.warning("Empty equity curve — returning default metrics")
            return m

        m.initial_capital = result.initial_capital
        m.final_equity = equity[-1]

        # ── Return Metrics ───────────────────────────────────
        m.total_return_pct = ((m.final_equity / m.initial_capital) - 1) * 100

        n_bars = len(equity)
        if n_bars > 1 and m.initial_capital > 0:
            total_return = m.final_equity / m.initial_capital
            years = n_bars / self.annualization_factor
            if years > 0 and total_return > 0:
                m.annualized_return_pct = ((total_return ** (1 / years)) - 1) * 100
            else:
                m.annualized_return_pct = 0.0

        # Buy & Hold
        if result.buy_hold_equity:
            bh_final = result.buy_hold_equity[-1]
            m.buy_hold_return_pct = ((bh_final / m.initial_capital) - 1) * 100

        # ── Trade Statistics ─────────────────────────────────
        m.num_trades = len(trades)

        if m.num_trades > 0:
            winners = [t for t in trades if t.is_winner]
            losers = [t for t in trades if t.is_loser]

            m.winning_trades = len(winners)
            m.losing_trades = len(losers)
            m.win_rate_pct = (m.winning_trades / m.num_trades) * 100

            # Profit/Loss
            profits = [t.pnl for t in winners]
            losses = [t.pnl for t in losers]

            m.total_profit = sum(profits) if profits else 0
            m.total_loss = sum(losses) if losses else 0

            m.average_profit = np.mean(profits) if profits else 0
            m.average_loss = np.mean(losses) if losses else 0

            m.largest_win = max(profits) if profits else 0
            m.largest_loss = min(losses) if losses else 0

            # Profit Factor
            if m.total_loss != 0:
                m.profit_factor = abs(m.total_profit / m.total_loss)
            else:
                m.profit_factor = float("inf") if m.total_profit > 0 else 0

            # Expectancy
            win_rate = m.winning_trades / m.num_trades
            loss_rate = m.losing_trades / m.num_trades
            m.expectancy = (win_rate * m.average_profit) + (loss_rate * m.average_loss)

            # Holding time
            holding_bars = [t.holding_bars for t in trades]
            m.avg_holding_bars = np.mean(holding_bars) if holding_bars else 0
            m.avg_holding_time = f"{m.avg_holding_bars:.1f} bars"

            # Total commission
            m.total_commission = sum(t.commission_total for t in trades)

        # ── Risk Metrics ─────────────────────────────────────
        equity_series = pd.Series(equity)
        daily_returns = equity_series.pct_change().fillna(0)

        # Sharpe Ratio
        m.sharpe_ratio = self._sharpe_ratio(daily_returns)

        # Sortino Ratio
        m.sortino_ratio = self._sortino_ratio(daily_returns)

        # Maximum Drawdown
        m.max_drawdown_pct, m.drawdown_curve = self._max_drawdown(equity_series)

        # Calmar Ratio
        if m.max_drawdown_pct != 0:
            m.calmar_ratio = m.annualized_return_pct / abs(m.max_drawdown_pct)
        else:
            m.calmar_ratio = float("inf") if m.annualized_return_pct > 0 else 0

        return m

    def _sharpe_ratio(self, returns: pd.Series) -> float:
        """
        Calculate annualized Sharpe Ratio.

        Sharpe = √N × (mean(excess_return) / std(excess_return))
        """
        daily_rf = self.risk_free_rate / self.annualization_factor
        excess = returns - daily_rf
        std = excess.std()

        if std > 0 and not np.isnan(std):
            return float(np.sqrt(self.annualization_factor) * (excess.mean() / std))
        return 0.0

    def _sortino_ratio(self, returns: pd.Series) -> float:
        """
        Calculate annualized Sortino Ratio.

        Like Sharpe but only penalizes downside deviation.
        """
        daily_rf = self.risk_free_rate / self.annualization_factor
        excess = returns - daily_rf
        downside = excess[excess < 0]
        downside_std = downside.std()

        if downside_std > 0 and not np.isnan(downside_std):
            return float(np.sqrt(self.annualization_factor) * (excess.mean() / downside_std))
        return 0.0

    def _max_drawdown(self, equity: pd.Series) -> tuple[float, list]:
        """
        Calculate maximum drawdown and the full drawdown curve.

        Returns:
            Tuple of (max_drawdown_pct, drawdown_curve_list).
        """
        cummax = equity.cummax()
        drawdown = (equity - cummax) / cummax
        drawdown = drawdown.fillna(0)

        max_dd = float(drawdown.min()) * 100  # Convert to percentage
        dd_curve = (drawdown * 100).tolist()

        return max_dd, dd_curve

    @staticmethod
    def calculate_from_trades(
        trades: List[Trade],
        initial_capital: float = 100000.0,
    ) -> "PerformanceMetrics":
        """
        Calculate basic metrics from just a trade list (for Monte Carlo).

        Rebuilds equity curve from sequential trade P&Ls.
        """
        m = PerformanceMetrics()
        m.initial_capital = initial_capital
        m.num_trades = len(trades)

        if not trades:
            m.final_equity = initial_capital
            return m

        # Rebuild equity curve from trades
        equity = initial_capital
        equity_curve = [initial_capital]
        for t in trades:
            equity += t.pnl
            equity_curve.append(equity)

        m.final_equity = equity
        m.total_return_pct = ((equity / initial_capital) - 1) * 100

        # Trade stats
        winners = [t for t in trades if t.pnl > 0]
        losers = [t for t in trades if t.pnl < 0]
        m.winning_trades = len(winners)
        m.losing_trades = len(losers)
        m.win_rate_pct = (m.winning_trades / m.num_trades) * 100 if m.num_trades > 0 else 0

        profits = [t.pnl for t in winners]
        losses = [t.pnl for t in losers]
        m.total_profit = sum(profits) if profits else 0
        m.total_loss = sum(losses) if losses else 0
        m.average_profit = float(np.mean(profits)) if profits else 0
        m.average_loss = float(np.mean(losses)) if losses else 0
        m.profit_factor = abs(m.total_profit / m.total_loss) if m.total_loss != 0 else 0

        # Drawdown from rebuilt curve
        eq_series = pd.Series(equity_curve)
        cummax = eq_series.cummax()
        dd = (eq_series - cummax) / cummax
        m.max_drawdown_pct = float(dd.min()) * 100

        # Sharpe from equity changes
        returns = eq_series.pct_change().fillna(0)
        std = returns.std()
        if std > 0:
            m.sharpe_ratio = float(np.sqrt(252) * (returns.mean() / std))

        return m
