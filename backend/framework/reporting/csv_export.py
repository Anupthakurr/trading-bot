"""
CSV export — trade history and equity curve.

Exports trade log as a CSV file importable into Excel, Google Sheets, etc.
"""

import os
import logging
from typing import List, Optional

import pandas as pd

from framework.backtester.engine import BacktestResult
from framework.backtester.order import Trade

logger = logging.getLogger(__name__)


def export_trades_csv(
    trades: List[Trade],
    output_path: str,
) -> str:
    """
    Export trade history to CSV.

    Columns: entry_date, exit_date, quantity, entry_price, exit_price,
             pnl, return_pct, commission, holding_bars, exit_reason, winner

    Args:
        trades: List of completed trades.
        output_path: Full path for the CSV file.

    Returns:
        Path to the saved file.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    rows = [t.to_dict() for t in trades]
    df = pd.DataFrame(rows)

    if df.empty:
        df = pd.DataFrame(columns=[
            "entry_date", "exit_date", "quantity", "entry_price",
            "exit_price", "pnl", "return_pct", "commission",
            "holding_bars", "exit_reason", "winner",
        ])

    df.to_csv(output_path, index=False)
    logger.info("Exported %d trades to %s", len(trades), output_path)
    return output_path


def export_equity_csv(
    result: BacktestResult,
    output_path: str,
) -> str:
    """
    Export equity curve to CSV.

    Args:
        result: Backtest result with equity curve.
        output_path: Full path for the CSV file.

    Returns:
        Path to the saved file.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    data = {"equity": result.equity_curve}
    if result.buy_hold_equity:
        data["buy_hold"] = result.buy_hold_equity

    if result.data is not None and "Date" in result.data.columns:
        dates = result.data["Date"].values[:len(result.equity_curve)]
        data["date"] = dates

    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False)
    logger.info("Exported equity curve to %s", output_path)
    return output_path
