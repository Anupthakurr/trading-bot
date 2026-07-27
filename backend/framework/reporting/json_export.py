"""
JSON export — summary metrics and configuration.

Exports a JSON file with all metrics, parameters, and top-level results.
"""

import json
import os
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from framework.backtester.engine import BacktestResult
from framework.metrics.calculator import PerformanceMetrics

logger = logging.getLogger(__name__)


def export_json_summary(
    result: BacktestResult,
    metrics: PerformanceMetrics,
    output_path: str,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Export a JSON summary of the backtest.

    Includes all metrics, strategy parameters, and metadata.

    Args:
        result: Backtest result.
        metrics: Computed performance metrics.
        output_path: Full path for the JSON file.
        extra: Optional additional data to include.

    Returns:
        Path to the saved file.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    summary = {
        "generated_at": datetime.now().isoformat(),
        "framework_version": "1.0.0",
        "backtest": {
            "strategy": result.strategy_name,
            "version": result.strategy_version,
            "symbol": result.symbol,
            "timeframe": result.timeframe,
            "start_date": result.start_date,
            "end_date": result.end_date,
            "initial_capital": result.initial_capital,
            "final_equity": round(result.final_equity, 2),
            "execution_time_seconds": round(result.execution_time_seconds, 2),
        },
        "parameters": result.strategy_params,
        "metrics": metrics.to_dict(),
        "trade_summary": {
            "total_trades": metrics.num_trades,
            "winners": metrics.winning_trades,
            "losers": metrics.losing_trades,
            "total_commission": round(metrics.total_commission, 2),
        },
    }

    if extra:
        summary["extra"] = extra

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    logger.info("Exported JSON summary to %s", output_path)
    return output_path
