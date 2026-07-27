"""
Chart generators for backtest visualization.

Produces 6 chart types using matplotlib:
1. Equity Curve (strategy vs buy-and-hold)
2. Drawdown Curve
3. Price Chart with Buy/Sell markers
4. Trade P&L Distribution histogram
5. Monthly Returns heatmap
6. Performance Summary Dashboard (2×3 grid)

All charts use a dark theme for consistency with the frontend.
"""

import io
import os
import base64
import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker

from framework.backtester.engine import BacktestResult
from framework.metrics.calculator import PerformanceMetrics

logger = logging.getLogger(__name__)

# ── Theme ────────────────────────────────────────────────────
DARK_BG = "#0f172a"
PANEL_BG = "#1e293b"
TEXT_PRIMARY = "#f8fafc"
TEXT_SECONDARY = "#94a3b8"
ACCENT = "#3b82f6"
GREEN = "#10b981"
RED = "#ef4444"
YELLOW = "#f59e0b"
GRID_COLOR = "rgba(255,255,255,0.08)"


def _apply_dark_theme() -> None:
    """Set matplotlib to dark theme matching the frontend."""
    plt.style.use("dark_background")
    plt.rcParams.update({
        "figure.facecolor": DARK_BG,
        "axes.facecolor": PANEL_BG,
        "axes.edgecolor": TEXT_SECONDARY,
        "axes.labelcolor": TEXT_PRIMARY,
        "text.color": TEXT_PRIMARY,
        "xtick.color": TEXT_SECONDARY,
        "ytick.color": TEXT_SECONDARY,
        "grid.color": "#334155",
        "grid.alpha": 0.3,
        "legend.facecolor": PANEL_BG,
        "legend.edgecolor": TEXT_SECONDARY,
        "font.family": "sans-serif",
        "font.size": 10,
    })


def _save_or_encode(fig: plt.Figure, path: Optional[str], dpi: int = 150) -> Optional[str]:
    """Save figure to file and/or return base64 encoded string."""
    b64 = None
    if path:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
        logger.info("Chart saved: %s", path)

    # Always generate base64 for HTML embedding
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    buf.close()

    plt.close(fig)
    return b64


# ═══════════════════════════════════════════════════════════════
# 1. EQUITY CURVE
# ═══════════════════════════════════════════════════════════════

def plot_equity_curve(
    result: BacktestResult,
    save_path: Optional[str] = None,
    dpi: int = 150,
) -> Optional[str]:
    """
    Plot equity curve: strategy vs buy-and-hold.

    Returns:
        Base64-encoded PNG string.
    """
    _apply_dark_theme()
    fig, ax = plt.subplots(figsize=(12, 5))

    x = range(len(result.equity_curve))
    ax.plot(x, result.equity_curve, color=ACCENT, linewidth=2, label="Strategy")

    if result.buy_hold_equity:
        ax.plot(x, result.buy_hold_equity, color=TEXT_SECONDARY, linewidth=1,
                alpha=0.6, linestyle="--", label="Buy & Hold")

    ax.fill_between(x, result.equity_curve, alpha=0.1, color=ACCENT)

    ax.set_title(f"Equity Curve — {result.strategy_name} ({result.symbol})",
                 fontsize=14, fontweight="bold")
    ax.set_xlabel("Bars")
    ax.set_ylabel("Portfolio Value ($)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.2)

    return _save_or_encode(fig, save_path, dpi)


# ═══════════════════════════════════════════════════════════════
# 2. DRAWDOWN CURVE
# ═══════════════════════════════════════════════════════════════

def plot_drawdown(
    metrics: PerformanceMetrics,
    result: BacktestResult,
    save_path: Optional[str] = None,
    dpi: int = 150,
) -> Optional[str]:
    """
    Plot drawdown curve showing percentage drops from peak.
    """
    _apply_dark_theme()
    fig, ax = plt.subplots(figsize=(12, 4))

    dd = metrics.drawdown_curve
    x = range(len(dd))

    ax.fill_between(x, dd, 0, color=RED, alpha=0.3)
    ax.plot(x, dd, color=RED, linewidth=1)

    ax.set_title(f"Drawdown — Max: {metrics.max_drawdown_pct:.2f}%",
                 fontsize=14, fontweight="bold")
    ax.set_xlabel("Bars")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, alpha=0.2)

    return _save_or_encode(fig, save_path, dpi)


# ═══════════════════════════════════════════════════════════════
# 3. PRICE CHART WITH BUY/SELL MARKERS
# ═══════════════════════════════════════════════════════════════

def plot_price_signals(
    result: BacktestResult,
    save_path: Optional[str] = None,
    dpi: int = 150,
) -> Optional[str]:
    """
    Plot price chart with buy (▲) and sell (▼) markers.
    """
    _apply_dark_theme()
    fig, ax = plt.subplots(figsize=(14, 6))

    data = result.data
    if data is None:
        return None

    closes = data["Close"].values
    x = range(len(closes))

    ax.plot(x, closes, color=TEXT_SECONDARY, linewidth=1, alpha=0.8, label="Price")

    # Buy signals
    for sig in result.buy_signals:
        idx = sig["index"]
        if idx < len(closes):
            ax.scatter(idx, closes[idx], marker="^", color=GREEN, s=80,
                      zorder=5, edgecolors="white", linewidth=0.5)

    # Sell signals
    for sig in result.sell_signals:
        idx = sig["index"]
        if idx < len(closes):
            ax.scatter(idx, closes[idx], marker="v", color=RED, s=80,
                      zorder=5, edgecolors="white", linewidth=0.5)

    # Add SMAs/EMAs if available
    for col, color, lbl in [
        ("SMA_short", ACCENT, "Short MA"), ("SMA_long", YELLOW, "Long MA"),
        ("EMA_fast", ACCENT, "Fast EMA"), ("EMA_slow", YELLOW, "Slow EMA"),
    ]:
        if col in data.columns:
            ax.plot(x, data[col].values, color=color, linewidth=1, alpha=0.7, label=lbl)

    ax.set_title(f"Price & Signals — {result.symbol} ({result.strategy_name})",
                 fontsize=14, fontweight="bold")
    ax.set_xlabel("Bars")
    ax.set_ylabel("Price")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.2)

    return _save_or_encode(fig, save_path, dpi)


# ═══════════════════════════════════════════════════════════════
# 4. TRADE P&L DISTRIBUTION
# ═══════════════════════════════════════════════════════════════

def plot_trade_distribution(
    result: BacktestResult,
    save_path: Optional[str] = None,
    dpi: int = 150,
) -> Optional[str]:
    """
    Plot histogram of trade P&L values.
    """
    _apply_dark_theme()
    fig, ax = plt.subplots(figsize=(10, 5))

    if not result.trades:
        ax.text(0.5, 0.5, "No trades", ha="center", va="center",
                fontsize=16, color=TEXT_SECONDARY, transform=ax.transAxes)
        return _save_or_encode(fig, save_path, dpi)

    pnls = [t.pnl for t in result.trades]
    colors = [GREEN if p > 0 else RED for p in pnls]

    n_bins = min(30, max(5, len(pnls) // 3))
    n, bins, patches = ax.hist(pnls, bins=n_bins, edgecolor=DARK_BG, linewidth=0.5)

    # Color bars based on profit/loss
    for patch, left_edge in zip(patches, bins):
        if left_edge >= 0:
            patch.set_facecolor(GREEN)
            patch.set_alpha(0.7)
        else:
            patch.set_facecolor(RED)
            patch.set_alpha(0.7)

    ax.axvline(0, color=TEXT_SECONDARY, linewidth=1, linestyle="--", alpha=0.5)
    avg_pnl = np.mean(pnls)
    ax.axvline(avg_pnl, color=ACCENT, linewidth=2, linestyle="-", alpha=0.8,
               label=f"Mean: ${avg_pnl:,.2f}")

    ax.set_title("Trade P&L Distribution", fontsize=14, fontweight="bold")
    ax.set_xlabel("P&L ($)")
    ax.set_ylabel("Frequency")
    ax.legend()
    ax.grid(True, alpha=0.2)

    return _save_or_encode(fig, save_path, dpi)


# ═══════════════════════════════════════════════════════════════
# 5. MONTHLY RETURNS HEATMAP
# ═══════════════════════════════════════════════════════════════

def plot_monthly_returns(
    result: BacktestResult,
    save_path: Optional[str] = None,
    dpi: int = 150,
) -> Optional[str]:
    """
    Plot monthly returns as a heatmap (year × month).
    """
    _apply_dark_theme()

    # Build monthly returns from equity curve
    equity = pd.Series(result.equity_curve)
    data = result.data

    if data is None or len(equity) == 0:
        return None

    # Try to parse dates
    try:
        dates = pd.to_datetime(data["Date"])
    except Exception:
        logger.warning("Cannot parse dates for monthly returns heatmap")
        return None

    df = pd.DataFrame({"equity": equity.values[:len(dates)], "date": dates.values[:len(dates)]})
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)

    # Monthly equity (last value per month)
    monthly = df["equity"].resample("ME").last()
    monthly_returns = monthly.pct_change().fillna(0) * 100

    # Pivot to year × month
    mr_df = pd.DataFrame({
        "year": monthly_returns.index.year,
        "month": monthly_returns.index.month,
        "return": monthly_returns.values,
    })
    pivot = mr_df.pivot_table(values="return", index="year", columns="month", aggfunc="sum")
    pivot.columns = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][:len(pivot.columns)]

    fig, ax = plt.subplots(figsize=(12, max(3, len(pivot) * 0.8)))

    # Custom colormap (red → white → green)
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("rg", [RED, PANEL_BG, GREEN])

    vmax = max(abs(pivot.values.min()), abs(pivot.values.max()), 5)
    im = ax.imshow(pivot.values, cmap=cmap, aspect="auto", vmin=-vmax, vmax=vmax)

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, fontsize=9)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=9)

    # Annotate cells
    for y in range(len(pivot.index)):
        for x in range(len(pivot.columns)):
            val = pivot.values[y, x]
            if not np.isnan(val):
                color = "white" if abs(val) > vmax * 0.5 else TEXT_PRIMARY
                ax.text(x, y, f"{val:.1f}%", ha="center", va="center",
                        fontsize=8, color=color, fontweight="bold")

    ax.set_title("Monthly Returns (%)", fontsize=14, fontweight="bold")
    fig.colorbar(im, ax=ax, label="Return %", shrink=0.8)

    return _save_or_encode(fig, save_path, dpi)


# ═══════════════════════════════════════════════════════════════
# 6. PERFORMANCE DASHBOARD (2×3 grid)
# ═══════════════════════════════════════════════════════════════

def plot_dashboard(
    result: BacktestResult,
    metrics: PerformanceMetrics,
    save_path: Optional[str] = None,
    dpi: int = 150,
) -> Optional[str]:
    """
    Generate a comprehensive 2×3 dashboard combining all charts.
    """
    _apply_dark_theme()
    fig, axes = plt.subplots(2, 3, figsize=(20, 12))
    fig.suptitle(
        f"QuantEngine — {result.strategy_name} | {result.symbol} | {result.timeframe}",
        fontsize=16, fontweight="bold", y=0.98,
    )

    # ── 1. Equity Curve (top-left) ───────────────────────────
    ax = axes[0, 0]
    x = range(len(result.equity_curve))
    ax.plot(x, result.equity_curve, color=ACCENT, linewidth=1.5, label="Strategy")
    if result.buy_hold_equity:
        ax.plot(x, result.buy_hold_equity, color=TEXT_SECONDARY,
                linewidth=1, alpha=0.5, linestyle="--", label="B&H")
    ax.fill_between(x, result.equity_curve, alpha=0.08, color=ACCENT)
    ax.set_title("Equity Curve", fontsize=11, fontweight="bold")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v/1000:.0f}k"))
    ax.legend(fontsize=7)
    ax.grid(True, alpha=0.2)

    # ── 2. Drawdown (top-center) ─────────────────────────────
    ax = axes[0, 1]
    dd = metrics.drawdown_curve
    ax.fill_between(range(len(dd)), dd, 0, color=RED, alpha=0.3)
    ax.plot(range(len(dd)), dd, color=RED, linewidth=1)
    ax.set_title(f"Drawdown (Max: {metrics.max_drawdown_pct:.2f}%)",
                 fontsize=11, fontweight="bold")
    ax.set_ylabel("%")
    ax.grid(True, alpha=0.2)

    # ── 3. Metrics Summary (top-right) ───────────────────────
    ax = axes[0, 2]
    ax.axis("off")
    metrics_text = [
        f"Total Return:    {metrics.total_return_pct:>8.2f}%",
        f"Annual Return:   {metrics.annualized_return_pct:>8.2f}%",
        f"Sharpe Ratio:    {metrics.sharpe_ratio:>8.2f}",
        f"Sortino Ratio:   {metrics.sortino_ratio:>8.2f}",
        f"Max Drawdown:    {metrics.max_drawdown_pct:>8.2f}%",
        f"Calmar Ratio:    {metrics.calmar_ratio:>8.2f}",
        f"Win Rate:        {metrics.win_rate_pct:>8.2f}%",
        f"Profit Factor:   {metrics.profit_factor:>8.2f}",
        f"Trades:          {metrics.num_trades:>8d}",
        f"Expectancy:     ${metrics.expectancy:>8.2f}",
    ]
    ax.text(0.1, 0.95, "PERFORMANCE METRICS", fontsize=12,
            fontweight="bold", transform=ax.transAxes, va="top")
    for idx, line in enumerate(metrics_text):
        ax.text(0.1, 0.85 - idx * 0.085, line, fontsize=9,
                fontfamily="monospace", transform=ax.transAxes, va="top")

    # ── 4. Price with Signals (bottom-left) ──────────────────
    ax = axes[1, 0]
    if result.data is not None:
        closes = result.data["Close"].values
        ax.plot(range(len(closes)), closes, color=TEXT_SECONDARY, linewidth=0.8)
        for sig in result.buy_signals:
            if sig["index"] < len(closes):
                ax.scatter(sig["index"], closes[sig["index"]], marker="^",
                          color=GREEN, s=30, zorder=5)
        for sig in result.sell_signals:
            if sig["index"] < len(closes):
                ax.scatter(sig["index"], closes[sig["index"]], marker="v",
                          color=RED, s=30, zorder=5)
    ax.set_title("Price & Signals", fontsize=11, fontweight="bold")
    ax.grid(True, alpha=0.2)

    # ── 5. Trade Distribution (bottom-center) ────────────────
    ax = axes[1, 1]
    if result.trades:
        pnls = [t.pnl for t in result.trades]
        n_bins = min(20, max(5, len(pnls) // 3))
        n, bins, patches = ax.hist(pnls, bins=n_bins, edgecolor=DARK_BG, linewidth=0.5)
        for patch, left_edge in zip(patches, bins):
            patch.set_facecolor(GREEN if left_edge >= 0 else RED)
            patch.set_alpha(0.7)
        ax.axvline(0, color=TEXT_SECONDARY, linewidth=1, linestyle="--", alpha=0.5)
    ax.set_title("Trade Distribution", fontsize=11, fontweight="bold")
    ax.set_xlabel("P&L ($)")
    ax.grid(True, alpha=0.2)

    # ── 6. Win/Loss breakdown (bottom-right) ─────────────────
    ax = axes[1, 2]
    if metrics.num_trades > 0:
        sizes = [metrics.winning_trades, metrics.losing_trades]
        labels = [f"Wins ({metrics.winning_trades})", f"Losses ({metrics.losing_trades})"]
        colors_pie = [GREEN, RED]
        wedges, texts, autotexts = ax.pie(
            sizes, labels=labels, colors=colors_pie, autopct="%1.1f%%",
            startangle=90, textprops={"color": TEXT_PRIMARY, "fontsize": 9},
        )
        for at in autotexts:
            at.set_fontweight("bold")
    else:
        ax.text(0.5, 0.5, "No trades", ha="center", va="center",
                fontsize=14, color=TEXT_SECONDARY, transform=ax.transAxes)
    ax.set_title("Win / Loss", fontsize=11, fontweight="bold")

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    return _save_or_encode(fig, save_path, dpi)


# ═══════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTION — Generate All Charts
# ═══════════════════════════════════════════════════════════════

def generate_all_charts(
    result: BacktestResult,
    metrics: PerformanceMetrics,
    output_dir: str,
    dpi: int = 150,
) -> Dict[str, str]:
    """
    Generate all 6 charts and return their base64 strings.

    Args:
        result: Backtest result.
        metrics: Computed performance metrics.
        output_dir: Directory to save PNG files.
        dpi: Chart resolution.

    Returns:
        Dict mapping chart name -> base64-encoded PNG.
    """
    charts = {}
    prefix = f"{result.symbol}_{result.strategy_name.replace(' ', '_')}"

    charts["equity_curve"] = plot_equity_curve(
        result, os.path.join(output_dir, f"{prefix}_equity.png"), dpi
    )
    charts["drawdown"] = plot_drawdown(
        metrics, result, os.path.join(output_dir, f"{prefix}_drawdown.png"), dpi
    )
    charts["price_signals"] = plot_price_signals(
        result, os.path.join(output_dir, f"{prefix}_signals.png"), dpi
    )
    charts["trade_distribution"] = plot_trade_distribution(
        result, os.path.join(output_dir, f"{prefix}_trades.png"), dpi
    )
    charts["monthly_returns"] = plot_monthly_returns(
        result, os.path.join(output_dir, f"{prefix}_monthly.png"), dpi
    )
    charts["dashboard"] = plot_dashboard(
        result, metrics, os.path.join(output_dir, f"{prefix}_dashboard.png"), dpi
    )

    logger.info("Generated %d charts in %s", len(charts), output_dir)
    return charts
