"""
Random search parameter optimizer.

Randomly samples N parameter combinations from the search space.
Useful when the grid is too large for exhaustive search (>10,000 combinations).
"""

import logging
import random
import time
from typing import Any, Dict, List, Optional

import pandas as pd
from tqdm import tqdm

from framework.backtester.engine import BacktestEngine
from framework.config.settings import Settings
from framework.metrics.calculator import MetricsCalculator
from framework.optimization.grid_search import OptimizationReport, OptimizationResult
from framework.strategies.adapter import get_strategy

logger = logging.getLogger(__name__)


def random_search(
    strategy_version: str,
    data: pd.DataFrame,
    settings: Settings,
    param_grid: Optional[Dict[str, List[Any]]] = None,
    n_iterations: int = 500,
    symbol: str = "",
    timeframe: str = "",
    rank_by: str = "sharpe_ratio",
    top_n: int = 10,
    annualization_factor: float = 252,
    seed: Optional[int] = None,
) -> OptimizationReport:
    """
    Random search over parameter space.

    Randomly samples n_iterations parameter combinations instead of
    testing all possible combinations. Statistically, 500 random samples
    have a 99.5% chance of finding a result in the top 1% of the space.

    Args:
        strategy_version: Strategy version string ('v1'–'v4').
        data: OHLCV DataFrame.
        settings: Framework settings.
        param_grid: Parameter ranges to sample from.
        n_iterations: Number of random samples to test.
        symbol: Symbol string for reporting.
        timeframe: Timeframe string.
        rank_by: Metric to rank by.
        top_n: Number of top results to keep.
        annualization_factor: For metrics computation.
        seed: Random seed for reproducibility.

    Returns:
        OptimizationReport with sampled results.
    """
    start_time = time.time()

    if seed is not None:
        random.seed(seed)

    # Get param grid
    if param_grid is None:
        base_strategy = get_strategy(strategy_version)
        param_grid = base_strategy.get_param_grid()

    if not param_grid:
        raise ValueError(f"No parameter grid for {strategy_version}")

    param_names = list(param_grid.keys())
    param_values = list(param_grid.values())

    # Track tested combinations to avoid duplicates
    tested = set()
    engine = BacktestEngine(settings)
    calc = MetricsCalculator(annualization_factor=annualization_factor)
    results: List[OptimizationResult] = []

    pbar = tqdm(total=n_iterations, desc=f"Random Search ({strategy_version})", unit="run")

    attempts = 0
    max_attempts = n_iterations * 5  # Prevent infinite loops

    while len(results) < n_iterations and attempts < max_attempts:
        attempts += 1

        # Random sample
        combo = tuple(random.choice(vals) for vals in param_values)
        if combo in tested:
            continue
        tested.add(combo)

        params = dict(zip(param_names, combo))

        try:
            strategy = get_strategy(strategy_version, params=params)
            bt_result = engine.run(strategy, data.copy(), symbol=symbol, timeframe=timeframe)
            metrics = calc.calculate(bt_result)
            results.append(OptimizationResult(params=params, metrics=metrics))
            pbar.update(1)
        except Exception as e:
            logger.debug("Failed combo %s: %s", params, e)

    pbar.close()

    # Rank
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
        method="random",
        total_combinations=len(results),
        elapsed_seconds=elapsed,
        results=results[:top_n],
        best_params=results[0].params if results else {},
        best_metrics=results[0].metrics if results else None,
    )

    logger.info("Random search: tested %d combos in %.1fs", len(results), elapsed)
    return report
