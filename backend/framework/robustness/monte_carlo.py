"""
Monte Carlo simulation for trade robustness analysis.

Randomly shuffles the order of closed trades N times and rebuilds
the equity curve for each shuffle. This tests whether the strategy's
performance is due to a lucky trade sequence or is statistically robust.

Produces confidence intervals for final equity, max drawdown, and Sharpe ratio.
"""

import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from framework.backtester.order import Trade
from framework.metrics.calculator import MetricsCalculator, PerformanceMetrics

logger = logging.getLogger(__name__)


@dataclass
class MonteCarloResult:
    """Results of Monte Carlo simulation."""
    n_simulations: int = 0
    initial_capital: float = 100000.0

    # Distributions
    final_equities: List[float] = field(default_factory=list)
    max_drawdowns: List[float] = field(default_factory=list)
    sharpe_ratios: List[float] = field(default_factory=list)

    # Confidence intervals
    equity_percentiles: Dict[str, float] = field(default_factory=dict)
    drawdown_percentiles: Dict[str, float] = field(default_factory=dict)
    sharpe_percentiles: Dict[str, float] = field(default_factory=dict)

    # Original (non-shuffled) values
    original_equity: float = 0.0
    original_drawdown: float = 0.0
    original_sharpe: float = 0.0

    def summary_table(self) -> str:
        """Format Monte Carlo results as a table."""
        lines = [
            f"\n{'='*70}",
            f"  MONTE CARLO SIMULATION - {self.n_simulations} iterations",
            f"{'='*70}",
            f"{'Percentile':<15} {'Final Equity':>15} {'Max DD%':>12} {'Sharpe':>10}",
            f"{'-'*70}",
        ]

        for pct_label in sorted(self.equity_percentiles.keys(), key=lambda x: float(x)):
            eq = self.equity_percentiles.get(pct_label, 0)
            dd = self.drawdown_percentiles.get(pct_label, 0)
            sh = self.sharpe_percentiles.get(pct_label, 0)
            lines.append(
                f"  {pct_label + '%':<13} ${eq:>14,.2f} {dd:>11.2f}% {sh:>9.2f}"
            )

        lines.append(f"{'-'*70}")
        lines.append(
            f"  {'Original':<13} ${self.original_equity:>14,.2f} "
            f"{self.original_drawdown:>11.2f}% {self.original_sharpe:>9.2f}"
        )
        lines.append(f"{'='*70}\n")
        return "\n".join(lines)


def monte_carlo_simulation(
    trades: List[Trade],
    initial_capital: float = 100000.0,
    n_simulations: int = 1000,
    confidence_levels: Optional[List[float]] = None,
    seed: Optional[int] = None,
) -> MonteCarloResult:
    """
    Run Monte Carlo simulation by shuffling trade order.

    Args:
        trades: List of completed trades from backtest.
        initial_capital: Starting capital.
        n_simulations: Number of random shuffles.
        confidence_levels: Percentile levels (e.g., [0.05, 0.25, 0.50, 0.75, 0.95]).
        seed: Random seed for reproducibility.

    Returns:
        MonteCarloResult with distributions and confidence intervals.
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    if confidence_levels is None:
        confidence_levels = [0.05, 0.25, 0.50, 0.75, 0.95]

    if not trades:
        logger.warning("No trades for Monte Carlo simulation")
        return MonteCarloResult(n_simulations=0, initial_capital=initial_capital)

    logger.info("Monte Carlo: %d simulations with %d trades", n_simulations, len(trades))

    # Original metrics
    orig_metrics = MetricsCalculator.calculate_from_trades(trades, initial_capital)

    final_equities = []
    max_drawdowns = []
    sharpe_ratios = []

    trade_pnls = [t.pnl for t in trades]

    for _ in range(n_simulations):
        # Shuffle trade order
        shuffled = trade_pnls.copy()
        random.shuffle(shuffled)

        # Rebuild equity curve
        equity = initial_capital
        equity_curve = [equity]
        for pnl in shuffled:
            equity += pnl
            equity_curve.append(equity)

        final_eq = equity_curve[-1]
        final_equities.append(final_eq)

        # Max drawdown
        eq_series = pd.Series(equity_curve)
        cummax = eq_series.cummax()
        dd = ((eq_series - cummax) / cummax).min() * 100
        max_drawdowns.append(dd)

        # Sharpe from equity changes
        returns = eq_series.pct_change().fillna(0)
        std = returns.std()
        sharpe = float(np.sqrt(252) * (returns.mean() / std)) if std > 0 else 0
        sharpe_ratios.append(sharpe)

    # Compute percentiles
    pct_levels = [int(p * 100) for p in confidence_levels]
    eq_pcts = dict(zip(
        [str(p) for p in pct_levels],
        [float(np.percentile(final_equities, p)) for p in pct_levels],
    ))
    dd_pcts = dict(zip(
        [str(p) for p in pct_levels],
        [float(np.percentile(max_drawdowns, p)) for p in pct_levels],
    ))
    sh_pcts = dict(zip(
        [str(p) for p in pct_levels],
        [float(np.percentile(sharpe_ratios, p)) for p in pct_levels],
    ))

    result = MonteCarloResult(
        n_simulations=n_simulations,
        initial_capital=initial_capital,
        final_equities=final_equities,
        max_drawdowns=max_drawdowns,
        sharpe_ratios=sharpe_ratios,
        equity_percentiles=eq_pcts,
        drawdown_percentiles=dd_pcts,
        sharpe_percentiles=sh_pcts,
        original_equity=orig_metrics.final_equity,
        original_drawdown=orig_metrics.max_drawdown_pct,
        original_sharpe=orig_metrics.sharpe_ratio,
    )

    logger.info(
        "Monte Carlo done: Equity 5th=%.0f, 50th=%.0f, 95th=%.0f",
        eq_pcts.get("5", 0), eq_pcts.get("50", 0), eq_pcts.get("95", 0),
    )

    return result
