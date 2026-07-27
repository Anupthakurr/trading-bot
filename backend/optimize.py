#!/usr/bin/env python3
"""
CLI tool: Run parameter optimization.

Usage:
    python optimize.py --symbol AAPL --timeframe 1D --strategy v4 --method grid
    python optimize.py --symbol BTCUSDT --strategy v3 --method random --iterations 500
    python optimize.py --symbol SPY --strategy v4 --method walk-forward
"""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from framework.config.settings import load_settings
from framework.data.provider import YFinanceProvider
from framework.data.cache import DataCache
from framework.data.timeframes import Timeframe
from framework.optimization.grid_search import grid_search
from framework.optimization.random_search import random_search
from framework.optimization.walk_forward import walk_forward_analysis
from framework.robustness.sensitivity import sensitivity_analysis

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="QuantEngine — Parameter Optimization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--symbol", "-s", type=str, default="AAPL",
                        help="Asset symbol")
    parser.add_argument("--timeframe", "-tf", type=str, default=None,
                        help="Timeframe: 5m, 15m, 1h, 4h, 1D")
    parser.add_argument("--strategy", "-st", type=str, default="v3",
                        help="Strategy version: v1, v2, v3, v4")
    parser.add_argument("--method", "-m", type=str, default="grid",
                        choices=["grid", "random", "walk-forward"],
                        help="Optimization method")
    parser.add_argument("--iterations", "-n", type=int, default=None,
                        help="Iterations for random search")
    parser.add_argument("--start", type=str, default=None, help="Start date")
    parser.add_argument("--end", type=str, default=None, help="End date")
    parser.add_argument("--top", type=int, default=10,
                        help="Number of top results to show")
    parser.add_argument("--sensitivity", action="store_true",
                        help="Run sensitivity analysis on best params")
    parser.add_argument("--config", type=str, default=None, help="Config file path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_settings(config_path=args.config)

    symbol = args.symbol.strip()
    timeframe_str = args.timeframe or settings.data.default_timeframe
    timeframe = Timeframe.from_string(timeframe_str)
    start = args.start or settings.data.default_start
    end = args.end or settings.data.default_end
    strategy_version = args.strategy.lower().strip()

    print(f"\n{'='*60}")
    print(f"  QuantEngine Optimization")
    print(f"  Symbol    : {symbol}")
    print(f"  Timeframe : {timeframe.display_name}")
    print(f"  Strategy  : {strategy_version}")
    print(f"  Method    : {args.method}")
    print(f"  Period    : {start} -> {end}")
    print(f"{'='*60}\n")

    # Fetch data
    cache = DataCache(cache_dir=settings.data_cache_dir, ttl_hours=settings.data.cache_ttl_hours)
    provider = YFinanceProvider(cache=cache)
    data = provider.fetch(symbol, timeframe, start, end)
    print(f"  Data: {len(data)} bars loaded\n")

    # Get param grid from config or strategy defaults
    param_grid = settings.optimization.param_grids.get(strategy_version, None)

    ann_factor = timeframe.annualization_factor

    if args.method == "grid":
        report = grid_search(
            strategy_version=strategy_version,
            data=data,
            settings=settings,
            param_grid=param_grid,
            symbol=symbol,
            timeframe=timeframe_str,
            rank_by=settings.optimization.rank_by,
            top_n=args.top,
            annualization_factor=ann_factor,
        )
        print(report.summary_table(top_n=args.top))

    elif args.method == "random":
        n_iter = args.iterations or settings.optimization.random_iterations
        report = random_search(
            strategy_version=strategy_version,
            data=data,
            settings=settings,
            param_grid=param_grid,
            n_iterations=n_iter,
            symbol=symbol,
            timeframe=timeframe_str,
            rank_by=settings.optimization.rank_by,
            top_n=args.top,
            annualization_factor=ann_factor,
        )
        print(report.summary_table(top_n=args.top))

    elif args.method == "walk-forward":
        wf_report = walk_forward_analysis(
            strategy_version=strategy_version,
            data=data,
            settings=settings,
            param_grid=param_grid,
            symbol=symbol,
            timeframe=timeframe_str,
            annualization_factor=ann_factor,
        )
        print(wf_report.summary_table())
        report = type('Report', (), {'best_params': {}, 'best_metrics': None})()
        if wf_report.windows:
            report.best_params = wf_report.windows[0].best_params
            report.best_metrics = wf_report.windows[0].train_metrics
    else:
        print(f"Unknown method: {args.method}")
        return

    # Sensitivity analysis on best params
    if args.sensitivity and hasattr(report, 'best_params') and report.best_params:
        print("\n  Running sensitivity analysis on best parameters...")
        sens = sensitivity_analysis(
            strategy_version=strategy_version,
            data=data,
            settings=settings,
            base_params=report.best_params,
            variation_pct=settings.robustness.sensitivity_variation_pct,
            symbol=symbol,
            timeframe=timeframe_str,
            annualization_factor=ann_factor,
        )
        print(sens.summary_table())

    print(f"\n{'='*60}")
    print(f"  Optimization complete!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
