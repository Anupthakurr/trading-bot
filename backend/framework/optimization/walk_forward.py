"""
Walk-forward analysis.

Splits historical data into rolling train/validation/test windows,
optimizes on the training set, and evaluates on unseen data to detect
overfitting and validate robustness.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from framework.backtester.engine import BacktestEngine, BacktestResult
from framework.config.settings import Settings, WalkForwardConfig
from framework.metrics.calculator import MetricsCalculator, PerformanceMetrics
from framework.optimization.grid_search import grid_search, OptimizationReport
from framework.strategies.adapter import get_strategy

logger = logging.getLogger(__name__)


@dataclass
class WalkForwardWindow:
    """Results for a single walk-forward window."""
    window_index: int = 0
    train_start: int = 0
    train_end: int = 0
    val_start: int = 0
    val_end: int = 0
    test_start: int = 0
    test_end: int = 0

    best_params: Dict[str, Any] = field(default_factory=dict)
    train_metrics: Optional[PerformanceMetrics] = None
    val_metrics: Optional[PerformanceMetrics] = None
    test_metrics: Optional[PerformanceMetrics] = None


@dataclass
class WalkForwardReport:
    """Complete walk-forward analysis report."""
    strategy_version: str = ""
    symbol: str = ""
    timeframe: str = ""
    n_windows: int = 0
    elapsed_seconds: float = 0.0
    windows: List[WalkForwardWindow] = field(default_factory=list)

    # Aggregate metrics
    avg_train_sharpe: float = 0.0
    avg_val_sharpe: float = 0.0
    avg_test_sharpe: float = 0.0
    overfitting_ratio: float = 0.0  # val_sharpe / train_sharpe

    def summary_table(self) -> str:
        """Format walk-forward results as a table."""
        lines = [
            f"\n{'='*90}",
            f"  WALK-FORWARD ANALYSIS - {self.strategy_version}",
            f"  Symbol: {self.symbol} | Timeframe: {self.timeframe} | Windows: {self.n_windows}",
            f"{'='*90}",
            f"{'Window':<8} {'Train Sharpe':>13} {'Val Sharpe':>13} {'Test Sharpe':>13} {'Overfit':>9}",
            f"{'-'*90}",
        ]

        for w in self.windows:
            ts = w.train_metrics.sharpe_ratio if w.train_metrics else 0
            vs = w.val_metrics.sharpe_ratio if w.val_metrics else 0
            tts = w.test_metrics.sharpe_ratio if w.test_metrics else 0
            of_ratio = vs / ts if ts != 0 else 0
            lines.append(
                f"  #{w.window_index:<5} {ts:>13.2f} {vs:>13.2f} {tts:>13.2f} {of_ratio:>8.2f}x"
            )

        lines.append(f"{'-'*90}")
        lines.append(
            f"  {'AVG':<7} {self.avg_train_sharpe:>13.2f} {self.avg_val_sharpe:>13.2f} "
            f"{self.avg_test_sharpe:>13.2f} {self.overfitting_ratio:>8.2f}x"
        )
        lines.append(f"{'='*90}")

        if self.overfitting_ratio < 0.5:
            lines.append("  [WARNING]: Significant overfitting detected (ratio < 0.5)")
        elif self.overfitting_ratio < 0.7:
            lines.append("  [CAUTION]: Moderate overfitting (ratio 0.5-0.7)")
        else:
            lines.append("  [ROBUST]: Out-of-sample performance holds up well")

        lines.append("")
        return "\n".join(lines)


def walk_forward_analysis(
    strategy_version: str,
    data: pd.DataFrame,
    settings: Settings,
    param_grid: Optional[Dict[str, List[Any]]] = None,
    symbol: str = "",
    timeframe: str = "",
    wf_config: Optional[WalkForwardConfig] = None,
    annualization_factor: float = 252,
) -> WalkForwardReport:
    """
    Perform walk-forward analysis.

    Splits data into rolling windows, optimizes on training data,
    and evaluates on validation and test data.

    Args:
        strategy_version: Strategy version string.
        data: OHLCV DataFrame (full history).
        settings: Framework settings.
        param_grid: Parameter grid for optimization.
        symbol: Symbol for reporting.
        timeframe: Timeframe for reporting.
        wf_config: Walk-forward configuration (splits, n_windows).
        annualization_factor: For metrics.

    Returns:
        WalkForwardReport with per-window and aggregate results.
    """
    start_time = time.time()
    wf = wf_config or settings.walk_forward
    n = len(data)
    n_splits = wf.n_splits

    logger.info(
        "Walk-forward: %d windows | %.0f%% train / %.0f%% val / %.0f%% test | %d bars",
        n_splits, wf.train_pct * 100, wf.validation_pct * 100, wf.test_pct * 100, n,
    )

    # Calculate window sizes for a single split
    window_size = n // n_splits
    train_size = int(window_size * wf.train_pct / (wf.train_pct + wf.validation_pct + wf.test_pct))
    val_size = int(window_size * wf.validation_pct / (wf.train_pct + wf.validation_pct + wf.test_pct))
    test_size = window_size - train_size - val_size

    engine = BacktestEngine(settings)
    calc = MetricsCalculator(annualization_factor=annualization_factor)
    windows: List[WalkForwardWindow] = []

    for i in range(n_splits):
        offset = i * window_size
        train_start = offset
        train_end = offset + train_size
        val_start = train_end
        val_end = val_start + val_size
        test_start = val_end
        test_end = min(test_start + test_size, n)

        if test_end > n or train_end > n:
            logger.warning("Window %d exceeds data length, skipping", i)
            break

        logger.info(
            "Window %d: train[%d:%d] val[%d:%d] test[%d:%d]",
            i, train_start, train_end, val_start, val_end, test_start, test_end,
        )

        train_data = data.iloc[train_start:train_end].copy().reset_index(drop=True)
        val_data = data.iloc[val_start:val_end].copy().reset_index(drop=True)
        test_data = data.iloc[test_start:test_end].copy().reset_index(drop=True)

        # Optimize on training data
        opt_report = grid_search(
            strategy_version=strategy_version,
            data=train_data,
            settings=settings,
            param_grid=param_grid,
            symbol=symbol,
            timeframe=timeframe,
            top_n=1,
            annualization_factor=annualization_factor,
        )
        best_params = opt_report.best_params

        # Run on validation data with best params
        val_strategy = get_strategy(strategy_version, params=best_params)
        val_result = engine.run(val_strategy, val_data, symbol=symbol, timeframe=timeframe)
        val_metrics = calc.calculate(val_result)

        # Run on test data with best params
        test_strategy = get_strategy(strategy_version, params=best_params)
        test_result = engine.run(test_strategy, test_data, symbol=symbol, timeframe=timeframe)
        test_metrics = calc.calculate(test_result)

        window = WalkForwardWindow(
            window_index=i,
            train_start=train_start,
            train_end=train_end,
            val_start=val_start,
            val_end=val_end,
            test_start=test_start,
            test_end=test_end,
            best_params=best_params,
            train_metrics=opt_report.best_metrics,
            val_metrics=val_metrics,
            test_metrics=test_metrics,
        )
        windows.append(window)

    # Aggregate
    train_sharpes = [w.train_metrics.sharpe_ratio for w in windows if w.train_metrics]
    val_sharpes = [w.val_metrics.sharpe_ratio for w in windows if w.val_metrics]
    test_sharpes = [w.test_metrics.sharpe_ratio for w in windows if w.test_metrics]

    avg_train = sum(train_sharpes) / len(train_sharpes) if train_sharpes else 0
    avg_val = sum(val_sharpes) / len(val_sharpes) if val_sharpes else 0
    avg_test = sum(test_sharpes) / len(test_sharpes) if test_sharpes else 0
    overfit_ratio = avg_val / avg_train if avg_train != 0 else 0

    elapsed = time.time() - start_time

    report = WalkForwardReport(
        strategy_version=strategy_version,
        symbol=symbol,
        timeframe=timeframe,
        n_windows=len(windows),
        elapsed_seconds=elapsed,
        windows=windows,
        avg_train_sharpe=avg_train,
        avg_val_sharpe=avg_val,
        avg_test_sharpe=avg_test,
        overfitting_ratio=overfit_ratio,
    )

    logger.info("Walk-forward complete: %d windows in %.1fs", len(windows), elapsed)
    return report
