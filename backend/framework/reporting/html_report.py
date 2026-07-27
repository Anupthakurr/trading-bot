"""
HTML report generator.

Creates a self-contained HTML report with embedded base64 charts,
metrics tables, trade list, and conclusions. Uses Jinja2 templates.
"""

import os
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from framework.backtester.engine import BacktestResult
from framework.backtester.order import Trade
from framework.metrics.calculator import PerformanceMetrics

logger = logging.getLogger(__name__)


# ── HTML Template ────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QuantEngine Report — {{ symbol }} {{ strategy_name }}</title>
    <style>
        :root {
            --bg: #0f172a; --panel: #1e293b; --border: rgba(255,255,255,0.08);
            --text: #f8fafc; --text2: #94a3b8; --accent: #3b82f6;
            --green: #10b981; --red: #ef4444; --yellow: #f59e0b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Inter', -apple-system, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }
        .container { max-width: 1200px; margin: 0 auto; padding: 40px 24px; }
        .header { text-align: center; margin-bottom: 40px; }
        .header h1 { font-size: 2.5rem; background: linear-gradient(135deg, #fff, #94a3b8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .header p { color: var(--text2); font-size: 1.1rem; margin-top: 8px; }
        .badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; margin: 4px; }
        .badge-blue { background: rgba(59,130,246,0.15); color: var(--accent); border: 1px solid rgba(59,130,246,0.3); }
        .badge-green { background: rgba(16,185,129,0.15); color: var(--green); border: 1px solid rgba(16,185,129,0.3); }
        .badge-red { background: rgba(239,68,68,0.15); color: var(--red); border: 1px solid rgba(239,68,68,0.3); }
        .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 16px; padding: 24px; margin-bottom: 24px; box-shadow: 0 4px 16px rgba(0,0,0,0.2); }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .grid-4 { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .metric-card { padding: 16px; }
        .metric-card .label { color: var(--text2); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
        .metric-card .value { font-size: 1.5rem; font-weight: 700; }
        .positive { color: var(--green); }
        .negative { color: var(--red); }
        table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--border); }
        th { color: var(--text2); font-weight: 600; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.05em; }
        tr:hover { background: rgba(255,255,255,0.03); }
        .chart-img { width: 100%; border-radius: 8px; margin-top: 16px; }
        .section-title { font-size: 1.3rem; font-weight: 700; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid var(--accent); }
        .conclusion { padding: 20px; border-radius: 12px; margin-top: 24px; }
        .conclusion-good { background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.3); }
        .conclusion-bad { background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); }
        .conclusion-neutral { background: rgba(245,158,11,0.1); border: 1px solid rgba(245,158,11,0.3); }
        .footer { text-align: center; color: var(--text2); font-size: 0.8rem; margin-top: 40px; padding-top: 20px; border-top: 1px solid var(--border); }
        @media (max-width: 768px) { .grid-2 { grid-template-columns: 1fr; } .grid-4 { grid-template-columns: 1fr 1fr; } }
        .trade-table-container { max-height: 400px; overflow-y: auto; }
    </style>
</head>
<body>
<div class="container">

    <!-- Header -->
    <div class="header">
        <h1>QuantEngine Report</h1>
        <p>{{ strategy_name }} — {{ symbol }} ({{ timeframe }})</p>
        <div style="margin-top: 12px;">
            <span class="badge badge-blue">{{ start_date }} → {{ end_date }}</span>
            <span class="badge badge-blue">v{{ strategy_version }}</span>
            <span class="badge {{ 'badge-green' if total_return >= 0 else 'badge-red' }}">
                {{ "%.2f"|format(total_return) }}% Return
            </span>
        </div>
    </div>

    <!-- Metrics Cards -->
    <div class="grid-4">
        <div class="panel metric-card">
            <div class="label">Total Return</div>
            <div class="value {{ 'positive' if total_return >= 0 else 'negative' }}">{{ "%.2f"|format(total_return) }}%</div>
        </div>
        <div class="panel metric-card">
            <div class="label">Sharpe Ratio</div>
            <div class="value {{ 'positive' if sharpe > 1 else 'negative' }}">{{ "%.2f"|format(sharpe) }}</div>
        </div>
        <div class="panel metric-card">
            <div class="label">Max Drawdown</div>
            <div class="value negative">{{ "%.2f"|format(max_dd) }}%</div>
        </div>
        <div class="panel metric-card">
            <div class="label">Win Rate</div>
            <div class="value {{ 'positive' if win_rate > 50 else 'negative' }}">{{ "%.1f"|format(win_rate) }}%</div>
        </div>
    </div>

    <!-- Full Metrics Table -->
    <div class="panel">
        <div class="section-title">Performance Metrics</div>
        <div class="grid-2">
            <table>
                <tr><th colspan="2">Returns</th></tr>
                <tr><td>Initial Capital</td><td>${{ "{:,.2f}".format(initial_capital) }}</td></tr>
                <tr><td>Final Equity</td><td>${{ "{:,.2f}".format(final_equity) }}</td></tr>
                <tr><td>Total Return</td><td>{{ "%.2f"|format(total_return) }}%</td></tr>
                <tr><td>Annualized Return</td><td>{{ "%.2f"|format(annual_return) }}%</td></tr>
                <tr><td>Buy & Hold Return</td><td>{{ "%.2f"|format(bh_return) }}%</td></tr>
                <tr><th colspan="2">Risk</th></tr>
                <tr><td>Sharpe Ratio</td><td>{{ "%.2f"|format(sharpe) }}</td></tr>
                <tr><td>Sortino Ratio</td><td>{{ "%.2f"|format(sortino) }}</td></tr>
                <tr><td>Max Drawdown</td><td>{{ "%.2f"|format(max_dd) }}%</td></tr>
                <tr><td>Calmar Ratio</td><td>{{ "%.2f"|format(calmar) }}</td></tr>
            </table>
            <table>
                <tr><th colspan="2">Trades</th></tr>
                <tr><td>Total Trades</td><td>{{ num_trades }}</td></tr>
                <tr><td>Winners / Losers</td><td>{{ winners }} / {{ losers }}</td></tr>
                <tr><td>Win Rate</td><td>{{ "%.1f"|format(win_rate) }}%</td></tr>
                <tr><td>Avg Profit</td><td>${{ "{:,.2f}".format(avg_profit) }}</td></tr>
                <tr><td>Avg Loss</td><td>${{ "{:,.2f}".format(avg_loss) }}</td></tr>
                <tr><td>Profit Factor</td><td>{{ "%.2f"|format(profit_factor) }}</td></tr>
                <tr><td>Expectancy</td><td>${{ "{:,.2f}".format(expectancy) }}</td></tr>
                <tr><td>Avg Holding Time</td><td>{{ avg_holding }}</td></tr>
                <tr><td>Total Commission</td><td>${{ "{:,.2f}".format(total_commission) }}</td></tr>
            </table>
        </div>
    </div>

    <!-- Parameters -->
    <div class="panel">
        <div class="section-title">Strategy Parameters</div>
        <table>
            <tr><th>Parameter</th><th>Value</th></tr>
            {% for key, value in params.items() %}
            <tr><td>{{ key }}</td><td>{{ value }}</td></tr>
            {% endfor %}
        </table>
    </div>

    <!-- Charts -->
    {% if dashboard_chart %}
    <div class="panel">
        <div class="section-title">Performance Dashboard</div>
        <img src="data:image/png;base64,{{ dashboard_chart }}" class="chart-img" alt="Dashboard">
    </div>
    {% endif %}

    {% if equity_chart %}
    <div class="panel">
        <div class="section-title">Equity Curve</div>
        <img src="data:image/png;base64,{{ equity_chart }}" class="chart-img" alt="Equity Curve">
    </div>
    {% endif %}

    {% if drawdown_chart %}
    <div class="panel">
        <div class="section-title">Drawdown</div>
        <img src="data:image/png;base64,{{ drawdown_chart }}" class="chart-img" alt="Drawdown">
    </div>
    {% endif %}

    {% if signals_chart %}
    <div class="panel">
        <div class="section-title">Price & Signals</div>
        <img src="data:image/png;base64,{{ signals_chart }}" class="chart-img" alt="Price Signals">
    </div>
    {% endif %}

    <div class="grid-2">
        {% if trades_chart %}
        <div class="panel">
            <div class="section-title">Trade Distribution</div>
            <img src="data:image/png;base64,{{ trades_chart }}" class="chart-img" alt="Trade Distribution">
        </div>
        {% endif %}
        {% if monthly_chart %}
        <div class="panel">
            <div class="section-title">Monthly Returns</div>
            <img src="data:image/png;base64,{{ monthly_chart }}" class="chart-img" alt="Monthly Returns">
        </div>
        {% endif %}
    </div>

    <!-- Trade List -->
    <div class="panel">
        <div class="section-title">Trade History ({{ num_trades }} trades)</div>
        <div class="trade-table-container">
            <table>
                <tr>
                    <th>#</th><th>Entry Date</th><th>Exit Date</th>
                    <th>Qty</th><th>Entry</th><th>Exit</th>
                    <th>P&L</th><th>Return%</th><th>Bars</th><th>Reason</th>
                </tr>
                {% for trade in trades %}
                <tr>
                    <td>{{ loop.index }}</td>
                    <td>{{ trade.entry_date }}</td>
                    <td>{{ trade.exit_date }}</td>
                    <td>{{ trade.quantity }}</td>
                    <td>${{ "%.2f"|format(trade.entry_price) }}</td>
                    <td>${{ "%.2f"|format(trade.exit_price) }}</td>
                    <td class="{{ 'positive' if trade.pnl > 0 else 'negative' }}">${{ "%.2f"|format(trade.pnl) }}</td>
                    <td class="{{ 'positive' if trade.return_pct > 0 else 'negative' }}">{{ "%.2f"|format(trade.return_pct * 100) }}%</td>
                    <td>{{ trade.holding_bars }}</td>
                    <td>{{ trade.exit_reason }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
    </div>

    <!-- Conclusions -->
    <div class="conclusion {{ conclusion_class }}">
        <div class="section-title" style="border-bottom-color: {{ conclusion_color }};">Conclusions</div>
        <ul style="padding-left: 20px; margin-top: 12px;">
            {% for c in conclusions %}
            <li style="margin-bottom: 8px;">{{ c }}</li>
            {% endfor %}
        </ul>
    </div>

    <div class="footer">
        <p>Generated by QuantEngine v1.0.0 — {{ generated_at }}</p>
    </div>

</div>
</body>
</html>"""


def generate_html_report(
    result: BacktestResult,
    metrics: PerformanceMetrics,
    charts: Dict[str, Optional[str]],
    output_path: str,
) -> str:
    """
    Generate a self-contained HTML report.

    Args:
        result: Backtest result.
        metrics: Computed performance metrics.
        charts: Dict of chart_name -> base64 PNG string.
        output_path: Full path for the HTML file.

    Returns:
        Path to the saved HTML file.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Auto-generate conclusions
    conclusions = _generate_conclusions(metrics)
    conclusion_class, conclusion_color = _conclusion_style(metrics)

    # Use jinja2 if available, otherwise simple string replacement
    try:
        from jinja2 import Template
        template = Template(_HTML_TEMPLATE)
        html = template.render(
            # Metadata
            symbol=result.symbol,
            strategy_name=result.strategy_name,
            strategy_version=result.strategy_version,
            timeframe=result.timeframe,
            start_date=result.start_date,
            end_date=result.end_date,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

            # Metrics
            initial_capital=metrics.initial_capital,
            final_equity=metrics.final_equity,
            total_return=metrics.total_return_pct,
            annual_return=metrics.annualized_return_pct,
            bh_return=metrics.buy_hold_return_pct,
            sharpe=metrics.sharpe_ratio,
            sortino=metrics.sortino_ratio,
            max_dd=metrics.max_drawdown_pct,
            calmar=metrics.calmar_ratio,
            num_trades=metrics.num_trades,
            winners=metrics.winning_trades,
            losers=metrics.losing_trades,
            win_rate=metrics.win_rate_pct,
            avg_profit=metrics.average_profit,
            avg_loss=metrics.average_loss,
            profit_factor=metrics.profit_factor,
            expectancy=metrics.expectancy,
            avg_holding=metrics.avg_holding_time,
            total_commission=metrics.total_commission,

            # Parameters
            params=result.strategy_params,

            # Charts
            dashboard_chart=charts.get("dashboard"),
            equity_chart=charts.get("equity_curve"),
            drawdown_chart=charts.get("drawdown"),
            signals_chart=charts.get("price_signals"),
            trades_chart=charts.get("trade_distribution"),
            monthly_chart=charts.get("monthly_returns"),

            # Trades
            trades=result.trades,

            # Conclusions
            conclusions=conclusions,
            conclusion_class=conclusion_class,
            conclusion_color=conclusion_color,
        )
    except ImportError:
        logger.warning("Jinja2 not available — generating simplified report")
        html = f"<html><body><h1>Report for {result.symbol}</h1><p>Install jinja2 for full reports.</p></body></html>"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("HTML report saved to %s", output_path)
    return output_path


def _generate_conclusions(metrics: PerformanceMetrics) -> List[str]:
    """Auto-generate conclusions based on metric thresholds."""
    c: List[str] = []

    # Return assessment
    if metrics.total_return_pct > 20:
        c.append(f"✅ Strong total return of {metrics.total_return_pct:.2f}%")
    elif metrics.total_return_pct > 0:
        c.append(f"⚡ Positive but modest return of {metrics.total_return_pct:.2f}%")
    else:
        c.append(f"❌ Negative return of {metrics.total_return_pct:.2f}% — strategy underperformed")

    # vs Buy & Hold
    alpha = metrics.total_return_pct - metrics.buy_hold_return_pct
    if alpha > 0:
        c.append(f"✅ Outperformed buy-and-hold by {alpha:.2f}% (positive alpha)")
    else:
        c.append(f"⚠️ Underperformed buy-and-hold by {abs(alpha):.2f}%")

    # Sharpe
    if metrics.sharpe_ratio > 2:
        c.append(f"✅ Excellent risk-adjusted return (Sharpe: {metrics.sharpe_ratio:.2f})")
    elif metrics.sharpe_ratio > 1:
        c.append(f"✅ Good risk-adjusted return (Sharpe: {metrics.sharpe_ratio:.2f})")
    elif metrics.sharpe_ratio > 0:
        c.append(f"⚡ Below-average risk-adjusted return (Sharpe: {metrics.sharpe_ratio:.2f})")
    else:
        c.append(f"❌ Negative Sharpe ratio ({metrics.sharpe_ratio:.2f}) — risk exceeds returns")

    # Drawdown
    if abs(metrics.max_drawdown_pct) < 10:
        c.append(f"✅ Low maximum drawdown ({metrics.max_drawdown_pct:.2f}%)")
    elif abs(metrics.max_drawdown_pct) < 20:
        c.append(f"⚡ Moderate drawdown ({metrics.max_drawdown_pct:.2f}%)")
    else:
        c.append(f"⚠️ High drawdown ({metrics.max_drawdown_pct:.2f}%) — significant capital risk")

    # Win rate
    if metrics.win_rate_pct > 55:
        c.append(f"✅ Above-average win rate ({metrics.win_rate_pct:.1f}%)")
    elif metrics.win_rate_pct > 40:
        c.append(f"⚡ Average win rate ({metrics.win_rate_pct:.1f}%)")
    elif metrics.num_trades > 0:
        c.append(f"⚠️ Low win rate ({metrics.win_rate_pct:.1f}%) — relies on large winners")

    # Profit factor
    if metrics.profit_factor > 2:
        c.append(f"✅ Strong profit factor ({metrics.profit_factor:.2f})")
    elif metrics.profit_factor > 1:
        c.append(f"⚡ Profit factor above 1 ({metrics.profit_factor:.2f})")
    elif metrics.num_trades > 0:
        c.append(f"❌ Profit factor below 1 ({metrics.profit_factor:.2f}) — losses exceed profits")

    return c


def _conclusion_style(metrics: PerformanceMetrics) -> tuple[str, str]:
    """Determine conclusion section style based on overall performance."""
    score = 0
    if metrics.total_return_pct > 0:
        score += 1
    if metrics.sharpe_ratio > 1:
        score += 1
    if abs(metrics.max_drawdown_pct) < 20:
        score += 1

    if score >= 2:
        return "conclusion-good", "var(--green)"
    elif score >= 1:
        return "conclusion-neutral", "var(--yellow)"
    else:
        return "conclusion-bad", "var(--red)"
