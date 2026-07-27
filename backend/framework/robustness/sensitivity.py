"""
Parameter sensitivity analysis.

Varies each parameter ±N% around the optimal value and measures
how much key metrics (Sharpe Ratio) change. Identifies fragile
parameters that cause large performance swings.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd
from tqdm import tqdm

from framework.backtester.engine import BacktestEngine
from framework.config.settings import Settings
from framework.metrics.calculator import MetricsCalculator
from framework.strategies.adapter import get_strategy

logger = logging.getLogger(__name__)


@dataclass
class SensitivityResult:
    """Sensitivity result for a single parameter."""
    param_name: str = ""
    base_value: Any = None
    test_values: List[Any] = field(default_factory=list)
    sharpe_ratios: List[float] = field(default_factory=list)
    profit_factors: List[float] = field(default_factory=list)
    returns: List[float] = field(default_factory=list)
    base_sharpe: float = 0.0
    max_sharpe_change_pct: float = 0.0
    is_fragile: bool = False  # >30% change = fragile


@dataclass
class SensitivityReport:
    """Complete sensitivity analysis report."""
    strategy_version: str = ""
    symbol: str = ""
    base_params: Dict[str, Any] = field(default_factory=dict)
    variation_pct: float = 0.20
    results: List[SensitivityResult] = field(default_factory=list)
    fragile_params: List[str] = field(default_factory=list)

    def summary_table(self) -> str:
        """Format sensitivity results as a table."""
        lines = [
            f"\n{'='*75}",
            f"  SENSITIVITY ANALYSIS - +/-{self.variation_pct*100:.0f}% parameter variation",
            f"  Strategy: {self.strategy_version} | Symbol: {self.symbol}",
            f"{'='*75}",
            f"{'Parameter':<20} {'Base Value':>12} {'Base Sharpe':>12} {'Max Chg%':>10} {'Status':>10}",
            f"{'-'*75}",
        ]
        for r in self.results:
            status = "[FRAGILE]" if r.is_fragile else "[STABLE]"
            lines.append(
                f"  {r.param_name:<18} {str(r.base_value):>12} "
                f"{r.base_sharpe:>12.2f} {r.max_sharpe_change_pct:>9.1f}% {status:>10}"
            )
        lines.append(f"{'='*75}")

        if self.fragile_params:
            lines.append(f"\n  [WARNING] Fragile parameters: {', '.join(self.fragile_params)}")
            lines.append("     These cause >30% Sharpe change with +/-20% variation.")
        else:
            lines.append("\n  [STABLE] All parameters are stable.")

        lines.append("")
        return "\n".join(lines)


def sensitivity_analysis(
    strategy_version: str,
    data: pd.DataFrame,
    settings: Settings,
    base_params: Dict[str, Any],
    variation_pct: float = 0.20,
    symbol: str = "",
    timeframe: str = "",
    annualization_factor: float = 252,
) -> SensitivityReport:
    """
    Perform sensitivity analysis on strategy parameters.

    For each parameter, varies it ±variation_pct around the base value
    while holding all other parameters fixed. Measures how much the
    Sharpe Ratio changes.

    Args:
        strategy_version: Strategy version string.
        data: OHLCV DataFrame.
        settings: Framework settings.
        base_params: Optimal parameter set to test around.
        variation_pct: Fraction to vary each parameter (e.g., 0.20 = ±20%).
        symbol: Symbol for reporting.
        timeframe: Timeframe for reporting.
        annualization_factor: For metrics.

    Returns:
        SensitivityReport with per-parameter results and fragile flags.
    """
    engine = BacktestEngine(settings)
    calc = MetricsCalculator(annualization_factor=annualization_factor)

    # First, run baseline
    base_strategy = get_strategy(strategy_version, params=base_params)
    base_result = engine.run(base_strategy, data.copy(), symbol=symbol, timeframe=timeframe)
    base_metrics = calc.calculate(base_result)
    base_sharpe = base_metrics.sharpe_ratio

    logger.info("Sensitivity baseline: Sharpe=%.2f", base_sharpe)

    results: List[SensitivityResult] = []
    fragile_params: List[str] = []

    for param_name, base_value in tqdm(base_params.items(), desc="Sensitivity Analysis"):
        # Skip non-numeric parameters
        if not isinstance(base_value, (int, float)):
            continue

        # Generate test values (5 points: -20%, -10%, base, +10%, +20%)
        variations = [-variation_pct, -variation_pct / 2, 0, variation_pct / 2, variation_pct]
        test_values = []

        for v in variations:
            if isinstance(base_value, int):
                new_val = max(1, int(base_value * (1 + v)))
            else:
                new_val = round(base_value * (1 + v), 6)
            test_values.append(new_val)

        # Remove duplicates while preserving order
        seen = set()
        unique_values = []
        for tv in test_values:
            if tv not in seen:
                seen.add(tv)
                unique_values.append(tv)
        test_values = unique_values

        sharpes = []
        pfs = []
        rets = []

        for test_val in test_values:
            test_params = base_params.copy()
            test_params[param_name] = test_val

            try:
                strategy = get_strategy(strategy_version, params=test_params)
                bt_result = engine.run(strategy, data.copy(), symbol=symbol, timeframe=timeframe)
                metrics = calc.calculate(bt_result)
                sharpes.append(metrics.sharpe_ratio)
                pfs.append(metrics.profit_factor)
                rets.append(metrics.total_return_pct)
            except Exception as e:
                logger.debug("Sensitivity test failed for %s=%s: %s", param_name, test_val, e)
                sharpes.append(0)
                pfs.append(0)
                rets.append(0)

        # Calculate max change
        if base_sharpe != 0:
            max_change_pct = max(
                abs((s - base_sharpe) / base_sharpe) * 100
                for s in sharpes
            ) if sharpes else 0
        else:
            max_change_pct = 0

        is_fragile = max_change_pct > 30

        sr = SensitivityResult(
            param_name=param_name,
            base_value=base_value,
            test_values=test_values,
            sharpe_ratios=sharpes,
            profit_factors=pfs,
            returns=rets,
            base_sharpe=base_sharpe,
            max_sharpe_change_pct=max_change_pct,
            is_fragile=is_fragile,
        )
        results.append(sr)

        if is_fragile:
            fragile_params.append(param_name)

    report = SensitivityReport(
        strategy_version=strategy_version,
        symbol=symbol,
        base_params=base_params,
        variation_pct=variation_pct,
        results=results,
        fragile_params=fragile_params,
    )

    logger.info(
        "Sensitivity done: %d params tested, %d fragile",
        len(results), len(fragile_params),
    )
    return report
