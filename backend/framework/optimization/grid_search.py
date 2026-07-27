"""
Grid search parameter optimizer.

Exhaustively tests all parameter combinations from a grid,
runs backtests for each, and ranks results by a chosen metric.
"""

import itertools
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd
from tqdm import tqdm

from framework.backtester.engine import BacktestEngine, BacktestResult
from framework.config.settings import Settings
from framework.metrics.calculator import MetricsCalculator, PerformanceMetrics
from framework.strategies.adapter import get_strategy
from framework.strategies.base import Strategy

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Result of a single parameter combination test."""
    params: Dict[str, Any] = field(default_factory=dict)
    metrics: Optional[PerformanceMetrics] = None
    rank: int = 0


@dataclass
class OptimizationReport:
    """Full optimization report with all results ranked."""
    strategy_version: str = ""
    symbol: str = ""
    timeframe: str = ""
    method: str = "grid"
    total_combinations: int = 0
    elapsed_seconds: float = 0.0
    results: List[OptimizationResult] = field(default_factory=list)
    best_params: Dict[str, Any] = field(default_factory=dict)
    best_metrics: Optional[PerformanceMetrics] = None

    def summary_table(self, top_n: int = 10) -> str:
        """Format top results as an ASCII table."""
        lines = [
            f"\n{'='*80}",
            f"  OPTIMIZATION RESULTS - {self.method.upper()} SEARCH",
            f"  Strategy: {self.strategy_version} | Symbol: {self.symbol} | TF: {self.timeframe}",
            f"  Tested: {self.total_combinations} combinations in {self.elapsed_seconds:.1f}s",
            f"{'='*80}",
            f"{'Rank':<5} {'Sharpe':>8} {'PF':>8} {'Return%':>9} {'MaxDD%':>8} {'WinR%':>7} {'Trades':>7}  Params",
            f"{'-'*80}",
        ]
        for r in self.results[:top_n]:
            m = r.metrics
            if m is None:
                continue
            param_str = ", ".join(f"{k}={v}" for k, v in r.params.items())
            lines.append(
                f"#{r.rank:<4} {m.sharpe_ratio:>8.2f} {m.profit_factor:>8.2f} "
                f"{m.total_return_pct:>8.2f}% {m.max_drawdown_pct:>7.2f}% "
                f"{m.win_rate_pct:>6.1f}% {m.num_trades:>6d}  {param_str}"
            )
        lines.append(f"{'='*80}\n")
        return "\n".join(lines)


def grid_search(
    strategy_version: str,
    data: pd.DataFrame,
    settings: Settings,
    param_grid: Optional[Dict[str, List[Any]]] = None,
    symbol: str = "",
    timeframe: str = "",
    rank_by: str = "sharpe_ratio",
    top_n: int = 10,
    annualization_factor: float = 252,
) -> OptimizationReport:
    """
    Exhaustive grid search over all parameter combinations.

    Args:
        strategy_version: 'v1', 'v2', 'v3', or 'v4'.
        data: OHLCV DataFrame.
        settings: Framework settings.
        param_grid: Dict of param_name -> list of values. If None, uses strategy defaults.
        symbol: Symbol string for reporting.
        timeframe: Timeframe string for reporting.
        rank_by: Metric to rank by ('sharpe_ratio' or 'profit_factor').
        top_n: Number of top results to return.
        annualization_factor: For metrics calculation.

    Returns:
        OptimizationReport with all results ranked.
    """
    start_time = time.time()

    # Get default param grid from strategy if not provided
    if param_grid is None:
        base_strategy = get_strategy(strategy_version)
        param_grid = base_strategy.get_param_grid()

    if not param_grid:
        raise ValueError(f"No parameter grid defined for {strategy_version}")

    # Generate all combinations
    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())
    combinations = list(itertools.product(*param_values))
    total = len(combinations)

    logger.info(
        "Grid search: %d combinations for %s on %s (%s)",
        total, strategy_version, symbol, timeframe,
    )

    # Run backtests
    engine = BacktestEngine(settings)
    calc = MetricsCalculator(annualization_factor=annualization_factor)
    results: List[OptimizationResult] = []

    for combo in tqdm(combinations, desc=f"Grid Search ({strategy_version})", unit="run"):
        params = dict(zip(param_names, combo))

        try:
            strategy = get_strategy(strategy_version, params=params)
            bt_result = engine.run(strategy, data.copy(), symbol=symbol, timeframe=timeframe)
            metrics = calc.calculate(bt_result)

            results.append(OptimizationResult(params=params, metrics=metrics))
        except Exception as e:
            logger.debug("Failed combo %s: %s", params, e)

    # Rank results
    if rank_by == "profit_factor":
        results.sort(key=lambda r: r.metrics.profit_factor if r.metrics else 0, reverse=True)
    else:
        results.sort(key=lambda r: r.metrics.sharpe_ratio if r.metrics else -999, reverse=True)

    for i, r in enumerate(results):
        r.rank = i + 1

    elapsed = time.time() - start_time

    report = OptimizationReport(
        strategy_version=strategy_version,
        symbol=symbol,
        timeframe=timeframe,
        method="grid",
        total_combinations=total,
        elapsed_seconds=elapsed,
        results=results[:top_n],
        best_params=results[0].params if results else {},
        best_metrics=results[0].metrics if results else None,
    )

    logger.info("Grid search complete: %d combos in %.1fs", total, elapsed)
    return report
